"""Create isolated, clearly labelled synthetic data for the four showcase templates.

No existing source is overwritten. Fixed seeds and recorded SHA-256 hashes make
examples reproducible. These are historical aggregates, not live business data.
"""

import argparse
import hashlib
import json
import random
import sqlite3
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / "data" / "dashboard_showcase_sources"
PROVINCES = [
    "北京市",
    "天津市",
    "河北省",
    "山西省",
    "内蒙古自治区",
    "辽宁省",
    "吉林省",
    "黑龙江省",
    "上海市",
    "江苏省",
    "浙江省",
    "安徽省",
    "福建省",
    "江西省",
    "山东省",
    "河南省",
    "湖北省",
    "湖南省",
    "广东省",
    "广西壮族自治区",
    "海南省",
    "重庆市",
    "四川省",
    "贵州省",
    "云南省",
    "西藏自治区",
    "陕西省",
    "甘肃省",
    "青海省",
    "宁夏回族自治区",
    "新疆维吾尔自治区",
]
NOTES = (
    "DB-GPT 自建合成演示数据，2025/2026 年同期历"
    "史样本；不代表真实机构、患者或经营结果。"
)


def generate(key):
    rng = random.Random("dbgpt-showcase-v1-" + key)
    rows = []

    def row(date, segment, category, entity, value, aux, **extras):
        rows.append(
            dict(
                event_date=date,
                year=date[:4],
                period=date[:7],
                segment=segment,
                category=category,
                entity=entity,
                value=value,
                aux=aux,
                **extras,
            )
        )

    for year in (2025, 2026):
        growth = 1 if year == 2025 else 1.18
        if key == "marketing_showcase":
            for month in range(1, 9):
                for venue in ("城中旗舰店", "湖畔生活店", "西区社区店"):
                    for campaign in ("春日尝鲜", "会员回馈", "双人套餐", "午后时光"):
                        for channel in ("店内", "小程序", "社群", "合作平台"):
                            reach = int(rng.randint(420, 2100) * growth)
                            visits = int(reach * rng.uniform(0.21, 0.43))
                            redeemed = int(visits * rng.uniform(0.35, 0.65))
                            row(
                                f"{year}-{month:02d}-01",
                                venue,
                                campaign,
                                campaign,
                                round(redeemed * rng.uniform(52, 138), 2),
                                redeemed,
                                channel=channel,
                                reach=reach,
                                visits=visits,
                            )
        elif key == "operations_showcase":
            for month in range(1, 9):
                for index, province in enumerate(PROVINCES):
                    for category in ("数码生活", "家居好物", "食品饮料", "运动户外"):
                        orders = int(
                            rng.randint(80, 900)
                            * growth
                            * (1 + 0.5 * (province in ("广东省", "江苏省", "浙江省")))
                        )
                        delivered = int(orders * rng.uniform(0.92, 0.99))
                        value = round(orders * rng.uniform(70, 320), 2)
                        row(
                            f"{year}-{month:02d}-01",
                            province,
                            category,
                            f"{index}-{category}",
                            value,
                            orders,
                            units=int(orders * rng.uniform(1.4, 3.3)),
                            delivered=delivered,
                            on_time=int(delivered * rng.uniform(0.89, 0.995)),
                            target=round(value * rng.uniform(0.93, 1.16), 2),
                        )
        elif key == "healthcare_showcase":
            for month in range(1, 9):
                for provider in (
                    "中心一院",
                    "东区二院",
                    "西区三院",
                    "南区四院",
                    "北区五院",
                ):
                    for department in (
                        "全科",
                        "儿科",
                        "皮肤科",
                        "内科",
                        "中医科",
                        "营养科",
                    ):
                        for channel in ("小程序", "互联网医院", "移动端"):
                            count = int(rng.randint(60, 330) * growth)
                            row(
                                f"{year}-{month:02d}-01",
                                department,
                                channel,
                                provider,
                                count,
                                int(count * rng.uniform(0.35, 0.7)),
                                fees=round(count * rng.uniform(20, 80), 2),
                                response_minutes=round(count * rng.uniform(2, 11), 2),
                                completed=int(count * rng.uniform(0.89, 0.995)),
                            )
        else:
            for month in range(1, 9):
                for province in PROVINCES[2:27]:
                    for product in ("惠农经营贷", "乡村创业贷", "农机设备贷"):
                        applications = int(rng.randint(80, 360) * growth)
                        approved = int(applications * rng.uniform(0.73, 0.94))
                        loans = int(approved * rng.uniform(0.9, 1))
                        due = rng.randint(60, 180)
                        row(
                            f"{year}-{month:02d}-01",
                            province,
                            product,
                            f"{province}-{product}",
                            round(loans * rng.uniform(8000, 65000), 2),
                            loans,
                            applications=applications,
                            approved=approved,
                            due=due,
                            on_time=int(due * rng.uniform(0.92, 1)),
                        )
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:5671")
    parser.add_argument("--register", action="store_true")
    args = parser.parse_args()
    DEST.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Id"] = "001"
    existing = set()
    if args.register:
        response = session.get(args.base + "/api/v2/serve/datasources", timeout=30)
        response.raise_for_status()
        existing = {s["db_name"] for s in response.json()["data"]}
    manifest = []
    for key in (
        "marketing_showcase",
        "operations_showcase",
        "healthcare_showcase",
        "rural_showcase",
    ):
        rows = generate(key)
        path = DEST / (key + ".sqlite")
        columns = list(rows[0])
        numeric = {
            name for name, value in rows[0].items() if isinstance(value, (int, float))
        }
        if not path.exists():
            with sqlite3.connect(path) as db:
                definitions = ",".join(
                    f'"{name}" ' + ("REAL" if name in numeric else "TEXT")
                    for name in columns
                )
                db.execute("CREATE TABLE facts (" + definitions + ")")
                db.executemany(
                    "INSERT INTO facts VALUES (" + ",".join("?" for _ in columns) + ")",
                    [tuple(r.values()) for r in rows],
                )
                db.execute("CREATE INDEX fact_scope ON facts(year, segment)")
                db.execute(
                    "CREATE TABLE source_metadata (kind TEXT, seed TEXT, notes TEXT)"
                )
                db.execute(
                    "INSERT INTO source_metadata VALUES (?,?,?)",
                    ("synthetic", "dbgpt-showcase-v1-" + key, NOTES),
                )
        name = "sqlite_" + key
        if args.register and name not in existing:
            response = session.post(
                args.base + "/api/v2/serve/datasources",
                json=dict(
                    type="sqlite", params=dict(path=str(path)), description=NOTES
                ),
                timeout=90,
            )
            response.raise_for_status()
            result = response.json()
            assert result["success"] and result["data"]["db_name"] == name, result
        with sqlite3.connect(path) as db:
            count = db.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        manifest.append(
            dict(
                source=name,
                kind="synthetic",
                rows=count,
                seed="dbgpt-showcase-v1-" + key,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                notes=NOTES,
            )
        )
        print(name, count, flush=True)
    (DEST / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
