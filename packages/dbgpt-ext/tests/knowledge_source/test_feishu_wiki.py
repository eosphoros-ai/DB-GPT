"""Contract tests for the Feishu wiki connector (fake client, no network)."""

import asyncio
from typing import List

from dbgpt_ext.knowledge_source.base import FetchedItem, SyncCursor
from dbgpt_ext.knowledge_source.connectors.feishu_wiki import FeishuWikiConnector
from dbgpt_ext.knowledge_source.registry import ConnectorRegistry


class FakeFeishuClient:
    """In-memory stand-in mirroring FeishuClient's surface."""

    def __init__(self):
        self.block_queries = 0

    async def _token_header(self):
        return {"Authorization": "Bearer fake"}

    async def wiki_spaces(self):
        return [{"space_id": "7101", "name": "产品知识库"}]

    async def wiki_nodes(self, space_id, parent_node_token=""):
        if not parent_node_token:
            return [
                {
                    "node_token": "nod-docx",
                    "obj_token": "docx1",
                    "obj_type": "docx",
                    "title": "接入指南",
                    "has_child": True,
                    "obj_edit_time": 1727100000,
                },
                {
                    "node_token": "nod-old",
                    "obj_token": "olddoc",
                    "obj_type": "doc",
                    "title": "老文档",
                    "has_child": False,
                    "obj_edit_time": 1727100001,
                },
            ]
        return [
            {
                "node_token": "nod-docx2",
                "obj_token": "docx2",
                "obj_type": "docx",
                "title": "子页面",
                "has_child": False,
                "obj_edit_time": 1727200000,
            }
        ]

    async def docx_blocks(self, doc_token):
        self.block_queries += 1
        if doc_token == "docx1":
            return [
                {
                    "block_id": "b0",
                    "block_type": 1,
                    "children": ["b1", "b2", "b3", "b4"],
                },
                {
                    "block_id": "b1",
                    "block_type": 3,
                    "heading1": {"elements": [{"text_run": {"content": "接入指南"}}]},
                },
                {
                    "block_id": "b2",
                    "block_type": 2,
                    "text": {
                        "elements": [{"text_run": {"content": "第一步，创建应用。"}}]
                    },
                },
                {
                    "block_id": "b3",
                    "block_type": 12,
                    "bullet": {"elements": [{"text_run": {"content": "获取 app_id"}}]},
                },
                {
                    "block_id": "b4",
                    "block_type": 31,
                    "table": {
                        "cells": ["c1", "c2", "c3", "c4"],
                        "property": {"row_size": 2, "col_size": 2},
                    },
                    "children": [],
                },
                {
                    "block_id": "c1",
                    "block_type": 34,
                    "text": {"elements": [{"text_run": {"content": "字段"}}]},
                },
                {
                    "block_id": "c2",
                    "block_type": 34,
                    "text": {"elements": [{"text_run": {"content": "说明"}}]},
                },
                {
                    "block_id": "c3",
                    "block_type": 34,
                    "text": {"elements": [{"text_run": {"content": "app_id"}}]},
                },
                {
                    "block_id": "c4",
                    "block_type": 34,
                    "text": {"elements": [{"text_run": {"content": "应用唯一标识"}}]},
                },
            ]
        return [
            {"block_id": "s1", "block_type": 1, "children": ["s2"]},
            {
                "block_id": "s2",
                "block_type": 2,
                "text": {"elements": [{"text_run": {"content": "子页面内容"}}]},
            },
        ]

    async def docx_raw_content(self, doc_token):
        return "raw fallback"


def _connector():
    conn = FeishuWikiConnector(client=FakeFeishuClient())
    return conn


def test_registered():
    ConnectorRegistry.register(FeishuWikiConnector)  # idempotent for same class
    assert "feishu_wiki" in ConnectorRegistry.all_types()


def test_list_resources_two_levels():
    conn = _connector()
    top = asyncio.run(conn.list_resources({}, ""))
    assert [r.title for r in top] == ["产品知识库"] and top[0].has_children
    children = asyncio.run(conn.list_resources({}, top[0].external_id))
    titles = [r.title for r in children]
    assert "接入指南" in titles and "老文档" in titles


def test_fetch_all_walks_tree_and_converts():
    conn = _connector()
    items: List[FetchedItem] = []

    async def on_item(item):
        items.append(item)

    cursor = asyncio.run(conn.fetch_all({}, ["space:7101"], on_item, None))
    docx_items = [i for i in items if i.metadata.get("obj_type") == "docx"]
    assert len(docx_items) == 2  # 接入指南(docx1) + 子页面(docx2)
    guide = next(i for i in docx_items if i.title == "接入指南")
    assert "# 接入指南" in guide.content
    assert "第一步，创建应用。" in guide.content
    assert "- 获取 app_id" in guide.content
    assert (
        "| 字段 | 说明 |" in guide.content
        and "| app_id | 应用唯一标识 |" in guide.content
    )
    # old doc / non-docx → skipped
    assert all(i.metadata.get("obj_type") != "doc" for i in items)
    # cursor records all visited docx nodes with edit times
    assert cursor.get("nod-docx") == "1727100000"
    assert cursor.get("nod-docx2") == "1727200000"


def test_fetch_incremental_skips_unchanged_and_refetches_changed():
    conn = _connector()

    def run(cursor):
        items = []

        async def on_item(item):
            items.append(item)

        new_cursor = asyncio.run(
            conn.fetch_incremental({}, ["space:7101"], cursor, on_item)
        )
        return items, new_cursor

    # pass 1: everything unchanged
    cursor = SyncCursor(
        {"nod-docx": "1727100000", "nod-docx2": "1727200000", "nod-old": "1"}
    )
    items, cursor = run(cursor)
    assert items == []

    # pass 2: pretend the sub page is older than the tree says → refetch
    cursor.set("nod-docx2", "0")
    items, cursor = run(cursor)
    assert [i.title for i in items] == ["子页面"]
    assert cursor.get("nod-docx2") == "1727200000"  # snapshotted to tree value


def test_converter_table_fallback_with_missing_cells():
    from dbgpt_ext.knowledge_source.converters.feishu_docx import (
        feishu_blocks_to_markdown,
    )

    md = feishu_blocks_to_markdown(
        [
            {"block_id": "p", "block_type": 1, "children": ["t1"]},
            {
                "block_id": "t1",
                "block_type": 2,
                "text": {"elements": [{"text_run": {"content": "plain"}}]},
            },
        ]
    )
    assert md.strip() == "plain"
