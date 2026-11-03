SELECT SUM(p.amount_cents-r.amount_cents) AS wrong_cents
FROM orders o JOIN payments p ON p.order_id=o.order_id
JOIN refunds r ON r.order_id=o.order_id
JOIN order_items i ON i.order_id=o.order_id
WHERE o.order_id=1 AND p.status='SUCCESS' AND r.status='SUCCESS'
AND p.paid_at >= '2026-01-01' AND p.paid_at < '2026-02-01'
AND r.refunded_at >= '2026-01-01' AND r.refunded_at < '2026-02-01';
