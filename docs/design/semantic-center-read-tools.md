# 语义中心只读工具

智能取数、智能分析的 ReAct 主流程、并行子 Agent 与 pi 工具桥注册以下工具。无需绑定普通
知识库，只需选择可访问的数据库；数据库连接加载失败时不挂载。
工具闭包绑定当前连接名称，不允许模型指定其他数据库或语义空间。

| 工具 | 用途 | 参数 |
| --- | --- | --- |
| `semantic_get_metadata` | 表/列元数据、类型、注释、PK/FK、枚举、敏感与白名单标记 | `table_name` 精确匹配、`query` 关键词、`limit` |
| `semantic_search_business` | 已发布表/字段业务定义、释义、同义词与目标映射 | `query`、`table_name`、`limit` |
| `semantic_search_metrics` | 搜索已发布指标，返回口径快照及 ID/版本 | `query`、`limit` |
| `semantic_get_metric` | 根据 ID 或名称读取完整已发布指标版本 | `metric_id` 或 `metric_name` 二选一、可选 `version` |

搜索是结构化关键词匹配，支持已维护别名，不依赖尚未接通的向量发布器。
建议从用户问题中提取业务名词，分别检索。`limit` 为 1–50，
返回 `matched_count` / `truncated`，可用表名和关键词缩小范围。
结果包含 `source`、`conn_id`、`ds_id`、空间状态及同步时间。

执行顺序：查指标候选 → 回源读取指标版本 → 查业务释义 → 核对表字段 →
依据真实定义生成 SQL → 引用指标 `citation`。多步分析使用回源返回的
整数版本再次读取，避免各步读取不同版本。

指标公式、业务定义、依赖指标和维度只读 `sem_metric_version` 的已发布快照。
不从可修改的 `sem_metric` 当前正文回退读取；精确版本缺失时也不换版本。
业务语义仅返回 `published` 状态且目标仍有效的表/字段标注。
指标不存在、属于其他库、尚未发布、版本不存在分别返回明确状态，不返回草稿正文。
元数据允许在未激活空间读取，但快照和标记仅供参考，不构成实时结构或执行权限保证。

`metric_definition` 保留完整内容，若存储为 JSON 则解析为对象；
`base_metrics`、`dimensions`、`synonyms`、`enum_values` 同样解析。
默认过滤、时间字段等信息只有在已保存定义中存在时才可使用，工具不生成这些字段。

当前边界：普通 `semantic_search` 仍是知识库检索。规则、血缘、样例读取、
执行前 SQL 口径校验、持久化会话 pin 和权限规则强制执行需后续独立接入。
本次没有新增公共 HTTP API，也不自动发布或激活用户草稿。

## English

The ReAct main flow and pi bridge mount four read-only tools for the selected
database: schema snapshots, published business meanings, published metric search,
and exact metric caliber retrieval. No ordinary knowledge base is required.
Search uses structured keywords and stored aliases. Metric payloads come only
from published version snapshots, with explicit missing/draft/version states.
Reuse the returned integer version and citation in multi-step analysis.
This adds semantic reads, not automatic SQL validation, persisted session pins,
or rule/lineage/example access.

## 验证记录（2026-10-27）

- 语义模块与工具专项：38 项通过（包含 15 项新增隔离、版本和工具测试）。
- 套件绑定独立回归：24 项与 19 个子测试通过。Ruff 与 `git diff --check` 通过。
- 本地真实读取：Olist 12 张表，Walmart 1 张表；业务语义与指标均无已发布命中。
  数据未被激活、发布或修改。
- 后端已重启，套件配置已同步；两个套件注册快照均包含四个新工具。
- 扩大回归的既有问题：语义 API 测试与套件绑定测试合并运行时，3 个旧测试
  因默认 asyncio 循环缺失而失败；不包含新增测试时同样复现。
  子 Agent 旧测试有 7 项失败，使用 Git HEAD 的原 dispatcher 源码执行时
  完全一致（工具资源类型及旧 fake reply/event 断言）。不将这些失败计为通过。
