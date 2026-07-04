"""CodeGraph Build Service - Build code knowledge graphs for git repo knowledge spaces.

Provides functions to build code graphs from repository files and persist them
for later querying by codegraph tools.
"""

import hashlib
import logging
import os
import tempfile
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


async def build_code_graph_from_knowledge_space(
    knowledge_id: str,
) -> Optional[Dict]:
    """Build a code graph by reconstructing files from chunks in the DB.

    This is a fallback method when the original files are not available
    (e.g., after a service restart). It reconstructs file contents from
    the stored chunks and builds the graph from those.

    Args:
        knowledge_id: Knowledge space ID.

    Returns:
        Dict with graph stats, or None if building fails.
    """
    try:
        from ..models.chunk_db import DocumentChunkDao, DocumentChunkEntity
        from ..models.document_db import KnowledgeDocumentDao, KnowledgeDocumentEntity
        from ..tools.codegraph_tools import _save_graph

        # Get all documents for this knowledge space
        doc_dao = KnowledgeDocumentDao()
        docs = doc_dao.get_knowledge_documents(
            KnowledgeDocumentEntity(knowledge_id=knowledge_id),
            page=1,
            page_size=100000,
        )
        if not docs:
            logger.warning(f"No documents found for knowledge_id={knowledge_id}")
            return None

        # Reconstruct files from chunks
        import json

        files_by_path = {}
        chunk_dao = DocumentChunkDao()

        for doc in docs:
            try:
                meta = json.loads(doc.meta_data) if doc.meta_data else {}
            except (json.JSONDecodeError, TypeError):
                meta = {}

            file_path = meta.get("file_path", "")
            file_type = meta.get("file_type", "")

            # Only process code and markdown files
            if file_type not in ("code", "markdown") or not file_path:
                continue

            # Get chunks for this document
            chunks = chunk_dao.get_document_chunks(
                DocumentChunkEntity(doc_id=doc.doc_id),
                page=1,
                page_size=10000,
            )

            # Reconstruct file content from chunks
            content_parts = []
            for chunk in sorted(chunks, key=lambda c: c.id if hasattr(c, 'id') else 0):
                if chunk.chunk_type == "summary":
                    continue
                content_parts.append(chunk.content or "")

            full_content = "\n".join(content_parts)
            if full_content.strip():
                files_by_path[file_path] = full_content

        if not files_by_path:
            logger.warning(f"No code files found for knowledge_id={knowledge_id}")
            return None

        # Build graph from reconstructed files
        files_list = [
            {"path": path, "content": content}
            for path, content in files_by_path.items()
        ]

        from dbgpt_ext.rag.graph_builder.repo_graph_builder import RepoGraphBuilder

        builder = RepoGraphBuilder()
        graph = await builder.build_from_files(
            files=files_list,
            repo_name=knowledge_id,
        )

        if graph and graph.vertex_count > 0:
            _save_graph(knowledge_id, graph, build_source="chunk_reconstruction")
            return {
                "vertices": graph.vertex_count,
                "edges": graph.edge_count,
                "files_processed": len(files_list),
                "status": "completed",
            }
        else:
            logger.warning(f"Graph building produced empty graph for {knowledge_id}")
            return None

    except Exception as e:
        logger.error(f"Failed to build code graph from chunks: {e}")
        return None


async def build_code_graph_from_files(
    knowledge_id: str,
    files: List[Dict],
    repo_url: str = "",
    repo_name: str = "",
) -> Optional[Dict]:
    """Build a code graph from a list of file dicts.

    Args:
        knowledge_id: Knowledge space ID.
        files: List of dicts with 'path' and 'content' keys.
        repo_url: Repository URL.
        repo_name: Repository name.

    Returns:
        Dict with graph stats, or None if building fails.
    """
    try:
        from ..tools.codegraph_tools import _save_graph
        from dbgpt_ext.rag.graph_builder.repo_graph_builder import RepoGraphBuilder

        builder = RepoGraphBuilder()
        graph = await builder.build_from_files(
            files=files,
            repo_url=repo_url,
            repo_name=repo_name or knowledge_id,
        )

        if graph and graph.vertex_count > 0:
            _save_graph(knowledge_id, graph, build_source="files")
            return {
                "vertices": graph.vertex_count,
                "edges": graph.edge_count,
                "files_processed": len(files),
                "status": "completed",
            }
        else:
            logger.warning(
                f"Graph building produced empty graph for {knowledge_id}"
            )
            return None

    except Exception as e:
        logger.error(f"Failed to build code graph from files: {e}")
        return None