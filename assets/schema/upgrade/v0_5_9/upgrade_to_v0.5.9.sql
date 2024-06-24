USE dbgpt;

-- For deploy model cluster of DB-GPT(StorageModelRegistry)
CREATE TABLE IF NOT EXISTS `dbgpt_cluster_registry_instance` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT 'Auto increment id',
  `model_name` varchar(128) NOT NULL COMMENT 'Model name',
  `host` varchar(128) NOT NULL COMMENT 'Host of the model',
  `port` int(11) NOT NULL COMMENT 'Port of the model',
  `weight` float DEFAULT 1.0 COMMENT 'Weight of the model',
  `check_healthy` tinyint(1) DEFAULT 1 COMMENT 'Whether to check the health of the model',
  `healthy` tinyint(1) DEFAULT 0 COMMENT 'Whether the model is healthy',
  `enabled` tinyint(1) DEFAULT 1 COMMENT 'Whether the model is enabled',
  `prompt_template` varchar(128) DEFAULT NULL COMMENT 'Prompt template for the model instance',
  `last_heartbeat` datetime DEFAULT NULL COMMENT 'Last heartbeat time of the model instance',
  `user_name` varchar(128) DEFAULT NULL COMMENT 'User name',
  `sys_code` varchar(128) DEFAULT NULL COMMENT 'System code',
  `gmt_created` datetime DEFAULT CURRENT_TIMESTAMP COMMENT 'Record creation time',
  `gmt_modified` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Record update time',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_model_instance` (`model_name`, `host`, `port`, `sys_code`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COMMENT='Cluster model instance table, for registering and managing model instances';

