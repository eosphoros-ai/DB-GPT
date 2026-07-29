"""Git Repository Knowledge - Load files from a git repository.

Supports cloning a repository, scanning supported files (.md + code),
and building Document objects with rich metadata for indexing.
Also supports incremental sync via git diff.
"""

import hashlib
import logging
import os
import re
import shutil
import subprocess
import tempfile
from typing import Any, Dict, List, Optional, Set, Union

from dbgpt.core import Document
from dbgpt.rag.knowledge.base import (
    ChunkStrategy,
    Knowledge,
    KnowledgeType,
)

logger = logging.getLogger(__name__)

# All scannable extensions: .md + all code file extensions
from dbgpt_ext.rag.knowledge.code_file import (  # noqa: E402
    EXTENSION_LANGUAGE_MAP,
)

SCAN_EXTENSIONS = {".md"} | set(EXTENSION_LANGUAGE_MAP.keys())

# Directories to skip during scanning
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

# Files to skip (lock files, generated files)
SKIP_FILES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "go.sum",
    "Cargo.lock",
    "poetry.lock",
    "Pipfile.lock",
    "composer.lock",
    "Gemfile.lock",
}


class GitRepoKnowledge(Knowledge):
    """Load Markdown and code files from a Git repository.

    Supports:
    - Full clone and scan
    - Incremental sync via git diff
    - File filtering (include/exclude dirs, skip patterns)
    - Rich metadata (file_path, file_type, language, content_hash)
    - Optional code graph building
    """

    def __init__(
        self,
        repo_url: Optional[str] = None,
        branch: Optional[str] = "main",
        knowledge_type: KnowledgeType = KnowledgeType.GIT_REPO,
        encoding: Optional[str] = "utf-8",
        loader: Optional[Any] = None,
        metadata: Optional[Dict[str, Union[str, List[str]]]] = None,
        extra_skip_dirs: Optional[Set[str]] = None,
        extra_skip_extensions: Optional[Set[str]] = None,
        include_dirs: Optional[Set[str]] = None,
        **kwargs: Any,
    ) -> None:
        """Create GitRepoKnowledge.

        Args:
            repo_url: Git repository URL to clone.
            branch: Branch to checkout (default: "main").
            knowledge_type: Knowledge type enum value.
            encoding: File encoding (default: "utf-8").
            loader: Optional custom data loader.
            metadata: Additional metadata dict.
            extra_skip_dirs: Additional directories to skip.
            extra_skip_extensions: Additional file extensions to skip.
            include_dirs: If set, only index files under these top-level dirs.
        """
        super().__init__(
            path=repo_url,
            knowledge_type=knowledge_type,
            data_loader=loader,
            metadata=metadata,
            **kwargs,
        )
        self._repo_url = repo_url
        self._branch = branch
        self._encoding = encoding
        self._clone_dir = None
        self._head_commit = None
        self._effective_skip_dirs = SKIP_DIRS | (extra_skip_dirs or set())
        self._extra_skip_extensions = extra_skip_extensions or set()
        self._include_dirs = include_dirs

    def _clone_repo(self, shallow: bool = True):
        """Clone the repository to a temp directory.

        Args:
            shallow: If True, clone with --depth 1 (faster, no history).
                     If False, clone full history (needed for git diff).
        """
        self._clone_dir = tempfile.mkdtemp(prefix="git_repo_knowledge_")
        # Disable git transports that spawn an arbitrary shell command
        # (ext::, and its cousins). Even though subprocess uses a list argv
        # (no shell=True), git itself executes `ext::<cmd>` via `sh -c`, which
        # is a pre-auth RCE when repo_url is user-controlled. See
        # git-remote-ext(1). file:// is intentionally left enabled so local
        # repo import keeps working.
        cmd = [
            "git",
            "-c",
            "protocol.ext.allow=never",
            "clone",
            "--branch",
            self._branch,
        ]
        if shallow:
            cmd.extend(["--depth", "1"])
        cmd.extend([self._repo_url, self._clone_dir])

        try:
            logger.info(
                f"Cloning repo {self._repo_url} branch={self._branch} "
                f"shallow={shallow} to {self._clone_dir}"
            )
            subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                timeout=600,
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"Git clone failed: {e.stderr}")
            shutil.rmtree(self._clone_dir, ignore_errors=True)
            self._clone_dir = None
            raise ValueError(f"Failed to clone repository: {e.stderr}")

        # Record HEAD commit SHA
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self._clone_dir,
            capture_output=True,
            text=True,
        )
        self._head_commit = result.stdout.strip() if result.returncode == 0 else None

    def _cleanup_clone(self):
        """Remove the cloned repository directory."""
        if self._clone_dir:
            shutil.rmtree(self._clone_dir, ignore_errors=True)
            self._clone_dir = None

    def should_index_file(self, file_path: str) -> bool:
        """Check whether a file should be indexed."""
        filename = os.path.basename(file_path)
        ext = os.path.splitext(filename)[1].lower()

        if filename in SKIP_FILES or ext not in SCAN_EXTENSIONS:
            return False

        if ext in self._extra_skip_extensions:
            return False

        if self._include_dirs:
            parts = file_path.split(os.sep)
            if len(parts) < 2 or parts[0] not in self._include_dirs:
                return False

        if filename.startswith("."):
            return False

        parts = file_path.split(os.sep)
        if any(
            part in self._effective_skip_dirs or part.startswith(".")
            for part in parts[:-1]
        ):
            return False

        return True

    def build_document_from_content(
        self, file_path: str, content: str
    ) -> Optional[Document]:
        """Build a Document from in-memory file content."""
        if not file_path or content is None:
            return None

        normalized_path = file_path.replace("/", os.sep)
        if not self.should_index_file(normalized_path):
            return None

        if not content.strip():
            return None

        filename = os.path.basename(normalized_path)
        ext = os.path.splitext(filename)[1].lower()

        if ext == ".md":
            file_type = "markdown"
            language = None
            normalized_content = re.sub(r"<[^>]+>", "", content)
            doc_name = filename.replace(".md", "")
        else:
            file_type = "code"
            language = EXTENSION_LANGUAGE_MAP.get(ext, "text")
            normalized_content = content
            doc_name = filename

        content_hash = hashlib.sha256(normalized_content.encode("utf-8")).hexdigest()

        doc_metadata = {
            "source": self._repo_url,
            "file_path": normalized_path,
            "doc_name": doc_name,
            "repo_url": self._repo_url,
            "branch": self._branch,
            "file_type": file_type,
            "language": language,
            "content_hash": content_hash,
        }
        if self._metadata:
            doc_metadata.update(self._metadata)

        return Document(content=normalized_content, metadata=doc_metadata)

    def build_documents_from_files(self, files: List[Any]) -> List[Document]:
        """Build Documents from a list of path/content items."""
        documents = []
        for item in files or []:
            if isinstance(item, dict):
                file_path = item.get("path")
                content = item.get("content")
            else:
                file_path = getattr(item, "path", None)
                content = getattr(item, "content", None)
            doc = self.build_document_from_content(file_path, content)
            if doc:
                documents.append(doc)
        return documents

    def _read_single_file(self, rel_path: str) -> Optional[Document]:
        """Read a single file from clone dir and return a Document."""
        abs_path = os.path.join(self._clone_dir, rel_path)
        if not os.path.isfile(abs_path):
            return None

        try:
            with open(abs_path, encoding=self._encoding, errors="ignore") as f:
                content = f.read()
        except Exception as e:
            logger.warning(f"Failed to read {rel_path}: {e}")
            return None

        return self.build_document_from_content(rel_path, content)

    def _load(self) -> List[Document]:
        """Clone the git repo and load all supported files as Documents."""
        if not self._repo_url:
            raise ValueError("repo_url is required")

        self._clone_repo(shallow=True)

        # Scan all supported files
        documents = []
        for root, dirs, files in os.walk(self._clone_dir):
            dirs[:] = [
                d
                for d in dirs
                if d not in self._effective_skip_dirs and not d.startswith(".")
            ]
            for filename in sorted(files):
                rel_path = os.path.relpath(
                    os.path.join(root, filename), self._clone_dir
                )
                doc = self._read_single_file(rel_path)
                if doc:
                    documents.append(doc)

        md_count = sum(
            1 for d in documents if d.metadata.get("file_type") == "markdown"
        )
        code_count = sum(1 for d in documents if d.metadata.get("file_type") == "code")
        logger.info(
            f"Loaded {len(documents)} files from {self._repo_url} "
            f"({md_count} markdown, {code_count} code), "
            f"HEAD={self._head_commit}"
        )

        self._cleanup_clone()
        return documents

    def load_incremental(self, last_commit: str) -> Optional[Dict]:
        """Load only changed files since last_commit using git diff.

        Args:
            last_commit: The commit SHA from the last sync.

        Returns:
            Dict with keys: head_commit, added, modified, deleted.
            Returns None if git diff fails (caller should fall back to full load).
        """
        if not self._repo_url:
            raise ValueError("repo_url is required")

        # Need full clone (not shallow) to have history for diff
        self._clone_repo(shallow=False)

        # Run git diff to find changed files
        diff_result = subprocess.run(
            ["git", "diff", "--name-status", last_commit, "HEAD"],
            cwd=self._clone_dir,
            capture_output=True,
            text=True,
        )

        if diff_result.returncode != 0:
            logger.warning(
                f"git diff failed (commit {last_commit} not reachable?): "
                f"{diff_result.stderr}"
            )
            self._cleanup_clone()
            return None

        # Parse diff output
        added = []
        modified = []
        deleted = []

        for line in diff_result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split("\t", 1)
            if len(parts) != 2:
                continue
            status, file_path = parts

            # Normalize status (R100 → R, etc.)
            status_char = status[0]

            if status_char == "D":
                ext = os.path.splitext(file_path)[1].lower()
                path_parts = file_path.split("/")
                if any(p.startswith(".") for p in path_parts):
                    continue
                if ext in SCAN_EXTENSIONS:
                    deleted.append(file_path)
            elif status_char in ("A", "M", "R"):
                # For renames, file_path may contain old\tnew
                if status_char == "R" and "\t" in file_path:
                    _, file_path = file_path.split("\t", 1)

                doc = self._read_single_file(file_path)
                if doc:
                    if status_char == "A":
                        added.append(doc)
                    else:
                        modified.append(doc)

        logger.info(
            f"Incremental diff from {last_commit[:8]}..{self._head_commit[:8]}: "
            f"{len(added)} added, {len(modified)} modified, {len(deleted)} deleted"
        )

        self._cleanup_clone()

        return {
            "head_commit": self._head_commit,
            "added": added,
            "modified": modified,
            "deleted": deleted,
        }

    @classmethod
    def support_chunk_strategy(cls) -> List[ChunkStrategy]:
        """Return supported chunk strategies."""
        return [
            ChunkStrategy.CHUNK_BY_MARKDOWN_HEADER,
            ChunkStrategy.CHUNK_BY_SIZE,
            ChunkStrategy.CHUNK_BY_SEPARATOR,
        ]

    @classmethod
    def default_chunk_strategy(cls) -> ChunkStrategy:
        """Return default chunk strategy."""
        return ChunkStrategy.CHUNK_BY_MARKDOWN_HEADER

    @classmethod
    def type(cls) -> KnowledgeType:
        """Return knowledge type."""
        return KnowledgeType.GIT_REPO

    @classmethod
    def document_type(cls):
        """Return document type."""
        from dbgpt.rag.knowledge.base import DocumentType

        return DocumentType.MARKDOWN

    @property
    def suffix(self) -> Any:
        """Get document suffix."""
        from dbgpt.rag.knowledge.base import DocumentType

        return DocumentType.MARKDOWN.value
