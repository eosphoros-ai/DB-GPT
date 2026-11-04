# Olist report and evidence case

The homepage uses `Olist_Ecommerce`, a bundled synthetic two-table SQLite
example. The data are invented and are not real Olist transactions.
`demo_orders` contains delivered orders and `demo_items` contains item-level
category and price data. The paired knowledge document is
`olist-analytics-metric-governance.md` in `Olist_Analytics_Governance_Demo_v2`.

Rebuild the demo at a new path (the command refuses to overwrite existing files):

```bash
python examples/olist/build_demo.py --output pilot/examples/olist-rebuilt.db
```

To derive the same two-table schema from an existing full Olist SQLite database,
pass `--source` and a different `--output`; the source is opened read-only.
That output inherits the provenance and license of its source and must not be
represented as synthetic unless its source is synthetic.

The full public Olist dataset is available from Kaggle under CC BY-NC-SA 4.0.
Keep real source databases separately and register them as a different datasource.
The homepage's simplified governance definitions apply only to the two-table schema.

The two-table demo uses a versioned knowledge space so existing full-schema knowledge is preserved and cannot be reused accidentally. The example prepare endpoint indexes the bundled governance document into this space.
