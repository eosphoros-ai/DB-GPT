# 多财报对比运行与验收记录

实施日期：2026-10-24。实施计划：`docs/financial-comparison-implementation-plan.zh-CN.md`。

## 交付范围

- 单报告继续使用 v1；对比使用 v2 判别协议，不伪造单公司身份字段。
- 对话和独立页均支持两到五份 PDF，明确选择同年度多公司或同公司跨年模式。公司/期间不明确时保存数据并等待确认。
- 逐文件持久化、任务内复用、显式局部重试、重启恢复；每任务文档提取预算为一，服务线程池有界，不创建同池子任务再等待。
- Decimal 确定性计算、候选来源和重述政策、方向及双方输入审计；缺失、冲突和不可比保留原因。
- 六专题及局部 patches、结构化归属/方向校验、模型语义复核、部分结果发布；追问固定版本且不心算。
- 复用既有工作区布局、多文档来源、移动矩阵、基准切换、历史版本选择、不可变引用与 JSON/离线 HTML。

## 数据迁移与部署

初次实现仅在 pytest 临时目录或 `web/node_modules/.cache/financial-comparison/acceptance-*.sqlite` 验证。2026-10-24 用户要求实际启用功能后，已备份并核验日常数据库、重启后端，并补充真实接口验收；没有重置或清理原有数据。

旧任务表增加 `mode`、`config_json` 和 `request_fingerprint`，增加成员表与不可变快照表；旧报告 JSON 原样保留。显式迁移工具不会读取应用默认数据库配置。

尚未添加上述三个字段的旧库在组件注册时使用单财报兼容映射，不再阻断整个后端。财报服务本身不自动 ALTER；应用随后按既有配置执行框架迁移，`SessionFileServe.after_init` 再刷新字段与版本能力，因此正常升级在同一次启动中即可启用对比。若框架迁移被关闭且库仍未升级，则继续保留单报告创建、旧报告读取、专题发布、当前版本问答/导出及重启恢复，对比操作返回 HTTP 503 / `COMPARISON_MIGRATION_REQUIRED`。未升级的兼容模式不提供新增不可变历史，缺失版本明确报错。

如果三个字段仅添加了其中一部分，仍明确拒绝该未完成的迁移，需通过显式工具完成后重启。迁移和重启完成后启用对比与不可变版本能力，不补造旧报告已经丢失的历史版本。

当前配置 `configs/dbgpt-proxy-tongyi.toml` 指向 `pilot/meta_data/dbgpt.db`。此次 `prepare_financial_comparison` 被拒绝的实际原因是：23:16:23 框架已通过本地 Alembic revision `f1172077f590` 补齐字段，但财报服务缓存了组件注册阶段的旧库状态。已补上迁移后的能力刷新，而非要求用户再重复修改已齐备的数据库。另已将“正在逐份提取”进度移到任务成功创建之后，避免任务尚未启动就显示提取中。

需要外部显式迁移时，以下示例须替换为确认且已备份的目标库；临时 SQLite 已验证实际增量升级，日常库本轮核验没有待执行 DDL：

```powershell
uv run --no-sync python -m dbgpt_serve.financial_analysis.migrate --database-url "sqlite:///D:/isolated/financial-copy.sqlite"
uv run --no-sync python -m dbgpt_serve.financial_analysis.migrate --database-url "sqlite:///D:/isolated/financial-copy.sqlite" --apply
```

迁移是可重复的增量操作。SQLite 已实际测试，MySQL/PostgreSQL 仅完成 DDL 编译检查，尚无真实数据库验收。MySQL DDL 会隐式提交，不能承诺多语句事务回滚。

与计划建议不同：为兼容旧表的 `file_id NOT NULL`，对比任务保留基准附件指针；权限验证实际使用成员表和 SHA-256，不依赖此兼容字段。旧任务无法恢复从未保存过的历史内容，缺失版本返回明确错误。旧程序不应直接运行在包含对比任务的新库上；回退前须导出比较任务并使用匹配的数据库备份。

当前执行器限单服务进程，不提供多进程分布式锁或调度。其他环境部署前需完成目标数据库迁移和离线组件构建；本轮已启用本地日常后端，未执行远端部署。

### 日常环境启用与数据保护

- 一致性备份：`pilot/meta_data/dbgpt-before-financial-comparison-20261024-232737.db`；审计：`logs/financial-comparison-migration-20261024-232737.json`。
- 迁移工具检测返回空计划；核对原有 67 张表、562 条记录（含 34 条财报任务），迁移核验期间所有原有字段的内容哈希一致，SQLite 完整性检查通过。
- 重启恢复了两条旧的未完成专题任务，财务内容保持不变，仅更新报告 revision 与任务阶段。两份重启前真实快照已从备份补入不可变版本表，原版本 API 读取返回 200；当前报告指针未回退。代码同时覆盖今后正常重启和“先旧库注册、后框架升级”的草稿版本保留。
- 后端健康检查返回 200，对比任务创建返回 202；独立验收会话 `comparison-acceptance-20261024-233131` 上传仓库两份真实 2019 年年报，任务 `dde766ec-51ea-43df-b566-31c6b7d47e4b` 已完成两份提取，比较就绪，保存 115 条事实与 25 项计算。旧单报告 API 读取仍返回 200。
- 真实接口快照和状态：`logs/financial-comparison-live-acceptance-20261024-233131.json`。本轮模型已结束，保留 15 条已校验发现；利润率、费用、现金流三个专题就绪，经营概览、经常性利润、资产负债三个专题失败，最终为 `draft / awaiting_revision`，未发布。提取 21.468 秒、对齐计算 0.016 秒、模型分析 629.312 秒；不将部分结果称为全专题验收通过。
- 最后一次后端重启后，保存的对比报告与重启前 JSON 完全一致；JSON 导出与指定 revision 完全一致，版本列表和两份原文下载均返回 200。当前本地后端监听 5670，PID 11980；启动记录为 `logs/financial-comparison-server-20261024-234341.json`。浏览器完整聊天链路和日常离线 HTML 成品仍未在本轮验证。
- 最终后端相关测试 **61 passed**（财报/工具/恢复 50 项，文件服务生命周期 11 项）；新增覆盖框架迁移后同一次启动启用对比、未迁移兼容模式、重启前草稿版本保留。

## 构建与工程验证

从项目根目录执行，避免覆盖已有日常离线产物：

```powershell
node standalone/financial-analysis/build.cjs web/node_modules/.cache/financial-comparison/runtime.html
uv run --no-sync python scripts/verify_financial_comparison.py --output-dir web/node_modules/.cache/financial-comparison --runtime web/node_modules/.cache/financial-comparison/runtime.html
uv run --no-sync pytest packages/dbgpt-serve/src/dbgpt_serve/financial_analysis/tests packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/tests/test_financial_comparison_tools.py packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/tests/test_financial_history_recovery.py -q
npm.cmd run test:financial --prefix web
npm.cmd run test:e2e:financial --prefix web
```

使用 `DBGPT_FINANCIAL_EXPORT_RUNTIME` 指定部署时的离线 runtime。导出 JSON/HTML 读取同一精确 revision；HTML 内联资源并对嵌入 JSON 转义。离线原文预览明确提示需返回应用授权，不能声称离线已含 PDF。

验收脚本的七类协议 fixtures 均明确标记 SYNTHETIC，只用于工程验证。脚本不会加载日常数据库。完整 TypeScript 检查存在本次开工时即有的 142 个错误；当前按文件与 TS 错误码对照，没有新增错误组，对比模块没有类型错误。部分 i18next 联合类型诊断的文本顺序会变化，不能将文本顺序差异当作新增问题。

初次收口结果：后端 40 项通过，前端单元 8 项通过，浏览器 11 项通过（十项合成/单报告场景和一项真实已保存快照）；改动范围 24 个前端文件 ESLint 通过，无警告；Python Ruff 与格式检查通过，`git diff --check` 通过。离线 runtime 为 3,932,112 字节。浏览器验证包含真实未发布状态、双方来源、移动矩阵及无外部网络依赖；没有将离线浏览器测试称为日常服务验收。

2026-10-24 23:06 用户反馈后端在 `SessionFileServe.init_app → FinancialAnalysisService → ensure_schema` 因旧库缺列退出。现已改为上述单财报兼容模式，并在临时 SQLite 复现组件注册路径。修复后同一后端测试命令 **46 项通过**，新增覆盖旧库组件注册、API 与对比操作限制、单报告专题/问答/导出全过程、重启恢复、显式迁移后开启对比及部分迁移拒绝；断言兼容模式下表结构不变。改动 Python 文件 Ruff/格式检查及 `git diff --check` 通过。本轮没有启动日常服务、连接日常数据库或运行真实模型；前端未改动，未重复执行前端验收。真实配置重新启动仍待用户验证。

## 真实同年度样本

来源为仓库已有 `docker/examples/fin_report/pdf/` 年报，未另外下载。两个来源为 2019 年报告，公司身份由 PDF 封面识别。初次检查发现释义页含很多关联公司，提取器已改为优先封面身份，前五页只作后备。

| 公司 | SHA-256 | 页数 |
| --- | --- | --- |
| 浙江海翔药业股份有限公司 | `f1ce2fa8da8088054d1d22ceaa14ddd91ea28668fc12f76ce1ca7f0b723d2be2` | 204 |
| 北方华锦化学工业股份有限公司 | `ab6bdbcba9a63e05e3476ee0f4276258918ae8582b1466c5aa22da910a30810a` | 121 |

下列值由实施 Agent 检查提取结果并渲染相关原表核对，**不是独立人工金标准**。金额单位均为元，页码为 PDF 物理页：

| 科目 | 海翔药业 | 来源页 | 华锦股份 | 来源页 |
| --- | --- | --- | --- | --- |
| 营业收入 | 2,941,412,770.30 | 7、83 | 39,608,340,979.04 | 50 |
| 归母净利润 | 770,782,185.09 | 7、85 | 992,955,495.15 | 51 |
| 经营现金流 | 612,399,095.31 | 7、89 | 2,723,475,056.01 | 54 |
| 总资产 | 6,747,198,664.47 | 7、79 | 29,359,202,252.30 | 47 |
| 总负债 | 1,022,736,568.92 | 80 | 15,213,067,305.30 | 48 |
| 营业成本 | 1,463,159,361.04 | 83 | 33,842,254,831.21 | 51 |

本次实际查看渲染图包括海翔第 7 页、华锦第 50、51 页；其余表页的独立人工逐项核对仍未完成。上述公司并非同业，财务科目可比不代表业务结构可比，不作竞争力或排名结论。

实施 Agent 的独立 Decimal 数值审计核对了选定的十二个核心金额、六个比率及一项差额；结果写入隔离缓存 `real-numerical-audit.json`，全部一致。毛利率分别约为 50.2565782058% 和 14.5577572938%，现金利润比分别约为 0.7945164109 和 2.7427967007，资产负债率分别约为 15.1579436116% 和 51.8170322700%。以海翔为基准的华锦营业收入差额为 36,666,928,208.74 元。此为工程数值核对，仍不标为人工 Gold 或投资判断。

## 真实模型执行

配置为已有 `configs/dbgpt-proxy-tongyi.toml`，凭证从 `.env` 读取但不输出；实际调用通义兼容接口。隔离运行 ID 为 `9dddd660-fd1b-4e6e-92bf-fae9ad8fab61`，数据库文件为 `acceptance-b96dcd2d9ce44c23b04467cf4fb7f5e0.sqlite`。

第一轮：提取分别耗时 12.093 秒和 10.141 秒；提取阶段 22.282 秒，对齐计算 0.015 秒，模型阶段 771.765 秒，总计 794.266 秒、17 次模型调用。费用专题通过结构化校验，其他五个专题失败；保留四条已校验发现，未发布。失败包括 subject 为空、指标输入归属不全、错误引用和无依据解释，复核未成功完成。以上是失败验收证据，不能标作真实模型发布通过。

随后补充字段模板、单对象 subject 要求和失败草稿反馈；恢复任务复用同一数据库与成功提取，仅重试失败专题，不覆盖第一轮 `first-real-*` 产物。最终状态与工程检查结果在实施计划执行记录中更新。

恢复轮：十四次模型调用、501.359 秒，文档提取调用为零；费用和扣非专题通过校验，保留发现从四条增加至七条，其余四个专题仍失败。单独复核轮：两次模型调用、33.016 秒，再次提取为零；复核意见在扣非专题 note 中重复出现未获引用的数字/格式，后端拒绝后保留 `awaiting_revision` 草稿。三轮累计三十三次模型调用、1328.641 秒。最终报告未发布，真实模型完整发布验收仍未通过，不能用七条有效发现替代该验收。

上述失败进一步推动工程修复：三次专题校验失败后保留其中可验证的部分；语义复核有界重试并携带实际错误；失败后显示“待修订 · 数据已保留”，执行页可查看复核原因。保存旧草稿再切换基准或补齐文件，旧版本仍可读取。后续这些边界已通过工程回归，没有为得到发布状态而放宽公司、方向或数字校验。

真实验收复现命令：

```powershell
$realPdfs = @(Get-ChildItem -LiteralPath 'docker/examples/fin_report/pdf' -Filter '*.pdf' | Sort-Object Name | Select-Object -First 2 -ExpandProperty FullName)
uv run --no-sync python -u scripts/verify_financial_comparison.py --output-dir web/node_modules/.cache/financial-comparison --runtime web/node_modules/.cache/financial-comparison/runtime.html --model-config configs/dbgpt-proxy-tongyi.toml --env-file .env --real-pdfs $realPdfs
```

已有隔离任务用 `--resume-database <同输出目录内的acceptance-*.sqlite> --resume-run-id <真实ID>` 继续；不得传入日常数据库。脚本记录 `real-acceptance.json`、`real-acceptance-attempts.jsonl` 和 `real-peer.json/html`，原始提取按 SHA-256 另存。

仅复核已保存且全部专题已结束的版本时可另加 `--review-only`，不重新解析 PDF 或生成失败专题。最终本地可复查产物位于 `web/node_modules/.cache/financial-comparison/`；没有把缓存产物添加到 Git 暂存区。

## 未完成的真实验收

- 同公司不同年度的两份真实 PDF：现有测试包含合成跨年及真实报告比较期数据，不能替代此场景。
- 真实缺失、重述或冲突材料：合成 before/after 和冲突校验已覆盖，尚无对应真实材料验收。
- 独立人工核心金额、比率与解释复核；上表不标为人工 Gold。
- 真实模型全专题及发布闭环：本次已执行并记录失败，最终为七条已校验发现的待修订草稿。
- MySQL/PostgreSQL 实际迁移、真实聊天浏览器全链路、生产构建；已补充日常 SQLite 配置下的后端启动、真实接口多财报提取和旧报告读取，不能将其等同于完整聊天发布验收。

2026-10-24 实施阶段没有提交、推送或远端部署。原有单报告功能及工作区内容保留；本地后端已按用户要求重启并启用对比，备份与验收记录保留，均未作为真实人工验收标签。

## 2026-10-25 交付复验

按用户要求执行检查，并将现有修改按对比计算核心、后端流程与工具、前端工作区、构建与验收工具、文档五个功能批次交付。远端目标为用户 fork 的 `origin`，同步 `feat/financial-analysis-round10` 与 `main`。

- 后端财报、工具、历史恢复及文件服务生命周期测试 **61 passed**。
- 前端财报单元测试 **8 passed**；重新构建离线 runtime，大小为 **3,932,112 字节**。
- 浏览器离线测试 **11 passed**，覆盖七类对比状态、双方来源、移动矩阵、单报告及真实已保存快照。所有页面使用本轮构建的 runtime；真实快照仅重新渲染，没有重新解析 PDF 或调用模型。
- 本轮涉及的 34 个 Python 文件 Ruff 与格式检查通过，前端改动范围 ESLint 无警告，Git 差异检查通过。
- 全量 TypeScript 检查仍有 **142 个错误**；按文件与 TS 错误码计数和已有基线一致，财报组件无类型诊断。全量类型检查尚未通过，不将范围检查等同于生产构建验收。

本轮复验使用临时 SQLite、明确标记的合成数据及已有保存快照；未操作日常数据库或重启服务。真实模型完整发布、跨年真实 PDF、独立人工核对、其他数据库及完整聊天浏览器链路等既有缺口继续保留。
