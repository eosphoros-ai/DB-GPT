






##### Q5:When I Chat Data and Chat Meta Data, I found the error
<p align="left">
  <img src="../../assets/faq/chatdataerror.png" width="800px" />
</p>

##### A5: you have not create your database and table
1.create your database.
```bash
mysql> create database {$your_name}
mysql> use {$your_name}
```

2.create table {$your_table} and insert your data. 
eg:
```bash
mysql>CREATE TABLE `users` (
  `id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(50) NOT NULL COMMENT '用户名',
  `password` varchar(50) NOT NULL COMMENT '密码',
  `email` varchar(50) NOT NULL COMMENT '邮箱',
  `phone` varchar(20) DEFAULT NULL COMMENT '电话',
  PRIMARY KEY (`id`),
  KEY `idx_username` (`username`) COMMENT '索引：按用户名查询'
) ENGINE=InnoDB AUTO_INCREMENT=101 DEFAULT CHARSET=utf8mb4 COMMENT='聊天用户表'
```












