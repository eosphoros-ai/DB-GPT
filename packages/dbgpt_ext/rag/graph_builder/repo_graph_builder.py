"""Repository-level code graph builder.

Builds a code knowledge graph from repository files using AST parsing.
Provides structural code search capabilities (call chains, class hierarchies).

This is a simplified version that focuses on the core graph building
and query functionality. Full cross-file resolution and incremental
caching can be added incrementally.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional, Set

from dbgpt.storage.graph_store.graph import Edge, MemoryGraph, Vertex

logger = logging.getLogger(__name__)

# Directories to skip during graph scanning
SKIP_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "dist",
    "build",
    ".idea",
    ".vscode",
    "vendor",
    "target",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".eggs",
    "egg-info",
    ".next",
    ".nuxt",
    "out",
    "coverage",
    ".gradle",
    ".mvn",
}

# Maximum file size to extract (1MB)
MAX_FILE_SIZE = 1_000_000


class RepoGraphBuilder:
    """Build and manage a code knowledge graph for an entire repository.

    Usage::

        builder = RepoGraphBuilder()
        graph = await builder.build_from_repo(
            "/path/to/repo", "https://github.com/org/repo"
        )

        # Build from in-memory files
        graph = await builder.build_from_files(
            files=[{"path": "src/main.py", "content": "..."}],
            repo_url="https://github.com/org/repo",
        )
    """

    def __init__(
        self,
        cache_dir: Optional[str] = None,
        skip_dirs: Optional[Set[str]] = None,
    ):
        """Initialize the repo graph builder.

        Args:
            cache_dir: Directory for graph cache persistence.
            skip_dirs: Additional directories to skip.
        """
        self._skip_dirs = SKIP_DIRS | (skip_dirs or set())
        self._cache_dir = cache_dir

    async def build_from_repo(
        self,
        repo_dir: str,
        repo_url: str = "",
        repo_name: str = "",
    ) -> Optional[MemoryGraph]:
        """Build a code graph from a cloned repository directory.

        Args:
            repo_dir: Path to the cloned repository.
            repo_url: Repository URL (stored in graph metadata).
            repo_name: Repository name (stored in graph metadata).

        Returns:
            MemoryGraph with code structure, or None if building fails.
        """
        try:
            files = self._scan_repo_files(repo_dir)
            return await self.build_from_files(
                files=files,
                repo_url=repo_url,
                repo_name=repo_name or os.path.basename(repo_dir),
            )
        except Exception as e:
            logger.warning(f"Failed to build code graph from repo: {e}")
            return None

    async def build_from_files(
        self,
        files: List[Dict[str, Any]],
        repo_url: str = "",
        repo_name: str = "",
    ) -> Optional[MemoryGraph]:
        """Build a code graph from a list of file dicts.

        Args:
            files: List of dicts with 'path' and 'content' keys.
            repo_url: Repository URL.
            repo_name: Repository name.

        Returns:
            MemoryGraph with code structure.
        """
        graph = MemoryGraph()

        # Add repository root node
        repo_id = _make_id("repo", repo_name or "unknown")
        graph.upsert_vertex(
            Vertex(
                vid=repo_id,
                name=repo_name or "unknown",
                label="repository",
                props={"url": repo_url, "type": "repository"},
            )
        )

        # Extract per-file graphs
        for file_info in files:
            if isinstance(file_info, dict):
                file_path = file_info.get("path", "")
                content = file_info.get("content", "")
            else:
                file_path = getattr(file_info, "path", "")
                content = getattr(file_info, "content", "")

            if not file_path or not content:
                continue

            if len(content) > MAX_FILE_SIZE:
                continue

            try:
                self._extract_file_to_graph(graph, file_path, content, repo_id)
            except Exception as e:
                logger.debug(f"Failed to extract graph from {file_path}: {e}")
                continue

        # Persist if cache_dir is set
        if self._cache_dir:
            self._save_graph_to_file(graph, repo_name or "unknown")

        logger.info(
            f"Built code graph: {graph.vertex_count} vertices, "
            f"{graph.edge_count} edges from {len(files)} files"
        )
        return graph

    def _scan_repo_files(self, repo_dir: str) -> List[Dict[str, Any]]:
        """Scan a repository directory and return file dicts."""
        files = []
        for root, dirs, filenames in os.walk(repo_dir):
            dirs[:] = [
                d for d in dirs if d not in self._skip_dirs and not d.startswith(".")
            ]
            for filename in sorted(filenames):
                if filename.startswith("."):
                    continue
                abs_path = os.path.join(root, filename)
                rel_path = os.path.relpath(abs_path, repo_dir)
                try:
                    if os.path.getsize(abs_path) > MAX_FILE_SIZE:
                        continue
                    with open(abs_path, encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    files.append({"path": rel_path, "content": content})
                except Exception:
                    continue
        return files

    def _extract_file_to_graph(
        self,
        graph: MemoryGraph,
        file_path: str,
        content: str,
        repo_id: str,
    ):
        """Extract code structure from a single file and add to graph.

        Uses tree-sitter AST parsing for supported languages,
        falls back to regex-based extraction for others.
        """
        ext = os.path.splitext(file_path)[1].lower()
        language = _get_language_from_extension(file_path)

        # Add file node
        file_id = _make_id("file", file_path)
        graph.upsert_vertex(
            Vertex(
                vid=file_id,
                name=os.path.basename(file_path),
                label="file",
                props={
                    "path": file_path,
                    "language": language,
                    "type": "file",
                },
            )
        )

        # Add containment edge: repo -> file
        graph.append_edge(
            Edge(
                sid=repo_id,
                tid=file_id,
                name="contains",
                label="contains",
                props={"type": "contains"},
            )
        )

        # Try AST-based extraction
        if language in _AST_LANGUAGES:
            try:
                self._extract_ast_nodes(graph, file_path, content, language, file_id)
            except Exception as e:
                logger.debug(f"AST extraction failed for {file_path}: {e}")
                # Fall back to regex
                self._extract_regex_nodes(graph, file_path, content, language, file_id)
        else:
            # Regex-based extraction for non-AST languages
            self._extract_regex_nodes(graph, file_path, content, language, file_id)

    def _extract_ast_nodes(
        self,
        graph: MemoryGraph,
        file_path: str,
        content: str,
        language: str,
        file_id: str,
    ):
        """Extract code nodes using tree-sitter AST parsing."""
        try:
            from dbgpt.rag.text_splitter.tree_sitter_utils import get_parser

            parser = get_parser(language)
        except (ImportError, ValueError):
            self._extract_regex_nodes(graph, file_path, content, language, file_id)
            return

        source_bytes = content.encode("utf-8")
        tree = parser.parse(source_bytes)

        from dbgpt.rag.text_splitter.tree_sitter_utils import LANGUAGE_NODE_TYPES

        target_types = LANGUAGE_NODE_TYPES.get(language, [])

        for node in self._walk_tree(tree.root_node):
            if node.type in target_types:
                name = _extract_node_name(node)
                if not name:
                    continue

                node_type = _map_node_type(node.type)
                node_id = _make_id(node_type, f"{file_path}:{name}")

                # Add vertex
                graph.upsert_vertex(
                    Vertex(
                        vid=node_id,
                        name=name,
                        label=node_type,
                        props={
                            "type": node_type,
                            "file_path": file_path,
                            "language": language,
                            "start_line": node.start_point[0] + 1,
                            "end_line": node.end_point[0] + 1,
                        },
                    )
                )

                # Add containment edge: file -> node
                graph.append_edge(
                    Edge(
                        sid=file_id,
                        tid=node_id,
                        name="defines",
                        label="defines",
                        props={"type": "defines"},
                    )
                )

    def _extract_regex_nodes(
        self,
        graph: MemoryGraph,
        file_path: str,
        content: str,
        language: str,
        file_id: str,
    ):
        """Extract code nodes using regex patterns (fallback)."""
        import re

        # Python-style class/function patterns
        patterns = [
            (r"^\s*(?:async\s+)?def\s+(\w+)", "function"),
            (r"^\s*class\s+(\w+)", "class"),
        ]

        for line_no, line in enumerate(content.split("\n"), 1):
            for pattern, node_type in patterns:
                match = re.match(pattern, line)
                if match:
                    name = match.group(1)
                    node_id = _make_id(node_type, f"{file_path}:{name}")

                    graph.upsert_vertex(
                        Vertex(
                            vid=node_id,
                            name=name,
                            label=node_type,
                            props={
                                "type": node_type,
                                "file_path": file_path,
                                "language": language,
                                "start_line": line_no,
                            },
                        )
                    )

                    graph.append_edge(
                        Edge(
                            sid=file_id,
                            tid=node_id,
                            name="defines",
                            label="defines",
                            props={"type": "defines"},
                        )
                    )

    def _walk_tree(self, node):
        """Walk AST tree depth-first."""
        yield node
        for child in node.children:
            yield from self._walk_tree(child)

    def _save_graph_to_file(self, graph: MemoryGraph, repo_name: str):
        """Save graph to JSON file for persistence."""
        if not self._cache_dir:
            return
        os.makedirs(self._cache_dir, exist_ok=True)
        graph_file = os.path.join(self._cache_dir, "code_graph.json")
        graph_data = self.graph_to_dict(graph)
        with open(graph_file, "w", encoding="utf-8") as f:
            json.dump(graph_data, f, ensure_ascii=False, indent=2)

    @staticmethod
    def remove_file_from_graph(graph: MemoryGraph, file_path: str):
        """Remove all vertices and edges associated with a file path."""
        vertices_to_remove = []
        for vertex in graph.vertices():
            if vertex.props.get("file_path") == file_path:
                vertices_to_remove.append(vertex.vid)

        for vid in vertices_to_remove:
            # Remove edges connected to this vertex
            for edge in graph.edges():
                if edge.sid == vid or edge.tid == vid:
                    graph.del_edge(edge.sid, edge.tid, edge.name)
            graph.del_vertex(vid)

    @staticmethod
    def graph_to_dict(graph: MemoryGraph) -> Dict:
        """Serialize MemoryGraph to a dictionary."""
        vertices = []
        for v in graph.vertices():
            vertices.append(
                {
                    "vid": v.vid,
                    "name": v.name,
                    "label": v.label,
                    "props": dict(v.props),
                }
            )

        edges = []
        for e in graph.edges():
            edges.append(
                {
                    "sid": e.sid,
                    "tid": e.tid,
                    "name": e.name,
                    "label": e.label,
                    "props": dict(e.props),
                }
            )

        return {"vertices": vertices, "edges": edges}

    @staticmethod
    def dict_to_graph(data: Dict) -> MemoryGraph:
        """Deserialize a dictionary to MemoryGraph."""
        graph = MemoryGraph()
        for v in data.get("vertices", []):
            graph.upsert_vertex(
                Vertex(
                    vid=v["vid"],
                    name=v.get("name", ""),
                    label=v.get("label", ""),
                    props=v.get("props", {}),
                )
            )
        for e in data.get("edges", []):
            graph.append_edge(
                Edge(
                    sid=e["sid"],
                    tid=e["tid"],
                    name=e.get("name", ""),
                    label=e.get("label", ""),
                    props=e.get("props", {}),
                )
            )
        return graph


# Helper functions

_AST_LANGUAGES = {
    "python",
    "java",
    "javascript",
    "typescript",
    "go",
    "rust",
    "c",
    "cpp",
}


def _make_id(prefix: str, name: str) -> str:
    """Create a unique ID for a graph element."""
    return f"{prefix}:{name}"


def _get_language_from_extension(file_path: str) -> str:
    """Get programming language from file extension."""
    ext_map = {
        ".py": "python",
        ".java": "java",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".go": "go",
        ".rs": "rust",
        ".c": "c",
        ".h": "c",
        ".cpp": "cpp",
        ".cc": "cpp",
        ".cxx": "cpp",
        ".hpp": "cpp",
        ".rb": "ruby",
        ".php": "php",
        ".scala": "scala",
        ".kt": "kotlin",
        ".swift": "swift",
        ".sh": "bash",
        ".md": "markdown",
    }
    _, ext = os.path.splitext(file_path)
    return ext_map.get(ext.lower(), "text")


def _extract_node_name(node) -> str:
    """Extract the name from an AST node."""
    for child in node.children:
        if child.type in (
            "identifier",
            "name",
            "type_identifier",
            "field_identifier",
            "property_identifier",
        ):
            return child.text.decode("utf-8")
        if child.type == "function_declarator":
            return _extract_node_name(child)
    return ""


def _map_node_type(ast_type: str) -> str:
    """Map AST node type to a simplified graph node type."""
    type_map = {
        "function_definition": "function",
        "class_definition": "class",
        "method_declaration": "method",
        "constructor_declaration": "constructor",
        "interface_declaration": "interface",
        "function_declaration": "function",
        "method_definition": "method",
        "export_statement": "export",
        "function_item": "function",
        "impl_item": "impl",
        "struct_item": "struct",
        "enum_item": "enum",
        "trait_item": "trait",
        "type_declaration": "type",
    }
    return type_map.get(ast_type, ast_type)
