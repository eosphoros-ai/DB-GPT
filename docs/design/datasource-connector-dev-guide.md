# 社区开发者指南：接入一个自定义数据源

> 契约层已落地：`packages/dbgpt-ext/src/dbgpt_ext/knowledge_source/`
> 参考实现：同目录 `connectors/rss.py`（本指南所有示例都来自这个能跑的文件）
> 架构背景见 `external-datasource-framework.md`

## 命名澄清

`knowledge_source` 面向**外部文档平台**（飞书/语雀/Notion/RSS…）。
数据库连接（MySQL/Postgres/Spark…）在 `dbgpt_ext.datasource`，两者互不相干。

## TL;DR

写一个类，实现 5 个方法，挂上 `@register_source_connector` 装饰器（或打包成 entry-points），结束。
前端配置表单、凭据加密、资源树、增量同步、命中现有管线（切片/检索/LLM-Wiki 更新）全部由框架负责。

```python
# my_connector.py — 一个最小可用的连接器
from dbgpt_ext.knowledge_source.base import (
    BaseKnowledgeSourceConnector, ConnectorError, ConnectorMeta, ConnectorAuthField,
    FetchedItem, ResourceInfo,
)
from dbgpt_ext.knowledge_source.registry import register_source_connector

@register_source_connector
class MyWikiConnector(BaseKnowledgeSourceConnector):
    type = "my_wiki"           # 全局唯一类型标识
    meta = ConnectorMeta(
        name="My WIKI",
        auth_fields=[
            ConnectorAuthField(key="base_url", label="API 地址", required=True),
            ConnectorAuthField(key="token", label="Token", required=True, secret=True),
        ],
        supports_incremental=True,
    )

    async def validate(self, config):          # 点「验证连接」时调用
        if not config.get("token"):
            raise ConnectorError("token 不能为空")

    async def list_resources(self, config, parent_id=""):
        # parent_id="" → 顶层；否则返回该节点的直接子级（懒加载树）
        return [ResourceInfo(external_id="root", title="我的空间", has_children=True)]

    async def fetch_all(self, config, resource_ids, on_item, cursor=None):
        # 逐条回调，不要攒大列表
        for doc in await api.list_docs(resource_ids):
            await on_item(FetchedItem(
                external_id=doc.id, title=doc.title,
                content=doc.markdown, source_url=doc.url,
                updated_at=doc.updated_at,
            ))
        return cursor  # SyncCursor：完整快照，不是 delta

    async def fetch_resource(self, config, resource_id):
        return await api.get_doc(resource_id)  # 返回 None 时引擎走 fetch_all 路径
```

本地开发期间，往 toml 里加一行即可让 server 认识它（无需打包）：

```toml
[rag.knowledge_source]
extra_connector_modules = ["my_connector"]
```

成熟后打包发布，改成 pip 即插：

```toml
# 你的 pyproject.toml
[project.entry-points."dbgpt.knowledge_sources"]
my_wiki = "my_connector:MyWikiConnector"
```

---

## 1. 两个必须知道的数据结构

### `FetchedItem` — 你交给框架的东西

| 字段 | 约定 |
|---|---|
| `external_id` | **平台内唯一且永久稳定**的 id。框架用它做「这页上次同步过吗」的映射键，换值会产生重复文档 |
| `title` | 文档名（会成为知识库文档名） |
| `content` | **Markdown 正文**（二进制/富文本平台需自行转换）。`content_format="html"` 时框架侧后续接 HTML 清洗入管线 |
| `source_url` | 平台原文链接（前端「查看原文」用） |
| `updated_at` | 来源修改时间。增量比对/排序都依赖它，能拿到务必填 |
| `metadata` | 附件链接、作者等旁路信息（不进检索正文） |

### `SyncCursor` — 增量的记忆

- 它是**完整可续传快照**，不是增量 diff——超时中断后框架从上次 checkpoint 恢复时，必须能仅凭它复现全部进度
- 典型用法：`{文档id: 最后修改时间}` 或 `{分页起始 token}`，`set/get` 读写，框架序列化后存 `knowledge_datasource.last_sync_cursor`
- 平台没有变更 API？保持默认 `fetch_incremental` = 回退全量（框架按 content hash 去重，不会产生脏更新）

## 2. 五个方法什么时候被调、契约是什么

| 方法 | 调用时机 | 契约 |
|---|---|---|
| `validate(config)` | 绑定向导点「验证连接」；首次绑定落库前 | 只读测试。失败抛 `ConnectorError`（信息会显示给用户） |
| `list_resources(config, parent_id)` | 资源树勾选器，用户每次展开节点 | 树形数据源：`parent_id=""` 给顶层，其余给直接子级；**平铺/一次全树**的可忽略 parent_id、对非空 parent 返回 `[]`（参考 rss.py） |
| `fetch_all(config, resource_ids, on_item, cursor)` | 手动同步 / 已勾选资源的全量同步 | **流式逐条** `await on_item(...)`；大列表攒内存会拖垮万级库 |
| `fetch_incremental(config, resource_ids, cursor, on_item)` | 定时增量触发（有 cursor 时） | 只回传变更项；结束返回新快照。默认实现就是回退全量 |
| `fetch_resource(config, resource_id)` | 框架对单资源做变更检测重拉 | 找不到返回 `None`（引擎自动降级 fetch_all） |

## 3. 平台适配的常见处理

- **富文本 → Markdown**：飞书 docx / Notion / 钉钉 blocks 都是 block 遍历映射（标题/表格/列表/图片）
- **分页**：在 `fetch_all` 内部循环调 `on_item`，把「当前页 token」写进 cursor 并周期性返回——框架在每个 item 后都会做 checkpoint
- **限流**：用 `asyncio.Semaphore` 控并发；对 429 做指数退避**抛错前重试**（参考 rss 超时处理：`httpx.HTTPError → ConnectorError`）
- **图片/附件**：平台临时 URL 会过期 → 下载后把链接写进 `metadata`，入管线时由框架统一替换为本地存储（框架侧能力，P1）
- **树形平台的「已选回显」**：返回树时带上正确 `parent_id`，勾选过的深层节点在前端刷新后能重新展开定位

## 4. 注册与打包

### 方式 A：pip entry-points（推荐，发布到 PyPI 的连接器）

```toml
[project.entry-points."dbgpt.knowledge_sources"]
my_wiki = "my_connector:MyWikiConnector"
```

用户 `pip install db-gpt-source-my-wiki` → 重启 DB-GPT → 完成。
`registry.ensure_datasource_connectors_loaded()` 在启动时自动扫描该 group，加载失败（模块坏了）只记日志不会拖垮主服务。

### 方式 B：toml 模块声明（单机试验）

```toml
[rag.knowledge_source]
extra_connector_modules = ["my_connector", "company_connectors.hub"]
```

### 方式 C：进程内装饰器（写测试 / notebook 原型）

```python
from dbgpt_ext.knowledge_source.registry import register_source_connector
@register_source_connector
class MyConnector(...): ...
```

注册时框架会校验：`type` 唯一非空、`meta.name` 必填——冲突在启动时炸而不是同步中途。

## 5. 契约自测（强烈建议照抄）

```python
import asyncio
from dbgpt_ext.datasource import ensure_datasource_connectors_loaded, get_connector

ensure_datasource_connectors_loaded()          # 或显式 import 你的模块

async def smoke():
    conn = get_connector("my_wiki")()
    await conn.validate(CONFIG)
    top = await conn.list_resources(CONFIG, "")
    seen = []
    async def on_item(item): seen.append(item)
    cursor = await conn.fetch_all(CONFIG, [top[0].external_id], on_item)
    assert seen and all(i.content for i in seen)
    again = await conn.fetch_incremental(CONFIG, [t.external_id for t in top], cursor, on_item)
    print(len(seen), "items; cursor keys:", len(again.to_dict()))

asyncio.run(smoke())
```

参考 `connectors/rss.py` 已经照这个模板对着真实 feed 跑通过（validate → list → fetch → cursor 快照）。

## 6. FAQ

- **Q: 我的平台没有资源树概念（如 RSS / 网页监控）？**
  `list_resources` 返回一个顶层节点（id 直接用配置里的 url），树形交互自动退化为单选。
- **Q: external_id 用 slug 行不行？**
  行，但平台改名 slug 会变——优先数字 id / guid，别用标题。
- **Q: 怎么让前端配置表单有中文标签和密文输入？**
  全靠 `meta.auth_fields`：`label` 填中文，`secret=True` 渲染密码框且落库 AES 加密。
- **Q: 增量怎么做最稳？**
  cursor 记 `{external_id: updated_at}`。fetch 时只对 `updated_at` 变化的条目回调；拿不到变更 API 就全量+去重（默认行为，不会坏数据）。
- **Q: 同步进来的文档和手动上传有区别吗？**
  没有。走同一条 `knowledge_document → sync_document` 管线：切片、检索、**LLM-Wiki 增量更新**（若空间开启）全自动。
