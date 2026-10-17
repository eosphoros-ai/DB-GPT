"""File system tools for knowledge spaces (kb_ls, kb_glob, kb_grep, kb_cat)."""

import fnmatch
import logging
import re
import time
from typing import Annotated, List, Optional

from dbgpt.agent.resource.tool.base import tool
from dbgpt.core.interface.report_capture import (
    capture_reference_artifact,
    get_current_artifact_sink,
    sha256_text,
)

from ..chunk_metadata import document_chunk_entries, parse_chunk_metadata

logger = logging.getLogger(__name__)

_CONTEXT_PREFIX_RE = re.compile(r"^\[文件: [^\]]*\](?:\s*\[路径: [^\]]*\])?\s*\n?")


def _get_document_dao():
    from ..models.document_db import KnowledgeDocumentDao, KnowledgeDocumentEntity

    return KnowledgeDocumentDao(), KnowledgeDocumentEntity


def _get_chunk_dao():
    from ..models.chunk_db import DocumentChunkDao, DocumentChunkEntity

    return DocumentChunkDao(), DocumentChunkEntity


def _resolve_space_name(knowledge_id: str) -> str:
    """Resolve knowledge_id (numeric id or name) to space name."""
    if not str(knowledge_id).isdigit():
        return str(knowledge_id)
    # Numeric id: look up the space name
    from ..models.models import KnowledgeSpaceDao, KnowledgeSpaceEntity

    dao = KnowledgeSpaceDao()
    spaces = dao.get_knowledge_space(KnowledgeSpaceEntity(id=int(knowledge_id)))
    return spaces[0].name if spaces else str(knowledge_id)


def _get_all_file_paths(knowledge_id: str) -> List[dict]:
    """Get all file paths for a knowledge space.

    knowledge_id can be either the space name or space id.
    In DB-GPT, KnowledgeDocumentEntity uses `space` (name) and `id` (doc id),
    and metadata is stored in `result` field as JSON.
    """
    dao, Entity = _get_document_dao()
    space_name = _resolve_space_name(knowledge_id)
    docs = dao.get_knowledge_documents(
        Entity(space=space_name), page=1, page_size=10000
    )
    if not docs:
        return []
    results = []
    for doc in docs:
        meta = parse_chunk_metadata(doc.summary)
        file_path = meta.get("file_path", "") or doc.doc_name or ""
        if not file_path:
            continue
        results.append(
            {
                "file_path": file_path,
                "file_type": meta.get("file_type", ""),
                "language": meta.get("language", ""),
                "doc_id": doc.id,
                "doc_name": doc.doc_name,
                "space_name": space_name,
                "vector_ids": (doc.vector_ids or "").split(",")
                if doc.vector_ids
                else [],
            }
        )
    return results


def _find_doc_by_file_path(knowledge_id: str, path: str) -> Optional[dict]:
    for f in _get_all_file_paths(knowledge_id):
        if f["file_path"] == path:
            return f
    return None


@tool("kb_ls", description="List files and directories in a knowledge space.")
async def kb_ls(
    knowledge_id: Annotated[str, "Knowledge space ID"],
    path: Annotated[str, "Directory path"] = "",
    offset: Annotated[int, "Pagination offset"] = 0,
    limit: Annotated[int, "Max results"] = 200,
) -> str:
    offset, limit = int(offset) or 0, int(limit) or 200
    all_files = _get_all_file_paths(knowledge_id)
    if not all_files:
        return f"No files in knowledge space {knowledge_id}"
    target = path.rstrip("/")
    prefix = (target + "/") if target else ""
    dirs: dict[str, int] = {}
    files = []
    for f in all_files:
        fp = f["file_path"]
        if not fp.startswith(prefix):
            continue
        remaining = fp[len(prefix) :]
        if not remaining:
            continue
        parts = remaining.split("/")
        if len(parts) == 1:
            files.append((parts[0], f["file_type"], f["language"]))
        else:
            dirs[parts[0]] = dirs.get(parts[0], 0) + 1
    if not dirs and not files:
        return f"Directory '{path}' does not exist or is empty"
    entries = []
    for d, c in sorted(dirs.items()):
        entries.append(f"  {d}/\t({c} files)")
    for n, ft, lang in sorted(files):
        entries.append(f"  {n}\t{lang or ft or ''}")
    paged = entries[offset : offset + limit]
    display = target or "/"
    lines = [f"Directory: {display} ({len(files)} files, {len(dirs)} dirs)"] + paged
    return "\n".join(lines)


async def kb_ls_json(
    knowledge_id: str,
    path: str = "",
    offset: int = 0,
    limit: int = 200,
) -> dict:
    """Return structured JSON directory listing for a knowledge space.

    Unlike kb_ls which returns formatted text for AI agents, this returns
    a dict suitable for building a file tree UI.
    """
    offset, limit = int(offset) or 0, int(limit) or 200
    all_files = _get_all_file_paths(knowledge_id)
    if not all_files:
        return {"path": path or "/", "entries": [], "total_files": 0, "total_dirs": 0}

    target = path.rstrip("/")
    prefix = (target + "/") if target else ""
    dirs: dict = {}  # dir_name -> count
    files: list = []

    for f in all_files:
        fp = f["file_path"]
        if not fp.startswith(prefix):
            continue
        remaining = fp[len(prefix) :]
        if not remaining:
            continue
        parts = remaining.split("/")
        if len(parts) == 1:
            files.append(
                {
                    "name": parts[0],
                    "path": fp,
                    "is_dir": False,
                    "file_type": f.get("file_type", ""),
                    "language": f.get("language", ""),
                    "doc_id": f.get("doc_id"),
                }
            )
        else:
            dir_name = parts[0]
            if dir_name not in dirs:
                dirs[dir_name] = 0
            dirs[dir_name] += 1

    entries = []
    for d, c in sorted(dirs.items()):
        dir_path = f"{prefix}{d}" if prefix else d
        entries.append(
            {
                "name": d,
                "path": dir_path,
                "is_dir": True,
                "child_count": c,
            }
        )
    for f in sorted(files, key=lambda x: x["name"]):
        entries.append(f)

    paged = entries[offset : offset + limit]

    return {
        "path": target or "/",
        "entries": paged,
        "total_files": len(files),
        "total_dirs": len(dirs),
    }


@tool(
    "kb_glob", description="Search files by name or glob pattern in a knowledge space."
)
async def kb_glob(
    knowledge_id: Annotated[str, "Knowledge space ID"],
    pattern: Annotated[str, "File name keyword or glob pattern"],
    limit: Annotated[int, "Max results"] = 200,
    offset: Annotated[int, "Pagination offset"] = 0,
) -> str:
    limit, offset = int(limit) or 200, int(offset) or 0
    all_files = _get_all_file_paths(knowledge_id)
    if not all_files:
        return f"No files in knowledge space {knowledge_id}"
    is_glob = any(c in pattern for c in "*?[")
    matches = []
    for f in all_files:
        fp = f["file_path"]
        if is_glob:
            if fnmatch.fnmatch(fp, pattern):
                matches.append(f)
            elif pattern.startswith("**/") and fnmatch.fnmatch(fp, pattern[3:]):
                matches.append(f)
        else:
            if pattern.lower() in fp.lower():
                matches.append(f)
    if not matches:
        return f"No files matching '{pattern}'"
    total = len(matches)
    paged = sorted(matches, key=lambda x: x["file_path"])[offset : offset + limit]
    lines = [
        f"Matching '{pattern}': {total} files "
        f"(showing {offset + 1}-{offset + len(paged)}):"
    ]
    for f in paged:
        lines.append(f"  {f['file_path']}\t{f['language'] or f['file_type'] or ''}")
    return "\n".join(lines)


@tool(
    "kb_grep",
    description="Search file contents by keyword. Prefer this over semantic search.",
)
async def kb_grep(
    knowledge_id: Annotated[str, "Knowledge space ID"],
    query: Annotated[str, "Search keyword"],
    path: Annotated[str, "Directory path filter"] = "",
    file_pattern: Annotated[str, "File pattern like *.py"] = "",
    limit: Annotated[int, "Max files"] = 20,
    offset: Annotated[int, "Pagination offset"] = 0,
) -> str:
    capture_enabled = get_current_artifact_sink() is not None
    started = time.perf_counter() if capture_enabled else None
    limit, offset = int(limit) or 20, int(offset) or 0
    chunk_dao, ChunkEntity = _get_chunk_dao()
    all_files = _get_all_file_paths(knowledge_id)
    if not all_files:
        return f"No files in knowledge space {knowledge_id}"
    target_files = {}
    norm_path = path.rstrip("/") if path else ""
    for f in all_files:
        fp = f["file_path"]
        if norm_path and fp != norm_path and not fp.startswith(norm_path + "/"):
            continue
        if file_pattern and not fnmatch.fnmatch(fp, file_pattern):
            continue
        target_files[f["doc_id"]] = f
    if not target_files:
        return f"No files in scope '{path or file_pattern or 'repo'}'"
    doc_matches: dict[int, list[tuple[str, int, str]]] = {}
    fetch_limit = offset + limit
    for doc_id in target_files:
        if len(doc_matches) >= fetch_limit:
            break
        chunks = _load_document_chunks(chunk_dao, ChunkEntity, doc_id)
        for chunk, chunk_meta in document_chunk_entries(target_files[doc_id], chunks):
            # Skip summary chunks (identified by meta_info chunk_type)
            if chunk_meta.get("chunk_type") == "summary":
                continue
            content = _CONTEXT_PREFIX_RE.sub("", chunk.content or "")
            start_line = chunk_meta.get("start_line") or 1
            chunk_matches = []
            for i, line in enumerate(content.split("\n")):
                if query.lower() in line.lower():
                    chunk_matches.append((start_line + i, line.strip()))
            if chunk_matches:
                doc_matches.setdefault(doc_id, []).extend(
                    (chunk_meta["chunk_id"], line, text) for line, text in chunk_matches
                )
                if capture_enabled:
                    file_info = target_files.get(doc_id) or {}
                    chunk_id = chunk_meta["chunk_id"]
                    page = chunk_meta.get("page")
                    if page is None:
                        page = chunk_meta.get("page_number")
                    capture_reference_artifact(
                        reference_type="knowledge",
                        source_id=chunk_id,
                        action="knowledge.grep",
                        duration_ms=max(
                            0,
                            int((time.perf_counter() - started) * 1000)
                            if started is not None
                            else 0,
                        ),
                        source_name=file_info.get("doc_name")
                        or file_info.get("file_path")
                        or chunk_id,
                        uri=f"kb://{knowledge_id}/{doc_id}/{chunk_id}",
                        locator={
                            "knowledge_id": str(knowledge_id),
                            "space_name": file_info.get("space_name"),
                            "document_id": doc_id,
                            "chunk_id": chunk_id,
                            "chunk_index": chunk_meta.get("chunk_index"),
                            "chunk_db_id": chunk_meta.get("chunk_db_id"),
                            "page": page,
                            "path": file_info.get("file_path"),
                            "chunk_start_line": start_line,
                            "start_line": min(line for line, _text in chunk_matches),
                            "end_line": max(line for line, _text in chunk_matches),
                            "matched_lines": [line for line, _text in chunk_matches],
                            "line_scope": "document"
                            if chunk_meta.get("start_line")
                            else "chunk",
                        },
                        excerpt=content,
                        metadata={
                            "query_sha256": sha256_text(query),
                            "retrieval_query": query[:500],
                        },
                    )
    if not doc_matches:
        return f"No content matching '{query}' in '{path or file_pattern or 'repo'}'"
    all_doc_ids = list(doc_matches.keys())
    total_files = len(all_doc_ids)
    paged_ids = all_doc_ids[offset : offset + limit]
    lines = [f"'{query}' matched {total_files} files:"]
    for doc_id in paged_ids:
        file_info = target_files.get(doc_id) or {}
        lines.append(f"\n{file_info.get('file_path', doc_id)}:")
        for source_chunk_id, line_no, content in doc_matches[doc_id][:10]:
            lines.append(
                f"  chunk_id={source_chunk_id} line={line_no}: {content[:120]}"
            )
    result = "\n".join(lines)
    # Cap total output size; larger results are persisted by ToolResultStorage.
    MAX_KB_GREP_CHARS = 15_000
    if len(result) > MAX_KB_GREP_CHARS:
        result = (
            result[:MAX_KB_GREP_CHARS]
            + f"\n\n... [Output truncated at {MAX_KB_GREP_CHARS} chars]"
        )
    return result


def _load_document_chunks(dao, entity, document_id):
    chunks = []
    page = 1
    while True:
        batch = dao.get_document_chunks(
            entity(document_id=document_id), page=page, page_size=1000
        )
        chunks.extend(batch)
        if len(batch) < 1000:
            return chunks
        page += 1


@tool(
    "kb_cat", description="Read knowledge content by path and optional source chunk ID."
)
async def kb_cat(
    knowledge_id: Annotated[str, "Knowledge space ID"],
    path: Annotated[str, "File path like src/auth/login.py"],
    start_line: Annotated[int, "Start line (1-based)"] = 1,
    end_line: Annotated[int, "End line, 0 = to end"] = 0,
    chunk_id: Annotated[str, "Optional source chunk ID returned by retrieval"] = "",
) -> str:
    capture_enabled = get_current_artifact_sink() is not None
    started = time.perf_counter() if capture_enabled else None
    start_line, end_line = int(start_line) or 1, int(end_line) or 0
    file_info = _find_doc_by_file_path(knowledge_id, path)
    if not file_info:
        return f"File '{path}' not found"
    chunk_dao, ChunkEntity = _get_chunk_dao()
    chunks = _load_document_chunks(chunk_dao, ChunkEntity, file_info["doc_id"])
    content_chunks = []
    for chunk, meta in document_chunk_entries(file_info, chunks):
        # Skip summary chunks
        if meta.get("chunk_type") == "summary":
            continue
        if chunk_id and str(chunk_id) not in {meta["chunk_id"], str(chunk.id)}:
            continue
        content_chunks.append((meta, _CONTEXT_PREFIX_RE.sub("", chunk.content or "")))
    if chunk_id and not content_chunks:
        return f"Chunk '{chunk_id}' not found in '{path}'"
    full_lines = []
    chunk_ranges = []
    for meta, content in content_chunks:
        first_line = len(full_lines)
        full_lines.extend(content.split("\n"))
        chunk_ranges.append((first_line, len(full_lines), meta, content))
    if not full_lines:
        return f"File '{path}' is empty"
    total = len(full_lines)
    lang = file_info.get("language") or file_info.get("file_type") or ""
    start_idx = max(0, start_line - 1)
    end_idx = min(end_line or total, total)
    visible_end = min(end_idx, start_idx + 500)
    lines = [f"{path} ({lang}, {total} lines)"]
    lines.append(
        "Source chunks (line ranges refer to this read, not original document pages):"
    )
    for first, last, meta, _ in chunk_ranges:
        if first < visible_end and last > start_idx:
            lines.append(
                (
                    "  chunk_id="
                    f"{meta['chunk_id']}"
                    " chunk_index="
                    f"{meta['chunk_index']}"
                    " lines="
                    f"{first + 1}"
                    "-"
                    f"{last}"
                )
            )
    for i, line in enumerate(full_lines[start_idx:visible_end]):
        lines.append(f"  {start_idx + i + 1:>4} | {line}")
    if visible_end < end_idx:
        lines.append(f"  ... (truncated, use start_line={visible_end + 1} to continue)")
    result = "\n".join(lines)
    # Cap total output size; larger results are persisted by ToolResultStorage.
    MAX_KB_CAT_CHARS = 20_000
    if len(result) > MAX_KB_CAT_CHARS:
        result = (
            result[:MAX_KB_CAT_CHARS]
            + f"\n\n... [Output truncated at {MAX_KB_CAT_CHARS} chars. "
            f"Use start_line/end_line to read specific sections]"
        )
    if capture_enabled:
        document_id = file_info["doc_id"]
        for first, last, meta, content in chunk_ranges:
            if first >= end_idx or last <= start_idx:
                continue
            locator = {
                "knowledge_id": str(knowledge_id),
                "space_name": file_info.get("space_name"),
                "document_id": document_id,
                "path": path,
                "chunk_id": meta["chunk_id"],
                "chunk_db_id": meta["chunk_db_id"],
                "chunk_index": meta["chunk_index"],
                "page": meta.get("page", meta.get("page_number")),
                "read_start_line": max(first, start_idx) + 1,
                "read_end_line": min(last, end_idx),
            }
            for key in ("start_line", "end_line"):
                if meta.get(key) is not None:
                    locator[key] = meta[key]
            capture_reference_artifact(
                reference_type="knowledge",
                source_id=meta["chunk_id"],
                action="knowledge.cat",
                duration_ms=max(0, int((time.perf_counter() - started) * 1000)),
                source_name=file_info.get("doc_name") or path,
                uri=f"kb://{knowledge_id}/{document_id}/{meta['chunk_id']}",
                locator=locator,
                excerpt=content,
            )
    return result
