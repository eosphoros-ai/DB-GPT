"""Knowledge base search tools package.

Provides structured search tools for agents:
- kb_ls: List files and directories in a knowledge space
- kb_glob: Search files by name pattern
- kb_grep: Search file contents by keyword
- kb_cat: Read file content by path
- kb_semantic_search: Semantic search using vector retrieval
- kb_codegraph_explore: Code knowledge graph exploration
"""

# Import tool modules to register them with the @tool decorator
from . import kb_file_tools  # noqa: F401
from . import semantic_search_tool  # noqa: F401

# CodeGraph tools - optional, requires graph_store
try:
    from . import codegraph_tools  # noqa: F401
except ImportError:
    pass

__all__ = ["kb_file_tools", "semantic_search_tool", "codegraph_tools"]