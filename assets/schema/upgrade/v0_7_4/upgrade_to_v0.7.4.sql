-- From 0.7.1 to 0.7.4, we have the following changes:
USE dbgpt;

-- evaluate_manage, Store the dataset benchmark task record
CREATE TABLE `evaluate_manage` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT 'autoincrement id',
  `evaluate_code` varchar(256) NOT NULL COMMENT 'evaluate unique code',
  `scene_key` varchar(100)  DEFAULT NULL COMMENT 'scene key',
  `scene_value` varchar(256) DEFAULT NULL COMMENT 'scene value',
  `context` text DEFAULT NULL COMMENT 'context',
  `evaluate_metrics` varchar(599) DEFAULT NULL COMMENT 'evaluate metrics',
  `datasets_name` varchar(256) DEFAULT NULL COMMENT 'datasets name',
  `datasets` text DEFAULT NULL COMMENT 'datasets content',
  `storage_type` varchar(256) DEFAULT NULL COMMENT 'result storage type',
  `parallel_num` int DEFAULT NULL COMMENT 'execute parallel thread number',
  `state` VARCHAR(100) DEFAULT NULL COMMENT 'execute state',
  `result` text DEFAULT NULL COMMENT 'evaluate result',
  `log_info` text DEFAULT NULL COMMENT 'evaluate error log',
  `average_score` text DEFAULT NULL COMMENT 'metrics average score',
  `user_id` varchar(100) DEFAULT NULL COMMENT 'user id',
  `user_name` varchar(128) DEFAULT NULL COMMENT 'user name',
  `sys_code` varchar(128) DEFAULT NULL COMMENT 'system code',
  `gmt_create` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'benchmark create time',
  `gmt_modified` TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'benchmark finish time',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_evaluate` (`evaluate_code`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- benchmark_summary, Store the dataset benchmark summary metric result
CREATE TABLE `benchmark_summary` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT 'autoincrement id',
  `round_id` int NOT NULL COMMENT 'task round id',
  `output_path` varchar(512)  NULL COMMENT 'output file path',
  `right` int DEFAULT NULL COMMENT 'right number',
  `wrong` int DEFAULT NULL COMMENT 'wrong number',
  `failed` int DEFAULT NULL COMMENT 'failed number',
  `exception` int DEFAULT NULL COMMENT 'exception number',
  `llm_code` varchar(256) DEFAULT NULL COMMENT 'benchmark llm code',
  `evaluate_code` varchar(256) DEFAULT NULL COMMENT 'benchmark evaluate code',
  `gmt_created` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'benchmark create time',
  `gmt_modified` TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'benchmark finish time',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
