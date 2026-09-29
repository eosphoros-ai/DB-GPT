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
