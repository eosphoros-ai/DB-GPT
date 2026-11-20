"""Import published case semantics through REST into a dedicated demo space."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen

if __package__:
    from .build_case import CONNECTION, seed
else:
    from build_case import CONNECTION, seed


def request(base: str, path: str, payload: dict | None = None):
    data = (
        json.dumps(payload, ensure_ascii=False).encode()
        if payload is not None
        else None
    )
    req = Request(
        base.rstrip("/") + "/api/v1/semantic/" + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST" if payload is not None else "GET",
    )
    with urlopen(req, timeout=60) as response:
        result = json.load(response)
    if result.get("success") is not True:
        raise RuntimeError(f"{path}: {result}")
    return result["data"]


def import_case(base: str, ds_id: int, report: Path) -> None:
    """Refuse existing content and any space outside the dedicated mock DB."""
    space = request(base, f"spaces/{ds_id}")
    if space["conn_id"] != CONNECTION:
        raise ValueError(f"Only dedicated connection {CONNECTION!r} is supported")
    for resource in ("entries", "metrics", "examples"):
        if request(base, f"spaces/{ds_id}/{resource}"):
            raise ValueError(
                f"Demo space has existing {resource}; refusing to duplicate"
            )
    if report.exists():
        raise FileExistsError(report)
    request(base, f"spaces/{ds_id}/sync", {})
    request(base, f"spaces/{ds_id}/activate", {"run_draft_generation": False})
    tables = {t["table_name"]: t for t in request(base, f"spaces/{ds_id}/tables")}
    fixture = seed()
    imported = {
        "space_id": ds_id,
        "connection": CONNECTION,
        "entries": [],
        "metrics": [],
    }
    # Persist IDs after each write so partial imports can be reviewed if an API fails.
    report.parent.mkdir(parents=True, exist_ok=True)

    def save() -> None:
        report.write_text(json.dumps(imported, ensure_ascii=False, indent=2) + "\n")

    save()
    for entry in fixture["entries"]:
        table = tables[entry["table"]]
        target = table["id"]
        if entry["column"]:
            columns = request(base, f"tables/{table['id']}/columns?ds_id={ds_id}")
            target = next(
                c["id"] for c in columns if c["column_name"] == entry["column"]
            )
        payload = {
            **entry,
            "target_id": target,
            "entry_type": "column" if entry["column"] else "table",
            "entry_definition": json.dumps(
                entry["entry_definition"], ensure_ascii=False
            ),
            "user": "semantic_case_importer",
        }
        created = request(base, f"spaces/{ds_id}/entries", payload)
        imported["entries"].append({**created, "name": entry["entry_name"]})
        save()
        if entry["publish"]:
            request(base, f"entries/{created['id']}/review", {"action": "confirm"})
    # REST has no metric edit API: install v2 as the canonical current definition,
    # v1 as a clearly named comparison metric, not a fabricated historical snapshot.
    for metric in fixture["metrics"]:
        payload = {**metric}
        if metric["metric_name"] == "净实收" and metric["case_version"] == 1:
            payload["metric_name"] = "净实收_含运费对照"
        payload["metric_definition"] = json.dumps(
            metric["metric_definition"], ensure_ascii=False
        )
        payload["user"] = "semantic_case_importer"
        created = request(base, f"spaces/{ds_id}/metrics", payload)
        imported["metrics"].append(
            {
                **created,
                "business_case_version": metric["case_version"],
            }
        )
        save()
        request(
            base,
            f"metrics/{created['id']}/publish",
            {
                "change_note": (
                    f"案例业务口径v{metric['case_version']}；首次导入发布版本为1"
                ),
            },
        )
    imported["status"] = "completed"
    imported["limitations"] = [
        "业务口径v2首次导入的发布版本为1；同指标历史v1/v2仅在隔离库验证。",
        "未触发LLM草稿/关系发现；外键参考schema.sql，血缘参考view_lineage.sql。",
    ]
    save()
    print(f"Imported demo semantics into space {ds_id}; report: {report}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:5670")
    parser.add_argument("--space-id", type=int, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    import_case(args.base_url, args.space_id, args.report)
