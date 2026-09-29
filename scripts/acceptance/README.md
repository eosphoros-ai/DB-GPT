# 按 Word 清单运行自动验收

入口是 `run_acceptance.py`。专门适配本项目的 **DB-GPT-v9.1-手动验收清单-更新版-20260907.docx**，读取其中 45 个编号、操作标准和模型原始提示词，输出逐项报告。它不是把任意 Word 文档自动转换成测试的通用工具；修改验收口径后也要维护对应断言。

## 运行

在项目根目录的 PowerShell 执行：

```powershell
python scripts/acceptance/run_acceptance.py
```

前端需要已经启动（默认 `http://127.0.0.1:5690`）。脚本从页面实际发出的 Dashboard 请求识别后端地址，检查首页与看板页的 BUILD_ID。浏览器使用项目已安装的 Playwright Chromium，Python 启动器只用标准库。

也可以指定用户提供的 Word 路径，支持 `/D:/...` 形式：

```powershell
python scripts/acceptance/run_acceptance.py --docx "/D:/CodexData/Documents/Codex/work/DB-GPT-Dashboard-Lab-v9.0-showcase-style/output/manual-acceptance/DB-GPT-v9.1-手动验收清单-更新版-20260907.docx"
```

其他环境参数：

```powershell
python scripts/acceptance/run_acceptance.py --base-url http://127.0.0.1:5690 --browser-channel msedge
python scripts/acceptance/run_acceptance.py --expected-build-id 新部署的实际BUILD_ID
python scripts/acceptance/run_acceptance.py --walmart-id 新的来源ID --apple-id 新的来源ID
python scripts/acceptance/run_acceptance.py --storage-state D:/test/login-state.json
```

`--storage-state` 仅使用已有的 Playwright 登录状态；匿名公开页始终使用独立、无登录状态的浏览器上下文。自定义身份头的部署需要额外适配，不能用本地无登录模式证明 SSO/跨用户 ACL 通过。

若依赖缺失，先使用项目运行时；在 `web` 下按项目锁文件安装：

```powershell
npm.cmd ci
node node_modules/@playwright/test/cli.js install chromium
```

`--node` 可指定 Node 可执行文件。脚本不自动安装依赖、不重启服务；运行失败会保留错误和报告。

## 默认会测什么

- A01–A03：真实页面/版本、三个业务模板、创建 Walmart/Apple 测试副本、核对原资产和分享没有变化。
- B01–B05：重新查询实际数据；Walmart 6,435 行、45 门店、143 日期、33 个完整年月、总额和前五名；Apple KPI、三年九项金额、三系列九行及映射。
- B06–B11：双宽度页面边界、四主题深浅模式保存、表头与数据列的实际几何对齐、图元/标签/绘图区测量和顶部截图。可读性结论保留人工复核。
- D01–D03：组件标题和 SQL 定位、未保存 Schema 的临时表格试运行、实际拖拽/缩放、撤销重做和保存重载。
- F01–F07：副本刷新和真实发布、匿名只读页面、V1 不变/V2 与固定最新更新、旧版本恢复、ZIP CRC/文件名/内容检查、八个视图及逐卡截图，最后撤销本轮历史分享。
- R01–R04：错误 SQL 与发布拒绝、无数据查询、浏览器断网保存失败及恢复、未保存离开提醒、真实修订冲突。
- X03/X04/X06/X07：清单自带 CSV 的真实上传/预览和独立关联计算、TXT 服务端拒绝、异常规则数值计算、390 宽公开页。

默认运行**会创建并保留** `UAT-...-运行时间` 副本及本批小样例上传数据，编辑、错误 SQL、发布和撤销只针对本轮新资产。最终保留副本便于复查，不自动清理已有数据。原始演示资产只读。报告中的 `state.json` 记录新 ID、修订、发布、上传数据集和计划。

来源资产没有筛选器，所以不能拿它们冒充 C05 的 A-筛选。D04/D05 的真实 AI 批注、自然出现的 X01/X02、浏览器上传队列重试等尚未实现的部分会明确显示未覆盖或待人工复核。

## 追加可选测试

```powershell
# 只解析文档并生成 45 项覆盖清单，不访问服务
python scripts/acceptance/run_acceptance.py --list-only

# 真实模型规划/修改规划/确认/生成/保存，追加 C01–C05 和依赖的 E01/E02
python scripts/acceptance/run_acceptance.py --live-model

# 两案例 × 四主题 × 深浅模式 × 双宽度：32 个真实发布视图
python scripts/acceptance/run_acceptance.py --theme-matrix

# 创建副本一分钟刷新计划；分别检查立即运行、自然调度、暂停后一个周期
python scripts/acceptance/run_acceptance.py --schedule

# 追加项目现有后端、Vitest、受控浏览器回放，单独保留工程回归结果
python scripts/acceptance/run_acceptance.py --regression
```

这些参数可以组合。`--live-model` 会使用页面当前默认模型和真实数据源，可能产生模型费用；按原提示执行，首次失败保留，不自动付费重试。该路径是可选适配器，只有真实执行后的本轮结果才构成验证证据。模型输出结构不符合预期时按失败或依赖阻塞报告，不能拿固定样例替代。

`--schedule` 通常增加约 3 分钟；计划在 `finally` 中暂停。强制终止进程或服务断联可能使暂停请求无法执行，可根据 `state.json` 的计划 ID 复核。本参数测试 DB-GPT 自身调度器，不创建 Codex 定时任务。

`--regression` 的后端套件需要当前 Python 安装本项目测试依赖。缺依赖、外部数据库未配置、测试跳过等以原始日志/JUnit 为准。受控回放与真实模型结果分列，不用回放给 C/X 人工条目打勾；不写入历史证据目录。

## 输出与退出码

每轮写入新的 `output/manual-acceptance/automation/时间戳/`，不会覆盖第一次失败：

- `report.html`：可按失败/阻塞/待人工复核筛选，展开查看断言、截图和原验收标准。
- `report.md` / `report.json`：完整结果，便于提交问题和接入 CI。
- `checks.jsonl`：逐个检查即时落盘，即使中途失败也保留已经完成的记录。
- `source-checklist.txt` / `config.json`：原文、源 DOCX SHA256、运行参数和基线。
- `api/` / `screenshots/` / `downloads/`：本轮请求结果、实际截图和校验过的 ZIP。
- `state.json`：本轮新建资产/版本/计划；`browser-trace.zip`：实际浏览器操作记录。

截图使用 `evidence` 或 `issue`，不靠 `final` 文件名暗示验收通过。自动检查和清单结论分列：例如 B10 可以测得图形高度，但整体结论仍为“待人工复核”。未知编号显示“未覆盖”，不会静默丢弃。

退出码：`0` 已执行自动检查无失败/阻塞（不代表 45 项人工验收全部通过）；`1` 断言、运行器或工程回归失败；`2` 前提阻塞。加 `--strict` 后，未覆盖或待人工复核也返回 `2`。

运行器自身验证：

```powershell
python -m unittest discover -s scripts/acceptance -p test_runner.py -v
```

## 本次交付的实跑记录（2026-09-07）

- [最终默认运行报告](../../output/manual-acceptance/automation/20260907-172553-481016/report.html)：70 个检查步骤，66 通过、4 失败；4 个失败均对应 **B09 Apple 表头/数据列错位**的两个页面与两个宽度。45 项清单中，31 项的自动断言通过、1 项失败、13 项未覆盖；其中 27 项仍需人工补充判断，不能记作完整验收通过。
- 本轮产生 98 张截图，报告引用的证据文件全部存在，执行期间捕获的浏览器未处理 JavaScript 异常为 0。原始 Walmart/Apple 资产及其原分享列表在运行结束时核对未变。
- [独立可选项运行报告](../../output/manual-acceptance/automation/20260907-171833-547591/report.html)：X05 真实立即运行、自然调度、暂停观察通过，测试计划已暂停；X08 生成 32 个真实公开视图，视觉结论仍待人工复核。这一轮还保留当时的 D03 脚本等待问题；最终默认运行已修正并验证 D03，不把两轮报告合并伪称一次全绿。
- 运行器的 7 个标准库测试通过，四个 Node 脚本语法检查通过。真实模型 `--live-model` 和完整 `--regression` 本次没有执行；相应适配器不能算已经实测通过。
- 复用现有 Python、Node.js 和 Playwright，本次没有下载新软件、技能或插件。
