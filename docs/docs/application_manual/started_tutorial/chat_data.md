# Chat Data
Chat data capability is to dialogue with data through natural language. Currently, it is mainly dialogue between structured and semi-structured data, which can assist in data analysis and insight.

:::info note

Before starting the data conversation, we first need to add the data source
:::

## steps

To start a data conversation, you need to go through the following steps:
- 1.Add data source
- 2.Select ChatData
- 3.Select the corresponding database
- 4.Start a conversation


### Add data source

First, select the `data source` on the left to add and add a database. Currently, DB-GPT supports multiple database types. Just select the corresponding database type to add. Here we choose MySQL as a demonstration. For the test data of the demonstration, see the [test sample](https://github.com/eosphoros-ai/DB-GPT/tree/main/docker/examples/sqls).


<p align="left">
  <img src={'/img/chat_data/add_data.png'} width="720px" />
</p>



### Choose ChatData

<p align="left">
  <img src={'/img/chat_data/choose_type.png'} width="720px" />
</p>

### Start a conversation


:::info note

⚠️ Pay attention to selecting the corresponding model and database during the dialogue. At the same time, DB-GPT also provides preview mode and editing mode.
:::


:::tip

preview mode
:::


<p align="left">
  <img src={'/img/chat_data/start_chat.gif'} width="720px" />
</p>



:::tip

editing mode
:::

<p align="left">
  <img src={'/img/chat_data/edit.png'} width="720px" />
</p>

