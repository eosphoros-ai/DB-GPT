# DB-GPT 知识管线扩展点全景

> 配套阅读：`external-datasource-framework.md`（来源侧扩展的完整设计）、
> `llm-wiki-upgrade-plan.md`（Wiki 能力）。
> 本文回答一个问题：**社区/业务想在知识链路上扩展能力时，应该插在哪。**

## 1. 数据流与扩展点位置

```
外部平台 ──① Connector──▶ knowledge_document ──② sync_document ──▶ chunk
                                            （③ DomainKnowledgeIndex）  │
                          ──④ index_methods（向量/全文/图谱/Wiki）──▶ 索引层
                                     │                    ▲
                                     │            ⑤ post-sync 钩子
                                      ──▶ ⑥ 检索链 Retriever/Ranker ──▶ ⑦ 场景 Prompt ──▶ ⑧ Agent 工具/前端
```

## 2. 八个扩展点速览

| # | 扩展点 | 契约 | 发现方式 | 粒度（回答"扩展什么"） | 现状 |
|---|---|---|---|---|---|
| ① | `BaseDatasourceConnector` | validate / list_resources / fetch_all / fetch_incremental / fetch_resource | entry-points `dbgpt.datasource_connectors` + 装饰器 | 平台（从哪来） | 契约层已落地（dbgpt_ext/datasource） |
| ②③ | `DomainKnowledgeIndex` | `extract → transform → load → clean` + `domain_type()` | `DomainKnowledgeIndexFactory.__subclasses__` 扫描 | 加工管线（怎么变 chunk） | 已有（Normal/GitRepo），扩展需新增 domain_type |
| ④ | `index_method` 能力 | {name, validate_space, doc_synced_hook, frontend_meta} | **待建**：注册表 | 空间索引形态（Wiki/知识图谱…） | 现为 service.py 字符串分支，建议注册化 |
| ⑤ | post-sync 钩子 | `@register_sync_hook(order)`，入参 (space, doc) | **待建**：钩子注册表 | 同步完成后的自动化（wiki 入队、heading graph、未来摘要/打标） | 现为 `async_doc_process` 尾部两段硬编码 |
| ⑥ | 检索策略 | `BaseRetriever` / `RetrieverStrategy` / `_retriever_chain` 组合 + Ranker 插拔 | 构造参数注入 | chunk 之后的召回/排序 | 已有链式结构（语义/全文/树/hybrid） |
| ⑦ | Prompt | 命名模板 + 空间级覆盖 | prompt serve（`dbgpt_serve/prompt`） | 模型看到什么 | serve 已存在；wiki 8 模板 P1 收编进去 |
| ⑧ | Agent 工具 | `@tool` 装饰器 | import 即注册 | Agent 能做什么 | 已有（kb_semantic_search 等） |

## 3. 选择标准（一句话版）

| 你想改的是什么 | 插在哪 |
|---|---|
| 更多**平台**的内容进到 chunk | ① Connector |
| 某类内容**加工方式**不同（代码/SQL/多模态） | ③ Domain index |
| 同一份 chunk 之上**多一种索引/能力形态** | ④ index_method |
| 文档同步后**自动多做一件事** | ⑤ post-sync 钩子 |
| 召回/排序**策略**不同 | ⑥ Retriever/Ranker |
| 模型**看到的内容/指令**不同 | ⑦ Prompt |
| Agent **多一个动作能力** | ⑧ Tool |

## 4. 典型组合示例

- **接入飞书知识库 + 自动生成 Wiki**：① 写 `feishu_wiki` 连接器 → ⑤ 的 wiki 钩子已存在 → 0 行改动即出 Wiki 页面
- **代码仓库 notion 化文档混在一个空间**：① Notion 连接器（文档）+ GitRepo 域（代码）共处理
- **新检索增强**：⑥ 加重排 Ranker；wiki boost（1.3x）即此类钩子的最小形态（chunk_sync.apply_wiki_boost）
- **新索引形态（如「摘要索引」）**：④ 注册 method + ⑤ 注册钩子生成内容，前端多选框/Tab 自动出现

## 5. 待办（按收益排序）

1. **④ 注册化**：抽出 `IndexMethodRegistry`，`"Wiki"` / `"KnowledgeGraph"` 改注册实现；
   `space-form` 的方法多选框、detail 页 Tab、`async_doc_process` 分支全部由注册表驱动。
   与 connector `auth_fields → 动态表单` 同构。
2. **⑤ 钩子化**：`_maybe_build_heading_graph` + wiki enqueue 抽成有序钩子；失败互不影响
   （现状已各自 try/except，钩子化后保留该语义）。
3. ⑦ wiki 8 模板收编 prompt serve（P1 既定项）。

> 原则：**扩展点注册表驱动，不再在管线主流程里长 if/else。**
