# Knowledge Source 连接器代码改造方案

> 前置已落地：契约层 `packages/dbgpt-ext/src/dbgpt_ext/knowledge_source/`
> （`BaseKnowledgeSourceConnector` / registry / rss 参考实现）
> 本方案给出：接入钉钉/飞书等数据源所需的**全部文件级改造**，分三个阶段落地。

---

## 0. 改造地图（文件树，按包分层）

```
packages/dbgpt-ext/src/dbgpt_ext/knowledge_source/     ← 平台无关 + 平台客户端（不依赖 dbgpt-serve）
├── base.py                    ✅ 契约
├── registry.py                ✅ 注册表
├── clients/                             【新增·阶段B/C】
│   ├── __init__.py
│   ├── http.py                          # 限流 + 重试 + 429 退避（全平台复用）
│   ├── feishu.py                        # app_token 缓存 + wiki/docx/drive/export/bitable API 封装
│   └── dingtalk.py                      # app access_token + dentry 树 + 内容 API
├── converters/                          【新增·阶段B/C】blocks → Markdown
│   ├── __init__.py
│   ├── feishu_docx.py                   # docx blocks → md（标题/表格/图片占位/代码块）
│   ├── dingtalk_blocks.py               # 钉钉 blocks → md（端点以 WeKnora client.go 对照）
│   ├── notion_blocks.py                 # notion blocks → md
│   ├── confluence_xhtml.py              # storage XHTML → md + 附件下载占位
│   └── yuque_lake.py                    # lake → md（复用现有 addYuque 转换逻辑）
└── connectors/                          【新增·阶段B/C】每个源一个类
    ├── rss.py                 ✅ 参考实现
    ├── feishu_wiki.py         【阶段B】
    ├── feishu_drive.py        【阶段B】
    ├── dingtalk.py            【阶段C】
    ├── notion.py              【阶段C】
    ├── confluence.py          【阶段C】
    └── yuque.py               【阶段C·收编】

packages/dbgpt-serve/src/dbgpt_serve/rag/knowledge_source/    ← 框架胶水（依赖 rag Service）【阶段A】
├── __init__.py
├── models.py                            # knowledge_source / knowledge_source_sync_log 两张表 + DAO
├── crypto.py                            # AES-256-GCM 凭据加解密（主密钥: configs）
├── service.py                           # 绑定 CRUD / sync 引擎（on_item→入库）/ 游标 checkpoint
├── ingest.py                            # FetchedItem → knowledge_document 适配器（衔接点，见§2）
├── scheduler.py                         # asyncio 每 60s 扫 due 绑定（模式同 wiki task scheduler）
└── api.py                               # 8 个端点（挂 /api/v2/serve/knowledge）

web/                                                     【阶段A-C 持续】
├── types/knowledgeSource.ts             # 绑定/资源/日志类型
├── client/api/knowledgeSource.ts        # 8 端点 client
├── components/knowledge/source/
│   ├── source-panel.tsx                 # 详情页「数据源」Tab（绑定卡片列表）
│   ├── binding-wizard.tsx               # ①选源(auth_fields 动态表单) ②资源树勾选 ③调度策略
│   └── sync-log-drawer.tsx
└── pages/construct/knowledge/detail.tsx # +1 Tab（'sources'）

packages/dbgpt-app/src/dbgpt_app/knowledge/…             【不动】
   （lake→md 若在 app 侧，则 converters/yuque_lake.py import 它或代码上移到 ext）
```

**分层原则**：dbgpt-ext 里的连接器只依赖 httpx + 自身 utils；所有「落库/触发 wiki」
的 glue 在 dbgpt-serve 侧，避免反向依赖。

## 1. 阶段 A：框架胶水（所有连接器的前置）

### 1.1 `models.py`（两表）

按设计文档 §5：`knowledge_source`（space_id/type/config加密/target_resources JSON/
interval_minutes/sync_mode/conflict_strategy/sync_deletions/status/last_sync_cursor/
last_sync_result/error）+ `knowledge_source_sync_log`。DAO 提供
`create_source / list_by_space / get / update_status / save_cursor`。

### 1.2 `ingest.py` —— 唯一的衔接点（§2 详细）

### 1.3 `service.py` —— sync 引擎骨架

```python
class KnowledgeSourceService:
    async def run_sync(self, source: KnowledgeSourceEntity, trigger: str) -> SyncLogSummary:
        cfg = crypto.decrypt(source.config)
        conn_cls = get_source_connector(source.type)
        connector = conn_cls()
        mapping = json.loads(source.mapping_json or "{}")      # external_id → doc_id
        cursor = SyncCursor.from_dict(json.loads(source.last_sync_cursor))
        stats = _StatsAux()
        mode_incremental = source.sync_mode == "incremental" and cursor
        fetch = connector.fetch_incremental if mode_incremental else connector.fetch_all
        new_cursor = await fetch(cfg, json.loads(source.target_resources_ids), cursor,
                                 on_item=self._on_item_factory(source, cfg, mapping, stats))
        return stats, new_cursor

    def _on_item_factory(...) -> ItemHandler:
        async def on_item(item: FetchedItem) -> None:
            action = await ingest.ingest_item(self._service, source, item, mapping,
                                              conflict=source.conflict_strategy)
            stats.count(action)
            # checkpoint：每 item 后落盘（断点续传语义）
            self._dao.save_cursor_partial(source.id, mapping, cursor_snapshot)
        return on_item
```

### 1.4 `api.py` 8 端点 + `serve.py` 挂钩

- 路由挂 RagServe（`wiki_router` 同款）；`init_knowledge_source_endpoints(system_app, config)`
- `Serve.after_start` 里：`ensure_source_connectors_loaded(extra_modules)`（读
  `[rag.knowledge_source]` 配置）→ 启动 `KnowledgeSourceScheduler` 启动 + shutdown 挂 stop
- 配置键：`[rag.knowledge_source] encrypt_key / extra_connector_modules`

## 2. `ingest.py` 的精确语义（衔接 domain/index 层的 30 行 glue）

沿用 GitRepo 短路先例（`git_repo_sync_service.py:300-317`）：

```
ingest_item(service, source, item, mapping, conflict):
 1. doc_id = mapping.get(external_id) → doc = documents_by_ids or None
 2. doc is None:
      doc = KnowledgeDocumentEntity(doc_name=item.title, doc_type="DOCUMENT",
            space=space.name, content=item.content, status=RUNNING,
            vector_ids=None, result="", gmt_*=now)          # create
 3. doc 存在:
      if conflict=="skip" and content_hash(doc.content)==hash(item.content): return "skipped"
      nums = vector_store.delete_by_ids(doc.vector_ids)；chunk_dao.raw_delete(doc.id)
      doc.content = item.content；doc.status = "RUNNING"      # 重置以重进管线
 4. doc.result="syncing：knowledge source"；update；mapping 落盘
 5. await service._sync_knowledge_document(space_id, doc, default_chunk_params(space))
    # ← 接缝：内部走 async_doc_process → Normal/DomainIndex 切片装载
    #   成功尾部既有钩子：wiki 入队（+heading graph）自动触发
 6. return "created" | "updated"
```

注意：`doc_type` 用 `DOCUMENT` 使文件视图正常显示；`source_url`/外部 id 存
`doc.result` 之外另存 mapping（避免侵入 sync 状态语义）。

## 3. 共享基建（clients/ + converters/）

### 3.1 `clients/http.py`

```python
class RateLimitedClient:      # Semaphore(N) + 429/精频退避(指数+jitter)
    def __init__(self, concurrency=3, base_backoff=1.0)
    async def get_json(url, headers, params=None, retries=3)
    async def post_json(url, headers, payload=None, retries=3)
```

### 3.2 `clients/feishu.py`（wiki+drive 共用）

```python
class FeishuClient:
    def __init__(self, app_id, app_secret)      # tenant_access_token 缓存至过期前 5min
    async def wiki_spaces()                      # GET /open-apis/wiki/v2/spaces
    async def wiki_nodes(space_id, parent_node_token="", page_token="")   # 分页
    async def docx_raw_content(obj_token)        # GET /open-apis/docx/v1/documents/:id/raw_content
    async def export_file(obj_token, file_ext)   # POST /drive/v1/export_tasks + 轮询 ticket → 下载 URL
    async def bitable_tables(app_token)          # GET /bitable/v1/apps/:app_token/tables
    async def drive_folder_files(folder_token)   # GET /open-apis/drive/v1/files
```

### 3.3 `clients/dingtalk.py`

```python
class DingTalkClient:            # app access_token（2h 缓存，unionId 处理）
    async def dentry_children(space_id, parent="")     # 文档树
    async def dentry_content(...)                      # blocks → converters/dingtalk_blocks.py
```
⚠️ 端点命名以 `WeKnora/internal/datasource/connector/dingtalk/client.go` 对照后定稿
（私有字段一致即可），不照抄 Go 代码只对照 API 路径。

### 3.4 converters 契约

```python
def feishu_blocks_to_markdown(blocks: list[dict], img_handler) -> str
def notion_blocks_to_markdown(blocks_iter, img_handler) -> str
def confluence_storage_to_markdown(xhtml: str, attachments_base) -> str
def dingtalk_blocks_to_markdown(blocks: list[dict]) -> str
def yuque_lake_to_markdown(lake: str) -> str      # 优先复用 app 侧已有实现
```
`img_handler(img_url) -> str(本地/占位链接)`：阶段 A 先返回原 URL，阶段 C 接文件存储下载。

## 4. 连接器实现卡

### 4.1 `feishu_wiki.py`【阶段B · 旗舰】

```python
@register_source_connector
class FeishuWikiConnector(BaseKnowledgeSourceConnector):
    type = "feishu_wiki"
    meta = ConnectorMeta(name="飞书知识库",
        auth_fields=[app_id(req), app_secret(req, secret=True)], supports_incremental=True)
```
| 项 | 设计 |
|---|---|
| validate | `tenant_access_token` 获取一次成功即通过 |
| list_resources | 两级懒加载：`""`→wiki 空间列表；`parent_id`→该空间下节点树（`parent_node_token` 逐层）；`ResolveResourceAncestors` 用节点 `obj_token` 反查（P1） |
| fetch_all | 对每个勾选节点：`node.obj_type` 分派 → docx(raw_content)；sheet/bitable/文件(export 轮询) → converters；`Semaphore(3)` |
| cursor | `{node_token: obj_edit_time}`；节点列表里带 edit_time，增量=比对+仅 fetch 变更节点 |
| 测试 | `tests/test_feishu_wiki.py` + FakeFeishuClient（XML/JSON fixture 端到端跑 validate→list→fetch） |

### 4.2 `feishu_drive.py`【阶段B】

- list_resources：`""`→根文件夹+用户勾选 folder token 列表（auth_fields 增加 `folder_tokens` 多值框）；
- fetch：`drive/v1/files` 树 → 每文件按类型 export（与 wiki 共用 FeishuClient.export_file）
- 非 docx 类（pdf/zip）→ `FetchedItem(content="", content_format="url")`（引擎只登记不入库正文）

### 4.3 `dingtalk.py`【阶段C】

- auth: `app_key` + `app_secret` (+`union_id` 处理按 WeKnora 经验)
- list_resources：文档树懒加载（dentry tree）
- fetch：dentry content blocks → `dingtalk_blocks_to_markdown`；图片临时 URL 经 img_handler
- cursor：节点 modified_time 快照

### 4.4 `notion.py`【阶段C】

- auth: `integration_token`
- list_resources：`POST /v1/search`（一次全树）→ ResourceInfo 树；`parent_id` 仍要兼容（过滤）
- fetch：`GET /v1/blocks/:id/children` 分页递归 → `notion_blocks_to_markdown`；child_database → 表格视图导出
- cursor：`{page_id: last_edited_time}`；`supports_incremental=True`

### 4.5 `confluence.py`【阶段C】

- auth: `base_url` + `email` + `api_token`；资源：空间列表 → CQL `space=X and type=page` 页面树
- fetch：页面 `body=storage` → `confluence_storage_to_markdown`；附件按 `/download/attachments` 下载
- cursor：CQL `lastmodified > {ts}`；冲突重试读旧值时以 `?expand` 拿 version 防竞争

### 4.6 `yuque.py`【阶段C·收编】

- auth: `token`；资源：`GET /api/v2/users/<login>/repos` 平铺（可再挂 TOC 树 P1）
- fetch：`GET /api/v2/repos/{ns}/docs` → 每篇 `?raw=1` lake → `yuque_lake_to_markdown`
- cursor: `{doc_id: updated_at}`

### 4.7 腾讯系（阶段D-E，单列）

- `tencent_ima.py`：直接移植 WeKnora `ima/client.go`（含 fake 桩测试模式）；接口私有，失败 fail-fast
- `tencent_docs.py`：docs.qq.com 开放平台 OAuth（client_id/secret/access_token）；`/openapi/drive/file_list` 树 + 导出；**先 doc 后 sheet/bitable**，API 细节以联调为准

## 5. 前端改造

| 文件 | 内容 |
|---|---|
| `types/knowledgeSource.ts` | SourceMeta / SourceBinding / ResourceInfo / SyncLog |
| `client/api/knowledgeSource.ts` | 8 端点（types 端点→动态表单） |
| `components/knowledge/source/source-panel.tsx` | 详情页「数据源」Tab：绑定卡片（图标/上次同步 N 项/状态/手动同步/日志） |
| `binding-wizard.tsx` | 3 步：选连接器(meta.icon 网格) → auth_fields 动态表单+「验证连接」→ 资源树勾选(antd Tree 懒加载 `list_resources?parent_id=`)+调度(interval/cron radio、conflict/sync_deletions) |
| `detail.tsx` | ViewTab 加 `'sources'`；仅当绑定>0 或总中心开关开启时显示 |

i18n：`locales/{zh,en}/knowledgeSource.ts`（对齐 check-locale-parity）。

## 6. 测试与验收

1. **契约测试**：每个连接器一份 `test_<source>.py`，Fake client（对齐 WeKnora fake_ima 模式）跑
   validate→list_resources(两层)→fetch_all(≥2 items)→cursor 快照→fetch_incremental（模拟 1 变更）
2. **ingest 适配器单测**：fake connector 出 2 items → 断言 created=2 文档（status FINISHED）/ 二次同步
   content 不变 → skipped / 变更 → updated(+chunks 重建+wiki 任务入队)
3. **e2e**：真实语雀/飞书凭据起服务绑定 → 手动同步 → 文件视图可见 → Wiki 增量页面出现
4. **验收口径**：新绑一个源从「创建绑定」到「文档+Wiki 页面出现」≤ 3 次点击 + 1 个同步周期

## 7. 工时与顺序

| 阶段 | 内容 | 人估 |
|---|---|---|
| A | §1+§2 胶水 + API + scheduler + serve 挂钩 + 前端 Tab/向导骨架 | 5d |
| B | http/feishu client + converters/feishu_docx + wiki/drive 两连接器 + fake 测试 | 4d |
| C | dingtalk/notion/confluence/yuque 四连接器（每源 ~1.5d 含转换器+测试） | 6d |
| D | 图片/附件落存储 img_handler + croniter + 删除同步 ✓ | 3d |
| E | 腾讯 IMA 移植 + 腾讯文档联调 | 按需 |

依赖：B/A 可并行；C 依赖 A(+B 的 converters 模式)；D 依赖 B。

## 8. 风险

1. 钉钉/飞书接口字段以 WeKnora client.go 对照为准（Go 源码即参考手册），不要凭记忆写端点
2. multimetable 内容（sheet/bitable）转 markdown 信息损失：先保「结构化表格」最小语义，
   单元格换行/合并单元格为 P2
3. encrypt_key 缺失时服务禁用 knowledge_source 功能并告警（凭据明文是红线）
4. 限流配额（飞书按应用频控/钉钉按 QPM）：`RateLimitedClient` 参数按源配置化
