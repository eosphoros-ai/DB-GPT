CREATE DATABASE prompt_management;
use prompt_management;
CREATE TABLE `prompt_manage` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `chat_scene` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '场景',
  `sub_chat_scene` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '子场景',
  `prompt_type` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '类型： common or private',
  `prompt_name` varchar(512) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'prompt的名字',
  `content` longtext COLLATE utf8mb4_unicode_ci COMMENT 'prompt的内容',
  `user_name` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '用户名',
  `gmt_created` datetime DEFAULT NULL,
  `gmt_modified` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `prompt_name_uiq` (`prompt_name`),
  KEY `gmt_created_idx` (`gmt_created`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='prompt管理表';