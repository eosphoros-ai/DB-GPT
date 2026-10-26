# financial-report-analyzer

此内置技能支持中文、人民币、非金融企业的文本型年度报告 PDF，可分析单报告、同年度两到五家公司（`peer`），或同公司两到五份不同年度年报（`trend`）。扫描件、季报、跨币种换算及金融企业专用口径不在本版验收范围。

## 使用入口

在当前智能体对话上传年报。单报告继续使用 `prepare_financial_report`；用户明确要求比较时，使用 `prepare_financial_comparison(file_ids, comparison_kind, baseline_file_id?)`。多附件本身不会触发比较，结果在既有 Computer 工作区展示。

独立 `/financial-analysis` 页面也支持单报告、横向和跨年模式、基准选择、历史与显式恢复。切换基准产生新版本。页面保留原章节导航、执行过程、证据面板和授权原文预览。

## 数据与分析

`scripts/financial_document.py` 提取页级事实和公司身份候选。金额与确定性计算使用十进制字符串；缺失、冲突、文件提取失败分别展示，可比性另行检查公司、期间、币种、合并口径和利润归属。

后端计算毛利率、费用率、现金利润比、资产负债率、相对基准差额、百分点与有效同比。跨年关系要求所选值具备共同披露依据，无法确认时保留断点。明确重述保留调整前后候选及取数政策版本，不按最新文件或首个值静默消除冲突。

智能体复用经营表现、扣非与利润构成、毛利、费用、现金流、资产负债六专题。每条发现声明公司、期间、指标、比较双方和方向，后端验证归属及引用。没有附注依据的原因只能列为待核查项，格式校验失败不得说成财务数据缺失。

发布前复核方向、口径和解释边界。自动校验和模型自查不等于人工确认；可以发布有依据的部分，同时在相关章节明确保留缺口。

## 恢复与导出

单报告保留 v1 协议，对比使用 v2。数据就绪、分析和发布分开表示。每份文档成功后立即持久化；显式继续仅重试失败文件，不重新解析成功文档。单专题重做保留其他专题。

发布版本不可改写。历史、追问、引用和导出可以选择明确版本。JSON 与离线交互 HTML 嵌入相同快照；HTML 内联脚本和样式，来源 PDF 需回应用授权访问。

## 运行说明

当前执行器仅支持单个本地服务进程。旧数据库具备对比所需表结构后才能运行对比任务。财报服务自身不执行 `ALTER`，但启用的框架迁移可能在应用启动时更新旧表，随后财报服务会刷新表结构状态。安排单独迁移前，应先检查目标库的实际结构。在仓库根目录将 `FINANCIAL_DATABASE_URL` 设置为 SQLAlchemy 数据库 URL，先不加 `--apply` 预览剩余变更。以下命令可直接执行，使用隔离的内存数据库；实际维护前应将 URL 替换为目标数据库地址。

Bash：

```bash
FINANCIAL_DATABASE_URL='sqlite:///:memory:'
uv run --no-sync python -m dbgpt_serve.financial_analysis.migrate --database-url "$FINANCIAL_DATABASE_URL"
```

PowerShell：

```powershell
$FINANCIAL_DATABASE_URL = 'sqlite:///:memory:'
uv run --no-sync python -m dbgpt_serve.financial_analysis.migrate --database-url "$FINANCIAL_DATABASE_URL"
```

启用启动迁移或执行维护迁移前应先备份目标库。若预览仍列出缺失变更，按正常维护流程核对后，再在同一命令末尾加 `--apply`；计划为空则无需再次迁移。旧程序不应直接运行在已有对比任务的新库上。

离线 HTML 运行时依赖配套财报工作区前端及已安装的 web 依赖，仅有后端的检出不包含构建脚本。在包含该前端的检出中运行 `node standalone/financial-analysis/build.cjs web/node_modules/.cache/financial-comparison/runtime.html`，然后在后端通过 `DBGPT_FINANCIAL_EXPORT_RUNTIME` 指向构建产物。运行时尚未安装时，HTML 导出返回 `EXPORT_RUNTIME_MISSING`，JSON 导出仍可使用。当前工具流程见 `skills/financial-report-analyzer/SKILL.md`；原脚本及模板保留兼容用途。

具体迁移、隔离验证命令、实测记录及未验收场景见仓库 `docs/financial-comparison-acceptance.zh-CN.md`。合成 fixtures 和工程测试不能代替真实 PDF、真实模型与人工验收。

HTML 导出支持可选的 `language`（`en` 或 `zh`，默认 `zh`），离线控件保留导出时选择的界面语言。中英文 HTML 分别保存为同一报告版本的独立文件，报告内容和 JSON 数据不变。更新前端后需重新构建离线运行时。
