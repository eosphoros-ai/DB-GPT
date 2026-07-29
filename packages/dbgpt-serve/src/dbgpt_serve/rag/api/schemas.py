import re
from typing import List, Optional, Union
from urllib.parse import urlparse

from fastapi import File, UploadFile

from dbgpt._private.pydantic import BaseModel, ConfigDict, Field, field_validator
from dbgpt_ext.rag.chunk_manager import ChunkParameters

from ..config import SERVE_APP_NAME_HUMP

# Allowed git URL schemes. ``ext::`` (and similar command-execution
# transports) MUST be rejected to prevent git from spawning an arbitrary shell
# command via its external-transport helper — see git-remote-ext(1). This is an
# RCE vector independent of how the parent process invokes ``git clone``.
_ALLOWED_GIT_SCHEMES = frozenset({"http", "https", "ssh", "git", "file"})
# SCP-style git URLs ("git@host:path" or bare "host:path") have no "://" so
# urlparse can't see a scheme — match them explicitly so private repos that use
# this shorthand keep working. ``ext::`` is NOT matched here: any "::" before a
# "://" is rejected up-front by the colon_colon guard above, so by the time we
# reach this regex a "::" payload is already gone. The regex only needs the
# single-colon "host:path" form.
_GIT_SCP_PATTERN = re.compile(r"^(?:[A-Za-z0-9._+-]+@)?[A-Za-z0-9._+-]+:[^/\s][^\s]*$")


def _validate_git_repo_url(url: str) -> str:
    """Validate a git repository URL, rejecting command-execution transports.

    Only http/https/ssh/git/file schemes and SCP-style ``git@host:path`` URLs
    are accepted. ``ext::`` / ``fd::`` / ``transport::`` and any other git
    transport that can spawn a shell are rejected before reaching ``git clone``.
    """
    if not isinstance(url, str) or not url.strip():
        raise ValueError("repo_url must be a non-empty string")
    url = url.strip()
    # Block anything with a ``::`` *before* the first ``://`` — that's the
    # signature of an ext-like transport prefix (e.g. ``ext::sh -c ...``).
    scheme_sep = url.find("://")
    colon_colon = url.find("::")
    if colon_colon != -1 and (scheme_sep == -1 or colon_colon < scheme_sep):
        raise ValueError(
            f"Unsupported git transport in repo_url: '{url}'. "
            "Only http/https/ssh/git/file and git@host:path URLs are allowed."
        )
    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()
    if scheme in _ALLOWED_GIT_SCHEMES:
        return url
    # No "://" means it's not a scheme://authority URL — urlparse then greedily
    # treats the leading "word:" as a scheme (e.g. "host:path"). Recognise the
    # SCP-style "[user@]host:path" form explicitly so such shorthands keep
    # working. Single-colon only ("ext::" was already rejected by the guard
    # above because it contains "::").
    if scheme_sep == -1 and _GIT_SCP_PATTERN.match(url):
        return url
    raise ValueError(
        f"Unsupported git repo_url scheme: '{scheme or 'none'}'. "
        "Allowed: http, https, ssh, git, file, git@host:path."
    )


class SpaceServeRequest(BaseModel):
    """name: knowledge space name"""

    """vector_type: vector type"""
    id: Optional[int] = Field(None, description="The space id")
    name: str = Field(None, description="The space name")
    """vector_type: vector type"""
    vector_type: str = Field(None, description="The vector type")
    """domain_type: domain type"""
    domain_type: str = Field(None, description="The domain type")
    """desc: description"""
    desc: Optional[str] = Field(None, description="The description")
    """owner: owner"""
    owner: Optional[str] = Field(None, description="The owner")
    """context: argument context"""
    context: Optional[str] = Field(None, description="The context")
    """gmt_created: created time"""
    gmt_created: Optional[str] = Field(None, description="The created time")
    """gmt_modified: modified time"""
    gmt_modified: Optional[str] = Field(None, description="The modified time")


class DocumentServeRequest(BaseModel):
    id: Optional[int] = Field(None, description="The doc id")
    doc_name: Optional[str] = Field(None, description="doc name")
    """doc_type: document type"""
    doc_type: Optional[str] = Field(None, description="The doc type")
    """content: description"""
    content: Optional[str] = Field(None, description="content")
    """doc file"""
    doc_file: Union[UploadFile, str] = File(None)
    """space id: space id"""
    space_id: Optional[str] = Field(None, description="space id")
    """space name: space name"""
    space_name: Optional[str] = Field(None, description="space name")
    """questions: questions"""
    questions: Optional[List[str]] = Field(None, description="questions")


class DocumentServeResponse(BaseModel):
    id: Optional[int] = Field(None, description="The doc id")
    doc_name: Optional[str] = Field(None, description="doc type")
    """vector_type: vector type"""
    doc_type: Optional[str] = Field(None, description="The doc content")
    """desc: description"""
    content: Optional[str] = Field(None, description="content")
    """vector ids"""
    vector_ids: Optional[str] = Field(None, description="vector ids")
    """space: space name"""
    space: Optional[str] = Field(None, description="space name")
    """status: status"""
    status: Optional[str] = Field(None, description="status")
    """last_sync: last sync time"""
    last_sync: Optional[str] = Field(None, description="last sync time")
    """result: result"""
    result: Optional[str] = Field(None, description="result")
    """summary: summary"""
    summary: Optional[str] = Field(None, description="summary")
    """gmt_created: created time"""
    gmt_created: Optional[str] = Field(None, description="created time")
    """gmt_modified: modified time"""
    gmt_modified: Optional[str] = Field(None, description="modified time")
    """chunk_size: chunk size"""
    chunk_size: Optional[int] = Field(None, description="chunk size")
    """questions: questions"""
    questions: Optional[str] = Field(None, description="questions")


class ChunkServeRequest(BaseModel):
    id: Optional[int] = Field(None, description="The primary id")
    document_id: Optional[int] = Field(None, description="document id")
    doc_name: Optional[str] = Field(None, description="document name")
    doc_type: Optional[str] = Field(None, description="document type")
    content: Optional[str] = Field(None, description="chunk content")
    meta_info: Optional[str] = Field(None, description="chunk meta info")
    questions: Optional[List[str]] = Field(None, description="chunk questions")
    gmt_created: Optional[str] = Field(None, description="chunk create time")
    gmt_modified: Optional[str] = Field(None, description="chunk modify time")


class ChunkServeResponse(BaseModel):
    id: Optional[int] = Field(None, description="The primary id")
    document_id: Optional[int] = Field(None, description="document id")
    doc_name: Optional[str] = Field(None, description="document name")
    doc_type: Optional[str] = Field(None, description="document type")
    content: Optional[str] = Field(None, description="chunk content")
    meta_info: Optional[str] = Field(None, description="chunk meta info")
    questions: Optional[str] = Field(None, description="chunk questions")
    gmt_created: Optional[str] = Field(None, description="chunk create time")
    gmt_modified: Optional[str] = Field(None, description="chunk modify time")


class KnowledgeSyncRequest(BaseModel):
    """Sync request"""

    """doc_ids: doc ids"""
    doc_id: Optional[int] = Field(None, description="The doc id")

    """space id"""
    space_id: Optional[str] = Field(None, description="space id")

    """model_name: model name"""
    model_name: Optional[str] = Field(None, description="model name")

    """chunk_parameters: chunk parameters 
    """
    chunk_parameters: Optional[ChunkParameters] = Field(
        None, description="chunk parameters"
    )


class KnowledgeRetrieveRequest(BaseModel):
    """Retrieve request"""

    """space id"""
    space_id: int = Field(None, description="space id")

    """query: query"""
    query: str = Field(None, description="query")

    """top_k: top k"""
    top_k: Optional[int] = Field(5, description="top k")

    """score_threshold: score threshold
    """
    score_threshold: Optional[float] = Field(0.0, description="score threshold")


# 复用这里代码


class SpaceServeResponse(BaseModel):
    """Flow response model"""

    model_config = ConfigDict(title=f"ServeResponse for {SERVE_APP_NAME_HUMP}")

    """name: knowledge space name"""

    """vector_type: vector type"""
    id: Optional[int] = Field(None, description="The space id")
    name: Optional[str] = Field(None, description="The space name")
    """vector_type: vector type"""
    vector_type: Optional[str] = Field(None, description="The vector type")
    """desc: description"""
    desc: Optional[str] = Field(None, description="The description")
    """context: argument context"""
    context: Optional[str] = Field(None, description="The context")
    """owner: owner"""
    owner: Optional[str] = Field(None, description="The owner")
    """user_id: user_id"""
    user_id: Optional[str] = Field(None, description="user id")
    """user_id: user_ids"""
    user_ids: Optional[str] = Field(None, description="user ids")
    """sys code"""
    sys_code: Optional[str] = Field(None, description="The sys code")
    """domain type"""
    domain_type: Optional[str] = Field(None, description="domain_type")


class DocumentChunkVO(BaseModel):
    id: int = Field(..., description="document chunk id")
    document_id: int = Field(..., description="document id")
    doc_name: str = Field(..., description="document name")
    doc_type: str = Field(..., description="document type")
    content: str = Field(..., description="document content")
    meta_info: str = Field(..., description="document meta info")
    gmt_created: str = Field(..., description="document create time")
    gmt_modified: str = Field(..., description="document modify time")


class DocumentVO(BaseModel):
    """Document Entity."""

    id: int = Field(..., description="document id")
    doc_name: str = Field(..., description="document name")
    doc_type: str = Field(..., description="document type")
    space: str = Field(..., description="document space name")
    chunk_size: int = Field(..., description="document chunk size")
    status: str = Field(..., description="document status")
    last_sync: str = Field(..., description="document last sync time")
    content: str = Field(..., description="document content")
    result: Optional[str] = Field(None, description="document result")
    vector_ids: Optional[str] = Field(None, description="document vector ids")
    summary: Optional[str] = Field(None, description="document summary")
    gmt_created: str = Field(..., description="document create time")
    gmt_modified: str = Field(..., description="document modify time")


class KnowledgeDomainType(BaseModel):
    """Knowledge domain type"""

    name: str = Field(..., description="The domain type name")
    desc: str = Field(..., description="The domain type description")


class KnowledgeStorageType(BaseModel):
    """Knowledge storage type"""

    name: str = Field(..., description="The storage type name")
    desc: str = Field(..., description="The storage type description")
    domain_types: List[KnowledgeDomainType] = Field(..., description="The domain types")


class KnowledgeConfigResponse(BaseModel):
    """Knowledge config response"""

    storage: List[KnowledgeStorageType] = Field(..., description="The storage types")


class GitRepoSyncRequest(BaseModel):
    """Request for syncing a git repository into a knowledge space."""

    model_config = ConfigDict(protected_namespaces=())

    repo_url: str = Field(..., description="Git repository URL")
    branch: str = Field("main", description="Branch to clone")
    exclude_dirs: List[str] = Field(
        default_factory=list, description="Directories to exclude from indexing"
    )
    exclude_extensions: List[str] = Field(
        default_factory=list, description="File extensions to exclude"
    )
    include_dirs: List[str] = Field(
        default_factory=list, description="Only include these top-level directories"
    )
    build_graph: bool = Field(
        False, description="Whether to build code knowledge graph"
    )
    chunk_strategy: str = Field(
        "CHUNK_BY_MARKDOWN_HEADER", description="Chunk strategy for splitting"
    )

    @field_validator("repo_url")
    @classmethod
    def _validate_repo_url(cls, v: str) -> str:
        """Reject git transports that can spawn a shell (e.g. ext::) — RCE guard."""
        return _validate_git_repo_url(v)


class GitRepoSyncStatusResponse(BaseModel):
    """Response for git repo sync status."""

    status: str = Field(
        ..., description="Overall status: RUNNING/FINISHED/FAILED/PENDING"
    )
    total_files: int = Field(0, description="Total number of files")
    finished: int = Field(0, description="Number of finished files")
    running: int = Field(0, description="Number of running files")
    failed: int = Field(0, description="Number of failed files")
    todo: int = Field(0, description="Number of todo files")
    last_sync_commit: Optional[str] = Field(None, description="Last synced commit SHA")
    last_sync_time: Optional[str] = Field(None, description="Last sync time")
    last_sync_mode: Optional[str] = Field(
        None, description="Last sync mode: full/incremental"
    )
    repo_url: Optional[str] = Field(None, description="Git repository URL")
    branch: Optional[str] = Field(None, description="Git branch")
    sync_started_at: Optional[str] = Field(
        None, description="Time when current sync started"
    )
    sync_error: Optional[str] = Field(None, description="Error message if sync failed")


class GitRepoIncrementalSyncRequest(BaseModel):
    """Request for incremental sync of a git repository."""

    model_config = ConfigDict(protected_namespaces=())

    repo_url: str = Field(..., description="Git repository URL")
    branch: str = Field("main", description="Branch to sync")
    last_commit: Optional[str] = Field(
        None, description="Last synced commit SHA (auto-detected if not provided)"
    )

    @field_validator("repo_url")
    @classmethod
    def _validate_repo_url(cls, v: str) -> str:
        """Reject git transports that can spawn a shell (e.g. ext::) — RCE guard."""
        return _validate_git_repo_url(v)


class KbSearchRequest(BaseModel):
    """Request for knowledge base search tools."""

    knowledge_id: str = Field(
        "", description="Knowledge space ID (optional, uses path param)"
    )
    query: str = Field("", description="Search query or pattern")
    path: str = Field("", description="Directory or file path filter")
    file_pattern: str = Field("", description="File pattern filter (e.g., '*.py')")
    start_line: int = Field(1, description="Start line number for kb_cat")
    end_line: int = Field(0, description="End line number for kb_cat (0 = to end)")
    offset: int = Field(0, description="Pagination offset")
    limit: int = Field(20, description="Maximum number of results")
    top_k: int = Field(5, description="Number of results for semantic search")
    score_threshold: float = Field(0.0, description="Minimum score for semantic search")


class KnowledgeSpaceStatsResponse(BaseModel):
    """Aggregate statistics for a knowledge space."""

    # Space info
    name: str = Field(..., description="Space name")
    domain_type: Optional[str] = Field(
        None, description="Domain type (Normal, GitRepo, etc.)"
    )
    vector_type: Optional[str] = Field(None, description="Vector type")
    index_methods: Optional[List[str]] = Field(None, description="Index methods")
    desc: Optional[str] = Field(None, description="Description")

    # Document stats
    document_count: int = Field(0, description="Total number of documents")
    chunk_count: int = Field(
        0, description="Total number of chunks (sum of chunk_size)"
    )

    # Sync progress (for GitRepo spaces)
    sync_status: Optional[str] = Field(
        None, description="Sync status: RUNNING/FINISHED/FAILED/PENDING"
    )
    sync_total_files: Optional[int] = Field(None, description="Total files in sync")
    sync_finished: Optional[int] = Field(None, description="Finished files")
    sync_running: Optional[int] = Field(None, description="Running files")
    sync_failed: Optional[int] = Field(None, description="Failed files")
    sync_todo: Optional[int] = Field(None, description="Todo files")
    repo_url: Optional[str] = Field(None, description="Git repo URL")
    branch: Optional[str] = Field(None, description="Git branch")

    # Graph stats
    graph_vertex_count: Optional[int] = Field(
        None, description="Number of graph vertices/nodes"
    )
    graph_edge_count: Optional[int] = Field(None, description="Number of graph edges")
    graph_community_count: Optional[int] = Field(
        None, description="Number of graph communities"
    )
    graph_build_status: Optional[str] = Field(None, description="Graph build status")


class KbFileEntry(BaseModel):
    """A file or directory entry in a knowledge base."""

    name: str = Field(..., description="File or directory name")
    path: str = Field(..., description="Full path")
    is_dir: bool = Field(..., description="Whether this is a directory")
    file_type: Optional[str] = Field(None, description="File type/extension")
    language: Optional[str] = Field(None, description="Programming language")
    doc_id: Optional[int] = Field(None, description="Document ID if it's a file")
    child_count: Optional[int] = Field(
        None, description="Number of children if directory"
    )


class KbLsJsonResponse(BaseModel):
    """Structured directory listing response."""

    path: str = Field("", description="Current directory path")
    entries: List[KbFileEntry] = Field(
        default_factory=list, description="Entries in this directory"
    )
    total_files: int = Field(0, description="Total files in directory")
    total_dirs: int = Field(0, description="Total subdirectories")
