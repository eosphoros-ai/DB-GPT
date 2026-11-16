---
id: agentic_rag_principles
title: Agentic RAG Conversation Principles
sidebar_label: Agentic RAG Principles
---

# Agentic RAG Conversation Principles

> This document explains how DB-GPT combines Agent + RAG to answer knowledge-base questions, from query to a cited final answer. Intended for product/design readers — no code.

## 1. Agentic RAG vs Traditional RAG

```
Traditional RAG (single retrieval)
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ Question │ →  │Retrieve  │ →  │ Build    │ →  │ LLM      │
└──────────┘    │  once    │    │ Prompt   │    │ Answer   │
                └──────────┘    └──────────┘    └──────────┘
                  retrieval once  stuff into ctx   one-shot
Weakness: quality hinges on one similarity pass; can't iterate; no multi-step lookahead

Agentic RAG (multi-round)  ← DB-GPT uses this
┌──────────┐    ┌──────────────────────────────────────┐    ┌──────────┐
│ Question │ →  │         ReAct Agent Loop              │ →  │ Cited    │
└──────────┘    │  ┌────────┐  ┌────────┐  ┌────────┐  │    │ Answer   │
                │  │ Thought│→ │ Action │→ │Observe │  │    └──────────┘
                │  └────────┘  └────────┘  └────────┘  │
                │       ↑                     │        │
                │       └── not enough? ──────┘        │
                │       (multi-round, pick tools)      │
                └──────────────────────────────────────┘
Strength: iterative retrieval, multiple tools, traceable citations
```

## 2. End-to-End Agent Conversation Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│  User: "What's the design philosophy of prompt caching?"                 │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Step 1: Agent Thought                                                  │
│  "User asks about caching philosophy. Let me semantic-search the KB."    │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Step 2: Pick Tool (Action)                                             │
│  ┌─────────────────────────────────────────────────┐                    │
│  │ Available tools (Knowledge-Agent mode, KB only):│                    │
│  │  • kb_semantic_search                            │                    │
│  │  • kb_grep / kb_cat                              │                    │
│  │  • kb_ls / kb_glob                               │                    │
│  │  • kb_codegraph_*                                │                    │
│  │  • todowrite / terminate                         │                    │
│  └─────────────────────────────────────────────────┘                    │
│  Agent picks: kb_semantic_search(query="prompt cache design")           │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Step 3: Execute + Observe                                              │
│  Tool returns 10 chunks with scores and source files                    │
│  Observation:                                                           │
│    Result 1 (0.67) [prompt cache.md] design-cost table...               │
│    Result 2 (0.66) [prompt cache.md] Hermes ephemeral injection...      │
│    ...                                                                  │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Step 4: Agent Thought again                                            │
│  "Rich results but the comparison table is truncated — read full file."  │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Step 5: Pick Tool → kb_cat(path="prompt cache.md")                    │
│  → Observation: full 315-line file                                       │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Step 6: Collect Citations                                              │
│  Every tool-returned chunk goes into _cited_chunks                      │
│  Dedup + strip HTML tags → clean traceable fragments                    │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Step 7: Terminate & Generate Answer                                    │
│  Agent decides info is enough → terminate(result="final answer")        │
│                                                                          │
│  Backend post-processing:                                               │
│   1. _auto_annotate_citations: insert [1][2] at citation spots          │
│   2. _build_references_xml: append <references> payload                 │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Step 8: Frontend renders cited answer                                  │
│  ┌─────────────────────────────────────────────────────────────┐        │
│  │ Pi rebuilds system prompt each turn[1]                      │        │
│  │ Hermes freezes snapshot + ephemeral injection[2][6]         │        │
│  │ Claude-Code uses Beta Header[3]                             │        │
│  │                                                              │        │
│  │  ↑ [1][2][3] are blue badges; hover shows the chunk         │        │
│  └─────────────────────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────────────────┘
```

## 3. The ReAct Loop (core of the agent)

```
                    ┌─────────────────┐
                    │   User query    │
                    └────────┬────────┘
                             │
                             ▼
               ┌─────────────────────────┐
               │  Thought (LLM reasoning)│ ← analyze state, decide next step
               └────────────┬────────────┘
                            │
                            ▼
               ┌─────────────────────────┐
               │  Action (tool + args)   │ ← pick one from available tools
               └────────────┬────────────┘
                            │
                            ▼
               ┌─────────────────────────┐
               │  Observation (tool ret) │ ← execute, get result
               └────────────┬────────────┘
                            │
                   ┌────────┴────────┐
                   │                 │
            enough info?         need more?
                   │                 │
                   ▼                 │
            ┌──────────┐             │
            │ Terminate│             │
            │ Answer   │             │
            └──────────┘             │
                                     │ yes → back to Thought (next round)
                                     │
                   (max N rounds to prevent loops)
```

**Key**: the agent doesn't blindly retrieve once — it judges "is this enough?" from the observation; if not, it switches tools/queries and searches again.

## 4. Citation Traceability Pipeline

```
Tool exec                  Backend collect              Frontend display
─────────                  ─────────────────            ────────────────
kb_semantic_search     ->  _cited_chunks[0] = {      -> [1] blue badge
  Result 1: "Pi... "        content: "Pi...",            hover shows:
  score: 0.67                recall_score: 0.67,          "Pi... · recall 0.67"
                           }

kb_cat                 ->  _cited_chunks[1] = {      -> [2] blue badge
  "Hermes freezes..."        content: "Hermes...",        hover shows:
                             recall_score: null,          "Hermes..."
                            }
                                                              │
Auto-annotate          ->  answer text:               -> [1][2] inserted
_auto_annotate             "Pi rebuilds[1]"              after cited
_citations                 "Hermes freezes[2]"           sentence

Ref panel              ->  <references> XML           -> 🔗 View References
_build_references_xml       references='[{               click → Drawer
                              name:"prompt cache.md",     tabs per doc
                              chunks:[{index:1,...},      all chunks
                                       {index:2,...}]
                            }]'
```

## 5. Tool Modes: Knowledge-Agent vs Full-Agent

```
KB detail-page chat (knowledge-agent)    Generic agent chat (react-agent)
─────────────────────────────────────    ────────────────────────────────
┌─────────────────────────┐             ┌─────────────────────────────┐
│ KB tools only:          │             │ All tools:                  │
│  • kb_semantic_search   │             │  • kb_* (knowledge)         │
│  • kb_grep / kb_cat     │             │  • shell_interpreter        │
│  • kb_ls / kb_glob      │             │  • sql_query                │
│  • kb_codegraph_*       │             │  • html_interpreter         │
│  • todowrite / terminate│             │  • code_interpreter         │
└─────────────────────────┘             │  • execute_skill_script     │
        ↑                                │  • todowrite / terminate    │
   focused on KB retrieval              └─────────────────────────────┘
   no noise from irrelevant tools                ↑
   ideal for pure KB Q&A                    capable, for complex tasks
                                            but many tools → easy to drift
```

## 6. Key Design Principles

1. **Agent-driven retrieval**: not one-shot; LLM decides whether to search again or switch tools based on observation
2. **Tools scoped to scene**: pure KB chat gets only KB tools, preventing the agent from calling shell/sql
3. **Citations auto-collected**: every tool-returned chunk enters `_cited_chunks` — doesn't rely on LLM compliance
4. **Post-processing fallback**: when the LLM ignores the "mark [1][2]" instruction, backend string-matches and inserts badges automatically
5. **Chunk content cleaning**: HTML tags stripped before matching so clean LLM text aligns with chunk text
6. **References shipped with answer**: `<references>` XML appended to the answer; frontend parses it to render badges + panel
7. **Closed-loop traceability**: every badge → chunk → document → viewable in the references panel