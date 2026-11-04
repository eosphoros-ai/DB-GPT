# DB-GPT 知识库 LLM-Wiki 能力升级方案

> 对标 WeKnora「Wiki 模式」：Agent 从原始文档自治生成结构化、相互链接的 Markdown Wiki 页面与可视化知识图谱，支持人工编辑、版本历史、行级 diff 与一键回滚。
>
> 分支：`feat_llm_wiki`（当前为空白分支，零 wiki 代码，可直接开工）
> 设计稿：`docs/design/llm-wiki-mockups/`（HTML，OpenCode 视觉风格）

---

## 1. 背景与目标

DB-GPT 知识库当前形态是「文档 → 分块 → 向量/全文索引 → 检索问答」，产出物是**检索结果**。WeKnora 的 Wiki 模式在同样Input之上多产出一层**人可读、可编辑、可演进的知识的结构化表达**：

- 用户能像百科一样**浏览**知识库（目录树 + 页面 + 双向链接）
- 知识以**页面**为单位沉淀，页面间以 `[[slug|别名]]` 链接互联，形成网状结构
- 每个知识页面有**版本历史**，LLM 生成、Agent 修复、人工编辑三类来源可追溯、可回滚
- **图谱视图**呈现页面链接网络，支持概览/邻域两种探索方式
- 文档增量入库时 Wiki **增量演化**（不是全量重建），文档删除时自动回收引用

本次升级目标：将 WeKnora 的 LLM-Wiki 能力复用搬运到 DB-GPT，做到 **后端管线逻辑等价移植、前端交互设计对齐、与 DB-GPT 既有 serve/agent/chat 体系深度融合**。

---

## 2. 能力全景与 Gap 对照

| 能力 | WeKnora 现状 | DB-GPT 现状 | 差距 |
|---|---|---|---|
| Wiki 页面存储 | `wiki_pages`（层次化 slug/6 种类型/双链/chunk 引用） | 无 | **新建** |
| 版本历史/回滚 | `wiki_page_revisions` 快照 + 乐观锁 + 两级保留策略 | 无 | **新建** |
| 目录树 | `wiki_folders` 实体 + materialized path | 无 | **新建**（P0 用隐式 category_path，P1 实体化） |
| 生成管线 | Map(候选slug+摘要+引用) → 去重 → 目录规划 → Reduce(改写) → Finalize(索引页/死链/交叉链接) | 无 | **移植重写（Go→Python）** |
| 异步任务 | asynq + Redis + 独立 Worker 池 + 死信队列 | `asyncio.create_task` fire-and-forget，无记账 | **适配**：wiki_task 记账表 + asyncio worker + debounce |
| 检索增强 | wiki 页面入 chunk 库 + rerank 后 1.3x boost | `chat_knowledge` 场景直接用 chunk 检索 | **新建**（P0 简化版） |
| 健康度 | lint（死链/孤儿页）+ autofix + issues 体系 | 无 | **P1** |
| Fixer Agent | 会话式增量修复（10 个 wiki 工具） | 已有 ReAct Agent 框架 + 工具机制 | **P1**（复用 agent 框架，写 wiki 工具集） |
| 图谱 | 页面链接图（overview top-N / ego BFS / bloom 扩展），手写 SVG 力导向 | heading 层级图 + codegraph（另一个东西） | **新建**（wiki link graph，与 codegraph 并存不冲突） |
| 聊天集成 | wiki 工具结果卡片 + chat 内抽屉阅读 wiki | 无 | **P1** |
| 前端 | Vue3+TDesign（WikiBrowser 单体 6593 行） | Next.js13+antd5 | **重做 UI，移植纯逻辑** |
| 多租户/RBAC | 四级角色矩阵 | 空间级权限 | **裁剪**（DB-GPT 无多租户，只保留空间归属） |

---

## 3. 复用策略总表（怎么「搬」）

按可搬运程度分四类：

### 3.1 直接移植（纯逻辑/纯函数，改个名就能用）

| WeKnora 源 | 落点 | 说明 |
|---|---|---|
| `utils/wikiLineDiff.ts`（90 行 LCS 行 diff，含 1500 行退化保护） | `web/utils/wiki/line-diff.ts` | 零依赖，照抄+单测 |
| `utils/wikiRevisionDiff.ts`（字段级 diff 组装） | `web/utils/wiki/revision-diff.ts` | 照抄 |
| `wikiDirectoryState.ts`（目录展开/收起状态机） | `web/utils/wiki/directory-state.ts` | 照抄 |
| `wikiStatusRefresh.ts`（文档解析→wiki 刷新联动判定） | `web/utils/wiki/status-refresh.ts` | 照抄 |
| 修订快照算法：`UpdateWithRevision`（同事务先快照后更新，`ON CONFLICT DO NOTHING` 幂等 + 版本乐观锁） | `wiki_dao.py` | 用 SQLAlchemy upsert 等价实现 |
| 双链维护：`parseOutLinks` / `updateInLinks` / `removeInLinks` | `wiki_link_service.py` | `[[slug|alias]]` 正则解析，照搬 |
| 死链清理/交叉链接注入：`stripDeadWikiLinks` / `injectCrossLinks` | `wiki_link_service.py` | 算法照搬 |
| lint 规则（断链/孤儿页/摘要死链）+ autofix | `wiki_lint.py`（P1） | 非 LLM 检查，规则照搬 |
| 两级修订保留策略（50 可清理机写 / 200 硬上限） | `wiki_revision_service.py` | 参数照搬 |

### 3.2 翻译重写（Go → Python，逻辑等价）

| WeKnora 源 | DB-GPT 落点 | 关键点 |
|---|---|---|
| 生成管线状态机 `wiki_ingest_batch.go`（3246 行） | `wiki/pipeline/`（map_phase.py / dedup.py / taxonomy.py / reduce_phase.py / finalize.py） | Map-Reduce 结构不变；并发用 `asyncio.Semaphore` + `asyncio.gather` 替代 goroutine 池 |
| 8 个 prompt 模板（`internal/agent/prompts_wiki.go` 硬编码） | prompt serve 注册 / pipeline 内常量 | **文本搬运后调优**：candidate_slug、doc_summary、chunk_citation、dedup、taxonomy_plan、page_modify、index_intro(+update) |
| chunk 引用批处理 `wiki_ingest_cite.go`（12000 rune/批、并发 4） | `pipeline/citation.py` | 分批阈值照搬，rune→字符 |
| 去重预筛 `wiki_ingest_dedup.go`（pg_trgm Jaccard 0.08/top5） | `pipeline/dedup.py` | DB-GPT 存储 SQLite/MySQL 均可能，预筛改为 Python `difflib`/rapidfuzz 表面相似度，LLM 终审不变 |
| 30s/20s debounce 入队 | `wiki_task_scheduler.py` | asynq 延迟队列 → task 表时间戳轮询 |
| `FOR UPDATE SKIP LOCKED` 行声明 | P0 不需要（单 worker）；P2 队列化时用 MySQL 8 同语法 | — |

### 3.3 架构替换（平台差异适配）

| 差异点 | WeKnora | DB-GPT 方案 |
|---|---|---|
| 任务队列 | asynq/Redis/死信/SKIP LOCKED | `knowledge_wiki_task` 表 + in-process asyncio worker loop（启动时恢复 pending）+ debounce 窗口判定；万级文档再考虑接入外部队列（P2，接口预留） |
| 触发挂点 | 文档 post-process 事务内 seed pending op | `Service._sync_knowledge_document` 的 `async_doc_process` 成功回调尾部 enqueue；文档删除挂 `delete_document` 尾部 reconcile |
| 多租户 RBAC | tenant + 四级角色 | 裁剪：只保留 space 归属；API 复用现有 serve 鉴权 |
| slug 路由 | gin `*slug` catch-all + `PUT /move-page` 绕开 | FastAPI `:path` 参数原生支持 `pages/{slug_path:path}`，无 move 端口岸 adjustment |
| 前端组件库 | TDesign + Vue3 | antd 5 + Next.js：三栏布局用 antd Layout/Tree 自绘叶子，diff 渲染用 `<pre>` + 行染色（同 WeKnora 方案） |
| Markdown 渲染 | marked + highlight.js | 复用 DB-GPT chat 现有 markdown 渲染组件，增加 `[[slug]]` 链接预处理（正则替换成 `<a data-slug>`，照搬 `renderMarkdown`） |

### 3.4 融入 DB-GPT 既有设施（不重造轮子）

| 设施 | 用法 |
|---|---|
| **Serve 模块模式** | 不新建 serve module，wiki 作为 `dbgpt_serve/rag` 的子域：`rag/api/wiki_endpoints.py` + `rag/service/wiki/` + `rag/models/wiki_db.py`，挂到现有 RagServe router（前缀 `/api/v2/serve/knowledge`） |
| **prompt serve** | 8 个管线 prompt 注册为命名模板，支持空间级覆盖（对齐 wiki_config 的自定义指令能力） |
| **Agent 框架（ReAct 原生工具调用已打通）** | P1 Fixer Agent = 内置 agent + wiki 工具集（wiki_search/read_page/write_page/replace_text/link_mutation/flag_issue），编辑来源标记 `agent` |
| **chat_knowledge 场景** | P0：wiki 页面同步生成 `chunk_type=wiki` 的检索单元 + retriever 内加权；P1：wiki-qa / hybrid 两种预设 prompt |
| **index_methods** | 复用 `knowledge_space.index_methods` JSON：`"Wiki"` 作为新索引方法，KB 详情页据此显示 Wiki/图谱 tab |

---

## 4. 数据模型设计

### 4.1 `knowledge_wiki_page`

| 字段 | 类型 | 说明 |
|---|---|---|
| id | BigInteger PK | |
| space_id | BigInteger, idx | → knowledge_space.id |
| slug | String(255), uk(space_id, slug) | 层次化，如 `entity/acme`、`summary/<uuid>`、`concept/年假` |
| title | String(255) | |
| page_type | String(32) | `summary / entity / concept / index / synthesis / comparison` |
| status | String(32) | `draft / published / archived` |
| content | Text | 完整 Markdown，含 `[[slug|alias]]` |
| summary | Text | 一行摘要（列表/索引用） |
| aliases | JSON | |
| parent_slug | String(255) | 冗余便于直接查子页 |
| category_path | JSON | 隐式目录路径 `["人力资源","休假"]`（P0 的树来源） |
| depth / sort_order | Int | |
| source_refs | JSON | `[{"document_id":..,"doc_name":..}]` 文档溯源；删除文档时反查回收 |
| chunk_refs | JSON | 生成时的证据 chunk id 列表（可跳转原文） |
| in_links / out_links | JSON | 双向链接缓存 |
| version | Int | 乐观锁 |
| last_edit_source | String(16) | `pipeline / agent / user / revert` |
| gmt_created / gmt_modified | DateTime | |

### 4.2 `knowledge_wiki_page_revision`

被替换的历史版本快照（当前版本不落行）：`page_id, space_id, version(uk with page_id), title, content, summary, aliases, edit_source, editor, gmt_created`。保留策略：机写（pipeline/agent）最多 50 条可清理，硬上限 200。

### 4.3 `knowledge_wiki_task`（替代 asynq 的记账表）

`space_id, task_type(ingest/finalize/reconcile), status(pending/running/done/failed/dead), payload(JSON), run_after(DateTime, debounce 判定点), retry_count, last_error`。
Worker：启动时恢复 pending；运行期每 5s 轮询 `run_after <= now` 的 pending；finalize 任务具有 KB 级互斥（拿不到任务锁就渗回 pending 延迟 20s）。

### 4.4 空间配置

`knowledge_space.index_methods` 追加 `"Wiki"`；`knowledge_space.context` 追加：

```json
"wiki_config": {
  "synthesis_model": "模型名(缺省用空间默认/summary 模型)",
  "granularity": "focused | standard | exhaustive",
  "max_pages_per_ingest": 8,
  "content_instructions": "内容侧重自定义指令",
  "extraction_instructions": "抽取侧重自定义指令"
}
```

> WeKnora 的 `wiki_config` 是独立列，DB-GPT 放进 context JSON 是为了不动 space 表结构、复用现有 context 透传链路。

---

## 5. 生成管线设计（核心）

```
文档 sync 成功
   │  (enqueue, run_after = now+30s 防抖，文档级去重)
   ▼
[knowledge_wiki_task: ingest]
   │  Processor: 收集 space 内全部 pending 文档 → 一次执行
   ▼
┌─ MAP（文档级并发, Semaphore=4）────────────────────────────┐
│ Pass0 候选 slug 抽取(带既有 slug 连续性) ──┐              │
│ Summary  每文档一张摘要页 summary/<uuid>   ├─ 并行          │
│ Citation 候选 slug × chunk 分批(12k字符/批) 映射证据引用 ──┘  │
└──────────────────────────────────────────────────────────────┘
   ▼
[DEDUP] 表面相似预筛(rapidafuzz Jaccard≥0.08 top5) → LLM 终审合并
[TAXONOMY] LLM 单轮目录规划(≤2 层，复用既有目录)
   ▼
┌─ REDUCE（slug 级）──────────────────────────────────────────┐
│ 合并本批全部更新 → 既有页: LLM 按"编译器不是写手"增量改写    │
│   (引用 chunk 证据、valid_links 白名单、SUMMARY 首行约束)     │
│ 新页: 直接落库；文档撤稿: <deleted_documents> 传入改写        │
│ 每次写走 快照→版本+1 的 DAO 原子路径                          │
└──────────────────────────────────────────────────────────────┘
   ▼
[enqueue finalize, run_after = now+20s 防抖]
[FINALIZE](KB 全局收敛, 互斥) 索引页(index)重建/增量改写 → 死链清理
   → 交叉链接注入(相似页互链) → 空目录回收 → wiki chunk 同步检索库
```

**与 WeKnora 的等价性说明**：五段结构、提示词契约（输出 `SUMMARY:` 首行、`[[slug|alias]]` 链接语法、valid_wiki_links 白名单）、map 三个 pass 的并发拓扑、reduce 的 slug 合并语义全部保持；差异只在并发原语（goroutine 池 → asyncio）与任务层（asynq → task 表）。LLM 调用统一走三层重试（3 次 + 指数退避），单页输出上限 32k tokens。

**防抖语义**：同一文档重复入库只保留一个 pending ingest（收录在 payload 的 document 集里不断合并）；finalize 复用 operate KB 级互斥标记，跑完才允许下一轮。

---

## 6. API 设计

前缀：`/api/v2/serve/knowledge/spaces/{space_id}/wiki`

| P0 | Method | Path | 说明 |
|---|---|---|---|
| ✔ | GET | `/status` | `{pending_tasks, is_active, pending_issues, stats}` — 前端 5s 轮询的单一来源 |
| ✔ | GET | `/pages` | 分页列表，`page_type/status/query/category_path` 过滤 |
| ✔ | POST | `/pages` | 手工建页 |
| ✔ | GET | `/pages/{slug_path:path}` | 页详情 |
| ✔ | PUT | `/pages/{slug_path:path}` | 更新（body.version 乐观锁，冲突 409 返回 current_version） |
| ✔ | DELETE | `/pages/{slug_path:path}` | 软删（unlink 回收） |
| ✔ | GET | `/tree` | 目录树（folder 分组 + 计数 + 页面懒加载指针），P0 从 category_path 聚合 |
| ✔ | GET | `/revisions/{slug_path:path}` | 版本列表（newest-first，不含正文；`?version=N` 取全文） |
| ✔ | POST | `/revert` | `{slug, version}` → 以 `edit_source=revert` 落为新编辑 |
| ✔ | GET | `/index` | 索引页（intro + 分类型分组，游标分页） |
| ✔ | GET | `/graph` | `mode=overview`(top-N 连通度，limit 500/2000) / `mode=ego&center=slug&depth=1..3` |
| ✔ | GET | `/search` | `?q=` 全文检索（标题/别名/正文 LIKE，P1 换全文索引） |
| ✔ | POST | `/generate` | 手动触发存量重建（首次开启 Wiki 时一键从现有文档生成） |
| P1 | POST | `/rebuild-links` | 全库重算双链 |
| P1 | GET | `/lint` + POST | `/auto-fix` 健康检查与修复 |
| P1 | GET/PUT | `/issues` 问题列表与状态流转 | |

对应前端 client 层 `web/client/api/wiki/index.ts`（函数签名对齐 WeKnora `api/wiki/index.ts`，便于移植调用侧代码）。

---

## 7. 前端设计

### 7.1 信息架构（对齐 WeKnora，Tab 结构）

```
知识库详情页 (pages/construct/knowledge/detail.tsx)
├─ 文档 (现状不动)
├─ ★ Wiki  → <WikiBrowser view="browser">
│    ├─ 左栏：状态条 | 搜索 | 类型Tab(摘要/知识) | 目录树(懒加载/树/列表切换)
│    ├─ 右栏：阅读器（[[链接]]渲染、被链接/来源文档、徽标: 版本/类型/编辑来源）
│    │        ├ 内联编辑（标题/摘要/正文，409 冲突提示）
│    │        └ 索引页（分段懒加载 Markdown 目录）
│    ├─ 抽屉：版本历史(diff/回滚) | 修复会话(P1) | 全局问题(P1)
│    └─ 覆盖层：新建页 Dialog
├─ ★ 图谱 → <WikiBrowser view="graph">
│    └─ 力导向 SVG 画布 + 图例过滤 + 搜索定位 + 右侧页预览抽屉 + ego 展开/bloom
└─ KB 列表页：Wiki 徽标 <KbWikiBadge>
```

组件目录：`web/components/knowledge/wiki/`（wiki-browser / wiki-sidebar / wiki-tree / wiki-reader / wiki-markdown / wiki-graph / wiki-revision-drawer / wiki-generate-modal / wiki-status-pill）。**吸取 WeKnora 单体 6593 行的教训，按上述拆分，graph 渲染器独立成 `wiki-graph-renderer.ts`（纯 DOM/SVG 模块，React 只做生命周期挂载）**。

### 7.2 从 WeKnora 移植的前端资产

| 资产 | 适配成本 |
|---|---|
| 行级 LCS diff + 字段 diff 组装（utils 4 个纯 TS 文件） | 零，直接抄 |
| 版本抽屉交互范式（增量/累计/原文三视图、请求序号防竞态） | 低，TDesign→antd |
| 三层轮询模型（stats 5s 父子两级 + 文档解析联动） | 低 |
| `[[slug]]` 链接渲染与跳栈导航 | 低 |
| 力导向模拟参数（alpha 0.985 衰减、斥力/弹簧/向心权重） | 低，纯参数照搬 |

### 7.3 视觉

本分支已引入 OpenCode 设计语言（`styles/opencode-theme.css`：smoke 暖灰中性面板 + cobalt 蓝主色 `#034cff/#0069fe`）。Wiki 模式按该语言出深色设计稿（`docs/design/llm-wiki-mockups/`，含 index 导航页 + 浏览器/图谱/版本历史/生成配置 4 屏），页面类型色板在 cobalt 基础上扩展：summary 蓝 / entity 绿 / concept 橙 / synthesis 紫 / comparison 红 / index 灰。

---

## 8. 检索与聊天集成

**P0（生成完成后立即生效）：**
- wiki 页面同步进检索库：每页生成一条 `chunk_type='wiki'` 的检索单元（正文前 1.5k 字符 + 标题/别名），随页面修订同步重建
- `chat_knowledge` 检索路径对该类 chunk 做 1.3x 加权（对齐 WeKnora `PluginWikiBoost` 语义，作用于 rerank 之后）

**P1：**
- 内置 `wiki-fixer` Agent：DB-GPT Agent 框架上挂 wiki 工具集（search/read_page/read_source_doc/write_page/replace_text/flag_issue），会话内编辑落 `edit_source=agent`
- 聊天流渲染 wiki 工具卡（创建/更新/替换 diff/重命名/删除 5 种卡片）+ 聊天内 wiki 阅读抽屉（点击 `[[链接]]` 继续浏览）
- `wiki-qa` 预设（图遍历式 prompt）+ hybrid RAG+Wiki 双源 prompt

---

## 9. 分期实施计划

### P0 — MVP（后端 2 周 + 前端 2 周，可并行）

| # | 工作 | 估时 |
|---|---|---|
| 1 | 数据模型 3 表 + DAO + 修订原子写 | 3d |
| 2 | task 表 + asyncio worker + debounce | 2d |
| 3 | 五段管线移植 + 8 个 prompt 调通 | 8d |
| 4 | P0 API 13 个端点 | 3d |
| 5 | wiki chunk 同步 + 检索加权 | 2d |
| 6 | 前端 client 层 + 浏览器三栏(树/阅读/索引) | 5d |
| 7 | 图谱 overview +ego + 页预览抽屉 | 3d |
| 8 | 状态轮询/进度/生成配置弹窗/首次一键生成 | 2d |
| 9 | 联调 + 生成质量调优 | 3d |

### P1 — 体验与质量闭环（约 1.5 周）

版本 diff + 手动编辑 + 409 冲突（3d）→ lint/autofix（2d）→ Fixer Agent + 工具集（5d）→ 聊天工具卡 + 抽屉（3d）→ 文件夹实体化(重命名/移动)（2d）→ i18n（1d）

### P2 — 规模与生态（按需）

任务队列治理（外接队列/死信/限流）、文档撤稿 reconcile 完整化、issues 体系完善、MCP 只读工具（wiki_search/read_page/index）、性能治理（万级页面：树虚拟滚动、graph 截断策略、全文索引）

### 风险与决策点

1. **生成质量是最大不确定项**：8 个 prompt 移植后需用真实语料调优（建议先拿本仓库文档当测试集）。设置验收样例 3 组（产品文档/财报/制度类）。
2. **无 Redis 的防抖可靠性**：task 表方案在单实例部署下可靠；多 worker 部署需要 DB 行锁或改接外部队列——P0 按单实例交付并在部署文档声明。
3. **SQLite 兼容**：`ON CONFLICT DO NOTHING`、JSON 字段在 SQLite 均可用，但全文检索 P0 用 LIKE 兜底。
4. **图谱与 codegraph 的关系**：两者并存（wiki link graph 挂 space、codegraph 挂 domain/code 类型），前端入口分开，不合并。
5. **成本**：granularity=standard 时每 MB 文档约 6~10 次中等长度 LLM 调用；暴露 max_pages_per_ingest 让空间管理员自控。

---

## 10. 验收口径（P0）

1. 空间开启 Wiki + 一键生成 → 万字级文档 10 分钟内产出 ≥10 个互链页面 + 索引页 + 图谱可浏览
2. 增量上传 1 篇新文档 → 30s 防抖后仅受影响页面被更新（版本+1，其余页面版本不变）
3. 页面手动编辑触发 409 冲突可正确提示并恢复
4. 版本历史可见 pipeline/agent/user 三种来源，回滚产生 revert 记录且自身可再回滚
5. chat_knowledge 问答能命中 wiki 页面内容并引用
