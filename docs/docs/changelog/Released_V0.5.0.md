# Released V0.5.0 | Develop native data applications through workflows and agents


## Release Notes for Version 0.5.0
After a period of intensive development, version 0.5.0 has taken over two months to come to fruition. This marks the first stable release that will be maintained over an extended period within the DB-GPT project. Concurrently, the long-term vision for DB-GPT has been officially set: it aims to be an AI native data application development framework utilizing Agentic Workflow Expression Language (AWEL) and agents.
In essence, this framework facilitates the creation of data-centric applications through an intelligent agent-based expression language.


<p align="left">
  <img src={'/img/app/app_list.png'} width="720px" />
</p>


## Introduction to Version Update

In its early releases, the DB-GPT project offered six default use cases, namely:
- [ChatData](https://docs.dbgpt.site/docs/application/started_tutorial/chat_data)
- [ChatExcel](https://docs.dbgpt.site/docs/application/started_tutorial/chat_excel)
- [ChatDB](https://docs.dbgpt.site/docs/application/started_tutorial/chat_db)
- [ChatKnowledge](https://docs.dbgpt.site/docs/application/started_tutorial/chat_knowledge)
- [ChatAgents](https://docs.dbgpt.site/docs/agents)
- [ChatDashboard](https://docs.dbgpt.site/docs/application/started_tutorial/chat_dashboard)

These scenarios were designed to satisfy basic and simple use requirements. However, for large-scale production deployment, particularly when dealing with complex business scenarios, it becomes necessary to develop custom scenarios tailored to specific business conditions. This presents significant challenges in terms of flexibility and development complexity.


To further enhance the usability and flexibility of the business framework, we have built upon our existing features, including the multi-model management (SMMF), knowledge base, Agents, data sources, plugins, and Prompts. We have abstracted the capabilities of intelligent agent orchestration (AWEL) and application construction. Additionally, to facilitate application management and distribution, we have introduced the [dbgpts](https://github.com/eosphoros-ai/dbgpts) subproject, which specifically manages the construction of native intelligent data applications, AWEL common operators, AWEL generic workflow templates, and Agents on top of DB-GPT.

This version update will not affect the usage of the previously established six scenarios. However, with subsequent iterations, these default scenarios will gradually be rewritten as Data Apps. We also plan to incorporate them into the `dbgpts` project as default applications, making them readily available for installation and use.

Now, let's provide a systematic explanation of the main updates in this local release.

### Glossary of Terms:

1. **Data App**: an intelligent Data application built on DB-GPT. 
2. **AWEL**: Agentic Workflow Expression Language, intelligent Workflow Expression Language 
3. **AWEL Flow**: workflow orchestration using the intelligent workflow Expression Language 
4. **SMMF**: a service-oriented multi-model management framework. 
5. **Datasource**: data sources, such as MySQL, PG, StarRocks, and Clickhouse.

## AWEL workflow and application
As shown in the following figure, in the left-side navigation pane, there is an AWEL workflow menu. After you open it, you can orchestrate the workflow.

<p align="left">
  <img src={'/img/app/awel_flow_list.png'} width="720px" />
</p>

After the default installation, there is no content in the AWEL stream. You can build it in two ways. 
1. Install it from the application repository provided by DB-GPT. 
2. Create it yourself. The following describes the simple use of the following two methods. For more detailed use, see DB-GPT following tutorial.

<p align="left">
  <img src={'/img/app/flow_detail.png'} width="720px" />
</p>

### To install from the official repository:

Ensure that you first install and deploy DB-GPT.
Following the installation and deployment, you can utilize the default `dbgpt` command for various operations.


:::info NOTE

This process will allow you to subsequently install the AWEL workflow.
:::

<p align="left">
  <img src={'/img/app/dbgpts_cli.png'} width="720px" />
</p>

As shown in the figure, the dbgpt command supports multiple operations, including model-related operations, knowledge base operations, and Trace logs. Here we will focus on the operation of the app.

<p align="left">
  <img src={'/img/app/dbgpts_apps.png'} width="720px" />
</p>

Pass `dbgpt app` list-remote command, we can see that there are three AWEL workflows available in the current warehouse. Here we install `awel-flow-web-info-search` this workflow. Run the command `dbgpt app install awel-flow-web-info-search`

<p align="left">
  <img src={'/img/app/dbgpts_app_install.png'} width="720px" />
</p>

After the installation is successful, restart the DB-GPT service (dynamic hot loading is on the way), refresh the page, and then `AWEL workflow page` see the corresponding workflow.

<p align="left">
  <img src={'/img/app/dbgpts_flow_black.png'} width="720px" />
</p>

### Building Your Own

In addition to installing the default AWEL flows using the official commands, you'll often need to build your own in practical scenarios. As illustrated below, by clicking on `New AWEL Flow`, you will be brought to the editing page as shown.

<p align="left">
  <img src={'/img/app/awel_flow_node.png'} width="720px" />
</p>

During the editing process, each task's downstream nodes and operators support auto-completion. By clicking the plus sign (➕) located at the bottom right of each operator, you can bring up a list of potential downstream operators that can be connected to the current one. This feature enhances the user experience by providing suggestions and making it easier to construct complex workflows without needing to remember the exact names or types of operators that are available for use.

<p align="left">
  <img src={'/img/app/awel_flow_node_plus.png'} width="720px" />
</p>

## Create a data application

We introduced the construction and installation of AWEL workflow. Next, we will introduce how to create a data application based on a large model.

### Search Chat App
The core capability of the search dialog application is to search for relevant knowledge through search engines (such as Baidu and Google) and then summarize and answer. The effect is as follows:

<p align="left">
  <img src={'/img/app/app_search.png'} width="720px" />
</p>

Creating the preceding application is very simple. On the application creation panel, click `create` , enter the following parameters to complete the creation. Note several parameters. 1. Working mode 2. Flows the working mode we use here is `awel_layout` the selected AWEL workflow is installed earlier. `awel-flow-web-info-search` this workflow.

<p align="left">
  <img src={'/img/app/app_awel.png'} width="720px" />
</p>

### Data analysis assistant 
Use Multi-Agents to write a data analysis Assistant application. The results are as follows.

<p align="left">
  <img src={'/img/app/app_analysis.png'} width="720px" />
</p>


<p align="left">
  <img src={'/img/app/app_analysis_black.png'} width="720px" />
</p>

## Other Update Details
- Release of dbgpt core sdk (#1092): Now includes AWEL operator orchestration capabilities.
To install, you can use the command: `pip install dbgpt`

- Support for Jina Embeddings (#1105): The update integrates with Jina AI, which provides a way to create and manage embeddings for various data types, enhancing search and similarity tasks within the applications.

- New example of schema-linking using AWEL (#1081): There's a new example available demonstrating how to use AWEL for schema-linking, which can be valuable for tasks that require mapping between different data schemas.

- Unified card UI style, including knowledge base cards, model management cards, etc.: This update brings a more consistent look and feel across different UI components that display information in a card format.

## Bug Fixes
- MySQL databases no longer support automatic table creation and field auto-updates (#1133): This change may require developers to manually handle database schema changes, improving control over database migrations.

- Fixed the issue with default dialogues carrying history message records (#1117): This addresses potential privacy or performance issues by ensuring that history records are handled properly.

- Fixed the issue in examples/awel where model_name was fetched from model_config improperly (#1112): This improves the reliability of AWEL examples by ensuring that the model configuration is fetched and used correctly.

- Fixed DAGs sharing data issue (#1102): This fix might relate to data isolation in Directed Acyclic Graphs (DAGs) to ensure that workflows do not inadvertently share or overwrite data.

- Fixed issue with examples/awel default loading model text2vec-large-chinese (#1095): This fix ensures that the large Chinese text-to-vector model loads as expected in the given examples.

These changes reflect ongoing improvements to the dbgpt project, enhancing its capabilities, fixing known issues, and refining user experience. Users should refer to the official documentation or release notes for detailed instructions and information on these updates.


## Upgrade to V0.5.0

If your current version is V0.4.6 or V0.4.7, you need to upgrade to V0.5.0. 
1. Suspend Service 
2. upgrade the database table structure

```sql
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
  `source` varchar(64) DEFAULT NULL COMMENT 'Flow source',
  `source_url` varchar(512) DEFAULT NULL COMMENT 'Flow source url',
  `version` varchar(32) DEFAULT NULL COMMENT 'Flow version',
  `label` varchar(128) DEFAULT NULL COMMENT 'Flow label',
  `editable` int DEFAULT NULL COMMENT 'Editable, 0: editable, 1: not editable',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_uid` (`uid`),
  KEY `ix_dbgpt_serve_flow_sys_code` (`sys_code`),
  KEY `ix_dbgpt_serve_flow_uid` (`uid`),
  KEY `ix_dbgpt_serve_flow_dag_id` (`dag_id`),
  KEY `ix_dbgpt_serve_flow_user_name` (`user_name`),
  KEY `ix_dbgpt_serve_flow_name` (`name`)
) ENGINE=InnoDB AUTO_INCREMENT=15 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

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
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_gpts_app` (`app_name`)
) ENGINE=InnoDB AUTO_INCREMENT=39 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `gpts_app_collection` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT 'autoincrement id',
  `app_code` varchar(255) NOT NULL COMMENT 'Current AI assistant code',
  `user_code` int(11) NOT NULL COMMENT 'user code',
  `sys_code` varchar(255) NOT NULL COMMENT 'system app code',
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
) ENGINE=InnoDB AUTO_INCREMENT=23 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
```

```SQL
ALTER TABLE `gpts_conversations`
ADD COLUMN `team_mode` varchar(255) NULL COMMENT 'agent team work mode';

ALTER TABLE `gpts_conversations`
ADD COLUMN  `current_goal` text COMMENT 'The target corresponding to the current message';
```

3. Reinstall dependencies

```shell
pip install -e ".[default]"
```

4. Start the service

## Acknowledgments
We would like to express our deepest gratitude to all the contributors who made this release possible!

@Aralhi, @Aries-ckt, @JoanFM, @csunny, @fangyinc, @Hzh_97, @junewgl, @lcxadml, @likenamehaojie, @xiuzhu9527 and @yhjun1026

## Appendix 
- DB-GPT framework: https://github.com/eosphoros-ai 
- Text2SQL fine tuning: https://github.com/eosphoros-ai/DB-GPT-Hub 
- DB-GPT-Web : https://github.com/eosphoros-ai/DB-GPT-Web 
- official English documentation: http://docs.dbgpt.site/docs/overview 
- official Chinese documentation: https://www.yuque.com/eosphoros/dbgpt-docs/bex30nsv60ru0fmx