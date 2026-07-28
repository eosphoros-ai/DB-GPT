"""Git Repository Sync Service - Server-side clone mode.

Handles cloning a git repository, scanning files, indexing them
through the DomainIndex ETL pipeline, and supporting incremental sync.

Sync operations run asynchronously in the background via asyncio.create_task,
returning immediately so the HTTP request does not block. Clients poll
GET /{space_id}/git/sync-status for progress.

Adapted to DB-GPT's data model:
- KnowledgeSpaceEntity: id, name, vector_type, domain_type
- KnowledgeDocumentEntity: id, doc_name, doc_type, space (name), content, meta_info
- DocumentChunkEntity: id, document_id, content, meta_info
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

from dbgpt.rag.knowledge.base import KnowledgeType

from ..domain.factory import DomainKnowledgeIndexFactory

logger = logging.getLogger(__name__)


class GitRepoSyncService:
    """Service for syncing git repository content into a knowledge space.

    Supports:
    - Full sync: clone repo → scan files → index all
    - Incremental sync: git diff → index only changed files
    - File filtering: include/exclude dirs, skip patterns
    - Content hash deduplication
    - Async background execution with status polling
    """

    def __init__(self, service):
        """Initialize with reference to the RAG service.

        Args:
            service: The RAG Service instance for document/chunk operations.
        """
        self.service = service

    def _resolve_space(self, knowledge_id: str):
        """Resolve knowledge space by id or name.

        Returns the KnowledgeSpaceEntity or None.
        """
        from ..models.models import KnowledgeSpaceEntity

        # Try by id first if numeric
        if str(knowledge_id).isdigit():
            spaces = self.service._dao.get_knowledge_space(
                KnowledgeSpaceEntity(id=int(knowledge_id))
            )
            if spaces:
                return spaces[0]
        # Try by name
        spaces = self.service._dao.get_knowledge_space(
            KnowledgeSpaceEntity(name=str(knowledge_id))
        )
        return spaces[0] if spaces else None

    def _build_git_knowledge(
        self,
        knowledge_id: str,
        repo_url: str,
        branch: str = "main",
        exclude_dirs: Optional[List[str]] = None,
        exclude_extensions: Optional[List[str]] = None,
        include_dirs: Optional[List[str]] = None,
        metadata: Optional[Dict] = None,
    ):
        """Build a GitRepoKnowledge instance."""
        from dbgpt_ext.rag.knowledge.git_repo import GitRepoKnowledge

        return GitRepoKnowledge(
            repo_url=repo_url,
            branch=branch,
            extra_skip_dirs=set(exclude_dirs) if exclude_dirs else None,
            extra_skip_extensions=set(exclude_extensions)
            if exclude_extensions
            else None,
            include_dirs=set(include_dirs) if include_dirs else None,
            metadata=metadata or {"knowledge_id": knowledge_id},
        )

    def _get_space_context(self, space) -> Dict:
        """Parse the knowledge space context JSON."""
        return json.loads(space.context) if space.context else {}

    def _set_sync_status(self, space, status: str, error: str = ""):
        """Update the sync_status in the knowledge space context."""
        context = self._get_space_context(space)
        context["sync_status"] = status
        if status == "RUNNING":
            context["sync_started_at"] = datetime.now().isoformat()
            context.pop("sync_error", None)
        elif status in ("FINISHED", "FAILED"):
            context["sync_finished_at"] = datetime.now().isoformat()
            if error:
                context["sync_error"] = error
            else:
                context.pop("sync_error", None)
        space.context = json.dumps(context, ensure_ascii=False)
        space.gmt_modified = datetime.now()
        self.service._dao.update_knowledge_space(space)

    # -------------------------------------------------------------------------
    # Public API — sync_repo (returns immediately, runs in background)
    # -------------------------------------------------------------------------

    async def sync_repo(
        self,
        knowledge_id: str,
        repo_url: str,
        branch: str = "main",
        exclude_dirs: Optional[List[str]] = None,
        exclude_extensions: Optional[List[str]] = None,
        include_dirs: Optional[List[str]] = None,
        build_graph: bool = False,
    ) -> Dict:
        """Start a full sync in the background.

        Validates the space, checks for concurrent syncs, then launches
        the actual sync as an asyncio background task.

        Returns:
            Dict with status="RUNNING" and message.
        """
        space = self._resolve_space(knowledge_id)
        if space is None:
            raise ValueError(f"Knowledge space {knowledge_id} not found")

        # Guard against concurrent syncs
        context = self._get_space_context(space)
        if context.get("sync_status") == "RUNNING":
            raise ValueError(
                f"Sync already in progress for {knowledge_id}. "
                f"Started at {context.get('sync_started_at', 'unknown')}"
            )

        # Mark as running
        self._set_sync_status(space, "RUNNING")

        # Re-resolve space after update (context changed)
        space = self._resolve_space(knowledge_id)

        # Launch background task
        asyncio.create_task(
            self._async_sync_repo(
                knowledge_id=knowledge_id,
                space=space,
                repo_url=repo_url,
                branch=branch,
                exclude_dirs=exclude_dirs,
                exclude_extensions=exclude_extensions,
                include_dirs=include_dirs,
                build_graph=build_graph,
            )
        )

        logger.info(f"Sync started in background for {repo_url} branch={branch}")
        return {
            "status": "RUNNING",
            "message": (
                "Sync started. Poll GET /{space_id}/git/sync-status for progress."
            ),
        }

    async def _async_sync_repo(
        self,
        knowledge_id: str,
        space,
        repo_url: str,
        branch: str = "main",
        exclude_dirs: Optional[List[str]] = None,
        exclude_extensions: Optional[List[str]] = None,
        include_dirs: Optional[List[str]] = None,
        build_graph: bool = False,
    ) -> Dict:
        """Background task: clone repo, scan files, index all.

        This is the actual sync logic, running as an asyncio task.
        """
        try:
            git_knowledge = self._build_git_knowledge(
                knowledge_id=knowledge_id,
                repo_url=repo_url,
                branch=branch,
                exclude_dirs=exclude_dirs,
                exclude_extensions=exclude_extensions,
                include_dirs=include_dirs,
            )

            # Clone and load documents
            logger.info(f"Starting full sync for {repo_url} branch={branch}")
            try:
                documents = git_knowledge.load()
            except Exception as e:
                logger.error(f"Failed to clone/load repo: {e}")
                raise

            head_commit = git_knowledge._head_commit
            md_count = sum(
                1 for d in documents if d.metadata.get("file_type") == "markdown"
            )
            code_count = sum(
                1 for d in documents if d.metadata.get("file_type") == "code"
            )
            logger.info(
                f"Loaded {len(documents)} files ({md_count} md, {code_count} code) "
                f"from {repo_url}, HEAD={head_commit}"
            )

            # Index documents through DomainIndex pipeline
            storage_connector = self.service.storage_manager.get_storage_connector(
                space.name, space.vector_type
            )
            domain_type_raw = (space.domain_type or "git_repo").lower()
            domain_type_norm = (
                "git_repo" if domain_type_raw == "gitrepo" else domain_type_raw
            )
            domain_index = DomainKnowledgeIndexFactory.create(domain_type_norm)

            from dbgpt_ext.rag import ChunkParameters

            chunk_parameter = ChunkParameters(chunk_strategy="CHUNK_BY_MARKDOWN_HEADER")

            stats = {
                "total_files": len(documents),
                "indexed": 0,
                "skipped": 0,
                "failed": 0,
            }

            for doc in documents:
                try:
                    file_path = doc.metadata.get("file_path", "")
                    doc_name = doc.metadata.get("doc_name", "")
                    content_hash = doc.metadata.get("content_hash", "")

                    # Check for existing document with same content hash
                    existing = self._find_document_by_file_path(space.name, file_path)
                    if existing and self._get_doc_hash(existing) == content_hash:
                        stats["skipped"] += 1
                        continue

                    # Delete old version if exists
                    if existing:
                        self.service.delete_document(str(existing.id))

                    # Create document entity
                    from ..models.document_db import KnowledgeDocumentEntity

                    doc_entity = KnowledgeDocumentEntity(
                        doc_name=doc_name or file_path,
                        doc_type=KnowledgeType.GIT_REPO.name,
                        space=space.name,
                        content=repo_url,
                        status="RUNNING",
                        summary=json.dumps(doc.metadata, ensure_ascii=False),
                        gmt_created=datetime.now(),
                        gmt_modified=datetime.now(),
                    )
                    doc_id = self.service._document_dao.create_knowledge_document(
                        doc_entity
                    )

                    # Index through DomainIndex
                    from dbgpt_ext.rag.knowledge.git_repo import (
                        GitRepoKnowledge as GK,
                    )

                    single_knowledge = GK(
                        repo_url=repo_url, branch=branch, metadata=doc.metadata
                    )
                    single_knowledge._load = lambda d=doc: [d]

                    chunks = await domain_index.extract(
                        single_knowledge, chunk_parameter
                    )
                    chunks = await domain_index.transform(chunks)
                    await domain_index.load(
                        chunks,
                        vector_store=storage_connector,
                        max_chunks_once_load=self.service.config.max_chunks_once_load,
                        max_threads=self.service.config.max_threads,
                    )

                    # Save chunk details
                    from ..models.chunk_db import DocumentChunkEntity

                    chunk_entities = [
                        DocumentChunkEntity(
                            doc_name=doc_name or file_path,
                            doc_type=KnowledgeType.GIT_REPO.name,
                            document_id=doc_id,
                            content=chunk.content,
                            meta_info=json.dumps(chunk.metadata, ensure_ascii=False),
                            gmt_created=datetime.now(),
                            gmt_modified=datetime.now(),
                        )
                        for chunk in chunks
                    ]
                    self.service._chunk_dao.create_documents_chunks(chunk_entities)

                    # Update document status
                    doc_entity.id = doc_id
                    doc_entity.status = "FINISHED"
                    doc_entity.chunk_size = len(chunks)
                    doc_entity.result = "success"
                    self.service._document_dao.update_knowledge_document(doc_entity)

                    stats["indexed"] += 1
                except Exception as e:
                    logger.error(
                        f"Failed to index document "
                        f"{doc.metadata.get('file_path', '')}: {e}"
                    )
                    stats["failed"] += 1
                    # Fix: update document status to FAILED
                    try:
                        from ..models.document_db import KnowledgeDocumentEntity

                        failed_doc = KnowledgeDocumentEntity(
                            doc_name=doc.metadata.get("doc_name", ""),
                            doc_type=KnowledgeType.GIT_REPO.name,
                            space=space.name,
                            content=repo_url,
                            status="FAILED",
                            result=f"Error: {str(e)[:200]}",
                            gmt_created=datetime.now(),
                            gmt_modified=datetime.now(),
                        )
                        self.service._document_dao.create_knowledge_document(failed_doc)
                    except Exception:
                        pass

            # Build code graph if requested
            if build_graph and stats["indexed"] > 0:
                try:
                    await self._build_code_graph(
                        knowledge_id, documents, repo_url, space.name, branch=branch
                    )
                except Exception as e:
                    logger.warning(f"Code graph build failed: {e}")

            # Update space context with sync info
            self._update_space_context(space, repo_url, branch, head_commit, "full")

            # Mark sync as finished
            self._set_sync_status(space, "FINISHED")

            logger.info(f"Full sync completed: {stats}")
            return {"status": "completed", "head_commit": head_commit, **stats}

        except Exception as e:
            # Mark sync as failed
            logger.error(f"Full sync failed: {e}")
            try:
                # Re-resolve space (may have stale reference)
                space = self._resolve_space(knowledge_id)
                if space:
                    self._set_sync_status(space, "FAILED", error=str(e))
            except Exception:
                logger.error(f"Failed to update sync status to FAILED: {e}")
            return {"status": "failed", "error": str(e)}

    async def _build_code_graph(
        self, knowledge_id, documents, repo_url, space_name, branch="main"
    ):
        """Build code graph from indexed documents."""
        try:
            from ..service.codegraph_build_service import build_code_graph_from_files

            files = []
            for doc in documents:
                file_type = doc.metadata.get("file_type", "")
                if file_type not in ("code", "markdown"):
                    continue
                files.append(
                    {
                        "path": doc.metadata.get("file_path", ""),
                        "content": doc.content,
                    }
                )
            if files:
                result = await build_code_graph_from_files(
                    knowledge_id=str(knowledge_id),
                    files=files,
                    repo_url=repo_url,
                    repo_name=space_name,
                    branch=branch,
                )
                if result:
                    logger.info(f"Code graph built: {result}")
        except Exception as e:
            logger.warning(f"Code graph build failed: {e}")

    # -------------------------------------------------------------------------
    # Public API — incremental_sync (returns immediately, runs in background)
    # -------------------------------------------------------------------------

    async def incremental_sync(
        self,
        knowledge_id: str,
        repo_url: str,
        branch: str = "main",
        last_commit: Optional[str] = None,
    ) -> Dict:
        """Start an incremental sync in the background.

        Returns:
            Dict with status="RUNNING" and message.
        """
        space = self._resolve_space(knowledge_id)
        if space is None:
            raise ValueError(f"Knowledge space {knowledge_id} not found")

        # Guard against concurrent syncs
        context = self._get_space_context(space)
        if context.get("sync_status") == "RUNNING":
            raise ValueError(
                f"Sync already in progress for {knowledge_id}. "
                f"Started at {context.get('sync_started_at', 'unknown')}"
            )

        # If no last_commit, fall back to full sync
        if not last_commit:
            last_commit = context.get("last_sync_commit")
        if not last_commit:
            logger.info("No last_commit found, falling back to full sync")
            return await self.sync_repo(
                knowledge_id=knowledge_id, repo_url=repo_url, branch=branch
            )

        # Mark as running
        self._set_sync_status(space, "RUNNING")

        # Re-resolve space after update
        space = self._resolve_space(knowledge_id)

        # Launch background task
        asyncio.create_task(
            self._async_incremental_sync(
                knowledge_id=knowledge_id,
                space=space,
                repo_url=repo_url,
                branch=branch,
                last_commit=last_commit,
            )
        )

        logger.info(
            f"Incremental sync started in background for {repo_url} "
            f"from {last_commit[:8]} to HEAD"
        )
        return {
            "status": "RUNNING",
            "message": (
                "Incremental sync started. Poll GET /{space_id}/git/sync-status "
                "for progress."
            ),
        }

    async def _async_incremental_sync(
        self,
        knowledge_id: str,
        space,
        repo_url: str,
        branch: str = "main",
        last_commit: Optional[str] = None,
    ) -> Dict:
        """Background task: incremental sync."""
        try:
            git_knowledge = self._build_git_knowledge(
                knowledge_id=knowledge_id, repo_url=repo_url, branch=branch
            )
            logger.info(
                f"Starting incremental sync for {repo_url} "
                f"from {last_commit[:8]} to HEAD"
            )
            try:
                diff_result = git_knowledge.load_incremental(last_commit)
            except Exception as e:
                logger.error(f"Incremental sync failed, falling back to full sync: {e}")
                # Reset status before full sync
                self._set_sync_status(space, "FINISHED")
                return await self._async_sync_repo(
                    knowledge_id=knowledge_id,
                    space=space,
                    repo_url=repo_url,
                    branch=branch,
                )

            if diff_result is None:
                self._set_sync_status(space, "FINISHED")
                return await self._async_sync_repo(
                    knowledge_id=knowledge_id,
                    space=space,
                    repo_url=repo_url,
                    branch=branch,
                )

            head_commit = diff_result["head_commit"]
            added = diff_result["added"]
            modified = diff_result["modified"]
            deleted = diff_result["deleted"]

            logger.info(
                f"Incremental diff: {len(added)} added, "
                f"{len(modified)} modified, {len(deleted)} deleted"
            )

            storage_connector = self.service.storage_manager.get_storage_connector(
                space.name, space.vector_type
            )

            # Delete removed files
            deleted_count = 0
            for file_path in deleted:
                doc_entity = self._find_document_by_file_path(space.name, file_path)
                if doc_entity:
                    self.service.delete_document(str(doc_entity.id))
                    deleted_count += 1

            # Index added and modified files
            domain_type_raw = (space.domain_type or "git_repo").lower()
            domain_type_norm = (
                "git_repo" if domain_type_raw == "gitrepo" else domain_type_raw
            )
            domain_index = DomainKnowledgeIndexFactory.create(domain_type_norm)
            from dbgpt_ext.rag import ChunkParameters

            chunk_parameter = ChunkParameters(chunk_strategy="CHUNK_BY_MARKDOWN_HEADER")
            indexed_count = 0

            for doc in added + modified:
                try:
                    file_path = doc.metadata.get("file_path", "")
                    existing = self._find_document_by_file_path(space.name, file_path)
                    if existing:
                        self.service.delete_document(str(existing.id))

                    from ..models.document_db import KnowledgeDocumentEntity

                    doc_entity = KnowledgeDocumentEntity(
                        doc_name=doc.metadata.get("doc_name", file_path),
                        doc_type=KnowledgeType.GIT_REPO.name,
                        space=space.name,
                        content=repo_url,
                        status="RUNNING",
                        summary=json.dumps(doc.metadata, ensure_ascii=False),
                        gmt_created=datetime.now(),
                        gmt_modified=datetime.now(),
                    )
                    doc_id = self.service._document_dao.create_knowledge_document(
                        doc_entity
                    )

                    from dbgpt_ext.rag.knowledge.git_repo import (
                        GitRepoKnowledge as GK,
                    )

                    single_knowledge = GK(
                        repo_url=repo_url, branch=branch, metadata=doc.metadata
                    )
                    single_knowledge._load = lambda d=doc: [d]

                    chunks = await domain_index.extract(
                        single_knowledge, chunk_parameter
                    )
                    chunks = await domain_index.transform(chunks)
                    await domain_index.load(
                        chunks,
                        vector_store=storage_connector,
                        max_chunks_once_load=self.service.config.max_chunks_once_load,
                        max_threads=self.service.config.max_threads,
                    )

                    from ..models.chunk_db import DocumentChunkEntity

                    chunk_entities = [
                        DocumentChunkEntity(
                            doc_name=doc.metadata.get("doc_name", file_path),
                            doc_type=KnowledgeType.GIT_REPO.name,
                            document_id=doc_id,
                            content=chunk.content,
                            meta_info=json.dumps(chunk.metadata, ensure_ascii=False),
                            gmt_created=datetime.now(),
                            gmt_modified=datetime.now(),
                        )
                        for chunk in chunks
                    ]
                    self.service._chunk_dao.create_documents_chunks(chunk_entities)

                    doc_entity.id = doc_id
                    doc_entity.status = "FINISHED"
                    doc_entity.chunk_size = len(chunks)
                    doc_entity.result = "success"
                    self.service._document_dao.update_knowledge_document(doc_entity)
                    indexed_count += 1
                except Exception as e:
                    logger.error(
                        f"Failed to index document "
                        f"{doc.metadata.get('file_path', '')}: {e}"
                    )

            self._update_space_context(
                space, repo_url, branch, head_commit, "incremental"
            )

            # Mark sync as finished
            self._set_sync_status(space, "FINISHED")

            return {
                "status": "completed",
                "head_commit": head_commit,
                "added": len(added),
                "modified": len(modified),
                "deleted": deleted_count,
                "indexed": indexed_count,
            }

        except Exception as e:
            logger.error(f"Incremental sync failed: {e}")
            try:
                space = self._resolve_space(knowledge_id)
                if space:
                    self._set_sync_status(space, "FAILED", error=str(e))
            except Exception:
                logger.error(f"Failed to update sync status to FAILED: {e}")
            return {"status": "failed", "error": str(e)}

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _find_document_by_file_path(self, space_name: str, file_path: str):
        """Find a document by its file_path in meta_info."""
        from ..models.document_db import KnowledgeDocumentEntity

        docs = self.service._document_dao.get_knowledge_documents(
            KnowledgeDocumentEntity(
                space=space_name, doc_type=KnowledgeType.GIT_REPO.name
            ),
            page=1,
            page_size=10000,
        )
        if not docs:
            return None
        for doc in docs:
            try:
                meta = (
                    json.loads(doc.summary)
                    if doc.summary and doc.summary.startswith("{")
                    else {}
                )
            except (json.JSONDecodeError, TypeError):
                meta = {}
            if meta.get("file_path") == file_path:
                return doc
        return None

    def _get_doc_hash(self, doc) -> str:
        """Get content_hash from document meta_info."""
        try:
            meta = (
                json.loads(doc.summary)
                if doc.summary and doc.summary.startswith("{")
                else {}
            )
        except (json.JSONDecodeError, TypeError):
            meta = {}
        return meta.get("content_hash", "")

    def _update_space_context(self, space, repo_url, branch, head_commit, sync_mode):
        """Update knowledge space context with sync information."""
        context = self._get_space_context(space)
        context["git_repo_url"] = repo_url
        context["git_branch"] = branch
        if head_commit:
            context["last_sync_commit"] = head_commit
            context["last_sync_time"] = datetime.now().isoformat()
        context["last_sync_mode"] = sync_mode
        space.context = json.dumps(context, ensure_ascii=False)
        space.gmt_modified = datetime.now()
        self.service._dao.update_knowledge_space(space)

    def get_index_status(self, knowledge_id: str) -> Dict:
        """Get the indexing status for a git repo knowledge space."""
        from ..models.document_db import KnowledgeDocumentEntity

        space = self._resolve_space(knowledge_id)
        if space is None:
            return {"status": "NOT_FOUND", "total_files": 0}

        docs = self.service._document_dao.get_knowledge_documents(
            KnowledgeDocumentEntity(
                space=space.name, doc_type=KnowledgeType.GIT_REPO.name
            ),
            page=1,
            page_size=100000,
        )
        status_counts = {"finished": 0, "running": 0, "failed": 0, "todo": 0}
        for doc in docs or []:
            status = (doc.status or "").upper()
            if status == "FINISHED":
                status_counts["finished"] += 1
            elif status == "RUNNING":
                status_counts["running"] += 1
            elif status == "FAILED":
                status_counts["failed"] += 1
            else:
                status_counts["todo"] += 1

        context = self._get_space_context(space)
        sync_status = context.get("sync_status", "")

        # Determine display status: space-level sync_status takes priority
        if sync_status == "RUNNING":
            display_status = "RUNNING"
        elif sync_status == "FAILED":
            display_status = "FAILED"
        elif status_counts["running"] > 0:
            display_status = "RUNNING"
        elif status_counts["failed"] > 0 and status_counts["finished"] == 0:
            display_status = "FAILED"
        elif docs:
            display_status = "FINISHED"
        else:
            display_status = "PENDING"

        return {
            "status": display_status,
            "total_files": len(docs or []),
            **status_counts,
            "last_sync_commit": context.get("last_sync_commit"),
            "last_sync_time": context.get("last_sync_time"),
            "last_sync_mode": context.get("last_sync_mode"),
            "repo_url": context.get("git_repo_url"),
            "branch": context.get("git_branch"),
            "sync_started_at": context.get("sync_started_at"),
            "sync_error": context.get("sync_error"),
        }
