CREATE VIEW v_cash_events AS
 SELECT p.payment_id AS event_id, 'payment' AS event_type, o.order_id,
        o.channel_id, p.paid_at AS event_at, p.amount_cents AS signed_cents
 FROM payments p JOIN orders o ON o.order_id=p.order_id
 WHERE p.status='SUCCESS' AND o.tenant_id=1 AND o.is_test=0
   AND o.is_deleted=0 AND o.status IN ('PAID','COMPLETED')
 UNION ALL
 SELECT r.refund_id, 'refund', o.order_id, o.channel_id,
        r.refunded_at, -r.amount_cents
 FROM refunds r JOIN orders o ON o.order_id=r.order_id
 WHERE r.status='SUCCESS' AND o.tenant_id=1 AND o.is_test=0
   AND o.is_deleted=0 AND o.status IN ('PAID','COMPLETED');
