"""CodeGraph Build Service."""

import json
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def _resolve_space_name(knowledge_id: str) -> Optional[str]:
    """Resolve a knowledge space name from an id or name.

    Returns the space name, or None if the space does not exist.
    """
    from ..api.git_repo_endpoints import global_system_app
    from ..config import SERVE_SERVICE_COMPONENT_NAME
    from ..models.models import KnowledgeSpaceEntity
    from ..service.service import Service

    try:
        if global_system_app is None:
            return None
        service = global_system_app.get_component(SERVE_SERVICE_COMPONENT_NAME, Service)
        # Try by id first if numeric
        if str(knowledge_id).isdigit():
            spaces = service._dao.get_knowledge_space(
                KnowledgeSpaceEntity(id=int(knowledge_id))
            )
            if spaces:
                return spaces[0].name
        # Try by name
        spaces = service._dao.get_knowledge_space(
            KnowledgeSpaceEntity(name=str(knowledge_id))
        )
        return spaces[0].name if spaces else None
    except Exception as e:
        logger.warning(f"Failed to resolve space name for {knowledge_id}: {e}")
        return None


def _parse_doc_metadata(doc) -> Dict:
    """Parse the metadata JSON stored in a document's summary field."""
    try:
        meta = (
            json.loads(doc.summary)
            if doc.summary and doc.summary.startswith("{")
            else {}
        )
    except (json.JSONDecodeError, TypeError):
        meta = {}
    return meta


def _is_graphable_document(doc, meta: Dict) -> bool:
    """Check whether a document should be included in graph building.

    Includes:
    - Git repo documents with file_type in (code, markdown)
    - Uploaded DOCUMENT type documents whose doc_name has a graphable extension
      (.md/.markdown for heading hierarchy, or code extensions for AST)
    """
    file_type = meta.get("file_type", "")
    if file_type in ("code", "markdown"):
        return True
    # Uploaded documents: check extension in doc_name
    doc_name = (doc.doc_name or "").lower()
    graphable_exts = (
        ".md",
        ".markdown",
        ".py",
        ".java",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".go",
        ".rs",
        ".c",
        ".h",
        ".cpp",
        ".cc",
        ".cxx",
        ".hpp",
    )
    return any(doc_name.endswith(ext) for ext in graphable_exts)


async def build_code_graph_from_knowledge_space(knowledge_id: str) -> Optional[Dict]:
    """Build a structural graph by reconstructing files from chunks in the DB.

    Works for both GIT_REPO spaces (code structure + markdown headings) and
    DOCUMENT spaces (uploaded markdown/code files). Reconstructs each file's
    content from its chunks and passes them to RepoGraphBuilder.
    """
    try:
        from ..models.chunk_db import DocumentChunkDao, DocumentChunkEntity
        from ..models.document_db import KnowledgeDocumentDao, KnowledgeDocumentEntity
        from ..tools.codegraph_tools import _save_graph

        space_name = _resolve_space_name(knowledge_id)
        if not space_name:
            logger.warning(f"Space not found for knowledge_id={knowledge_id}")
            return None

        doc_dao = KnowledgeDocumentDao()
        docs = doc_dao.get_knowledge_documents(
            KnowledgeDocumentEntity(space=space_name), page=1, page_size=100000
        )
        if not docs:
            return None

        files_by_path = {}
        chunk_dao = DocumentChunkDao()
        for doc in docs:
            meta = _parse_doc_metadata(doc)
            if not _is_graphable_document(doc, meta):
                continue
            # Prefer file_path from metadata (git repo), fall back to doc_name
            file_path = meta.get("file_path", "") or doc.doc_name or ""
            if not file_path:
                continue
            chunks = chunk_dao.get_document_chunks(
                DocumentChunkEntity(document_id=doc.id), page=1, page_size=10000
            )
            content_parts = [c.content or "" for c in chunks]
            full_content = "\n".join(content_parts)
            if full_content.strip():
                files_by_path[file_path] = full_content

        if not files_by_path:
            return None

        files_list = [{"path": p, "content": c} for p, c in files_by_path.items()]
        from dbgpt_ext.rag.graph_builder.repo_graph_builder import RepoGraphBuilder

        builder = RepoGraphBuilder()
        graph = await builder.build_from_files(files=files_list, repo_name=space_name)
        if graph and graph.vertex_count > 0:
            # Persist using the resolved space name as the key, so that the
            # visualize endpoint (which queries by space name) can find it.
            _save_graph(space_name, graph, build_source="chunk_reconstruction")
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

        # Normalize to space name so the visualize endpoint (which queries by
        # space name) can find the persisted graph regardless of whether the
        # caller passed an id or a name.
        graph_key = _resolve_space_name(knowledge_id) or knowledge_id

        builder = RepoGraphBuilder()
        graph = await builder.build_from_files(
            files=files, repo_url=repo_url, repo_name=repo_name or graph_key
        )
        if graph and graph.vertex_count > 0:
            _save_graph(
                graph_key,
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
