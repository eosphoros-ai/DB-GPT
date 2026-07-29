"""Code graph tools for GIT_REPO knowledge spaces.

Provides kb_codegraph_explore, kb_codegraph_call_chain, kb_codegraph_class_hierarchy
as @tool for Agent use. These tools query the code knowledge graph to answer
structural questions that vector search cannot handle:
  - "PaymentService 有哪些方法？"
  - "谁调用了 process_payment？"
  - "哪些类实现了 PaymentProvider？"

The graph is built during knowledge space indexing (when build_graph=True)
and persisted to both database (primary) and JSON file (backup).

Ported from derisk; uses DB-GPT's @tool decorator and CodeGraphRetriever.
"""

import json
import logging
import os
from typing import Annotated, Optional, Tuple

from dbgpt.agent.resource.tool.base import tool
from dbgpt.storage.graph_store.graph import MemoryGraph

logger = logging.getLogger(__name__)

# Cache for loaded graphs: knowledge_id -> MemoryGraph
_graph_cache: dict = {}


def _get_graph_cache_dir(knowledge_id: str) -> str:
    """Get the graph cache directory for a knowledge space.

    Security: knowledge_id can be user-controlled (chat ext_info / URL path
    param) and is joined into a filesystem path, so it MUST NOT contain path
    separators or ``.``/``..`` segments — otherwise an attacker can traverse
    out of ``~/.dbgpt/graph_cache/``. We REJECT such input rather than
    transforming it, so legitimate space names (including Chinese / spaces /
    hyphens) keep their exact on-disk key and existing graphs stay readable.
    """
    kid = str(knowledge_id)
    if not kid or "/" in kid or "\\" in kid or kid in (".", ".."):
        raise ValueError(f"Invalid knowledge_id for graph cache dir: {kid!r}")
    return os.path.join(os.path.expanduser("~"), ".dbgpt", "graph_cache", kid)


def _load_graph(knowledge_id: str) -> Tuple[Optional[MemoryGraph], Optional[str]]:
    """Load the code graph for a knowledge space.

    Tries DB first, falls back to JSON file if DB is empty.
    Returns (graph, error_message) tuple:
      - (graph, None) on success
      - (None, error_message) on failure
    """
    if knowledge_id in _graph_cache:
        logger.debug(f"[codegraph] Cache hit for {knowledge_id}")
        return _graph_cache[knowledge_id], None

    # Try DB first
    try:
        from ..service.codegraph_store import CodeGraphStore

        store = CodeGraphStore()
        graph = store.load_graph(knowledge_id)
        if graph and graph.vertex_count > 0:
            _graph_cache[knowledge_id] = graph
            logger.info(
                f"[codegraph] Loaded graph from DB for {knowledge_id}: "
                f"{graph.vertex_count} vertices, {graph.edge_count} edges"
            )
            return graph, None
        elif graph is not None:
            logger.warning(
                f"[codegraph] DB returned graph for {knowledge_id} "
                f"but vertex_count=0, falling back to file"
            )
        else:
            logger.info(
                f"[codegraph] DB returned None for {knowledge_id}, falling back to file"
            )
    except Exception as e:
        logger.warning(
            f"[codegraph] DB load failed for {knowledge_id}: "
            f"{type(e).__name__}: {e}, falling back to file"
        )

    # Fallback to JSON file
    graph_dir = _get_graph_cache_dir(knowledge_id)
    graph_file = os.path.join(graph_dir, "code_graph.json")

    if not os.path.exists(graph_file):
        # Try to get DB counts for diagnostics
        db_info = ""
        try:
            from ..models.code_graph_db import (
                CodeGraphEdgeDao,
                CodeGraphMetaDao,
                CodeGraphVertexDao,
            )

            v_count = CodeGraphVertexDao().count_by_knowledge_id(knowledge_id)
            e_count = CodeGraphEdgeDao().count_by_knowledge_id(knowledge_id)
            meta = CodeGraphMetaDao().get_by_knowledge_id(knowledge_id)
            if v_count > 0:
                db_info = (
                    f" (DB has {v_count} vertices, {e_count} edges "
                    f"but load_graph failed; meta={meta.to_dict() if meta else 'None'})"
                )
            else:
                db_info = " (DB has no vertices)"
        except Exception as e2:
            db_info = f" (DB diagnostic failed: {type(e2).__name__}: {e2})"

        error_msg = (
            f"No graph found for {knowledge_id}: "
            f"file not found at {graph_file}{db_info}"
        )
        logger.warning(f"[codegraph] {error_msg}")
        return None, error_msg

    try:
        with open(graph_file, "r", encoding="utf-8") as f:
            graph_data = json.load(f)

        from dbgpt_ext.rag.graph_builder.repo_graph_builder import RepoGraphBuilder

        graph = RepoGraphBuilder.dict_to_graph(graph_data)
        _graph_cache[knowledge_id] = graph
        logger.info(
            f"[codegraph] Loaded graph from file for {knowledge_id}: "
            f"{graph.vertex_count} vertices, {graph.edge_count} edges"
        )
        return graph, None
    except Exception as e:
        error_msg = f"Failed to load graph file for {knowledge_id}: {e}"
        logger.warning(f"[codegraph] {error_msg}")
        return None, error_msg


def _save_graph(
    knowledge_id: str,
    graph: MemoryGraph,
    build_source: str = "repo",
    repo_url: str = "",
    branch: str = "",
):
    """Persist the code graph for a knowledge space.

    Saves to both DB (primary) and JSON file (backup).
    """
    from dbgpt_ext.rag.graph_builder.repo_graph_builder import RepoGraphBuilder

    # 1. Save to DB (primary)
    try:
        from ..service.codegraph_store import CodeGraphStore

        store = CodeGraphStore()
        result = store.save_graph(
            knowledge_id=knowledge_id,
            graph=graph,
            build_source=build_source,
            repo_url=repo_url,
            branch=branch,
        )
        logger.info(
            f"Saved code graph to DB for {knowledge_id}: "
            f"{result['vertex_count']} vertices, {result['edge_count']} edges"
        )
    except Exception as e:
        logger.warning(f"Failed to save code graph to DB for {knowledge_id}: {e}")

    # 2. Save to JSON file (backup)
    graph_dir = _get_graph_cache_dir(knowledge_id)
    os.makedirs(graph_dir, exist_ok=True)
    graph_file = os.path.join(graph_dir, "code_graph.json")

    graph_data = RepoGraphBuilder.graph_to_dict(graph)
    with open(graph_file, "w", encoding="utf-8") as f:
        json.dump(graph_data, f, ensure_ascii=False, indent=2)

    # Update cache
    _graph_cache[knowledge_id] = graph
    logger.info(
        f"Saved code graph to file for {knowledge_id}: "
        f"{graph.vertex_count} vertices, {graph.edge_count} edges"
    )


def _format_graph_result(chunks) -> str:
    """Format retriever chunks into a string for the Agent."""
    if not chunks:
        return (
            "No code structure found. The knowledge base may not have a code "
            "graph built, or no nodes matched the query."
        )
    return "\n".join(chunk.content for chunk in chunks)


def _no_graph_message(knowledge_id: str, load_error: Optional[str]) -> str:
    """Build a helpful message when no code graph is available."""
    error_detail = f" Details: {load_error}" if load_error else ""
    return (
        f"Knowledge space {knowledge_id} has no code graph built."
        f" Ensure the space type is GitRepo and graph building is enabled"
        f" (build_graph=True).{error_detail}"
    )


# ---------------------------------------------------------------------------
# codegraph_explore — main search tool (auto-detects entity/call/inheritance)
# ---------------------------------------------------------------------------


@tool(
    "kb_codegraph_explore",
    description=(
        "Query the code knowledge graph for structural info. "
        "Auto-detects three query modes: entity search ('PaymentService methods'), "
        "call chain ('who calls process_payment'), inheritance ('what implements "
        "PaymentProvider'). Use for code structure, call relations, and class "
        "hierarchies. For exact file content search, use kb_grep instead."
    ),
)
async def kb_codegraph_explore(
    knowledge_id: Annotated[str, "Knowledge space ID"],
    query: Annotated[
        str,
        "Query: class/function name, or natural language like 'who calls X'",
    ],
) -> str:
    """Explore the code knowledge graph for structural information."""
    graph, load_error = _load_graph(knowledge_id)
    if graph is None:
        return _no_graph_message(knowledge_id, load_error)

    from ..retriever.code_graph_retriever import CodeGraphRetriever

    retriever = CodeGraphRetriever(graph=graph, knowledge_id=knowledge_id)
    chunks = retriever.retrieve(query)
    return _format_graph_result(chunks)


# ---------------------------------------------------------------------------
# codegraph_call_chain — call chain tracing
# ---------------------------------------------------------------------------


@tool(
    "kb_codegraph_call_chain",
    description=(
        "Trace the call chain of a function/method in the code graph. "
        "Given a function name, returns all functions that call it (callers, "
        "reverse chain) or all functions it calls (callees, forward chain). "
        "Use for understanding code execution paths and impact analysis."
    ),
)
async def kb_codegraph_call_chain(
    knowledge_id: Annotated[str, "Knowledge space ID"],
    function_name: Annotated[str, "Function or method name to trace"],
    depth: Annotated[int, "Trace depth (default 2, max 6)"] = 2,
    direction: Annotated[
        str, "'callers' (who calls it) or 'callees' (it calls what), default 'callers'"
    ] = "callers",
) -> str:
    """Trace call chains for a function/method in the code graph."""
    # Ensure depth is int — agent tool calls may pass it as str
    depth = int(depth) if depth else 2

    graph, load_error = _load_graph(knowledge_id)
    if graph is None:
        return _no_graph_message(knowledge_id, load_error)

    from ..retriever.code_graph_retriever import CodeGraphRetriever

    retriever = CodeGraphRetriever(
        graph=graph,
        knowledge_id=knowledge_id,
        bfs_depth=min(depth, 6),
    )

    # Find matching nodes
    terms = retriever._extract_search_terms(function_name)
    matched_nodes = retriever._find_matching_nodes(terms)
    if not matched_nodes:
        return f"No function/method found matching: {function_name}"

    # Expand call chain
    reverse = direction == "callers"
    subgraph = retriever._expand_call_chain(matched_nodes, reverse=reverse)

    if subgraph.vertex_count == 0:
        return f"No call chain info found for {function_name}."

    # Format result
    mode_desc = "Callers" if reverse else "Callees"
    chunks = retriever._format_subgraph(
        subgraph, "call_chain", f"{mode_desc} of {function_name}"
    )
    return _format_graph_result(chunks)


# ---------------------------------------------------------------------------
# codegraph_class_hierarchy — inheritance hierarchy tracing
# ---------------------------------------------------------------------------


@tool(
    "kb_codegraph_class_hierarchy",
    description=(
        "Trace the inheritance and implementation hierarchy of a class in the "
        "code graph. Given a class/interface name, returns its parents "
        "(extends/inherits) and children/subclasses/implementations. "
        "Use for understanding class hierarchies and polymorphism."
    ),
)
async def kb_codegraph_class_hierarchy(
    knowledge_id: Annotated[str, "Knowledge space ID"],
    class_name: Annotated[str, "Class or interface name to trace"],
) -> str:
    """Trace class hierarchy in the code graph."""
    graph, load_error = _load_graph(knowledge_id)
    if graph is None:
        return _no_graph_message(knowledge_id, load_error)

    from ..retriever.code_graph_retriever import CodeGraphRetriever

    retriever = CodeGraphRetriever(graph=graph, knowledge_id=knowledge_id)

    # Find matching nodes
    terms = retriever._extract_search_terms(class_name)
    matched_nodes = retriever._find_matching_nodes(terms)
    if not matched_nodes:
        return f"No class/interface found matching: {class_name}"

    # Expand inheritance
    subgraph = retriever._expand_inheritance(matched_nodes)

    if subgraph.vertex_count == 0:
        return f"No inheritance hierarchy info found for {class_name}."

    chunks = retriever._format_subgraph(
        subgraph, "inheritance", f"Hierarchy of {class_name}"
    )
    return _format_graph_result(chunks)
