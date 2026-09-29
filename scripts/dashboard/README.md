# Dashboard 检查脚本

当前安装、迁移与测试入口见 [开发指南](../../docs/dashboard/DEVELOPER_GUIDE.md)，已执行结果及跳过原因见 [验证说明](../../docs/dashboard/VALIDATION.md)。

## 不依赖服务的材料检查

在仓库根目录运行：

```sh
python scripts/dashboard/verify_pr_materials.py
```

检查维护文档中的本地链接、浏览器与上传样例的 manifest 和 SHA-256、上传样例关联计算，以及参考数据库的相对路径。该命令不启动服务、不下载数据，也不创建看板。

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
