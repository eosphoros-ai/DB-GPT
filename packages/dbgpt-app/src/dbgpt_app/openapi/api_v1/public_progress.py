"""Ordered, public assistant narration shared by the chat engines."""

import re
from typing import Any, Dict, List, Optional

_REACT_FIELDS = (
    "Thought",
    "Action Intention",
    "Action Reason",
    "Action Input",
    "Action",
    "Observation",
    "Phase",
)
_REACT_FIELD = re.compile(
    r"^[ \t]*(?:[-*][ \t]+)?(?:\*\*)?"
    r"(" + "|".join(_REACT_FIELDS) + r")(?:\*\*)?[ \t]*[:：][ \t]*\*{0,2}[ \t]*",
    re.IGNORECASE | re.MULTILINE,
)


def public_assistant_text(text: str, *, streaming: bool = False) -> str:
    """Keep ordinary narration and explicit intentions, never ReAct internals.

    Native providers can still emit text-protocol fields in their text channel.
    Withhold split field names before publishing them, rather than briefly
    displaying a private field and removing it when the colon arrives.
    """
    if streaming:
        last_line = text.rsplit("\n", 1)[-1]
        candidate = re.sub(r"^[ \t]*(?:[-*][ \t]+)?(?:\*\*)?", "", last_line)
        candidate = candidate.strip().lower()
        if last_line.strip() in ("*", "**") or (
            candidate
            and any(
                field.lower().startswith(candidate) or candidate == field.lower() + "**"
                for field in _REACT_FIELDS
            )
        ):
            text = text[: len(text) - len(last_line)]
    fields = list(_REACT_FIELD.finditer(text))
    if not fields:
        return text
    parts = [text[: fields[0].start()].rstrip()]
    for index, field in enumerate(fields):
        if field.group(1).lower() != "action intention":
            continue
        end = fields[index + 1].start() if index + 1 < len(fields) else len(text)
        intention = text[field.end() : end].split("\n", 1)[0].rstrip("\r")
        if intention.strip():
            parts.append(intention)
    return "\n".join(part for part in parts if part)


class PublicProgressStream:
    """Upsert snapshots in place so live deltas and history share identities."""

    def __init__(self, history_steps: List[Dict[str, Any]]) -> None:
        self.history_steps = history_steps
        self.records: Dict[int, Dict[str, Any]] = {}

    def update(
        self,
        round_no: int,
        content: str,
        *,
        streaming: bool,
        before_step_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        content = public_assistant_text(content, streaming=streaming)
        if not content.strip():
            return None
        record = self.records.get(round_no)
        if record is None:
            record = {
                "id": f"progress-{round_no}",
                "action": "__progress__",
                "outputs": [],
            }
            self.records[round_no] = record
            self.history_steps.append(record)
        record.update(
            progress_content=content, status="running" if streaming else "done"
        )
        return {
            "type": "progress",
            "id": record["id"],
            "content": content,
            "streaming": streaming,
            "before_step_id": before_step_id,
        }

    def remove(self, round_no: int) -> Optional[Dict[str, Any]]:
        record = self.records.pop(round_no, None)
        if record is None:
            return None
        self.history_steps.remove(record)
        return {"type": "progress.remove", "id": record["id"]}

    def finish_all(self) -> List[Dict[str, Any]]:
        events = []
        for round_no, record in self.records.items():
            if record.get("status") == "running":
                event = self.update(
                    round_no, record["progress_content"], streaming=False
                )
                if event:
                    events.append(event)
        return events


def react_public_intention(text: str) -> str:
    """Extract only the explicitly public ReAct field, including partial text."""
    marker = re.search(r"(?:^|\n)Action Intention:[ \t]*", text)
    if marker is None:
        return ""
    content = text[marker.end() :]
    # ReAct fields occupy separate lines. Withhold an unfinished next field
    # so split tokens such as "\nAction Re" cannot leak into public narration.
    return content.split("\n", 1)[0].rstrip("\r")
