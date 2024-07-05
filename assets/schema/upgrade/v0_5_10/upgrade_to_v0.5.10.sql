USE dbgpt;
ALTER TABLE  knowledge_space
    ADD COLUMN `field_type` varchar(50) null comment 'space field type' after `vector_type`;