# 财报工具调用、复核反馈与最终回答修复

日期：2026-10-06。

## 问题与修复

首页上传海翔药业年报后输入“为我分析一下这份财报”，智能体读取了
`financial-report-analyzer`，却把 `prepare_financial_report` 当作技能脚本。
它反复猜测不存在的脚本名，再绕去 Python、Shell 和知识库工具，未进入财报流程。

首页自定义系统提示覆盖了 ReAct 默认提示，却遗漏实际 `action_space`。
手写工具清单既未说明财报工具参数，又描述了当前未注册的知识库工具。
通用的“处理数据执行脚本”和“报告必须生成 HTML”指令也与财报 Skill 冲突。

- `react_prompt.py` 使用 ReAct 当前绑定资源生成的 `action_space` 和
  `action_space_names`。工具名、描述与参数来自实际注册资源，覆盖自动选择和预选
  Skill，并保留嵌套工具包中的工具及描述里的字面 JSON/引用。
- 财报提示明确六个工具为后端工具，提供 `Action: prepare_financial_report` /
  `Action Input: {}` 示例；脚本执行仅用于技能明确提供的脚本。
- 通用提示和 `html_interpreter` 描述将 HTML 规则限定到非财报场景。
- 真实联调发现另一个阻塞点：模型把失败专题的三项 Checked 填为 false，后端只
  返回笼统复核错误，模型持续修改 note。`workflow.review_report` 现在指出具体
  专题、错误字段和要求；note 错误也指出对应专题。Checked 表示已检查该维度及
  缺口，结论是否通过由 verdict 表达。失败/缺数据仍用 insufficient，校验失败
  不修改报告。
- 联调追问还发现最终回答参数不一致：实际 `terminate` 工具声明 `output`，首页
  只提取旧 `result`。现在提示使用实际参数，最终回答兼容 `output`、`result` 和
  `final_answer` 的 ReAct/JSON/字典返回，并处理内核已有的仅 Thought 终止分支。
  读取报告返回可直接复制的引用示例，金额、年份与来源页码仍由后端严格校验和渲染，
  不把模型思考中的数字混入回答。

## 回归

财报服务、首页示例、提示词与最终回答检查共 **113 项通过**。新增覆盖直接调用示例、
实际注册工具清单、未注册工具不进入清单、字面引用保留，以及复核反馈的字段
定位、严格布尔值、失败时报告不变，以及终止参数兼容与引用校验衔接。
修改文件 Ruff 检查、格式检查和空白检查通过。

附件与聊天历史扩展测试为 59 项通过、3 项跳过、14 项失败。使用原版
`agentic_data_api.py` 对照得到相同结果；这些既有失败涉及 Windows 路径及入口测试。
另外流式生命周期测试为 2 项通过、3 项失败，原版入口得到相同结果，原因是旧测试桩
未接受已有的 `attachment_ctx` 参数。以上既有失败未纳入本次修复。

海翔药业年报使用原始问题“为我分析一下这份财报”，不预选 Skill，在独立服务上
完成提取、六个专题的保存与复核、发布和历史报告引用检查。六个专题均为 reviewed，
分析状态 completed，保存 **18 条有效发现**；全过程未绕去脚本、Python/Shell、
HTML 或语义搜索。

追问“本期营业收入是多少？请提供它的原文依据。”只调用读取报告和终止工具，返回
`2,941,412,770.30 元` 和原 PDF 物理第 `7、83` 页，报告及版本没有变化。
联调证据位于 `.work/financial-analysis/tool-routing/final-automatic/`，包含
`result.json`、`report.json` 和分析/追问 SSE 事件。
普通 Qwen 对话也通过严格正文检查：只终止对话，返回要求的测试标记，不泄漏
`Thought:` 等协议前缀。
在同一会话连续重复追问的检查中，模型曾多次调用只读工具后才结束；没有重新提取
或修改报告。本次未加入模型工具调用的确定性去重机制。

## 可重复的自动选择入口检查

`financial_analysis_agent_check.py` 新增 `--no-skill` 与 `--question`，能够复现
不预选 Skill、直接上传 PDF 的首页请求。检查还要求整个分析不绕去脚本、通用
解释器、HTML 或语义搜索，并检查发布、历史报告引用及追问读取已有报告。

在独立测试服务和数据库上运行；此命令会创建测试会话、上传文件并调用模型：

```powershell
.venv/Scripts/python.exe scripts/financial_analysis_agent_check.py --base-url http://127.0.0.1:5671 --output-dir .work/financial-analysis/tool-routing/final-automatic --user-id financial-tool-routing --no-skill --question "为我分析一下这份财报" --pdf "python_uploads/001/2020-01-23__浙江海翔药业股份有限公司__002099__海翔药业__2019年__年度报告.pdf"
```

日常使用先重启后端，再新建聊天、上传 PDF 并发起分析，以加载新的工具说明和反馈。

```powershell
cd D:\Python\py_projects\DB-GPT
uv run --env-file .env --no-sync dbgpt start webserver --config configs/dbgpt-proxy-tongyi.toml
```
