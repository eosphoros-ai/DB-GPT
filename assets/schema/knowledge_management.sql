CREATE DATABASE knowledge_management;
use knowledge_management;
CREATE TABLE `knowledge_space` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT 'auto increment id',
  `name` varchar(100) NOT NULL COMMENT 'knowledge space name',
  `vector_type` varchar(50) NOT NULL COMMENT 'vector type',
  `desc` varchar(500) NOT NULL COMMENT 'description',
  `owner` varchar(100) DEFAULT NULL COMMENT 'owner',
  `context` TEXT DEFAULT NULL COMMENT 'context argument',
  `gmt_created` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'created time',
  `gmt_modified` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'update time',
  PRIMARY KEY (`id`),
  KEY `idx_name` (`name`) COMMENT 'index:idx_name'
) ENGINE=InnoDB AUTO_INCREMENT=100001 DEFAULT CHARSET=utf8mb4 COMMENT='knowledge space table';

CREATE TABLE `knowledge_document` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT 'auto increment id',
  `doc_name` varchar(100) NOT NULL COMMENT 'document path name',
  `doc_type` varchar(50) NOT NULL COMMENT 'doc type',
  `space` varchar(50) NOT NULL COMMENT 'knowledge space',
  `chunk_size` int NOT NULL COMMENT 'chunk size',
  `last_sync` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'last sync time',
  `status` varchar(50) NOT NULL COMMENT 'status TODO,RUNNING,FAILED,FINISHED',
  `content` LONGTEXT NOT NULL COMMENT 'knowledge embedding sync result',
  `result` TEXT NULL COMMENT 'knowledge content',
  `vector_ids` LONGTEXT NULL COMMENT 'vector_ids',
  `gmt_created` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'created time',
  `gmt_modified` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'update time',
  PRIMARY KEY (`id`),
  KEY `idx_doc_name` (`doc_name`) COMMENT 'index:idx_doc_name'
) ENGINE=InnoDB AUTO_INCREMENT=100001 DEFAULT CHARSET=utf8mb4 COMMENT='knowledge document table';

CREATE TABLE `document_chunk` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT 'auto increment id',
  `doc_name` varchar(100) NOT NULL COMMENT 'document path name',
  `doc_type` varchar(50) NOT NULL COMMENT 'doc type',
  `document_id` int NOT NULL COMMENT 'document parent id',
  `content` longtext NOT NULL COMMENT 'chunk content',
  `meta_info` varchar(200) NOT NULL COMMENT 'metadata info',
  `gmt_created` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'created time',
  `gmt_modified` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'update time',
  PRIMARY KEY (`id`),
  KEY `idx_document_id` (`document_id`) COMMENT 'index:document_id'
) ENGINE=InnoDB AUTO_INCREMENT=100001 DEFAULT CHARSET=utf8mb4 COMMENT='knowledge document chunk detail';

CREATE DATABASE EXAMPLE_1;
use EXAMPLE_1;
CREATE TABLE `users` (
  `id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(50) NOT NULL COMMENT '用户名',
  `password` varchar(50) NOT NULL COMMENT '密码',
  `email` varchar(50) NOT NULL COMMENT '邮箱',
  `phone` varchar(20) DEFAULT NULL COMMENT '电话',
  PRIMARY KEY (`id`),
  KEY `idx_username` (`username`) COMMENT '索引：按用户名查询'
) ENGINE=InnoDB AUTO_INCREMENT=101 DEFAULT CHARSET=utf8mb4 COMMENT='聊天用户表';

INSERT INTO users (username, password, email, phone) VALUES ('user_1', 'password_1', 'user_1@example.com', '12345678901');
INSERT INTO users (username, password, email, phone) VALUES ('user_2', 'password_2', 'user_2@example.com', '12345678902');
INSERT INTO users (username, password, email, phone) VALUES ('user_3', 'password_3', 'user_3@example.com', '12345678903');
INSERT INTO users (username, password, email, phone) VALUES ('user_4', 'password_4', 'user_4@example.com', '12345678904');
INSERT INTO users (username, password, email, phone) VALUES ('user_5', 'password_5', 'user_5@example.com', '12345678905');
INSERT INTO users (username, password, email, phone) VALUES ('user_6', 'password_6', 'user_6@example.com', '12345678906');
INSERT INTO users (username, password, email, phone) VALUES ('user_7', 'password_7', 'user_7@example.com', '12345678907');
INSERT INTO users (username, password, email, phone) VALUES ('user_8', 'password_8', 'user_8@example.com', '12345678908');
INSERT INTO users (username, password, email, phone) VALUES ('user_9', 'password_9', 'user_9@example.com', '12345678909');
INSERT INTO users (username, password, email, phone) VALUES ('user_10', 'password_10', 'user_10@example.com', '12345678900');
INSERT INTO users (username, password, email, phone) VALUES ('user_11', 'password_11', 'user_11@example.com', '12345678901');
INSERT INTO users (username, password, email, phone) VALUES ('user_12', 'password_12', 'user_12@example.com', '12345678902');
INSERT INTO users (username, password, email, phone) VALUES ('user_13', 'password_13', 'user_13@example.com', '12345678903');
INSERT INTO users (username, password, email, phone) VALUES ('user_14', 'password_14', 'user_14@example.com', '12345678904');
INSERT INTO users (username, password, email, phone) VALUES ('user_15', 'password_15', 'user_15@example.com', '12345678905');
INSERT INTO users (username, password, email, phone) VALUES ('user_16', 'password_16', 'user_16@example.com', '12345678906');
INSERT INTO users (username, password, email, phone) VALUES ('user_17', 'password_17', 'user_17@example.com', '12345678907');
INSERT INTO users (username, password, email, phone) VALUES ('user_18', 'password_18', 'user_18@example.com', '12345678908');
INSERT INTO users (username, password, email, phone) VALUES ('user_19', 'password_19', 'user_19@example.com', '12345678909');
INSERT INTO users (username, password, email, phone) VALUES ('user_20', 'password_20', 'user_20@example.com', '12345678900');