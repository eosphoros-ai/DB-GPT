SELECT SUM(signed_cents) AS net_cents FROM v_cash_events
WHERE event_at >= '2026-01-01' AND event_at < '2026-02-01';
