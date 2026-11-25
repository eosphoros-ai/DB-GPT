"""The MySQL schema scripts must create the wiki and knowledge source tables.

MySQL deployments do not run ``create_all``; the tables come only from the
SQL scripts under ``assets/schema``. The wiki task scheduler queries
``knowledge_wiki_task`` while the webserver starts, so a missing table stops
the webserver from starting.
"""

import re
from pathlib import Path

import pytest

from dbgpt_serve.rag.knowledge_source.models import (
    KnowledgeSourceEntity,
    KnowledgeSourceKeyEntity,
    KnowledgeSourceSyncLogEntity,
)
from dbgpt_serve.rag.models.wiki_db import (
    KnowledgeWikiPageEntity,
    KnowledgeWikiPageRevisionEntity,
    KnowledgeWikiTaskEntity,
)

ROOT = Path(__file__).parents[6]
SCHEMA_PATHS = (
    "assets/schema/dbgpt.sql",
    "assets/schema/upgrade/v0_8_3/v0.8.3.sql",
    "assets/schema/upgrade/v0_8_3/upgrade_to_v0.8.3.sql",
)
ENTITIES = (
    KnowledgeWikiPageEntity,
    KnowledgeWikiPageRevisionEntity,
    KnowledgeWikiTaskEntity,
    KnowledgeSourceEntity,
    KnowledgeSourceKeyEntity,
    KnowledgeSourceSyncLogEntity,
)


def _table_sql(sql: str, table_name: str) -> str:
    match = re.search(
        rf"CREATE TABLE IF NOT EXISTS `{table_name}` \((.*?)\n\)", sql, re.S
    )
    assert match, f"{table_name} is not created"
    return match.group(1)


@pytest.mark.parametrize("schema_path", SCHEMA_PATHS)
@pytest.mark.parametrize("entity", ENTITIES, ids=lambda e: e.__tablename__)
def test_mysql_schema_creates_table(schema_path, entity):
    sql = (ROOT / schema_path).read_text(encoding="utf-8")
    table = entity.__table__
    table_sql = _table_sql(sql, table.name)

    columns = set(re.findall(r"^\s*`(\w+)` ", table_sql, re.M))
    assert columns == set(table.columns.keys())
    assert "PRIMARY KEY (`id`)" in table_sql
    for index in table.indexes:
        index_columns = ",".join(f"`{column.name}`" for column in index.columns)
        assert f"KEY `{index.name}` ({index_columns})" in table_sql
