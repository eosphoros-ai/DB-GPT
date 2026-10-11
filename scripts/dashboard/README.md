# Dashboard 检查脚本

## 按需生成参考数据库

四个 UCI 参考库不随仓库分发。以下命令校验固定下载哈希和记录数，
在忽略目录 `output/dashboard-reference-sources/` 生成 SQLite 文件及清单：

```sh
python scripts/dashboard/install_reference_sources.py
```

重复执行会核对已有数据库；数据不符时停止并保留原文件。下载缓存位于输出目录的
`raw/` 子目录；可用 `--cache-dir <目录> --offline` 仅使用已缓存、哈希一致的 ZIP。
`--sources energy students` 可以只生成所需数据源。

默认只生成文件。如需注册到自己的 DB-GPT 服务，显式指定：

```sh
python scripts/dashboard/install_reference_sources.py --register --api-base http://127.0.0.1:5670
```

后端必须能访问生成文件的绝对路径；已有同名数据源不会被覆盖。可用 `--output`
选择共享目录，或在数据源页面手动添加文件。来源、许可证、原始哈希和转换说明见
`data/dashboard_reference_sources/manifest.json`。图库卡片为布局示意，查询预览使用所选数据源。

当前安装、迁移与测试入口、已执行结果及跳过原因见 [PR 正文](https://github.com/eosphoros-ai/DB-GPT/pull/3278)。

## 生产浏览器回归

在 web 目录按锁文件安装依赖，构建生产前端并安装 Chromium。PowerShell 示例：

```powershell
npm ci
npm run build
npx playwright install chromium
$env:DASHBOARD_E2E_START_SERVER = '1'
$env:DASHBOARD_E2E_BASE_URL = 'http://127.0.0.1:5670'
$env:DASHBOARD_E2E_DISABLE_VIDEO = '1'
$env:DASHBOARD_E2E_LIVE_AGENT = '0'
npm run test:e2e:dashboard -- --workers=2 --retries=0
```

该配置为测试启动生产前端。固定输入套件拦截 API/SSE；两个 live 套件需要单独配置历史模型生成资产及真实后端，未配置时会明确跳过。实际计数以报告为准，不能将回放结果写成真实模型或外部数据库验证。

## 需要既有环境的历史适配器

`verify_template_catalog.py` 及同目录部分脚本保留了集成开发环境的端口、资产或证据约定。运行前须阅读脚本并配置自己的隔离服务；其中的旧模板数量、历史通过数及证据目录不代表新检出已具备这些资产。可能创建数据或看板的适配器不属于上述只读材料检查。

原集成版的 `test:layout` 命令与首页专用测试不属于拆分候选；当前浏览器入口为 `test:e2e:dashboard`。随库固定输入位于 [web/tests/dashboard-e2e/fixtures](../../web/tests/dashboard-e2e/fixtures/README.md)。
