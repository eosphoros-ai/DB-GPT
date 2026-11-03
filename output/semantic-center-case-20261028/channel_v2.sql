WITH eligible AS (SELECT * FROM orders WHERE tenant_id=1 AND is_test=0
AND is_deleted=0 AND status IN ('PAID','COMPLETED')),
paid AS (
 SELECT p.order_id, SUM(p.amount_cents) AS cents FROM payments p
 WHERE p.status='SUCCESS'
 AND p.paid_at >= '2026-01-01' AND p.paid_at < '2026-02-01'
 GROUP BY p.order_id
), returned AS (
 SELECT r.order_id, SUM(r.amount_cents-r.freight_cents) AS cents FROM refunds r
 WHERE r.status='SUCCESS'
 AND r.refunded_at >= '2026-01-01' AND r.refunded_at < '2026-02-01'
 GROUP BY r.order_id
)
SELECT c.channel_name, SUM(
 CASE WHEN p.order_id IS NOT NULL THEN p.cents-o.freight_cents ELSE 0 END
 -COALESCE(r.cents,0)) AS net_cents
FROM eligible o JOIN channels c ON c.channel_id=o.channel_id
LEFT JOIN paid p ON p.order_id=o.order_id
LEFT JOIN returned r ON r.order_id=o.order_id
GROUP BY c.channel_id, c.channel_name ORDER BY c.channel_id;
