CREATE DATABASE history;
use history;
CREATE TABLE `chat_feed_back` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `conv_uid` varchar(128) DEFAULT NULL COMMENT '会话id',
  `conv_index` int(4) DEFAULT NULL COMMENT '第几轮会话',
  `score` int(1) DEFAULT NULL COMMENT '评分',
  `ques_type` varchar(32) DEFAULT NULL COMMENT '用户问题类别',
  `question` longtext DEFAULT NULL COMMENT '用户问题',
  `knowledge_space` varchar(128) DEFAULT NULL COMMENT '知识库',
  `messages` longtext DEFAULT NULL COMMENT '评价详情',
  `user_name` varchar(128) DEFAULT NULL COMMENT '评价人',
  `gmt_created` datetime DEFAULT NULL,
  `gmt_modified` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_conv` (`conv_uid`,`conv_index`),
  KEY `idx_conv` (`conv_uid`,`conv_index`)
) ENGINE=InnoDB AUTO_INCREMENT=0 DEFAULT CHARSET=utf8mb4 COMMENT='用户评分反馈表';