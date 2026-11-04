# 分析任务刷新与恢复

开发环境通过 `127.0.0.1` 访问前端时，Next.js 的热更新连接需要列入
`allowedDevOrigins`。连接被阻止会导致开发客户端反复重连并可能整页刷新。
修改配置后须重启前端开发服务。

ReAct 对话现在会在执行开始时保存用户消息和当前轮次，并每隔至少两秒保存一次
有流式事件的进度快照。正常完成时更新同一条回答，不追加重复消息；连接断开时先
取消并等待执行任务清理，再保存中断记录。已完成步骤、附件公开元数据和已保存财报
引用会保留。恢复页面不会自动重新调用模型；用户可继续任务或重试相应专题。

恢复期间显示加载状态。尚未完成的历史步骤不会显示为已完成。
旧会话若没有对话消息，会通过受认证的 `/api/v1/financial-analysis/runs/latest`
读取当前用户、当前会话最新的已保存财报。恢复入口不补造原始提问或执行步骤，
也不修改报告的校验、复核和发布状态。

后端保存与恢复接口的修改须重启后端服务后生效。运行中的任务应先结束或停止，
再重启服务。

验证命令：

```powershell
uv run --no-sync python -m pytest packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/tests/test_react_history.py packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/tests/test_agentic_data_api_lifecycle.py packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/tests/test_financial_history_recovery.py packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/tests/test_report_persistence_publication.py packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/tests/test_react_final.py packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/tests/test_share_privacy.py -q
cd web
npx vitest run --config vitest.dashboard.config.mts new-components/financial-analysis/recover-history.test.ts
npx playwright test --config playwright.recovery.config.ts
```

浏览器测试使用隔离端口 `5688` 和模拟 API，不调用真实模型或读写日常数据库。
