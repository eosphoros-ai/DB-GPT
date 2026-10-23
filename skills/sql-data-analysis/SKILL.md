---
name: sql-data-analysis
description: |
  Comprehensive SQL data analysis skill for executing queries, analyzing results, 
  and generating visualizations. Use when Claude needs to: (1) Execute SQL queries against 
  databases, (2) Analyze query results and generate insights, (3) Create data visualizations 
  (charts, graphs) from query results, (4) Perform data aggregation and reporting, 
  (5) Work with database connections and query optimization. Supports MySQL, PostgreSQL, 
  SQLite, and other SQL databases.
---

# SQL Data Analysis

## Quick Start

### Execute a Query

Use the `execute_query.py` script to run SQL queries:

```bash
python scripts/execute_query.py --db-type postgresql --host localhost --port 5432 \
  --database mydb --user myuser --password mypass --query "SELECT * FROM users LIMIT 10"
```

### Generate Visualization

Use the `visualize_data.py` script to create charts from query results:

```bash
python scripts/visualize_data.py \
  --data "[{"name": "A", "value": 10}, {"name": "B", "value": 20}]" \
  --chart-type {bar|line|pie|scatter} \
  --x-column name --y-column value \
  --title "My Chart" --output chart.png
```

## Database Connection

### Connection Parameters

Required parameters for database connections:

- `--db-type`: Database type (postgresql, mysql, sqlite)
- `--host`: Database host (not required for SQLite)
- `--port`: Database port (default: 5432 for PostgreSQL, 3306 for MySQL)
- `--database`: Database name
- `--user`: Username (not required for SQLite)
- `--password`: Password (not required for SQLite)

### SQLite Example

```bash
python scripts/execute_query.py --db-type sqlite --database /path/to/db.sqlite \
  --query "SELECT * FROM table_name"
```

## Query Execution

### Basic Query

```bash
python scripts/execute_query.py --db-type postgresql --host localhost \
  --database mydb --user myuser --password mypass \
  --query "SELECT id, name FROM users WHERE active = true"
```

### Query with Output File

```bash
python scripts/execute_query.py --db-type postgresql --host localhost \
  --database mydb --user myuser --password mypass \
  --query "SELECT * FROM orders" --output results.json
```

### Parameterized Query

```bash
python scripts/execute_query.py --db-type postgresql --host localhost \
  --database mydb --user myuser --password mypass \
  --query "SELECT * FROM users WHERE id = %s" --params "[1]"
```

## Data Visualization

### Supported Chart Types

- **bar**: Bar chart for categorical data comparison
- **line**: Line chart for trends over time
- **pie**: Pie chart for proportional data
- **scatter**: Scatter plot for correlation analysis

### Bar Chart Example

```bash
python scripts/visualize_data.py \
  --data "[{"category": "A", "count": 100}, {"category": "B", "count": 150}]" \
  --chart-type bar --x-column category --y-column count \
  --title "Category Distribution" --output bar_chart.png
```

### Line Chart Example

```bash
python scripts/visualize_data.py \
  --data "[{"month": "Jan", "sales": 1000}, {"month": "Feb", "sales": 1200}]" \
  --chart-type line --x-column month --y-column sales \
  --title "Monthly Sales Trend" --output trend.png
```

### Pie Chart Example

```bash
python scripts/visualize_data.py \
  --data "[{"product": "A", "share": 30}, {"product": "B", "share": 70}]" \
  --chart-type pie --x-column product --y-column share \
  --title "Market Share" --output pie.png
```

## Common Analysis Patterns

### Time Series Analysis

```sql
SELECT 
  DATE(created_at) as date,
  COUNT(*) as count,
  SUM(amount) as total
FROM orders
WHERE created_at >= '2024-01-01'
GROUP BY DATE(created_at)
ORDER BY date;
```

### Top N Analysis

```sql
SELECT 
  product_id,
  COUNT(*) as order_count,
  SUM(amount) as revenue
FROM orders
GROUP BY product_id
ORDER BY revenue DESC
LIMIT 10;
```

### Cohort Analysis

```sql
SELECT 
  DATE(first_order) as cohort,
  COUNT(DISTINCT user_id) as users,
  COUNT(*) as total_orders
FROM (
  SELECT 
    user_id,
    MIN(created_at) as first_order,
    created_at
  FROM orders
  GROUP BY user_id, created_at
) user_orders
GROUP BY cohort
ORDER BY cohort;
```

### Funnel Analysis

```sql
WITH funnel AS (
  SELECT 
    user_id,
    COUNT(CASE WHEN step = 'view' THEN 1 END) as views,
    COUNT(CASE WHEN step = 'cart' THEN 1 END) as carts,
    COUNT(CASE WHEN step = 'purchase' THEN 1 END) as purchases
  FROM events
  WHERE event_date >= '2024-01-01'
  GROUP BY user_id
)
SELECT 
  COUNT(*) as total_users,
  SUM(CASE WHEN views > 0 THEN 1 ELSE 0 END) as viewed,
  SUM(CASE WHEN carts > 0 THEN 1 ELSE 0 END) as added_to_cart,
  SUM(CASE WHEN purchases > 0 THEN 1 ELSE 0 END) as purchased
FROM funnel;
```

## Reference Materials

For detailed guidance, consult these references:

- **[API Reference](references/api_reference.md)**: Complete API documentation for all scripts
- **[SQL Patterns](references/sql_patterns.md)**: Common SQL query patterns and examples
- **[Best Practices](references/best_practices.md)**: Query optimization and security guidelines

## Error Handling

### Common Issues

1. **Connection failed**: Verify host, port, and credentials
2. **Table not found**: Check database name and table existence
3. **Permission denied**: Ensure user has required privileges
4. **Syntax error**: Validate SQL syntax for specific database type

### Debug Mode

Add `--debug` flag to scripts for detailed error messages:

```bash
python scripts/execute_query.py --debug --query "SELECT * FROM users"
```

## Security Notes

- Never hardcode passwords in scripts
- Use environment variables for sensitive data
- Use read-only database users for analysis queries
- Validate all user inputs before query execution
- Use parameterized queries to prevent SQL injection
