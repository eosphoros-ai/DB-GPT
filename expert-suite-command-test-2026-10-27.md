# 专家套件快捷命令实测记录

日期：2026-10-27。页面：`http://localhost:3000/`；真实后端：`http://127.0.0.1:5670`。数据库：`Walmart_Sales`（SQLite）。完成请求使用 `deepseek-v4-flash`；另测 `deepseek-r1:1.5b`，本机 Ollama 连接失败后运行时出现模型回退，部分请求超时。

## 已修复的命令链路

之前的绿色前缀引用的是推荐问题标题；详情页的快捷命令卡片没有点击动作，后端没有解析命令的 `skill` 映射。

现在首页显示真实快捷命令入口。点击 `/nl2sql` 等命令后，输入框显示绿色锤子与 `智能取数 · /nl2sql`。修改问题及数据库时保留已选命令；点击声明了命令的示例会自动绑定其命令。详情页快捷命令可直接跳转首页并选中。手动输入已注册的 `/命令 参数` 也会被识别。

取数套件的 5 个推荐示例现在均已声明命令：4 个查询示例使用 `/nl2sql`，订单明细导出示例使用 `/export`。卡片显示对应指令，点击即可覆盖此前选择并自动带入，用户无需再选一次命令。数据库确认流程保留。

实际页面发送的请求（捕获真实请求，无 API mock）：

```json
{
  "model_name": "deepseek-v4-flash",
  "user_input": "[Database: Walmart_Sales] 统计 walmart_sales 表一共有多少条记录。只返回总数。",
  "ext_info": {
    "locale": "zh",
    "database_name": "Walmart_Sales",
    "database_type": "sqlite",
    "suite": "db-query",
    "suite_command": "/nl2sql"
  }
}
```

后端读取已安装套件的 `commands`，按照该命令的 `skill` 找到套件内声明的技能路径，读取 `SKILL.md` 正文，与套件 SOP 一起注入本轮提示词。路径必须在套件目录内。未知命令、缺失技能、空文件、越界路径会产生明确错误并阻止业务工具执行。

后端返回 `suite.bound`，包含真实命令、技能名、是否加载及正文 SHA-256。页面收到回执后显示“指令 /nl2sql · 知识技能 nl2sql-precision 已加载”。这条回执证明加载，不证明业务工具执行完成；查询结果必须另查工具返回。

## 真实执行结果

| 命令 | 实际加载的知识技能 | 工具证据 | 结论 |
|---|---|---|---|
| `/nl2sql` | `nl2sql-precision` | 页面自然语言请求生成 `SELECT COUNT(*) AS total_records FROM walmart_sales`；真实 `sql_query` 结果为 `6435`。独立 REST 请求同样返回 `6435`，并收到 `final`、`done` | 查询链路通过 |
| `/schema` | `semantic-linking` | 执行 `pragma_table_info('walmart_sales')`，返回 8 个字段；`pragma_index_list` 返回空 | 部分通过：返回表结构，但还额外查询了业务行数、门店数等统计，超出本次“只查元数据”的要求 |
| `/metric` | `semantic-linking` | 命令技能已加载；语义检索/权威口径接口未能使用，转而查询 `sqlite_master`；收到 `final`、`done` | 未取得权威指标定义。不能将这次结构探查当作“指标未发布”的权威证明 |
| `/export` | `result-export` | `sql_query` 取回前 5 行；后续 `code`、`bash`、技能脚本、动态工具加载等通道被套件规则拦截；收到 `final`、`done`，最终明确未生成文件 | 导出失败；CSV 文本预览不能算真实文件交付 |

`/schema` 工具回传的字段为 `Store`、`Date`、`Weekly_Sales`、`Holiday_Flag`、`Temperature`、`Fuel_Price`、`CPI`、`Unemployment`。字段来自真实查询，并非仅引用模型最终答案。

需要纠正模型最终答案中的两项说法：

- `/export` 的最终答案称 `export_csv` 不在套件白名单，但清单实际上包含 `export_csv`。实测阻断发生在运行时导出工具接入与替代写文件通道，不能据此建议开放整个 shell/code 权限。
- `/schema` 最终答案声称没有扫描业务数据，但工具轨迹包含对 `walmart_sales` 的聚合查询，所以本记录仅计为部分通过。

当前 `suite.bound.semantic_status` 返回 `bound`，源码探测仅判断语义模块能否导入，不能证明本次数据库绑定了已发布的指标口径。实测仍存在语义工具缺失及 `knowledge_retrieve` 被套件白名单拦截的问题。

## 命令如何与知识技能结合

这里的“知识技能”是套件目录中的 `SKILL.md`：它描述流程、口径要求、工具使用和降级方式。实际业务执行依靠工具，不是把命令字符串或技能名称显示出来就算完成。

| 智能取数命令 | `commands[].skill` | 作用 |
|---|---|---|
| `/nl2sql` | `nl2sql-precision` | 自然语言到 SQL 的生成、校验与纠错流程 |
| `/schema` | `semantic-linking` | 表结构、语义标注和白名单信息 |
| `/metric` | `semantic-linking` | 权威指标定义、版本与默认过滤 |
| `/export` | `result-export` | 结果集导出、类型保真与交付检查 |

本轮组合为：用户问题 + 数据库/知识库等资源上下文 + 套件 SOP + 命令指定技能正文 → 模型规划 → 工具调用 → 套件白名单/拒绝规则 → 原有审批检查 → 真实结果。

当前实现直接加载命令指定的主技能，不会因为套件列出 4 个技能就自动执行全部技能。套件 SOP 可以规定协作流程，支持技能及语义检索、指标回源、导出等工具还需要实际接入。另行选择的知识库会通过资源上下文参与检索，但与读取 `SKILL.md` 是两条独立链路；本轮主实测未选择知识库，未宣称知识库检索成功。

## 验证范围

- 6 项 Playwright 回归测试通过：原有数据库绑定与示例命令自动带入、命名数据库切换、缺库阻止发送、命令随问题编辑保留并进入请求、详情页快捷命令跳转、导出示例覆盖此前命令并发送 `/export`。此组使用 mock API，验证页面与请求契约。
- 13 项后端 unittest 通过，其中遍历三套官方套件的全部 15 个快捷命令，核对技能映射、真实文件正文与散列、工具边界、未知命令、技能路径、手动命令及命令不跨轮自动继承。
- 另做真实 Chrome + 真实后端 + 真实模型 + 真实数据库验证，截图保留自然语言生成的 SQL、6,435 结果及服务器技能加载回执。
- TypeScript 当前 175 项错误，虚拟 HEAD 基线同为 175 项，无新增诊断；全项目类型检查仍未通过。
- `git diff --check` 通过。未修改套件的工具白名单和审批规则。

截图：

- [快捷命令引用](expert-suite-command-reference.png)
- [真实查询结果与技能回执](expert-suite-command-result.png)

业务能力尚未全部通过，后续重点为语义工具实际接入、导出工具注册，以及 `/schema` 的执行范围约束。
