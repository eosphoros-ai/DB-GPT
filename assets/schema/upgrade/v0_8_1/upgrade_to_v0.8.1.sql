-- From 0.8.0 to 0.8.1, we have the following changes:
USE dbgpt;

ALTER TABLE gpts_messages MODIFY COLUMN content longtext COMMENT 'Content of the speech';
