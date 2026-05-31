-- From 0.8.0 to 0.8.1, we have the following changes:
USE dbgpt;

-- connector_instance, Persist MCP connector instances (encrypted credentials, transport/extra config, lifecycle status)
CREATE TABLE IF NOT EXISTS `connector_instance` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT 'Auto increment id',
  `connector_id` varchar(64) NOT NULL COMMENT 'Connector UUID',
  `connector_type` varchar(64) NOT NULL COMMENT 'Connector type, e.g. yuque, feishu, custom_mcp',
  `display_name` varchar(256) DEFAULT NULL COMMENT 'Display name',
  `encrypted_credentials` text COMMENT 'Encrypted credentials JSON',
  `encryption_salt` varchar(256) DEFAULT NULL COMMENT 'Encryption salt',
  `status` varchar(32) DEFAULT NULL COMMENT 'Status: active / error / disconnected / needs_reactivation',
  `config_json` text COMMENT 'Extra config JSON (server_uri, transport, description, auth_type, header_name, ...)',
  `user_name` varchar(128) DEFAULT NULL COMMENT 'User name',
  `sys_code` varchar(128) DEFAULT NULL COMMENT 'System code',
  `gmt_created` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT 'Record creation time',
  `gmt_modified` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Record update time',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_connector_instance_connector_id` (`connector_id`),
  KEY `ix_connector_instance_user_name` (`user_name`),
  KEY `ix_connector_instance_sys_code` (`sys_code`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='MCP connector instance table';

-- dbgpt_serve_scheduled_task, Scheduled tasks bound to a connector (APScheduler cron + one-shot tool invocation snapshot)
CREATE TABLE IF NOT EXISTS `dbgpt_serve_scheduled_task` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT 'Auto increment id',
  `task_id` varchar(64) NOT NULL COMMENT 'Task UUID',
  `connector_id` varchar(64) NOT NULL COMMENT 'Associated connector UUID',
  `task_name` varchar(256) NOT NULL COMMENT 'Task display name',
  `description` text COMMENT 'Task description',
  `cron_expression` varchar(128) NOT NULL COMMENT 'APScheduler cron expression',
  `tool_name` varchar(256) NOT NULL COMMENT 'Tool name to execute',
  `tool_args` text COMMENT 'JSON-serialized tool arguments',
  `enabled` tinyint(1) NOT NULL DEFAULT '1' COMMENT 'Whether the task is enabled',
  `last_run_time` DATETIME DEFAULT NULL COMMENT 'Last execution time',
  `last_run_status` varchar(32) DEFAULT NULL COMMENT 'Last run status: success / failed / pending',
  `last_run_result` text COMMENT 'JSON-serialized last run result summary',
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT 'Record creation time',
  `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Record update time',
  `user_name` varchar(128) DEFAULT NULL COMMENT 'User name',
  `sys_code` varchar(128) DEFAULT NULL COMMENT 'System code',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_dbgpt_serve_scheduled_task_task_id` (`task_id`),
  KEY `ix_dbgpt_serve_scheduled_task_connector_id` (`connector_id`),
  KEY `ix_dbgpt_serve_scheduled_task_user_name` (`user_name`),
  KEY `ix_dbgpt_serve_scheduled_task_sys_code` (`sys_code`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Connector scheduled task table';
