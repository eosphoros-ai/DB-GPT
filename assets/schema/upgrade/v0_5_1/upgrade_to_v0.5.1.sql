USE dbgpt;
ALTER TABLE  dbgpt_serve_flow
    ADD COLUMN `error_message` varchar(512) null comment 'Error message' after `state`;
