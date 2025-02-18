-- From 0.6.3 to 0.7.0, we have the following changes:
USE dbgpt;

-- connect_config
ALTER TABLE `connect_config`
    ADD COLUMN `gmt_created` datetime DEFAULT CURRENT_TIMESTAMP COMMENT 'Record creation time',
    ADD COLUMN `gmt_modified` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Record update time',
    ADD COLUMN `ext_config` text COMMENT 'Extended configuration, json format';

-- dbgpt_serve_model, Store the model information of the model worker
CREATE TABLE `dbgpt_serve_model` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT 'Auto increment id',
  `host` varchar(255) NOT NULL COMMENT 'The model worker host',
  `port` int NOT NULL COMMENT 'The model worker port',
  `model` varchar(255) NOT NULL COMMENT 'The model name',
  `provider` varchar(255) NOT NULL COMMENT 'The model provider',
  `worker_type` varchar(255) NOT NULL COMMENT 'The worker type',
  `params` text NOT NULL COMMENT 'The model parameters, JSON format',
  `enabled` int DEFAULT 1 COMMENT 'Whether the model is enabled, if it is enabled, it will be started when the system starts, 1 is enabled, 0 is disabled',
  `worker_name` varchar(255) DEFAULT NULL COMMENT 'The worker name',
  `description` text DEFAULT NULL COMMENT 'The model description',
  `user_name` varchar(128) DEFAULT NULL COMMENT 'User name',
  `sys_code` varchar(128) DEFAULT NULL COMMENT 'System code',
  `gmt_created` datetime DEFAULT CURRENT_TIMESTAMP COMMENT 'Record creation time',
  `gmt_modified` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Record update time',
  PRIMARY KEY (`id`),
  KEY `idx_user_name` (`user_name`),
  KEY `idx_sys_code` (`sys_code`),
  UNIQUE KEY `uk_model_provider_type` (`model`, `provider`, `worker_type`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Model persistence table';

ALTER TABLE `recommend_question`
MODIFY COLUMN `user_code` varchar(255) NULL COMMENT 'user code';

