# DB-GPT 外接数据源（Connector）框架设计

> 参考项目：WeKnora `internal/datasource/`（连接器契约 / 资源树 / 增量游标 / Cron 调度 / 加密凭据）。
> 覆盖数据源：语雀、飞书知识库、飞书云盘、钉钉文档、Notion、Confluence、腾讯 IMA、腾讯文档。
> 注：**WeKnora 没有腾讯文档连接器**（只有腾讯 IMA），腾讯文档按 docs.qq.com 开放平台自行设计。

---

## 1. 目标

1. 让知识库空间能**绑定**外部平台数据源，把文档自动同步进来（→ 切片 → 检索 → LLM-Wiki 增量更新，与现有管线无缝衔接）
2. 提供**统一连接器契约**：社区开发者按接口实现一个类（+ 声明式注册）即可接入新平台，不改框架代码
3. 统一治理：凭据加密落库、资源树勾选、全量/增量同步、冲突策略、同步日志

## 2. 架构总览

```
外部平台 API（飞书/Notion/钉钉/...）
        │
┌────────▼─────────────────────────────────────────────────┐
│ Connector 契约层（dbgpt_ext/knowledge_source/connectors/*）     │
│  validate / list_resources / fetch_all / fetch_incremental│
└────────┬─────────────────────────────────────────────────┘
         │ 注册表 ConnectorRegistry（内置 + entry_points 插件）
┌────────▼─────────────────────────────────────────────────┐
│ DatasourceService（dbgpt_serve/rag/knowledge_source/service.py）│
│  CRUD / 凭据加密 / 资源发现 / 手动同步 / 冲突处理          │
└─────┬──────────────────────────────┬─────────────────────┘
      │ item(content Markdown)       │ due 触发
┌─────▼──────────┐          ┌────────▼──────────────────┐
│ 文档入库适配     │          │ 同步调度器 SyncScheduler   │
│ create/update   │          │ (asyncio 每 60s 扫 due 绑定 │
│ knowledge_      │          │  — 复用 wiki 调度器模式     │
│ document → 现有  │          │  P1 升级 croniter)        │
│ sync_document   │          └───────────────────────────┘
│ → chunk/wiki 链 │
└────────────────┘
```

**核心原则：连接器只负责「发现资源 + 取内容」，入库一律走现有 `knowledge_document → sync_document`
管线。** 同步进来的文档与手工上传的文档在处理层零差异（切片/检索/Wiki 增量自动生效）。

## 3. 连接器契约（对齐 WeKnora six-method 接口）

`dbgpt_ext/knowledge_source/base.py`：

```python
@dataclass
class ResourceInfo:
    """资源树节点：飞书=空间/Wiki 节点, 语雀=知识库/文档, Notion=页面树"""
    external_id: str          # 平台内唯一 id
    parent_id: Optional[str]  # 树形资源的父节点；平铺型语雀/RSS 传 None
    title: str
    has_children: bool
    resource_type: str        # "wiki_space"/"page"/"folder"/"doc"/"feed"

@dataclass
class FetchedItem:
    external_id: str
    title: str
    content: str              # Markdown（二进制类内容走 content_url）
    content_format: str = "markdown"   # markdown | html | url
    source_url: str = ""
    updated_at: Optional[datetime] = None
    metadata: dict = field(default_factory=dict)

@dataclass
class SyncCursor:            # 完整可续传快照（非 delta），参考 WeKnora #2136
    cursor: dict = field(default_factory=dict)

class BaseKnowledgeSourceConnector(ABC):
    type: ClassVar[str]                       # "feishu_wiki" / "yuque" / ...
    meta: ClassVar[ConnectorMeta]             # 名称/图标/认证字段 schema（供前端渲染表单）

    @abstractmethod
    async def validate(self, config: dict) -> None: ...
    """测试连通性，失败抛 ConnectorError。验证不落库。"""

    @abstractmethod
    async def list_resources(self, config: dict, parent_id: str = "") -> List[ResourceInfo]: ...
    """parent_id="" 返回顶层（懒加载资源树）；一次性全树的平台可忽略。"""

    @abstractmethod
    async def fetch_all(self, config: dict, resource_ids: List[str],
                        on_item: Callable[[FetchedItem], Awaitable]) -> None: ...
    """全量拉取，逐条回调（流式消费，避免整库驻留内存）。"""

    async def fetch_incremental(self, config: dict, cursor: SyncCursor,
                                on_item: Callable[[FetchedItem], Awaitable]) -> SyncCursor: ...
    """平台支持增量时实现；默认实现回退 fetch_all（返回新 cursor 时建议带上资源 mtime）。"""

    async def fetch_resource(self, config: dict, resource_id: str) -> Optional[FetchedItem]: ...
    """单个资源内容（更新检测后重拉单个文档时用）。"""
```

要点（来自 WeKnora 实战经验）：
- **逐条回调（流式）** 而非返回大列表：万级文档知识库不爆内存；`on_item` 由框架提供（入库 + checkpoint）
- **SyncCursor 必须是完整快照**：超时中断可从上次 checkpoint 续传，全量同步失败可断点重来
- **`meta.used_fields`** 声明认证字段 schema（`app_id`/`app_secret`/`token`...），前端据此自动渲染配置表单——社区连接器不用改前端代码

## 4. 社区自定义数据源（扩展协议）⭐

三层发现机制，优先级从高到低：

### 4.1 entry_points 插件（推荐，pip install 即用）

`pyproject.toml`（社区开发者的包）：

```toml
[project.entry-points."dbgpt.knowledge_sources"]
my_gitea = "my_gitea_connector.connector:GiteaConnector"
```

框架启动时扫描该 group：

```python
# dbgpt_ext/datasource/registry.py
from importlib.metadata import entry_points

def load_external_connectors():
    for ep in entry_points(group="dbgpt.knowledge_sources"):
        connector_cls = ep.load()
        ConnectorRegistry.register(connector_cls)   # 校验 type 唯一性 + 契约完整性
```

### 4.2 配置声明外部模块（单机快速试验，无需打包）

```toml
# configs/dbgpt-*.toml
[rag.knowledge_source]
extra_connector_modules = ["my_project.connectors"]   # importlib.import_module 扫 @register_connector
```

### 4.3 进程内注册（测试/Notebook）

```python
from dbgpt_ext.datasource.registry import register_connector
from dbgpt_ext.datasource.base import BaseKnowledgeSourceConnector

@register_connector
class GiteaConnector(BaseKnowledgeSourceConnector):
    type = "gitea"
    meta = ConnectorMeta(
        name="Gitea", icon="gitea", auth_fields=[
            {"key": "base_url", "label": "API 地址", "required": True},
            {"key": "token", "label": "Access Token", "required": True, "secret": True},
        ],
        supports_incremental=True,
    )
    ...
```

**最小的社区连接器长这样**（平铺型 数据源，~40 行）：

```python
@register_connector
class RSSConnector(BaseKnowledgeSourceConnector):
    type = "rss"
    meta = ConnectorMeta(name="RSS", auth_fields=[{"key": "feed_url", "required": True}])

    async def validate(self, config):
        feed = await fetch(config["feed_url"]);  assert feed.ok

    async def list_resources(self, config, parent_id=""):
        return [ResourceInfo(external_id=config["feed_url"], parent_id=None,
                             title=feed.title, has_children=False, resource_type="feed")]

    async def fetch_all(self, config, resource_ids, on_item):
        for entry in await entries(config["feed_url"]):
            await on_item(FetchedItem(external_id=entry.id, title=entry.title,
                                      content=entry.to_markdown(), source_url=entry.link,
                                      updated_at=entry.updated))
```

**契约校验**（注册时强制）：`type` 非空且全库唯一；`auth_fields` 字段 key 可加密；`list_resources` 支持 `parent_id=""`；`fetch_all` 能对 `list_resources` 返回的任意 id 工作。提供 `pytest` 基类 `DatasourceConnectorContractTest`，社区连接器继承后填 2 个 fixture 即可跑契约测试。

## 5. 数据模型（2 张表）

### `knowledge_datasource`（WeKnora data_sources 的裁剪版）

| 字段 | 类型 | 说明 |
|---|---|---|
| id / space_id | PK / FK idx | 绑定到知识空间 |
| name, type | String | 展示名 / 连接器类型（registry 校验存在） |
| config | Text(AES-GCM) | 加密凭据+配置（`auth_fields` schema 渲染；AES-256-GCM 对齐 WeKnora） |
| target_resources | Text(JSON) | 用户勾选的资源 [{resource_type, external_id, title}] |
| sync_schedule | String | P0 `interval_minutes`；P1 起 cron 表达式（croniter） |
| sync_mode | String | `incremental` \| `full` |
| conflict_strategy | String | `overwrite`（更新文档并重新同步） \| `skip` |
| sync_deletions | Bool | 源端删除是否级联删除本地文档 |
| status | String | `active` \| `paused` \| `error` |
| last_sync_at / last_sync_cursor(JSON) / last_sync_result(JSON) / error_message | | 游标 = 可续传快照 |

### `knowledge_datasource_sync_log`

`datasource_id, trigger(manual/schedule), mode, items_fetched, items_created, items_updated, items_deleted, status, error, started_at, finished_at`（保留 30 天）

## 6. 同步执行流（复用现有管线）

```
触发(手动/定时) → 取绑定 → Registry 解析连接器
→ sync_mode=incremental && cursor 存在 ? fetch_incremental : fetch_all(勾选资源)
→ on_item 逐条：
    1. resolve：external_id → knowledge_document（映射表 datasource.mapping JSON 存 external_id↔doc_id）
    2. 无 → create：knowledge_document(doc_name=title, doc_type='DOCUMENT', content=Markdown)
    3. 有 → content 未变(updated_at/hash) ? skip : update(content)
    4. sync_document(space, {doc_id, chunk_parameters})  ← 现有管线
       sync 成功回调自动 enqueue wiki ingest（已有）→ Wiki 自动增量更新 ✓
    5. checkpoint(cursor) 每 N 条
→ 同步删除审计(sync_deletions=true 时，源端不存在的 → delete_document)
→ 写 sync_log / 更新绑定 cursor/status
```

删除文档走 `Service.delete_document`，其尾部已挂 wiki reconcile —— 全链路闭环。

## 7. 八个数据源逐个设计

### 7.1 语雀 `yuque`（已有能力收编为首个标准连接器）

- **认证**：`token`（个人私有 Token）
- **资源模型**：平铺——`list_resources` 拉 token 可见知识库列表（`GET /api/v2/users/{login}/repos`），一层树
- **内容**：文档正文接口 `GET repos/{ns}/docs/{slug}` body 为lake 格式 → **lake→Markdown 转换**（WeKnora / 现有 addYuque 均已有处理，社区有 lake-md 转换实现可借鉴）
- **增量**：语雀 API 无变更事件 → cursor 存全量文档 `updated_at` 映射，增量 = 按 mtime 过滤
- **现状收编**：现有 v1 `addYuque`（手动贴 URL）保留；连接器版提供资源树+定时

### 7.2 飞书知识库 `feishu_wiki`（P0 旗舰，WeKnora 最成熟可参考）

- **认证**：`app_id` + `app_secret`（企业自建应用）。凭据换取 tenant_access_token（缓存至过期前 5min）
- **权限**：`wiki:wiki:readonly` + `docx:document:readonly` + `drive:export:readonly` + `sheets:spreadsheet:readonly`
- **资源模型**：两级懒加载树：Wiki 空间 (`GET /wiki/v2/spaces`) → 节点树 (`GET /wiki/v2/spaces/:id/nodes`；`parent_node_token` 逐层 + `ResolveResourceAncestors` 由 `obj_token` 反查路径)
- **内容获取分型**（WeKnora 同款策略）：
  - `docx`（新版文档）：`GET /docx/v1/documents/:id/raw_content` 或 blocks 遍历 → Markdown（保留标题层级/表格/任务列表）
  - `sheet`：导出接口 → CSV→Markdown 表格
  - `bitable`：`GET /bitable/v1/apps/:id/tables` → 每表转 Markdown 表
  - `file`/ Older doc：走 `drive:export` 异步导出任务（轮询 ticket）
- **限流**：飞书 QPS 按应用频控（~50/5s），全局 `asyncio.Semaphore(5)` + 429 退避 + `X-Ogw-Status` 处理
- **增量**：`fetch_incremental` 遍历节点树比对节点 `obj_edit_time`，cursor = {node_token: edit_time}快照

### 7.3 飞书云盘 `feishu_drive`（与 7.2 共用 core`

- **资源模型**：指定文件夹 `folder_token` 树（`GET /drive/v1/files?folder_token=`）
- **内容**：全部走 drive export（doc/sheet/mindnote/bitable）；文件类型不入正文的按 `FetchedItem.metadata` 记录链接
- **增量**：folder 列表返回的 `modified_time` 比对

### 7.4 钉钉文档 `dingtalk`

- **认证**：企业内部应用 `app_key` + `app_secret`（需开通 `Documents.Readonly` + 企业授权）
- **资源模型**：UnionId 维度文档树（`GET /v1.0/doc/nodes`）
- **内容**：WeKnora 的做法——调文档内容接口 → **blocks → Markdown**（专门写了 `markdown.go`：文字/标题/表格/图片(临时链接下载)）。Python 侧按 block type 逐一映射，图片经临时 URL 下载后存文件存储并替换为本地链接
- **增量**：节点 `modified_time`

### 7.5 Notion `notion`

- **认证**：`integration_token`（Internal Integration）或 OAuth（P2）
- **资源模型**：搜索接口 `POST /search` 一次返回全树（`fix_obj` 侧已全量）→ 一次性树，无需懒加载
- **内容**：`GET /blocks/:id/children` 分页 → block→Markdown（notion 官方类型映射；子页面递归；`child_database` 转表格视图）
- **限流**：~3 rps，`Semaphore(2)` + 指数退避
- **增量**：页面 `last_edited_time`；cursor 存 `{page_id: edited_time}`

### 7.6 Confluence `confluence`

- **认证**：`base_url` + `email` + `api_token`（Cloud）/ PAT（DC，P2）
- **资源模型**：空间列表（`/rest/api/space`）→ 空间下页面树（`/rest/api/content/search?cql=space=x and type=page`）
- **内容**：页面 `body.storage`（XHTML）→ Markdown（`xhtml2md` 轻量转换，图片走附件 `/download/attachments` 下载到本地）
- **增量**：CQL `lastmodified > cursor_ts`，cursor = 时间戳

### 7.7 腾讯 IMA `tencent_ima`

- **认证/协议**：WeKnora `ima/client.go` 为私有实现（凭据 + 内容接口），P2 阶段**直接移植其请求模型**（含 fake_ima 测试桩模式搬过来）
- **风险**：接口非公开稳定协议，做在 `dbgpt-ext` 里并允许 fail-fast

### 7.8 腾讯文档 `tencent_docs`（WeKnora 没有，自设计）

- **认证**：docs.qq.com 开放平台应用 `client_id` + `client_secret`（OAuth）+ 用户授权 access_token
- **资源模型**：`/openapi/drive/file_list` 拉文件夹树（懒加载，同飞书）
- **内容**：`/openapi/v3/export` 异步导出 → doc/sheet/bitable → Markdown / CSV→表格；⚠️ 开放平台能力以实际联调为准，设计为**可配置导出格式 + fail-fast**，首次实现时先做 doc（文字文档），sheet/bitable P2
- **增量**：`file` 元数据 `modified_time`

### 覆盖矩阵

| 源 | 树形/平铺 | 原生增量 | 内容转换难度 | 认证字段 | 期 |
|---|---|---|---|---|---|
| 语雀 | 平铺 | mtime 扫描 | 中（lake→md） | token | **P0** |
| 飞书知识库 | 懒加载树 | edit_time | 中高（docx/sheet/bitable/export） | app_id+secret | **P0** |
| 飞书云盘 | 懒加载树 | modified_time | 中（全 export） | app_id+secret | P1 |
| 钉钉文档 | 树 | modified_time | 中（blocks→md） | app_key+secret | P1 |
| Notion | 全量树 | last_edited_time | 中（blocks→md） | token | P1 |
| Confluence | 空间树 | CQL 时间戳 | 中（xhtml→md） | url+email+token | P1 |
| 腾讯 IMA | ? | ? | ? | 私有 | P2 |
| 腾讯文档 | 懒加载树 | modified_time | 中（export） | client_id+secret+OAuth | P2 |
| RSS（示例） | 平铺 | etag/last-modified | 低 | url | P0 作为契约样例 |

## 8. API 端点（挂 `/api/v2/serve/knowledge`）

| Method | Path | 说明 |
|---|---|---|
| GET | `/datasources/types` | 连接器元数据（registry，含 auth_fields schema → 前端动态表单） |
| POST | `/datasources/validate` | 凭据验证（不落库） |
| GET/POST | `/spaces/{space_id}/datasources` | 绑定列表 / 创建绑定（加密落库） |
| PUT/DELETE | `/spaces/{space_id}/datasources/{id}` | 更新（改凭据/资源/调度）/ 解绑（可选清理文档） |
| GET | `/spaces/{space_id}/datasources/{id}/resources` | 资源树懒加载（`&parent_id=`） |
| GET | `/spaces/{space_id}/datasources/{id}/resolve-ancestors?ids=` | 已选资源回显路径 |
| POST | `/spaces/{space_id}/datasources/{id}/sync` | 手动同步（入队，复用 task 记账） |
| POST | `/spaces/{space_id}/datasources/{id}/pause` \| `/resume` | 停/恢复调度 |
| GET | `/spaces/{space_id}/datasources/{id}/logs` | 同步日志 |

## 9. 前端

- KB 详情页新 Tab「数据源」：绑定卡片列表（类型图标/上次同步/状态徽标/手动同步按钮/日志抽屉）
- 绑定向导（参考 WeKnora）：① 选连接器（meta 渲染图标网格）② 动态凭据表单（auth_fields → antd Form 自动生成，secret 字段 Password）→「验证连接」③ 资源树勾选（antd Tree，懒加载 loadTreeNode）④ 调度与策略（interval/cron、增量/全量、冲突策略、删除同步开关）
- 空间 ID 透传给 wiki：同步完成 → toast「已同步 N 篇，Wiki 将自动更新」

## 10. 分期

| 阶段 | 内容 | 估量 |
|---|---|---|
| **P0 骨架** | 连接器契约 + registry（entry_points + 模块扫描）+ 2 表 + service + 同步执行器（流式/游标/checkpoint）+ 文档入库适配 + API + 语雀连接器（收编现有逻辑）+ RSS 示例连接器（作为社区样例）+ 前端 Tab/向导 | 2 周 |
| **P1** | 飞书知识库 + 飞书云盘（共用 core token 管理）+ 钉钉 + Notion + Confluence；cron 调度（croniter）；图片/附件落文件存储 | 3 周 |
| **P2** | 腾讯 IMA（移植 WeKnora 私有协议）+ 腾讯文档（OpenAPI 联调）+ OAuth 型 Notion/飞书 + 权限审计 | 按需 |

## 11. 风险与决策点

1. **凭据加密主密钥**：复用 DB-GPT `SECRET_KEY` 或独立 `DATASOURCE_ENCRYPT_KEY`（必填才启用框架），密钥丢失即凭据不可解——文档声明
2. **图片/附件存储**：默认下载入本地文件存储并替换链接（飞书/钉钉/Confluence 临时 URL 会过期）；大文件走引用不下载
3. **冲突**：overwrite 策略下 `update content` + resync 会产生版本+1 的旧文档记录与 chunk 重建成本——增量比对做在 hash 层（无变化不同步）
4. **腾讯文档开放平台**能力以联调为准，先 text doc、后 sheet/bitable；如 OAuth 门槛太高，降级为「粘贴分享链接 + 导出服务」的受限模式（需用户确认取舍）
5. **与 GitRepo domain 的关系**：GitRepo 保留现状（domain_type 级管线）；datasource 框架面向 SaaS 文档平台，二者互斥共存；GitHub 代码库场景指向 GitRepo

---

## 12. 与 index/domain 层的关系（决策记录）

问题：DB-GPT 已有 `DomainKnowledgeIndex`（`domain/base.py`，extract→transform→load→clean，
`DomainKnowledgeIndexFactory` 经 `__subclasses__` 自动发现），GitRepo 即借由该层承载。
连接器是否也应做成 index 层扩展（`FeishuIndex(DomainKnowledgeIndex)`）？

**结论：不。连接器不做成 domain index，但吸收 index 层两个设计。**

| 维度 | domain/index 层 | connector 层（本方案） |
|---|---|---|
| 回答的问题 | 怎么加工（每空间一条处理管线） | 从哪来/何时来/增量从哪续（多源绑定） |
| 绑定粒度 | domain_type 空间单值 | 一个空间可绑 N 个源 |
| 状态 | 无外部源状态 | 游标/凭据/冲突策略 → 独立绑定表 |
| 各平台差异点 | 加工管线（实际都是通用切片，无差异化价值） | 认证/资源树/游标（真正的差异所在） |

否定理由：① domain_type 空间单值无法表达多源；② SaaS 文档拉下即普通 Markdown，
加工端八个"空壳 index"没有价值；③ source 状态（游标等）放 space.context 会重演
`embedding` KeyError 类问题。

吸收项：① **子类自动发现**——registry 的 entry-points+装饰器是 `__subclasses__`
扫描的等价升级，支持跨包插件 ✓；② **sink 扩展点**——连接器协议可选声明
`preferred_domain_type`（默认 `Normal`），未来代码类内容源可接代码切片管线；
GitRepo 维持现状（内部域），P2 可选把 GitHub 仓库场景包成 connector 供演示统一。
