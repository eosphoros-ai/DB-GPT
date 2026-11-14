"""Build and verify an isolated semantic-center commerce case, without an LLM."""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import shutil
import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Any

CONNECTION = "Semantic_Commerce_Case"
WINDOW = ">= '2026-01-01' AND {alias}.{time} < '2026-02-01'"
ELIGIBLE = """SELECT * FROM orders WHERE tenant_id=1 AND is_test=0
AND is_deleted=0 AND status IN ('PAID','COMPLETED')"""


def net_sql(version: int, grouped: bool = False) -> str:
    """Aggregate each child at order grain before joining; freight removed once."""
    payment = "p.amount_cents"
    refund = "r.amount_cents"
    freight = ""
    if version == 2:
        refund = "r.amount_cents-r.freight_cents"
        freight = "-o.freight_cents"
    group = "c.channel_name," if grouped else ""
    suffix = (
        "GROUP BY c.channel_id, c.channel_name ORDER BY c.channel_id" if grouped else ""
    )
    return f"""WITH eligible AS ({ELIGIBLE}),
paid AS (
 SELECT p.order_id, SUM({payment}) AS cents FROM payments p
 WHERE p.status='SUCCESS'
 AND p.paid_at {WINDOW.format(alias="p", time="paid_at")}
 GROUP BY p.order_id
), returned AS (
 SELECT r.order_id, SUM({refund}) AS cents FROM refunds r
 WHERE r.status='SUCCESS'
 AND r.refunded_at {WINDOW.format(alias="r", time="refunded_at")}
 GROUP BY r.order_id
)
SELECT {group} SUM(
 CASE WHEN p.order_id IS NOT NULL THEN p.cents{freight} ELSE 0 END
 -COALESCE(r.cents,0)) AS net_cents
FROM eligible o JOIN channels c ON c.channel_id=o.channel_id
LEFT JOIN paid p ON p.order_id=o.order_id
LEFT JOIN returned r ON r.order_id=o.order_id
{suffix}"""


def event_sql(table: str, time_column: str) -> str:
    return f"""WITH eligible AS ({ELIGIBLE})
SELECT SUM(e.amount_cents) AS amount_cents FROM {table} e
JOIN eligible o ON o.order_id=e.order_id WHERE e.status='SUCCESS'
AND e.{time_column} >= '2026-01-01' AND e.{time_column} < '2026-02-01'"""


GMV_SQL = f"""WITH eligible AS ({ELIGIBLE})
SELECT SUM(i.goods_cents) AS gmv_cents
FROM eligible o JOIN order_items i ON i.order_id=o.order_id
WHERE o.created_at >= '2026-01-01' AND o.created_at < '2026-02-01'"""

VIEW_SQL = """SELECT SUM(signed_cents) AS net_cents FROM v_cash_events
WHERE event_at >= '2026-01-01' AND event_at < '2026-02-01'"""

# Deliberate counterexample: two payment rows x two January refund rows x two items.
BAD_JOIN_SQL = """SELECT SUM(p.amount_cents-r.amount_cents) AS wrong_cents
FROM orders o JOIN payments p ON p.order_id=o.order_id
JOIN refunds r ON r.order_id=o.order_id
JOIN order_items i ON i.order_id=o.order_id
WHERE o.order_id=1 AND p.status='SUCCESS' AND r.status='SUCCESS'
AND p.paid_at >= '2026-01-01' AND p.paid_at < '2026-02-01'
AND r.refunded_at >= '2026-01-01' AND r.refunded_at < '2026-02-01'"""

EXPECTED = {
    "net_v1": [{"net_cents": 36800}],
    "net_v2": [{"net_cents": 33800}],
    "channel_v1": [
        {"channel_name": "自然渠道", "net_cents": 13500},
        {"channel_name": "广告渠道", "net_cents": 23300},
    ],
    "channel_v2": [
        {"channel_name": "自然渠道", "net_cents": 12600},
        {"channel_name": "广告渠道", "net_cents": 21200},
    ],
    "gmv": [{"gmv_cents": 40000}],
    "view_v1": [{"net_cents": 36800}],
    "bad_join": [{"wrong_cents": 38000}],
    "successful_payments": [{"amount_cents": 41300}],
    "successful_refunds": [{"amount_cents": 4500}],
}


def queries() -> dict[str, str]:
    return {
        "net_v1": net_sql(1),
        "net_v2": net_sql(2),
        "channel_v1": net_sql(1, True),
        "channel_v2": net_sql(2, True),
        "gmv": GMV_SQL,
        "view_v1": VIEW_SQL,
        "bad_join": BAD_JOIN_SQL,
        "successful_payments": event_sql("payments", "paid_at"),
        "successful_refunds": event_sql("refunds", "refunded_at"),
    }


def seed() -> dict[str, Any]:
    """Use named targets, resolved to real IDs during installation."""
    definitions = [
        (
            "orders",
            None,
            "有效订单",
            ["真实订单", "成交单"],
            "tenant_id=1、is_test=0、is_deleted=0，状态 PAID/COMPLETED；不是所有订单。",
        ),
        (
            "orders",
            "created_at",
            "下单时间",
            ["订单日期"],
            "UTC+08，下单事件时间；不能替代支付时间或退款时间。",
        ),
        (
            "orders",
            "freight_cents",
            "订单运费",
            ["配送费"],
            "单位分，订单粒度；多笔支付时仅扣一次。v2限定本案例一次完整结清。",
        ),
        (
            "order_items",
            "goods_cents",
            "商品成交额",
            ["货款", "商品金额"],
            "单位分，已折扣的行总额；已包含 quantity，不得再次乘数量；不含运费。",
        ),
        (
            "payments",
            "paid_at",
            "支付时间",
            ["到账日期", "收款日"],
            "以成功支付事件发生时间归属月份，不以订单创建时间归属。",
        ),
        (
            "payments",
            "amount_cents",
            "支付流水金额",
            ["到账金额", "实收流水"],
            "单位分、支付流水粒度、含运费，仅 SUCCESS；订单可多次支付。",
        ),
        (
            "refunds",
            "refunded_at",
            "退款时间",
            ["退钱日期"],
            "成功退款事件发生月份；跨月退款只扣退款月，不回写下单月。",
        ),
        (
            "refunds",
            "amount_cents",
            "退款流水金额",
            ["退钱金额"],
            "单位分、退款流水粒度、含退运费，仅 SUCCESS；订单可多次退款。",
        ),
        (
            "refunds",
            "freight_cents",
            "退运费",
            ["退配送费"],
            "退款金额中的运费部分；v2扣退款货款 amount_cents-freight_cents。",
        ),
        (
            "channels",
            "channel_name",
            "获客渠道",
            ["来源", "流量渠道"],
            "通过 orders.channel_id 关联；不要把支付方式当作获客渠道。",
        ),
        (
            "v_cash_events",
            None,
            "收支事件视图",
            ["现金流视图"],
            "真实 SQL 视图：支付正数 UNION ALL 退款负数，仅支持含运费 v1。",
        ),
    ]
    entries = [
        {
            "table": table,
            "column": column,
            "entry_name": name,
            "synonyms": aliases,
            "entry_comment": description,
            "entry_definition": {"meaning": description},
            "publish": True,
        }
        for table, column, name, aliases, description in definitions
    ]
    entries.append(
        {
            "table": "payments",
            "column": "amount_cents",
            "entry_name": "草稿诱饵_到账金额",
            "synonyms": ["到账金额"],
            "entry_comment": "错误草稿：不区分租户，包含失败支付。",
            "entry_definition": {"forbidden": "DRAFT_ONLY"},
            "publish": False,
        }
    )
    metrics = []
    for name, table, time in (
        ("成功支付额", "payments", "paid_at"),
        ("成功退款额", "refunds", "refunded_at"),
    ):
        metrics.append(
            {
                "metric_name": name,
                "case_version": 1,
                "metric_type": "atomic",
                "metric_comment": "有效订单的成功流水，按事件月，含运费，人民币分。",
                "formula": f"SUM({table}.amount_cents)",
                "base_metrics": [],
                "dimensions": ["channels.channel_name"],
                "metric_definition": {
                    "sql": event_sql(table, time),
                    "unit": "CNY_cent",
                    "timezone": "UTC+08",
                    "filters": ELIGIBLE,
                    "lineage": {
                        "kind": "manually_authored_metric_dependencies",
                        "sources": [
                            f"{table}.amount_cents",
                            f"{table}.{time}",
                            f"{table}.status",
                            f"{table}.order_id",
                            "orders.order_id",
                            "orders.tenant_id",
                            "orders.is_test",
                            "orders.is_deleted",
                            "orders.status",
                        ],
                    },
                },
            }
        )
    for version in (1, 2):
        lineage = {
            "kind": "manually_authored_metric_dependencies",
            "sources": [
                "payments.amount_cents",
                "payments.paid_at",
                "payments.status",
                "refunds.amount_cents",
                "refunds.refunded_at",
                "refunds.status",
                "orders.order_id",
                "orders.tenant_id",
                "orders.is_test",
                "orders.is_deleted",
                "orders.status",
                "orders.channel_id",
                "channels.channel_id",
                "channels.channel_name",
            ],
            "grain": "payments/refunds -> order_id -> channel",
        }
        if version == 2:
            lineage["sources"] += ["orders.freight_cents", "refunds.freight_cents"]
        metrics.append(
            {
                "metric_name": "净实收",
                "case_version": version,
                "metric_comment": "成功支付减成功退款；v1含运费，v2仅商品货款。",
                "metric_type": "derived",
                "formula": (
                    "successful_payments - successful_refunds"
                    if version == 1
                    else "successful_payments - paid_order_freight"
                    " - (successful_refunds - refunded_freight)"
                ),
                "base_metrics": ["成功支付额", "成功退款额"],
                "dimensions": ["channels.channel_name"],
                "metric_definition": {
                    "unit": "CNY_cent",
                    "timezone": "UTC+08",
                    "window": ["2026-01-01", "2026-02-01"],
                    "filters": ELIGIBLE,
                    "refund_attribution": "refund event month",
                    "payment_attribution": "payment event month",
                    "freight_included": version == 1,
                    "lineage": lineage,
                    "scope": (
                        "固定2026-01案例；v2订单运费在本窗口完整结清时扣一次。"
                        "分月分期支付需另行定义运费分摊，不能直接推广本SQL。"
                    ),
                    "sql": net_sql(version),
                    "channel_sql": net_sql(version, True),
                },
            }
        )
    metrics.append(
        {
            "metric_name": "有效GMV",
            "case_version": 1,
            "metric_comment": "有效订单的商品行成交额，按下单月，不扣退款，不含运费。",
            "metric_type": "atomic",
            "formula": "SUM(order_items.goods_cents)",
            "dimensions": ["channels.channel_name"],
            "base_metrics": [],
            "metric_definition": {
                "unit": "CNY_cent",
                "timezone": "UTC+08",
                "filters": ELIGIBLE,
                "time_field": "orders.created_at",
                "sql": GMV_SQL,
                "lineage": {
                    "kind": "manually_authored_metric_dependencies",
                    "sources": [
                        "order_items.goods_cents",
                        "order_items.order_id",
                        "orders.order_id",
                        "orders.created_at",
                        "orders.tenant_id",
                        "orders.is_test",
                        "orders.is_deleted",
                        "orders.status",
                    ],
                },
            },
        }
    )
    return {"connection": CONNECTION, "entries": entries, "metrics": metrics}


CASES = [
    (
        "Q01",
        "智能取数",
        "按到账日期统计2026年1月净实收，只看租户1真实业务，使用最新已发布口径。",
        "338.00元；引用净实收@v2，支付时间/退款时间分别过滤；排除草稿。",
    ),
    (
        "Q02",
        "智能取数",
        "2026年1月按来源看净实收，用v2。",
        "自然126.00元、广告212.00元；来源映射channels.channel_name，先按订单聚合支付/退款。",
    ),
    (
        "Q03",
        "智能取数",
        "重跑2026年1月月报，必须固定净实收v1，再说明与v2的差异。",
        "v1=368.00元、v2=338.00元；差30.00元是运费33.00减退运费3.00。",
    ),
    (
        "Q04",
        "智能取数",
        "1月有效GMV和净实收v2为什么不同？",
        "GMV400.00元按下单时间、不扣退款；净实收338.00元按收支事件月。",
    ),
    (
        "Q05",
        "智能取数",
        "订单1的1月含运费净实收多少？直接关联商品、支付、退款汇总可以吗？",
        "95.00元；错误三表JOIN得到380.00元（放大4倍），必须先聚合。",
    ),
    (
        "Q06",
        "智能取数",
        "订单3和4该计入哪个月？订单1的2月退款影响1月吗？",
        "订单3的1月实收50减退款10=40元，GMV属12月；订单4的GMV70属1月、支付属2月；2月退款不扣1月。",
    ),
    (
        "Q07",
        "智能取数",
        "请用净实收v99算1月结果。",
        "version_not_found，不能退回v2或虚构口径；停止该版本计算。",
    ),
    (
        "M01",
        "元数据",
        "解释货款、到账金额、退钱金额、来源对应字段，输出数据字典。",
        "对应商品行金额/支付流水/退款流水/渠道名；标明单位分、粒度、业务别名。",
    ),
    (
        "M02",
        "元数据",
        "画订单、商品、支付、退款、渠道的ER关系，并解释一对多放大风险。",
        "5条真实外键；ER关系是关联关系，不能称为ETL加工血缘。",
    ),
    (
        "M03",
        "元数据",
        "净实收v2来自哪些字段？退运费字段改变影响哪些指标？",
        "引用手工发布依赖：refunds.freight_cents影响净实收v2，不影响v1或有效GMV；仅回答已登记范围。",
    ),
    (
        "M04",
        "元数据",
        "v_cash_events怎么加工？能直接算最新净实收吗？",
        "展示实际CREATE VIEW的支付/退款UNION ALL及过滤，"
        "视图仅支持v1=368元，不能冒充v2。",
    ),
    (
        "M05",
        "元数据",
        "找出净实收的上游调度任务、任务负责人和运行时间。",
        "本案例无调度平台证据；明确缺失，不能从FK或视图猜出任务。",
    ),
]


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def build_database(output: Path) -> Path:
    path = output / "commerce.db"
    with sqlite3.connect(path) as conn:
        conn.executescript(Path(__file__).with_name("schema.sql").read_text())
        violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise AssertionError(violations)
    return path


def install_isolated(path: Path, output: Path, fixture: dict) -> tuple[Any, int]:
    """Only call from this CLI process; never change the running server's DB."""
    from dbgpt.storage.metadata import db
    from dbgpt_ext.datasource.rdbms.conn_sqlite import SQLiteConnector
    from dbgpt_serve.semantic.join_discovery import JoinDiscoverer
    from dbgpt_serve.semantic.models import SemMetricEntity
    from dbgpt_serve.semantic.publisher import LoggingSink, SemanticPublisher
    from dbgpt_serve.semantic.service import SemanticService
    from dbgpt_serve.semantic.sync import SemanticSyncService

    db.init_db(f"sqlite:///{output / 'semantic_meta.db'}")
    db.create_all()
    connector = SQLiteConnector.from_file_path(str(path))
    sync = SemanticSyncService()
    report = sync.sync(CONNECTION, connector)
    service = SemanticService(publisher=SemanticPublisher(LoggingSink()))
    service.activate(report.ds_id, run_draft_generation=False)
    tables = {t["table_name"]: t for t in service.list_tables(report.ds_id)}
    for entry in fixture["entries"]:
        table = tables[entry["table"]]
        target = table["id"]
        if entry["column"]:
            target = next(
                c["id"]
                for c in service.list_columns(report.ds_id, table["id"])
                if c["column_name"] == entry["column"]
            )
        payload = {
            **entry,
            "entry_type": "column" if entry["column"] else "table",
            "target_id": target,
            "entry_definition": json.dumps(
                entry["entry_definition"], ensure_ascii=False
            ),
        }
        created = service.create_entry(report.ds_id, payload, user="case_builder")
        if entry["publish"]:
            service.review_entry(created["id"], "confirm", user="case_builder")
    ids = {}
    for metric in fixture["metrics"]:
        payload = {
            **metric,
            "metric_definition": json.dumps(
                metric["metric_definition"], ensure_ascii=False
            ),
        }
        name = metric["metric_name"]
        if name not in ids:
            ids[name] = service.create_metric(report.ds_id, payload).id
        else:
            session = service._metric_dao.get_raw_session()
            try:
                row = session.get(SemMetricEntity, ids[name])
                row.metric_definition = payload["metric_definition"]
                row.formula = payload["formula"]
                session.commit()
            finally:
                session.close()
        service.publish_metric(
            ids[name],
            user="case_builder",
            change_note=f"case v{metric['case_version']}",
        )
    # Mutable unpublished edit while published snapshots remain authoritative.
    session = service._metric_dao.get_raw_session()
    try:
        row = session.get(SemMetricEntity, ids["净实收"])
        row.formula = "UNPUBLISHED_POISON"
        row.metric_definition = '{"sql":"SELECT 999999 AS net_cents"}'
        session.commit()
    finally:
        session.close()
    draft = service.create_metric(
        report.ds_id,
        {
            "metric_name": "草稿诱饵净实收",
            "formula": "DRAFT_ONLY",
        },
    )
    joins = JoinDiscoverer().discover(report.ds_id, connector=connector)
    write_json(
        output / "governance.json",
        {
            "sync": asdict(report),
            "joins": joins,
            "draft_metric_id": draft.id,
            "coverage": service.coverage(report.ds_id),
            "relations": service.list_relations(report.ds_id),
        },
    )
    connector._engine.dispose()
    return service, report.ds_id


async def verify(path: Path, output: Path, service: Any, ds_id: int) -> dict:
    from dbgpt_app.openapi.api_v1.tools.semantic_tools import make_semantic_tools
    from dbgpt_serve.semantic.reader import SemanticReader

    tools = {
        t._tool.name: t
        for t in make_semantic_tools(
            CONNECTION, reader=SemanticReader(CONNECTION, service)
        )
    }
    checks = []
    evidence = {}

    def check(name: str, condition: bool) -> None:
        checks.append({"check": name, "passed": bool(condition)})
        if not condition:
            raise AssertionError(name)

    async def call(name: str, **kwargs: Any) -> dict:
        result = json.loads(await tools[name](**kwargs))
        evidence[f"{name}:{json.dumps(kwargs, ensure_ascii=False)}"] = result
        return result

    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        for name, sql in queries().items():
            rows = [dict(r) for r in conn.execute(sql)]
            check(f"gold_sql:{name}", rows == EXPECTED[name])
        for version in (1, 2):
            result = await call(
                "semantic_get_metric", metric_name="净实收", version=version
            )
            metric = result["metric"]
            check(f"published_snapshot:v{version}", metric["version"] == version)
            check(
                f"snapshot_sql:v{version}",
                [dict(r) for r in conn.execute(metric["metric_definition"]["sql"])]
                == EXPECTED[f"net_v{version}"],
            )
        latest = await call("semantic_get_metric", metric_name="净实收")
        check(
            "latest_is_v2_not_unpublished_edit",
            latest["metric"]["version"] == 2
            and "UNPUBLISHED_POISON" not in json.dumps(latest),
        )
        missing = await call("semantic_get_metric", metric_name="净实收", version=99)
        check("unknown_version_no_fallback", missing["status"] == "version_not_found")
        business = await call(
            "semantic_search_business", query="按到账金额统计", table_name="payments"
        )
        check(
            "alias_resolves_to_payment_amount",
            any(i["column_name"] == "amount_cents" for i in business["items"]),
        )
        check(
            "business_drafts_excluded",
            business["items"]
            and all(i["status"] == "published" for i in business["items"])
            and "DRAFT_ONLY" not in json.dumps(business),
        )
        source = await call("semantic_search_business", query="来源")
        check(
            "source_is_channel_name",
            any(
                i["table_name"] == "channels" and i["column_name"] == "channel_name"
                for i in source["items"]
            ),
        )
        metrics = await call("semantic_search_metrics", query="净实收")
        check("search_published_metrics_only", len(metrics["items"]) == 1)
        draft = await call("semantic_get_metric", metric_name="草稿诱饵净实收")
        check("draft_metric_cannot_be_consumed", draft["status"] == "not_published")
        metadata = await call("semantic_get_metadata", table_name="orders")
        check(
            "real_metadata_snapshot",
            len(metadata["items"]) == 1
            and any(
                c["column_name"] == "order_id" and c["is_pk"]
                for c in metadata["items"][0]["columns"]
            ),
        )
        relations = service.list_relations(ds_id)
        check("five_declared_foreign_keys", len(relations) == 5)
        lineage = latest["metric"]["metric_definition"]["lineage"]
        check(
            "metric_lineage_is_explicit_not_inferred",
            lineage["kind"] == "manually_authored_metric_dependencies"
            and "refunds.freight_cents" in lineage["sources"],
        )
        for base_name in latest["metric"]["base_metrics"]:
            base = await call("semantic_get_metric", metric_name=base_name)
            check(f"base_metric_is_published:{base_name}", base["status"] == "ok")
        # Scope isolation uses the real reader with an unregistered connection.
        other = SemanticReader("not_registered_case", service).search_metrics("净实收")
        check("connection_scope_isolation", other["status"] == "space_not_found")
        annotations = {
            (e["table"], e["column"]): e for e in seed()["entries"] if e["publish"]
        }
        dictionary = []
        for table in conn.execute(
            "SELECT name, type, sql FROM sqlite_master "
            "WHERE type IN ('table','view') ORDER BY name"
        ):
            for col in conn.execute(f'PRAGMA table_info("{table["name"]}")'):
                annotation = annotations.get((table["name"], col["name"]), {})
                dictionary.append(
                    {
                        "table": table["name"],
                        "kind": table["type"],
                        "column": col["name"],
                        "type": col["type"],
                        "pk": col["pk"],
                        "business_name": annotation.get("entry_name", ""),
                        "synonyms": "、".join(annotation.get("synonyms", [])),
                        "meaning": annotation.get("entry_comment", ""),
                    }
                )
        with (output / "data_dictionary.csv").open(
            "w", encoding="utf-8-sig", newline=""
        ) as f:
            writer = csv.DictWriter(f, fieldnames=list(dictionary[0]))
            writer.writeheader()
            writer.writerows(dictionary)
        view = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name='v_cash_events'"
        ).fetchone()[0]
        (output / "view_lineage.sql").write_text(view + ";\n", encoding="utf-8")
        er = ["erDiagram"]
        for table in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ):
            for fk in conn.execute(f'PRAGMA foreign_key_list("{table["name"]}")'):
                er.append(
                    f"    {fk['table']} ||--o{{ {table['name']} : "
                    f'"{fk["from"]} to {fk["to"]}"'
                )
        (output / "relationships.mmd").write_text(
            "\n".join(er) + "\n", encoding="utf-8"
        )
    write_json(output / "tool_evidence.json", evidence)
    result = {
        "status": "passed",
        "checks": checks,
        "passed_count": len(checks),
        "llm_e2e_tested": False,
        "vector_retrieval_tested": False,
        "known_gaps": [
            "No dedicated relation/ETL-lineage Agent tool; "
            "L4 graph is management API data.",
            "Metric lineage is manually authored JSON, "
            "not parsed/validated impact graph.",
            "No job scheduler/task owner evidence; FK is not ETL lineage.",
            "Semantic metadata flags are descriptive; "
            "this case does not test SQL guardrails.",
            "Live API lacks metric-edit endpoint; "
            "same-metric v1/v2 tested only in isolation.",
        ],
    }
    write_json(output / "verification.json", result)
    return result


def build(output: Path) -> dict:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    path = build_database(output)
    fixture = seed()
    write_json(output / "semantic_seed.json", fixture)
    write_json(output / "expected.json", EXPECTED)
    write_json(
        output / "cases.json",
        [
            {
                "id": id_,
                "scenario": scenario,
                "question": question,
                "expected": expected,
            }
            for id_, scenario, question, expected in CASES
        ],
    )
    for name, sql in queries().items():
        (output / f"{name}.sql").write_text(sql + ";\n", encoding="utf-8")
    shutil.copyfile(Path(__file__).with_name("schema.sql"), output / "schema.sql")
    shutil.copyfile(Path(__file__).with_name("README.md"), output / "README.md")
    service, ds_id = install_isolated(path, output, fixture)
    result = asyncio.run(verify(path, output, service, ds_id))
    lines = [
        "# 验证记录",
        "",
        f"通过 {result['passed_count']} 项断言。",
        "实际SQLite连接器 → 元数据同步 → 审核发布 → 真实语义工具 → 金标SQL。",
        "未调用模型、未验证向量召回；发布索引使用LoggingSink，非线上向量库。",
        "",
        "| ID | 场景 | 问题 | 预期 |",
        "|---|---|---|---|",
    ]
    lines += [
        f"| {id_} | {scene} | {question} | {expected} |"
        for id_, scene, question, expected in CASES
    ]
    (output / "verification.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(args.output)
    print(f"PASS: {result['passed_count']} checks; artifacts: {args.output.resolve()}")
