# Multi-file upload samples

`optional_checks.cjs` uses these four small, synthetic inputs. The source is the
historical manual-acceptance input set dated 2026-09-07. No database or service is
needed to inspect them. The acceptance script itself requires a running isolated
application and can create test assets.

- `customers.csv`: three customers, unique customer_id and region.
- `orders.csv`: four orders, each referencing one customer.
- `order_items.csv`: five lines, linked by order_id; line_no is unique per order.
- `not-a-table.txt`: the negative input for rejecting an unsupported table file.

Sum quantity × unit_price after joining the three tables: **1500**. Monthly totals
are 2024-01=250, 2024-02=1100, 2024-03=150. Regional totals are 华东=350, 华南=1000,
华北=150. These invariants catch missing inputs and accidental join multiplication.

[manifest.json](manifest.json) records file hashes. The repository material checker
verifies both hashes and the independent join totals. These are fixture checks,
not evidence that the upload browser workflow has run.
