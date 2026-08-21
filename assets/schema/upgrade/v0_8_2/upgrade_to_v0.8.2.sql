-- From 0.8.1 to 0.8.2, we have the following changes:
USE dbgpt;

-- dbgpt_session_file, Private persistence for owner-bound session and task files
CREATE TABLE IF NOT EXISTS `dbgpt_session_file` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT 'Auto increment id',
  `file_id` varchar(64) NOT NULL COMMENT 'Public file ID',
  `owner_id` varchar(255) NOT NULL COMMENT 'Owning user ID',
  `session_id` varchar(255) DEFAULT NULL COMMENT 'Interactive session ID',
  `task_id` varchar(64) DEFAULT NULL COMMENT 'Scheduled task ID',
  `display_name` varchar(256) NOT NULL COMMENT 'Display file name',
  `storage_uri` varchar(512) NOT NULL COMMENT 'Private managed storage URI',
  `media_type` varchar(255) NOT NULL COMMENT 'Detected media type',
  `file_kind` varchar(32) NOT NULL COMMENT 'File kind',
  `size_bytes` bigint NOT NULL COMMENT 'File size in bytes',
  `sha256` varchar(64) NOT NULL COMMENT 'File content SHA-256',
  `ordinal` int NOT NULL COMMENT 'Stable order within the scope',
  `status` varchar(32) NOT NULL COMMENT 'File lifecycle status',
  `inspection_json` longtext DEFAULT NULL COMMENT 'Private inspection metadata JSON',
  `error_code` varchar(64) DEFAULT NULL COMMENT 'Private processing error code',
  `error_message` text DEFAULT NULL COMMENT 'Private processing error message',
  `source_file_id` varchar(64) DEFAULT NULL COMMENT 'Source file ID for task lineage',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Record creation time',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Record update time',
  PRIMARY KEY (`id`),
  CONSTRAINT `ck_session_file_scope` CHECK ((`session_id` IS NULL) <> (`task_id` IS NULL)),
  UNIQUE KEY `uk_session_file_file_id` (`file_id`),
  KEY `idx_session_file_owner_session` (`owner_id`,`session_id`,`ordinal`),
  KEY `idx_session_file_owner_task` (`owner_id`,`task_id`,`ordinal`),
  KEY `idx_session_file_sha256` (`owner_id`,`sha256`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Session file metadata table';
