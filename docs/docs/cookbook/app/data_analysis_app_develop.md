# Data App Develop Guide

In this document, we will guide you through the process of developing a data analysis app using DB-GPT.

# Target

In this case, our goal is to build a data assistant application that includes the following capabilities:
1. Intelligent question and answer based on the documents.
2. Conduct data dialogue based on database.
3. Internet search based on tool usage.

These three capabilities can be utilized within a single conversation based on the intent recognition ability provided by DB-GPT. The data assistant will match appropriate sub-agent applications to answer questions in corresponding domains based on the user's inquiries.

:::tip
Note: This case is mainly for demonstration purposes of application building, and actual applications in production environments still need further optimization.
:::

# Prepare

Before starting to build the application, you first need to complete the installation and deployment of the project. For relevant tutorials, please refer to the [deployment documentation](../../installation/sourcecode.md).

# Sub-Data App Construction

First, we need to create three sub-intelligent applications separately, and then use the intent recognition capability provided by AppLink to integrate the intelligent applications into a unified intelligent entity and unify the dialogue interaction entrance.


## 1. Building a question answering assistant based on RAG

We use the agent module provided by DB-GPT to build a RAG-based question-answering assistant. DB-GPT has some built-in agents, such as

- Intent Recognition Expert Agent
- CodeEnginner Agent
- Report Generator Agent
- Data Scientist Agent
- Document Summarizer Agent
- ToolExpert Agent
- ...

In this case, intelligent question answering mainly relies on the domain knowledge base and document summarization agent (Summarizer), so we first need to build the domain knowledge base. The process is as follows:

1. Domain Knowledge Cleaning and Organization
2. Upload to DB-GPT Knowledge
3. Create Knowledge-Based Data App
4. Chat with KBQA

### Domain Knowledge Cleaning and Organization
The organization and processing of domain knowledge is a very important task and has a very important impact on the final effect. You need to organize and clean up the files according to your actual application. In this example, we use the default PDF for uploading. We prepare the official DB-GPT document as demonstration material.

### Create a knowledge base

On the product interface, select the knowledge base, click [Create Knowledge], and fill in the corresponding parameters. We provide multiple storage types. 1. Embedding vector 2. Knowledge graph 3. Full text. In this example, we use the Embedding solution for construction.

<p align="center">
  <img src={'/img/cookbook/knowledge_base.png'} width="800" />
</p>


After filling in the corresponding parameters, click [Next] to select the document type and upload the document.

<p align="center">
  <img src={'/img/cookbook/knowledge_base_upload.png'} width="800" />
</p>


Select the appropriate slicing method and wait for the document to be uploaded. At this point, our knowledge base has been built and we can proceed with the subsequent intelligent question and answer application

<p align="center">
  <img src={'/img/cookbook/knowledge_base_success.png'} width="800" />
</p>

### Create a KBQA App

Select [Application Management] -> [Create Application], and select Single Agent Mode in the pop-up dialog box.

<p align="center">
  <img src={'/img/cookbook/app_create_with_agent.png'} width="800" />
</p>

Click [OK], in the pop-up dialog box
1. Select the Summarizer agent
2. The prompt word is empty by default. If you need to modify it, you can customize the prompt first. For a tutorial on prompt definition, see the documentation.
3. Model strategy: Supports multiple model strategies. If there are multiple models, they can be configured according to priority.
4. Add resources: In this case, we rely on the previously created knowledge base, so select the resource type [knowledge] and the parameter is the name of the knowledge base just created.
5. Add a recommended question, [Whether it takes effect] to control the effectiveness of the recommended question.

<p align="center">
  <img src={'/img/cookbook/qa_app_build_parameters.png'} width="800" />
</p>

Click [Save] to complete the creation of the smart application.

### Start Chat

<p align="center">
  <img src={'/img/cookbook/qa_app_chat.png'} width="800" />
</p>

:::tip
Note:  The agent application shown in this tutorial is built based on the Summarizer agent. The Summarizer agent is a built-in agent of DB-GPT. See the [source code](https://github.com/eosphoros-ai/DB-GPT/blob/main/dbgpt/agent/expand/summary_assistant_agent.py) for the relevant code implementation. In actual use, the relevant code can be further modified according to specific scenarios. Customization and optimization. Or customize the agent based on this case
:::

## Data ChatBot Assistant

In the same way, a data dialogue assistant can be built based on similar ideas. The data dialogue assistant can conduct simple data dialogue based on a database and draw corresponding charts. It mainly includes the following steps:

1. Data Preparation
2. Create Datasource
3. Create Data Chat App
4. Chat

### Data Preparation 

For data preparation, please refer to the [data preparation](https://github.com/eosphoros-ai/DB-GPT/blob/main/docker/examples/dashboard/test_case_mysql_data.py) section in the document.

### Create Datasource 

After preparing the data, you need to add the database to the data source for subsequent use. Select [Application Management] -> [Database] -> [Add Data Source]

<p align="center">
  <img src={'/img/cookbook/datasource.png'} width="800" />
</p>

### Create Data Chat App

As shown in the figure below, select [Application Management] -> [Application] -> [Create Application], select a single agent application, fill in the corresponding parameters, and click OK.

<p align="center">
  <img src={'/img/cookbook/data_app_create.png'} width="800" />
</p>

Select the corresponding parameters in turn:
- Agent: Select the `DataScientist` agent
- Prompt: The default is empty. For customization, please refer to the Prompt management tutorial.
- Model strategy: The priority strategy is selected here. You can use the `proxyllm` and `tongyi_proxyllm` models according to the priority.
- Available resources: Select the database type as the resource type, and select the database we added before as the parameter.
- Recommended questions: Default questions can be set based on data conditions.

<p align="center">
  <img src={'/img/cookbook/data_app_build_parameters.png'} width="800" />
</p>

### Start Chat

Click to start the conversation and enter the corresponding questions for data Q&A.

<p align="center">
  <img src={'/img/cookbook/data_app_chat.png'} width="800" />
</p>

## Search Assistant

The weather assistant needs to call the search engine to query relevant information, so the Tool call needs to be designed, and the construction process is relatively complicated. In order to simplify application creation, we have built the relevant capabilities into an AWEL workflow, which can be installed and used directly.

### AWEL workflow install

First execute the command `dbgpt app list-remote` to view all AWEL sample processes in the remote warehouse. `awel-flow-web-info-search` provides the ability to search the Internet.

```
dbgpt app list-remote

┏━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃           存储库  ┃ 类型       ┃                               名称 ┃
┡━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ eosphoros/dbgpts │ operators │               awel-simple-operator │
│ eosphoros/dbgpts │ resources │                    jina-web-reader │
│ eosphoros/dbgpts │ resources │          simple-calculator-example │
│ eosphoros/dbgpts │ workflow  │                all-in-one-entrance │
│ eosphoros/dbgpts │ workflow  │        andrewyng-translation-agent │
│ eosphoros/dbgpts │ workflow  │             awel-flow-example-chat │
│ eosphoros/dbgpts │ workflow  │         awel-flow-rag-chat-example │
│ eosphoros/dbgpts │ workflow  │      awel-flow-rag-summary-example │
│ eosphoros/dbgpts │ workflow  │    awel-flow-simple-streaming-chat │
│ eosphoros/dbgpts │ workflow  │          awel-flow-web-info-search │
│ eosphoros/dbgpts │ workflow  │                 db-expert-assisant │
│ eosphoros/dbgpts │ workflow  │ financial-report-knowledge-factory │
│ eosphoros/dbgpts │ workflow  │                financial-robot-app │
│ eosphoros/dbgpts │ workflow  │             rag-save-url-to-vstore │
│ eosphoros/dbgpts │ workflow  │          rag-url-knowledge-example │
└──────────────────┴───────────┴────────────────────────────────────┘

```

Execute the `dbgpt app install awel-flow-web-info-search` command to install it locally.

```
dbgpt app install awel-flow-web-info-search

> 
  Installing collected packages: awel-flow-web-info-search
  Successfully installed awel-flow-web-info-search-0.1.0
  Installed dbgpts at ~/.dbgpts/packages/ae442685cde998fe51eb565a23180544/awel-flow-web-info-search.
  dbgpts 'awel-flow-web-info-search' installed successfully.
```

Refresh the interface. In the AWEL workflow interface, you can see that the corresponding workflow has been installed.

<p align="center">
  <img src={'/img/cookbook/awel_web_search.png'} width="800" />
</p>

Click on the AWEL workflow and we can see the content inside. Here is a brief explanation.

1. Agent Resource: The resource that the agent depends on, in this case baidu_search
2. ToolExpert: Tool expert, used to implement tool invocation.
3. Summarizer agent: used to summarize the query results.

To summarize: This AWEL workflow uses two agents, ToolExpert and Summarizer. ToolExpert relies on the built-in tool baidu_search. Summarizer further summarizes the results of the tool expert's execution and generates the final answer.

<p align="center">
  <img src={'/img/cookbook/awel_web_search_tool.png'} width="800" />
</p>

### Create a search assistant

At the same time, [Create Application] -> [Task Flow Orchestration Mode]

<p align="center">
  <img src={'/img/cookbook/search_app.png'} width="800" />
</p>

Select the corresponding workflow, add recommended questions, and click Save.

<p align="center">
  <img src={'/img/cookbook/search_app_build.png'} width="800" />
</p>

### Chat
<p align="center">
  <img src={'/img/cookbook/search_app_chat.png'} width="800" />
</p>


# Unified intelligent application construction

According to the above process, we have created intelligent applications for each sub-scenario, but in actual applications. We need to complete all questions and answers at one entrance, so we need to integrate agents from these sub-fields. Unify the interaction portal through AppLink and intent recognition capabilities.

In order to implement problem routing, a core capability is intent recognition and classification. In order to make application construction more flexible in design, we provide intent recognition and classification capabilities based on knowledge base and Agent. And supports customization based on AWEL.



### Intent knowledge base construction

To implement intent classification and route user questions to corresponding intelligent applications, we first need to define and describe the capabilities of each application. Here we build it through a knowledge base. The following is a simple intent definition document used to describe the capabilities of each intelligent application. There are four main types of information that need to be filled in


1. Intent: Intent type

2. App Code: Can be copied in the application interface.

<p align="center">
  <img src={'/img/cookbook/app_code.png'} width="800" />
</p>

3. Describe: Describe the capabilities of the agent.


4. Slots: Slot information, used to represent the parameters that the agent relies on in actual question and answer, such as [time] and [location] information required in weather queries.


```
#######################
Intent:DB答疑 App Code:a41d0274-8ac4-11ef-8735-3ea07eeef889 Describe: 所有DB领域相关知识的咨询答疑，包含了日常DBA的FAQ问题数据、OceanBase(OB)的官方文档手册，操作手册、问题排查手册、日常疑难问题的知识总结、可以进行专业的DBA领域知识答疑。 只要和DB相关的不属于其他应用负责范畴的都可以使用我来回答 问题范例: 1.怎么查看OB抖动？ 2.DMS权限如何申请 3.如何确认xxxxx 类型:知识库咨询
#######################
Intent:数据对话 App Code:516963c4-8ac9-11ef-8735-3ea07eeef889 Describe: 通过SQL查询分析当前数据库(dbgpt-test:包含用户和用户销售订单数据的数据库） 类型:数据查询
#######################
Intent:天气检索助手 App Code:f93610cc-8acc-11ef-8735-3ea07eeef889 Describe: 可以进行天气查询 Slots:
位置: 要获取天气信息的具体位置
时间: 要获取的天气信息的时间，如果没有明确提到，使用当前时间

```

### Create an intent classification knowledge base

As shown in the figure below, create an intent classification knowledge base.

<p align="center">
  <img src={'/img/cookbook/app_intent_knowledge.png'} width="800" />
</p>

It should be noted that the delimiter needs to be separated by our custom delimiter, that is, # in the document.

<p align="center">
  <img src={'/img/cookbook/chunk_sep.png'} width="800" />
</p>

### AWEL workflow installation editor
Again, to simplify usage. We have written the corresponding AWEL workflow for intent recognition and can be installed and used directly.

```
dbgpt app install db-expert-assisant

> Installing collected packages: db-expert-assisant
Successfully installed db-expert-assisant-0.1.0
Installed dbgpts at ~/.dbgpts/packages/ae442685cde998fe51eb565a23180544/db-expert-assisant.
dbgpts 'db-expert-assisant' installed successfully.
```

Open the front-end interface. In the AWEL workflow interface, we can see db_expert_assisant. In order to facilitate our subsequent editing, we copy a process for editing. Click [Copy] in the upper right corner, customize the name and description, and complete the copy.

<p align="center">
  <img src={'/img/cookbook/awel_db_expert.png'} width="800" />
</p>

We open the copied AWEL process, here we name it `db_expert_assistant_v1`, and open the workflow. We can see the following orchestration process. Similarly, the following agents are used in this workflow


1. `Intent Recognition Expert`: Intent recognition expert is specially used for intent recognition. It relies on a knowledge base resource, that is, the knowledge base resource for intent recognition we defined earlier.

2. `AppLauncher`: used to call experts in each field.

3. `Summarizer`: Summarizes the entire question and answer. If there is no routing in all scenarios, a default answer will be given based on the database knowledge base.

<p align="center">
  <img src={'/img/cookbook/awel_expert_v1.png'} width="800" />
</p>

### Application creation

Create an application and select the task flow orchestration mode.


<p align="center">
  <img src={'/img/cookbook/data_app_build.png'} width="800" />
</p>

Click OK, select the workflow, enter the recommended questions, and save.

<p align="center">
  <img src={'/img/cookbook/data_app_awel.png'} width="800" />
</p>


### Chat 
<p align="center">
  <img src={'/img/cookbook/data_expert_chat.png'} width="800" />
</p>







