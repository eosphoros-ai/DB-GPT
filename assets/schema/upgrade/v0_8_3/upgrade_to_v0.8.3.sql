-- One-time upgrade from the upstream v0.8.2 schema to v0.8.3.
-- Back up first; for a fresh database use v0.8.3.sql instead.
-- Change dbgpt below if your metadata database has another name.
USE dbgpt;

ALTER TABLE `dbgpt_serve_scheduled_task` ADD COLUMN `owner_id` varchar(255) DEFAULT NULL;
ALTER TABLE `dbgpt_serve_scheduled_task` ADD COLUMN `resource_type` varchar(64) DEFAULT NULL;
ALTER TABLE `dbgpt_serve_scheduled_task` ADD COLUMN `resource_id` varchar(128) DEFAULT NULL;
ALTER TABLE `dbgpt_serve_scheduled_task` ADD COLUMN `lease_owner` varchar(64) DEFAULT NULL;
ALTER TABLE `dbgpt_serve_scheduled_task` ADD COLUMN `lease_expires_at` datetime DEFAULT NULL;
ALTER TABLE `dbgpt_serve_scheduled_task` ADD INDEX `ix_dbgpt_serve_scheduled_task_owner_id` (`owner_id`);
ALTER TABLE `dbgpt_serve_scheduled_task` ADD INDEX `ix_dbgpt_serve_scheduled_task_resource_type` (`resource_type`);
ALTER TABLE `dbgpt_serve_scheduled_task` ADD INDEX `ix_dbgpt_serve_scheduled_task_resource_id` (`resource_id`);
ALTER TABLE `dbgpt_serve_scheduled_task` ADD INDEX `ix_dbgpt_serve_scheduled_task_lease_expires_at` (`lease_expires_at`);
ALTER TABLE `dbgpt_serve_scheduled_run` ADD COLUMN `output_resource_id` varchar(255) DEFAULT NULL;
ALTER TABLE `dbgpt_serve_scheduled_run` ADD COLUMN `attempt_count` int NOT NULL DEFAULT 1;
ALTER TABLE `dbgpt_serve_scheduled_run` ADD COLUMN `result_json` longtext DEFAULT NULL;
ALTER TABLE `dbgpt_serve_scheduled_run` ADD COLUMN `idempotency_key` varchar(128) DEFAULT NULL;
ALTER TABLE `dbgpt_serve_scheduled_run` ADD UNIQUE INDEX `uk_scheduled_run_idempotency` (`task_id`, `idempotency_key`);
ALTER TABLE `chat_history_message` ADD COLUMN `trace_id` varchar(128) DEFAULT NULL;
ALTER TABLE `chat_history_message` ADD INDEX `ix_chat_history_message_trace_id` (`trace_id`);

CREATE TABLE IF NOT EXISTS dbgpt_dashboard (
	id VARCHAR(64) NOT NULL,
	owner_id VARCHAR(255) NOT NULL,
	conversation_id VARCHAR(255),
	source_turn_id VARCHAR(64),
	origin VARCHAR(32) NOT NULL,
	asset_state VARCHAR(32) NOT NULL,
	saved_at DATETIME,
	title VARCHAR(255) NOT NULL,
	description TEXT,
	data_source_id VARCHAR(255) NOT NULL,
	schema_json LONGTEXT NOT NULL,
	current_revision INTEGER NOT NULL,
	status VARCHAR(32) NOT NULL,
	public_slug VARCHAR(64),
	gmt_created DATETIME NOT NULL,
	gmt_modified DATETIME NOT NULL,
	PRIMARY KEY (id),
	KEY `ix_dbgpt_dashboard_asset_state` (`asset_state`),
	KEY `ix_dbgpt_dashboard_conversation_id` (`conversation_id`),
	KEY `ix_dbgpt_dashboard_origin` (`origin`),
	KEY `ix_dbgpt_dashboard_owner_id` (`owner_id`),
	UNIQUE KEY `ix_dbgpt_dashboard_public_slug` (`public_slug`),
	KEY `ix_dbgpt_dashboard_saved_at` (`saved_at`),
	KEY `ix_dbgpt_dashboard_source_turn_id` (`source_turn_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS dbgpt_dashboard_annotation (
	id VARCHAR(64) NOT NULL,
	dashboard_id VARCHAR(64) NOT NULL,
	actor_id VARCHAR(255) NOT NULL,
	conversation_id VARCHAR(255),
	source_turn_id VARCHAR(64),
	base_revision INTEGER NOT NULL,
	target_json LONGTEXT NOT NULL,
	prompt LONGTEXT NOT NULL,
	intent VARCHAR(32) NOT NULL DEFAULT 'modify',
	status VARCHAR(32) NOT NULL,
	proposal_json LONGTEXT,
	resolved_at DATETIME,
	gmt_created DATETIME NOT NULL,
	gmt_modified DATETIME NOT NULL,
	PRIMARY KEY (id),
	KEY `ix_dbgpt_dashboard_annotation_actor_id` (`actor_id`),
	KEY `ix_dbgpt_dashboard_annotation_base_revision` (`base_revision`),
	KEY `ix_dbgpt_dashboard_annotation_conversation_id` (`conversation_id`),
	KEY `ix_dbgpt_dashboard_annotation_dashboard_id` (`dashboard_id`),
	KEY `ix_dbgpt_dashboard_annotation_gmt_created` (`gmt_created`),
	KEY `ix_dbgpt_dashboard_annotation_resolved_at` (`resolved_at`),
	KEY `ix_dbgpt_dashboard_annotation_source_turn_id` (`source_turn_id`),
	KEY `ix_dbgpt_dashboard_annotation_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS dbgpt_dashboard_audit (
	id BIGINT NOT NULL AUTO_INCREMENT,
	dashboard_id VARCHAR(64) NOT NULL,
	actor_id VARCHAR(255) NOT NULL,
	action VARCHAR(64) NOT NULL,
	target_type VARCHAR(64) NOT NULL,
	target_id VARCHAR(255),
	details_json LONGTEXT NOT NULL,
	request_id VARCHAR(64),
	gmt_created DATETIME NOT NULL,
	PRIMARY KEY (id),
	KEY `ix_dbgpt_dashboard_audit_action` (`action`),
	KEY `ix_dbgpt_dashboard_audit_actor_id` (`actor_id`),
	KEY `ix_dbgpt_dashboard_audit_dashboard_id` (`dashboard_id`),
	KEY `ix_dbgpt_dashboard_audit_gmt_created` (`gmt_created`),
	KEY `ix_dbgpt_dashboard_audit_request_id` (`request_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS dbgpt_dashboard_cover (
	owner_id VARCHAR(255) NOT NULL,
	dashboard_id VARCHAR(64) NOT NULL,
	revision INTEGER NOT NULL,
	image LONGTEXT NOT NULL,
	captured_at DATETIME NOT NULL,
	PRIMARY KEY (owner_id, dashboard_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS dbgpt_dashboard_edit_version (
	id BIGINT NOT NULL AUTO_INCREMENT,
	dashboard_id VARCHAR(64) NOT NULL,
	revision INTEGER NOT NULL,
	schema_json LONGTEXT NOT NULL,
	source VARCHAR(64) NOT NULL,
	actor_id VARCHAR(255) NOT NULL,
	operation_id VARCHAR(64),
	gmt_created DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uk_dashboard_edit_version UNIQUE (dashboard_id, revision),
	KEY `ix_dbgpt_dashboard_edit_version_actor_id` (`actor_id`),
	KEY `ix_dbgpt_dashboard_edit_version_dashboard_id` (`dashboard_id`),
	KEY `ix_dbgpt_dashboard_edit_version_gmt_created` (`gmt_created`),
	KEY `ix_dbgpt_dashboard_edit_version_operation_id` (`operation_id`),
	KEY `ix_dbgpt_dashboard_edit_version_source` (`source`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS dbgpt_dashboard_folder (
	id VARCHAR(64) NOT NULL,
	owner_id VARCHAR(255) NOT NULL,
	name VARCHAR(80) NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uk_dashboard_folder_name UNIQUE (owner_id, name),
	KEY `ix_dbgpt_dashboard_folder_owner_id` (`owner_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS dbgpt_dashboard_folder_item (
	owner_id VARCHAR(255) NOT NULL,
	dashboard_id VARCHAR(64) NOT NULL,
	folder_id VARCHAR(64) NOT NULL,
	PRIMARY KEY (owner_id, dashboard_id),
	KEY `ix_dbgpt_dashboard_folder_item_folder_id` (`folder_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS dbgpt_dashboard_live_share (
	dashboard_id VARCHAR(64) NOT NULL,
	token_hash VARCHAR(64) NOT NULL,
	owner_id VARCHAR(255) NOT NULL,
	revision INTEGER NOT NULL,
	schema_json LONGTEXT NOT NULL,
	cache_json LONGTEXT NOT NULL,
	gmt_created DATETIME NOT NULL,
	last_attempt_at DATETIME NOT NULL,
	expires_at DATETIME NOT NULL,
	revoked_at DATETIME,
	PRIMARY KEY (dashboard_id),
	UNIQUE (token_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS dbgpt_dashboard_member (
	id INTEGER NOT NULL AUTO_INCREMENT,
	dashboard_id VARCHAR(64) NOT NULL,
	principal_id VARCHAR(255) NOT NULL,
	`role` VARCHAR(32) NOT NULL,
	created_by VARCHAR(255) NOT NULL,
	gmt_created DATETIME NOT NULL,
	gmt_modified DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uk_dashboard_member_principal UNIQUE (dashboard_id, principal_id),
	KEY `ix_dbgpt_dashboard_member_dashboard_id` (`dashboard_id`),
	KEY `ix_dbgpt_dashboard_member_principal_id` (`principal_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS dbgpt_dashboard_operation (
	id BIGINT NOT NULL AUTO_INCREMENT,
	dashboard_id VARCHAR(64) NOT NULL,
	operation_id VARCHAR(64) NOT NULL,
	client_id VARCHAR(128) NOT NULL,
	actor_id VARCHAR(255) NOT NULL,
	base_revision INTEGER NOT NULL,
	applied_revision INTEGER NOT NULL,
	patch_json LONGTEXT NOT NULL,
	gmt_created DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uk_dashboard_operation_id UNIQUE (dashboard_id, operation_id),
	CONSTRAINT uk_dashboard_operation_revision UNIQUE (dashboard_id, applied_revision),
	KEY `ix_dbgpt_dashboard_operation_actor_id` (`actor_id`),
	KEY `ix_dbgpt_dashboard_operation_client_id` (`client_id`),
	KEY `ix_dbgpt_dashboard_operation_dashboard_id` (`dashboard_id`),
	KEY `ix_dbgpt_dashboard_operation_gmt_created` (`gmt_created`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS dbgpt_dashboard_revision (
	id INTEGER NOT NULL AUTO_INCREMENT,
	dashboard_id VARCHAR(64) NOT NULL,
	revision INTEGER NOT NULL,
	schema_json LONGTEXT NOT NULL,
	snapshot_json LONGTEXT NOT NULL,
	validation_json LONGTEXT NOT NULL,
	share_token_hash VARCHAR(64) NOT NULL,
	gmt_published DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uk_dashboard_published_revision UNIQUE (dashboard_id, revision),
	CONSTRAINT uk_dashboard_share_token_hash UNIQUE (share_token_hash),
	KEY `ix_dbgpt_dashboard_revision_dashboard_id` (`dashboard_id`),
	KEY `ix_dbgpt_dashboard_revision_share_token_hash` (`share_token_hash`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS dbgpt_dashboard_share (
	id INTEGER NOT NULL AUTO_INCREMENT,
	dashboard_id VARCHAR(64) NOT NULL,
	revision INTEGER NOT NULL,
	token_hash VARCHAR(64) NOT NULL,
	created_by VARCHAR(255) NOT NULL,
	expires_at DATETIME,
	revoked_at DATETIME,
	gmt_created DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uk_dashboard_share_token UNIQUE (token_hash),
	KEY `ix_dbgpt_dashboard_share_created_by` (`created_by`),
	KEY `ix_dbgpt_dashboard_share_dashboard_id` (`dashboard_id`),
	KEY `ix_dbgpt_dashboard_share_expires_at` (`expires_at`),
	KEY `ix_dbgpt_dashboard_share_revision` (`revision`),
	KEY `ix_dbgpt_dashboard_share_revoked_at` (`revoked_at`),
	KEY `ix_dbgpt_dashboard_share_token_hash` (`token_hash`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS dbgpt_dashboard_share_secret (
	token_hash VARCHAR(64) NOT NULL,
	ciphertext VARCHAR(512) NOT NULL,
	PRIMARY KEY (token_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS dbgpt_uploaded_dataset (
	dataset_id VARCHAR(64) NOT NULL,
	owner_id VARCHAR(255) NOT NULL,
	conversation_id VARCHAR(255) NOT NULL,
	database_name VARCHAR(255) NOT NULL,
	database_path TEXT NOT NULL,
	batch_dir TEXT NOT NULL,
	manifest_json LONGTEXT NOT NULL,
	relationships_json LONGTEXT NOT NULL,
	status VARCHAR(32) NOT NULL,
	error_message TEXT,
	gmt_created DATETIME NOT NULL,
	gmt_modified DATETIME NOT NULL,
	PRIMARY KEY (dataset_id),
	KEY `ix_dbgpt_uploaded_dataset_conversation_id` (`conversation_id`),
	UNIQUE KEY `ix_dbgpt_uploaded_dataset_database_name` (`database_name`),
	KEY `ix_dbgpt_uploaded_dataset_owner_id` (`owner_id`),
	KEY `ix_dbgpt_uploaded_dataset_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

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
