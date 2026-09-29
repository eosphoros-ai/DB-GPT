# 模板与浏览器验收

在项目根目录使用现有 Python 环境，将各 `packages/*/src` 加入 `PYTHONPATH` 后运行：

```powershell
python scripts/dashboard/verify_template_catalog.py --environment formal
```

该脚本在本机正式后端 5671 上检查模板。默认 `candidate` 对应隔离后端 5672。它会创建已保存的示例看板，执行真实 SQL，并验证保存重开、年份和业务维度筛选；不调用模型，不修改来源数据。已有相同环境的成功证据直接复用。同一证据目录中，每模板累计最多两次尝试；本轮九个模板的额度均已使用完毕。

生产浏览器回归从 `web` 目录运行：

```powershell
npm run test:layout -- --base-url=http://127.0.0.1:5680 --scope=all
```

范围为 129 个基线用例和 27 个新增用例，使用受控 API 回放，不调用真实模型。每次输出新时间戳目录，可用 `--scope=historical / layout / feedback / workspace` 定向执行。对通过数量的表述必须依据每批实际报告，不能把分批结果拼成一次通过。

自有数据源的真实浏览器记录、原始执行脚本与两份明确标记为合成的 SQLite 验收数据保存在 `docs/dashboard/evidence/v9-4-template-workspace-20260908/`。`source-fixtures/actual-source-identifiers.json` 解释请求名称与实际登记标识的差异。归档脚本是当次运行记录，其中的端口、临时路径和已存在的资产 ID 需按新环境配置后才可重用。
