# Common SQL Patterns

## Basic Queries

### Select all columns
```sql
SELECT * FROM table_name;
```

### Select specific columns
```sql
SELECT column1, column2 FROM table_name;
```

### Filter with WHERE
```sql
SELECT * FROM table_name WHERE condition;
```

### Sort results
```sql
SELECT * FROM table_name ORDER BY column_name ASC/DESC;
```

### Limit results
```sql
SELECT * FROM table_name LIMIT 10;
```

## Aggregation

### Count rows
```sql
SELECT COUNT(*) FROM table_name;
```

### Sum values
```sql
SELECT SUM(column_name) FROM table_name;
```

### Average
```sql
SELECT AVG(column_name) FROM table_name;
```

### Group by
```sql
SELECT column1, COUNT(*) FROM table_name GROUP BY column1;
```

### Having clause
```sql
SELECT column1, COUNT(*) as cnt FROM table_name 
GROUP BY column1 HAVING cnt > 10;
```

## Joins

### Inner join
```sql
SELECT a.*, b.* FROM table_a a 
INNER JOIN table_b b ON a.id = b.a_id;
```

### Left join
```sql
SELECT a.*, b.* FROM table_a a 
LEFT JOIN table_b b ON a.id = b.a_id;
```

### Self join
```sql
SELECT a.name, b.name FROM employees a 
JOIN employees b ON a.manager_id = b.id;
```

## Date Operations

### Filter by date range
```sql
SELECT * FROM table_name 
WHERE date_column BETWEEN '2024-01-01' AND '2024-12-31';
```

### Extract date parts
```sql
SELECT 
  EXTRACT(YEAR FROM date_column) as year,
  EXTRACT(MONTH FROM date_column) as month
FROM table_name;
```

## Window Functions

### Row number
```sql
SELECT *, ROW_NUMBER() OVER (ORDER BY column_name) as row_num
FROM table_name;
```

### Running total
```sql
SELECT *, 
  SUM(amount) OVER (ORDER BY date_column) as running_total
FROM table_name;
```

## Data Modification

### Insert
```sql
INSERT INTO table_name (col1, col2) VALUES (val1, val2);
```

### Update
```sql
UPDATE table_name SET column = value WHERE condition;
```

### Delete
```sql
DELETE FROM table_name WHERE condition;
```
