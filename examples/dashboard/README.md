# Agent Dashboard v1 reproducible demos

Both demos use the same Schema v1 renderer, editor, API, and publishing path.
Only the data source and JSON schema change.

## Build the SQLite databases

```powershell
python examples/dashboard/build_demo_databases.py
```

The command writes generated databases to `examples/dashboard/generated/`:

- `walmart_sales_demo.db` — deterministic synthetic retail data with a
  Walmart-compatible store/week shape. It is clearly marked as synthetic and is
  intended for functional demonstrations, not business conclusions.
- `apple_financial_demo.db` — a small, redistributable extraction of Apple fiscal
  2022–2024 figures from SEC Form 10-K filings. Values are in USD millions and
  source URLs are stored in the database and in `sources/apple-sec-sources.json`.

## Load and demonstrate

1. Add one SQLite data source for each generated database in DB-GPT.
2. Name them `walmart_sales_demo` and `apple_financial_demo`, matching the
   `data_source_id` values in the example schemas.
3. Create a dashboard from the matching JSON schema through
   `POST /api/v1/dashboards`, or ask the Data Assistant to generate the same
   business view and compare the generated draft with the deterministic schema.
4. Change filters, refresh, drag/resize widgets, save, reload, publish, then open
   the anonymous share URL.

The JSON schemas intentionally cover KPI, line, bar, pie, table, date range,
single-select, and multi-select behavior.

## 可选参考数据

以下脚本由演示者按需手动运行，不参与服务启动、前端打包或数据库结构升级。
`install_reference_sources.py` 下载校验过的 UCI 数据并生成 SQLite 文件；
`install_research_sources.py` 准备研究布局示例；`install_showcase_sources.py` 生成合成展示数据。
已有自己的数据源时无需运行这些脚本。

```sh
python examples/dashboard/install_reference_sources.py --sources energy students
```

默认只生成本地文件。需要注册到自己的后端时，显式传入 `--register --api-base`，
或在数据源页面添加生成的数据库。来源和许可证见
`data/dashboard_reference_sources/manifest.json`；其他两个脚本的来源说明写在文件开头。
后端启用了 API Key 时，在运行脚本的进程环境中设置 `DBGPT_API_KEY`；
三个注册脚本都会使用 Bearer 认证，不会将密钥写入数据或清单。
