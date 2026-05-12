-- From 0.7.x to 0.8.0, we have the following changes:
USE dbgpt;

-- share_links, Store conversation share link tokens
CREATE TABLE `share_links` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT 'Primary key',
  `token` varchar(64) NOT NULL COMMENT 'Unique random share token',
  `conv_uid` varchar(255) NOT NULL COMMENT 'The conversation uid being shared',
  `created_by` varchar(255) DEFAULT NULL COMMENT 'User who created the share link',
  `gmt_created` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Creation time',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_share_token` (`token`),
  KEY `ix_share_links_token` (`token`),
  KEY `ix_share_links_conv_uid` (`conv_uid`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Conversation share link table';
