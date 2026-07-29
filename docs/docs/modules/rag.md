# MS-RAG

Multi-Source Enhanced Retrieval-Augmented Generation Framework (MS-RAG)

:::info Principles deep-dive
This page is the **framework reference**. For the *why* behind indexing and the agentic
retrieval loop, read the design docs first:
- [Knowledge Base Indexing Principles](/docs/design/kb_index_principles) — how a document becomes searchable: structural / knowledge-graph (incl. code graph) / vector / keyword indexes.
- [Agentic RAG Conversation Principles](/docs/design/agentic_rag_principles) — how a question becomes a cited answer via an agent-driven retrieval loop.
:::

# Introduction

Large Language Models (LLMs) are powerful, but they can only answer based on the data they were trained on. When users need up-to-date or domain-specific information — such as internal documents, proprietary databases, or the latest reports — LLMs alone fall short.

**Retrieval-Augmented Generation (RAG)** bridges this gap by retrieving relevant information from external knowledge sources and feeding it as context to the LLM before generating a response. This ensures answers are grounded in real data rather than memorized patterns.

DB-GPT implements a **Multi-Source RAG (MS-RAG)** framework that goes beyond basic document Q&A. It supports multiple knowledge sources (documents, URLs, databases, knowledge graphs, git repos), multiple indexing strategies, and integrates deeply with the DB-GPT agent and workflow ecosystem. Conversation over a knowledge base is performed by an **agentic RAG** loop — the agent can rewrite the query, retrieve multiple times, fuse and rerank results, and produce a cited answer — rather than a single retrieve-then-generate pass.

# Architecture

## Two phases: indexing and conversation

```
INDEXING (runs at document-sync time)              CONVERSATION (runs at chat time)
─────────────────────────────────────              ─────────────────────────────────
Knowledge Source → Chunking → Indexes              User question
        │                                                 │
   one chunking,                                          ▼
  multiple indexes:                              Agentic RAG loop
   • Vector   • Keyword                         (query rewrite → retrieve
   • Knowledge-graph (triplets,                      multiple times → fuse +
   •  document-paragraph, Markdown                    rerank → assemble prompt)
   •  heading, code AST)                                     │
                                                              ▼
                                              LLM generates a cited answer
```

Indexing and conversation are **decoupled**: indexing happens once when documents are synced; chat only retrieves and never re-indexes.

### Indexing pipeline

Building an index is an **ETL** pipeline — one *extract* + one *chunk* feeds every enabled index; only the per-index *transform* and *load* differ.

```
Extract                Transform                          Load
──────────             ───────────────────────            ────────────────────────
Knowledge.load()   →   ChunkManager.split()           →   persist into the index store
parse source →         + per-index transform:             · EmbeddingAssembler   → vector DB
raw text               · embed      (vector)              · BM25Assembler        → Elasticsearch
                       · tokenize   (keyword / BM25)      · graph store + RepoGraphBuilder
                       · triplets / heading /                → graph store / code graph
                         code AST  (knowledge graph)     · SummaryAssembler     → vector DB
                       · summary    (summary)             · DBSchemaAssembler    → vector DB
                       attach metadata (header path,
                        chunk_id, …) for retrieval/citation
```

1. **Extract** — `KnowledgeFactory` routes each data source (file / URL / text / git repo) to the right `Knowledge` implementation, which parses it into raw text (`Knowledge.load()`).
2. **Transform** — `ChunkManager.split()` chunks the text (by size / page / paragraph / separator / markdown headers) and each index applies its own transform — embedding, BM25 tokenization, LLM triplet / heading / code-AST extraction, summary, or schema embedding — attaching metadata (`Header1…Header6`, `chunk_id`, …) that later underpins retrieval and citation.
3. **Load** — the per-index driver persists the transformed representation into the index store: `EmbeddingAssembler` / `BM25Assembler` / `SummaryAssembler` / `DBSchemaAssembler` for the vector / keyword / summary / schema indexes, and the graph store (`aload_document`) + `RepoGraphBuilder` for the knowledge-graph and code-graph indexes. (The **structural** index is *not* loaded — it is rebuilt at retrieve time from the `HeaderN` metadata written in this stage.)
4. **Retrieval & Generation** — this is the **agentic RAG conversation** (see next section).

## Indexing ETL pipeline

`BaseAssembler` defines the common Extract → Transform → Load shape; each index type plugs in its own transform + load. One extract + one chunking feeds **every** enabled index — only the transform + load differ per index.

```python
Knowledge.load()  →  ChunkManager.split()  →  Assembler.persist()  →  Assembler.as_retriever()
   # Extract           # Transform               # Load                 # retrieve-time (chat)
```

| Index | Transform | Load driver (implementation) | Index store |
|---|---|---|---|
| **Vector** | chunk → embedding | `EmbeddingAssembler.persist()` | Vector DB (Chroma, Milvus, …) |
| **Keyword** | chunk → BM25 tokens | `BM25Assembler.persist()` | Elasticsearch |
| **Knowledge graph** | chunk → LLM triplets + document/heading/code-AST graph | graph store `aload_document` + `RepoGraphBuilder` | TuGraph / Neo4j / Memgraph |
| **Summary** | chunk → LLM summary → embedding | `SummaryAssembler.persist()` | Vector DB |
| **DB schema** | schema → embedding | `DBSchemaAssembler.persist()` | Vector DB |
| **Code graph** | code → tree-sitter AST | `RepoGraphBuilder` → `CodeGraphStore` | code-graph tables |
| **Structural** | *(none — built at retrieve time)* | retrieve-time `DocTreeIndex` from `HeaderN` metadata | — |

> The assemblers are the **Load-stage drivers** for the vector / keyword / summary / schema indexes. The knowledge-graph and code-graph indexes are built by the graph store and `RepoGraphBuilder` respectively. All of them consume the same chunks produced in the Extract + Transform stage — which is why chunking quality is the shared foundation under every index.

# Indexes

DB-GPT selects which indexes to build per knowledge space via `index_methods` (a string list). Three index *methods* are persisted; **structural index** and **code graph** are two extra shapes layered on top. All indexes operate on the *same chunks*, so chunking quality dominates retrieval quality.

| Index | `index_methods` value | Built at sync time? | What it gives you |
|---|---|---|---|
| **Vector** | `VectorStore` | yes | semantic similarity ranking via embeddings + cosine |
| **Keyword** | `FullText` | yes | exact term / BM25 hits |
| **Knowledge-graph** | `KnowledgeGraph` | yes | graph traversal over entities, document structure, headings, and code |
| **Structural** | *(retrieve-time tree)* | no — rebuilt at query time from `HeaderN` chunk metadata | markdown-header tree / parent-child section navigation |
| **Code graph** | *(layered on `KnowledgeGraph`; also for `GIT_REPO` spaces)* | yes | AST of code files as `function` / `class` nodes with `defines` edges |

:::tip
The knowledge-graph index is **not one graph but a family**: an LLM-extracted triplet graph, a document–paragraph structure graph, a Markdown heading-hierarchy graph, and (for code/git repos) a code AST graph. They share one build path. Details and the code-graph tree-sitter parsing are in [Knowledge Base Indexing Principles](/docs/design/kb_index_principles).
:::

# Conversation: agentic RAG

When a user asks a question over a knowledge base, DB-GPT does **not** do a single retrieve-then-generate. Instead an **agent** drives the loop:

```
question
   │
   ▼
query rewrite / multi-query        ◄── LLM expands the question for better recall
   │
   ▼
retrieve (vector + keyword + graph, possibly repeated)   ◄── may iterate: retrieve → judge → retrieve again
   │
   ▼
fusion + rerank
   │
   ▼
assemble context, generate answer with citations
```

This agentic loop — multi-step retrieval, query rewriting, result fusion and reranking, and citation — is what lets DB-GPT answer complex or multi-part questions that a one-shot RAG cannot. The full flow is documented in [Agentic RAG Conversation Principles](/docs/design/agentic_rag_principles).

## Retrieval strategies

You can configure the retrieve mode in the knowledge base settings:

<p align="center">
  <img src={'/img/rag/embedding_retrieve_mode.png'} width="720px" />
</p>

| Strategy | Description | Backend Required |
|---|---|---|
| **Semantic** | Vector similarity search using embeddings | Vector Store |
| **Keyword** | BM25-based keyword matching | Elasticsearch |
| **Hybrid** | Combines vector + keyword search with Reciprocal Rank Fusion (RRF) | Vector Store + Elasticsearch |
| **Tree** | Tree-structured retrieval over the markdown heading hierarchy | Vector Store |

## Query enhancement

Beyond raw retrieval, the agentic loop provides advanced query processing:

- **Query Rewrite** — Uses an LLM to expand and rephrase the original query into multiple search queries for better recall, and to decide whether another retrieval round is needed.
- **Reranking** — After retrieval, a reranker re-scores and re-orders the results for higher precision before they enter the prompt.

### Supported Rerankers

| Reranker | Type | Description |
|---|---|---|
| **CrossEncoderRanker** | Local | Uses sentence-transformers CrossEncoder models |
| **QwenRerankEmbeddings** | Local | Qwen3-Reranker via transformers |
| **OpenAPIRerankEmbeddings** | API | Compatible with OpenAI-style rerank APIs |
| **RRFRanker** | Algorithm | Reciprocal Rank Fusion for merging multi-source results |
| **DefaultRanker** | Algorithm | Simple score-based sorting |

# Knowledge Sources

DB-GPT supports loading knowledge from multiple source types. In the Web UI, you can select a datasource type when uploading:

<p align="center">
  <img src={'/img/rag/knowledge_datasource_type.png'} width="720px" />
</p>

## Datasource Types

| Type | Description | Example |
|---|---|---|
| **Document** | Upload files in various formats | PDF, Word, Excel, CSV, Markdown, PowerPoint, TXT, HTML, JSON, ZIP |
| **URL** | Fetch and index web page content | Any accessible HTTP/HTTPS URL |
| **Text** | Directly input raw text | Paste text content in the UI |
| **Yuque** | Import from Yuque documentation platform | Yuque document links |
| **Git Repo** | Clone a code repository and index it as a code graph | A GitHub/GitLab repo URL |

## Supported Document Formats

| Format | Extension | Knowledge Class |
|---|---|---|
| PDF | `.pdf` | `PDFKnowledge` |
| CSV | `.csv` | `CSVKnowledge` |
| Markdown | `.md` | `MarkdownKnowledge` |
| Word (docx) | `.docx` | `DocxKnowledge` |
| Word (legacy) | `.doc` | `Word97DocKnowledge` |
| Excel | `.xlsx` | `ExcelKnowledge` |
| PowerPoint | `.pptx` | `PPTXKnowledge` |
| Plain Text | `.txt` | `TXTKnowledge` |
| HTML | `.html` | `HTMLKnowledge` |
| JSON | `.json` | `JSONKnowledge` |
| Code | `.py .java .js .ts .go .rs .c .cpp …` | `CodeFileKnowledge` (parsed with tree-sitter into the code graph) |

# Storage Types

When creating a knowledge base, you choose which index store(s) to use — one or more can be enabled together and are complementary:

<p align="center">
  <img src={'/img/rag/choose_knowledge_type.png'} width="720px" />
</p>

| Storage Type | `index_methods` | Description | Best For |
|---|---|---|---|
| **Vector Store** | `VectorStore` | Stores document embeddings for semantic similarity search | General-purpose document Q&A |
| **Knowledge Graph** | `KnowledgeGraph` | Builds the graph family (LLM triplets + document/heading/code structure) for relational retrieval | Domain knowledge with entity relationships, code, structured docs |
| **Full Text** | `FullText` | Full-text/BM25 index for keyword-based retrieval | Exact term matching and keyword search |

## Vector Store Backends

| Backend | Description | Install Extra |
|---|---|---|
| **ChromaDB** | Default embedded vector database, zero setup | `storage_chromadb` |
| **Milvus** | Distributed vector database for production scale | `storage_milvus` |
| **PGVector** | PostgreSQL extension for vector operations | `storage_pgvector` |
| **Valkey** | High-performance in-memory vector store with HNSW/FLAT indexing | `storage_valkey` |
| **Weaviate** | Cloud-native vector search engine | `storage_weaviate` |
| **Elasticsearch** | Full-text + vector hybrid search | `storage_elasticsearch` |
| **OceanBase** | Cloud-native distributed database | `storage_oceanbase` |

## Knowledge Graph Backends

| Backend | Description |
|---|---|
| **TuGraph** | High-performance graph database by Ant Group |
| **Neo4j** | Popular open-source graph database |
| **Memgraph** | In-memory graph database for low-latency queries |

## Full-Text Backends

| Backend | Description |
|---|---|
| **Elasticsearch** | Industry-standard full-text search engine |
| **OpenSearch** | AWS-managed search and analytics suite |

# Knowledge Graph RAG

When the **KnowledgeGraph** index method is enabled, DB-GPT builds a **family of graphs**, not a single one. They share one build path and all support edge-traversal retrieval:

1. **LLM triplet graph** — An LLM extracts `(subject, predicate, object)` triplets from each chunk; triplets are upserted as `entity -edge- entity` into the graph store (TuGraph, Neo4j, or Memgraph). Each edge remembers the chunk it came from, so answers stay citable.
2. **Document–paragraph graph** — a structural skeleton of `document → chunk → chunk` (`include` / `next` edges) so retrieval can hop from an entity to the chunk and document that contain it. (With the community-summary variant, communities are also detected and summarised by an LLM.)
3. **Markdown heading graph** — for `.md` files, a `file → H1 → H2 → H3` (`contains`) hierarchy. This is the graph analogue of the structural index.
4. **Code graph** — for code files and `GIT_REPO` spaces, the source is parsed with **tree-sitter** (Python / Java / JavaScript / TypeScript / Go / Rust / C / C++) and `function` / `class` / `method` / `interface` / `struct` … nodes are emitted with `file → defines → node` edges. This enables precise code-level questions such as "where is `apply_anthropic_cache_control` defined?".

:::note
The retriever also supports `CALLS` / `INHERITS` / `IMPLEMENTS` edges, but the current code-graph builder only emits `contains` and `defines`. Call-chain and inheritance traversals only return data when those edges were produced by another builder. See [Knowledge Base Indexing Principles](/docs/design/kb_index_principles) for the full detail and this caveat.
:::

## Graph retrieval sub-strategies

At query time, the `GraphRetriever` combines several sub-strategies:

- **Keyword-based** — Match graph nodes by extracted keywords
- **Vector-based** — Semantic similarity search on graph node embeddings
- **Text-based** — Convert natural language to graph query language (Text2GQL) via LLM
- **Document-based** — Retrieve through document-graph associations

# Chunking Strategies

Document chunking is a critical step in RAG quality — it is the shared foundation under every index. DB-GPT supports multiple chunking strategies:

<p align="center">
  <img src={'/img/rag/file_chunk.png'} width="720px" />
</p>

| Strategy | Splitter | Description |
|---|---|---|
| **Chunk by Size** | `RecursiveCharacterTextSplitter` | Split by character count with configurable size and overlap (default: 512 / 50) |
| **Chunk by Page** | `PageTextSplitter` | Split at page boundaries (useful for PDFs) |
| **Chunk by Paragraph** | `ParagraphTextSplitter` | Split at paragraph boundaries |
| **Chunk by Separator** | `SeparatorTextSplitter` | Split at custom separator strings |
| **Chunk by Markdown Header** | `MarkdownHeaderTextSplitter` | Split at markdown heading levels; preserves the heading path used by the structural index and the heading graph |

## Chunking Parameters

<p align="center">
  <img src={'/img/rag/embedding_argument.png'} width="720px" />
</p>

| Parameter | Description | Default |
|---|---|---|
| **chunk_size** | Maximum characters per chunk | 512 |
| **chunk_overlap** | Overlapping characters between adjacent chunks | 50 |
| **topk** | Number of chunks to retrieve per query | 5 |
| **recall_score** | Minimum relevance score threshold | 0 |
| **recall_type** | Recall strategy (TopK) | TopK |
| **model** | Embedding model to use | Depends on configuration |

# Embedding Models

DB-GPT supports a wide range of embedding models for converting text into vector representations:

## Local Models

| Model | Class | Description |
|---|---|---|
| **HuggingFace** | `HuggingFaceEmbeddings` | General-purpose HuggingFace models |
| **BGE Series** | `HuggingFaceBgeEmbeddings` | BAAI BGE models with instruction support (Chinese/English) |
| **Instructor** | `HuggingFaceInstructEmbeddings` | Instruction-following embedding models |

## Remote API Models

| Provider | Class | Description |
|---|---|---|
| **OpenAI-compatible** | `OpenAPIEmbeddings` | Any OpenAI-compatible embedding API |
| **Jina** | `JinaEmbeddings` | Jina AI embedding service |
| **Ollama** | `OllamaEmbeddings` | Local Ollama embedding server |
| **Tongyi (Aliyun)** | `TongyiEmbeddings` | Alibaba Cloud DashScope |
| **Qianfan (Baidu)** | `QianfanEmbeddings` | Baidu Wenxin platform |
| **SiliconFlow** | `SiliconFlowEmbeddings` | SiliconFlow embedding service |

# Usage

## Creating a Knowledge Base (Web UI)

### Step 1 — Open Knowledge Management

Navigate to the **Knowledge** section in the sidebar.

<p align="center">
  <img src={'/img/rag/create_knowledge.png'} width="720px" />
</p>

### Step 2 — Create and Configure

1. Click **Create** to start a new knowledge base.
2. Select the **index methods** to enable (Vector Store, Knowledge Graph, Full Text — combinable).
3. Choose the **Embedding Model** and configure chunk parameters.

<p align="center">
  <img src={'/img/rag/choose_knowledge_type.png'} width="720px" />
</p>

### Step 3 — Upload Data

Select a datasource type and upload your content. Supported types include Document (PDF, Word, Excel, CSV, etc.), URL, Text, Yuque, and Git Repo.

### Step 4 — Configure Chunking

Choose a chunking strategy and set parameters:

<p align="center">
  <img src={'/img/rag/file_chunk.png'} width="720px" />
</p>

### Step 5 — Configure Retrieval Strategy (Optional)

You can configure the retrieval strategy for your knowledge base. DB-GPT supports multiple retrieve modes — **Semantic**, **Keyword**, **Hybrid**, and **Tree** — to suit different query scenarios. Select the mode that best fits your use case in the knowledge base settings.

<p align="center">
  <img src={'/img/rag/embedding_retrieve_mode.png'} width="720px" />
</p>

### Step 6 — Chat with Your Knowledge

Go to **Chat**, click the knowledge base icon in the chat input toolbar, select your knowledge base from the dropdown, and start asking questions. The conversation runs the agentic RAG loop described above.

<p align="center">
  <img src={'/img/rag/use_knowledge.png'} width="720px" />
</p>

## Programmatic Usage (Python API)

```python
from dbgpt.rag import Chunk
from dbgpt_ext.rag.assembler import EmbeddingAssembler
from dbgpt_ext.rag.knowledge import KnowledgeFactory

# Extract: parse the source into raw text
knowledge = KnowledgeFactory.create(file_path="your_document.pdf")

# Transform + Load: chunk, embed, and persist into the vector index
assembler = await EmbeddingAssembler.aload_from_knowledge(
    knowledge=knowledge,
    index_store=your_vector_store,
    embedding_model=your_embedding_model,
)
assembler.persist()

# Retrieve (chat time): the vector index answers similarity queries
retriever = assembler.as_retriever(top_k=5)
chunks = await retriever.aretrieve("What is the main topic?")
```

# Next Steps

| Topic | Link |
|---|---|
| Indexing principles (structural / KG / code graph / vector / keyword) | [Knowledge Base Indexing Principles](/docs/design/kb_index_principles) |
| Agentic RAG conversation principles | [Agentic RAG Conversation Principles](/docs/design/agentic_rag_principles) |
| Knowledge Base Web UI Guide | [Knowledge Base](/docs/getting-started/web-ui/knowledge-base) |
| RAG Concepts | [RAG](/docs/getting-started/concepts/rag) |
| Graph RAG Setup | [Graph RAG](/docs/application/graph_rag) |
| AWEL RAG Operators | [AWEL](/docs/getting-started/concepts/awel) |
| Source Code | [GitHub](https://github.com/eosphoros-ai/DB-GPT/tree/main/packages/dbgpt-core/src/dbgpt/rag) |