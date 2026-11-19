-- Invented CNY transactions. Integer amounts are cents; timestamps are UTC+08.
PRAGMA foreign_keys = ON;
CREATE TABLE channels (
    channel_id INTEGER PRIMARY KEY, channel_name TEXT NOT NULL
);
CREATE TABLE products (
    product_id INTEGER PRIMARY KEY, product_name TEXT NOT NULL, category TEXT NOT NULL
);
CREATE TABLE orders (
    order_id INTEGER PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL REFERENCES channels(channel_id),
    status TEXT NOT NULL,
    is_test INTEGER NOT NULL,
    is_deleted INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    freight_cents INTEGER NOT NULL
);
CREATE TABLE order_items (
    item_id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(order_id),
    product_id INTEGER NOT NULL REFERENCES products(product_id),
    quantity INTEGER NOT NULL,
    goods_cents INTEGER NOT NULL
);
CREATE TABLE payments (
    payment_id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(order_id),
    status TEXT NOT NULL,
    paid_at TEXT NOT NULL,
    amount_cents INTEGER NOT NULL
);
CREATE TABLE refunds (
    refund_id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(order_id),
    status TEXT NOT NULL,
    refunded_at TEXT NOT NULL,
    amount_cents INTEGER NOT NULL,
    freight_cents INTEGER NOT NULL
);
INSERT INTO channels VALUES (1, '自然渠道'), (2, '广告渠道');
INSERT INTO products VALUES (1, '模拟咖啡', '食品'), (2, '模拟杯子', '日用品');
INSERT INTO orders VALUES
 (1,1,1,'COMPLETED',0,0,'2026-01-05',1000),
 (2,1,2,'COMPLETED',0,0,'2026-01-10',2000),
 (3,1,1,'COMPLETED',0,0,'2025-12-30',0),
 (4,1,1,'PAID',0,0,'2026-01-31',0),
 (5,1,1,'PAID',1,0,'2026-01-05',0),
 (6,2,1,'PAID',0,0,'2026-01-05',0),
 (7,1,1,'PAID',0,1,'2026-01-05',0),
 (8,1,1,'CANCELED',0,0,'2026-01-05',0),
 (9,1,2,'PENDING',0,0,'2026-01-05',0),
 (10,1,2,'PAID',0,0,'2026-01-20',300);
INSERT INTO order_items VALUES
 (1,1,1,1,6000), (2,1,2,2,4000), (3,2,1,2,20000),
 (4,3,1,1,5000), (5,4,2,1,7000), (6,5,1,1,99900),
 (7,6,1,1,88800), (8,7,1,1,77700), (9,8,1,1,66600),
 (10,9,1,1,999), (11,10,2,1,3000);
INSERT INTO payments VALUES
 (1,1,'SUCCESS','2026-01-05',6000), (2,1,'SUCCESS','2026-01-06',5000),
 (3,2,'SUCCESS','2026-01-10',22000), (4,3,'SUCCESS','2026-01-02',5000),
 (5,4,'SUCCESS','2026-02-01',7000), (6,5,'SUCCESS','2026-01-05',99900),
 (7,6,'SUCCESS','2026-01-05',88800), (8,7,'SUCCESS','2026-01-05',77700),
 (9,8,'SUCCESS','2026-01-05',66600), (10,9,'FAILED','2026-01-05',999),
 (11,10,'SUCCESS','2026-01-20',3300);
INSERT INTO refunds VALUES
 (1,1,'SUCCESS','2026-01-15',1000,100),
 (2,1,'SUCCESS','2026-01-16',500,0),
 (3,1,'SUCCESS','2026-02-02',500,0),
 (4,2,'SUCCESS','2026-01-20',2000,200),
 (5,3,'SUCCESS','2026-01-03',1000,0),
 (6,2,'FAILED','2026-01-22',9000,0);
-- Actual SQL view lineage, not an inferred ETL pipeline.
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
