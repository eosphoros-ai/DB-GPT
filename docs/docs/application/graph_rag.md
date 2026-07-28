# Graph RAG

Graph RAG is the retrieval mode that uses DB-GPT's **knowledge-graph index**. When you enable the `KnowledgeGraph` index method on a knowledge space, DB-GPT builds a *family of graphs* and retrieves by graph traversal instead of (or in addition to) vector / keyword search.

## What gets built

| Graph | Built for | Captures |
|---|---|---|
| **LLM triplet graph** | any text | `(subject, predicate, object)` facts and relations |
| **Document–paragraph graph** | any document | `document → chunk → chunk` structure (`include` / `next`) |
| **Markdown heading graph** | `.md` files | `file → H1 → H2 → H3` heading hierarchy (`contains`) |
| **Code graph** | code files / `GIT_REPO` spaces | code AST parsed with **tree-sitter** → `function` / `class` / `method` nodes with `file → defines` edges |

All four share one build path and write into the configured graph store (TuGraph / Neo4j / Memgraph).

## How retrieval works

The `GraphRetriever` matches graph nodes by keyword, by vector similarity on node embeddings, by natural-language-to-graph-query (Text2GQL), and via document–graph associations — then expands along edges. Every edge remembers the chunk it came from, so answers remain citable.

:::note
The retriever can traverse `CALLS` / `INHERITS` / `IMPLEMENTS` edges, but the current code-graph builder only emits `contains` and `defines`. Call-chain and inheritance queries will be empty unless those edges were produced by another builder.
:::

## Learn more

- [Knowledge Base Indexing Principles](/docs/design/kb_index_principles) — the graph family and code-graph AST parsing in depth
- [Agentic RAG Conversation Principles](/docs/design/agentic_rag_principles) — how graph retrieval fits into the agentic loop
- [Graph RAG Cookbook](/docs/cookbook/rag/graph_rag_app_develop) — build a Graph RAG app programmatically
- [TuGraph integration](/docs/installation/integrations/graph_rag_install) — install the graph-store backend