# DB 智能分析双 Agent 并行实现

2026-11-01

中英文内置模板现采用：

```text
语义口径接地 → 分析计划 ┬→ 趋势与贡献分析 ─┐
                      └→ 数据质量检查 ───┤
                                       汇总与数字复核 → HTML 报告 → 输出
```

两个分支使用 `parallel_group: "db_analysis"`，并共享已确定的数据源、指标发布版本、引用和分析范围。复核节点等待两分支完成后才执行。

模板不再固定 Walmart_Sales。打开编辑器后，在顶栏“流程数据源”选择数据库，会统一绑定五个查询节点。未选择数据库时可保存草稿，试运行前必须补齐配置。已有工作流保留原定义；要使用新结构，请从新的 DB 智能分析模板创建。

实现包括：

- 编译器仅传递声明图中的祖先产出，不再把两个兄弟 Agent 连成串行依赖。
- 执行器运行同组就绪 Agent，最多两个；独立任务上下文共享工作流结果与锁，共同祖先执行一次。
- 分支失败或用户取消时取消同批其他任务，禁止继续生成汇总报告。未分组流程保持原来的串行行为。
- 接入四个语义读取工具，只允许绑定单个已选数据源；两个并行 Agent 的数据源范围必须一致。
- 修正 `code` 工具名称，移除不存在的强制技能依赖。模板要求沿用指标指定发布版本，口径或范围不明确时返回澄清项。
- 编辑器按拓扑阶段排列分支，显示“并行”标记和分组字段；Agent 开始执行立即发送状态，工具轨迹和完成结果按节点 ID 归属。
- Agent 未单独配置模型时使用试运行选择的模型；模型连接、鉴权或计费错误明确失败。每个 Agent 使用独立起止时间，避免第二个并行分支被误计为 0ms。
- 保存与对话修改支持显式双 Agent 分组及汇合结构，禁止依赖彼此的 Agent 被配置为同组。

验证：

- 93 项专项及兼容性测试通过：实际编译模板执行、两个 Agent 同时进入、祖先仅执行一次、完整汇合、共享证据传递、上下文隔离、并发上限、失败取消、用户取消、原串行 DAG、语义工具、草稿与保存校验、模型选择传递和连接错误判定。
- 追加 Agent 类型和取消处理后，14 项并行/事件标记测试通过。
- 最终模型传递与计时修正后，7 项既有事件标记测试通过。
- 前端构建、修改文件 ESLint、Python Ruff 通过，分支布局测试通过。
- 浏览器实际打开内置模板，确认两分支同层、汇总位于下一层，选择 Semantic_Commerce_Case 后五个节点数据源一致，成功保存未发布草稿，无页面错误。

测试范围：并行 Agent 测试使用受控模型响应，真实运行编译器、执行器、Agent Operator 和事件队列，证明调度和结果归属；不能替代真实模型分析正确性验收。真实试运行发现未指定模型的节点曾使用默认模型，并将 `LLM_PROVIDER_ERROR: Connection refused` 误报为成功。本轮已修正模型传递与错误状态，并增加回归测试；连接错误文本不属于成功分析结果。当前 DeepSeek 服务还出现 HTTP 402 `Insufficient Balance`，因此真实模型成功端到端分析仍受模型服务限制。

修正后的真实 DeepSeek 复测在约 31 秒后返回 `agent node failed: model provider error`，明确报告 HTTP 402 余额不足，未继续执行分析和报告节点。

浏览器验收草稿（未发布，已绑定既有合成样例数据库）：http://localhost:3000/taskflow/editor?id=bbbf5008-446c-4aea-a896-bb04aae1a921

已知原有测试：`test_agent_runner.py::TestRobustFinalAnswer::test_unparseable_envelope_falls_back_to_stripped` 与现有子 Agent 结果过滤策略冲突，本轮未修改该策略；上述 93 项命令排除了该测试。旧 `test_taskflow.py` 的若干测试仍引用已删除的模板，本轮新测试直接覆盖实际 DB 模板。

主要测试文件：

- `packages/dbgpt-core/src/dbgpt/core/awel/tests/test_parallel_groups.py`
- `packages/dbgpt-serve/src/dbgpt_serve/flow/tests/test_taskflow_parallel.py`
- `packages/dbgpt-serve/src/dbgpt_serve/flow/tests/test_generation.py`
- `packages/dbgpt-app/src/dbgpt_app/tests/test_agent_runner.py`
- `web/utils/taskflow-layout.test.ts`
