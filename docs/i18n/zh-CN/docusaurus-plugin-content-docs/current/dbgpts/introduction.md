# Skills 总览

> 本页对 skill 的定义参考了 [Agent Skills](https://agentskills.io/what-are-skills) 的描述：skill 是一种轻量、自包含的能力包，智能体可以按需发现、加载并执行。

## 什么是 skill？

在 DB-GPT 中，skill 是一种可复用的能力包，为智能体提供完成某类任务的结构化方式。

相比只依赖自由推理，skill 为特定类型的工作提供了更稳定、更可重复的执行模式。

<img
  src="/img/skill/skill_list_zh.png"
  alt="DB-GPT 技能总览"
  className="showcase-hero-image"
/>

## Skill 的定义

结合 Agent Skills 的定义，可以把 skill 理解为：

- 一种为智能体提供专业知识和工作流的**轻量扩展格式**
- 一种**经验与方法的打包形式**，而不只是事实、API 或 prompt
- 一种**渐进式暴露**的能力单元：先发现，真正需要时再完整加载
- 一个自包含的指令、脚本、模板和参考资料集合
- 一种让智能体行为更**稳定、可重复、具备领域感知**的方式

在 DB-GPT 语境里，skill 不只是“模型知道什么”，而是一个打包好的工作流，帮助智能体决定：

- 它要解决什么问题
- 它应该调用哪些工具
- 执行步骤应遵循怎样的顺序
- 需要产出什么结果
- 需要遵守哪些约束

## 一个 skill 通常包含什么

一个 DB-GPT skill 包通常包括：

- 名称
- `SKILL.md` 中的说明与指令
- 可选脚本
- 可选模板
- 可选静态资源或示例

从本质上说，skill 是一个包含 `SKILL.md` 的目录。这个文件定义元数据与执行指令，告诉智能体如何完成某类任务。skill 还可以附带脚本、模板和参考资料。

```text
my-skill/
├── SKILL.md          # Required: instructions + metadata
├── scripts/          # Optional: executable code
├── references/       # Optional: documentation loaded as needed
└── assets/           # Optional: templates, output resources, static files
```

## Skill 结构

按照 DB-GPT 当前 skill-creator 的实践，一个 skill 通常组织为一个小型、自包含的能力包：

| 部分 | 必需 | 作用 |
|------|------|------|
| `SKILL.md` | 是 | 定义 skill 的身份信息与执行指令 |
| `scripts/` | 否 | 存放可执行代码，如 Python 或 shell 辅助脚本 |
| `references/` | 否 | 存放按需加载进上下文的参考文档 |
| `assets/` | 否 | 存放模板、字体、图标、样板文件或其他输出资源 |

### `SKILL.md`

`SKILL.md` 是 skill 的入口文件，通常包含：

- `name`、`description` 等元数据
- 智能体应遵循的工作流指令
- 什么时候读取附加参考资料或使用打包资源的说明

### `scripts/`

`scripts/` 用于放置可执行辅助程序，例如：

- Python 数据处理脚本
- shell 脚本
- 报告生成辅助代码
- skill 运行中需要的自动化代码

### `references/`

`references/` 用于保存不适合一直塞进 `SKILL.md` 的补充知识，例如：

- API 文档
- 业务逻辑说明
- schema 定义
- 工作流指南
- 领域规范或策略文档

这样既能保持 `SKILL.md` 精简，又能在需要时为智能体提供更深的上下文。

### `assets/`

`assets/` 用于存放更多面向输出而不是推理过程的资源，例如：

- HTML 模板
- 图标与 logo
- 字体
- 前端样板文件
- 报告资源

## 为什么 skill 很重要

在以下场景中，skill 很有价值：

- 工作流需要标准化
- 任务需要领域化推理
- 报告或分析需要遵循固定模式
- 希望智能体优先使用整理好的指令，而不是完全临场发挥

## Skill 如何工作

常见执行流程如下：

1. 智能体识别当前任务适合某个 skill。
2. 加载该 skill 的指令。
3. 按照 skill 定义的工作流执行。
4. 调用所需工具。
5. 返回最终答案、报告或页面。

## Skill 与内置工具

skill 经常会编排多个内置执行工具一起工作：

- `load_skill` → 加载 skill 指令
- `sql_query` → 按需获取结构化数据
- `code_interpreter` → 计算指标、转换数据、生成图表
- `shell_interpreter` → 在需要时执行 shell 命令
- `html_interpreter` → 渲染最终报告或网页

## 实际示例

### 财报分析

一个财报分析 skill 可以定义：

- 如何检查上传的财报
- 如何计算指标并进行期间对比
- 如何生成图表与摘要
- 如何渲染最终 HTML 报告

### CSV / Excel 分析

一个数据分析 skill 可以定义：

- 如何检查数据集
- 如何计算核心指标
- 如何可视化结果
- 如何把结果整理成可复用报告

## 最佳实践

- 当工作流需要可重复时，优先使用 skill
- 严格遵循 skill 中定义的指令
- 优先使用 skill 指定的工具，而不是临时替代方案
- 当 skill 产出网页或报告时，优先使用 `html_interpreter` 做最终渲染

## 下一步

想看具体使用方式，请继续阅读 [How to Use Skill](./how-to-use-skill.md)。
