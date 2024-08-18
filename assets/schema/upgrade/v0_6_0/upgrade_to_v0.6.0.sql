-- dbgpt.dbgpt_serve_file definition
CREATE TABLE `dbgpt_serve_file` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT 'Auto increment id',
  `bucket` varchar(255) NOT NULL COMMENT 'Bucket name',
  `file_id` varchar(255) NOT NULL COMMENT 'File id',
  `file_name` varchar(256) NOT NULL COMMENT 'File name',
  `file_size` int DEFAULT NULL COMMENT 'File size',
  `storage_type` varchar(32) NOT NULL COMMENT 'Storage type',
  `storage_path` varchar(512) NOT NULL COMMENT 'Storage path',
  `uri` varchar(512) NOT NULL COMMENT 'File URI',
  `custom_metadata` text DEFAULT NULL COMMENT 'Custom metadata, JSON format',
  `file_hash` varchar(128) DEFAULT NULL COMMENT 'File hash',
  `user_name` varchar(128) DEFAULT NULL COMMENT 'User name',
  `sys_code` varchar(128) DEFAULT NULL COMMENT 'System code',
  `gmt_created` datetime DEFAULT CURRENT_TIMESTAMP COMMENT 'Record creation time',
  `gmt_modified` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Record update time',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_bucket_file_id` (`bucket`, `file_id`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- dbgpt.dbgpt_serve_variables definition
CREATE TABLE `dbgpt_serve_variables` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT 'Auto increment id',
  `key` varchar(128) NOT NULL COMMENT 'Variable key',
  `name` varchar(128) DEFAULT NULL COMMENT 'Variable name',
  `label` varchar(128) DEFAULT NULL COMMENT 'Variable label',
  `value` text DEFAULT NULL COMMENT 'Variable value, JSON format',
  `value_type` varchar(32) DEFAULT NULL COMMENT 'Variable value type(string, int, float, bool)',
  `category` varchar(32) DEFAULT 'common' COMMENT 'Variable category(common or secret)',
  `encryption_method` varchar(32) DEFAULT NULL COMMENT 'Variable encryption method(fernet, simple, rsa, aes)',
  `salt` varchar(128) DEFAULT NULL COMMENT 'Variable salt',
  `scope` varchar(32) DEFAULT 'global' COMMENT 'Variable scope(global,flow,app,agent,datasource,flow:uid, flow:dag_name,agent:agent_name) etc',
  `scope_key` varchar(256) DEFAULT NULL COMMENT 'Variable scope key, default is empty, for scope is "flow:uid", the scope_key is uid of flow',
  `enabled` int DEFAULT 1 COMMENT 'Variable enabled, 0: disabled, 1: enabled',
  `user_name` varchar(128) DEFAULT NULL COMMENT 'User name',
  `sys_code` varchar(128) DEFAULT NULL COMMENT 'System code',
  `gmt_created` datetime DEFAULT CURRENT_TIMESTAMP COMMENT 'Record creation time',
  `gmt_modified` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Record update time',
  PRIMARY KEY (`id`),
  KEY `ix_your_table_name_key` (`key`),
  KEY `ix_your_table_name_name` (`name`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

