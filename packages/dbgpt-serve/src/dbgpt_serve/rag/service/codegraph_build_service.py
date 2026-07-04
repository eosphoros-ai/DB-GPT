"""CodeGraph Build Service."""

import json
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


async def build_code_graph_from_knowledge_space(knowledge_id: str) -> Optional[Dict]:
    """Build code graph by reconstructing files from chunks in the DB."""
    try:
        from ..models.chunk_db import DocumentChunkDao, DocumentChunkEntity
        from ..models.document_db import KnowledgeDocumentDao, KnowledgeDocumentEntity
        from ..tools.codegraph_tools import _save_graph

        doc_dao = KnowledgeDocumentDao()
        docs = doc_dao.get_knowledge_documents(
            KnowledgeDocumentEntity(knowledge_id=knowledge_id), page=1, page_size=100000
        )
        if not docs:
            return None

        files_by_path = {}
        chunk_dao = DocumentChunkDao()
        for doc in docs:
            try:
                meta = json.loads(doc.meta_data) if doc.meta_data else {}
            except (json.JSONDecodeError, TypeError):
                meta = {}
            file_path = meta.get("file_path", "")
            file_type = meta.get("file_type", "")
            if file_type not in ("code", "markdown") or not file_path:
                continue
            chunks = chunk_dao.get_document_chunks(
                DocumentChunkEntity(doc_id=doc.doc_id), page=1, page_size=10000
            )
            content_parts = [
                c.content or "" for c in chunks if c.chunk_type != "summary"
            ]
            full_content = "\n".join(content_parts)
            if full_content.strip():
                files_by_path[file_path] = full_content

        if not files_by_path:
            return None

        files_list = [{"path": p, "content": c} for p, c in files_by_path.items()]
        from dbgpt_ext.rag.graph_builder.repo_graph_builder import RepoGraphBuilder

        builder = RepoGraphBuilder()
        graph = await builder.build_from_files(files=files_list, repo_name=knowledge_id)
        if graph and graph.vertex_count > 0:
            _save_graph(
                knowledge_id, graph, build_source="chunk_reconstruction"
            )
            return {
                "vertices": graph.vertex_count,
                "edges": graph.edge_count,
                "files_processed": len(files_list),
                "status": "completed",
            }
        return None
    except Exception as e:
        logger.error(f"Failed to build code graph from chunks: {e}")
        return None


async def build_code_graph_from_files(
    knowledge_id: str,
    files: List[Dict],
    repo_url: str = "",
    repo_name: str = "",
    branch: str = "",
) -> Optional[Dict]:
    """Build code graph from a list of file dicts.

    Args:
        knowledge_id: Knowledge space ID.
        files: List of dicts with keys: path, content.
        repo_url: Git repository URL.
        repo_name: Repository name.
        branch: Git branch.
    """
    try:
        from dbgpt_ext.rag.graph_builder.repo_graph_builder import RepoGraphBuilder

        from ..tools.codegraph_tools import _save_graph

        builder = RepoGraphBuilder()
        graph = await builder.build_from_files(
            files=files, repo_url=repo_url, repo_name=repo_name or knowledge_id
        )
        if graph and graph.vertex_count > 0:
            _save_graph(
                knowledge_id,
                graph,
                build_source="files",
                repo_url=repo_url,
                branch=branch,
            )
            return {
                "vertices": graph.vertex_count,
                "edges": graph.edge_count,
                "files_processed": len(files),
                "status": "completed",
            }
        return None
    except Exception as e:
        logger.error(f"Failed to build code graph from files: {e}")
        return None
