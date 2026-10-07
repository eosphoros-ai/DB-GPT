# ruff: noqa: F811
# pytest registers the imported fixture by its argument name.
import importlib.util
import sqlite3
from pathlib import Path

import pytest

from dbgpt_app.openapi.api_v1.dashboard.catalog import build_template, preview_template
from dbgpt_app.openapi.api_v1.dashboard.catalog_showcase import SHOWCASE_RECIPES
from dbgpt_ext.datasource.rdbms.conn_sqlite import SQLiteConnector

from .test_feedback import real_service  # noqa: F401


def sample_rows(key):
    root = next(
        p
        for p in Path(__file__).resolve().parents
        if (p / "scripts/dashboard/install_showcase_sources.py").exists()
    )
    spec = importlib.util.spec_from_file_location(
        "showcase_samples", root / "scripts/dashboard/install_showcase_sources.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.generate(key)


@pytest.mark.parametrize("recipe", SHOWCASE_RECIPES, ids=lambda r: r["id"])
def test_showcase_queries_match_frozen_publication_and_filters(real_service, recipe):
    service, _, path = real_service
    rows = sample_rows(recipe["dataset"])
    with sqlite3.connect(path) as db:
        db.execute(
            "CREATE TABLE facts ("
            + ",".join(
                f'"{k}" ' + ("REAL" if isinstance(v, (int, float)) else "TEXT")
                for k, v in rows[0].items()
            )
            + ")"
        )
        db.executemany(
            "INSERT INTO facts VALUES (" + ",".join("?" for _ in rows[0]) + ")",
            [tuple(r.values()) for r in rows],
        )
    service.query_executor._connector_resolver = lambda _: (
        SQLiteConnector.from_file_path(str(path))
    )
    preview = preview_template(service, recipe["id"], "test", "alice")
    assert preview["validation"]["publication_equivalent"]
    assert all(
        w["row_count"] and not w["error"]
        for w in preview["snapshot"]["widgets"].values()
    )
    # Ratios must be ratios of totals, never unweighted means of monthly rates.
    schema = build_template(recipe["id"], "test")
    with sqlite3.connect(path) as db:
        for widget in schema.widgets:
            if not any(
                m.aggregation.value == "ratio" for m in widget.publication.measures
            ):
                continue
            actual = db.execute(
                widget.query.sql, {"year": "2026", "segment": rows[-1]["segment"]}
            ).fetchone()[0]
            subset = [
                r
                for r in rows
                if r["year"] == "2026" and r["segment"] == rows[-1]["segment"]
            ]
            formula = {
                "basket": ("value", "aux", 1),
                "conversion": ("aux", "reach", 100),
                "fulfillment": ("on_time", "delivered", 100),
                "response": ("response_minutes", "value", 1),
                "completion": ("completed", "value", 100),
                "average": ("value", "aux", 1),
                "approval": ("approved", "applications", 100),
                "repayment": ("on_time", "due", 100),
            }[widget.id]
            numerator, denominator, scale = formula
            assert actual == pytest.approx(
                sum(r[numerator] for r in subset)
                / sum(r[denominator] for r in subset)
                * scale
            )
        empty = service.query_executor.execute_dashboard(
            schema, {"year": "1900", "segment": "all"}
        )
        assert all(not w.error for w in empty.values())
    # No layout overlap or placeholder/external HTML panel is accepted.
    positions = schema.layouts.desktop
    for index, left in enumerate(positions):
        for right in positions[index + 1 :]:
            assert (
                left.x + left.w <= right.x
                or right.x + right.w <= left.x
                or left.y + left.h <= right.y
                or right.y + right.h <= left.y
            )
    assert all(widget.query.sql and widget.publication for widget in schema.widgets)
