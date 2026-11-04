# 什么是 Harness？

**Harness（执行引擎层）** 是驱动一轮 Agent 任务的执行运行时：它持有模型循环、工具调用、
流式轨迹与产物产出。DB-GPT 将 harness 抽象为**可插拔引擎层**——同一套对话界面、工具 containment、
审批策略与产物表面，可以由不同运行时驱动。

![Setting 弹层中的 Harness 选择](/img/harness/zh/fig-01-settings-harness.png)

## 内置引擎

| 引擎 | 说明 | 可用性 |
|---|---|---|
| **DB-GPT** | 内置 ReAct / tool-calling 循环，无外部依赖。 | 始终可用 |
| **pi** | 外部 CLI harness（`pi --mode rpc`），按会话拉起子进程；DB-GPT 将工具、模型与审批桥接进 pi 进程。 | 需要 pi CLI 与 Node ≥ 22.19 |
| **DSH** | 预留引擎位。 | coming soon |

所有引擎对产品层遵守同一契约：

- **工具**——同一套受控工具带（SQL 查询、代码/Shell 解释器、HTML 渲染、技能、知识库）；引擎无法逃逸 containment。
- **审批**——高危工具调用走同一策略引擎与同一确认 dock，与哪个引擎发起调用无关。
- **产物**——HTML 报告、取数结果集、文件以同一套一等产物卡、rail 条目与导出形式呈现。
- **历史**——回合以同一 protocol payload 持久化，刷新会话可一致地重建轨迹与产物。

## 引擎如何被选择

每轮新任务的解析顺序：

1. **请求级覆盖**——API 调用方可在 chat 请求中用 `ext_info.harness_engine` 钉死引擎。
2. **服务端偏好**——Setting 弹层持久化的值（服务端工作目录下的 `harness_engine.json`，
   经 `PUT /api/v1/chat/harness/engine` 写入）。
3. **项目默认**——新部署默认为 `pi`，且**带可用性门控**：探测不到 pi CLI 时静默回落内置
   DB-GPT 引擎，裸部署不会启动即死。

偏好只作用于**新任务**；已有会话保持其启动时的引擎，保证轨迹与历史自洽。

## 下一步

- [使用 Harness](usage.md)——选择引擎、pi 前置条件、如何读一轮运行。
- [扩展 Harness](extending.md)——新增引擎（如 DSH、Codex）的适配器契约。
