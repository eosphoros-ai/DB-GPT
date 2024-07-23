USE dbgpt;
ALTER TABLE  knowledge_space
    ADD COLUMN `domain_type` varchar(50) null comment 'space domain type' after `vector_type`;