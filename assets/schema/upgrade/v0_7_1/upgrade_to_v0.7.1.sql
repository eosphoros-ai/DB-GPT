-- From 0.7.0 to 0.7.1, we have the following changes:
USE dbgpt;

-- Change message_detail column type from text to longtext in chat_history_message table
ALTER TABLE `gpts_messages`
    MODIFY COLUMN `action_report` longtext COMMENT 'Current conversation action report';

ALTER TABLE `dbgpt_serve_flow`
    MODIFY COLUMN `flow_data` longtext null COMMENT 'Flow data, JSON format';