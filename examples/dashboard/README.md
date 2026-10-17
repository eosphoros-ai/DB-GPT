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
最小演示只需上面的 `build_demo_databases.py`，无需安装以下可选数据。
三个入口分别对应不同的模板和数据转换，保留独立入口以兼容现有演示命令：

| 脚本 | 对应演示与数据源 |
|---|---|
| `install_reference_sources.py` | IT 工单、能源、设备维护、学生表现模板；分别生成 `sqlite_itsm`、`sqlite_energy`、`sqlite_maintenance`、`sqlite_students`，支持 `--sources` 只选需要的数据。 |
| `install_research_sources.py` | “趋势洞察 · 健康研究总览”和“数据脉搏 · 健康分析长报告”共用 Cleveland 数据；“AI 语音趋势实验室”使用合成语音数据。对应 `sqlite_heart_cleveland`、`sqlite_voice_lab`。 |
| `install_showcase_sources.py` | “门店营销沙盘”“全国经营指挥大屏”“互联网医疗服务大屏”“乡村普惠金融大屏”，分别生成对应的 `sqlite_*_showcase` 合成数据。 |

已有自己的数据源时无需运行这些脚本；数据来源与获取地址见下文。

```sh
python examples/dashboard/install_reference_sources.py --sources energy students
```

默认只生成本地文件。需要注册到自己的后端时，显式传入 `--register --api-base`，
或在数据源页面添加生成的数据库。默认输出统一放在已忽略的
`examples/dashboard/generated/` 下的 `reference-sources/`、`research-sources/`
和 `showcase-sources/` 中；下载缓存及生成的 manifest 也保留在对应目录。
后端启用了 API Key 时，在运行脚本的进程环境中设置 `DBGPT_API_KEY`；
三个注册脚本都会使用 Bearer 认证，不会将密钥写入数据或清单。

## 参考数据的来源与许可证

UCI 压缩包按 SHA-256 校验，原始行数与转换后行数也必须匹配；脚本中的固定值用于离线复现和防止下载内容变化。

| 数据 | DOI / 来源 | 许可证 | 原始行数 → 输出行数 |
|---|---|---|---|
| `itsm` | [DOI](https://doi.org/10.24432/C57S4H) · [UCI 下载](https://archive.ics.uci.edu/static/public/498/incident+management+process+enriched+event+log.zip) | CC BY 4.0 | 141712 → 24918 |
| `energy` | [DOI](https://doi.org/10.24432/C5VC8G) · [UCI 下载](https://archive.ics.uci.edu/static/public/374/appliances+energy+prediction.zip) | CC BY 4.0 | 19735 → 19735 |
| `maintenance` | [DOI](https://doi.org/10.24432/C5HS5C) · [UCI 下载](https://archive.ics.uci.edu/static/public/601/ai4i+2020+predictive+maintenance+dataset.zip) | CC BY 4.0 | 10000 → 10000 |
| `students` | [DOI](https://doi.org/10.24432/C5TG7T) · [UCI 下载](https://archive.ics.uci.edu/static/public/320/student+performance.zip) | CC BY 4.0 | 649 → 649 |

- **itsm**：按工单编号取最后一次更新；解决耗时=(resolved_at-opened_at)/3600，缺失或负时长不计平均。SLA 仅展示源 made_sla 为 True 的比例，不自行推断 SLA 阈值。
  压缩包 SHA-256：`6294e29a311647306bfdfc85783f7df66517c197b9cd49aa5ee36ba9c525d1d6`。

- **energy**：比利时一栋实验住宅，2016 年每 10 分钟采样；Appliances 与 lights 为 Wh，分别除以 1000 后汇总为 kWh。最后一天为部分采样日。
  压缩包 SHA-256：`2fccf354445d886e7917620b0195db1f3e3e34d5a067a93b844694a4c561255a`。

- **maintenance**：AI4I 2020 为 UCI 提供的合成工业数据，非真实生产记录。样本组按 UDI 每 1000 条划分，不能解释为时间趋势。故障比例按 Machine failure=1 统计。
  压缩包 SHA-256：`f601f14294bcf190f9d720676b7f0aea46a26cde9ab8ebc7b4f8174d9d26b252`。

- **students**：只使用两所葡萄牙中学的葡语课程数据，每行一名学生，避免与数学课程重复计人。成绩范围 0–20，达标线定义为 >=10；缺课按原始 absences 计。数据没有逐日日期。
  压缩包 SHA-256：`82ae9d66437b9808df42e8c89d2bb179c46e9cfbcf06f38abc1d20b3b747e177`。

研究示例中的 Cleveland 心脏病数据来自 Janosi、Steinbrunn、Pfisterer 与 Detrano（1989），[UCI Heart Disease，DOI:10.24432/C52P4X](https://doi.org/10.24432/C52P4X)，许可为 CC BY 4.0；下载地址为 [UCI 压缩包](https://archive.ics.uci.edu/static/public/45/heart%2Bdisease.zip)。语音研究数据及四个展示模板的数据由固定随机种子合成，不代表真实用户、临床结论或市场预测。
