"""Structured semantic reads: DB isolation and immutable published calibers."""

from datetime import datetime

import pytest

from dbgpt.storage.metadata import db
from dbgpt_serve.semantic.models import (
    SemColumnEntity,
    SemDatasourceDao,
    SemDatasourceEntity,
    SemEntryEntity,
    SemMetricEntity,
    SemMetricVersionEntity,
    SemTableEntity,
    dump_json,
)
from dbgpt_serve.semantic.reader import SemanticReader


@pytest.fixture
def reader(tmp_path):
    db.init_db(f"sqlite:///{tmp_path / 'reader.db'}")
    db.create_all()
    session = SemDatasourceDao().get_raw_session()
    try:
        session.add_all(
            [
                SemDatasourceEntity(id=1, conn_id="orders_db", status="activated"),
                SemDatasourceEntity(id=2, conn_id="other_db", status="activated"),
                SemTableEntity(
                    id=10, ds_id=1, table_name="orders", is_whitelisted=True
                ),
                SemTableEntity(id=20, ds_id=2, table_name="secret"),
                SemColumnEntity(
                    id=100,
                    ds_id=1,
                    table_id=10,
                    column_name="region",
                    column_type="varchar",
                    is_fk=True,
                    is_enum=True,
                    is_sensitive=True,
                    enum_values=dump_json(["华东", "华南"]),
                ),
                SemColumnEntity(
                    id=200,
                    ds_id=2,
                    table_id=20,
                    column_name="private",
                ),
                SemEntryEntity(
                    id=1,
                    ds_id=1,
                    entry_type="column",
                    target_id=100,
                    entry_name="销售地区",
                    synonyms=dump_json(["华东区"]),
                    entry_definition="区域按下单地址定义",
                    status="published",
                    version=2,
                    publish_version=2,
                ),
                SemEntryEntity(
                    id=2,
                    ds_id=1,
                    entry_type="column",
                    target_id=100,
                    entry_name="草稿释义",
                    entry_definition="未审业务定义",
                    status="draft",
                ),
                SemEntryEntity(
                    id=3,
                    ds_id=1,
                    entry_type="column",
                    target_id=200,
                    entry_name="错误跨库目标",
                    status="published",
                ),
                SemMetricEntity(
                    id=1,
                    ds_id=1,
                    metric_name="gmv",
                    metric_comment="有效销售额",
                    formula="DRAFT_MUTATED_FORMULA",
                    status="published",
                    version=2,
                    publish_version=2,
                ),
                SemMetricEntity(
                    id=2,
                    ds_id=1,
                    metric_name="draft_gmv",
                    formula="UNREVIEWED",
                    status="draft",
                ),
                SemMetricEntity(
                    id=3,
                    ds_id=2,
                    metric_name="secret_metric",
                    formula="PRIVATE",
                    status="published",
                    publish_version=1,
                ),
                SemMetricEntity(
                    id=4,
                    ds_id=1,
                    metric_name="missing_snapshot",
                    formula="DO_NOT_FALL_BACK",
                    status="published",
                    publish_version=1,
                ),
                SemMetricVersionEntity(
                    metric_id=1,
                    version=1,
                    formula="SUM(amount)",
                    metric_definition="旧版口径",
                    published_at=datetime.utcnow(),
                ),
                SemMetricVersionEntity(
                    metric_id=1,
                    version=2,
                    formula="SUM(paid_amount)",
                    metric_definition=dump_json(
                        {
                            "default_filters": ["status = 'paid'"],
                            "time_column": "paid_at",
                        }
                    ),
                    base_metrics=dump_json(["paid_sales"]),
                    dimensions=dump_json(["region"]),
                    published_at=datetime.utcnow(),
                    published_by="reviewer",
                ),
            ]
        )
        session.commit()
    finally:
        session.close()
    return SemanticReader("orders_db")


def test_metadata_contains_scoped_columns_and_complete_flags(reader):
    result = reader.metadata(table_name="orders")
    assert result["conn_id"] == "orders_db"
    table = result["items"][0]
    assert table["is_whitelisted"] is True
    column = table["columns"][0]
    assert column["is_fk"] and column["is_sensitive"]
    assert column["enum_values"] == ["华东", "华南"]
    assert reader.metadata(table_name="secret")["items"] == []


def test_business_aliases_return_published_definition_and_valid_target(reader):
    result = reader.business_semantics(query="华东区的销售", table_name="orders")
    assert len(result["items"]) == 1
    row = result["items"][0]
    assert row["column_name"] == "region"
    assert row["entry_definition"] == "区域按下单地址定义"
    assert row["synonyms"] == ["华东区"]
    assert row["publish_version"] == 2
    assert len(reader.business_semantics()["items"]) == 1
    assert reader.business_semantics(table_name="secret")["items"] == []


def test_latest_metric_reads_snapshot_not_mutable_body(reader):
    row = reader.get_metric(metric_name="gmv")["metric"]
    assert row["formula"] == "SUM(paid_amount)"
    assert row["version"] == 2
    assert row["metric_definition"]["default_filters"] == ["status = 'paid'"]
    assert row["base_metrics"] == ["paid_sales"]
    assert row["dimensions"] == ["region"]
    assert row["citation"] == "semantic::orders_db/metric/1@v2"


def test_exact_historical_version_never_falls_back(reader):
    row = reader.get_metric(metric_id=1, version=1)["metric"]
    assert row["formula"] == "SUM(amount)"
    assert row["version"] == 1
    assert reader.get_metric(metric_id=1, version=99)["status"] == "version_not_found"
    assert reader.get_metric(metric_id=4)["metric"] is None


def test_metric_ids_cannot_escape_current_database(reader):
    assert reader.get_metric(metric_id=3) == reader.get_metric(metric_id=999)
    assert reader.get_metric(metric_name="secret_metric")["status"] == "not_found"


def test_drafts_are_not_returned_or_searchable(reader):
    result = reader.get_metric(metric_id=2)
    assert result["status"] == "not_published"
    assert result["metric"] is None
    assert reader.search_metrics(query="draft")["items"] == []
    assert reader.search_metrics(query="有效销售额")["items"][0]["id"] == 1
    assert len(reader.search_metrics()["items"]) == 1


def test_missing_space_and_empty_matches_are_explicit(reader):
    assert reader.search_metrics(query="不存在")["status"] == "empty"
    missing = SemanticReader("missing", service=reader.service)
    assert missing.metadata()["status"] == "space_not_found"
    assert missing.get_metric(metric_id=1)["metric"] is None


@pytest.mark.parametrize(
    "kwargs",
    [{}, {"metric_id": 1, "metric_name": "gmv"}, {"metric_id": 1, "version": 0}],
)
def test_metric_selector_validation(reader, kwargs):
    with pytest.raises(ValueError):
        reader.get_metric(**kwargs)


@pytest.mark.parametrize("limit", [0, 51])
def test_search_limits_are_bounded(reader, limit):
    with pytest.raises(ValueError):
        reader.search_metrics(limit=limit)
