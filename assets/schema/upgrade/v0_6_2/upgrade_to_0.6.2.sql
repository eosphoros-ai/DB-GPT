USE dbgpt;

-- Modify sys_code column to be nullable in gpts_app_collection table
ALTER TABLE `gpts_app_collection`
MODIFY COLUMN `sys_code` varchar(255) NULL COMMENT 'system app code';

-- Change app_code to NOT NULL and sys_code to nullable in recommend_question table
ALTER TABLE `recommend_question`
MODIFY COLUMN `app_code` varchar(255) NOT NULL COMMENT 'Current AI assistant code',
MODIFY COLUMN `sys_code` varchar(255) NULL COMMENT 'system app code';

-- Change app_code to NOT NULL in user_recent_apps table
ALTER TABLE `user_recent_apps`
MODIFY COLUMN `app_code` varchar(255) NOT NULL COMMENT 'AI assistant code';