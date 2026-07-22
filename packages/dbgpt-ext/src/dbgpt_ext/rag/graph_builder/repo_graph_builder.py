"""Repository-level code graph builder (simplified version)."""

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Set

from dbgpt.storage.graph_store.graph import Edge, MemoryGraph, Vertex

logger = logging.getLogger(__name__)

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
MAX_FILE_SIZE = 1_000_000


class RepoGraphBuilder:
    """Build and manage a code knowledge graph for an entire repository."""

    def __init__(
        self, cache_dir: Optional[str] = None, skip_dirs: Optional[Set[str]] = None
    ):
        self._skip_dirs = SKIP_DIRS | (skip_dirs or set())
        self._cache_dir = cache_dir

    async def build_from_repo(
        self, repo_dir: str, repo_url: str = "", repo_name: str = ""
    ) -> Optional[MemoryGraph]:
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
        self, files: List[Dict[str, Any]], repo_url: str = "", repo_name: str = ""
    ) -> Optional[MemoryGraph]:
        graph = MemoryGraph()
        repo_id = _make_id("repo", repo_name or "unknown")
        graph.upsert_vertex(
            Vertex(
                vid=repo_id,
                name=repo_name or "unknown",
                type="repository",
                url=repo_url,
            )
        )
        for file_info in files:
            if isinstance(file_info, dict):
                file_path, content = (
                    file_info.get("path", ""),
                    file_info.get("content", ""),
                )
            else:
                file_path, content = (
                    getattr(file_info, "path", ""),
                    getattr(file_info, "content", ""),
                )
            if not file_path or not content or len(content) > MAX_FILE_SIZE:
                continue
            try:
                self._extract_file_to_graph(graph, file_path, content, repo_id)
            except Exception as e:
                logger.debug(f"Failed to extract graph from {file_path}: {e}")
                continue
        if self._cache_dir:
            self._save_graph_to_file(graph, repo_name or "unknown")
        logger.info(
            f"Built code graph: {graph.vertex_count} vertices, {graph.edge_count} edges"
        )
        return graph

    def _scan_repo_files(self, repo_dir: str) -> List[Dict[str, Any]]:
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
        self, graph: MemoryGraph, file_path: str, content: str, repo_id: str
    ):
        language = _get_language_from_extension(file_path)
        file_id = _make_id("file", file_path)
        graph.upsert_vertex(
            Vertex(
                vid=file_id,
                name=os.path.basename(file_path),
                type="file",
                path=file_path,
                language=language,
            )
        )
        graph.append_edge(
            Edge(sid=repo_id, tid=file_id, name="contains", type="contains")
        )
        if language == "markdown":
            # Markdown files: extract heading hierarchy (H1 -> H2 -> H3)
            self._extract_markdown_nodes(graph, file_path, content, file_id)
        elif language in _AST_LANGUAGES:
            try:
                self._extract_ast_nodes(graph, file_path, content, language, file_id)
            except Exception:
                self._extract_regex_nodes(graph, file_path, content, language, file_id)
        else:
            self._extract_regex_nodes(graph, file_path, content, language, file_id)

    def _extract_markdown_nodes(
        self, graph: MemoryGraph, file_path: str, content: str, file_id: str
    ):
        """Extract markdown heading hierarchy into graph vertices/edges.

        Builds a parent-child structure following the heading levels:
        file -> contains -> H1 -> contains -> H2 -> contains -> H3

        Uses a stack-based approach (same as MarkdownHeaderTextSplitter) to
        track the current parent heading at each level. Headings inside code
        blocks (``` ... ```) are ignored.
        """
        heading_pattern = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
        # Stack of (level, heading_id) for the current heading ancestry
        header_stack: List[tuple] = []
        in_code_block = False

        for line in content.split("\n"):
            stripped = line.strip()
            # Track fenced code blocks to avoid parsing # inside them
            if stripped.startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue

            match = heading_pattern.match(stripped)
            if not match:
                continue

            level = len(match.group(1))
            title = match.group(2).strip()
            if not title:
                continue

            # Pop headers of same or deeper level (they can't be parents)
            while header_stack and header_stack[-1][0] >= level:
                header_stack.pop()

            # Parent is the top of stack (or the file vertex if stack empty)
            parent_id = header_stack[-1][1] if header_stack else file_id

            heading_id = _make_id("heading", f"{file_path}:{level}:{title}")
            graph.upsert_vertex(
                Vertex(
                    vid=heading_id,
                    name=title,
                    type="heading",
                    level=level,
                    heading_text=title,
                    file_path=file_path,
                )
            )
            graph.append_edge(
                Edge(sid=parent_id, tid=heading_id, name="contains", type="contains")
            )

            header_stack.append((level, heading_id))

    def _extract_ast_nodes(self, graph, file_path, content, language, file_id):
        try:
            from dbgpt.rag.text_splitter.tree_sitter_utils import (
                LANGUAGE_NODE_TYPES,
                get_parser,
            )

            parser = get_parser(language)
        except (ImportError, ValueError):
            self._extract_regex_nodes(graph, file_path, content, language, file_id)
            return
        source_bytes = content.encode("utf-8")
        tree = parser.parse(source_bytes)
        target_types = LANGUAGE_NODE_TYPES.get(language, [])
        for node in self._walk_tree(tree.root_node):
            if node.type in target_types:
                name = _extract_node_name(node)
                if not name:
                    continue
                node_type = _map_node_type(node.type)
                node_id = _make_id(node_type, f"{file_path}:{name}")
                graph.upsert_vertex(
                    Vertex(
                        vid=node_id,
                        name=name,
                        type=node_type,
                        file_path=file_path,
                        language=language,
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                    )
                )
                graph.append_edge(
                    Edge(sid=file_id, tid=node_id, name="defines", type="defines")
                )

    def _extract_regex_nodes(self, graph, file_path, content, language, file_id):
        import re

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
                            type=node_type,
                            file_path=file_path,
                            language=language,
                            start_line=line_no,
                        )
                    )
                    graph.append_edge(
                        Edge(sid=file_id, tid=node_id, name="defines", type="defines")
                    )

    def _walk_tree(self, node):
        yield node
        for child in node.children:
            yield from self._walk_tree(child)

    def _save_graph_to_file(self, graph: MemoryGraph, repo_name: str):
        if not self._cache_dir:
            return
        os.makedirs(self._cache_dir, exist_ok=True)
        graph_file = os.path.join(self._cache_dir, "code_graph.json")
        with open(graph_file, "w", encoding="utf-8") as f:
            json.dump(self.graph_to_dict(graph), f, ensure_ascii=False, indent=2)

    @staticmethod
    def remove_file_from_graph(graph: MemoryGraph, file_path: str):
        vertices_to_remove = [
            v.vid for v in graph.vertices() if v.get_prop("file_path") == file_path
        ]
        for vid in vertices_to_remove:
            for edge in list(graph.edges()):
                if edge.sid == vid or edge.tid == vid:
                    graph.del_edge(edge.sid, edge.tid, edge.name)
            graph.del_vertex(vid)

    @staticmethod
    def graph_to_dict(graph: MemoryGraph) -> Dict:
        vertices = [
            {"vid": v.vid, "name": v.name, "props": dict(v.props)}
            for v in graph.vertices()
        ]
        edges = [
            {"sid": e.sid, "tid": e.tid, "name": e.name, "props": dict(e.props)}
            for e in graph.edges()
        ]
        return {"vertices": vertices, "edges": edges}

    @staticmethod
    def dict_to_graph(data: Dict) -> MemoryGraph:
        graph = MemoryGraph()
        for v in data.get("vertices", []):
            graph.upsert_vertex(
                Vertex(vid=v["vid"], name=v.get("name", ""), **v.get("props", {}))
            )
        for e in data.get("edges", []):
            graph.append_edge(
                Edge(
                    sid=e["sid"],
                    tid=e["tid"],
                    name=e.get("name", ""),
                    **e.get("props", {}),
                )
            )
        return graph


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
    return f"{prefix}:{name}"


def _get_language_from_extension(file_path: str) -> str:
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
    type_map = {
        "function_definition": "function",
        "class_definition": "class",
        "method_declaration": "method",
        "constructor_declaration": "constructor",
        "interface_declaration": "interface",
        "function_declaration": "function",
        "method_definition": "method",
        "function_item": "function",
        "impl_item": "impl",
        "struct_item": "struct",
        "enum_item": "enum",
        "trait_item": "trait",
    }
    return type_map.get(ast_type, ast_type)
