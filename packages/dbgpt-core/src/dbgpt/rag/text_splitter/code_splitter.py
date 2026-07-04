"""Code Text Splitter - Split code files by AST nodes using tree-sitter.

Splits code into semantic chunks at function/class/method boundaries,
preserving complete code structures for better RAG retrieval.
"""

import logging
from typing import Any, List

from dbgpt.core import Chunk
from dbgpt.rag.text_splitter.text_splitter import TextSplitter
from dbgpt.rag.text_splitter.tree_sitter_utils import (
    GRAMMAR_MODULES,
    LANGUAGE_NODE_TYPES,
    extract_imports,
    extract_name,
    get_parser,
)

logger = logging.getLogger(__name__)

# Backward-compatible aliases for external consumers
_GRAMMAR_MODULES = GRAMMAR_MODULES
_get_parser = get_parser
_extract_name = extract_name
_extract_imports = extract_imports


class CodeTextSplitter(TextSplitter):
    """Split code files by AST nodes (functions, classes, methods).

    Uses tree-sitter to parse code into an AST, then extracts
    function/class/method definitions as individual chunks.
    Each chunk includes the file's import statements as context.
    """

    def __init__(
        self,
        language: str = "python",
        chunk_size: int = 4000,
        chunk_overlap: int = 200,
        **kwargs: Any,
    ):
        """Create a CodeTextSplitter.

        Args:
            language: Programming language (python, java, go, etc.)
            chunk_size: Maximum chunk size in characters.
            chunk_overlap: Overlap between chunks (not used for AST splitting).
        """
        super().__init__(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            **kwargs,
        )
        self._language = language
        self._target_types = LANGUAGE_NODE_TYPES.get(language, [])
        self._parser = None

    def _get_parser(self):
        """Lazy-load the parser."""
        if self._parser is None:
            self._parser = _get_parser(self._language)
        return self._parser

    def split_text(self, text: str, **kwargs) -> List[str]:
        """Split code text into chunks by AST nodes."""
        if not text.strip():
            return []

        if not self._target_types:
            # Language not supported for AST, fall back to line-based split
            return self._fallback_split(text)

        try:
            parser = self._get_parser()
        except (ImportError, ValueError) as e:
            logger.warning(
                f"tree-sitter not available for {self._language}: {e}, "
                f"falling back to line-based split"
            )
            return self._fallback_split(text)

        source_bytes = text.encode("utf-8")
        tree = parser.parse(source_bytes)

        # Extract imports as context prefix
        imports_text = _extract_imports(source_bytes, tree)

        # Collect target AST nodes
        chunks = []
        covered_ranges = []

        self._collect_nodes(
            tree.root_node, source_bytes, imports_text, chunks, covered_ranges
        )

        # Collect uncovered top-level code (constants, globals, etc.)
        top_level_text = self._collect_uncovered(
            tree.root_node, source_bytes, covered_ranges
        )
        if top_level_text.strip():
            chunks.insert(0, top_level_text)

        # Merge small chunks
        chunks = self._merge_small_chunks(chunks)

        return chunks if chunks else [text]

    def _collect_nodes(
        self,
        node,
        source_bytes: bytes,
        imports_text: str,
        chunks: List[str],
        covered_ranges: List[tuple],
    ):
        """Recursively collect target AST nodes as chunks."""
        if node.type in self._target_types:
            node_text = source_bytes[node.start_byte : node.end_byte].decode("utf-8")
            node_len = len(node_text)

            if node_len <= self._chunk_size:
                # Node fits in one chunk - prepend imports for context
                if imports_text:
                    chunk_text = f"{imports_text}\n\n{node_text}"
                else:
                    chunk_text = node_text
                chunks.append(chunk_text)
                covered_ranges.append((node.start_byte, node.end_byte))
            else:
                # Node too large, try splitting into children
                has_child_targets = False
                for child in node.children:
                    if child.type in self._target_types:
                        has_child_targets = True
                        break

                if has_child_targets:
                    # Recurse into children
                    for child in node.children:
                        self._collect_nodes(
                            child, source_bytes, imports_text, chunks, covered_ranges
                        )
                    covered_ranges.append((node.start_byte, node.end_byte))
                else:
                    # No child targets, just include the whole node
                    if imports_text:
                        chunk_text = f"{imports_text}\n\n{node_text}"
                    else:
                        chunk_text = node_text
                    chunks.append(chunk_text)
                    covered_ranges.append((node.start_byte, node.end_byte))
            return

        # Not a target node, recurse into children
        for child in node.children:
            self._collect_nodes(
                child, source_bytes, imports_text, chunks, covered_ranges
            )

    def _collect_uncovered(
        self,
        root_node,
        source_bytes: bytes,
        covered_ranges: List[tuple],
    ) -> str:
        """Collect top-level code that isn't part of any target node."""
        uncovered_parts = []
        for child in root_node.children:
            child_start = child.start_byte
            child_end = child.end_byte

            # Check if this child is covered by any collected node
            is_covered = False
            for start, end in covered_ranges:
                if child_start >= start and child_end <= end:
                    is_covered = True
                    break

            if not is_covered:
                text = source_bytes[child_start:child_end].decode("utf-8").strip()
                if text:
                    uncovered_parts.append(text)

        return "\n\n".join(uncovered_parts)

    def _merge_small_chunks(self, chunks: List[str]) -> List[str]:
        """Merge consecutive small chunks that together fit in chunk_size."""
        if not chunks:
            return chunks

        merged = []
        buffer = ""
        for chunk in chunks:
            if not buffer:
                buffer = chunk
            elif len(buffer) + len(chunk) + 2 <= self._chunk_size:
                buffer = f"{buffer}\n\n{chunk}"
            else:
                merged.append(buffer)
                buffer = chunk
        if buffer:
            merged.append(buffer)
        return merged

    def _fallback_split(self, text: str) -> List[str]:
        """Fallback: split by double newlines when AST parsing unavailable."""
        paragraphs = text.split("\n\n")
        chunks = []
        buffer = ""
        for para in paragraphs:
            if not buffer:
                buffer = para
            elif len(buffer) + len(para) + 2 <= self._chunk_size:
                buffer = f"{buffer}\n\n{para}"
            else:
                chunks.append(buffer)
                buffer = para
        if buffer:
            chunks.append(buffer)
        return chunks if chunks else [text]

    def split_documents(self, documents, **kwargs) -> List[Chunk]:
        """Split documents into chunks with code-specific metadata."""
        all_chunks = []
        for doc in documents:
            text = doc.content or ""
            source_bytes = text.encode("utf-8") if text else b""
            metadata = doc.metadata or {}

            # Parse for metadata extraction
            parser = None
            tree = None
            try:
                parser = self._get_parser()
                tree = parser.parse(source_bytes) if source_bytes else None
            except Exception:
                pass

            split_texts = self.split_text(text)

            for i, chunk_text in enumerate(split_texts):
                chunk_metadata = {**metadata}

                # Try to extract symbol info from the chunk
                if tree and parser:
                    symbol_name, symbol_type, start_line, end_line = (
                        self._extract_chunk_symbol_info(chunk_text, source_bytes, tree)
                    )
                    if symbol_name:
                        chunk_metadata["symbol_name"] = symbol_name
                    if symbol_type:
                        chunk_metadata["symbol_type"] = symbol_type
                    if start_line is not None:
                        chunk_metadata["start_line"] = start_line
                    if end_line is not None:
                        chunk_metadata["end_line"] = end_line

                chunk_metadata["chunk_index"] = i

                all_chunks.append(Chunk(content=chunk_text, metadata=chunk_metadata))

        return all_chunks

    def _extract_chunk_symbol_info(
        self, chunk_text: str, source_bytes: bytes, tree
    ) -> tuple:
        """Extract symbol name and type from a chunk by matching AST nodes."""
        # Find the main definition in the chunk text
        for node in self._walk_target_nodes(tree.root_node):
            node_text = source_bytes[node.start_byte : node.end_byte].decode("utf-8")
            if node_text in chunk_text:
                name = _extract_name(node)
                return (
                    name,
                    node.type,
                    node.start_point[0] + 1,
                    node.end_point[0] + 1,
                )
        return (None, None, None, None)

    def _walk_target_nodes(self, node):
        """Walk AST and yield target nodes."""
        if node.type in self._target_types:
            yield node
        for child in node.children:
            yield from self._walk_target_nodes(child)
