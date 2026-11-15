---
title: Knowledge Base Chat
---

# Ask questions with your knowledge base

Knowledge base chat helps an agent find relevant material in your documents and use it to answer a question. It is useful for questions such as “What is the refund attribution rule?” or “What checks are required before a schema change?”

Start with a [knowledge space](/docs/getting-started/web-ui/knowledge-base) containing processed documents. Uploading a file is not enough: inspect its status and chunks before expecting an answer based on it.

## Start a conversation

1. Open **Knowledge Base** and select the space you need.
2. Open **Chat**.
3. Confirm the knowledge space and choose an available model.
4. Ask a question with a clear scope and request source passages.

![Chat with a selected knowledge space](/img/data-agent/en/knowledge-chat.png)

This screenshot shows the English chat entry before a question is submitted. It is not an example of a completed answer.

You can also start a task from the homepage and select a knowledge base. Check the selected resources before sending the question, especially when moving between business topics.

## Ask a question the documents can answer

For a space containing metric governance documents:

> Explain the definition of net receipts in this knowledge base. Does it include shipping fees? How are refunds paid in the following month attributed? Cite the source passages. If the documents leave a rule undefined, say so.

For a runbook:

> According to the slow-query runbook, what evidence should I collect before recommending an index? List the checks in order and cite their source sections.

Name the business term, system, or document you mean. If several versions exist, specify the relevant date or version and check the references returned. A request to use a version does not itself enforce a persistent version lock.

## Verify before using the answer

| Check | What a usable result should show |
|---|---|
| Source relevance | The references concern the requested term or procedure |
| Support for the conclusion | The cited passages actually establish the answer |
| Coverage | Each part of the question is addressed, or a missing definition is identified |
| Currency | The source is the applicable version rather than a superseded copy |
| Scope | The answer distinguishes document rules from any live data or actions needed |

Open the references and compare the answer with the original text. Do not treat a plausible explanation or a citation label alone as proof. If no relevant source is returned, inspect indexing and retrieval before expanding the question.

For a calculation from live records, connect a [datasource](/docs/modules/connections), prepare the definition in the [Semantic Layer](/docs/semantic-center/overview), and select an appropriate [plugin](/docs/plugins/overview). Knowledge documents provide context; a database result requires an executed query.

## Improve a weak result

If the agent retrieves the wrong material, confirm the selected space, use the exact term from the source, and inspect whether the relevant text exists in its chunks. Review retrieval settings in **Arguments** only after checking the content. Increasing the number of retrieved chunks may add noise as well as coverage.

If sources disagree, ask for a comparison with explicit references and have the document owner resolve the rule. For a broader overview, a generated [LLM-Wiki](/docs/getting-started/web-ui/llm-wiki) can help navigate concepts, but its interpretation still needs review against the source.

Model permission, quota, and connection failures must be resolved in the model service. An empty or failed conversation is not a successful knowledge-based answer.
