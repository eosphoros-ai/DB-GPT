# 财报布局恢复与分析流程提速

后续已按要求加入专题并发生成和并行校验，最新实现与实测见 [并发改造记录](financial-analysis-parallel.zh-CN.md)。本文保留上一阶段的串行基线与验收结果。

本次在上一轮未提交的工具路由、最终回答修复之上修改，未回退这些工作，未提交 Git。
开始时阅读了 `financial-analysis-tool-routing-fix.zh-CN.md` 并检查工作区。

## 实现与文件

- `web/new-components/financial-analysis/FinancialAnalysisPage.tsx`：移除报告标题和章节导航之间的专题卡片，恢复原 mock 的布局。
- `ExecutionProcessPanel.tsx`、`TopicCoverage.tsx`、`financial-analysis.module.css`：复用执行步骤列表，在选中专题的详情中显示进度、保存尝试、错误码、字段错误、历史校验、独立复核意见和重试。没有第二组卡片。
- `ReportSections.tsx`、`report-data.ts`、`types.ts`：对应章节如实显示未完成、缺项、失败；兼容旧报告没有错误码的情况。旧报告的引用校验错误不再显示成历史数据缺失。保留指标、图表、来源和内嵌模式。
- `packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/tools/financial_tools.py`：prepare 直接提供首专题，save 直接交接下一专题；正常保存只返回状态、版本和下一步需要的数据。完整已保存 findings 只在读取报告和复核阶段提供。展示用 `chunks` 与模型用 `model_context` 分开，修复草稿不进入展示片段。
- `packages/dbgpt-serve/src/dbgpt_serve/financial_analysis/workflow.py`：失败草稿私下持久化，支持按 finding_index/字段 patches 修复并完整重验；记录保存次数、后端错误码和校验历史；模型复核意见单独保存。达到失败上限仍允许明确部分发布与后续单专题重做。
- `analysis.py`：收集同一发现中所有可定位字段错误；期间只能来自实际提取数据，允许明确年份标签、已知期间范围及 period 引用，金额和其他数字仍需真实引用。增加可用证据/引用修复提示和部分通用解释边界检查，没有公司、PDF 文件名或固定年份分支。
- `service.py`：沿用锁和 revision 检查，在明确逐专题复核通过（或明确失败/不足）后同一事务内执行确定性发布；revise 不发布。保留显式读取、重做和发布兼容工具。
- `api.py`、`exports.py`：公开快照及 JSON/HTML 导出剔除内部修复草稿。已注册导出保持不可变。
- `agentic_data_api.py`、`skills/financial-report-analyzer/SKILL.md`：两种入口都使用直接交接和复核后自动发布说明。
- 后端三个财报测试文件、`scripts/financial_analysis_agent_check.py`、`standalone/financial-analysis/` 下测试/构建/预览入口：补充测试及实测记录。预览入口只用于测试，不用于正常导出。

无失败时调用链从至少 16 轮降为 9 轮：prepare、六次 save、review、terminate。没有并发写报告，也没有删除专题或跳过复核。费用专题还要求覆盖当前提供的各类费用科目。

## 只读基线与最终实测

基线读取 `pilot/meta_data/dbgpt.db` 与 `logs/observability.db`，SQLite 使用 mode=ro；没有重新调用模型建立基线。
运行 `7e87b6f4-2661-4b47-bab8-2a23d3d83dca`，会话 `cecff643-ae1e-4896-93ed-8e7ec8f46ae2`。
确认经营表现的末次错误是待核查字段中的裸年份，而原始年度事实存在；模型复核意见错误地归因为历史数据缺失。

测试使用端口 5672 和 `.work/financial-analysis/speed-layout/` 下的独立配置、元数据库、跟踪库、文件与向量目录。没有重启或终止日常服务。
最终测试设置独立 DBGPT_HOME；较早中间测试的代理快照使用默认目录中的独立测试会话名，没有覆盖日常会话。
全部真实测试使用用户指定的同一份海翔药业 PDF 和“为我分析一下这份财报”，不预选 Skill，经首页相同的 API/SSE 自动入口发起。

| 指标 | 原运行 | 最终运行 |
| --- | ---: | ---: |
| 智能体根 span 耗时 | 532.784 秒 | 254.917 秒 |
| PDF 提取 | 11.313 秒 | 11.078 秒 |
| 提取后分析阶段 | 511.692 秒 | 237.605 秒 |
| 模型调用 | 24 | 11 |
| 模型调用累计耗时 | 512.888 秒 | 242.432 秒 |
| 序列化输入消息字符 | 2,099,996 | 936,061 |
| 模型输出字符 | 45,723 | 24,003 |
| 保存尝试 / 校验失败 | 12 / 7 | 8 / 2 |
| 保存的、通过字段/引用校验的发现 | 14 | 18 |
| 独立事实 / 计算引用数 | 26 / 24 | 27 / 24 |
| 专题状态 | 经营表现失败，其余五项 reviewed | 六项 reviewed |
| 发布 / 分析状态 | published / partial | published / completed |

最终智能体时间下降约 52.2%，输入字符下降约 55.4%。最终上传开始至最终回答为 **277.2 秒**，不含后续追问和重做；连同追问、重做的检查脚本为 362.3 秒。根 span 与端到端计时边界不同，不混用比较。
模型接口没有返回可用 token 统计，因此以上是字符数，不能作为 token 数。计数取同一根运行的时间范围，排除追问/重做。

最终 run：`248ec26f-3ebe-41cd-92da-7dc7947b882b`。
最终会话：`financial-agent-check-55e1e14feb7d4053980a994e992d1e16`。
证据：`.work/financial-analysis/speed-layout/acceptance/` 中的 result、report、analysis/followup/retry events、重启后快照和导出；汇总在 `performance-all.json`。

为避免只选择最快结果，中间三轮智能体时间分别为 182.407、190.935、279.177 秒，调用数分别 12、12、17；保存失败分别 3、3、9 次，发现数 12、18、12。第三轮为经营表现失败的部分发布。中间结果暴露了期间范围、错误反馈和内容解释问题，随后修订；不是最终版本的重复抽样，也不能用于宣称稳定的平均性能。

## 验证及未通过项

- 财报后端、工具、入口提示、最终回答和示例 API：**121 passed**，只有已有依赖弃用警告。
- 前端数据/SSR、原 mock 布局比较（`5eb7ac42`）、历史/导出、聊天 artifact、追问状态检查通过。
- Chrome 真实组件与真实报告数据：成功、运行中、部分失败，各含整页和内嵌，共六种情况通过；验证标题紧邻导航，正文没有专题卡片，执行详情和重试禁用/回调正确。保存并查看截图，浏览器无 pageerror。
- 图片在 `.work/financial-analysis/speed-layout/visual-acceptance/`。运行/失败状态由真实快照调整状态以确定性复现；没有宣称每种状态均单独调用模型。
- 真实追问只读已有报告，返回收入与原文页码，revision 不变。真实费用专题重做发布新 revision，其他专题发现不变。
- 独立服务重启后，历史列表与报告可重新打开；PDF 下载 SHA256 一致；来源物理页 80、83、89 返回有效 PNG；JSON/HTML 导出注册、下载与公开快照一致，未改变报告。
- Ruff、修改前端文件 ESLint、git diff --check 通过。
- 全项目 TypeScript：对照 HEAD 内容的 139 个诊断，当前 138 个；**新增零个**，修复财报 CashFlowTab 的 undefined 类型错误一个。没有将全项目类型检查说成通过。
- 上一轮文档记载的附件/聊天历史及流式生命周期失败，本轮没有重新运行扩大测试，不能视为本轮已修复；详见原工具路由修复文档。

**未达到 2～3 分钟目标。** 最终模型累计用时约占根运行的 95%，剩余瓶颈是模型生成延迟/输出量及修复调用。轮次和重复上下文已减少，但单次模型速度与内容长度仍会波动。没有为追求时间并发写同一 revision；如后续做并发，需先实现各专题独立草稿版本和确定性合并。

**内容质量验收仍有限制，不能把 18 条保存记录等同于 18 条语义正确的发现。** 人工抽查最终报告发现：毛利专题尝试从收入增长与毛利率变化自行推导成本降幅；现金流文字存在同一引用与自身比较；还有对实际已有历史数据作缺失判断等问题。模型的全部 reviewed 没能拦截这些错误。通用引用、字段、数字和部分解释规则检查不是完整语义证明；本次不通过继续堆砌针对这份 PDF 的措辞规则来掩盖问题。因而已验证六专题覆盖和流程提速，但不能宣称“同等内容质量已全面验收”。保留人工核对提示、原文证据及重做能力，后续需要跨公司样本和独立的语义复核评估。

本轮验证是自动入口 API/SSE 联调加真实 React 组件浏览器检查，没有人工在完整 Next 首页逐项点击上传；预选 Skill 入口的提示/路由通过测试保留，本轮未为它再额外调用一次完整模型。

## 用户重启使用

自行停止并重启原后端进程，使新工具说明和校验代码生效。沿用当前配置，例如：

```powershell
cd D:\Python\py_projects\DB-GPT
uv run --env-file .env --no-sync dbgpt start webserver --config configs/dbgpt-proxy-tongyi.toml
```

前端开发服务通常热更新；若使用构建版本，按原部署方式重新 build 并重启前端。Windows 下可直接调用 Next CLI，避免 package 脚本中的 Unix 环境变量语法：

```powershell
cd D:\Python\py_projects\DB-GPT\web
$env:NODE_OPTIONS='--max_old_space_size=8192'
node node_modules/next/dist/bin/next build
node node_modules/next/dist/bin/next start
```

HTML 导出也需重建离线运行时（已有注册导出保持原版本）：

```powershell
cd D:\Python\py_projects\DB-GPT
node standalone/financial-analysis/build.cjs .work/financial-analysis/export-runtime.html --export-runtime
```

如果部署设置了 DBGPT_FINANCIAL_EXPORT_RUNTIME，构建到它指定的位置。不要使用本次测试的 workflow-preview 文件作为正式导出运行时。新建聊天上传 PDF 即可使用自动入口，也可预选财报 Skill；旧报告可继续从历史打开。
