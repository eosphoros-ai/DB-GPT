"""Source identities shared by knowledge readers and report capture."""

import ast
import json
from typing import Any, Dict


def parse_chunk_metadata(value: Any) -> Dict[str, Any]:
    """Read JSON and the Python dictionary format used by older ingestions."""
    if isinstance(value, dict):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except ValueError:
            try:
                parsed = ast.literal_eval(value)
            except (ValueError, SyntaxError):
                return {}
    else:
        return {}
    if not isinstance(parsed, dict):
        return {}
    properties = parsed.get("prop_field")
    if isinstance(properties, (dict, str)) and properties is not parsed:
        return {**parse_chunk_metadata(properties), **parsed}
    return dict(parsed)


def prepare_document_chunks(chunks, document, vector_ids=None):
    """Attach document identity and source order before indexing/persistence."""
    summary = parse_chunk_metadata(document.summary)
    for index, chunk in enumerate(chunks):
        metadata = parse_chunk_metadata(chunk.metadata)
        metadata.update(
            document_id=document.id,
            doc_name=document.doc_name,
            chunk_index=index,
            chunk_id=(
                vector_ids[index]
                if vector_ids and index < len(vector_ids)
                else chunk.chunk_id
            ),
        )
        metadata.setdefault("file_path", summary.get("file_path") or document.doc_name)
        chunk.metadata = metadata


def document_chunk_entries(file_info, chunks):
    """Resolve old database rows against the document's persisted vector IDs."""
    vector_ids = file_info.get("vector_ids") or []
    if isinstance(vector_ids, str):
        vector_ids = vector_ids.split(",") if vector_ids else []
    if len(vector_ids) != len(chunks):
        # A partially deleted/rebuilt document cannot be mapped by position.
        vector_ids = []
    entries = []
    for index, chunk in enumerate(chunks):
        metadata = parse_chunk_metadata(chunk.meta_info)
        chunk_index = metadata.get("chunk_index")
        if (
            not isinstance(chunk_index, int)
            or isinstance(chunk_index, bool)
            or chunk_index < 0
        ):
            chunk_index = index
        chunk_id = metadata.get("chunk_id")
        if not chunk_id and index < len(vector_ids):
            chunk_id = vector_ids[index]
        metadata.update(
            document_id=file_info["doc_id"],
            doc_name=file_info.get("doc_name") or file_info["file_path"],
            file_path=file_info["file_path"],
            chunk_id=str(chunk_id or chunk.id),
            chunk_db_id=chunk.id,
            chunk_index=chunk_index,
        )
        entries.append((chunk, metadata))
    return sorted(entries, key=lambda entry: entry[1]["chunk_index"])


class KnowledgeChunkResolver:
    """Resolve retrieval IDs to source rows, including legacy vector metadata."""

    def __init__(self, space_name):
        self.space_name = space_name
        self._files = None
        self._entries = {}

    def resolve(self, chunk):
        metadata = parse_chunk_metadata(getattr(chunk, "metadata", None))
        chunk_id = str(
            metadata.get("chunk_id") or getattr(chunk, "chunk_id", None) or ""
        )
        document_id = (
            metadata.get("document_id")
            or metadata.get("doc_id")
            or metadata.get("file_id")
        )
        from .tools.kb_file_tools import _get_all_file_paths, _get_chunk_dao

        if self._files is None:
            self._files = _get_all_file_paths(self.space_name)
        files = [f for f in self._files if chunk_id in f.get("vector_ids", [])]
        if not files:
            files = [f for f in self._files if str(f["doc_id"]) == str(document_id)]
        for file_info in files:
            doc_id = file_info["doc_id"]
            if doc_id not in self._entries:
                dao, entity = _get_chunk_dao()
                chunks = []
                page = 1
                while True:
                    batch = dao.get_document_chunks(
                        entity(document_id=doc_id), page=page, page_size=1000
                    )
                    chunks.extend(batch)
                    if len(batch) < 1000:
                        break
                    page += 1
                self._entries[doc_id] = document_chunk_entries(file_info, chunks)
            entries = self._entries[doc_id]
            matches = [
                entry
                for entry in entries
                if entry[1]["chunk_id"] == chunk_id
                or entry[1]["chunk_db_id"] == metadata.get("chunk_db_id")
            ]
            if not matches:
                # Some retrievers create a fresh Chunk UUID. Only accept a unique
                # exact content match within the identified document.
                matches = [
                    entry for entry in entries if entry[0].content == chunk.content
                ]
            if len(matches) == 1:
                return {**metadata, **matches[0][1]}
        return metadata
