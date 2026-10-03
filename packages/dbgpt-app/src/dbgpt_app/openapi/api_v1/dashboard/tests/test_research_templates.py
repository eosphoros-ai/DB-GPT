# ruff: noqa: F811
import importlib.util
import sqlite3
from pathlib import Path

import pytest

from dbgpt_app.openapi.api_v1.dashboard.catalog import build_template, preview_template
from dbgpt_app.openapi.api_v1.dashboard.catalog_research import RESEARCH_RECIPES
from dbgpt_ext.datasource.rdbms.conn_sqlite import SQLiteConnector

from .test_feedback import real_service  # noqa: F401


def source_rows(voice):
    root = next(
        p
        for p in Path(__file__).resolve().parents
        if (p / "scripts/dashboard/install_research_sources.py").exists()
    )
    spec = importlib.util.spec_from_file_location(
        "research_samples", root / "scripts/dashboard/install_research_sources.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if voice:
        return module.voice_rows()
    # Source-format fixture: both labels, genders and uneven age groups.
    return module.heart_rows(
        "\n".join(
            [
                "63,1,1,145,233,1,2,150,0,2.3,3,0,6,0",
                "67,1,4,160,286,0,2,108,1,1.5,2,3,3,2",
                "58,0,4,130,0,0,0,130,0,0.0,1,?,3,0",
                "44,0,2,120,230,0,0,170,0,0.0,1,0,3,1",
                "50,1,3,140,240,0,0,160,1,1.0,2,0,3,1",
            ]
        )
    )


@pytest.mark.parametrize("recipe", RESEARCH_RECIPES, ids=lambda r: r["id"])
def test_research_queries_filters_and_frozen_publication(real_service, recipe):
    service, _, path = real_service
    voice = recipe["id"] == "voice-observatory"
    rows = source_rows(voice)
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
    service.query_executor._connector_resolver = lambda _: (
        SQLiteConnector.from_file_path(str(path))
    )
    preview = preview_template(service, recipe["id"], "test", "alice")
    assert preview["validation"]["publication_equivalent"]
    assert all(
        not w["error"] and w["row_count"]
        for w in preview["snapshot"]["widgets"].values()
    )
    schema = build_template(recipe["id"], "test")
    scope, segment = ("2026", "服务咨询") if voice else ("Cleveland", "男性")
    subset = [r for r in rows if r["year"] == scope and r["segment"] == segment]
    formulas = (
        {
            "latency": ("latency_total", "aux", 1),
            "expression": ("passed", "evaluations", 100),
            "voice_share": ("aux", "value", 100),
        }
        if voice
        else {"prevalence": ("aux", "value", 100)}
    )
    with sqlite3.connect(path) as db:
        for widget in schema.widgets:
            if widget.id in formulas:
                numerator, denominator, scale = formulas[widget.id]
                actual = db.execute(
                    widget.query.sql, dict(year=scope, segment=segment)
                ).fetchone()[0]
                assert actual == pytest.approx(
                    sum(r[numerator] for r in subset)
                    / sum(r[denominator] for r in subset)
                    * scale
                )
    empty = service.query_executor.execute_dashboard(
        schema, {"year": "unavailable", "segment": "all"}
    )
    assert all(not w.error for w in empty.values())
    assert (
        schema.metadata.compatibility["catalog_presentation"]["reference_source"]
        == "sqlite_" + recipe["dataset"]
    )
    assert "已切换" in schema.metric_context.source_notes[0]
    positions = schema.layouts.desktop
    for i, left in enumerate(positions):
        for right in positions[i + 1 :]:
            assert (
                left.x + left.w <= right.x
                or right.x + right.w <= left.x
                or left.y + left.h <= right.y
                or right.y + right.h <= left.y
            )


def test_heart_missing_values_and_target_mapping():
    rows = source_rows(False)
    assert len(rows) == 5
    assert sum(r["aux"] for r in rows) == 3
    assert rows[2]["cholesterol"] is None
    assert all(r["event_date"] is None for r in rows)
