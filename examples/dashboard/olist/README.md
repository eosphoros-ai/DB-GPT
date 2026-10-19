# Olist multi-table Dashboard case

This case exercises the teacher-requested path that a single flat Walmart table
cannot prove:

```text
multiple related CSV files
  -> one relational data source
  -> natural-language Dashboard planning
  -> joins across orders, customers, items, products, payments and reviews
  -> the same verified answers on SQLite and MySQL
```

## Source and license

The raw data is the **Brazilian E-Commerce Public Dataset by Olist** from Kaggle.
It contains roughly 100,000 anonymized orders from 2016–2018.  The pinned source,
version, license (`CC BY-NC-SA 4.0`), archive SHA-256, and expected file list are
recorded in `source-manifest.json`.

Raw CSV files and generated databases are deliberately excluded from Git.  This
repository contains only code, metadata, synthetic test fixtures, and verified
aggregate answers.  Commercial use would require a separate license review.

The initializer prefers the checksum-pinned Kaggle archive. If Kaggle is
temporarily unreachable, it can fetch the eight required CSVs from a
commit-pinned GitHub mirror; every fallback file has its own recorded byte size
and SHA-256 digest in `source-manifest.json`. The optional geolocation table is
never taken from that fallback.

## Reproduce

```powershell
# One command: checksum-pinned download, eight-table SQLite rebuild, gold-answer
# verification, and execution of all Dashboard widgets through DB-GPT.
python examples/dashboard/olist/initialize_olist_demo.py

# Optionally load and verify MySQL from the exact same CSV files as well.
python examples/dashboard/olist/initialize_olist_demo.py `
  --mysql-url "mysql+pymysql://USER:PASSWORD@127.0.0.1:3306/olist?charset=utf8mb4"

# The lower-level steps remain available when only one stage is needed.
python examples/dashboard/olist/download_olist.py

# SQLite
python examples/dashboard/olist/load_olist.py `
  --source-dir examples/dashboard/olist/data/raw/extracted `
  --sqlite examples/dashboard/olist/data/generated/olist.db `
  --replace

# MySQL (credentials stay in the environment/command line and are never saved)
python examples/dashboard/olist/load_olist.py `
  --source-dir examples/dashboard/olist/data/raw/extracted `
  --mysql-url "mysql+pymysql://USER:PASSWORD@127.0.0.1:3306/olist?charset=utf8mb4" `
  --replace
```

The default core load imports eight related tables.  Add
`--include-geolocation` to import the ninth, approximately one-million-row
geolocation table.

The case was reproduced on 2026-08-24 with SQLite and MySQL Community Server
8.4.11.  Both databases produced the same seven gold-query groups and executed
all six Dashboard widgets through the current DB-GPT safety/query layer.

Then verify business answers:

```powershell
python examples/dashboard/olist/verify_olist.py `
  --sqlite examples/dashboard/olist/data/generated/olist.db

# Execute all six widgets through DB-GPT's SQL safety and query layer.
python examples/dashboard/olist/verify_dashboard_schema.py `
  --sqlite examples/dashboard/olist/data/generated/olist.db
```

The Dashboard verifier also executes the exact pre-publish contract and proves
that default, single-value, multi-value, and cleared filters return the same
results from the frozen share snapshot as from the owner's live SQLite/MySQL
queries. Anonymous share requests still receive only the frozen rows.

## Business questions used for Dashboard planning

1. How many orders were created and delivered?
2. How does paid revenue change by purchase month?
3. Which translated product categories contribute the most item revenue?
4. Which customer states contribute the most orders and payments?
5. What is the average delivery time and late-delivery rate?
6. How does review score relate to delivery performance?
7. Which payment methods are used and what value do they carry?

`gold_answers.json` prevents a visually plausible Dashboard from hiding incorrect
joins.  In particular, payments and items are aggregated per order before they
are joined so that one-to-many relationships do not multiply revenue.
