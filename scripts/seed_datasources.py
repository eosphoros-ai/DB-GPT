"""Seed ALL DB-GPT datasources from hotel-be DMS config.

Reads the DMS.environments section from hotel-be config YAML and registers:
  - MySQL instances as DB-GPT datasources (type=mysql)
  - TDengine instances as DB-GPT datasources (type=tdengine)
  - Redis instances as env vars for the Redis tool plugin
  - MinIO instances as env vars for the MinIO tool plugin

Idempotent: skips if a datasource with the same db_name already exists.

Usage:
    python scripts/seed_datasources.py
    python scripts/seed_datasources.py --env prod
    python scripts/seed_datasources.py --all-envs
    python scripts/seed_datasources.py --dry-run
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error

import yaml


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def api_get(base: str, path: str) -> dict:
    url = f"{base}{path}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"code": e.code, "data": None}
    except Exception as e:
        return {"code": -1, "msg": str(e), "data": None}


def api_post(base: str, path: str, body: dict) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"{base}{path}", data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"code": e.code, "msg": e.read().decode("utf-8", errors="replace")}
    except Exception as e:
        return {"code": -1, "msg": str(e)}


# ---------------------------------------------------------------------------
# DSN parser
# ---------------------------------------------------------------------------

def parse_mysql_dsn(dsn: str) -> dict | None:
    """Parse Go-style DSN: user:pass@tcp(host:port)/dbname?params"""
    try:
        creds, rest = dsn.split("@tcp(", 1)
        hp_db = rest.split(")/", 1)
        host_port = hp_db[0]
        dbname = hp_db[1].split("?")[0]
        user, pwd = creds.split(":", 1)
        host, port = host_port.rsplit(":", 1)
        return {"host": host, "port": port, "user": user, "pwd": pwd, "dbname": dbname}
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Extract ALL datasources from DMS config
# ---------------------------------------------------------------------------

def extract_all_datasources(config: dict, envs: list[str] | None = None) -> list[dict]:
    """Extract all datasources from DMS.environments, grouped by environment.

    Returns list of dicts, each with keys: env, type, db_name, db_type, db_host,
    db_port, db_user, db_pwd, comment, plus extra type-specific keys.
    """
    dms = config.get("DMS", {})
    results = []

    for environment in dms.get("environments", []):
        env_name = environment.get("name", "")
        if envs and env_name not in envs:
            continue

        for ds in environment.get("dataSources", []):
            ds_type = ds.get("type", "")
            ds_name = ds.get("name", "")
            # Unique db_name: env_prefix_original_name  (avoid collision across envs)
            unique_name = f"{env_name}_{ds_name}"

            entry = {
                "env": env_name,
                "source_type": ds_type,       # mysql/redis/tdengine/minio
                "ds_name": ds_name,
                "unique_name": unique_name,
            }

            if ds_type == "mysql":
                parsed = parse_mysql_dsn(ds.get("mysql", {}).get("dsn", ""))
                if parsed:
                    entry.update({
                        "db_type": "mysql",
                        "db_name": parsed["dbname"],       # real DB name for chat_data
                        "db_host": parsed["host"],
                        "db_port": parsed["port"],
                        "db_user": parsed["user"],
                        "db_pwd": parsed["pwd"],
                        "comment": f"[{env_name}] {ds_name} ({parsed['dbname']})",
                    })
                    results.append(entry)

            elif ds_type == "tdengine":
                td = ds.get("tdengine", {})
                entry.update({
                    "db_type": "tdengine",
                    "db_name": td.get("database", "hblog_ns"),
                    "db_host": td.get("host", ""),
                    "db_port": str(td.get("port", 6030)),
                    "db_user": td.get("user", "root"),
                    "db_pwd": td.get("password", ""),
                    "comment": f"[{env_name}] {ds_name}",
                    "ext_config": json.dumps({"driver": td.get("driver", "taosSql")}),
                })
                results.append(entry)

            elif ds_type == "redis":
                rd = ds.get("redis", {})
                addr = rd.get("addr", "")
                host, port = (addr.split(":", 1) + ["6379"])[:2]
                entry.update({
                    "redis_host": host,
                    "redis_port": port,
                    "redis_password": rd.get("password", ""),
                    "redis_db": rd.get("db", 0),
                    "comment": f"[{env_name}] {ds_name}",
                })
                results.append(entry)

            elif ds_type == "minio":
                mn = ds.get("minio", {})
                endpoints = mn.get("endpoints", [])
                entry.update({
                    "minio_endpoints": endpoints,
                    "minio_access_key": mn.get("accessKey", ""),
                    "minio_secret_key": mn.get("secretKey", ""),
                    "minio_use_ssl": mn.get("useSSL", False),
                    "minio_bucket": ds.get("bucket", ""),
                    "comment": f"[{env_name}] {ds_name}",
                })
                results.append(entry)

    return results


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

def fetch_existing_datasource_names(api_base: str) -> set[str]:
    resp = api_get(api_base, "/api/v2/serve/datasources")
    names = set()
    data = resp.get("data")
    if not data:
        return names
    items = data.get("items", data) if isinstance(data, dict) else data
    for item in (items if isinstance(items, list) else []):
        if isinstance(item, dict):
            names.add(item.get("db_name", item.get("name", "")))
    return names


def register_sql_datasource(api_base: str, ds: dict, existing: set[str], dry_run: bool) -> str:
    """Register a MySQL or TDengine datasource. Returns 'created'|'skipped'|'failed'."""
    db_name = ds["db_name"]
    if db_name in existing:
        print(f"  SKIP  {db_name} (exists)")
        return "skipped"

    body = {
        "db_type": ds["db_type"],
        "db_name": db_name,
        "db_host": ds["db_host"],
        "db_port": ds["db_port"],
        "db_user": ds["db_user"],
        "db_pwd": ds["db_pwd"],
        "comment": ds["comment"],
    }
    if ds.get("ext_config"):
        body["ext_config"] = ds["ext_config"]

    if dry_run:
        print(f"  DRY   {db_name} ({ds['db_type']} @ {ds['db_host']}:{ds['db_port']})")
        return "created"

    resp = api_post(api_base, "/api/v2/serve/datasources", body)
    if resp.get("msg") is None or resp.get("code") in (200, 0):
        print(f"  OK    {db_name} ({ds['db_type']} @ {ds['db_host']}:{ds['db_port']})")
        return "created"
    else:
        print(f"  FAIL  {db_name}: {resp.get('msg', resp)}")
        return "failed"


def generate_env_file(datasources: list[dict], env_filter: list[str] | None, output_path: str):
    """Generate a .env file with Redis/MinIO connection info for the tool plugins.

    When multiple instances exist, only the first matching instance is used
    (DB-GPT tools read from single env vars). For multi-instance, the operator
    can switch by re-exporting the env vars.
    """
    lines = [
        "# Auto-generated DB-GPT tool environment variables",
        "# Source this file before starting DB-GPT: set -a; source dbgpt-tools.env; set +a",
        "",
    ]

    seen_redis = False
    seen_minio = False

    for ds in datasources:
        if env_filter and ds.get("env") not in env_filter:
            continue

        if ds["source_type"] == "redis" and not seen_redis:
            lines.append(f"# Redis [{ds['env']}] {ds['ds_name']}")
            lines.append(f"REDIS_HOST={ds['redis_host']}")
            lines.append(f"REDIS_PORT={ds['redis_port']}")
            lines.append(f"REDIS_PASSWORD={ds['redis_password']}")
            lines.append(f"REDIS_DB={ds['redis_db']}")
            lines.append("")
            seen_redis = True

        elif ds["source_type"] == "minio" and not seen_minio:
            endpoints = ds.get("minio_endpoints", [])
            lines.append(f"# MinIO [{ds['env']}] {ds['ds_name']}")
            lines.append(f"MINIO_ENDPOINT={endpoints[0] if endpoints else ''}")
            lines.append(f"MINIO_ACCESS_KEY={ds['minio_access_key']}")
            lines.append(f"MINIO_SECRET_KEY={ds['minio_secret_key']}")
            lines.append(f"MINIO_SECURE={'true' if ds.get('minio_use_ssl') else 'false'}")
            lines.append("")
            seen_minio = True

    # If there are multiple instances, list them all as commented alternatives
    multi_redis = [d for d in datasources if d["source_type"] == "redis" and (not env_filter or d.get("env") in env_filter)]
    multi_minio = [d for d in datasources if d["source_type"] == "minio" and (not env_filter or d.get("env") in env_filter)]

    if len(multi_redis) > 1:
        lines.append("# --- Alternative Redis instances (uncomment to switch) ---")
        for rd in multi_redis:
            prefix = "" if rd == multi_redis[0] else "# "
            lines.append(f"{prefix}# [{rd['env']}] {rd['ds_name']}")
            if rd != multi_redis[0]:
                lines.append(f"# REDIS_HOST={rd['redis_host']}")
                lines.append(f"# REDIS_PORT={rd['redis_port']}")
                lines.append(f"# REDIS_PASSWORD={rd['redis_password']}")
                lines.append(f"# REDIS_DB={rd['redis_db']}")
        lines.append("")

    if len(multi_minio) > 1:
        lines.append("# --- Alternative MinIO instances (uncomment to switch) ---")
        for mn in multi_minio:
            if mn != multi_minio[0]:
                lines.append(f"# [{mn['env']}] {mn['ds_name']}")
                lines.append(f"# MINIO_ENDPOINT={mn['minio_endpoints'][0] if mn['minio_endpoints'] else ''}")
                lines.append(f"# MINIO_ACCESS_KEY={mn['minio_access_key']}")
                lines.append(f"# MINIO_SECRET_KEY={mn['minio_secret_key']}")
        lines.append("")

    with open(output_path, "w") as f:
        f.write("\n".join(lines))
    print(f"\nGenerated tool env file: {output_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Seed ALL DB-GPT datasources from hotel-be DMS config")
    parser.add_argument("--api-base", default="http://localhost:5670")
    parser.add_argument("--env", default=None, help="Seed only this environment (dev|uat|prod). Default: all")
    parser.add_argument("--config-yaml", default=None, help="hotel-be config YAML path")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--env-file", default=None, help="Output .env file for Redis/MinIO tool vars")
    args = parser.parse_args()

    # Resolve config
    config_yaml = args.config_yaml
    if not config_yaml:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        for candidate in [
            os.path.join(script_dir, "..", "..", "api", "config", "config.dev.yaml"),
            os.path.join(script_dir, "..", "..", "api", "config", "config.uat.yaml"),
        ]:
            if os.path.exists(candidate):
                config_yaml = candidate
                break
    if not config_yaml or not os.path.exists(config_yaml):
        print("ERROR: Cannot find hotel-be config YAML. Use --config-yaml.")
        sys.exit(1)

    with open(config_yaml) as f:
        config = yaml.safe_load(f)

    envs = [args.env] if args.env else None
    all_ds = extract_all_datasources(config, envs)

    if not all_ds:
        print("No datasources found in DMS config.")
        sys.exit(0)

    # Summary
    print(f"Found {len(all_ds)} datasources:")
    for ds in all_ds:
        tag = ds["source_type"]
        name = ds.get("db_name") or ds.get("ds_name", "")
        env = ds["env"]
        host = ds.get("db_host") or ds.get("redis_host") or ds.get("minio_endpoints", ["?"])[0]
        print(f"  [{env:4s}] {tag:10s} {name:20s} @ {host}")
    print()

    # Register SQL-type datasources (MySQL, TDengine)
    # Deduplicate by (db_type, db_name) — same real DB from different envs
    # only registered once. E.g. dev/uat share hoteldev on same MySQL host.
    sql_ds = [d for d in all_ds if d["source_type"] in ("mysql", "tdengine")]
    seen_sql = set()
    unique_sql = []
    for ds in sql_ds:
        key = (ds["db_type"], ds["db_name"])
        if key not in seen_sql:
            seen_sql.add(key)
            unique_sql.append(ds)
        else:
            print(f"  DEDUP [{ds['env']}] {ds['db_type']}:{ds['db_name']} (same as earlier env, skip)")

    stats = {"created": 0, "skipped": 0, "failed": 0}
    if unique_sql:
        print(f"\n--- Registering {len(unique_sql)} unique SQL datasources ---")
        existing = fetch_existing_datasource_names(args.api_base)
        for ds in unique_sql:
            result = register_sql_datasource(args.api_base, ds, existing, args.dry_run)
            stats[result] += 1
    else:
        print("No SQL datasources to register.")

    # Generate env file for tool datasources (Redis, MinIO)
    tool_ds = [d for d in all_ds if d["source_type"] in ("redis", "minio")]
    if tool_ds:
        env_file = args.env_file
        if not env_file:
            env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dbgpt-tools.env")
        if not args.dry_run:
            generate_env_file(tool_ds, envs, env_file)
        else:
            print(f"\nDRY-RUN: would generate env file at {env_file} with {len(tool_ds)} tool entries")

    print(f"\nResult: {stats['created']} created, {stats['skipped']} skipped, {stats['failed']} failed")
    if stats["failed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
