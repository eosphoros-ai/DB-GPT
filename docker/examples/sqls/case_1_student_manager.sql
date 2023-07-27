create database case_1_student_manager character set utf8;
use case_1_student_manager;

CREATE TABLE students (
    student_id INT PRIMARY KEY,
    student_name VARCHAR(100) COMMENT '学生姓名',
    major VARCHAR(100) COMMENT '专业',
    year_of_enrollment INT COMMENT '入学年份',
    student_age INT COMMENT '学生年龄'
) COMMENT '学生信息表';

CREATE TABLE courses (
    course_id INT PRIMARY KEY,
    course_name VARCHAR(100) COMMENT '课程名称',
    credit FLOAT COMMENT '学分'
) COMMENT '课程信息表';

CREATE TABLE scores (
    student_id INT,
    course_id INT,
    score INT COMMENT '得分',
    semester VARCHAR(50) COMMENT '学期',
    PRIMARY KEY (student_id, course_id),
    FOREIGN KEY (student_id) REFERENCES students(student_id),
    FOREIGN KEY (course_id) REFERENCES courses(course_id)
) COMMENT '学生成绩表';


INSERT INTO students (student_id, student_name, major, year_of_enrollment, student_age) VALUES
(1, '张三', '计算机科学', 2020, 20),
(2, '李四', '计算机科学', 2021, 19),
(3, '王五', '物理学', 2020, 21),
(4, '赵六', '数学', 2021, 19),
(5, '周七', '计算机科学', 2022, 18),
(6, '吴八', '物理学', 2020, 21),
(7, '郑九', '数学', 2021, 19),
(8, '孙十', '计算机科学', 2022, 18),
(9, '刘十一', '物理学', 2020, 21),
(10, '陈十二', '数学', 2021, 19);

INSERT INTO courses (course_id, course_name, credit) VALUES
(1, '计算机基础', 3),
(2, '数据结构', 4),
(3, '高等物理', 3),
(4, '线性代数', 4),
(5, '微积分', 5),
(6, '编程语言', 4),
(7, '量子力学', 3),
(8, '概率论', 4),
(9, '数据库系统', 4),
(10, '计算机网络', 4);

INSERT INTO scores (student_id, course_id, score, semester) VALUES
(1, 1, 90, '2020年秋季'),
(1, 2, 85, '2021年春季'),
(2, 1, 88, '2021年秋季'),
(2, 2, 90, '2022年春季'),
(3, 3, 92, '2020年秋季'),
(3, 4, 85, '2021年春季'),
(4, 3, 88, '2021年秋季'),
(4, 4, 86, '2022年春季'),
(5, 1, 90, '2022年秋季'),
(5, 2, 87, '2023年春季');
