-- From 0.8.1 to 0.8.2, we have the following changes:
USE dbgpt;

-- knowledge_space.index_methods, JSON string of selected index methods for agentic
ALTER TABLE `knowledge_space` ADD COLUMN `index_methods` varchar(500) DEFAULT NULL COMMENT 'JSON string of index methods' AFTER `context`;

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

-- code_graph_vertex, AST-extracted code nodes (classes, functions, modules, etc.)
CREATE TABLE IF NOT EXISTS `code_graph_vertex` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT 'Auto increment id',
  `knowledge_id` varchar(100) NOT NULL COMMENT 'Knowledge space ID',
  `vid` varchar(500) NOT NULL COMMENT 'Vertex unique ID within the knowledge space',
  `name` varchar(500) NOT NULL COMMENT 'Node name',
  `node_type` varchar(50) NOT NULL DEFAULT '' COMMENT 'Node type (class, function, module, etc.)',
  `source_file` varchar(500) DEFAULT '' COMMENT 'Source file path',
  `language` varchar(30) DEFAULT '' COMMENT 'Programming language',
  `community` varchar(50) DEFAULT '' COMMENT 'Community ID',
  `props` text DEFAULT NULL COMMENT 'Additional properties JSON',
  `gmt_create` datetime DEFAULT CURRENT_TIMESTAMP COMMENT 'Record creation time',
  `gmt_modified` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Record update time',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_cgv_knowledge_vid` (`knowledge_id`,`vid`),
  KEY `idx_cgv_knowledge_id` (`knowledge_id`),
  KEY `idx_cgv_name` (`name`),
  KEY `idx_cgv_node_type` (`node_type`),
  KEY `idx_cgv_source_file` (`source_file`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Code graph vertex table';

-- code_graph_edge, structural relationships (contains, calls, imports, etc.)
CREATE TABLE IF NOT EXISTS `code_graph_edge` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT 'Auto increment id',
  `knowledge_id` varchar(100) NOT NULL COMMENT 'Knowledge space ID',
  `sid` varchar(500) NOT NULL COMMENT 'Source vertex ID',
  `tid` varchar(500) NOT NULL COMMENT 'Target vertex ID',
  `edge_type` varchar(50) NOT NULL DEFAULT 'references' COMMENT 'Edge type (contains, calls, imports, etc.)',
  `confidence` varchar(20) DEFAULT 'EXTRACTED' COMMENT 'Edge confidence',
  `source_file` varchar(500) DEFAULT '' COMMENT 'Source file path',
  `source_location` varchar(30) DEFAULT '' COMMENT 'Source location in file',
  `props` text DEFAULT NULL COMMENT 'Additional properties JSON',
  `gmt_create` datetime DEFAULT CURRENT_TIMESTAMP COMMENT 'Record creation time',
  `gmt_modified` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Record update time',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_cge_edge` (`knowledge_id`,`sid`(255),`tid`(255),`edge_type`),
  KEY `idx_cge_knowledge_id` (`knowledge_id`),
  KEY `idx_cge_sid` (`sid`),
  KEY `idx_cge_tid` (`tid`),
  KEY `idx_cge_edge_type` (`edge_type`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Code graph edge table';

-- code_graph_meta, per-knowledge-space graph metadata (counts, build info)
CREATE TABLE IF NOT EXISTS `code_graph_meta` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT 'Auto increment id',
  `knowledge_id` varchar(100) NOT NULL COMMENT 'Knowledge space ID',
  `vertex_count` int DEFAULT 0 COMMENT 'Vertex count',
  `edge_count` int DEFAULT 0 COMMENT 'Edge count',
  `community_count` int DEFAULT 0 COMMENT 'Community count',
  `build_source` varchar(20) DEFAULT '' COMMENT 'Build source type',
  `repo_url` varchar(500) DEFAULT '' COMMENT 'Source repository URL',
  `branch` varchar(100) DEFAULT '' COMMENT 'Source repository branch',
  `build_status` varchar(20) DEFAULT 'completed' COMMENT 'Build status',
  `graph_version` int DEFAULT 1 COMMENT 'Graph version',
  `gmt_create` datetime DEFAULT CURRENT_TIMESTAMP COMMENT 'Record creation time',
  `gmt_modified` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Record update time',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_cgm_knowledge_id` (`knowledge_id`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Code graph metadata table';
