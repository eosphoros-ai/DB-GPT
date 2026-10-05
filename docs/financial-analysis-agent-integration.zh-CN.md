# 首页智能体财报接入与验收

日期：2026-09-29；收尾与提交：2026-09-30。

后续六专题分析、修正反馈、复核发布和最新验证结果见[第 10 轮记录](financial-analysis-round10.zh-CN.md)。下面保留首次首页接入的验收说明和历史结果。

## 当前行为

用户点击首页财报示例，或在当前对话上传 PDF 年报后要求分析，继续使用 `/api/v1/chat/react-agent`。当前智能体调用 `prepare_financial_report` 提取事实并执行 Decimal 计算，然后根据工具返回的数据撰写结论，调用 `publish_financial_report` 校验和保存。此路径不会再启动独立的 Qwen 分析器。

工具返回持久化的报告引用，首页右侧 Computer 直接渲染已有 React 财报组件，复用原 mock 设计的五个章节、证据、来源和下载界面。真实结果不引用 mock 数字。独立 `/financial-analysis` 页面保留兼容用途，首页卡片的预览按钮通过 `?demo=1` 查看原演示；执行分析点击卡片本身。

报告发布前禁止智能体用“接下来将生成报告”结束任务。完成摘要使用已保存的真实状态和结论数量，避免将部分分析宣称为完整覆盖。后续追问必须先读取当前 owner/session 的已保存报告，数字占位符在最终回答和历史保存前统一校验并替换，来源页码由服务端补齐。解释校验失败时仅展示有效引用数据并说明降级，未知引用被拒绝。

## 启动与验收

先重启自己运行的后端加载代码，前端使用开发模式即可加载修改。分别在两个 PowerShell 窗口执行：

```powershell
cd D:\Python\py_projects\DB-GPT
uv run --env-file .env --no-sync dbgpt start webserver --config configs/dbgpt-proxy-tongyi.toml
```

```powershell
cd D:\Python\py_projects\DB-GPT\web
$env:NODE_OPTIONS = "--max_old_space_size=16384"
node .\node_modules\next\dist\bin\next dev -p 3000
```

1. 打开 <http://127.0.0.1:3000/>，点击财报示例卡片发起新对话。确认示例加载不再出现 Windows `file_path invalid`。
2. 执行过程应出现 `prepare_financial_report`、`publish_financial_report`，右侧显示海翔药业实际报告；不要求进入独立财报路由，也不另外生成一套 HTML 页面。
3. 查看五个章节，点击营业收入等指标的依据，打开 PDF 原页。缺项及“部分分析”应如实显示。
4. 在当前聊天输入“本期营业收入是多少？请提供原文依据。”，应读取已有报告，无需重新解析 PDF，最终答案不应残留双花括号占位符。
5. 刷新并重新打开聊天历史，检查报告能重新加载。在报告文件页下载 JSON/HTML，核对公司、数值和来源。
6. 新建对话上传自己的 PDF 后分析；多份 PDF 时明确选择文件。其他对话不能读取当前报告。

## 已做验证及边界

- 财报服务与示例 API 共 71 项测试通过，包括无嵌套分析器、真实存储、跨 owner/session 拒绝、发布版本校验、追问完成约束、数值引用校验和中文 PDF 示例路径。
- 结构化产物测试通过：聊天历史引用保留、切换报告的过期响应丢弃、嵌入布局、来源/导出作用域、失败重试和下载。
- mock/替换/空报告及真实报告渲染测试通过；独立演示初始 HTML 与已接受的 `5eb7ac42` 一致。
- TypeScript 基线比较无新增错误（基线和当前均为 138 项历史错误）；修改文件 ESLint 无错误，保留 ManusRightPanel 两条已有 Hooks 警告。
- 独立测试端口 5671 上通过真实首页示例 API 和真实 Qwen 当前智能体完成提取、发布、同会话追问及历史引用保存。两次海翔报告分别保留 2 条和 3 条结论，状态均为 `partial`；不代表所有章节均有通过校验的结论。最后一次执行为 prepare → publish → terminate，追问为 read → terminate。
- 该报告来源物理页 7、80、89 的接口响应、原 PDF 字节、访问归属校验通过；重新打开、JSON/HTML 快照、摘要及导出幂等检查通过。
- Next 首页编译并返回 HTTP 200。浏览器工具无可用连接，未完成实际点击、布局、下载及离线 HTML 的浏览器验收；以上组件/API 检查不替代用户验收。

测试运行文件保存在被忽略的 `.work/financial-agent/`，示例复制文件在被忽略的 `python_uploads/`，不随源码提交。独立测试使用临时数据库，示例报告不会自动出现在用户 5670 服务的历史中，用户验收需从首页发起新分析。

收尾时已关闭本轮独立的 3001/5671 测试服务，用户原有 3000/5670 服务仍在运行。后端需由用户重启以加载本轮修改。

## 回归命令

在仓库根目录执行：

```powershell
.venv\Scripts\python.exe -m pytest packages/dbgpt-serve/src/dbgpt_serve/financial_analysis/tests packages/dbgpt-app/src/dbgpt_app/tests/test_examples_api.py -q --disable-warnings
node standalone/financial-analysis/test-data.cjs
node standalone/financial-analysis/test-layout.cjs 5eb7ac42
```

有状态 React 测试沿用第 7 轮独立安装的 `react-test-renderer`；该目录不存在时，按第 7 轮说明安装与前端 React 一致的版本，并将模块目录作为参数传入：

```powershell
node standalone/financial-analysis/test-agent-artifact.cjs .work/financial-analysis/round7/ui-test/node_modules/react-test-renderer
```

用户验收后再讨论新增需求。完整附注检索、扫描件 OCR、多文件期间合并和人工复核流程仍是后续议题。

## 2026-09-30 用户验收修复：结论校验重复失败

安靠年报的实际智能体记录中，模型反复将计算引用写成缺少 `calculation:` 的简写，一条发现使用十个计算引用（限制为六个），另一条还直接写出数字阈值。原反馈只有错误计数，连续四次同类失败后，模型提交空结论，最终保存部分分析的数据报告，有效结论为零。

本次改动：

- 对已经声明且确实存在的计算 ID，兼容双花括号中直接写计算 ID 的无歧义简写；未知引用、未声明引用、直接数字和重复单位仍拒绝。
- 提取结果提供可直接复制的 `reference` 字段及使用当前报告真实 ID 的合法提交示例，格式说明放在数据前。
- 校验失败返回发现序号、字段名和长度限制给当前智能体。界面展示自动修正进度，不再只显示英文错误统计。
- 连续三次全部失败后停止重试，保存明确说明“仅保留财务数据与原文依据”的部分结果，不宣称完成分析。

74 项财报与示例回归通过。只读获取该报告并重放原失败提交，恢复两条有效引用结论，另两条仍被拒绝，动态提交示例也通过校验。重放未修改用户已保存报告；新工具提示对真实模型的下一轮输出仍需重启后端后重新验收。
