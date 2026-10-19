"""Generate attributed UCI reference data in isolated SQLite files.

Only creates attributed SQLite sources; existing data is never replaced. Raw downloads
and a SHA-256 manifest make the transformations reproducible. Backend registration
requires --register and --api-base.
"""

import argparse
import csv
import hashlib
import io
import json
import os
import sqlite3
import zipfile
from contextlib import closing
from datetime import datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
# Pinned source provenance; see README.md for citations and transformations.
SOURCES = {
    "itsm": {
        "name": "sqlite_itsm",
        "download": "https://archive.ics.uci.edu/static/public/498/incident+management+process+enriched+event+log.zip",
        "citation": "https://doi.org/10.24432/C57S4H",
        "license": "CC BY 4.0",
        "sha256": "6294e29a311647306bfdfc85783f7df66517c197b9cd49aa5ee36ba9c525d1d6",
        "source_rows": 141712,
        "rows": 24918,
        "notes": (
            "按工单编号取最后一次更新；解决耗时=(resolved_at-opened_at)/3600，"
            "缺失或负时长不计平均。SLA 仅展示源 made_sla 为 True 的比例，"
            "不自行推断 SLA 阈值。"
        ),
    },
    "energy": {
        "name": "sqlite_energy",
        "download": "https://archive.ics.uci.edu/static/public/374/appliances+energy+prediction.zip",
        "citation": "https://doi.org/10.24432/C5VC8G",
        "license": "CC BY 4.0",
        "sha256": "2fccf354445d886e7917620b0195db1f3e3e34d5a067a93b844694a4c561255a",
        "source_rows": 19735,
        "rows": 19735,
        "notes": (
            "比利时一栋实验住宅，2016 年每 10 分钟采样；"
            "Appliances 与 lights 为 Wh，分别除以 1000 后汇总为 kWh。"
            "最后一天为部分采样日。"
        ),
    },
    "maintenance": {
        "name": "sqlite_maintenance",
        "download": "https://archive.ics.uci.edu/static/public/601/ai4i+2020+predictive+maintenance+dataset.zip",
        "citation": "https://doi.org/10.24432/C5HS5C",
        "license": "CC BY 4.0",
        "sha256": "f601f14294bcf190f9d720676b7f0aea46a26cde9ab8ebc7b4f8174d9d26b252",
        "source_rows": 10000,
        "rows": 10000,
        "notes": (
            "AI4I 2020 为 UCI 提供的合成工业数据，非真实生产记录。"
            "样本组按 UDI 每 1000 条划分，不能解释为时间趋势。"
            "故障比例按 Machine failure=1 统计。"
        ),
    },
    "students": {
        "name": "sqlite_students",
        "download": "https://archive.ics.uci.edu/static/public/320/student+performance.zip",
        "citation": "https://doi.org/10.24432/C5TG7T",
        "license": "CC BY 4.0",
        "sha256": "82ae9d66437b9808df42e8c89d2bb179c46e9cfbcf06f38abc1d20b3b747e177",
        "source_rows": 649,
        "rows": 649,
        "notes": (
            "只使用两所葡萄牙中学的葡语课程数据，每行一名学生，"
            "避免与数学课程重复计人。成绩范围 0–20，达标线定义为 >=10；"
            "缺课按原始 absences 计。数据没有逐日日期。"
        ),
    },
}


def parse_date(value):
    if not value or value == "?":
        return None
    for pattern in ("%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, pattern)
        except ValueError:
            pass
    raise ValueError("Unrecognized source date: " + value)


def csv_rows(blob, name, separator=","):
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        return list(
            csv.DictReader(
                io.StringIO(archive.read(name).decode("utf-8-sig")), delimiter=separator
            )
        )


def derive(key, blob):
    if key == "itsm":
        events = csv_rows(blob, "incident_event_log.csv")
        latest = {}
        for row in events:
            stamp = (parse_date(row["sys_updated_at"]), int(row["sys_mod_count"]))
            if row["number"] not in latest or stamp >= latest[row["number"]][0]:
                latest[row["number"]] = (stamp, row)
        output = []
        for _, row in latest.values():
            opened, resolved = (
                parse_date(row["opened_at"]),
                parse_date(row["resolved_at"]),
            )
            hours = (
                (resolved - opened).total_seconds() / 3600
                if resolved and opened
                else None
            )
            output.append(
                dict(
                    event_date=opened.date().isoformat(),
                    year=str(opened.year),
                    period=opened.strftime("%Y-%m"),
                    segment=row["priority"],
                    category=row["assignment_group"].replace("?", "未记录"),
                    entity=row["number"],
                    value=1.0,
                    aux=hours if hours is not None and hours >= 0 else None,
                    sla_true=100.0
                    if row["made_sla"].lower() == "true"
                    else 0.0
                    if row["made_sla"].lower() == "false"
                    else None,
                    reopen=float(row["reopen_count"]),
                    state=row["incident_state"],
                    closed=100.0 if row["incident_state"].lower() == "closed" else 0.0,
                )
            )
        return (
            output,
            len(events),
            (
                "按工单编号取最后一次更新；解决耗时=(resolved_at-opened"
                "_at)/3600，缺失或负时长不"
                "计平均。SLA 仅展示源 made_sla 为 True 的比例，不自行推断 SLA 阈值。"
            ),
        )
    if key == "energy":
        rows = csv_rows(blob, "energydata_complete.csv")
        return (
            [
                dict(
                    event_date=r["date"][:10],
                    year=r["date"][:7],
                    period=r["date"][:10],
                    segment="周末"
                    if parse_date(r["date"]).weekday() >= 5
                    else "工作日",
                    category=r["date"][11:13] + "时",
                    entity=r["date"],
                    value=float(r["Appliances"]) / 1000,
                    aux=float(r["lights"]) / 1000,
                    temperature=float(r["T_out"]),
                )
                for r in rows
            ],
            len(rows),
            (
                "比利时一栋实验住宅，2016 年每 10 分钟采样；Appliances "
                "与 lights 为 Wh，分别除"
                "以 1000 后汇总为 kWh。最后一天为部分采样日。"
            ),
        )
    if key == "maintenance":
        rows = csv_rows(blob, "ai4i2020.csv")
        return (
            [
                dict(
                    event_date=None,
                    year="合成样本",
                    period=f"{(int(r['UDI']) - 1) // 1000 + 1:02d} 样本组",
                    segment=r["Type"],
                    category="故障" if r["Machine failure"] == "1" else "正常",
                    entity=r["UDI"],
                    value=1.0,
                    aux=float(r["Machine failure"]) * 100,
                    wear=float(r["Tool wear [min]"]),
                    rpm=float(r["Rotational speed [rpm]"]),
                )
                for r in rows
            ],
            len(rows),
            (
                "AI4I 2020 为 UCI 提供的合成工业数据，非真实生产记录。"
                "样本组按 UDI 每 1000 条划分，"
                "不能解释为时间趋势。故障比例按 Machine failure=1 统计。"
            ),
        )
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        inner = archive.read("student.zip")
    rows = csv_rows(inner, "student-por.csv", ";")
    return (
        [
            dict(
                event_date=None,
                year="葡语课程",
                period="期末",
                segment=r["school"],
                category={
                    "1": "少于2小时",
                    "2": "2至5小时",
                    "3": "5至10小时",
                    "4": "超过10小时",
                }[r["studytime"]],
                entity=str(i + 1),
                value=float(r["G3"]),
                aux=float(r["absences"]),
                first_grade=float(r["G1"]),
                second_grade=float(r["G2"]),
                pass_score=100.0 if float(r["G3"]) >= 10 else 0.0,
            )
            for i, r in enumerate(rows)
        ],
        len(rows),
        (
            "只使用两所葡萄牙中学的葡语课程数据，每行一名学生，避免"
            "与数学课程重复计人。成绩范围 0–20，达标线定义为 "
            ">=10；缺课按原始 absences 计。数据没有逐日日期。"
        ),
    )


def write_database(database, rows, metadata):
    fields = list(rows[0])
    numeric = {
        "value",
        "aux",
        "sla_true",
        "reopen",
        "closed",
        "temperature",
        "wear",
        "rpm",
        "first_grade",
        "second_grade",
        "pass_score",
    }
    expected = [tuple(row.values()) for row in rows]
    if database.exists():
        with closing(
            sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
        ) as connection:
            actual = connection.execute("SELECT * FROM facts ORDER BY rowid").fetchall()
            source = connection.execute("SELECT * FROM source_metadata").fetchall()
        if actual != expected or source != [metadata]:
            raise ValueError(
                f"Existing database differs; preserved without changes: {database}"
            )
        return
    # Exclusive creation protects an existing user's database from replacement.
    with database.open("xb"):
        pass
    try:
        with closing(sqlite3.connect(database)) as connection, connection:
            connection.execute(
                "CREATE TABLE facts ("
                + ",".join(
                    f'"{field}" ' + ("REAL" if field in numeric else "TEXT")
                    for field in fields
                )
                + ")"
            )
            connection.executemany(
                "INSERT INTO facts VALUES (" + ",".join("?" for _ in fields) + ")",
                expected,
            )
            connection.execute("CREATE UNIQUE INDEX fact_entity ON facts(entity)")
            connection.execute(
                "CREATE TABLE source_metadata "
                "(url TEXT, citation TEXT, license TEXT, notes TEXT)"
            )
            connection.execute("INSERT INTO source_metadata VALUES (?,?,?,?)", metadata)
    except Exception:
        database.unlink()
        raise


def generate_sources(output, cache_dir, *, offline=False, source_keys=None):
    """Generate and verify data without contacting a DB-GPT backend."""
    output = Path(output).resolve()
    cache_dir = Path(cache_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    generated = []
    for key in source_keys or SOURCES:
        spec = SOURCES[key]
        raw = cache_dir / f"{key}.zip"
        if raw.exists():
            blob = raw.read_bytes()
        else:
            if offline:
                raise FileNotFoundError(f"Offline source archive missing: {raw}")
            response = requests.get(spec["download"], timeout=120)
            response.raise_for_status()
            blob = response.content
        digest = hashlib.sha256(blob).hexdigest()
        if digest != spec["sha256"]:
            raise ValueError(f"SHA-256 mismatch for {key}; no database generated")
        if not raw.exists():
            with raw.open("xb") as stream:
                stream.write(blob)
        rows, source_rows, notes = derive(key, blob)
        if source_rows != spec["source_rows"] or len(rows) != spec["rows"]:
            raise ValueError(f"Unexpected source or derived row count for {key}")
        database = output / f"{key}.sqlite"
        write_database(
            database, rows, (spec["download"], spec["citation"], spec["license"], notes)
        )
        generated.append(
            {
                **spec,
                "database": database.name,
                "database_sha256": hashlib.sha256(database.read_bytes()).hexdigest(),
            }
        )
        print(
            f"{key}: {source_rows} -> {len(rows)} rows; checksum verified", flush=True
        )
    manifest = output / "manifest.json"
    manifest.write_text(
        json.dumps(generated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return generated


def register_sources(manifest, output, api_base, user_id=None):
    """Register only when explicitly requested against the caller's chosen server."""
    session = requests.Session()
    if os.environ.get("DBGPT_API_KEY"):
        session.headers["Authorization"] = f"Bearer {os.environ['DBGPT_API_KEY']}"
    if user_id:
        session.headers["User-Id"] = user_id
    endpoint = api_base.rstrip("/") + "/api/v2/serve/datasources"
    response = session.get(endpoint, timeout=30)
    response.raise_for_status()
    body = response.json()
    if not body.get("success"):
        raise RuntimeError(body.get("err_msg") or "Cannot list data sources")
    existing = {record["db_name"] for record in body["data"]}
    for item in manifest:
        if item["name"] in existing:
            print(f"{item['name']}: already registered; left unchanged")
            continue
        database = (Path(output) / item["database"]).resolve()
        response = session.post(
            endpoint,
            json={
                "type": "sqlite",
                "params": {"path": str(database)},
                "description": f"{item['notes']} {item['citation']} {item['license']}",
            },
            timeout=90,
        )
        response.raise_for_status()
        result = response.json()
        if not result.get("success") or result["data"]["db_name"] != item["name"]:
            raise RuntimeError(result.get("err_msg") or "Unexpected source identifier")
        print(f"{item['name']}: registered")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "examples/dashboard/generated/reference-sources",
    )
    parser.add_argument(
        "--cache-dir", type=Path, help="Directory of the four pinned UCI ZIP archives"
    )
    parser.add_argument(
        "--offline", action="store_true", help="Use verified cached archives only"
    )
    parser.add_argument(
        "--sources", nargs="+", choices=list(SOURCES), help="Generate a subset"
    )
    parser.add_argument(
        "--register",
        action="store_true",
        help="Explicitly register generated files with DB-GPT",
    )
    parser.add_argument(
        "--api-base",
        help="DB-GPT origin; required with --register; "
        "server must access the output path",
    )
    parser.add_argument(
        "--user-id", help="Optional User-Id header for explicit registration"
    )
    args = parser.parse_args()
    if args.register and not args.api_base:
        parser.error("--register requires --api-base")
    if not args.register and (args.api_base or args.user_id):
        parser.error("--api-base and --user-id require --register")
    output = args.output.resolve()
    manifest = generate_sources(
        output,
        args.cache_dir or output / "raw",
        offline=args.offline,
        source_keys=args.sources,
    )
    if args.register:
        register_sources(manifest, output, args.api_base, args.user_id)


if __name__ == "__main__":
    main()
