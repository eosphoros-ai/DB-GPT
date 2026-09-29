# 测试记录入口

当前执行状态见 [验证说明](VALIDATION.md)，可执行命令见 [开发指南](DEVELOPER_GUIDE.md)。

| 材料 | 用途 |
|---|---|
| [浏览器固定输入和 manifest](../../web/tests/dashboard-e2e/fixtures/README.md) | 新检出可加载的回归输入，记录来源与 SHA-256；不是一次执行结果。 |
| [上传样例](../../scripts/acceptance/fixtures/upload-samples/README.md) | 多文件关联与拒绝非表格文件的确定性输入。 |
| [Walmart](demos/walmart.md)、[Apple](demos/apple.md) | 数据口径、核验目标和历史截图。 |
| [历史资料说明](HISTORY.md) | 旧过程记录、私人路径与未分发原始日志的边界。 |

工具链依赖的 [Ubuntu/macOS Actions](https://github.com/jcsdxhe/DB-GPT/actions/runs/36565457316) 已通过，提交为 `ae095321f2f93d1536fdead00b1484d2637b96d9`。Dashboard 的本机验证与工具链矩阵分开记录；Dashboard 自身已在提交 `cd95575f` 完成 [独立 Ubuntu/macOS Actions](https://github.com/jcsdxhe/DB-GPT/actions/runs/36565508485)，两个平台均为组件 286 项通过、浏览器 125 项通过及 7 项显式跳过，生产构建与静态导出通过。分组范围和首次 macOS EMFILE 的修复记录见 [验证说明](VALIDATION.md)。

工具链已进入 [官方 PR #3277](https://github.com/eosphoros-ai/DB-GPT/pull/3277) 评审。Dashboard 浏览器完整发现 10 套件，8 个实跑共 125 项通过、2 个 live 套件共 7 项跳过；[逐套件范围及原因](VALIDATION.md#浏览器套件覆盖)单独列示。
