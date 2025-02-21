USE dbgpt;

-- Modify doc_token column to be nullable in knowledge_document table
ALTER TABLE `knowledge_document`
MODIFY COLUMN `doc_token` varchar(100) NULL COMMENT 'doc token';

-- Change meta_info column type from varchar(200) to text in document_chunk table
ALTER TABLE `document_chunk`
MODIFY COLUMN `meta_info` text NOT NULL COMMENT 'metadata info';

-- Change message_detail column type from text to longtext in chat_history_message table
ALTER TABLE `chat_history_message`
MODIFY COLUMN `message_detail` longtext COLLATE utf8mb4_unicode_ci COMMENT 'Message details, json format';