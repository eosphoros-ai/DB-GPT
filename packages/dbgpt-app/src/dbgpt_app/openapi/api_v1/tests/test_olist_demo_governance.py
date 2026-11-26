"""Keep the bundled and generated Olist demo aligned with its governance SQL."""

import re
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_demo_governance_queries(tmp_path):
    root = next(
        p for p in Path(__file__).resolve().parents if (p / "examples/olist").is_dir()
    )
    doc = (root / "examples/olist/olist-analytics-metric-governance.md").read_text(
        encoding="utf-8"
    )
    queries = re.findall(r"```sql\s*(.*?)```", doc, re.S)
    assert len(queries) == 3
    generated = tmp_path / "demo.db"
    subprocess.run(
        [
            sys.executable,
            str(root / "examples/olist/build_demo.py"),
            "--output",
            str(generated),
        ],
        check=True,
    )
    for path in [root / "pilot/examples/Olist_Ecommerce.db", generated]:
        with sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True) as db:
            for query in queries:
                rows = db.execute(
                    query, {"start_date": "2017-01-01", "end_date": "2018-09-01"}
                ).fetchall()
                assert rows
            total = db.execute(
                queries[0], {"start_date": "2017-01-01", "end_date": "2018-09-01"}
            ).fetchone()
            assert total[0] > 0 and total[1] > 0
