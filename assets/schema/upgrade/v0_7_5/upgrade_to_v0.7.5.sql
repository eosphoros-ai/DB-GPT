-- From 0.7.4 to 0.7.5, we have the following changes:
USE dbgpt;
ALTER TABLE gpts_messages ADD COLUMN `conv_session_id` varchar(255) DEFAULT NULL COMMENT 'The unique id of the conversation record';
ALTER TABLE gpts_messages ADD COLUMN `message_id` varchar(255) DEFAULT NULL COMMENT 'The unique id of the messages';
ALTER TABLE gpts_messages ADD COLUMN `sender_name` varchar(255) DEFAULT NULL COMMENT 'Who(name) speaking in the current conversation turn';
ALTER TABLE gpts_messages ADD COLUMN `receiver_name` varchar(255) DEFAULT NULL COMMENT 'Who(name) receive message in the current conversation turn';
ALTER TABLE gpts_messages ADD COLUMN `thinking` LONGTEXT DEFAULT NULL COMMENT 'Thinking of the speech';
ALTER TABLE gpts_messages ADD COLUMN `system_prompt` LONGTEXT DEFAULT NULL COMMENT 'this message system prompt';
ALTER TABLE gpts_messages ADD COLUMN `user_prompt` LONGTEXT DEFAULT NULL COMMENT 'this message user prompt';
ALTER TABLE gpts_messages ADD COLUMN `show_message` tinyint(1) DEFAULT 1 COMMENT '"Whether the current message needs to be displayed to the user';
ALTER TABLE gpts_messages ADD COLUMN `goal_id` varchar(255) DEFAULT NULL COMMENT 'The target id to the current message';
ALTER TABLE gpts_messages ADD COLUMN `avatar` varchar(255) DEFAULT NULL COMMENT 'The avatar of the agent who send current message content';
-- todo: gpts_messages: created_at(gmt_create)  updated_at(gmt_modified)

ALTER TABLE gpts_conversations ADD COLUMN `conv_session_id` varchar(255) DEFAULT NULL COMMENT 'The unique id of the conversation record';
ALTER TABLE gpts_conversations ADD COLUMN `vis_render` varchar(255) DEFAULT NULL COMMENT 'vis mode of chat conversation';
-- todo: gpts_conversations: created_at(gmt_create)  updated_at(gmt_modified)

ALTER TABLE gpts_plans ADD COLUMN `conv_session_id` varchar(255) DEFAULT NULL COMMENT 'The unique id of the conversation record';
ALTER TABLE gpts_plans ADD COLUMN `task_uid` varchar(255) DEFAULT NULL COMMENT 'The uid of the plan task';
ALTER TABLE gpts_plans ADD COLUMN `conv_round` varchar(255) DEFAULT NULL COMMENT 'The dialogue turns';
ALTER TABLE gpts_plans ADD COLUMN `conv_round_id` varchar(255) DEFAULT NULL COMMENT 'The dialogue turns uid';
ALTER TABLE gpts_plans ADD COLUMN `sub_task_id` varchar(255) DEFAULT NULL COMMENT 'Subtask id';
ALTER TABLE gpts_plans ADD COLUMN `task_parent` varchar(255) DEFAULT NULL COMMENT 'Subtask parent task id';
-- todo: gpts_plans: created_at(gmt_create)  updated_at(gmt_modified)
