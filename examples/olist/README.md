# Olist report and evidence case

This example uses the
[Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
to exercise DB-GPT's report and evidence flow against a realistic relational
datasource.

The public dataset contains anonymized Brazilian marketplace orders and is
licensed under CC BY-NC-SA 4.0. Do not redistribute the source files from this
repository; download them from Kaggle and preserve the attribution and license.

## Offline example

The home-page example works without downloading Olist data. Like the bundled
Walmart database, `pilot/examples/Olist_Ecommerce.db` is included in source and
the application package, provisioned into the workspace, and registered on
startup. An existing `Olist_Ecommerce` datasource is preserved.

This small database contains **synthetic observations, not real Olist
transactions**, under the project's MIT license. It preserves the nine source
table shapes and includes canceled orders, multiple items and payments, missing
reviews, repeat customers, states, categories and delivery delays. Report
conclusions describe this demonstration only. `dataset_metadata` records its
origin; `metric_definitions` also contains the governing document. The same
document, `examples/olist/olist-analytics-metric-governance.md`, is bundled in
the application package. Clicking the card prepares the
`Olist_Analytics_Governance` knowledge space with the configured embedding
service and waits for indexing before sending the question, datasource and
knowledge space name/ID together. Subsequent clicks reuse the indexed knowledge;
existing spaces and documents are preserved. A failed or unfinished index blocks
the example instead of silently sending a question without its knowledge.
The database and document are available offline; first-use vector indexing and
analysis still require the configured model services.

Regenerate the business data deterministically with the existing CSV importer:

```bash
python examples/olist/build_demo.py
```

Business rows and source CSV hashes are reproducible; import timestamps record
each actual build. To use real Olist data instead, follow the steps below and
register your imported database. The card uses that existing datasource rather
than overwriting it with the demonstration.

## Prepare the full real datasource

The downloaded CSV files and generated database live under `pilot/data/`, which
is already excluded from Git.

```bash
mkdir -p pilot/data/olist/csv
curl -L --fail \
  -o pilot/data/olist/olist.zip \
  https://www.kaggle.com/api/v1/datasets/download/olistbr/brazilian-ecommerce
python -m zipfile -e pilot/data/olist/olist.zip pilot/data/olist/csv
python examples/olist/build_olist_sqlite.py \
  --csv-dir pilot/data/olist/csv \
  --output pilot/data/olist/olist.db
```

The archive downloaded on 2026-08-29 had this SHA-256 digest:

```text
967e41e04fc306fe604e2a693f488995a8b41e5047418f8a5c8e4abd6deca784
```

Kaggle may publish a new dataset version later. The importer therefore stores
the row count and SHA-256 digest of every imported CSV in
`_olist_import_manifest`; that manifest, rather than the archive digest above,
is the evidence for a particular local datasource build.

Add `pilot/data/olist/olist.db` as a SQLite datasource in DB-GPT. The importer
preserves the nine source relations and adds indexes only on common join keys.
It does not create a denormalized table or precompute the expected answers.

## Case question

Use the complete-month comparison period from 2017-01-01 through 2018-08-31:

> 请基于 Olist 电商数据库生成一份经营与履约诊断报告。只统计已交付订单，分析
> 2017-01-01 至 2018-08-31 的 GMV、订单量、客单价、运费占比和月度趋势；比较
> 主要商品品类及客户所在州的表现；分析配送时长、逾期交付与客户评分之间的关系；
> 分析支付方式和分期情况；最后给出三条可执行的经营建议。每个指标、图表和结论
> 都必须绑定其 SQL、输入表、结果摘要及上游证据，不能把模型推断写成数据库事实。

This single question is intended to produce:

- metric blocks for GMV, delivered orders, average order value, freight ratio,
  average review score, and late-delivery rate;
- chart blocks for monthly trend, category/state performance, delivery versus
  review score, and payment composition;
- table blocks for ranked categories, states, and operational exceptions;
- insight/text blocks whose evidence resolves to the SQL and result artifacts;
- an immutable report revision that can be opened from the chat response and
  exported through DB-GPT's existing PDF path.

## Reproducibility baseline

For the Kaggle version last updated on 2021-10-01, the importer produced
1,550,922 rows:

| Table | Rows |
| --- | ---: |
| `customers` | 99,441 |
| `geolocation` | 1,000,163 |
| `order_items` | 112,650 |
| `order_payments` | 103,886 |
| `order_reviews` | 99,224 |
| `orders` | 99,441 |
| `product_category_translation` | 71 |
| `products` | 32,951 |
| `sellers` | 3,095 |

The following values are validation anchors, not report fixtures. They use
delivered orders purchased at or after 2017-01-01 and before 2018-09-01:

| Metric | Expected value |
| --- | ---: |
| Delivered orders | 96,211 |
| GMV (`SUM(order_items.price)`) | 13,181,027.13 |
| Average order value | 137.00 |
| Freight value | 2,192,092.88 |
| Freight / GMV | 16.63% |
| Average delivery duration | 12.54 days |
| Late-delivery rate | 8.13% |
| Average review score | 4.16 |

These anchors should be rechecked whenever the source manifest changes. A
report must still retain the executed SQL and result artifacts; matching these
numbers alone is not evidence provenance.
