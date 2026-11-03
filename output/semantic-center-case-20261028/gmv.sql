WITH eligible AS (SELECT * FROM orders WHERE tenant_id=1 AND is_test=0
AND is_deleted=0 AND status IN ('PAID','COMPLETED'))
SELECT SUM(i.goods_cents) AS gmv_cents
FROM eligible o JOIN order_items i ON i.order_id=o.order_id
WHERE o.created_at >= '2026-01-01' AND o.created_at < '2026-02-01';
