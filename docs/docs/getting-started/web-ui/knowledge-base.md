---
sidebar_position: 2
title: Knowledge Base
---

# Knowledge Base

Build and manage knowledge bases for Retrieval-Augmented Generation (RAG). Upload documents, configure retrieval, and use them in chat.

## Creating a knowledge base

### Step 1 — Navigate to Knowledge

Click **Knowledge** in the sidebar to open the knowledge management page.

### Step 2 — Create a new knowledge base

1. Click **Create** (or the **+** button)
2. Fill in:
   - **Name** — A descriptive name for the knowledge base
   - **Description** — Brief description of the content
   - **Embedding Model** — The embedding model to use for vectorization (must match your configured embedding)
3. Click **Create**

### Step 3 — Upload documents

1. Open the knowledge base you just created
2. Click **Upload** to add documents
3. Select one or more files
4. Wait for processing to complete (chunking, embedding, and indexing)

:::info Supported file formats
| Format | Extensions |
|---|---|
| Documents | `.pdf`, `.docx`, `.doc`, `.txt`, `.md` |
| Spreadsheets | `.xlsx`, `.xls`, `.csv` |
| Web | `.html`, `.htm` |
| Data | `.json` |
| Code | `.py`, `.java`, `.js`, `.ts`, etc. |
:::

## Using a knowledge base in chat

1. Go to **Chat** and create a new conversation
2. Select **Chat Knowledge** mode
3. Choose your knowledge base from the dropdown
4. Ask questions — the LLM will use your documents as context

## Knowledge base settings

Each knowledge base has configurable settings:

| Setting | Description | Default |
|---|---|---|
| **Chunk Size** | Maximum characters per chunk | 512 |
| **Chunk Overlap** | Overlap between consecutive chunks | 50 |
| **Top K** | Number of chunks to retrieve per query | 5 |
| **Score Threshold** | Minimum relevance score for retrieval | 0.3 |

:::tip Tuning retrieval
- **Large documents**: Increase chunk size to preserve context
- **Precise answers**: Increase Top K and lower the score threshold
- **Noisy results**: Raise the score threshold
:::

## Storage types

DB-GPT supports multiple vector storage backends:

| Backend | Description | Install Extra |
|---|---|---|
| **ChromaDB** | Default, embedded, no setup needed | `storage_chromadb` |
| **Milvus** | Distributed vector database for production | `storage_milvus` |
| **OceanBase** | Cloud-native distributed database | `storage_oceanbase` |

To use a non-default backend, add the corresponding extra to your install command:

```bash
uv sync --all-packages --extra "storage_milvus" ...
```

## Advanced features

<details>
<summary><strong>Graph RAG</strong></summary>

DB-GPT supports knowledge graphs for structured retrieval:

- Extracts entities and relationships from documents
- Enables graph-based queries alongside vector search
- Useful for complex domain knowledge with interconnected concepts

See [Graph RAG](/docs/application/graph_rag) for setup instructions.

</details>

<details>
<summary><strong>Keyword retrieval (BM25)</strong></summary>

For hybrid retrieval combining vector and keyword search:

```bash
uv sync --all-packages --extra "rag_bm25" ...
```

This enables BM25 indexing alongside vector embeddings for improved recall.

</details>

## Managing knowledge bases

| Action | How |
|---|---|
| **View** | Click on a knowledge base to see its documents and settings |
| **Add documents** | Use the Upload button within the knowledge base |
| **Delete documents** | Select documents and click Delete |
| **Delete knowledge base** | Use the Delete button on the knowledge base card |

:::warning Deleting is permanent
Deleting a knowledge base removes all associated vector embeddings and indexed data. The original uploaded files are not recoverable.
:::

## Next steps

| Topic | Link |
|---|---|
| Use knowledge in chat | [Chat](/docs/getting-started/web-ui/chat) |
| RAG concepts | [RAG](/docs/getting-started/concepts/rag) |
| Advanced RAG configuration | [RAG Tutorial](/docs/application/advanced_tutorial/rag) |
