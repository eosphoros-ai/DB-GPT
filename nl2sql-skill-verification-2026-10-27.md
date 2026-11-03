# /nl2sql 知识技能加载复测

日期：2026-10-27。真实接口：`http://127.0.0.1:5670/api/v1/chat/react-agent`。请求模型：`deepseek-v4-flash`。数据源：`Walmart_Sales`（SQLite）。本次未修改套件配置或业务代码。

## 结论

`/nl2sql` 会自动读取包内 `nl2sql-precision/SKILL.md`，并把完整正文与公共 SOP 一起加入模型上下文。它不是独立的固定 SQL 执行流水线：当前由 ReAct 模型参考提示词和数据库结构选择工具。本次实际生成 SQL 并调用 `sql_query`。

主技能中提到的 `semantic-linking`、`readonly-guardrails` 没有被命令绑定器自动加载。实际要求模型读取这两个技能时，技能读取工具被套件白名单拦截。主技能加载成功与依赖技能协作完成是两件不同的事。

## 源码链路与文件读取审计

1. `assets/suites/db-query/suite.yaml` 声明 `/nl2sql → nl2sql-precision`，并声明包内路径 `skills/nl2sql-precision/SKILL.md`。
2. `suite_binder.bind_command` 查找命令与技能索引，检查路径位于套件目录内，再调用 `Path.read_text` 读取正文。
3. `suite_binder.build_sop_block` 拼接公共 SOP、命令目标与主技能完整正文。
4. `agentic_data_api._react_agent_stream_impl` 把上述内容加入本轮系统提示词，发出 `suite.bound` 回执，再进入模型工具执行流程。

独立审计使用真实套件文件和绑定函数，只记录命令绑定阶段的文件读取：

```text
读取：assets/suites/db-query/skills/nl2sql-precision/SKILL.md
主技能完整正文包含于注入提示词：true
semantic-linking 完整正文包含于注入提示词：false
readonly-guardrails 完整正文包含于注入提示词：false
```

审计范围不包括服务启动或通用技能注册阶段；它证明的是该命令绑定器的直接加载行为。

## 真实请求一：普通 /nl2sql 取数

会话：`3945e728-fd39-4b8b-ab23-1e4281f23e13`。

问题：统计 `walmart_sales` 表总记录数，返回实际 SQL 和总数。请求使用 `ext_info.suite=db-query`、`ext_info.suite_command=/nl2sql`。请求耗时约 5.17 秒。

后端回执：

```json
{
  "type": "suite.bound",
  "suite": "db-query",
  "command": "/nl2sql",
  "command_skill": "nl2sql-precision",
  "skill_loaded": true,
  "skill_sha256": "50b5dd64c226933d2be456e078bf9bd67ebdfaf1ffe36c39878b1d29dcaecdb2",
  "command_error": null
}
```

回执 SHA-256 与磁盘技能正文（按绑定器逻辑去除首尾空白后）完全一致。

持久化历史中的真实工具结果：

```sql
SELECT COUNT(*) AS total_records FROM walmart_sales
```

```json
{
  "columns": ["total_records"],
  "rows": [[6435]],
  "row_count": 1,
  "truncated": false,
  "db_name": "Walmart_Sales"
}
```

历史只有一个业务步骤 `sql_query`，状态为 `done`。收到 `final` 和 `done`。本轮没有 `load_skill` 调用；主技能由后端提前读取。

## 真实请求二：主动要求读取关联技能

会话：`3e85b4be-628f-4a1f-9989-58010442132c`。

问题以 `/nl2sql` 开头，要求先读取 `semantic-linking`、`readonly-guardrails` 的完整 `SKILL.md`，再统计总记录数；请求未设置 `suite_command`，用于同时验证文本指令识别。请求耗时约 11.78 秒。

同样收到 `/nl2sql → nl2sql-precision` 的成功加载回执及一致的正文 SHA-256。

持久化执行记录：

| 步骤 | 实际调用 | 结果 |
|---|---|---|
| 1 | 分别为两个依赖调用 `load_skill` | 两次均失败，工具不在套件白名单内 |
| 2 | 分别为两个依赖调用 `get_skill_resource` | 两次均失败，工具不在套件白名单内 |
| 3 | `sql_query` 执行 `SELECT COUNT(*) AS total_rows FROM walmart_sales` | 成功，返回 6435 |

真实拦截观察：

```text
[suite guardrail] tool `load_skill` is not in suite db-query@1.0.0 allowlist (tools.allow). Only whitelisted tools may run in this scenario.
[suite guardrail] tool `get_skill_resource` is not in suite db-query@1.0.0 allowlist (tools.allow). Only whitelisted tools may run in this scenario.
```

这说明模型尝试读取依赖，但依赖正文并未通过这些调用加载成功。不能把“尝试调用”视为“已读取”。

## 验证边界

两次请求证明主技能读取、提示词拼接、基础 SQL 执行与依赖读取受阻。它们没有证明完整的权威语义回源、指标默认过滤注入、独立 `sql.validate` 校验或依赖技能编排已实现；执行历史中也没有这些步骤。

本次查询是单表原始行数统计，不能据此推断复杂业务指标取数的正确率。模型回答中的“只读从库”、指标状态等说明，也不能替代连接器配置或独立工具证据。

若后续补齐依赖加载，应按套件内声明路径解析并加载依赖，明确依赖顺序和失败处理，同时保留现有业务工具边界。仅放开通用读取工具的白名单，不等于完成依赖编排。

## 追加：从真实页面复现“看不到技能读取”

会话：`a8045574-938a-4e17-951e-157ec560dca7`。页面：`http://localhost:3000/`。本次没有拦截或模拟 API，实际点击取数示例、选择 `Walmart_Sales`，再输入计数问题并发送。

页面实际请求包含：

```json
{
  "model_name": "deepseek-r1:1.5b",
  "ext_info": {
    "locale": "zh",
    "database_name": "Walmart_Sales",
    "database_type": "sqlite",
    "suite": "db-query",
    "suite_display": "智能取数",
    "suite_command": "/nl2sql"
  }
}
```

这是页面实际发送的模型选择，不以测试脚本预设的 localStorage 值推断模型，也不据此断言最终模型提供方。本次检查重点是绑定回执、工具结果和界面状态。

实际返回的 `suite.bound` 仍为 `skill_loaded=true`、`command_skill=nl2sql-precision`，正文 SHA-256 与前两次一致。实际 SQL 为 `SELECT COUNT(*) AS total_records FROM walmart_sales`，界面结果表显示 6,435。

| 页面状态 | 实测 |
|---|---|
| 发送完成后 | 绿色提示“指令 /nl2sql · 知识技能 nl2sql-precision 已加载”可见 |
| 刷新会话后 | 套件引用“智能取数 · /nl2sql”恢复，但技能加载提示消失 |
| 独立打开同一会话复核 | SQL 与 6,435 结果可见；加载提示的 DOM 数量为 0 |

截图：`nl2sql-skill-live-before-reload.png`、`nl2sql-skill-live-after-reload.png`。

具体原因：

1. 主技能在工具循环前由后端读取并注入，所以它不产生一个模型调用 `load_skill` 的执行步骤。执行列表只有 `sql_query` 不代表主技能未读取。
2. 前端在 `web/pages/index.tsx` 的 SSE 分支里把 `suite.bound` 写入 `suiteCommandBindings`。当前历史保存及恢复只保留 `suite_reference` 的套件名、显示名和命令，没有保留和恢复技能加载回执。因此刷新后看不到“已加载”提示。
3. 两个关联技能的问题仍是依赖没有自动展开，且模型发起的技能读取工具不在套件白名单内。界面显示问题与关联技能加载失败应分别处理。

本次追加验证未修改业务代码或白名单。
