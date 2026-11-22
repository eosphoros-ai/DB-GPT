# SQL Best Practices

## Query Optimization

### Use specific columns instead of *
```sql
-- Bad
SELECT * FROM users;

-- Good
SELECT id, name, email FROM users;
```

### Add LIMIT to large result sets
```sql
SELECT * FROM large_table LIMIT 1000;
```

### Use indexes effectively
```sql
-- Create index on frequently filtered columns
CREATE INDEX idx_user_email ON users(email);

-- Query will use the index
SELECT * FROM users WHERE email = 'user@example.com';
```

### Avoid functions on indexed columns
```sql
-- Bad (index not used)
SELECT * FROM users WHERE YEAR(created_at) = 2024;

-- Good (index used)
SELECT * FROM users WHERE created_at >= '2024-01-01' 
  AND created_at < '2025-01-01';
```

## Data Integrity

### Use transactions for multi-step operations
```sql
BEGIN;
UPDATE accounts SET balance = balance - 100 WHERE id = 1;
UPDATE accounts SET balance = balance + 100 WHERE id = 2;
COMMIT;
```

### Validate before INSERT/UPDATE
```sql
-- Check existence first
INSERT INTO orders (user_id, total)
SELECT 1, 100.00
WHERE EXISTS (SELECT 1 FROM users WHERE id = 1);
```

## Security

### Use parameterized queries (prevent SQL injection)
```python
# In application code, use placeholders
# Bad: f"SELECT * FROM users WHERE name = '{user_input}'"
# Good: cursor.execute("SELECT * FROM users WHERE name = %s", (user_input,))
```

### Principle of least privilege
- Use read-only accounts for reporting queries
- Grant only necessary permissions
- Separate admin and application users

## Readability

### Use consistent formatting
```sql
SELECT 
    u.id,
    u.name,
    o.order_date,
    SUM(oi.quantity * oi.price) as total
FROM users u
JOIN orders o ON u.id = o.user_id
JOIN order_items oi ON o.id = oi.order_id
WHERE o.order_date >= '2024-01-01'
GROUP BY u.id, u.name, o.order_date
HAVING SUM(oi.quantity * oi.price) > 1000
ORDER BY total DESC
LIMIT 10;
```

### Use meaningful aliases
```sql
-- Good
SELECT u.name as user_name, p.title as product_title
FROM users u
JOIN purchases p ON u.id = p.user_id;
```

## Performance Tips

### Use EXISTS instead of IN for subqueries
```sql
-- Often faster
SELECT * FROM users u 
WHERE EXISTS (
    SELECT 1 FROM orders o 
    WHERE o.user_id = u.id 
ugsAND o.total > 1000
);
```

### Use UNION ALL instead of UNION when duplicates don't matter
```sql
-- UNION ALL is faster (no duplicate check)
SELECT name FROM employees
UNION ALL
SELECT name FROM contractors;
```

### Consider materialized views for complex aggregations
```sql
CREATE MATERIALIZED VIEW daily_sales AS
SELECT 
    DATE(order_date) as day,
    COUNT(*) as orders,
    SUM(total) as revenue
FROM orders
GROUP BY DATE(order_date);
```
