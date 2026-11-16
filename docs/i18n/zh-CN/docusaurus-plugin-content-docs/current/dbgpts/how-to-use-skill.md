# How to Use Skill

## 基本使用流程

在实际使用中，skill 往往遵循下面的模式：

1. 先识别当前任务适合哪个 skill。
2. 加载该 skill 的说明和指令。
3. 按照 skill 定义的工作流执行。
4. 调用 skill 所需的内置工具。
5. 返回最终结果，或者渲染最终报告。

## 常见工具链路

根据 skill 类型不同，执行路径通常类似这样：

- `load_skill` → 加载 skill 指令
- `sql_query` → 在需要时获取结构化数据
- `code_interpreter` → 计算指标、转换数据、生成图表
- `shell_interpreter` → 在需要时执行 shell 命令
- `html_interpreter` → 渲染最终 HTML 报告或页面

## 示例场景

### 财报分析

智能体可以：

1. 加载 financial-report skill
2. 执行需要的数据提取与分析步骤
3. 生成图表与指标结果
4. 使用 `html_interpreter` 渲染最终报告

![财报分析 Skill 示例](/img/skill/use_financial_report_analysis_skill_zh.png)

### CSV / Excel 分析

智能体可以：

1. 加载一个数据分析 skill
2. 检查上传文件
3. 使用 Python 分析计算指标并可视化结果
4. 如果需要，再将结果渲染为报告

![CSV 数据分析 Skill 示例](/img/skill/use_csv_data_skill_zh.png)


## 最佳实践

- 当工作流需要可重复时，优先使用 skill
- 严格遵循 skill 中定义的指令
- 优先使用 skill 指定的工具，而不是临时替代方案
- 当 skill 产出网页或报告时，优先使用 `html_interpreter` 做最终渲染

## 相关阅读

- [dbgpts Introduction](./introduction.md)
- [Tools Overview](../agents/introduction/tools.md)
- [Built-in tools](../agents/modules/resource/tools.md)
