"""Import attributed UCI reference data into new, isolated SQLite sources.

Only creates attributed SQLite sources; existing data is never replaced. Raw downloads
and a SHA-256 manifest make the transformations reproducible.
"""

import csv
import hashlib
import io
import json
import sqlite3
import zipfile
from datetime import datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / "data" / "dashboard_reference_sources"
SOURCES = {
    "itsm": (
        498,
        "incident+management+process+enriched+event+log",
        "https://doi.org/10.24432/C57S4H",
    ),
    "energy": (374, "appliances+energy+prediction", "https://doi.org/10.24432/C5VC8G"),
    "maintenance": (
        601,
        "ai4i+2020+predictive+maintenance+dataset",
        "https://doi.org/10.24432/C5HS5C",
    ),
    "students": (320, "student+performance", "https://doi.org/10.24432/C5TG7T"),
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


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Id"] = "001"
    existing = {
        r["db_name"]
        for r in session.get(
            "http://127.0.0.1:5671/api/v2/serve/datasources", timeout=30
        ).json()["data"]
    }
    manifest = []
    for key, (number, slug, citation) in SOURCES.items():
        raw = DEST / f"{key}.zip"
        url = f"https://archive.ics.uci.edu/static/public/{number}/{slug}.zip"
        if not raw.exists():
            response = session.get(url, timeout=120)
            response.raise_for_status()
            raw.write_bytes(response.content)
        blob = raw.read_bytes()
        rows, source_rows, notes = derive(key, blob)
        database = DEST / f"{key}.sqlite"
        if not database.exists():
            with sqlite3.connect(database) as connection:
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
                    [tuple(r.values()) for r in rows],
                )
                connection.execute("CREATE UNIQUE INDEX fact_entity ON facts(entity)")
                connection.execute(
                    (
                        "CREATE TABLE source_metadata (url TEXT, citation TEXT,"
                        " license TEXT, notes TEXT)"
                    )
                )
                connection.execute(
                    "INSERT INTO source_metadata VALUES (?,?,?,?)",
                    (url, citation, "CC BY 4.0", notes),
                )
        name = f"sqlite_{key}"
        if name not in existing:
            response = session.post(
                "http://127.0.0.1:5671/api/v2/serve/datasources",
                json={
                    "type": "sqlite",
                    "params": {"path": str(database)},
                    "description": notes + " " + citation + " CC BY 4.0",
                },
                timeout=90,
            )
            response.raise_for_status()
            assert response.json()["success"], response.json()
            assert response.json()["data"]["db_name"] == name, (
                "Unexpected source identifier"
            )
        item = dict(
            name=name,
            download=url,
            citation=citation,
            license="CC BY 4.0",
            sha256=hashlib.sha256(blob).hexdigest(),
            source_rows=source_rows,
            rows=len(rows),
            notes=notes,
            database=database.relative_to(ROOT).as_posix(),
        )
        manifest.append(item)
        (DEST / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(name, source_rows, "->", len(rows), flush=True)


if __name__ == "__main__":
    main()
