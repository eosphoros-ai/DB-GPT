---
sidebar_position: 5
title: 自定义知识数据源连接器
---

# 自定义知识数据源连接器

本指南说明如何接入一个新的外部文档平台（类似内置的**飞书**、**语雀**、**RSS** 连接器），使其文档自动进入 DB-GPT 知识空间——分块、检索、LLM-Wiki 更新全链路无需额外代码。

全部实现集中在一个接口之后。前端的凭据表单、凭据加密存储、懒加载资源树、增量同步与入库管线均由框架提供。

## 架构一图

```
你的连接器（validate / list_resources / fetch_*）
        │  通过 entry-points、配置模块或装饰器注册
        ▼
知识源同步引擎（调度 / 游标 checkpoint / 冲突策略）
        │  FetchedItem（Markdown）→ knowledge_document
        ▼
标准知识管线（分块 → 索引 → 检索 → LLM-Wiki）
```

契约层代码（建议对照阅读）：

- `packages/dbgpt-ext/src/dbgpt_ext/knowledge_source/base.py` — 接口定义
- `packages/dbgpt-ext/src/dbgpt_ext/knowledge_source/registry.py` — 发现与注册
- `packages/dbgpt-ext/src/dbgpt_ext/knowledge_source/connectors/rss.py` — 最小参考连接器

## 快速开始（一个完整连接器）

```python
# my_connector.py —— 一个 OpenAPI 风格的 wiki 平台
from typing import Dict, List, Optional
from dbgpt_ext.knowledge_source.base import (
    BaseKnowledgeSourceConnector,
    ConnectorAuthField,
    ConnectorError,
    ConnectorMeta,
    FetchedItem,
    ResourceInfo,
    SyncCursor,
)
from dbgpt_ext.knowledge_source.registry import register_source_connector


@register_source_connector
class MyWikiConnector(BaseKnowledgeSourceConnector):
    type = "my_wiki"  # 全局唯一，作为绑定记录的类型
    meta = ConnectorMeta(
        name="My Wiki",
        description="同步内部 wiki 的页面",
        auth_fields=[
            ConnectorAuthField(key="base_url", label="API 地址", required=True),
            ConnectorAuthField(key="token", label="Token", required=True, secret=True),
        ],
        supports_incremental=True,
    )

    async def validate(self, config: Dict[str, str]) -> None:
        """用户在向导中点击「验证连接」时触发。"""
        me = await api_get(config, "/user")
        if not me:
            raise ConnectorError("token 无效")

    async def list_resources(
        self, config: Dict[str, str], parent_id: str = ""
    ) -> List[ResourceInfo]:
        """为范围选择器返回资源树。

        parent_id == ""  → 顶层行（如空间）
        parent_id != ""  → 该行的直接子级（懒加载）
        """
        parent = parent_id or "root"
        return [
            ResourceInfo(
                external_id=page_id,          # 稳定的平台 id
                title=page_title,
                parent_id=parent if parent_id else None,
                has_children=False,
                resource_type="page",
            )
            for page_id, page_title in await api_list_pages(config, parent)
        ]

    async def fetch_all(
        self,
        config: Dict[str, str],
        resource_ids: List[str],
        on_item,                       # 异步回调——逐条产出条目
        cursor: Optional[SyncCursor] = None,
    ) -> SyncCursor:
        cursor = cursor or SyncCursor()
        for doc in await api_fetch_docs(config, resource_ids):
            await on_item(
                FetchedItem(
                    external_id=doc["id"],        # 永久稳定，不要用标题
                    title=doc["title"],
                    content=doc["markdown"],      # Markdown 进入管线
                    source_url=doc["url"],
                    updated_at=doc["updated_at"],  # 驱动增量同步
                )
            )
            cursor.set(doc["id"], doc["updated_at"])
        return cursor

    async def fetch_resource(
        self, config: Dict[str, str], resource_id: str
    ) -> Optional[FetchedItem]:
        return await api_get_doc(config, resource_id)  # 返回 None 则回退 fetch_all
```

这就是连接器的全部内容。完成注册（见下）并重启 DB-GPT，它会出现在 **知识库 → 数据源 → 绑定外部数据源** 中，凭据表单通过 `meta.auth_fields` 自动生成——无需任何前端代码。

## 五个方法的详细契约

| 方法 | 触发时机 | 契约 |
|---|---|---|
| `validate(config)` | 向导中的「验证连接」 | 只读探针；失败抛出带友好提示的 `ConnectorError` |
| `list_resources(config, parent_id)` | 用户每次展开树节点 | `parent_id == ""` → 顶层；否则直接子级。平铺平台忽略 `parent_id`，仅返回一行 |
| `fetch_all(config, resource_ids, on_item, cursor)` | 全量同步（手动/定时/兜底） | 通过 `await on_item(...)` 逐条流式产出；不要在内存中累积全量语料。返回最终 `SyncCursor` 快照 |
| `fetch_incremental(config, resource_ids, cursor, on_item)` | 定时增量同步 | 仅产出变更条目；返回更新后的游标。默认实现直接调用 `fetch_all`（引擎按内容哈希去重） |
| `fetch_resource(config, resource_id)` | 单资源刷新 | 返回 `None` 表示让引擎回退到 `fetch_all` |

## 数据契约规则

- **`external_id` 必须永久稳定**——它把平台条目映射到本地文档。只用数字 id/guid；标题和 slug 会变。
- **`content` 必须是 Markdown**——平台负载（blocks、XHTML、lake）先转换再产出；管线按原样分块与向量化。
- **`updated_at` 驱动增量同步**——平台提供编辑时间时务必填写；否则保持默认的全量重拉行为。
- **`SyncCursor` 是可恢复快照**，不是增量。序列化必须支持超时中断后从 checkpoint 恢复（常见形态：`{external_id: updated_at}` 或 `{next_page_token}`）。
- 通过 `on_item` **逐条**产出条目——引擎会在每条之后 checkpoint 游标。

## 注册（三种方式）

### A. pip entry-points（推荐，发布到 PyPI）

```toml
# 你的包 pyproject.toml
[project.entry-points."dbgpt.knowledge_sources"]
my_wiki = "my_connector:MyWikiConnector"
```

用户 `pip install your-connector` 并重启 DB-GPT。

### B. 配置声明模块（本地开发）

```toml
[rag.knowledge_source]
extra_connector_modules = ["my_connector"]
```

### C. 进程内装饰器（测试 / 原型）

```python
from dbgpt_ext.knowledge_source.registry import register_source_connector
@register_source_connector
class MyConnector(...): ...
```

注册时会校验 `type` 唯一、`meta.name` 必填，坏插件在启动时报错而不是同步中途。

## 零前端代码的凭据表单

`meta.auth_fields` 驱动绑定向导的表单：

```python
ConnectorAuthField(key="base_url", label="API 地址", required=True)
ConnectorAuthField(key="token", label="API Token", required=True, secret=True)
```

`secret=True` 渲染为密码输入框并以 AES-256-GCM 加密存储。表单布局、校验展示与加密全部由框架处理。

## 契约自测

参考 `packages/dbgpt-ext/tests/knowledge_source/`（飞书与语雀套件）：一个 Fake API 客户端 + 固定数据，覆盖
`validate → list_resources（两级）→ fetch_all（≥2 条）→ 游标快照 → fetch_incremental（1 条变更）`。Mock 平台 API，无需真实网络，断言产出的 `FetchedItem` 与返回的游标。

## 参考实现

| 连接器 | 文件 | 适合学习 |
|---|---|---|
| RSS | `.../knowledge_source/connectors/rss.py` | 平铺范围、单循环抓取、HTML→Markdown |
| 语雀 | `.../knowledge_source/connectors/yuque.py` | 个人+团队仓库合并、分页、格式防护 |
| 飞书知识库 | `.../knowledge_source/connectors/feishu_wiki.py` | 两级懒加载树、按类型内容分发、编辑时间增量 |
| 飞书云盘 | `.../knowledge_source/connectors/feishu_drive.py` | 文件夹遍历、docx blocks 转换 |

## FAQ

- **平台没有树概念（订阅源、监控）？** 返回一个顶层资源；选择器自动退化为单选。
- **分页？** 在 `fetch_all`/`list_resources` 内循环翻页，把页码 token 写入 `SyncCursor`。
- **限流？** 用 `asyncio.Semaphore` 包并发，429 指数退避，重试耗尽后抛 `ConnectorError`。
- **附件图片？** 平台 URL 放入 `FetchedItem.metadata`，引擎的附件处理器会下载并重写为本地存储。
- **插件加载失败？** 启动时导入失败只记日志并跳过——服务器照常启动，修复后重启。

## 数据去向

`FetchedItem → knowledge_document（doc_type=TEXT） → 标准分块/向量化管线`。同步进来的文档在检索与对话中与手动上传的文档完全等价；空间开启 Wiki 时受影响页面自动再生。
