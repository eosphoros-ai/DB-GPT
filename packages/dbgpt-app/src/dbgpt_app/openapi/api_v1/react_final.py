"""Structured final-answer and citation handling for ReAct agent streams."""

import hashlib
import json
import math
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

FINAL_PROTOCOL_VERSION = 2
MAX_CITATIONS = 10
MAX_CITATION_CHARS = 2_000
MAX_TOTAL_CITATION_CHARS = 12_000
MIN_CITATION_CHARS = 10

_TRUSTED_CITATION_TOOLS = {
    "knowledge_retrieve",
    "kb_cat",
    "kb_grep",
    "semantic_search",
}
_LEGACY_REFERENCES_PATTERN = re.compile(
    r"\s*<references\b\s+"
    r"title\s*=\s*([\"'])References\1\s+"
    r"references\s*=\s*([\"'])[\s\S]*?</references\s*>\s*$",
    flags=re.IGNORECASE,
)
_SEMANTIC_RESULT_PATTERN = re.compile(
    r"(?:^|\n)---\s*\n"
    r"###\s+Result\s+\d+"
    r"(?:\s+\(score:\s*([^\)]+)\))?"
    r"\s+\[([^\]\n]*)\]\s*\n"
    r"([\s\S]*?)"
    r"(?=\n---\s*\n###\s+Result\s+\d+|\Z)",
    flags=re.IGNORECASE,
)
_GREP_FILE_PATTERN = re.compile(r"(?m)^(\S[^\r\n]*):\r?\n(?=[ \t]+\d+:\s)")
_NUMBERED_CHUNK_PATTERN = re.compile(r"(?m)^\[(\d+)\]\s*")


@dataclass(frozen=True)
class AgentCitation:
    """One knowledge source cited by a final answer."""

    index: int
    id: str
    source_name: str
    excerpt: str
    score: Optional[float] = None
    path: Optional[str] = None
    url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the citation using the version 2 wire field names."""
        return {
            "index": self.index,
            "id": self.id,
            "sourceName": self.source_name,
            "excerpt": self.excerpt,
            "score": self.score,
            "path": self.path,
            "url": self.url,
        }


@dataclass(frozen=True)
class AgentFinalAnswer:
    """Pure final content plus independently rendered citations."""

    content: str
    citations: Tuple[AgentCitation, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize fields shared by SSE and conversation history."""
        return {
            "content": self.content,
            "citations": [citation.to_dict() for citation in self.citations],
        }

    def to_sse_payload(self) -> Dict[str, Any]:
        """Serialize a complete version 2 final SSE event."""
        return {
            "type": "final",
            "protocol_version": FINAL_PROTOCOL_VERSION,
            **self.to_dict(),
        }


@dataclass(frozen=True)
class _CitationDraft:
    source_name: str
    excerpt: str
    citation_id: Optional[str] = None
    score: Optional[float] = None
    path: Optional[str] = None
    url: Optional[str] = None


def strip_legacy_references(content: Any) -> str:
    """Remove one well-formed legacy references block at the end of content.

    Only a trailing, closed block is removed. Text that merely discusses the
    ``<references>`` syntax is left untouched.
    """
    text = content if isinstance(content, str) else str(content or "")
    return _LEGACY_REFERENCES_PATTERN.sub("", text).rstrip()


class FinalAnswerAssembler:
    """Collect citations from an allowlist of knowledge-producing tools.

    Tool output is not a citation by default. Each trusted tool has an explicit
    adapter for its known output shape; malformed or failed output is ignored.
    """

    def __init__(self) -> None:
        self._drafts: List[_CitationDraft] = []
        self._deduplication_keys: set[Tuple[str, str, str]] = set()
        self._total_excerpt_chars = 0

    def observe(
        self,
        tool_name: Any,
        action_input: Any,
        observation: Any,
        succeeded: bool = True,
    ) -> None:
        """Observe one tool result and collect citations when explicitly safe."""
        if not succeeded or not isinstance(tool_name, str):
            return
        normalized_name = tool_name.strip().lower()
        if normalized_name not in _TRUSTED_CITATION_TOOLS:
            return

        try:
            parsed_input = _parse_action_input(action_input, normalized_name)
        except (json.JSONDecodeError, TypeError, ValueError):
            return
        if parsed_input is None:
            return

        adapters = {
            "knowledge_retrieve": _adapt_knowledge_retrieve,
            "kb_cat": _adapt_kb_cat,
            "kb_grep": _adapt_kb_grep,
            "semantic_search": _adapt_semantic_search,
        }
        try:
            drafts = adapters[normalized_name](parsed_input, observation)
        except (AttributeError, json.JSONDecodeError, TypeError, ValueError):
            return
        for draft in drafts:
            self._append(draft)

    def finalize(self, content: Any) -> AgentFinalAnswer:
        """Build a final answer whose content never contains legacy metadata."""
        citations = tuple(
            AgentCitation(
                index=index,
                id=draft.citation_id or _stable_citation_id(draft),
                source_name=draft.source_name,
                excerpt=draft.excerpt,
                score=draft.score,
                path=draft.path,
                url=draft.url,
            )
            for index, draft in enumerate(self._drafts, start=1)
        )
        return AgentFinalAnswer(
            content=strip_legacy_references(content),
            citations=citations,
        )

    def _append(self, draft: _CitationDraft) -> None:
        if len(self._drafts) >= MAX_CITATIONS:
            return

        source_name = _clean_metadata(draft.source_name, 300)
        citation_id = _clean_metadata(draft.citation_id, 300) or None
        path = _clean_metadata(draft.path, 500) or None
        url = _clean_metadata(draft.url, 2_000) or None
        excerpt = _clean_excerpt(draft.excerpt)
        if not source_name or len(excerpt) < MIN_CITATION_CHARS:
            return

        remaining = MAX_TOTAL_CITATION_CHARS - self._total_excerpt_chars
        if remaining < MIN_CITATION_CHARS:
            return
        excerpt = excerpt[: min(MAX_CITATION_CHARS, remaining)].rstrip()
        if len(excerpt) < MIN_CITATION_CHARS:
            return

        key = (source_name, path or "", excerpt)
        if key in self._deduplication_keys:
            return
        self._deduplication_keys.add(key)
        self._drafts.append(
            _CitationDraft(
                source_name=source_name,
                excerpt=excerpt,
                citation_id=citation_id,
                score=_coerce_score(draft.score),
                path=path,
                url=url,
            )
        )
        self._total_excerpt_chars += len(excerpt)


def _parse_action_input(action_input: Any, tool_name: str) -> Optional[Dict[str, Any]]:
    if isinstance(action_input, dict):
        return action_input
    if isinstance(action_input, str):
        try:
            parsed = json.loads(action_input)
        except json.JSONDecodeError:
            parsed = action_input
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, str) and parsed.strip():
            primary_keys = {
                "knowledge_retrieve": "query",
                "kb_cat": "path",
                "kb_grep": "query",
                "semantic_search": "query",
            }
            primary_key = primary_keys.get(tool_name)
            return {primary_key: parsed.strip()} if primary_key else None
        return None
    return {} if action_input is None else None


def _adapt_knowledge_retrieve(
    action_input: Dict[str, Any], observation: Any
) -> List[_CitationDraft]:
    del action_input
    parsed = json.loads(observation) if isinstance(observation, str) else observation
    if not isinstance(parsed, dict):
        return []

    explicit_citations = parsed.get("citations")
    if "citations" in parsed:
        if not isinstance(explicit_citations, list):
            return []
        excerpt_by_index: Dict[int, str] = {}
        chunks = parsed.get("chunks")
        if isinstance(chunks, list):
            for chunk in chunks:
                if not isinstance(chunk, dict):
                    continue
                content = chunk.get("content")
                if not isinstance(content, str) or _is_retrieval_status(content):
                    continue
                for index, excerpt in _split_numbered_chunks_by_index(content).items():
                    excerpt_by_index.setdefault(index, excerpt)
        return _adapt_explicit_citations(explicit_citations, excerpt_by_index)

    if not isinstance(parsed.get("chunks"), list):
        return []

    drafts: List[_CitationDraft] = []
    for item in parsed["chunks"]:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if not isinstance(content, str) or _is_retrieval_status(content):
            continue
        metadata = (
            item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        )
        path = item.get("path") or metadata.get("file_path") or metadata.get("path")
        source_name = (
            item.get("sourceName")
            or item.get("source_name")
            or item.get("document_name")
            or path
            or "Knowledge Base"
        )
        score = item.get("score", item.get("recall_score"))
        url = item.get("url") or metadata.get("url")
        for excerpt in _split_numbered_chunks(content):
            drafts.append(
                _CitationDraft(
                    source_name=str(source_name),
                    excerpt=excerpt,
                    score=score,
                    path=str(path) if path else None,
                    url=str(url) if url else None,
                )
            )
    return drafts


def _adapt_explicit_citations(
    citations: List[Any], excerpt_by_index: Optional[Dict[int, str]] = None
) -> List[_CitationDraft]:
    drafts: List[_CitationDraft] = []
    for item in citations:
        if not isinstance(item, dict):
            continue
        metadata = (
            item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        )
        excerpt = item.get("excerpt", item.get("content"))
        if not isinstance(excerpt, str) and excerpt_by_index:
            chunk_index = item.get("chunkIndex", item.get("chunk_index"))
            try:
                excerpt = excerpt_by_index.get(int(chunk_index))
            except (TypeError, ValueError):
                excerpt = None
        path = (
            item.get("path")
            or item.get("file_path")
            or metadata.get("file_path")
            or metadata.get("path")
        )
        source_name = (
            item.get("sourceName")
            or item.get("source_name")
            or item.get("document_name")
            or path
        )
        if not isinstance(excerpt, str) or not source_name:
            continue
        raw_id = item.get("id", item.get("chunk_id"))
        raw_url = item.get("url") or metadata.get("url")
        drafts.append(
            _CitationDraft(
                source_name=str(source_name),
                excerpt=excerpt,
                citation_id=str(raw_id) if raw_id is not None else None,
                score=item.get("score", item.get("recall_score")),
                path=str(path) if path else None,
                url=str(raw_url) if raw_url else None,
            )
        )
    return drafts


def _adapt_kb_cat(
    action_input: Dict[str, Any], observation: Any
) -> List[_CitationDraft]:
    path = action_input.get("path")
    if (
        not isinstance(path, str)
        or not path.strip()
        or not isinstance(observation, str)
    ):
        return []
    path = path.strip()
    text = observation.strip()
    lowered = text.casefold()
    if lowered.startswith("file '") and (
        " not found" in lowered or " is empty" in lowered
    ):
        return []
    if not text.startswith(f"{path} ("):
        return []
    return [_CitationDraft(source_name=path, excerpt=text, path=path)]


def _adapt_kb_grep(
    action_input: Dict[str, Any], observation: Any
) -> List[_CitationDraft]:
    query = action_input.get("query")
    if (
        not isinstance(query, str)
        or not query.strip()
        or not isinstance(observation, str)
    ):
        return []
    text = observation.strip()
    lowered = text.casefold()
    failure_prefixes = (
        "no files in knowledge space",
        "no files in scope",
        "no content matching",
    )
    if lowered.startswith(failure_prefixes):
        return []

    matches = list(_GREP_FILE_PATTERN.finditer(text))
    drafts: List[_CitationDraft] = []
    for position, match in enumerate(matches):
        path = match.group(1).strip()
        end = (
            matches[position + 1].start() if position + 1 < len(matches) else len(text)
        )
        excerpt = text[match.end() : end].strip()
        if path and excerpt:
            drafts.append(
                _CitationDraft(
                    source_name=path,
                    excerpt=excerpt,
                    path=path,
                )
            )
    return drafts


def _adapt_semantic_search(
    action_input: Dict[str, Any], observation: Any
) -> List[_CitationDraft]:
    query = action_input.get("query")
    if (
        not isinstance(query, str)
        or not query.strip()
        or not isinstance(observation, str)
    ):
        return []
    text = observation.strip()
    lowered = text.casefold()
    failure_prefixes = (
        "semantic search service unavailable",
        "semantic search failed",
        "knowledge space ",
        "no results for",
    )
    if lowered.startswith(failure_prefixes):
        return []

    drafts: List[_CitationDraft] = []
    for match in _SEMANTIC_RESULT_PATTERN.finditer(text):
        score_text, path, excerpt = match.groups()
        path = path.strip()
        excerpt = excerpt.strip()
        if excerpt:
            drafts.append(
                _CitationDraft(
                    source_name=path or "Knowledge Base",
                    excerpt=excerpt,
                    score=_coerce_score(score_text),
                    path=path or None,
                )
            )
    return drafts


def _split_numbered_chunks(content: str) -> List[str]:
    indexed_chunks = _split_numbered_chunks_by_index(content)
    if indexed_chunks:
        return list(indexed_chunks.values())
    cleaned = content.strip()
    return [cleaned] if cleaned else []


def _split_numbered_chunks_by_index(content: str) -> Dict[int, str]:
    """Split numbered excerpts without renumbering sparse or empty chunks."""
    matches = list(_NUMBERED_CHUNK_PATTERN.finditer(content))
    if not matches:
        return {}
    chunks: Dict[int, str] = {}
    for position, match in enumerate(matches):
        end = (
            matches[position + 1].start()
            if position + 1 < len(matches)
            else len(content)
        )
        excerpt = content[match.end() : end].strip()
        if excerpt:
            chunks.setdefault(int(match.group(1)), excerpt)
    return chunks


def _is_retrieval_status(content: str) -> bool:
    lowered = content.strip().casefold()
    return lowered.startswith(
        (
            "retrieved ",
            "no knowledge base available",
            "no relevant information found",
            "knowledge retrieval failed",
        )
    )


def _clean_excerpt(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.replace("\x00", "").strip()


def _clean_metadata(value: Any, max_chars: int) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value.replace("\x00", "")).strip()[:max_chars]


def _coerce_score(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    return score if math.isfinite(score) else None


def _stable_citation_id(draft: _CitationDraft) -> str:
    identity = "\x1f".join(
        (draft.source_name, draft.path or "", draft.url or "", draft.excerpt)
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
    return f"citation-{digest}"
