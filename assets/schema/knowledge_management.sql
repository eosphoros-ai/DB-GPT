CREATE TABLE `knowledge_space` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT 'auto increment id',
  `name` varchar(100) NOT NULL COMMENT 'knowledge space name',
  `vector_type` varchar(50) NOT NULL COMMENT 'vector type',
  `desc` varchar(500) NOT NULL COMMENT 'description',
  `owner` varchar(100) DEFAULT NULL COMMENT 'owner',
  `gmt_created` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'created time',
  `gmt_modified` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'update time',
  PRIMARY KEY (`id`),
  KEY `idx_name` (`name`) COMMENT 'index:idx_name'
) ENGINE=InnoDB AUTO_INCREMENT=100001 DEFAULT CHARSET=utf8mb4 COMMENT='knowledge space table';

CREATE TABLE `knowledge_document` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT 'auto increment id',
  `doc_name` varchar(100) NOT NULL COMMENT 'document path name',
  `doc_type` varchar(50) NOT NULL COMMENT 'doc type',
  `space` varchar(50) NOT NULL COMMENT 'knowledge space',
  `chunk_size` int NOT NULL COMMENT 'chunk size',
  `last_sync` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'last sync time',
  `status` varchar(50) NOT NULL COMMENT 'status TODO,RUNNING,FAILED,FINISHED',
  `content` LONGTEXT NOT NULL COMMENT 'knowledge embedding sync result',
  `result` TEXT NULL COMMENT 'knowledge content',
  `vector_ids` LONGTEXT NULL COMMENT 'vector_ids',
  `gmt_created` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'created time',
  `gmt_modified` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'update time',
  PRIMARY KEY (`id`),
  KEY `idx_doc_name` (`doc_name`) COMMENT 'index:idx_doc_name'
) ENGINE=InnoDB AUTO_INCREMENT=100001 DEFAULT CHARSET=utf8mb4 COMMENT='knowledge document table';

CREATE TABLE `document_chunk` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT 'auto increment id',
  `doc_name` varchar(100) NOT NULL COMMENT 'document path name',
  `doc_type` varchar(50) NOT NULL COMMENT 'doc type',
  `document_id` int NOT NULL COMMENT 'document parent id',
  `content` longtext NOT NULL COMMENT 'chunk content',
  `meta_info` varchar(200) NOT NULL COMMENT 'metadata info',
  `gmt_created` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'created time',
  `gmt_modified` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'update time',
  PRIMARY KEY (`id`),
  KEY `idx_document_id` (`document_id`) COMMENT 'index:document_id'
) ENGINE=InnoDB AUTO_INCREMENT=100001 DEFAULT CHARSET=utf8mb4 COMMENT='knowledge document chunk detail'