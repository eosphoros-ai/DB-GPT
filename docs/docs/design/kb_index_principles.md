---
id: kb_index_principles
title: Knowledge Base Indexing Principles
sidebar_label: KB Indexing Principles
---

# Knowledge Base Indexing Principles

> How DB-GPT indexes an uploaded document — from raw file to searchable indexes.
> Intended for product / design readers. No code, but the mechanisms match the implementation.

## What "indexing" means here

Indexing happens at **document-sync time**, not at chat time. Chat only *retrieves*; it never re-indexes.
The pipeline for every document:

```
upload ──► load file ──► chunk ──► embed ──► persist into one or more indexes
                                          │
                                          └─► optionally build graph(s)
```

A knowledge space declares which indexes to build via `index_methods` (a string list). Three index
*methods* are selectable; "structural index" and "code graph" are capabilities layered on top
(structural index is built at retrieve time; the code/heading graph is built on top of the
`KnowledgeGraph` method or for `GIT_REPO` spaces).

| Index entry point | Code name (`index_methods`) | Built at sync time? | What it gives you |
|---|---|---|---|
| Vector index | `VectorStore` | yes | semantic similarity ranking |
| Keyword index | `FullText` | yes | exact keyword / BM25 hits |
| Knowledge-graph index | `KnowledgeGraph` | yes | graph-traversal over entities, headings, code |
| Structural index | *(retrieve-time tree)* | no — rebuilt at query time | markdown-header tree / parent-child navigation |
| Code graph | *(layered on `KnowledgeGraph` / `GIT_REPO`)* | yes | AST of code files as `function` / `class` nodes |

> In short: **vector, keyword, knowledge-graph** are the three persisted index methods. **Structural**
> index and **code graph** are two extra shapes of indexing that DB-GPT builds on top of those.

---

## 1. Structural index — navigate by document structure

### What it is
A *view* over the already-chunked document that arranges chunks into a tree by their Markdown
heading level (H1 → H2 → H3 …). Every chunk already carries `Header1/Header2/...` metadata from
chunking (see *Metadata pipeline* below); the structural index simply *organises* those chunks into a
tree so retrieval can walk up to a parent section and then back down to its children — instead of
treating every chunk as an isolated island.

### Why it's a separate concept (even though it has no own index method)
During indexing, DB-GPT **persists** the heading path on each chunk but does **not** persist the tree.
At **retrieve time** the retriever reconstructs the tree from those `HeaderN` fields in memory and
walks it ("find this leaf chunk, then expand its whole parent section, then rank"). So the "structural
index" is really *structural metadata + a tree-view retriever*, not a separate store.

### Principle (how it's built + used)
```
markdown file                  chunking writes HeaderN on every chunk
─────────────                  ────────────────────────────────────────
# Prompt Cache Design     ──►  chunk A  { H1: "Prompt Cache Design" }
   ## Core Principle      ──►  chunk B  { H1: "Prompt Cache", H2: "Core Principle" }
      ### Hit Condition   ──►  chunk C  { H1..H3: "Hit Condition" }
   ## Three Strategies    ──►  chunk D  { H1: "Prompt Cache", H2: "Three Strategies" }
                                         │
                          retrieve-time  ▼  organise into tree by H1>H2>H3
                                      ┌── H1 Prompt Cache ──┐
                                      │                     │
                              H2 Core Principle        H2 Three Strategies
                                      │                     │
                              H3 Hit Condition        (chunk D)
                              (chunk C)
```

- Best for: "what's in this whole section?", "summarise chapter 3", parent-context expansion.
- Note: for non-Markdown documents there is no heading hierarchy, so the structural tree degrades to a
  flat list — its value is concentrated on Markdown / structured docs.

---

## 2. Knowledge-graph index — relational retrieval

This is the richest index, and internally it is **not one graph but several** that all get built when
the `KnowledgeGraph` method is enabled:

```
enable index_methods = KnowledgeGraph
        │
        ├── (a) LLM triplet graph          semantic:  (entity) -predicate- (entity)
        ├── (b) document–paragraph graph   structural: document → chunk → chunk (include / next)
        ├── (c) Markdown heading graph     structural: file → H1 → H2 → H3 (contains)
        └── (d) code graph                 structural: repository → file → function/class (defines)
```

(a) and (b) live in the **knowledge-graph store** (TuGraph / Neo4j / Memgraph); (c) and (d) both land
in the **code-graph tables** and share one builder.

### 2a. LLM triplet-extraction graph (semantic)
Each chunk is sent to an LLM with an extraction prompt that asks for `(subject, predicate, object)`
triplets. The returned triplets are upserted into the graph store as `entity -edge- entity`. This is
the classic "knowledge graph from text": it captures facts and relations that pure keyword/vector
search cannot.

```
chunk text: "Anthropic's prompt cache reuses the KV matrix to cut cost"
      │  LLM triplet extraction prompt
      ▼
(Anthropic) ──has──▶ (Prompt Cache)
(Prompt Cache) ──reuses──▶ (KV matrix)
(Prompt Cache) ──cuts──▶ (cost)
```
Retrieval traverses edges: an entity hit expands to its neighbours, and each edge knows which chunk
it came from (via a `_chunk_id` edge property) so answers can still be cited back to source.

### 2b. Document–paragraph graph
Independently of triplets, the KG store also builds a structural skeleton:
`document -include- chunk`, `chunk -include- chunk` (parent/child when chunks nest), and
`chunk -next- chunk` (reading order). This lets retrieval hop from an entity → the chunk that
contains it → the document → neighbouring chunks. (When the community-summary variant is enabled, it
also runs community detection and summarises each community with an LLM.)

### 2c. Markdown heading graph
For `.md` files under a `KnowledgeGraph`-method space, the builder reconstructs each file's content
from its stored chunks, scans `^(#{1,6})\s+` heading lines (skipping headings inside fenced code
blocks), and emits `heading` vertices connected by `contains` edges:
`file → H1 → H2 → H3`. This is the graph analogue of the structural index above — queryable via edge
traversal instead of an in-memory tree.

### 2d. Code graph (代码图谱)
This is the part most worth understanding. The **same** `RepoGraphBuilder` that builds the Markdown
heading graph is also able to build a graph from **source code**, and it is what powers code-level
retrieval over a `GIT_REPO` space (or over code files uploaded into a `KnowledgeGraph`-method space).

**Principle — parse with an AST, not with regex:**

```
walk repo
  repository  ──contains──▶  file
                              │ language inferred from extension
   ┌──────────────────────────┼───────────────────────────┐
   │                          │                            │
 .py/.java/.js/.ts/       .md/.markdown              other languages
 .go/.rs/.c/.cpp          (heading graph 2c)         (regex fallback)
   │                                                     │
   ▼ parse with tree-sitter                               ▼ regex def/class lines
 function_definition / class_definition / ...        file ──defines──▶ function|class
   │
   ▼ for each AST target node
 create a vertex:  type=function|class|method|class|interface|impl|struct|enum|trait
                   name, file_path, start_line, end_line, language
 add edge: file ──defines──▶ <that vertex>
```

- **Nodes** created: `repository`, `file`, and code nodes `function` / `class` / `method` /
  `interface` / `impl` / `struct` / `enum` / `trait`.
- **Edges** created by the builder: `contains` (repo→file, file→heading) and `defines` (file→code node).
- **Parser:** [tree-sitter](https://tree-sitter.github.io/) for Python / Java / JavaScript /
  TypeScript / Go / Rust / C / C++. Each target AST node type (e.g. `function_definition`,
  `class_definition`, `method_declaration`, `interface_declaration`, `struct_item`) is mapped to a
  semantic node type. Languages without a tree-sitter grammar here fall back to a regex `def`/`class`
  scan that still emits `file -defines-> function|class` edges.
- **What it buys you:** "where is `apply_anthropic_cache_control` defined?", "list all methods of
  class `PromptCache`" — answered by vertex lookup + `defines` edge traversal, instead of fuzzy
  vector match.

> **Honest caveat about edges.** The retrieval layer also supports `CALLS` / `INHERITS` /
> `IMPLEMENTS` / `IMPORTS` / `REFERENCES` edges (for call-chain and class-hierarchy queries). The
> current `RepoGraphBuilder`, however, only emits `contains` and `defines`. So call-chain and
> inheritance traversals only return data when those edges were produced by another builder; for
> graphs built purely by this builder they will be empty. Call it out when designing features that
> depend on call graphs.

---

## 3. Vector index — semantic similarity

```
chunk ──embedding model──► [0.12, -0.34, 0.56, …] (e.g. 1024-d) ──► vector store
query ──embedding model──► query vector ──cosine similarity──► top-K chunks
```

### Principle
Each chunk is run through an embedding model that maps text to a high-dimensional vector; the
vector + the chunk's metadata are bulk-upserted into a vector database (Chroma / Milvus / PGVector /
Qdrant / Weaviate / …) as chosen by the space config. At query time the question is embedded the same
way and the store returns the chunks whose vectors are nearest (cosine / inner-product) to the query
vector.

### Why it's the default
Vector search catches *paraphrase*: "caching mechanism" still retrieves "prompt cache" because the
vectors live nearby even though no words match. It doesn't need any structural information about the
document and works on every file type.

### Weakness
A vector averages a whole chunk into one point — if the chunk mixes two topics it blurs; if the exact
term matters (an API name, an error code) it may miss. That's why keyword + vector are usually
enabled together.

---

## 4. Keyword index — exact-term match (BM25)

```
chunk ──indexed as text in search engine──► BM25 term index
query ──tokenize──► "terms" ──BM25 score over chunks──► top-K chunks
```

### Principle
Chunks are stored verbatim as text documents in a full-text search engine (Elasticsearch with BM25
scoring; `k1` / `b` tunable). Retrieval tokenises the query and returns chunks ranked by BM25 score —
i.e. by term frequency × inverse document frequency, with length normalisation. No embedding, no LLM,
pure lexical matching.

### When it wins
Precise identifiers: `apply_anthropic_cache_control`, `ERR_CONN_REFUSED`, a config key. Vector search
may dilute such exact tokens into "similar" but wrong neighbours; BM25 returns the exact hit and
ranks it at the very top.

### Weakness
It cannot match synonyms or paraphrase ("caching" will not find "cache" reliably once tokenised, and
definitely won't find "缓存"). It is purely complementary to the vector index.

---

## How the four combine at retrieval time

```
                      user question
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
   vector           keyword (BM25)        knowledge graph
  semantic            exact term        / structural / code
   hits                hits                   hits
        │                  │                  │
        └──────────────────┼──────────────────┘
                           ▼
                  fusion + rerank (structural tree can expand parents here)
                           │
                           ▼
                  Top-K chunks ──► into the LLM prompt ──► cited answer
```

---

## Chunking & metadata pipeline (the foundation under all four)

All four indexes operate on the *same chunks*, so chunking quality dominates retrieval quality.

**Chunking strategies**
- Markdown header split (`H1→H2→H3`): preserves semantic boundary + heading path — best for tech docs.
- Size split (fixed chars): for plain text without structure.
- Separator split (paragraph / newline / table cell): for tabular / unstructured content.

**Metadata written on every chunk during indexing** (used later by every index and by citation
tracing):

```
upload                 chunking                     storage
──────                 ────────                     ───────
file_name: prompt.md → chunk_id: 101             → vector: [0.12, ...]
file_path: /docs/...  → doc_name: prompt.md      → content: "Prefix..."
doc_type: DOCUMENT    → chunk_type: text         → meta_info: {
index_methods:        → file_path: /docs/...     →   "Header1": "Prompt Cache",
 [Vector, FullText,   → header_path: H1>H2>H3    →   "Header2": "Core Principle",
  KG]                                              →   "Header3": "Hit Condition"
                                                   → }
```

---

## Key design principles

1. **Three persisted index methods** — `VectorStore`, `FullText`, `KnowledgeGraph` — combinable per space.
2. **Structural index is metadata + a retrieve-time tree**, not a separate store; it relies on the
   `HeaderN` written during chunking.
3. **The knowledge-graph index is a family of graphs** — LLM triplets, document–paragraph skeleton,
   Markdown headings, and the code graph (AST) — that share the build path.
4. **Code graph parses with tree-sitter**, emitting `function`/`class` nodes + `defines` edges; it is
   what makes code-level question-answering precise. Mind that call/inheritance edges are not
   populated by the current builder.
5. **One chunking, four indexes** — chunk quality and the `HeaderN` metadata underpin everything;
   chunk per doc type (Markdown→headers, text→size, table→separator).
6. **Index/chat decoupled** — indexing runs at sync time; chat only retrieves.