"""Install two source-backed examples for the Sive research layouts.

The UCI Cleveland file is public historical research data (CC BY 4.0).
Voice observations are deterministic synthetic examples, not market forecasts.
Existing files and registrations are preserved on repeated runs.
"""

import argparse
import csv
import hashlib
import io
import json
import random
import sqlite3
import zipfile
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / "data" / "dashboard_research_sources"
UCI_URL = "https://archive.ics.uci.edu/static/public/45/heart%2Bdisease.zip"
UCI_CITATION = (
    "Janosi, Steinbrunn, Pfisterer & Detrano (1989). Heart Disease. "
    "UCI Machine Learning Repository. DOI:10.24432/C52P4X. CC BY 4.0."
)


def heart_rows(raw_text):
    rows = []
    chest = {1: "典型心绞痛", 2: "非典型心绞痛", 3: "非心绞痛性胸痛", 4: "无症状"}
    for i, values in enumerate(csv.reader(io.StringIO(raw_text))):
        if not values:
            continue
        values = [None if v == "?" else float(v) for v in values]
        age, sex, cp, bp, chol, _, _, heart_rate, exang, _, slope, _, _, target = values
        positive = int(target > 0)
        rows.append(
            dict(
                event_date=None,
                year="Cleveland",
                period=f"{int(age // 10) * 10}–{int(age // 10) * 10 + 9}岁",
                segment="男性" if sex == 1 else "女性",
                category=chest[int(cp)],
                entity=f"研究样本{i + 1:04d}",
                value=1,
                aux=positive,
                age=age,
                bp=bp,
                max_hr=heart_rate,
                cholesterol=chol if chol and chol > 0 else None,
                slope={1: "上升型", 2: "平坦型", 3: "下降型"}[int(slope)],
                exang="阳性" if exang else "阴性",
                diagnosis="目标阳性" if positive else "目标阴性",
            )
        )
    return rows


def voice_rows():
    rng = random.Random("dbgpt-voice-lab-v1")
    rows = []
    for year in range(2022, 2027):
        for month in range(1, 9 if year == 2026 else 13):
            age = (year - 2022) + month / 12
            for scenario in ("服务咨询", "设备控制", "内容检索"):
                total = int(14500 * (1 + age * 0.42) * rng.uniform(0.85, 1.18))
                share = min(0.68, 0.20 + age * 0.085 + rng.uniform(-0.03, 0.03))
                voice = int(total * share)
                evaluation = max(1, voice // 12)
                passed = int(
                    evaluation
                    * min(0.94, 0.58 + age * 0.068 + rng.uniform(-0.035, 0.035))
                )
                latency = max(180, 1600 / (1 + age * 0.9) * rng.uniform(0.90, 1.1))
                for channel, count in (
                    ("语音交互", voice),
                    ("其他交互", total - voice),
                ):
                    is_voice = channel == "语音交互"
                    rows.append(
                        dict(
                            event_date=f"{year}-{month:02d}-01",
                            year=str(year),
                            period=f"{year}-{month:02d}",
                            segment=scenario,
                            category=channel,
                            entity=scenario,
                            value=count,
                            aux=count if is_voice else 0,
                            latency_total=round(latency * count, 3) if is_voice else 0,
                            evaluations=evaluation if is_voice else 0,
                            passed=passed if is_voice else 0,
                        )
                    )
    return rows


def install_database(key, rows, metadata):
    path = DEST / (key + ".sqlite")
    if not path.exists():
        columns = list(rows[0])
        numeric = {k for r in rows for k, v in r.items() if isinstance(v, (int, float))}
        with sqlite3.connect(path) as db:
            db.execute(
                "CREATE TABLE facts ("
                + ",".join(
                    f'"{k}" ' + ("REAL" if k in numeric else "TEXT") for k in columns
                )
                + ")"
            )
            db.executemany(
                "INSERT INTO facts VALUES (" + ",".join("?" for _ in columns) + ")",
                [tuple(r.values()) for r in rows],
            )
            db.execute("CREATE INDEX fact_scope ON facts(year, segment)")
            db.execute("CREATE TABLE source_metadata (metadata TEXT)")
            db.execute(
                "INSERT INTO source_metadata VALUES (?)",
                (json.dumps(metadata, ensure_ascii=False),),
            )
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--register", action="store_true")
    parser.add_argument("--base", default="http://127.0.0.1:5671")
    args = parser.parse_args()
    DEST.mkdir(parents=True, exist_ok=True)
    raw_path = DEST / "processed.cleveland.data"
    if not raw_path.exists():
        response = requests.get(UCI_URL, timeout=60)
        response.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            filename = next(
                n for n in archive.namelist() if n.endswith("processed.cleveland.data")
            )
            raw_path.write_bytes(archive.read(filename))
    heart = heart_rows(raw_path.read_text(encoding="utf-8"))
    assert len(heart) == 303
    sources = [
        (
            "heart_cleveland",
            heart,
            dict(
                kind="public",
                source_url=UCI_URL,
                citation=UCI_CITATION,
                notes=(
                    "Cleveland 历史研究样本；目标阳性为原 num>0。只描述样本关联，"
                    "不作为个体诊断或总体患病率。保留缺失值。"
                ),
            ),
        ),
        (
            "voice_lab",
            voice_rows(),
            dict(
                kind="synthetic",
                seed="dbgpt-voice-lab-v1",
                notes=(
                    "2022–2026 年合成语音交互样本，非真实产品评测或行业预测；"
                    "均值按交互数加权，比例按汇总分子分母计算。"
                ),
            ),
        ),
    ]
    session = requests.Session()
    session.headers["User-Id"] = "001"
    existing = set()
    if args.register:
        response = session.get(args.base + "/api/v2/serve/datasources", timeout=30)
        response.raise_for_status()
        existing = {x["db_name"] for x in response.json()["data"]}
    manifest = []
    for key, rows, metadata in sources:
        path = install_database(key, rows, metadata)
        name = "sqlite_" + key
        if args.register and name not in existing:
            response = session.post(
                args.base + "/api/v2/serve/datasources",
                json=dict(
                    type="sqlite",
                    params=dict(path=str(path)),
                    description=metadata["notes"],
                ),
                timeout=90,
            )
            response.raise_for_status()
            result = response.json()
            assert result["success"] and result["data"]["db_name"] == name, result
        manifest.append(
            dict(
                source=name,
                rows=len(rows),
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                **metadata,
            )
        )
        print(name, len(rows), flush=True)
    (DEST / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
