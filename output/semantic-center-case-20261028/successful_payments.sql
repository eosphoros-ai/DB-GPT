WITH eligible AS (SELECT * FROM orders WHERE tenant_id=1 AND is_test=0
AND is_deleted=0 AND status IN ('PAID','COMPLETED'))
SELECT SUM(e.amount_cents) AS amount_cents FROM payments e
JOIN eligible o ON o.order_id=e.order_id WHERE e.status='SUCCESS'
AND e.paid_at >= '2026-01-01' AND e.paid_at < '2026-02-01';
