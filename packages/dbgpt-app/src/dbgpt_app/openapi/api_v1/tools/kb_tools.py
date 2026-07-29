"""Factory functions for knowledge base file tools bound to a specific space.

These wrap the generic kb_ls, kb_glob, kb_grep, kb_cat, and kb_semantic_search
tools so that `knowledge_id` is pre-bound and the LLM does not need to provide it.
"""

from typing import List

from dbgpt.agent.resource.tool.base import tool


def make_kb_ls(knowledge_id: str):
    """Create a kb_ls tool bound to a specific knowledge space."""

    @tool(
        "kb_ls",
        description=(
            "List files and directories in the knowledge base. "
            "Use this to explore the repository structure, find what files exist, "
            "and navigate directories. "
            'Parameters: {{"path": "directory path (optional, default root)"}}'
        ),
    )
    async def _kb_ls(path: str = "") -> str:
        from dbgpt_serve.rag.tools.kb_file_tools import kb_ls as _impl

        return await _impl(knowledge_id=knowledge_id, path=path)

    return _kb_ls


def make_kb_glob(knowledge_id: str):
    """Create a kb_glob tool bound to a specific knowledge space."""

    @tool(
        "kb_glob",
        description=(
            "Search files by name or glob pattern in the knowledge base. "
            "Use this to find files matching a pattern, e.g. '*.py', "
            "'*test*', 'src/**/*.ts'. "
            'Parameters: {{"pattern": "file name keyword or glob pattern"}}'
        ),
    )
    async def _kb_glob(pattern: str) -> str:
        from dbgpt_serve.rag.tools.kb_file_tools import kb_glob as _impl

        return await _impl(knowledge_id=knowledge_id, pattern=pattern)

    return _kb_glob


def make_kb_grep(knowledge_id: str):
    """Create a kb_grep tool bound to a specific knowledge space."""

    @tool(
        "kb_grep",
        description=(
            "Search file contents by keyword in the knowledge base. "
            "Use this to find code or text containing a specific keyword or phrase. "
            "Prefer this over semantic search for exact matches. "
            'Parameters: {{"query": "search keyword", '
            '"path": "directory filter (optional)", '
            '"file_pattern": "file pattern like *.py (optional)"}}'
        ),
    )
    async def _kb_grep(
        query: str,
        path: str = "",
        file_pattern: str = "",
    ) -> str:
        from dbgpt_serve.rag.tools.kb_file_tools import kb_grep as _impl

        return await _impl(
            knowledge_id=knowledge_id,
            query=query,
            path=path,
            file_pattern=file_pattern,
        )

    return _kb_grep


def make_kb_cat(knowledge_id: str):
    """Create a kb_cat tool bound to a specific knowledge space."""

    @tool(
        "kb_cat",
        description=(
            "Read the content of a specific file in the knowledge base. "
            "Use this after kb_ls or kb_glob to read a file you found. "
            'Parameters: {{"path": "file path like src/main.py", '
            '"start_line": "start line number (optional, default 1)", '
            '"end_line": "end line number (optional, 0 = to end)"}}'
        ),
    )
    async def _kb_cat(
        path: str,
        start_line: int = 1,
        end_line: int = 0,
    ) -> str:
        from dbgpt_serve.rag.tools.kb_file_tools import kb_cat as _impl

        return await _impl(
            knowledge_id=knowledge_id,
            path=path,
            start_line=start_line,
            end_line=end_line,
        )

    return _kb_cat


def make_kb_semantic_search(knowledge_id: str):
    """Create a semantic_search tool bound to a specific knowledge space."""

    @tool(
        "semantic_search",
        description=(
            "Semantic search in the knowledge base. "
            "Use this when you need to find information by meaning rather "
            "than exact keywords. "
            "Prefer kb_grep for exact keyword matches; use semantic_search when "
            "kb_grep returns empty or insufficient results. "
            'Parameters: {{"query": "search query in natural language", '
            '"top_k": "number of results (optional, default 5)"}}'
        ),
    )
    async def _semantic_search(
        query: str,
        top_k: int = 5,
    ) -> str:
        from dbgpt_serve.rag.tools.semantic_search_tool import (
            kb_semantic_search as _impl,
        )

        return await _impl(
            knowledge_id=knowledge_id,
            query=query,
            top_k=top_k,
        )

    return _semantic_search


def make_kb_codegraph_explore(knowledge_id: str):
    """Create a kb_codegraph_explore tool bound to a specific knowledge space."""

    @tool(
        "kb_codegraph_explore",
        description=(
            "Query the code knowledge graph for structural info. "
            "Auto-detects entity/call-chain/inheritance modes. "
            'Parameters: {{"query": "class/function name or \'who calls X\'"}}'
        ),
    )
    async def _kb_codegraph_explore(query: str) -> str:
        from dbgpt_serve.rag.tools.codegraph_tools import kb_codegraph_explore as _impl

        return await _impl(knowledge_id=knowledge_id, query=query)

    return _kb_codegraph_explore


def make_kb_codegraph_call_chain(knowledge_id: str):
    """Create a kb_codegraph_call_chain tool bound to a specific knowledge space."""

    @tool(
        "kb_codegraph_call_chain",
        description=(
            "Trace the call chain of a function/method in the code graph. "
            "Returns callers (who calls it) or callees (it calls what). "
            'Parameters: {{"function_name": "function name", '
            '"depth": "trace depth (optional, default 2)", '
            '"direction": "callers or callees (optional, default callers)"}}'
        ),
    )
    async def _kb_codegraph_call_chain(
        function_name: str,
        depth: int = 2,
        direction: str = "callers",
    ) -> str:
        from dbgpt_serve.rag.tools.codegraph_tools import (
            kb_codegraph_call_chain as _impl,
        )

        return await _impl(
            knowledge_id=knowledge_id,
            function_name=function_name,
            depth=depth,
            direction=direction,
        )

    return _kb_codegraph_call_chain


def make_kb_codegraph_class_hierarchy(knowledge_id: str):
    """Create a kb_codegraph_class_hierarchy tool bound to a specific space."""

    @tool(
        "kb_codegraph_class_hierarchy",
        description=(
            "Trace the inheritance and implementation hierarchy of a class. "
            "Returns parents (extends/inherits) and children/implementations. "
            'Parameters: {{"class_name": "class or interface name"}}'
        ),
    )
    async def _kb_codegraph_class_hierarchy(class_name: str) -> str:
        from dbgpt_serve.rag.tools.codegraph_tools import (
            kb_codegraph_class_hierarchy as _impl,
        )

        return await _impl(
            knowledge_id=knowledge_id,
            class_name=class_name,
        )

    return _kb_codegraph_class_hierarchy


def make_kb_tools(knowledge_id: str) -> List:
    """Create all knowledge base tools bound to a specific space.

    Returns a list of tool instances:
    - kb_ls: List files and directories
    - kb_glob: Search files by name pattern
    - kb_grep: Search file contents by keyword
    - kb_cat: Read file content
    - semantic_search: Semantic search
    - kb_codegraph_explore: Query code graph (entity/call/inheritance)
    - kb_codegraph_call_chain: Trace function call chains
    - kb_codegraph_class_hierarchy: Trace class inheritance

    Note: codegraph tools are always returned; callers are responsible for
    filtering them out when the knowledge space has no built code graph.
    """
    return [
        make_kb_ls(knowledge_id),
        make_kb_glob(knowledge_id),
        make_kb_grep(knowledge_id),
        make_kb_cat(knowledge_id),
        make_kb_semantic_search(knowledge_id),
        make_kb_codegraph_explore(knowledge_id),
        make_kb_codegraph_call_chain(knowledge_id),
        make_kb_codegraph_class_hierarchy(knowledge_id),
    ]
