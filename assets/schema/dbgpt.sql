-- You can change `dbgpt` to your actual metadata database name in your `.env` file
-- eg. `LOCAL_DB_NAME=dbgpt`

CREATE
DATABASE IF NOT EXISTS dbgpt;
use dbgpt;

-- For alembic migration tool
CREATE TABLE IF NOT EXISTS `alembic_version`
(
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
) DEFAULT CHARSET=utf8mb4 ;

CREATE TABLE IF NOT EXISTS `knowledge_space`
(
    `id`           int          NOT NULL AUTO_INCREMENT COMMENT 'auto increment id',
    `name`         varchar(100) NOT NULL COMMENT 'knowledge space name',
    `vector_type`  varchar(50)  NOT NULL COMMENT 'vector type',
    `domain_type`  varchar(50)  NOT NULL COMMENT 'domain type',
    `desc`         varchar(500) NOT NULL COMMENT 'description',
    `owner`        varchar(100) DEFAULT NULL COMMENT 'owner',
    `context`      TEXT         DEFAULT NULL COMMENT 'context argument',
    `gmt_created`  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP COMMENT 'created time',
    `gmt_modified` TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'update time',
    PRIMARY KEY (`id`),
    KEY            `idx_name` (`name`) COMMENT 'index:idx_name'
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COMMENT='knowledge space table';

CREATE TABLE IF NOT EXISTS `knowledge_document`
(
    `id`           int          NOT NULL AUTO_INCREMENT COMMENT 'auto increment id',
    `doc_name`     varchar(100) NOT NULL COMMENT 'document path name',
    `doc_type`     varchar(50)  NOT NULL COMMENT 'doc type',
    `doc_token`    varchar(100) NULL COMMENT 'doc token',
    `space`        varchar(50)  NOT NULL COMMENT 'knowledge space',
    `chunk_size`   int          NOT NULL COMMENT 'chunk size',
    `last_sync`    TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'last sync time',
    `status`       varchar(50)  NOT NULL COMMENT 'status TODO,RUNNING,FAILED,FINISHED',
    `content`      LONGTEXT     NOT NULL COMMENT 'knowledge embedding sync result',
    `result`       TEXT NULL COMMENT 'knowledge content',
    `questions`    TEXT NULL COMMENT 'document related questions',
    `vector_ids`   LONGTEXT NULL COMMENT 'vector_ids',
    `summary`      LONGTEXT NULL COMMENT 'knowledge summary',
    `gmt_created`  TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'created time',
    `gmt_modified` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'update time',
    PRIMARY KEY (`id`),
    KEY            `idx_doc_name` (`doc_name`) COMMENT 'index:idx_doc_name'
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COMMENT='knowledge document table';

CREATE TABLE IF NOT EXISTS `document_chunk`
(
    `id`           int          NOT NULL AUTO_INCREMENT COMMENT 'auto increment id',
    `doc_name`     varchar(100) NOT NULL COMMENT 'document path name',
    `doc_type`     varchar(50)  NOT NULL COMMENT 'doc type',
    `document_id`  int          NOT NULL COMMENT 'document parent id',
    `content`      longtext     NOT NULL COMMENT 'chunk content',
    `questions`    text         NULL COMMENT 'chunk related questions',
    `meta_info`    text NOT NULL COMMENT 'metadata info',
    `gmt_created`  timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'created time',
    `gmt_modified` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'update time',
    PRIMARY KEY (`id`),
    KEY            `idx_document_id` (`document_id`) COMMENT 'index:document_id'
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COMMENT='knowledge document chunk detail';


CREATE TABLE IF NOT EXISTS `connect_config`
(
    `id`       int          NOT NULL AUTO_INCREMENT COMMENT 'autoincrement id',
    `db_type`  varchar(255) NOT NULL COMMENT 'db type',
    `db_name`  varchar(255) NOT NULL COMMENT 'db name',
    `db_path`  varchar(255) DEFAULT NULL COMMENT 'file db path',
    `db_host`  varchar(255) DEFAULT NULL COMMENT 'db connect host(not file db)',
    `db_port`  varchar(255) DEFAULT NULL COMMENT 'db cnnect port(not file db)',
    `db_user`  varchar(255) DEFAULT NULL COMMENT 'db user',
    `db_pwd`   varchar(255) DEFAULT NULL COMMENT 'db password',
    `comment`  text COMMENT 'db comment',
    `sys_code` varchar(128) DEFAULT NULL COMMENT 'System code',
    `user_name`  varchar(255) DEFAULT NULL COMMENT 'user name',
    `user_id`  varchar(255) DEFAULT NULL COMMENT 'user id',

    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_db` (`db_name`),
    KEY        `idx_q_db_type` (`db_type`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COMMENT 'Connection confi';

CREATE TABLE IF NOT EXISTS `chat_history`
(
    `id`        int                                     NOT NULL AUTO_INCREMENT COMMENT 'autoincrement id',
    `conv_uid`  varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Conversation record unique id',
    `chat_mode` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Conversation scene mode',
    `summary`   longtext COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Conversation record summary',
    `user_name` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'interlocutor',
    `messages`  text COLLATE utf8mb4_unicode_ci COMMENT 'Conversation details',
    `message_ids` text COLLATE utf8mb4_unicode_ci COMMENT 'Message id list, split by comma',
    `app_code` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'App unique code',
    `sys_code`  varchar(128)                            DEFAULT NULL COMMENT 'System code',
    `gmt_created`  timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'created time',
    `gmt_modified` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'update time',
    UNIQUE KEY `conv_uid` (`conv_uid`),
    PRIMARY KEY (`id`),
    KEY `idx_chat_his_app_code` (`app_code`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT 'Chat history';

CREATE TABLE IF NOT EXISTS `chat_history_message`
(
    `id`             int                                     NOT NULL AUTO_INCREMENT COMMENT 'autoincrement id',
    `conv_uid`       varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Conversation record unique id',
    `index`          int                                     NOT NULL COMMENT 'Message index',
    `round_index`    int                                     NOT NULL COMMENT 'Round of conversation',
    `message_detail` longtext COLLATE utf8mb4_unicode_ci COMMENT 'Message details, json format',
    `gmt_created`  timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'created time',
    `gmt_modified` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'update time',
    UNIQUE KEY `message_uid_index` (`conv_uid`, `index`),
    PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT 'Chat history message';


CREATE TABLE IF NOT EXISTS `chat_feed_back`
(
    `id`              bigint(20) NOT NULL AUTO_INCREMENT,
    `conv_uid`        varchar(128) DEFAULT NULL COMMENT 'Conversation ID',
    `conv_index`      int(4) DEFAULT NULL COMMENT 'Round of conversation',
    `score`           int(1) DEFAULT NULL COMMENT 'Score of user',
    `ques_type`       varchar(32)  DEFAULT NULL COMMENT 'User question category',
    `question`        longtext     DEFAULT NULL COMMENT 'User question',
    `knowledge_space` varchar(128) DEFAULT NULL COMMENT 'Knowledge space name',
    `messages`        longtext     DEFAULT NULL COMMENT 'The details of user feedback',
    `message_id`      varchar(255)  NULL COMMENT 'Message id',
    `feedback_type`   varchar(50)  NULL COMMENT 'Feedback type like or unlike',
    `reason_types`    varchar(255)  NULL COMMENT 'Feedback reason categories',
    `remark`          text          NULL COMMENT 'Feedback remark',
    `user_code`       varchar(128)  NULL COMMENT 'User code',
    `user_name`       varchar(128) DEFAULT NULL COMMENT 'User name',
    `gmt_created`     timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'created time',
    `gmt_modified`    timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'update time',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_conv` (`conv_uid`,`conv_index`),
    KEY               `idx_conv` (`conv_uid`,`conv_index`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COMMENT='User feedback table';


CREATE TABLE IF NOT EXISTS `my_plugin`
(
    `id`          int                                     NOT NULL AUTO_INCREMENT COMMENT 'autoincrement id',
    `tenant`      varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'user tenant',
    `user_code`   varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'user code',
    `user_name`   varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'user name',
    `name`        varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'plugin name',
    `file_name`   varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'plugin package file name',
    `type`        varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'plugin type',
    `version`     varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'plugin version',
    `use_count`   int                                     DEFAULT NULL COMMENT 'plugin total use count',
    `succ_count`  int                                     DEFAULT NULL COMMENT 'plugin total success count',
    `sys_code`    varchar(128)                            DEFAULT NULL COMMENT 'System code',
    `gmt_created` TIMESTAMP                               DEFAULT CURRENT_TIMESTAMP COMMENT 'plugin install time',
    PRIMARY KEY (`id`),
    UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='User plugin table';

CREATE TABLE IF NOT EXISTS `plugin_hub`
(
    `id`              int                                     NOT NULL AUTO_INCREMENT COMMENT 'autoincrement id',
    `name`            varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'plugin name',
    `description`     varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'plugin description',
    `author`          varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'plugin author',
    `email`           varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'plugin author email',
    `type`            varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'plugin type',
    `version`         varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'plugin version',
    `storage_channel` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'plugin storage channel',
    `storage_url`     varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'plugin download url',
    `download_param`  varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'plugin download param',
    `gmt_created`     TIMESTAMP                               DEFAULT CURRENT_TIMESTAMP COMMENT 'plugin upload time',
    `installed`       int                                     DEFAULT NULL COMMENT 'plugin already installed count',
    PRIMARY KEY (`id`),
    UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Plugin Hub table';


CREATE TABLE IF NOT EXISTS `prompt_manage`
(
    `id`             int(11) NOT NULL AUTO_INCREMENT,
    `chat_scene`     varchar(100) DEFAULT NULL COMMENT 'Chat scene',
    `sub_chat_scene` varchar(100) DEFAULT NULL COMMENT 'Sub chat scene',
    `prompt_type`    varchar(100) DEFAULT NULL COMMENT 'Prompt type: common or private',
    `prompt_name`    varchar(256) DEFAULT NULL COMMENT 'prompt name',
    `prompt_code`    varchar(256) DEFAULT NULL COMMENT 'prompt code',
    `content`        longtext COMMENT 'Prompt content',
    `input_variables` varchar(1024) DEFAULT NULL COMMENT 'Prompt input variables(split by comma))',
    `response_schema` text  DEFAULT NULL COMMENT 'Prompt response schema',
    `model` varchar(128) DEFAULT NULL COMMENT 'Prompt model name(we can use different models for different prompt)',
    `prompt_language` varchar(32) DEFAULT NULL COMMENT 'Prompt language(eg:en, zh-cn)',
    `prompt_format` varchar(32) DEFAULT 'f-string' COMMENT 'Prompt format(eg: f-string, jinja2)',
    `prompt_desc`    varchar(512) DEFAULT NULL COMMENT 'Prompt description',
    `user_code`     varchar(128) DEFAULT NULL COMMENT 'User code',
    `user_name`      varchar(128) DEFAULT NULL COMMENT 'User name',
    `sys_code`       varchar(128)                            DEFAULT NULL COMMENT 'System code',
    `gmt_created`    timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'created time',
    `gmt_modified`   timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'update time',
    PRIMARY KEY (`id`),
    UNIQUE KEY `prompt_name_uiq` (`prompt_name`, `sys_code`, `prompt_language`, `model`),
    KEY              `gmt_created_idx` (`gmt_created`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Prompt management table';



 CREATE TABLE IF NOT EXISTS `gpts_conversations` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT 'autoincrement id',
  `conv_id` varchar(255) NOT NULL COMMENT 'The unique id of the conversation record',
  `user_goal` text NOT NULL COMMENT 'User''s goals content',
  `gpts_name` varchar(255) NOT NULL COMMENT 'The gpts name',
  `state` varchar(255) DEFAULT NULL COMMENT 'The gpts state',
  `max_auto_reply_round` int(11) NOT NULL COMMENT 'max auto reply round',
  `auto_reply_count` int(11) NOT NULL COMMENT 'auto reply count',
  `user_code` varchar(255) DEFAULT NULL COMMENT 'user code',
  `sys_code` varchar(255) DEFAULT NULL COMMENT 'system app ',
  `created_at` datetime DEFAULT NULL COMMENT 'create time',
  `updated_at` datetime DEFAULT NULL COMMENT 'last update time',
  `team_mode` varchar(255) NULL COMMENT 'agent team work mode',

  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_gpts_conversations` (`conv_id`),
  KEY `idx_gpts_name` (`gpts_name`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COMMENT="gpt conversations";

CREATE TABLE IF NOT EXISTS `gpts_instance` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT 'autoincrement id',
  `gpts_name` varchar(255) NOT NULL COMMENT 'Current AI assistant name',
  `gpts_describe` varchar(2255) NOT NULL COMMENT 'Current AI assistant describe',
  `resource_db` text COMMENT 'List of structured database names contained in the current gpts',
  `resource_internet` text COMMENT 'Is it possible to retrieve information from the internet',
  `resource_knowledge` text COMMENT 'List of unstructured database names contained in the current gpts',
  `gpts_agents` varchar(1000) DEFAULT NULL COMMENT 'List of agents names contained in the current gpts',
  `gpts_models` varchar(1000) DEFAULT NULL COMMENT 'List of llm model names contained in the current gpts',
  `language` varchar(100) DEFAULT NULL COMMENT 'gpts language',
  `user_code` varchar(255) NOT NULL COMMENT 'user code',
  `sys_code` varchar(255) DEFAULT NULL COMMENT 'system app code',
  `created_at` datetime DEFAULT NULL COMMENT 'create time',
  `updated_at` datetime DEFAULT NULL COMMENT 'last update time',
  `team_mode` varchar(255) NOT NULL COMMENT 'Team work mode',
  `is_sustainable` tinyint(1) NOT NULL COMMENT 'Applications for sustainable dialogue',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_gpts` (`gpts_name`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COMMENT="gpts instance";

CREATE TABLE `gpts_messages` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT 'autoincrement id',
  `conv_id` varchar(255) NOT NULL COMMENT 'The unique id of the conversation record',
  `sender` varchar(255) NOT NULL COMMENT 'Who speaking in the current conversation turn',
  `receiver` varchar(255) NOT NULL COMMENT 'Who receive message in the current conversation turn',
  `model_name` varchar(255) DEFAULT NULL COMMENT 'message generate model',
  `rounds` int(11) NOT NULL COMMENT 'dialogue turns',
  `is_success` int(4)  NULL DEFAULT 0 COMMENT 'agent message is success',
  `app_code` varchar(255) NOT NULL COMMENT 'Current AI assistant code',
  `app_name` varchar(255) NOT NULL COMMENT 'Current AI assistant name',
  `content` text COMMENT 'Content of the speech',
  `current_goal` text COMMENT 'The target corresponding to the current message',
  `context` text COMMENT 'Current conversation context',
  `review_info` text COMMENT 'Current conversation review info',
  `action_report` text COMMENT 'Current conversation action report',
  `resource_info` text DEFAULT NULL  COMMENT 'Current conversation resource info',
  `role` varchar(255) DEFAULT NULL COMMENT 'The role of the current message content',
  `created_at` datetime DEFAULT NULL COMMENT 'create time',
  `updated_at` datetime DEFAULT NULL COMMENT 'last update time',
  PRIMARY KEY (`id`),
  KEY `idx_q_messages` (`conv_id`,`rounds`,`sender`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COMMENT="gpts message";


CREATE TABLE `gpts_plans` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT 'autoincrement id',
  `conv_id` varchar(255) NOT NULL COMMENT 'The unique id of the conversation record',
  `sub_task_num` int(11) NOT NULL COMMENT 'Subtask number',
  `sub_task_title` varchar(255) NOT NULL COMMENT 'subtask title',
  `sub_task_content` text NOT NULL COMMENT 'subtask content',
  `sub_task_agent` varchar(255) DEFAULT NULL COMMENT 'Available agents corresponding to subtasks',
  `resource_name` varchar(255) DEFAULT NULL COMMENT 'resource name',
  `rely` varchar(255) DEFAULT NULL COMMENT 'Subtask dependencies，like: 1,2,3',
  `agent_model` varchar(255) DEFAULT NULL COMMENT 'LLM model used by subtask processing agents',
  `retry_times` int(11) DEFAULT NULL COMMENT 'number of retries',
  `max_retry_times` int(11) DEFAULT NULL COMMENT 'Maximum number of retries',
  `state` varchar(255) DEFAULT NULL COMMENT 'subtask status',
  `result` longtext COMMENT 'subtask result',
  `created_at` datetime DEFAULT NULL COMMENT 'create time',
  `updated_at` datetime DEFAULT NULL COMMENT 'last update time',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_sub_task` (`conv_id`,`sub_task_num`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COMMENT="gpt plan";

-- dbgpt.dbgpt_serve_flow definition
CREATE TABLE `dbgpt_serve_flow` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT 'Auto increment id',
  `uid` varchar(128) NOT NULL COMMENT 'Unique id',
  `dag_id` varchar(128) DEFAULT NULL COMMENT 'DAG id',
  `name` varchar(128) DEFAULT NULL COMMENT 'Flow name',
  `flow_data` text COMMENT 'Flow data, JSON format',
  `user_name` varchar(128) DEFAULT NULL COMMENT 'User name',
  `sys_code` varchar(128) DEFAULT NULL COMMENT 'System code',
  `gmt_created` datetime DEFAULT NULL COMMENT 'Record creation time',
  `gmt_modified` datetime DEFAULT NULL COMMENT 'Record update time',
  `flow_category` varchar(64) DEFAULT NULL COMMENT 'Flow category',
  `description` varchar(512) DEFAULT NULL COMMENT 'Flow description',
  `state` varchar(32) DEFAULT NULL COMMENT 'Flow state',
  `error_message` varchar(512) NULL comment 'Error message',
  `source` varchar(64) DEFAULT NULL COMMENT 'Flow source',
  `source_url` varchar(512) DEFAULT NULL COMMENT 'Flow source url',
  `version` varchar(32) DEFAULT NULL COMMENT 'Flow version',
  `define_type` varchar(32) null comment 'Flow define type(json or python)',
  `label` varchar(128) DEFAULT NULL COMMENT 'Flow label',
  `editable` int DEFAULT NULL COMMENT 'Editable, 0: editable, 1: not editable',
  `variables` text DEFAULT NULL COMMENT 'Flow variables, JSON format',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_uid` (`uid`),
  KEY `ix_dbgpt_serve_flow_sys_code` (`sys_code`),
  KEY `ix_dbgpt_serve_flow_uid` (`uid`),
  KEY `ix_dbgpt_serve_flow_dag_id` (`dag_id`),
  KEY `ix_dbgpt_serve_flow_user_name` (`user_name`),
  KEY `ix_dbgpt_serve_flow_name` (`name`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- dbgpt.dbgpt_serve_file definition
CREATE TABLE `dbgpt_serve_file` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT 'Auto increment id',
  `bucket` varchar(255) NOT NULL COMMENT 'Bucket name',
  `file_id` varchar(255) NOT NULL COMMENT 'File id',
  `file_name` varchar(256) NOT NULL COMMENT 'File name',
  `file_size` int DEFAULT NULL COMMENT 'File size',
  `storage_type` varchar(32) NOT NULL COMMENT 'Storage type',
  `storage_path` varchar(512) NOT NULL COMMENT 'Storage path',
  `uri` varchar(512) NOT NULL COMMENT 'File URI',
  `custom_metadata` text DEFAULT NULL COMMENT 'Custom metadata, JSON format',
  `file_hash` varchar(128) DEFAULT NULL COMMENT 'File hash',
  `user_name` varchar(128) DEFAULT NULL COMMENT 'User name',
  `sys_code` varchar(128) DEFAULT NULL COMMENT 'System code',
  `gmt_created` datetime DEFAULT CURRENT_TIMESTAMP COMMENT 'Record creation time',
  `gmt_modified` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Record update time',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_bucket_file_id` (`bucket`, `file_id`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- dbgpt.dbgpt_serve_variables definition
CREATE TABLE `dbgpt_serve_variables` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT 'Auto increment id',
  `key` varchar(128) NOT NULL COMMENT 'Variable key',
  `name` varchar(128) DEFAULT NULL COMMENT 'Variable name',
  `label` varchar(128) DEFAULT NULL COMMENT 'Variable label',
  `value` text DEFAULT NULL COMMENT 'Variable value, JSON format',
  `value_type` varchar(32) DEFAULT NULL COMMENT 'Variable value type(string, int, float, bool)',
  `category` varchar(32) DEFAULT 'common' COMMENT 'Variable category(common or secret)',
  `encryption_method` varchar(32) DEFAULT NULL COMMENT 'Variable encryption method(fernet, simple, rsa, aes)',
  `salt` varchar(128) DEFAULT NULL COMMENT 'Variable salt',
  `scope` varchar(32) DEFAULT 'global' COMMENT 'Variable scope(global,flow,app,agent,datasource,flow_priv,agent_priv, ""etc)',
  `scope_key` varchar(256) DEFAULT NULL COMMENT 'Variable scope key, default is empty, for scope is "flow_priv", the scope_key is dag id of flow',
  `enabled` int DEFAULT 1 COMMENT 'Variable enabled, 0: disabled, 1: enabled',
  `description` text DEFAULT NULL COMMENT 'Variable description',
  `user_name` varchar(128) DEFAULT NULL COMMENT 'User name',
  `sys_code` varchar(128) DEFAULT NULL COMMENT 'System code',
  `gmt_created` datetime DEFAULT CURRENT_TIMESTAMP COMMENT 'Record creation time',
  `gmt_modified` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Record update time',
  PRIMARY KEY (`id`),
  KEY `ix_your_table_name_key` (`key`),
  KEY `ix_your_table_name_name` (`name`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- dbgpt.gpts_app definition
CREATE TABLE `gpts_app` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT 'autoincrement id',
  `app_code` varchar(255) NOT NULL COMMENT 'Current AI assistant code',
  `app_name` varchar(255) NOT NULL COMMENT 'Current AI assistant name',
  `app_describe` varchar(2255) NOT NULL COMMENT 'Current AI assistant describe',
  `language` varchar(100) NOT NULL COMMENT 'gpts language',
  `team_mode` varchar(255) NOT NULL COMMENT 'Team work mode',
  `team_context` text COMMENT 'The execution logic and team member content that teams with different working modes rely on',
  `user_code` varchar(255) DEFAULT NULL COMMENT 'user code',
  `sys_code` varchar(255) DEFAULT NULL COMMENT 'system app code',
  `created_at` datetime DEFAULT NULL COMMENT 'create time',
  `updated_at` datetime DEFAULT NULL COMMENT 'last update time',
  `icon` varchar(1024) DEFAULT NULL COMMENT 'app icon, url',
  `published` varchar(64) DEFAULT 'false' COMMENT 'Has it been published?',
  `param_need` text DEFAULT NULL COMMENT 'Parameter information supported by the application',
  `admins` text DEFAULT NULL COMMENT 'administrator',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_gpts_app` (`app_name`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `gpts_app_collection` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT 'autoincrement id',
  `app_code` varchar(255) NOT NULL COMMENT 'Current AI assistant code',
  `user_code` int(11) NOT NULL COMMENT 'user code',
  `sys_code` varchar(255) NULL COMMENT 'system app code',
  `created_at` datetime DEFAULT NULL COMMENT 'create time',
  `updated_at` datetime DEFAULT NULL COMMENT 'last update time',
  PRIMARY KEY (`id`),
  KEY `idx_app_code` (`app_code`),
  KEY `idx_user_code` (`user_code`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COMMENT="gpt collections";

-- dbgpt.gpts_app_detail definition
CREATE TABLE `gpts_app_detail` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT 'autoincrement id',
  `app_code` varchar(255) NOT NULL COMMENT 'Current AI assistant code',
  `app_name` varchar(255) NOT NULL COMMENT 'Current AI assistant name',
  `agent_name` varchar(255) NOT NULL COMMENT ' Agent name',
  `node_id` varchar(255) NOT NULL COMMENT 'Current AI assistant Agent Node id',
  `resources` text COMMENT 'Agent bind  resource',
  `prompt_template` text COMMENT 'Agent bind  template',
  `llm_strategy` varchar(25) DEFAULT NULL COMMENT 'Agent use llm strategy',
  `llm_strategy_value` text COMMENT 'Agent use llm strategy value',
  `created_at` datetime DEFAULT NULL COMMENT 'create time',
  `updated_at` datetime DEFAULT NULL COMMENT 'last update time',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_gpts_app_agent_node` (`app_name`,`agent_name`,`node_id`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- For deploy model cluster of DB-GPT(StorageModelRegistry)
CREATE TABLE IF NOT EXISTS `dbgpt_cluster_registry_instance` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT 'Auto increment id',
  `model_name` varchar(128) NOT NULL COMMENT 'Model name',
  `host` varchar(128) NOT NULL COMMENT 'Host of the model',
  `port` int(11) NOT NULL COMMENT 'Port of the model',
  `weight` float DEFAULT 1.0 COMMENT 'Weight of the model',
  `check_healthy` tinyint(1) DEFAULT 1 COMMENT 'Whether to check the health of the model',
  `healthy` tinyint(1) DEFAULT 0 COMMENT 'Whether the model is healthy',
  `enabled` tinyint(1) DEFAULT 1 COMMENT 'Whether the model is enabled',
  `prompt_template` varchar(128) DEFAULT NULL COMMENT 'Prompt template for the model instance',
  `last_heartbeat` datetime DEFAULT NULL COMMENT 'Last heartbeat time of the model instance',
  `user_name` varchar(128) DEFAULT NULL COMMENT 'User name',
  `sys_code` varchar(128) DEFAULT NULL COMMENT 'System code',
  `gmt_created` datetime DEFAULT CURRENT_TIMESTAMP COMMENT 'Record creation time',
  `gmt_modified` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Record update time',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_model_instance` (`model_name`, `host`, `port`, `sys_code`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COMMENT='Cluster model instance table, for registering and managing model instances';

-- dbgpt.recommend_question definition
CREATE TABLE `recommend_question` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT COMMENT 'autoincrement id',
  `gmt_create` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'create time',
  `gmt_modified` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'last update time',
  `app_code` varchar(255) NOT NULL COMMENT 'Current AI assistant code',
  `question` text DEFAULT NULL COMMENT 'question',
  `user_code` int(11) NOT NULL COMMENT 'user code',
  `sys_code` varchar(255) NULL COMMENT 'system app code',
  `valid` varchar(10) DEFAULT 'true' COMMENT 'is it effective，true/false',
  `chat_mode` varchar(255) DEFAULT NULL COMMENT 'Conversation scene mode，chat_knowledge...',
  `params` text DEFAULT NULL COMMENT 'question param',
  `is_hot_question` varchar(10) DEFAULT 'false' COMMENT 'Is it a popular recommendation question?',
  PRIMARY KEY (`id`),
  KEY `idx_rec_q_app_code` (`app_code`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT="AI application related recommendation issues";

-- dbgpt.user_recent_apps definition
CREATE TABLE `user_recent_apps` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT COMMENT 'autoincrement id',
  `gmt_create` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'create time',
  `gmt_modified` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'last update time',
  `app_code` varchar(255) NOT NULL COMMENT 'AI assistant code',
  `last_accessed` timestamp NULL DEFAULT NULL COMMENT 'User recent usage time',
  `user_code` varchar(255) DEFAULT NULL COMMENT 'user code',
  `sys_code` varchar(255) DEFAULT NULL COMMENT 'system app code',
  PRIMARY KEY (`id`),
  KEY `idx_user_r_app_code` (`app_code`),
  KEY `idx_last_accessed` (`last_accessed`),
  KEY `idx_user_code` (`user_code`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='User recently used apps';

-- dbgpt.dbgpt_serve_dbgpts_my definition
CREATE TABLE `dbgpt_serve_dbgpts_my` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT 'autoincrement id',
  `name` varchar(255)  NOT NULL COMMENT 'plugin name',
  `user_code` varchar(255)  DEFAULT NULL COMMENT 'user code',
  `user_name` varchar(255)  DEFAULT NULL COMMENT 'user name',
  `file_name` varchar(255)  NOT NULL COMMENT 'plugin package file name',
  `type` varchar(255)  DEFAULT NULL COMMENT 'plugin type',
  `version` varchar(255)  DEFAULT NULL COMMENT 'plugin version',
  `use_count` int DEFAULT NULL COMMENT 'plugin total use count',
  `succ_count` int DEFAULT NULL COMMENT 'plugin total success count',
  `sys_code` varchar(128) DEFAULT NULL COMMENT 'System code',
  `gmt_created` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'plugin install time',
  `gmt_modified` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'update time',
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`, `user_name`),
  KEY `ix_my_plugin_sys_code` (`sys_code`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- dbgpt.dbgpt_serve_dbgpts_hub definition
CREATE TABLE `dbgpt_serve_dbgpts_hub` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT 'autoincrement id',
  `name` varchar(255) NOT NULL COMMENT 'plugin name',
  `description` varchar(255)  NULL COMMENT 'plugin description',
  `author` varchar(255) DEFAULT NULL COMMENT 'plugin author',
  `email` varchar(255) DEFAULT NULL COMMENT 'plugin author email',
  `type` varchar(255) DEFAULT NULL COMMENT 'plugin type',
  `version` varchar(255) DEFAULT NULL COMMENT 'plugin version',
  `storage_channel` varchar(255) DEFAULT NULL COMMENT 'plugin storage channel',
  `storage_url` varchar(255) DEFAULT NULL COMMENT 'plugin download url',
  `download_param` varchar(255) DEFAULT NULL COMMENT 'plugin download param',
  `gmt_created` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'plugin upload time',
  `gmt_modified` TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'update time',
  `installed` int DEFAULT NULL COMMENT 'plugin already installed count',
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE
DATABASE IF NOT EXISTS EXAMPLE_1;
use EXAMPLE_1;
CREATE TABLE IF NOT EXISTS `users`
(
    `id`       int         NOT NULL AUTO_INCREMENT,
    `username` varchar(50) NOT NULL COMMENT '用户名',
    `password` varchar(50) NOT NULL COMMENT '密码',
    `email`    varchar(50) NOT NULL COMMENT '邮箱',
    `phone`    varchar(20) DEFAULT NULL COMMENT '电话',
    PRIMARY KEY (`id`),
    KEY        `idx_username` (`username`) COMMENT '索引：按用户名查询'
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COMMENT='聊天用户表';

INSERT INTO users (username, password, email, phone)
VALUES ('user_1', 'password_1', 'user_1@example.com', '12345678901');
INSERT INTO users (username, password, email, phone)
VALUES ('user_2', 'password_2', 'user_2@example.com', '12345678902');
INSERT INTO users (username, password, email, phone)
VALUES ('user_3', 'password_3', 'user_3@example.com', '12345678903');
INSERT INTO users (username, password, email, phone)
VALUES ('user_4', 'password_4', 'user_4@example.com', '12345678904');
INSERT INTO users (username, password, email, phone)
VALUES ('user_5', 'password_5', 'user_5@example.com', '12345678905');
INSERT INTO users (username, password, email, phone)
VALUES ('user_6', 'password_6', 'user_6@example.com', '12345678906');
INSERT INTO users (username, password, email, phone)
VALUES ('user_7', 'password_7', 'user_7@example.com', '12345678907');
INSERT INTO users (username, password, email, phone)
VALUES ('user_8', 'password_8', 'user_8@example.com', '12345678908');
INSERT INTO users (username, password, email, phone)
VALUES ('user_9', 'password_9', 'user_9@example.com', '12345678909');
INSERT INTO users (username, password, email, phone)
VALUES ('user_10', 'password_10', 'user_10@example.com', '12345678900');
INSERT INTO users (username, password, email, phone)
VALUES ('user_11', 'password_11', 'user_11@example.com', '12345678901');
INSERT INTO users (username, password, email, phone)
VALUES ('user_12', 'password_12', 'user_12@example.com', '12345678902');
INSERT INTO users (username, password, email, phone)
VALUES ('user_13', 'password_13', 'user_13@example.com', '12345678903');
INSERT INTO users (username, password, email, phone)
VALUES ('user_14', 'password_14', 'user_14@example.com', '12345678904');
INSERT INTO users (username, password, email, phone)
VALUES ('user_15', 'password_15', 'user_15@example.com', '12345678905');
INSERT INTO users (username, password, email, phone)
VALUES ('user_16', 'password_16', 'user_16@example.com', '12345678906');
INSERT INTO users (username, password, email, phone)
VALUES ('user_17', 'password_17', 'user_17@example.com', '12345678907');
INSERT INTO users (username, password, email, phone)
VALUES ('user_18', 'password_18', 'user_18@example.com', '12345678908');
INSERT INTO users (username, password, email, phone)
VALUES ('user_19', 'password_19', 'user_19@example.com', '12345678909');
INSERT INTO users (username, password, email, phone)
VALUES ('user_20', 'password_20', 'user_20@example.com', '12345678900');