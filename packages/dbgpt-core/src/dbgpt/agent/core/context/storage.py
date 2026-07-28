"""Tool result persistence — saves oversized outputs to filesystem with preview + path.

Ported from hermes-agent's ``tools/tool_result_storage.py`` and adapted for DB-GPT's
agent architecture.

Storage layout::

    {output_dir}/
    +-- op_snapshots/          <-- existing operation snapshots
    |   +-- {conv_id}/
    |       +-- step_001_sql_query.json
    |       +-- step_002_kb_grep.json
    +-- persisted_results/     <-- NEW: persisted tool results
        +-- {conv_id}/
            +-- sql_query_d4e5f6.txt
            +-- kb_grep_a1b2c3.txt

The ``<persisted-output>`` block that replaces the in-context content looks like::

    <persisted-output>
    This tool result was too large (50,000 characters, 48.8 KB).
    Full output saved to: ~/.dbgpt/workspace/persisted_results/conv_abc/kb_grep_x.txt
    Use the read_file tool with this file path to access specific sections.

    Preview (first 1500 chars):
    ...preview content...
    ...
    </persisted-output>

Defense against context-window overflow operates at three levels:

1. **Per-tool output cap** (inside each tool): Tools like ``sql_query``,
   ``kb_cat`` pre-truncate their own output before returning. This is the
   first line of defense and the only one the tool author controls.

2. **Per-result persistence** (``maybe_persist``): After a tool returns,
   if its output exceeds the tool's registered threshold, the full output
   is written to the ``persisted_results/`` directory. The in-context
   content is replaced with a preview + file path reference. The model
   can use ``read_file`` to access the full output on any backend.

3. **Per-turn aggregate budget** (``enforce_turn_budget``): After all tool
   results in a single assistant turn are collected, if the total exceeds
   ``turn_result_budget`` (default 200K), the largest non-persisted results
   are spilled to disk until the aggregate is under budget.
"""

from __future__ import annotations

import contextvars
import hashlib
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Context var holding the active ToolResultStorage for the current agent run.
# Set by ConversableAgent.act() / ReActAgent before tool execution so that
# the standalone run_tool() function can access it without a signature change.
_current_storage: "contextvars.ContextVar[Optional[ToolResultStorage]]" = (
    contextvars.ContextVar("dbgpt_tool_result_storage", default=None)
)


def set_current_storage(storage: Optional["ToolResultStorage"]) -> None:
    """Bind a ToolResultStorage to the current async context.

    Called by the agent before tool execution so ``run_tool`` can pick it up.
    """
    _current_storage.set(storage)


def get_current_storage() -> Optional["ToolResultStorage"]:
    """Return the ToolResultStorage bound to the current async context, if any."""
    return _current_storage.get()


PERSISTED_OUTPUT_TAG = "<persisted-output>"
PERSISTED_OUTPUT_CLOSING_TAG = "</persisted-output>"

# Characters that are unsafe in filenames (kept simple for cross-platform compat).
_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9_.\-]+")
_MAX_FILENAME_STEM = 120

# ---------------------------------------------------------------------------
# Budget configuration
# ---------------------------------------------------------------------------

# Tools whose thresholds must never be overridden.
# read_file=inf prevents infinite persist->read->persist loops.
PINNED_THRESHOLDS: Dict[str, float] = {
    "read_file": float("inf"),
}

# Default thresholds matching hermes-agent's values.
DEFAULT_RESULT_SIZE_CHARS: int = 100_000
DEFAULT_TURN_BUDGET_CHARS: int = 200_000
DEFAULT_PREVIEW_SIZE_CHARS: int = 1_500


@dataclass(frozen=True)
class ToolResultBudgetConfig:
    """Immutable budget constants for the 3-layer tool result persistence system.

    Layer 2 (per-result): ``resolve_threshold(tool_name)`` -> threshold in chars.
    Layer 3 (per-turn):   ``turn_budget`` -> aggregate char budget across all tool
                          results in a single assistant turn.
    Preview:              ``preview_size`` -> inline snippet size after persistence.
    """

    default_result_size: int = DEFAULT_RESULT_SIZE_CHARS
    turn_budget: int = DEFAULT_TURN_BUDGET_CHARS
    preview_size: int = DEFAULT_PREVIEW_SIZE_CHARS
    tool_overrides: Dict[str, int] = field(default_factory=dict)

    def resolve_threshold(self, tool_name: str) -> int | float:
        """Resolve the persistence threshold for a tool.

        Priority: pinned -> tool_overrides -> default.
        """
        if tool_name in PINNED_THRESHOLDS:
            return PINNED_THRESHOLDS[tool_name]
        if tool_name in self.tool_overrides:
            return self.tool_overrides[tool_name]
        return self.default_result_size


# Default config -- matches current hardcoded behavior exactly.
DEFAULT_TOOL_RESULT_BUDGET = ToolResultBudgetConfig()

# ---------------------------------------------------------------------------
# Token<->char conversion used when scaling the budget to a model's context
# window. Deliberately conservative (4 chars/token).
_CHARS_PER_TOKEN: int = 4

# Fraction of a model's context window we allow a SINGLE tool result to occupy
# before persisting/truncating it, and the fraction the WHOLE turn's tool output
# may occupy.
_PER_RESULT_WINDOW_FRACTION: float = 0.15
_PER_TURN_WINDOW_FRACTION: float = 0.30

# Floor so even a tiny-but-admitted model still gets a usable preview/result.
_MIN_RESULT_SIZE_CHARS: int = 8_000
_MIN_TURN_BUDGET_CHARS: int = 16_000


def tool_result_budget_for_context_window(
    context_length: int | None,
) -> ToolResultBudgetConfig:
    """Return a ``ToolResultBudgetConfig`` scaled to the active model's context window.

    The fixed defaults (100K result / 200K turn chars) are correct for large
    (200K+ token) models but blind to small ones: on a 65K-token model a single
    tool result persisted at the 100K-char threshold can by itself approach or
    exceed the whole window.

    Scaling keeps large models byte-identical to today (the proportional value
    is clamped to the existing defaults as a CAP) while shrinking the budget for
    small models proportionally to their window, floored so a usable preview
    always survives.
    """
    if not context_length or context_length <= 0:
        return DEFAULT_TOOL_RESULT_BUDGET

    window_chars = context_length * _CHARS_PER_TOKEN
    per_result = int(window_chars * _PER_RESULT_WINDOW_FRACTION)
    per_turn = int(window_chars * _PER_TURN_WINDOW_FRACTION)

    # Clamp: never exceed the historical defaults (so large models are
    # unchanged), never drop below the floor (so tiny models stay usable).
    per_result = max(_MIN_RESULT_SIZE_CHARS, min(per_result, DEFAULT_RESULT_SIZE_CHARS))
    per_turn = max(_MIN_TURN_BUDGET_CHARS, min(per_turn, DEFAULT_TURN_BUDGET_CHARS))

    return ToolResultBudgetConfig(
        default_result_size=per_result,
        turn_budget=per_turn,
        preview_size=DEFAULT_PREVIEW_SIZE_CHARS,
    )


# ---------------------------------------------------------------------------
# Core storage class
# ---------------------------------------------------------------------------


def _safe_filename(tool_use_id: str) -> str:
    """Return a single safe filename for a tool result id."""
    raw_id = str(tool_use_id or "tool_result")
    safe_stem = _UNSAFE_FILENAME_CHARS.sub("_", raw_id).strip("._-")
    changed = safe_stem != raw_id

    if not safe_stem:
        safe_stem = "tool_result"
        changed = True

    if changed or len(safe_stem) > _MAX_FILENAME_STEM:
        digest = hashlib.sha256(raw_id.encode("utf-8")).hexdigest()[:12]
        safe_stem = safe_stem[:_MAX_FILENAME_STEM].rstrip("._-") or "tool_result"
        safe_stem = f"{safe_stem}_{digest}"

    return f"{safe_stem}.txt"


def generate_preview(
    content: str, max_chars: int = DEFAULT_PREVIEW_SIZE_CHARS
) -> Tuple[str, bool]:
    """Truncate at last newline within *max_chars*. Returns (preview, has_more)."""
    if len(content) <= max_chars:
        return content, False
    truncated = content[:max_chars]
    last_nl = truncated.rfind("\n")
    if last_nl > max_chars // 2:
        truncated = truncated[: last_nl + 1]
    return truncated, True


def _build_persisted_message(
    preview: str,
    has_more: bool,
    original_size: int,
    file_path: str,
) -> str:
    """Build the ``<persisted-output>`` replacement block."""
    size_kb = original_size / 1024
    if size_kb >= 1024:
        size_str = f"{size_kb / 1024:.1f} MB"
    else:
        size_str = f"{size_kb:.1f} KB"

    msg = f"{PERSISTED_OUTPUT_TAG}\n"
    msg += (
        f"This tool result was too large ({original_size:,} characters, {size_str}).\n"
    )
    msg += f"Full output saved to: {file_path}\n"
    msg += "Use the read_file tool with this file path to access specific sections.\n\n"
    msg += f"Preview (first {len(preview)} chars):\n"
    msg += preview
    if has_more:
        msg += "\n..."
    msg += f"\n{PERSISTED_OUTPUT_CLOSING_TAG}"
    return msg


class ToolResultStorage:
    """Persist large tool results to disk, replace in-context with preview + path.

    Usage::

        storage = ToolResultStorage(
            storage_dir="/path/to/persisted_results/conv_abc",
            default_threshold=100_000,
            preview_size=1500,
        )
        replacement, path = storage.maybe_persist(
            content=tool_output,
            tool_name="sql_query",
            tool_call_id="sql_query_abc123",
        )
        if path:
            # Content was persisted; *replacement* has the <persisted-output> block.
            action_output.content = replacement
            action_output.persisted_path = path
    """

    def __init__(
        self,
        storage_dir: str,
        default_threshold: int = DEFAULT_RESULT_SIZE_CHARS,
        preview_size: int = DEFAULT_PREVIEW_SIZE_CHARS,
        tool_overrides: Optional[Dict[str, int]] = None,
        pinned_thresholds: Optional[Dict[str, float]] = None,
        config: Optional[ToolResultBudgetConfig] = None,
    ):
        self.storage_dir = storage_dir
        self.preview_size = preview_size
        if config is not None:
            self._config = config
        else:
            self._config = ToolResultBudgetConfig(
                default_result_size=default_threshold,
                preview_size=preview_size,
                tool_overrides=tool_overrides or {},
            )
        # Merge pinned thresholds (caller can add extra pinned tools).
        self._pinned = dict(PINNED_THRESHOLDS)
        if pinned_thresholds:
            self._pinned.update(pinned_thresholds)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def resolve_threshold(self, tool_name: str) -> int | float:
        """Resolve the persistence threshold for a tool.

        Priority: pinned -> tool_overrides -> default.
        """
        if tool_name in self._pinned:
            return self._pinned[tool_name]
        return self._config.resolve_threshold(tool_name)

    def maybe_persist(
        self,
        content: str,
        tool_name: str,
        tool_call_id: str,
        threshold: Optional[int] = None,
    ) -> Tuple[str, Optional[str]]:
        """Layer 2: persist oversized result into the storage dir, return preview.

        Writes the full content to ``{storage_dir}/{safe_filename}.txt`` and
        returns a ``<persisted-output>`` replacement block. Falls back to inline
        truncation if the write fails.

        Args:
            content: Raw tool result string.
            tool_name: Name of the tool (used for threshold lookup).
            tool_call_id: Unique ID for this tool call (used as filename stem).
            threshold: Explicit override; takes precedence over config resolution.

        Returns:
            Tuple of (replacement_content, persisted_file_path_or_None).
            If the content is under threshold, returns (content, None).
        """
        effective_threshold = (
            threshold if threshold is not None else self.resolve_threshold(tool_name)
        )

        if effective_threshold == float("inf"):
            return content, None

        if len(content) <= effective_threshold:
            return content, None

        # Write to disk.
        try:
            os.makedirs(self.storage_dir, exist_ok=True)
        except OSError:
            logger.warning(
                "Could not create storage dir %s; falling back to inline truncation",
                self.storage_dir,
            )
            preview, _ = generate_preview(content, self.preview_size)
            return (
                f"{preview}\n\n"
                f"[Truncated: tool response was {len(content):,} chars. "
                f"Full output could not be saved to disk.]"
            ), None

        filename = _safe_filename(tool_call_id)
        filepath = os.path.join(self.storage_dir, filename)
        preview, has_more = generate_preview(content, self.preview_size)

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(
                "Persisted large tool result: %s (%s, %d chars -> %s)",
                tool_name,
                tool_call_id,
                len(content),
                filepath,
            )
            return (
                _build_persisted_message(preview, has_more, len(content), filepath),
                filepath,
            )
        except OSError:
            logger.warning(
                "Failed to write persisted result for %s: disk write error",
                tool_name,
            )
            return (
                f"{preview}\n\n"
                f"[Truncated: tool response was {len(content):,} chars. "
                f"Full output could not be saved to disk.]"
            ), None

    def enforce_turn_budget(
        self,
        results: List[Tuple[str, str, str]],
        budget: Optional[int] = None,
    ) -> List[Tuple[str, Optional[str]]]:
        """Layer 3: enforce aggregate budget across all tool results in a turn.

        If total chars exceed budget, persist the largest non-persisted results
        first (via disk write) until under budget. Already-persisted results
        (those containing ``<persisted-output>``) are skipped.

        Args:
            results: List of (content, tool_name, tool_call_id) tuples.
            budget: Aggregate char budget. Defaults to ``config.turn_budget``.

        Returns:
            List of (replacement_content, persisted_file_path_or_None) tuples.
        """
        if budget is None:
            budget = self._config.turn_budget

        total_size = sum(len(content) for content, _, _ in results)
        if total_size <= budget:
            return [(content, None) for content, _, _ in results]

        # Identify candidates (non-persisted, sorted by size descending).
        candidates: List[Tuple[int, int]] = []  # (index, size)
        for i, (content, _, _) in enumerate(results):
            if PERSISTED_OUTPUT_TAG not in content:
                candidates.append((i, len(content)))

        candidates.sort(key=lambda x: x[1], reverse=True)

        # Build output list (mutable copy).
        output: List[Tuple[str, Optional[str]]] = [
            (content, None) for content, _, _ in results
        ]

        for idx, size in candidates:
            if total_size <= budget:
                break
            content, tool_name, call_id = results[idx]
            replacement, path = self.maybe_persist(
                content=content,
                tool_name=tool_name,
                tool_call_id=call_id,
                threshold=0,  # Force persist (budget enforcement).
            )
            if replacement != content:
                total_size -= size
                total_size += len(replacement)
                output[idx] = (replacement, path)
                logger.info(
                    "Budget enforcement: persisted tool result %s (%d chars)",
                    call_id,
                    size,
                )

        return output

    def read_persisted(self, file_path: str) -> Optional[str]:
        """Read back a persisted result from disk.

        Args:
            file_path: Absolute path to the persisted file.

        Returns:
            The file content, or None if the file does not exist or cannot be read.
        """
        # Security: only allow reading from the storage directory.
        try:
            real_path = os.path.realpath(file_path)
            real_storage = os.path.realpath(self.storage_dir)
            if not real_path.startswith(real_storage):
                logger.warning(
                    "read_persisted: path %s is outside storage dir %s",
                    file_path,
                    self.storage_dir,
                )
                return None
        except Exception:
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except OSError:
            logger.warning("read_persisted: could not read %s", file_path)
            return None
