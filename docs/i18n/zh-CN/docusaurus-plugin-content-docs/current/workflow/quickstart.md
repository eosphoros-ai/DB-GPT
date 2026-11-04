# 快速开始：创建并运行工作流

十分钟，从内置模板到一个属于自己的工作流。

## 1. 选一个模板

打开 **Task Flow → 内置模板**。每张卡片直接展示节点链；**运行**在对话里启动它，
**编辑副本**把它作为你自己的 flow 打开到编辑器。

![内置模板中心](/img/workflow/zh/fig-01-template-center.png)

当前内置集覆盖 DB 领域：

- **DB 数据库答疑**——模式接地 → 带来源引用的答案；
- **DB 数据取数**——接地/查询规划 → SQL 取数（报错自修复）→ 校验与口径说明；
- **DB 智能分析**——接地 → 分析计划 → 透视分析 → 数字复核 → HTML 分析报告。

## 2. 在对话里运行

也可以从聊天输入框发起：打开附件菜单选择工作流，输入问题发送。被选中的工作流以 chip 形式
显示在输入框上方。

![输入框选中工作流](/img/workflow/zh/fig-02-flow-composer.png)

运行卡**第一帧就给出完整节点链**——DAG 还没跑到的节点以虚线"待执行"chip 展示，计划全程
可见：

![带待执行节点的节点链](/img/workflow/zh/fig-03-run-pending.png)

## 3. 读结果

运行结束后，每张节点卡带着自己的轨迹与产出。报告节点会把 HTML 登记为产物 chip——点文件名
在右栏预览交互报告，点下载图标保存文件。

![完成态运行卡与产物 chips](/img/workflow/zh/fig-04-run-complete.png)
![右栏 HTML 报告预览](/img/workflow/zh/fig-05-html-preview.png)

## 4. 改成自己的

**编辑副本**在编辑器里打开模板节点：改目标、换工具、换数据源、增删节点，然后**保存并部署**。

:::warning
编辑器保存后 flow 处于 `developing`（未部署）状态，对话只认 `running` 的 flow——改完必须
部署，否则对话会报 *dag not found*。见[故障排查](./troubleshooting.md)。
:::

## 5. 复用

部署后的 flow 出现在 **My Flows** 与聊天附件菜单。内置模板首次在对话中运行时会实例化为你的
flow；你的修改永远不会污染模板本身。

下一步：[编辑器](./editor.md) · [节点参考](./nodes/overview.md)
