-- From 0.8.2 to 0.8.3, we have the following changes:
USE dbgpt;

-- v0.8.3: Report/evidence persistence (execution lineage, not model reasoning)
CREATE TABLE IF NOT EXISTS `dbgpt_report` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT 'Auto increment id',
  `report_id` varchar(64) NOT NULL COMMENT 'Stable report identifier',
  `owner_id` varchar(255) NOT NULL COMMENT 'Owning user ID',
  `title` varchar(512) NOT NULL COMMENT 'Latest report title',
  `conv_uid` varchar(255) NOT NULL COMMENT 'Source conversation ID',
  `latest_run_id` varchar(64) NOT NULL COMMENT 'Latest immutable run ID',
  `latest_revision` int NOT NULL COMMENT 'Latest report revision',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Record creation time',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Record update time',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_report_owner_report` (`owner_id`,`report_id`),
  KEY `idx_report_owner_updated` (`owner_id`,`updated_at`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Owner-scoped report identity';

CREATE TABLE IF NOT EXISTS `dbgpt_report_run` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT 'Auto increment id',
  `run_id` varchar(64) NOT NULL COMMENT 'Immutable report run ID',
  `report_id` varchar(64) NOT NULL COMMENT 'Stable report identifier',
  `owner_id` varchar(255) NOT NULL COMMENT 'Owning user ID',
  `revision` int NOT NULL COMMENT 'Monotonic report revision',
  `schema_version` int NOT NULL COMMENT 'Report protocol schema version',
  `trigger_type` varchar(32) NOT NULL DEFAULT 'interactive' COMMENT 'Run trigger type',
  `parent_run_id` varchar(64) DEFAULT NULL COMMENT 'Parent run for refresh or replay',
  `status` varchar(32) NOT NULL DEFAULT 'completed' COMMENT 'Persisted run status',
  `document_json` longtext NOT NULL COMMENT 'Lossless ReportDocument JSON',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Run creation time',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_report_run_id` (`run_id`),
  UNIQUE KEY `uk_report_run_owner_report_revision` (`owner_id`,`report_id`,`revision`),
  KEY `idx_report_run_owner_report_created` (`owner_id`,`report_id`,`id`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Immutable report snapshots';

CREATE TABLE IF NOT EXISTS `dbgpt_report_artifact` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT 'Auto increment id',
  `run_id` varchar(64) NOT NULL COMMENT 'Immutable report run ID',
  `artifact_id` varchar(128) NOT NULL COMMENT 'Artifact ID within the run',
  `artifact_type` varchar(32) NOT NULL COMMENT 'Protocol artifact discriminator',
  `conv_uid` varchar(255) NOT NULL COMMENT 'Producing conversation ID',
  `step_id` varchar(255) NOT NULL COMMENT 'Producing execution step ID',
  `message_id` varchar(255) DEFAULT NULL COMMENT 'Producing message ID',
  `task_id` varchar(64) DEFAULT NULL COMMENT 'Producing scheduled task ID',
  `execution_run_id` varchar(64) DEFAULT NULL COMMENT 'Producing execution run ID',
  `artifact_json` longtext NOT NULL COMMENT 'Lossless artifact JSON',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_report_artifact_run_artifact` (`run_id`,`artifact_id`),
  KEY `idx_report_artifact_execution` (`conv_uid`,`step_id`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Report artifact query index';

CREATE TABLE IF NOT EXISTS `dbgpt_report_artifact_dependency` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT 'Auto increment id',
  `run_id` varchar(64) NOT NULL COMMENT 'Immutable report run ID',
  `artifact_id` varchar(128) NOT NULL COMMENT 'Dependent artifact ID',
  `input_artifact_id` varchar(128) NOT NULL COMMENT 'Input artifact ID',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_report_artifact_dependency` (`run_id`,`artifact_id`,`input_artifact_id`),
  KEY `idx_report_artifact_dependency_input` (`run_id`,`input_artifact_id`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Artifact execution lineage edges';

CREATE TABLE IF NOT EXISTS `dbgpt_report_evidence` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT 'Auto increment id',
  `run_id` varchar(64) NOT NULL COMMENT 'Immutable report run ID',
  `section_id` varchar(128) NOT NULL COMMENT 'Report section ID',
  `block_id` varchar(128) NOT NULL COMMENT 'Report block ID',
  `ordinal` int NOT NULL COMMENT 'Evidence order within the block',
  `artifact_id` varchar(128) NOT NULL COMMENT 'Referenced artifact ID',
  `role` varchar(32) NOT NULL COMMENT 'Evidence role',
  `selector_json` longtext NOT NULL COMMENT 'Artifact source selector JSON',
  `target_selector_json` longtext NOT NULL COMMENT 'Report target selector JSON',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_report_evidence_ordinal` (`run_id`,`block_id`,`ordinal`),
  KEY `idx_report_evidence_artifact` (`run_id`,`artifact_id`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Report block evidence bindings';
