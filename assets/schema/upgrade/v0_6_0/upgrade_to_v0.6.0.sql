USE dbgpt;
-- chat_history
ALTER TABLE  chat_history ADD COLUMN `app_code` varchar(255) DEFAULT NULL COMMENT 'App unique code' after `message_ids`;

-- gpts_app
ALTER TABLE  gpts_app ADD COLUMN `published` varchar(64) DEFAULT 'false' COMMENT 'Has it been published?';
ALTER TABLE  gpts_app ADD COLUMN `param_need` text DEFAULT NULL COMMENT 'Parameter information supported by the application';
ALTER TABLE  gpts_app ADD COLUMN `admins` text DEFAULT NULL COMMENT 'administrator';


-- connect_config
ALTER TABLE  connect_config ADD COLUMN `user_name` varchar(255) DEFAULT NULL COMMENT 'user name';
ALTER TABLE  connect_config ADD COLUMN `user_id` varchar(255) DEFAULT NULL COMMENT 'user id';

-- document_chunk
ALTER TABLE  document_chunk ADD COLUMN `questions` text DEFAULT NULL COMMENT 'chunk related questions';

-- knowledge_document
ALTER TABLE  knowledge_document ADD COLUMN `doc_token` varchar(100) DEFAULT NULL COMMENT 'doc token';
ALTER TABLE  knowledge_document ADD COLUMN `questions` text DEFAULT NULL COMMENT 'document related questions';

-- gpts_messages
ALTER TABLE  gpts_messages ADD COLUMN `is_success` int(4)  NULL DEFAULT 0 COMMENT 'agent message is success';
ALTER TABLE  gpts_messages ADD COLUMN `app_code` varchar(255) NOT NULL COMMENT 'Current AI assistant code';
ALTER TABLE  gpts_messages ADD COLUMN `app_name` varchar(255) NOT NULL COMMENT 'Current AI assistant name';
ALTER TABLE  gpts_messages ADD COLUMN `resource_info` text DEFAULT NULL  COMMENT 'Current conversation resource info';

-- prompt_manage
ALTER TABLE  prompt_manage ADD COLUMN `prompt_code` varchar(255) NULL COMMENT 'Prompt code';
ALTER TABLE  prompt_manage ADD COLUMN `response_schema` text  NULL COMMENT 'Prompt response schema';
ALTER TABLE  prompt_manage ADD COLUMN `user_code` varchar(128)  NULL COMMENT 'User code';

-- chat_feed_back
ALTER TABLE  chat_feed_back ADD COLUMN `message_id` varchar(255)  NULL COMMENT 'Message id';
ALTER TABLE  chat_feed_back ADD COLUMN `feedback_type` varchar(50)  NULL COMMENT 'Feedback type like or unlike';
ALTER TABLE  chat_feed_back ADD COLUMN `reason_types` varchar(255)  NULL COMMENT 'Feedback reason categories';
ALTER TABLE  chat_feed_back ADD COLUMN `user_code` varchar(128)  NULL COMMENT 'User code';
ALTER TABLE  chat_feed_back ADD COLUMN `remark` text NULL COMMENT 'Feedback remark';

-- dbgpt_serve_flow
ALTER TABLE dbgpt_serve_flow ADD COLUMN `variables` text DEFAULT NULL COMMENT 'Flow variables, JSON format';

-- dbgpt.recommend_question definition
CREATE TABLE `recommend_question` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT COMMENT 'autoincrement id',
  `gmt_create` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'create time',
  `gmt_modified` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'last update time',
  `app_code` varchar(255) DEFAULT NULL COMMENT 'Current AI assistant code',
  `question` text DEFAULT NULL COMMENT 'question',
  `user_code` int(11) DEFAULT NULL COMMENT 'user code',
  `sys_code` varchar(255) DEFAULT NULL COMMENT 'system app code',
  `valid` varchar(10) DEFAULT 'true' COMMENT 'is it effective，true/false',
  `chat_mode` varchar(255) DEFAULT NULL COMMENT 'Conversation scene mode，chat_knowledge...',
  `params` text DEFAULT NULL COMMENT 'question param',
  `is_hot_question` varchar(10) DEFAULT 'false' COMMENT 'Is it a popular recommendation question?',
  PRIMARY KEY (`id`),
  KEY `idx_rec_q_app_code` (`app_code`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT="AI application related recommendation issues";

-- dbgpt.user_recent_apps definition
CREATE TABLE `user_recent_apps` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT COMMENT 'autoincrement id',
  `gmt_create` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'create time',
  `gmt_modified` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'last update time',
  `app_code` varchar(255) DEFAULT NULL COMMENT 'AI assistant code',
  `last_accessed` timestamp NULL DEFAULT NULL COMMENT 'User recent usage time',
  `user_code` varchar(255) DEFAULT NULL COMMENT 'user code',
  `sys_code` varchar(255) DEFAULT NULL COMMENT 'system app code',
  PRIMARY KEY (`id`),
  KEY `idx_user_r_app_code` (`app_code`),
  KEY `idx_last_accessed` (`last_accessed`),
  KEY `idx_user_code` (`user_code`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='User recently used apps';

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
  `scope` varchar(32) DEFAULT 'global' COMMENT 'Variable scope(global,flow,app,agent,datasource,flow_priv,agent_priv, ""etc)',
  `scope_key` varchar(256) DEFAULT NULL COMMENT 'Variable scope key, default is empty, for scope is "flow_priv", the scope_key is dag id of flow',
  `enabled` int DEFAULT 1 COMMENT 'Variable enabled, 0: disabled, 1: enabled',
  `description` text DEFAULT NULL COMMENT 'Variable description',
  `user_name` varchar(128) DEFAULT NULL COMMENT 'User name',
  `sys_code` varchar(128) DEFAULT NULL COMMENT 'System code',
  `gmt_created` datetime DEFAULT CURRENT_TIMESTAMP COMMENT 'Record creation time',
  `gmt_modified` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Record update time',
  PRIMARY KEY (`id`),
  KEY `ix_your_table_name_key` (`key`),
  KEY `ix_your_table_name_name` (`name`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

