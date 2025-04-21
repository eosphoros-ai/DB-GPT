-- From 0.7.0 to 0.7.1, we have the following changes:
USE dbgpt;

-- Change message_detail column type from text to longtext in chat_history_message table
ALTER TABLE `gpts_messages`
     ADD COLUMN `message_id` varchar(255) NOT NULL DEFAULT '' COMMENT 'message id',
     ADD COLUMN `thinking` longtext DEFAULT NULL COMMENT 'llm thinking text',
     ADD COLUMN `show_message`  tinyint(4) DEFAULT NULL COMMENT 'Whether the current message needs to be displayed to the user',
     ADD COLUMN `sender_name` varchar(255) NOT NULL DEFAULT '' COMMENT 'Who(name) speaking in the current conversation turn',
     ADD COLUMN `receiver_name` varchar(255) NOT NULL DEFAULT '' COMMENT 'Who(name) receive message in the current conversation turn',
     ADD COLUMN `avatar` varchar(255) DEFAULT '' COMMENT 'Who(avatar) send message in the current conversation turn';



ALTER TABLE `gpts_plans`
    ADD COLUMN  conv_round  int(11) NOT NULL DEFAULT '0' COMMENT 'the current conversation turn number',
    ADD COLUMN  sub_task_id varchar(255) NOT NULL DEFAULT '' COMMENT 'the message task id',
    ADD COLUMN  task_parent varchar(255) DEFAULT '' COMMENT 'Subtask parent task i',
    ADD COLUMN  `action` text DEFAULT NULL COMMENT 'plan action',
    ADD COLUMN  `action_input` longtext DEFAULT NULL COMMENT 'plan action input',
    ADD COLUMN  `task_uid` varchar(255) NOT NULL DEFAULT '' COMMENT 'task uid';

ALTER TABLE `gpts_app_detail`
    ADD COLUMN  `type` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'bind agent type, default agent';


