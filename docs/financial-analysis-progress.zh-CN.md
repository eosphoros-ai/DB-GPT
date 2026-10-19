# 财报分析的固定阶段与实时反馈

原先临时计划、报告内部步骤和工具调用次数是三套数量。财报公共进度现在始终为
读取财报、分析财务数据、核对结论、生成报告四个阶段。内部专题、重试次数、失败
状态和证据校验仍保留，不参与公共阶段计数；“报告已生成”也不代表所有内容都有依据。

报告页面顶部的状态同样按发布状态显示“分析中”或“报告已生成”，不再把内部的
`analysis.status=partial` 直接显示为“部分分析”。旧版无 workflow 的报告使用分析
完成状态/时间判断；缺项和校验说明仍保留在对应章节及执行详情中。

## 实现

- `financial_analysis/progress.py` 投影公共阶段，保存阶段 ID、开始时间、更新时间和说明。
- `financial_tools.py` 使用已有 `financial.progress → plan.update → task_plan` 通道，
  提取开始即推送；中断保留四阶段。历史使用本轮保存的进度。
- `parallel.py` 在模型生成、校验、修正时推送真实活动，合并成功后更新已保存发现数。
  不输出模型内部思考，不增加模型调用，不改变并发限制与版本合并规则。
- `FinancialProgressPanel.tsx` 用于左侧 `ManusLeftPanel`，显示阶段、最新进度及本阶段用时。
  工具调用详情可展开，默认展示四阶段。报告生成后若还在整理回复，说明可以先查看报告。
  已结束的历史不运行计时器。
- 右侧 `ManusRightPanel` 使用正常对话已有的工具参数和输出布局，恢复按步骤查看执行详情。
  `financial.execution` 在工具实际开始时登记当前步骤；`financial_execution.py` 将提取科目、
  生成/校验/修正状态及已校验发现转换为标准 `step.chunk` 输出。
  20 秒未收到新进展时补一条明确的等待反馈，不伪造进度或新增模型调用。
  所有中间观察归入当前工具的同一份历史记录，工具完成后合并实际输出，不新增重复步骤。
  已校验发现标记为待最终复核；失败草稿不进入输出。
- 右侧新输出会在用户处于底部时跟随滚动；用户向上阅读时保持位置。
  保留内嵌报告、来源及重做入口；切换步骤或会话按已有消息/步骤 ID 隔离内容。

## 验证

针对性后端测试 41 项通过：包括长时间等待模型时事件已经发出、固定阶段、校验反馈、
复核、部分发布、重做、中断、等待反馈、同一步骤的历史合并及原有并发/工具测试。
Ruff 与 diff 空白检查通过。

隔离 Chromium 测试加载真实左右聊天面板，使用后端正式进度/执行记录组件产生的事件夹具，
覆盖左侧固定阶段、右侧工具输入和增量输出、等待反馈、步骤切换、持久化历史恢复、普通
工具输出隔离及滚动跟随。截图经人工查看。与本功能无关的图表、轨迹、报告加载依赖在
浏览器夹具中替换为桩，夹具自行分发标准步骤事件，未启动完整首页；本次不是新的真实
模型端到端/导出验收。

TypeScript 对照检查无新增诊断，项目仍有 138 条既有诊断，不宣称整个前端类型检查通过。
没有调用真实模型或改写日常数据库，没有重启日常服务、提交 Git。

复现浏览器检查（依赖当前工作区已有 Playwright）：

```powershell
.venv/Scripts/python.exe standalone/financial-analysis/progress-fixture.py .work/financial-analysis/progress-wire.json
node standalone/financial-analysis/build.cjs .work/financial-analysis/progress-preview.html --progress-preview
node standalone/financial-analysis/test-progress-browser.cjs .work/financial-analysis/speed-layout/browser/node_modules/playwright-core .work/financial-analysis/progress-preview.html .work/financial-analysis/progress-visual .work/financial-analysis/progress-wire.json
```

## 使用

重启后端加载新的进度事件；前端开发模式刷新页面，生产模式需要重新构建并重启前端。
新建一次财报分析即可看到四阶段和实时反馈。旧聊天记录没有这些阶段元数据，仍按旧格式
显示；本次不迁移旧历史，也不重写旧报告。
