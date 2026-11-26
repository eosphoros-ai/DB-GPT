---
name: report-evidence-internal
description: Internal guidance for selecting captured report objects.
---

# 报告证据核查

供报告代理内部使用。报告中区分观测、推断与建议，相关性不能当作因果关系。

## 选择证据

- 使用 list_report_objects 读取当前会话捕获的对象。按实际业务含义选择 object_id，结合 label、preview、kind 确认来源。不得仅凭数值相同选择对象。
- 目录支持 query、kind、artifact_ids 筛选与 offset 分页。预览截断不表示数据缺失。目录中的字段名称是源数据名称，不自动证明业务口径。
- 计算值选择 value 对象，知识库口径选择 reference 对象，表格选择 table 对象，图表选择 table 或 chart 对象。
- 对象 ID 由程序登记。程序负责展开路径、读取完整结果、格式化数值、生成表格列与图表配置。
- 缺少必要的合计、差值、比例或转换结果时，使用 request_report_calculation 请求补算，再重新读取对象目录。

## 报告装配

- 使用 compose_report，严格遵循该工具的 JSON Schema。正文由普通文字与对象引用组成。统计数字通过 object_id 插入，不手写测量值。
- 选择表格或图表对象即可。禁止传入字段路径、底层产物引用、HTML、图片地址或 ECharts 配置。
- 建议目标使用独立 goal 字符串，观测依据仍用对象引用。目标不证明该效果会实现。
- 模板已有自动注入字段时，保留程序填入的真实指标。具名模板使用目录列出的模板字段。
- 模板若声明正文仅作定性解读，数值已由程序的统计区域展示，正文不得再插入数值对象或手写统计数字；解释结论与局限即可。
- 具名模板优先通过 set_report_field 逐字段提交，按 remaining_fields 补齐。字段会保存到检查点；全部提交后调用 compose_report，不必重发整份正文。
- 工具返回 invalid_selection 时，修正指定位置的对象或结构；遵循 retryable 状态。只有编译和渲染校验均通过才交付完成报告。
- 有缺失对象、未满足的分析要求或部分交付告警时如实说明。自然语言解释仍需审慎核对。
