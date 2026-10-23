# 语义中心（Semantic Center）改造方案

> v1.0 · 2026-10-22 · 配套：`data-agent-product-design.md` §7.5、语义层设计稿（六 tab）、`scenario-suite-impl-plan.md`（套件侧 semantic 块）
> 结论先行：语义中心 = **六层语义栈**（物理→含义→度量→关系→行为→政策），全部以结构化库为权威源、KB 托管空间为派生索引；**口径不是独立实体，而是指标的版本化载荷**；血缘 P0 只做 join 图。

---

## 一、概念定义：六层语义栈

| 层 | 实体 | 定义 | 来源 | 治理 |
|---|---|---|---|---|
| L1 物理事实 | 元数据中心（sem_table/sem_column） | 库"是什么"：schema/类型/约束/索引/分区/comment/行数/基数/采样值/视图与存储过程定义 | **连接即自动同步**，只读 | 仅同步与漂移检测，无人审 |
| L2 业务含义 | 语义标注（sem_entry） | 字段/表"什么意思"：枚举语义、描述补全、同义词 | LLM 草稿+置信度 / 人工 / 反馈 | 草稿→人审→发布 |
| L3 度量 | 指标（sem_metric）+ **口径（sem_metric_version）** | 指标=有 owner 的命名度量（身份）；**口径=该指标某版本的定义载荷**（expression+默认过滤+维度+时间粒度+单位+去重规则+同义词） | 视图/存储过程/历史 SQL 反提取草稿 + 业务确认 | 版本化发布；pin 可复现 |
| L4 关系 | 血缘/_join 图（sem_relation） | 表间可用 join 路径（带 join key）供 schema linking 与可解释性；列级血缘 P2 | FK 自动 + 历史 SQL/名称启发推断 + 人工校准 | 推断→人审 |
| L5 行为 | 样例库（sem_example） | Verified Q→SQL，few-shot 与自进化载体 | 点赞沉淀 / 人工导入 / 历史挖掘 | verified 才进检索 |
| L6 政策 | 规则护栏（sem_rule） | 只读/租户注入/软删除约定/白名单/超时行数/从库路由 | 管理员配置（C 类决策） | 直接生效，进 gate |

**关键建模决策**：
1. **口径=指标版本载荷**：不建独立"口径表"。`sem_metric` 是身份（name/owner/status/tags/access_tag），`sem_metric_version` 是口径（v1/v2…），发布即 current_version+1；套件 pin 与对话引用都指向 version，改口径=新版本，历史可复现。
2. **语义标注统一 entry 表**：column_desc/enum/synonym/table_desc 用一张 `sem_entry`（type 区分，content JSON），避免四张碎表；chunk 文本由 entry 渲染。
3. **血缘 P0=join 图**：NL2SQL 需要的是"可用 join 路径"，不是全列级血缘；列级血缘（视图/ETL 解析）放 P2 做可解释性增强。
4. **向量只是索引**：托管空间 chunk=一条语义项（metadata{id,type,target,v,ds}），命中后回结构化库加载权威定义；换 embedding 模型全量重建。

---

## 二、数据模型（meta 库新增表，DDL 骨架）

```sql
sem_datasource(id, conn_id UNIQUE, name, dialect, sync_status, last_sync_at,
               table_count, whitelist_count, embedding_model, created_at)
sem_table(id, ds_id FK, schema_name, table_name, comment, row_est, freq_score,
          is_whitelist BOOL, semantic_status, synced_at, UNIQUE(ds_id,schema_name,table_name))
sem_column(id, table_id FK, col_name, dtype, nullable, default_val, is_pk, is_fk,
           comment, cardinality, sample_values JSON, synced_at, UNIQUE(table_id,col_name))
sem_entry(id, ds_id, type, target, content JSON, provenance, confidence,
          status[draft|published|rejected|stale], version, owner, created_at, published_at)
sem_metric(id, ds_id, name, display, description, owner, tags JSON, access_tag,
           status[draft|published|deprecated], current_version, created_at, UNIQUE(ds_id,name))
sem_metric_version(id, metric_id FK, version, expression, dialect, tables JSON,
           dimensions JSON, default_filters JSON, time_grain JSON, dedup_rule,
           synonyms JSON, change_note, status, created_at, UNIQUE(metric_id,version))
sem_relation(id, ds_id, src_table, src_col, dst_table, dst_col, join_key,
             kind[fk|inferred|manual], confidence, status, usage_count)
sem_example(id, ds_id, question, sql, dialect, source[thumbs_up|import|history_mined|suite],
            src_conv_id, linked_metric_ids JSON, use_count, status[verified|pending], created_at)
sem_rule(id, ds_id, kind[readonly|tenant_filter|soft_delete|whitelist|limit|replica],
         params JSON, enabled, scope, created_at)
sem_publish_log(id, ds_id, entry_type, entry_id, action[publish|reject|rollback],
                from_version, to_version, operator, chunk_ids JSON, created_at)
sem_citation(id, conv_id, message_id, ds_id, cite_type[metric|table|example|rule],
             cite_id, cite_version, feedback[NULL|up|correct], created_at)
```

托管空间：KB 空间名 `semantic::<conn_id>`，只读；chunk metadata `{id,type,target,v,ds}`。

---

## 三、四条管道

### 3.1 同步管道（L1，连接即有）
connector introspection（复用 `dbgpt_ext/datasource` 的 schema/index 接口 + DBSummary 冷启动）→ upsert sem_table/sem_column → 统计（基数/min-max/采样，按权限与采样上限）→ 视图/存储过程定义入库（**代码态口径源**）→ freq_score（有查询历史用历史，无则 comment/行数启发）→ 白名单建议（freq top-N）进确认队列。
**漂移检测**：列删除/改名/类型变更 → 关联 sem_entry/sem_metric_version 标 `stale` 进复审队列；不静默失效。

### 3.2 草稿管道（L2/L3/L4 的 B 层）
- 标注器：按表批跑（采样值+comment+命名）→ sem_entry 草稿（enum/desc/synonym）+ 置信度；
- 指标矿工：解析视图/存储过程/高频历史 SQL → 指标候选（expression+默认过滤）→ sem_metric(draft)+version v1(draft)；
- join 推断：FK 直接入（kind=fk, 免审）+ 历史 SQL co-occurrence/命名启发 → kind=inferred 草稿；
- 低置信度（<0.8）强制人审；全部草稿**不进入检索**。

### 3.3 发布管道（治理口子）
confirm/modify/reject → status=published、metric current_version+1 → **chunk writer**：渲染检索文本（column=desc+enum+synonyms；metric=name+synonyms+expression+filters；example=Q→SQL）→ 按 metadata.id 删旧 chunk→插新→embed → sem_publish_log 审计。托管空间在 KB UI 只读；提供 rebuild 全量重建任务。

### 3.4 反馈管道（D 层）
引用 chip 👍 → sem_example(source=thumbs_up, linked_metric_ids, src_conv) + use_count++；✏️ → sem_entry 草稿（provenance=feedback，预填原内容）进复审；纠错涉及口径时同时给 sem_metric_version 开修订草稿。

---

## 四、消费侧：SemanticRetriever（AWEL 算子）

输入：question + ds_id + 套件 semantic 块（scope/pin/consumption）。
1. **双路召回**：托管空间向量 top-k（按 metadata.type 分桶控配额，避免样例挤占描述）+ 结构化精确匹配（metric name/synonyms、column synonyms）；
2. **按 id 加载权威定义**：metric 取 pin 版本或 latest published；entry 仅 published；rule 全量生效集；
3. **组装 prompt pack**：`{metrics[], default_filters[], joins[], rules[], examples[]}`，token 预算内按 consumption 模式配权（metric_first/schema_first/rule_first）；
4. **输出 citations[]**：供答案区引用 chip 与 sem_citation 落库。
接入点：`scene/chat_db` prompt 组装与 react_agent 上下文构建（替换/增强现有 `{table_info}` 注入）；语义层未就绪时 fail-soft 降级 DBSummary。

**规则执行点**（L6 不进 prompt 而进执行层）：soft_delete/tenant_filter 在 SQL 生成后校验注入（sql_guard）；readonly/limit/replica 在 tool_action gate 与 approval 路径执行——与套件 overrides 合并顺序：core deny > suite > sem_rule > core default。

---

## 五、与套件的接缝

manifest.semantic 解析：`layer`→sem_datasource；`scope`→retriever 过滤；`pin`→metric_version 选择；`proposals`→sem_metric(draft)+version(draft)，provenance=suite、水印"暂定"直至人审发布；`consumption`→召回配权。反查：指标卡显示"被引用套件/pin 情况"，改口径前做影响分析。

---

## 六、任务分解（文件级）

| # | 任务 | 落点 | 估行 |
|---|---|---|---|
| S1 | models + 建表/迁移 | `dbgpt-serve/src/dbgpt_serve/semantic/models.py` | ~350 |
| S2 | 同步管道 + 漂移检测 + 白名单建议 | `semantic/sync.py`（复用 connector introspection） | ~300 |
| S3 | 标注器 + 指标矿工 + join 推断 | `semantic/annotator.py`、`metric_miner.py` | ~400 |
| S4 | 发布 + chunk writer + rebuild + 托管空间只读 | `semantic/publisher.py` + `dbgpt_serve/rag` 空间helper | ~300 |
| S5 | SemanticRetriever 算子 + prompt pack + citations | `semantic/retriever.py` + AWEL operator + chat_db/react 接入 | ~350 |
| S6 | sql_guard 规则注入 + gate 挂钩 | `semantic/sql_guard.py` + tool_action/approval 挂点 | ~150 |
| S7 | REST API（六 tab + publish + sync + rebuild） | `semantic/api.py` | ~300 |
| S8 | 反馈闭环（citation/点赞/纠错） | `semantic/feedback.py` + chat API 扩展 | ~150 |
| S9 | 前端六 tab + 复审队列 + 覆盖率 + 引用 chip | `web/pages/construct/semantic/*`、chat 组件 | ~800 |

顺序 S1→S2→S4→S5→S6→S3→S7→S8→S9（S3 草稿管道可稍后，P0 可先人工录入指标）。

## 七、分期与验收

- **P0**：S1/S2/S4/S5/S6/S7/S9 基础 + 人工录入指标与规则；验收：连库分钟级出目录；发布指标后 chunk 可命中；问数 SQL 带默认过滤；答案带引用 chip；readonly 规则拦 DDL。
- **P1**：S3 全量 + 历史样例挖掘 + 输入待办队列 + 覆盖率水位 + 套件 proposals 入队 + rebuild 任务。
- **P2**：列级血缘（视图/ETL 解析）、Semantic-as-API/MCP、access_tag 行级联动、跨源指标组合。

---

## 八、存储分工决策：不是所有东西都进 DB 表

四类存储：

1. **meta 库新表（治理态+权威定义）**：P0 十表 `sem_datasource / sem_table / sem_column / sem_entry / sem_metric / sem_metric_version / sem_relation / sem_example / sem_rule / sem_publish_log`；`sem_entry.confidence` 为 S3 实施期补充列（已有 dev 库需 `ALTER TABLE sem_entry ADD COLUMN confidence FLOAT`，MySQL 用 DOUBLE）。
2. **复用 KB VectorStore**：托管空间 `semantic::<conn_id>` 的 chunk（派生索引，按 metadata.id 删旧插新）；`ManagedSpaceSink` 真向量接线（StorageManager+EmbeddingFactory）随阶段三 retriever 落地，阶段二 LoggingSink fail-soft。
3. **文件**：套件包（suite.yaml/skills/prompts）、toml bootstrap seed、P2 的 YAML 导入/导出 interchange。
4. **复用现有字段**：对话 `ext_info.suite` pin、message metadata 引用 chips（sem_citation 表 P0 不建，反馈直接回写 example/entry）。

被否替代：YAML 文件当真源（dbt 式）——web 多节点+审核工作流+漂移检测都不顺；实时 introspect 不存——无漂移基线、重复 introspect 贵、源库离线不可浏览。

## 九、实施状态与代码挂点（截至 2026-10-23）

| 任务 | 状态 | 落点 |
|---|---|---|
| S1 models+建表 | ✅ | `semantic/models.py`（10 表+Dao），注册进 `db_model_initialization._MODELS` 启动建表 |
| S2 同步 | ✅ | `semantic/sync.py`（sync/漂移/白名单/`semantic_auto_register`），挂 datasource `create()` 后台同步 |
| S3 草稿 | ✅ | `annotator.py`（LLM/启发式双模四档置信度）、`metric_miner.py`（SUM/COUNT 候选+LLM 提案）、`join_discovery.py`（FK→active 免审、命名启发→draft 待审）、`llm_bridge.py`（CFG.LLM_MODEL+WorkerManager，`asyncio.to_thread` 桥接） |
| S4 发布 | ✅ | `semantic/publisher.py`（四渲染器+sink 协议+审计日志）；向量真接线留阶段三 |
| S5 retriever | ❌ 阶段三 | `semantic/retriever.py` + AWEL 算子 + chat_db/react 注入 + 引用 chip |
| S6 sql_guard | ❌ 阶段三 | `semantic/sql_guard.py` + tool_action/approval 挂点 |
| S7 API | ✅ | `semantic/api.py`：spaces/activate/sync/backfill/drafts/coverage/tables/columns/entries+review/metrics+publish/examples/relations/rules+status，注册进 `dbgpt_server` |
| S8 反馈 | ⏸ 部分 | 引用 chip 依赖 S5；点赞回写通道已预留（source=thumbs_up） |
| S9 前端 | ✅ | `web/pages/construct/semantic.tsx`（空间列表+登记存量连接+六 tab+激活卡+生成草稿+置信度列）、侧栏导航、`client/api/semantic.ts` |

验收对照：清单 1-3 ✅；清单 4（发布后 chunk 可命中）待 ManagedSpaceSink 真接线后闭环；清单 5（readonly 拦 DDL）随 S6 sql_guard 落地。
