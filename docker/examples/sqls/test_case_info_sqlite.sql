CREATE TABLE test_cases (
    case_id INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_name VARCHAR(100),
    scenario_description TEXT,
    test_question VARCHAR(500),
    expected_sql TEXT,
    correct_output TEXT
);


INSERT INTO test_cases (scenario_name, scenario_description, test_question, expected_sql, correct_output) VALUES
('学校管理系统', '测试SQL助手的联合查询，条件查询和排序功能', '查询所有学生的姓名，专业和成绩，按成绩降序排序', 'SELECT students.student_name, students.major, scores.score FROM students JOIN scores ON students.student_id = scores.student_id ORDER BY scores.score DESC;', '返回所有学生的姓名，专业和成绩，按成绩降序排序的结果'),
('学校管理系统', '测试SQL助手的联合查询，条件查询和排序功能', '查询计算机科学专业的学生的平均成绩', 'SELECT AVG(scores.score) as avg_score FROM students JOIN scores ON students.student_id = scores.student_id WHERE students.major = ''计算机科学'';', '返回计算机科学专业学生的平均成绩'),
('学校管理系统', '测试SQL助手的联合查询，条件查询和排序功能', '查询哪些学生在2023年秋季学期的课程学分总和超过15', 'SELECT students.student_name FROM students JOIN scores ON students.student_id = scores.student_id JOIN courses ON scores.course_id = courses.course_id WHERE scores.semester = ''2023年秋季'' GROUP BY students.student_id HAVING SUM(courses.credit) > 15;', '返回在2023年秋季学期的课程学分总和超过15的学生的姓名'),
('电商系统', '测试SQL助手的数据聚合和分组功能', '查询每个用户的总订单数量', 'SELECT users.user_name, COUNT(orders.order_id) as order_count FROM users JOIN orders ON users.user_id = orders.user_id GROUP BY users.user_id;', '返回每个用户的总订单数量'),
('电商系统', '测试SQL助手的数据聚合和分组功能', '查询每种商品的总销售额', 'SELECT products.product_name, SUM(products.product_price * orders.quantity) as total_sales FROM products JOIN orders ON products.product_id = orders.product_id GROUP BY products.product_id;', '返回每种商品的总销售额'),
('电商系统', '测试SQL助手的数据聚合和分组功能', '查询2023年最受欢迎的商品（订单数量最多的商品）', 'SELECT products.product_name FROM products JOIN orders ON products.product_id = orders.product_id WHERE YEAR(orders.order_date) = 2023 GROUP BY products.product_id ORDER BY COUNT(orders.order_id) DESC LIMIT 1;', '返回2023年最受欢迎的商品（订单数量最多的商品）的名称');
