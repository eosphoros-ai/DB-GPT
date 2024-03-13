# 测试问题

## 场景一 

学校管理系统，主要测试SQL助手的联合查询，条件查询和排序功能。

我们的数据库有三个表：学生表、课程表和成绩表。我们要测试SQL助手能否处理复杂的SQL查询，包括连接多个表，按照一定的条件筛选数据，以及对结果进行排序。

### Q1

查询所有学生的姓名，专业和成绩，按成绩降序排序

SQL：
```sql
SELECT students.student_name, students.major, scores.score
FROM students
JOIN scores ON students.student_id = scores.student_id
ORDER BY scores.score DESC;
```

### Q2

查询 "计算机科学" 专业的学生的平均成绩

SQL：
```sql
SELECT AVG(scores.score) as avg_score
FROM students
JOIN scores ON students.student_id = scores.student_id
WHERE students.major = '计算机科学';
```

### Q3

查询哪些学生在 "2023年春季" 学期的课程学分总和超过2学分

```sql
SELECT students.student_name
FROM students
JOIN scores ON students.student_id = scores.student_id
JOIN courses ON scores.course_id = courses.course_id
WHERE scores.semester = '2023年春季'
GROUP BY students.student_id
HAVING SUM(courses.credit) > 2;
```

## 场景二：电商系统，主要测试SQL助手的数据聚合和分组功能。

我们的数据库有三个表：用户表、商品表和订单表。我们要测试SQL助手能否处理复杂的SQL查询，包括对数据进行聚合和分组。

### Q1

查询每个用户的总订单数量

SQL:

```sql
SELECT users.user_name, COUNT(orders.order_id) as order_count
FROM users
JOIN orders ON users.user_id = orders.user_id
GROUP BY users.user_id;
```

### Q2

查询每种商品的总销售额

```sql
SELECT products.product_name, SUM(products.product_price * orders.quantity) as total_sales
FROM products
JOIN orders ON products.product_id = orders.product_id
GROUP BY products.product_id;
```

### Q3

查询2023年最受欢迎的商品（订单数量最多的商品）

```sql
SELECT products.product_name
FROM products
JOIN orders ON products.product_id = orders.product_id
WHERE YEAR(orders.order_date) = 2023
GROUP BY products.product_id
ORDER BY COUNT(orders.order_id) DESC
LIMIT 1;
```