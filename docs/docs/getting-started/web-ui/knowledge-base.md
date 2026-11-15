---
sidebar_position: 2
title: Knowledge Base
---

# Knowledge Base

A knowledge base makes your team's documents available to an agent. Use it to answer questions about policies, metric definitions, product manuals, or operational procedures with relevant source material.

In DB-GPT, a **knowledge space** groups documents, processing settings, source bindings, and conversations. A **chunk** is a portion of a document prepared for retrieval. An optional **LLM-Wiki** organizes source material into linked pages for browsing and agent use.

For example, put the definition of “net receipts” and its refund rules into a space, then ask the agent to explain those rules with source excerpts. To calculate net receipts from live database records, also connect a [datasource](/docs/modules/connections) and prepare the metric in the [Semantic Layer](/docs/semantic-center/overview).

## Before you start

Have a small document with a known answer ready—a Markdown policy or runbook is a useful first check. Your deployment needs a working document-processing backend and, for vector retrieval, an embedding model and vector store. Chat and Wiki generation also need an available language model. Check [RAG configuration](/docs/application/advanced_tutorial/rag) if these services are not configured.

:::info About the screenshots
These screenshots use the English product UI. Existing space names and document descriptions keep their authored language. The demo document is still `TODO` with zero chunks, the Wiki has no pages, and the chat has no answer. They illustrate the current controls, not a completed ingestion or answer.
:::

## 1. Create a space

Open **Knowledge Base** in the sidebar and click **Create Knowledge**.

![Knowledge base list](/img/data-agent/en/knowledge-list.png)

Enter a **Knowledge Space Name** and **Description**. Choose a name such as `Analytics_Governance`; names accept Chinese characters, ASCII letters, numbers, underscores, and hyphens. In the description, explain the scope and intended use—for example, “Approved metric definitions and refund attribution rules for commerce analysis.”

![Knowledge space creation, source types, and index methods](/img/data-agent/en/knowledge-create.png)

Choose a source:

| Source | When to use it |
|---|---|
| **Document** | Upload PDF, Word, Excel, PowerPoint, text, Markdown, or CSV files supported by your installed loaders |
| **Git Repository** | Import code and documentation from a repository; set branch and include/exclude directories as needed |
| **Text** | Add a short definition or procedure by pasting its content |
| **Feishu Wiki / Yuque Wiki / RSS** | Bind an external source and choose what to synchronize |

The Notion card is disabled in the current picker. For external platforms, complete the [source binding flow](/docs/getting-started/web-ui/external-datasources) after creating the space. A Git space holds one repository; once imported, use its synchronization controls to update that repository.

### Choose processing options

Select only the index methods your deployment is configured to support:

| UI option | Purpose and prerequisite |
|---|---|
| **Vector Index** | Semantic retrieval; needs a configured embedding model and vector store |
| **Structural Index** | The current UI label for the `FullText` option; needs a configured full-text backend |
| **LLM-Wiki Index** | Generate linked Wiki pages; needs an available language model and successful source processing |
| **Graph Index** | Additional graph processing for supported Markdown/code content; follow the format hint in the form |

Selecting multiple options does not prove that each index has been built. Confirm document processing and inspect the relevant output views separately. **Wiki Graph** shows links between Wiki pages; **Code Graph** concerns imported code. They are different views.

Open **Advanced Settings** if you need to change chunking. Preserve meaningful units such as a policy section or procedure step. Available strategies and values depend on the source and deployment; the creation form does not select an embedding model.

For a document space, select files and click **Create & Upload**. Keep the first import small so you can check the entire path before adding a large collection.

## 2. Add documents and check processing

Open the space's **File View**. The tree on the left helps navigate documents; the list shows chunk counts and processing status.

![File View with a document awaiting processing](/img/data-agent/en/knowledge-files.png)

To add files later, click **Add Datasource**, select files in **Add Document**, and click **Upload & Sync**.

![Add Document upload dialog](/img/data-agent/en/knowledge-upload.png)

Upload acceptance and indexing completion are separate. Use **Refresh status** to read the latest state; use **Sync** in the document's action menu to start processing or reprocess it.

| Status | What to do |
|---|---|
| `TODO` | Processing has not completed; initiate sync if needed |
| `RUNNING` | Wait for the job, then refresh the status |
| `FINISHED` | Inspect chunks and test retrieval; this does not certify Wiki generation |
| `FAILED` | Read the error and server logs, fix its cause, and sync again |

Open a processed document to inspect its available content and chunks. Verify that a known section was extracted correctly. A scanned PDF may need OCR; a successful upload alone does not show that its text is readable.

## 3. Ask a question and verify the answer

Open **Chat** in the space, confirm the selected knowledge base and model, and ask a question whose answer exists in your source. You can also select the knowledge base when starting a task from the homepage.

![Knowledge-scoped chat entry](/img/data-agent/en/knowledge-chat.png)

For the governance example, try:

> According to this knowledge base, does net receipts include shipping fees? Explain how a refund paid in the following month is attributed. Cite the source passages, and identify any rule the documents do not specify.

Check the answer against the returned references and original text. A fluent answer without relevant evidence is insufficient. If the source does not define a rule, have the agent identify the gap instead of assuming a definition. See [Knowledge Base Chat](/docs/application/apps/chat_knowledge) for a practical verification checklist.

## 4. Keep the knowledge current

| View or action | Use it to |
|---|---|
| **File View** | Inspect documents, chunks, and processing status; upload or sync files |
| **Arguments** | Review the space's embedding/retrieval, prompt, and summary settings |
| **Sources** | Bind external platforms, inspect sync logs, and pause or resume synchronization |
| **Wiki / Wiki Graph** | Browse generated pages and their relationships when available |
| **Chat** | Ask questions within the selected space |
| **Code Graph** | Explore code relationships when repository graph processing is available |

In **Sources**, click **Bind source** to start the connector wizard. Source synchronization, document indexing, and Wiki generation are separate stages: check each stage rather than assuming that a successful fetch makes every view ready.

![Sources tab and binding entry](/img/data-agent/en/knowledge-sources.png)

For an organized reading layer, enable and use [LLM-Wiki](/docs/getting-started/web-ui/llm-wiki). Keep source documents as the authority and review generated interpretations before relying on them.

Before deleting a document or space, confirm the scope shown by the action and retain originals outside DB-GPT. Removing a source binding keeps its synchronized documents; review those separately when retiring a source.

## Troubleshooting

| Symptom | Next check |
|---|---|
| Upload succeeds but chunks remain at zero | Document state, loader errors, file content, and whether sync ran |
| Processing fails | Embedding endpoint, storage backend, file format, and server logs |
| No useful references | Selected space, indexed content, exact terminology, and retrieval settings in Arguments |
| Answer contradicts the document | Inspect cited passages, clarify the question, and check conflicting source versions |
| Model permission, quota, or connection error | Fix the configured model service; changing documents will not resolve model access |
| Wiki or graph is empty | Relevant index option, source processing, generation/graph job state, and its dependencies |

Once a small document produces usable chunks and an answer supported by its text, expand the collection. Group related material by business scope so an agent can select the right knowledge for each task.
