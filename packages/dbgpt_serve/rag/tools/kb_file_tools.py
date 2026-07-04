"""File system tools for knowledge spaces (kb_ls, kb_glob, kb_grep, kb_cat)."""

import fnmatch
import json
import logging
import re
from typing import Annotated, List, Optional

from dbgpt.agent.resource.tool.base import tool

logger = logging.getLogger(__name__)

_CONTEXT_PREFIX_RE = re.compile(r"^\[文件: [^\]]*\](?:\s*\[路径: [^\]]*\])?\s*\n?")


def _get_document_dao():
    from ..models.document_db import KnowledgeDocumentDao, KnowledgeDocumentEntity
    return KnowledgeDocumentDao(), KnowledgeDocumentEntity


def _get_chunk_dao():
    from ..models.chunk_db import DocumentChunkDao, DocumentChunkEntity
    return DocumentChunkDao(), DocumentChunkEntity


def _get_all_file_paths(knowledge_id: str) -> List[dict]:
    dao, Entity = _get_document_dao()
    docs = dao.get_knowledge_documents(
        Entity(knowledge_id=knowledge_id), page=1, page_size=10000,
    )
    if not docs:
        return []
    results = []
    for doc in docs:
        try:
            meta = json.loads(doc.meta_data) if doc.meta_data else {}
        except (json.JSONDecodeError, TypeError):
            meta = {}
        if not isinstance(meta, dict):
            meta = {}
        file_path = meta.get("file_path", "") or doc.doc_name or ""
        if not file_path:
            continue
        results.append({
            "file_path": file_path,
            "file_type": meta.get("file_type", ""),
            "language": meta.get("language", ""),
            "doc_id": doc.doc_id,
            "doc_name": doc.doc_name,
        })
    return results


def _find_doc_by_file_path(knowledge_id: str, path: str) -> Optional[dict]:
    all_files = _get_all_file_paths(knowledge_id)
    for f in all_files:
        if f["file_path"] == path:
            return f
    return None


@tool(
    name="kb_ls",
    description="列出知识库指定目录下的文件和子目录。查找文件请优先用 kb_glob 或 kb_grep。",
)
async def kb_ls(
    knowledge_id: Annotated[str, "知识空间 ID"],
    path: Annotated[str, "目录路径，空字符串表示根目录"] = "",
    offset: Annotated[int, "跳过前 N 条记录"] = 0,
    limit: Annotated[int, "最多返回条目数"] = 200,
) -> str:
    offset = int(offset) if offset else 0
    limit = int(limit) if limit else 200
    all_files = _get_all_file_paths(knowledge_id)
    if not all_files:
        return f"知识空间 {knowledge_id} 中没有文件"
    target = path.rstrip("/")
    prefix = (target + "/") if target else ""
    dirs = {}
    files = []
    for f in all_files:
        fp = f["file_path"]
        if not fp.startswith(prefix):
            continue
        remaining = fp[len(prefix):]
        if not remaining:
            continue
        parts = remaining.split("/")
        if len(parts) == 1:
            files.append((parts[0], f["file_type"], f["language"]))
        else:
            dirs[parts[0]] = dirs.get(parts[0], 0) + 1
    if not dirs and not files:
        return f"目录 '{path}' 不存在或为空"
    all_entries = []
    for dir_name in sorted(dirs.keys()):
        all_entries.append(f"  {dir_name}/\t({dirs[dir_name]} files)")
    for name, ftype, lang in sorted(files):
        all_entries.append(f"  {name}\t{lang or ftype or ''}")
    total_entries = len(all_entries)
    display_path = target or "/"
    paged_entries = all_entries[offset : offset + limit]
    if not paged_entries:
        return f"目录 '{display_path}' 共 {total_entries} 条，offset={offset} 超出范围"
    lines = [f"目录: {display_path} ({len(files)} files, {len(dirs)} dirs)"]
    MAX_OUTPUT_CHARS = 8000
    current_chars = len(lines[0])
    truncated = False
    for entry in paged_entries:
        current_chars += len(entry)
        if current_chars > MAX_OUTPUT_CHARS:
            truncated = True
            break
        lines.append(entry)
    shown = len(lines) - 1
    if truncated or offset + limit < total_entries:
        next_offset = offset + shown
        remaining = total_entries - next_offset
        if remaining > 0:
            lines.append(f"\n... 还有 {remaining} 条未显示，使用 offset={next_offset} 查看后续结果。")
    return "\n".join(lines)


@tool(
    name="kb_glob",
    description="按文件名/文档名搜索知识库文件。支持关键词和 glob 模式。",
)
async def kb_glob(
    knowledge_id: Annotated[str, "知识空间 ID"],
    pattern: Annotated[str, "文件名关键词或 glob 模式"],
    limit: Annotated[int, "最多返回文件数"] = 200,
    offset: Annotated[int, "跳过前 N 个匹配文件"] = 0,
) -> str:
    limit = int(limit) if limit else 200
    offset = int(offset) if offset else 0
    all_files = _get_all_file_paths(knowledge_id)
    if not all_files:
        return f"知识空间 {knowledge_id} 中没有文件"
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
        return f"没有匹配 '{pattern}' 的文件"
    total_matches = len(matches)
    sorted_matches = sorted(matches, key=lambda x: x["file_path"])
    paged = sorted_matches[offset : offset + limit]
    if not paged:
        return f"匹配 '{pattern}' 共 {total_matches} 个文件，offset={offset} 超出范围"
    lines = [f"匹配 '{pattern}' 共 {total_matches} 个文件 (显示第 {offset + 1}-{offset + len(paged)} 个):"]
    MAX_OUTPUT_CHARS = 8000
    current_chars = len(lines[0])
    truncated = False
    for f in paged:
        type_info = f["language"] or f["file_type"] or ""
        entry = f"  {f['file_path']}\t{type_info}"
        current_chars += len(entry)
        if current_chars > MAX_OUTPUT_CHARS:
            truncated = True
            break
        lines.append(entry)
    shown = len(lines) - 1
    if truncated or offset + limit < total_matches:
        next_offset = offset + shown
        remaining = total_matches - next_offset
        if remaining > 0:
            lines.append(f"\n... 还有 {remaining} 个文件未显示，使用 offset={next_offset} 查看后续结果。")
    return "\n".join(lines)


@tool(
    name="kb_grep",
    description="在知识库文件内容中搜索关键词，返回包含该关键词的文件和具体行内容。优先使用此工具而非语义搜索。",
)
async def kb_grep(
    knowledge_id: Annotated[str, "知识空间 ID"],
    query: Annotated[str, "搜索关键词"],
    path: Annotated[str, "限定搜索的目录路径"] = "",
    file_pattern: Annotated[str, "限定文件类型如 '*.py'"] = "",
    limit: Annotated[int, "最多返回文件数"] = 20,
    offset: Annotated[int, "跳过前 N 个匹配文件"] = 0,
) -> str:
    limit = int(limit) if limit else 20
    offset = int(offset) if offset else 0
    chunk_dao, ChunkEntity = _get_chunk_dao()
    all_files = _get_all_file_paths(knowledge_id)
    if not all_files:
        return f"知识空间 {knowledge_id} 中没有文件"
    target_files = {}
    norm_path = path.rstrip("/") if path else ""
    for f in all_files:
        fp = f["file_path"]
        if norm_path:
            if fp != norm_path and not fp.startswith(norm_path + "/"):
                continue
        if file_pattern and not fnmatch.fnmatch(fp, file_pattern):
            continue
        target_files[f["doc_id"]] = f
    if not target_files:
        scope = path or file_pattern or "仓库"
        return f"在 '{scope}' 范围内没有文件"
    doc_matches = {}
    fetch_limit = offset + limit
    if len(target_files) <= 50:
        for doc_id in target_files:
            if len(doc_matches) >= fetch_limit:
                break
            chunks = chunk_dao.get_document_chunks(
                ChunkEntity(doc_id=doc_id, content=query), page=1, page_size=200,
            )
            _collect_grep_matches(chunks, doc_id, query, doc_matches, fetch_limit)
    else:
        query_entity = ChunkEntity(knowledge_id=knowledge_id, content=query)
        chunks = chunk_dao.get_document_chunks(query_entity, page=1, page_size=500)
        for chunk in chunks:
            if chunk.chunk_type == "summary":
                continue
            doc_id = chunk.doc_id
            if doc_id not in target_files:
                continue
            if len(doc_matches) >= fetch_limit and doc_id not in doc_matches:
                break
            _collect_grep_matches([chunk], doc_id, query, doc_matches, fetch_limit)
    if not doc_matches:
        scope = path or file_pattern or "仓库"
        return f"在 '{scope}' 中未找到包含 '{query}' 的内容"
    all_doc_ids = list(doc_matches.keys())
    total_files = len(all_doc_ids)
    total_matches = sum(len(v) for v in doc_matches.values())
    paged_doc_ids = all_doc_ids[offset : offset + limit]
    if not paged_doc_ids:
        return f"'{query}' 共匹配 {total_files} 个文件，offset={offset} 超出范围"
    result_lines = [
        f"'{query}' 匹配 {total_files} 个文件 {total_matches} 处"
        f" (显示第 {offset + 1}-{offset + len(paged_doc_ids)} 个文件):"
    ]
    MAX_OUTPUT_CHARS = 8000
    current_chars = len(result_lines[0])
    truncated = False
    for doc_id in paged_doc_ids:
        matches = doc_matches[doc_id]
        file_info = target_files.get(doc_id) or {}
        file_header = f"\n{file_info.get('file_path', doc_id)}:"
        result_lines.append(file_header)
        current_chars += len(file_header)
        for line_no, content in matches[:10]:
            line = f"  {line_no}: {content}"
            current_chars += len(line)
            if current_chars > MAX_OUTPUT_CHARS:
                truncated = True
                break
            result_lines.append(line)
        if truncated:
            break
    if truncated or offset + limit < total_files:
        next_offset = offset + len(paged_doc_ids)
        result_lines.append(f"\n... 使用 offset={next_offset} 查看后续结果。")
    return "\n".join(result_lines)


def _collect_grep_matches(chunks, doc_id, query, doc_matches, limit):
    for chunk in chunks:
        if chunk.chunk_type == "summary":
            continue
        if doc_id not in doc_matches:
            if len(doc_matches) >= limit:
                return
            doc_matches[doc_id] = []
        content = chunk.content or ""
        content = _CONTEXT_PREFIX_RE.sub("", content)
        try:
            chunk_meta = json.loads(chunk.meta_data) if chunk.meta_data else {}
        except (json.JSONDecodeError, TypeError):
            chunk_meta = {}
        start_line = chunk_meta.get("start_line", 1)
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if query.lower() in line.lower():
                line_no = start_line + i
                doc_matches[doc_id].append((line_no, line.strip()[:120]))


@tool(
    name="kb_cat",
    description="读取知识库中指定文件/文档的内容。支持按行号范围读取。",
)
async def kb_cat(
    knowledge_id: Annotated[str, "知识空间 ID"],
    path: Annotated[str, "文件路径，如 'src/auth/login.py'"],
    start_line: Annotated[int, "起始行号（从 1 开始）"] = 1,
    end_line: Annotated[int, "结束行号，0 表示读到末尾"] = 0,
) -> str:
    start_line = int(start_line) if start_line else 1
    end_line = int(end_line) if end_line else 0
    file_info = _find_doc_by_file_path(knowledge_id, path)
    if not file_info:
        return f"文件 '{path}' 不存在"
    doc_id = file_info["doc_id"]
    chunk_dao, ChunkEntity = _get_chunk_dao()
    chunks = chunk_dao.get_document_chunks(
        ChunkEntity(doc_id=doc_id), page=1, page_size=1000,
    )
    content_chunks = []
    for chunk in chunks:
        if chunk.chunk_type == "summary":
            continue
        try:
            meta = json.loads(chunk.meta_data) if chunk.meta_data else {}
        except (json.JSONDecodeError, TypeError):
            meta = {}
        chunk_index = meta.get("chunk_index", 0)
        content_chunks.append((chunk_index, chunk.content or ""))
    content_chunks.sort(key=lambda x: x[0])
    full_lines = []
    for _, content in content_chunks:
        content = _CONTEXT_PREFIX_RE.sub("", content)
        full_lines.extend(content.split("\n"))
    if not full_lines:
        return f"文件 '{path}' 内容为空"
    total_lines = len(full_lines)
    lang = file_info.get("language") or file_info.get("file_type") or ""
    start_idx = max(0, start_line - 1)
    end_idx = end_line if end_line > 0 else total_lines
    end_idx = min(end_idx, total_lines)
    selected = full_lines[start_idx:end_idx]
    result_lines = [f"{path} ({lang}, {total_lines} lines)"]
    for i, line in enumerate(selected):
        line_no = start_idx + i + 1
        result_lines.append(f"  {line_no:>4} | {line}")
    if len(result_lines) > 502:
        result_lines = result_lines[:502]
        next_start = start_idx + 500 + 1
        result_lines.append(
            f"  ... (已截断，使用 start_line={next_start} 继续读取)"
        )
    return "\n".join(result_lines)