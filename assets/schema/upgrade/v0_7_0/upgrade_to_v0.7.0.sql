-- From 0.6.3 to 0.7.0, we have the following changes:
USE dbgpt;

-- connect_config
ALTER TABLE `connect_config`
    ADD COLUMN `gmt_created` datetime DEFAULT CURRENT_TIMESTAMP COMMENT 'Record creation time',
    ADD COLUMN `gmt_modified` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Record update time',
    ADD COLUMN `ext_config` text COMMENT 'Extended configuration, json format';