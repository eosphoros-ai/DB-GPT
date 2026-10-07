import sqlite3

import pytest

from dbgpt_app.openapi.api_v1.dashboard.catalog import (
    TEMPLATES,
    instantiate_template,
    preview_template,
)
from dbgpt_app.openapi.api_v1.dashboard.catalog_extended import get_recipe
from dbgpt_app.openapi.api_v1.dashboard.catalog_source import (
    TemplateSourceMapping,
    required_grain,
)
from dbgpt_ext.datasource.rdbms.conn_sqlite import SQLiteConnector

from .test_feedback import real_service as _real_service_fixture

real_service = _real_service_fixture


@pytest.fixture
def mapped_source(real_service):
    service, _, path = real_service
    with sqlite3.connect(path) as conn:
        conn.execute(
            (
                "CREATE TABLE transactions (sale_id TEXT, purchas"
                "ed TEXT, net REAL, market TEXT, product TEXT, cu"
                "stomer TEXT, extra REAL)"
            )
        )
        conn.executemany(
            "INSERT INTO transactions VALUES (?,?,?,?,?,?,?)",
            [
                ("1", "2025-01-03", 10, "North", "A", "a", 2),
                ("2", "2025-01-20", 20, "North", "B", "b", 3),
                ("3", "2025-02-01", 30, "North", "A", "a", 4),
                ("4", "2025-02-09", 15, "South", "B", "c", 5),
                ("5", "2025-03-01", 25, "North", "A", "a", 6),
                ("6", "2026-01-02", 50, "South", "B", "d", 7),
            ],
        )

    def mapping(template_id):
        columns = dict(
            date="purchased",
            value="net",
            segment="market",
            category="product",
            entity="customer",
            aux="extra",
            record_id="sale_id",
        )
        return TemplateSourceMapping(
            table="transactions",
            fields={
                k: dict(table="transactions", column=v) for k, v in columns.items()
            },
            unit="元",
            grain=required_grain(template_id),
        )

    service.query_executor._connector_resolver = lambda _: (
        SQLiteConnector.from_file_path(str(path))
    )
    return service, path, mapping


@pytest.mark.parametrize(
    "template_id",
    [
        t["id"]
        for t in TEMPLATES
        if not get_recipe(t["id"]) or get_recipe(t["id"])["base"]
    ],
)
def test_all_compositions_map_renamed_fields_and_round_trip(mapped_source, template_id):
    service, _, mapping = mapped_source
    before = service.list_dashboard_page("alice").total
    preview = preview_template(
        service, template_id, "my-renamed-database", "alice", mapping(template_id)
    )
    assert service.list_dashboard_page("alice").total == before, (
        "Preview must not create assets"
    )
    assert preview["validation"]["publication_equivalent"]
    assert all(not w["error"] for w in preview["snapshot"]["widgets"].values())
    record = instantiate_template(
        service, template_id, "my-renamed-database", "alice", mapping(template_id)
    )
    reopened = service.get_dashboard(record.id, "alice")
    assert reopened.schema_payload == record.schema_payload
    assert reopened.schema_payload.layouts.model_dump() == preview["schema"]["layouts"]
    assert all(
        w.query.data_source_id == "my-renamed-database"
        for w in reopened.schema_payload.widgets
    )


def test_cohort_uses_unique_customers_and_preserves_observation_mask(mapped_source):
    service, _, mapping = mapped_source
    result = preview_template(
        service,
        "northwind-customers",
        "source",
        "alice",
        mapping("northwind-customers"),
    )
    rows = result["snapshot"]["widgets"]["retention"]["rows"]
    assert ["2025-01-01", 0, 2, 2, 1] in rows
    assert ["2025-01-01", 1, 1, 2, 1] in rows
    assert ["2025-01-01", 3, 0, 2, 1] in rows, "Observed zero must remain zero"
    assert ["2026-01-01", 1, 0, 1, 0] in rows, "Future periods are not zero retention"


def test_each_template_has_distinct_layout_and_chart_mix():
    from dbgpt_app.openapi.api_v1.dashboard.catalog import build_template

    signatures = []
    for item in TEMPLATES:
        schema = build_template(item["id"], item["source"])
        signatures.append(
            (
                tuple((p.x, p.y, p.w, p.h) for p in schema.layouts.desktop),
                tuple(w.presentation.visualization for w in schema.widgets),
            )
        )
    assert len(set(signatures)) == len(TEMPLATES)


@pytest.mark.parametrize(
    "sql,error",
    [
        ("UPDATE transactions SET purchased='invalid' WHERE sale_id='1'", "日期"),
        ("UPDATE transactions SET net='ten' WHERE sale_id='1'", "数值"),
        ("UPDATE transactions SET market=NULL WHERE sale_id='1'", "分类"),
    ],
)
def test_invalid_source_is_explained_without_creating_assets(mapped_source, sql, error):
    service, path, mapping = mapped_source
    with sqlite3.connect(path) as conn:
        conn.execute(sql)
    before = service.list_dashboard_page("alice").total
    with pytest.raises(ValueError, match=error):
        instantiate_template(
            service, "retail-overview", "source", "alice", mapping("retail-overview")
        )
    assert service.list_dashboard_page("alice").total == before


def test_duplicate_orders_and_lookup_keys_are_rejected(mapped_source):
    service, path, mapping = mapped_source
    with sqlite3.connect(path) as conn:
        conn.execute(
            "INSERT INTO transactions SELECT * FROM transactions WHERE sale_id='1'"
        )
        conn.execute("CREATE TABLE lookup (market TEXT,label TEXT)")
        conn.executemany(
            "INSERT INTO lookup VALUES (?,?)", [("North", "One"), ("North", "Two")]
        )
    with pytest.raises(ValueError, match="订单编号"):
        preview_template(
            service,
            "northwind-customers",
            "source",
            "alice",
            mapping("northwind-customers"),
        )
    payload = mapping("retail-overview").model_dump()
    payload["joins"] = [
        dict(
            table="lookup",
            left=dict(table="transactions", column="market"),
            right_column="market",
        )
    ]
    with pytest.raises(ValueError, match="不唯一"):
        preview_template(
            service,
            "retail-overview",
            "source",
            "alice",
            TemplateSourceMapping.model_validate(payload),
        )


def test_mapping_identifiers_cannot_be_sql_fragments(mapped_source):
    service, _, mapping = mapped_source
    payload = mapping("retail-overview").model_dump()
    payload["fields"]["value"]["column"] = "net); DROP TABLE transactions;--"
    with pytest.raises(ValueError, match="字段不存在"):
        preview_template(
            service,
            "retail-overview",
            "source",
            "alice",
            TemplateSourceMapping.model_validate(payload),
        )
