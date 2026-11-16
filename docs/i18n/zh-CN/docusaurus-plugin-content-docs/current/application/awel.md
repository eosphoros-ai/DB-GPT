# Use Data App With AWEL

## What Is AWEL?

> Agentic Workflow Expression Language(AWEL) is a set of intelligent agent workflow expression language specially designed for large model application
development.

You can found more information about AWEL in [AWEL](../awel/awel.md) and 
[AWEL Tutorial](../awel/tutorial/) if you want to know more about AWEL.

In short, you can use AWEL to develop LLM applications with AWEL Python API.

## What Is AWEL Flow?

AWEL flow allows you to develop LLM applications without writing code. It is built on top of AWEL Python API.


## Visit Your AWEL Flows in `AWEL Flow` Page

In the `AWEL Flow` page, you can see all the AWEL flows you have created. You can also create a new AWEL flow by clicking the `Create Flow` button.


<p align="left">
  <img src={'/img/application/awel/awel_flow_page.png'} width="720px"/>
</p>


## Examples

### Build Your RAG Application

To build your RAG application, you need to create a knowledge space according to [Chat Knowledge Base](./apps/chat_knowledge.md) first.
Then, click the `Create Flow` button to create a new flow. 

In the flow editor, you can drag and drop the nodes to build your RAG application.

1. You will see an empty flow editor like below:

<p align="left">
  <img src={'/img/application/awel/flow_dev_empty_page_img.png'} width="720px"/>
</p>

2. Drag a `Streaming LLM Operator` node to the flow editor.

<p align="left">
  <img src={'/img/application/awel/flow_dev_rag_llm_1.png'} width="720px"/>
</p>

3. Drag a `Knowledge Operator` node to the flow editor.

You can click the "+" button in the `Streaming LLM Operator` node's second input(`"HOContext"`), 
it will show a list of nodes that can be connected to current node of input, then you can select the `Knowledge Operator` node.

<p align="left">
  <img src={'/img/application/awel/flow_dev_rag_llm_2_.png'} width="720px"/>
</p>

The options of nodes can be connected as follows:

<p align="left">
  <img src={'/img/application/awel/flow_dev_rag_llm_3.png'} width="720px"/>
</p>

Then, drag the `Knowledge Operator` node and connect it to the `Streaming LLM Operator` node.

<p align="left">
  <img src={'/img/application/awel/flow_def_rag_ko_1.png'} width="720px"/>
</p>

Please select your knowledge space in the `Knowledge Operator` node's `Knowledge Space Name` option.

4. Drag a `Common LLM Http Trigger` node to the flow editor.

<p align="left">
  <img src={'/img/application/awel/flow_dev_rag_ko_2.png'} width="720px"/>
</p>

4. Drag a `Common Chat Prompt Template` **resource** node to the flow editor.

<p align="left">
  <img src={'/img/application/awel/flow_dev_rag_prompt_1.png'} width="720px"/>
</p>

And you can type your prompt template in the `Common Chat Prompt Template` parameters.

5. Drag a `OpenAI Streaming Output Operator` node to the flow editor.

<p align="left">
  <img src={'/img/application/awel/flow_dev_rag_output_1.png'} width="720px"/>
</p>

6. Click the `Save` button in the top right corner to save your flow.

<p align="left">
  <img src={'/img/application/awel/flow_dev_rag_save_1.png'} width="720px"/>
</p>

Lastly, you will see your RAG application in the `AWEL Flow` page.

<p align="left">
  <img src={'/img/application/awel/flow_dev_rag_show_1.png'} width="720px"/>
</p>

After that, you can use it to build your APP according to [App Manage](./apps/app_manage.md).

## Reference

- [AWEL](../awel/awel.md)
- [AWEL CookBook](../awel/cookbook/)
- [AWEL Tutorial](../awel/tutorial/)
