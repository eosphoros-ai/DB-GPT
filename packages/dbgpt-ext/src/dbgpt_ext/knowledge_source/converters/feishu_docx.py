"""Feishu docx blocks → Markdown.

P0 coverage: page/text/heading1-9/bullet/ordered/code/quote/todo/divider/
callout render as Markdown; table (31) renders as a Markdown table from its
cell blocks; image (32) renders as a placeholder link; unknown types degrade
to extracted text runs.

`elements` extraction tolerates the attr-key differences across block types
by probing the well-known keys (`text`, `heading1..9`, `bullet`, `ordered`,
`code`, `quote`, `todo`, `callout`).
"""

from __future__ import annotations

from typing import Dict, List, Optional

_HEADING = {
    3: ("heading1", "# "),
    4: ("heading2", "## "),
    5: ("heading3", "### "),
    6: ("heading4", "#### "),
    7: ("heading5", "##### "),
    8: ("heading6", "###### "),
    9: ("heading7", "###### "),
    10: ("heading8", "###### "),
    11: ("heading9", "###### "),
}
_TEXTY = (
    "text",
    "heading1",
    "heading2",
    "heading3",
    "heading4",
    "heading5",
    "heading6",
    "heading7",
    "heading8",
    "heading9",
    "bullet",
    "ordered",
    "code",
    "quote",
    "todo",
    "callout",
)


def _elements_text(block: Dict) -> str:
    """Concat text_run contents from whichever attr key this block carries."""
    for key in _TEXTY:
        attr = block.get(key)
        if isinstance(attr, dict):
            parts = []
            for el in attr.get("elements", []) or []:
                tr = el.get("text_run")
                if tr:
                    parts.append(tr.get("content", "") or "")
            text = "".join(parts)
            if text:
                return text
    return ""


def _table_cells(blocks_by_id: Dict[str, Dict], table_block: Dict) -> List[List[str]]:
    cells = (table_block.get("table") or {}).get("cells", []) or []
    rows: List[List[str]] = []
    for cell_id in cells:
        cell = blocks_by_id.get(cell_id) or {}
        # cell body may live on the cell block itself and/or its children
        lines: List[str] = []
        own = _elements_text(cell)
        if own:
            lines.append(own)
        for child_id in cell.get("children", []) or []:
            child = blocks_by_id.get(child_id)
            if child:
                text = _elements_text(child)
                if text:
                    lines.append(text)
        rows.append([" ".join(lines) or " "])
    return rows


def _cells_to_rows(cells: List[List[str]], col_size: int) -> List[List[str]]:
    """Feishu returns cell ids column-wise? Empirically it returns them
    row-wise in reading order; we chunk defensively by reported col_size."""
    if col_size <= 0:
        return [[c[0] for c in cells]] if cells else []
    rows = []
    for i in range(0, len(cells), col_size):
        rows.append([c[0] for c in cells[i : i + col_size]])
    return rows


def _render_table(rows: List[List[str]]) -> str:
    if not rows:
        return ""
    width = max((len(r) for r in rows), default=1) or 1
    norm = [(r + [" "] * width)[:width] for r in rows]
    header, body = norm[0], norm[1:]
    out = ["| " + " | ".join(header) + " |", "| " + " | ".join(["---"] * width) + " |"]
    for r in body:
        out.append("| " + " | ".join(r) + " |")
    return "\n".join(out)


def feishu_blocks_to_markdown(blocks: List[Dict]) -> str:
    blocks_by_id: Dict[str, Dict] = {b.get("block_id", ""): b for b in blocks}
    lines: List[str] = []
    ordered_queue: int = 0
    page_child_ids: Optional[List[str]] = None
    for block in blocks:
        bt = int(block.get("block_type", 0) or 0)
        if bt == 1:  # page block: iterate its children in order
            page_child_ids = block.get("children", []) or []
            break
    iterator = (
        [blocks_by_id[i] for i in page_child_ids if i in blocks_by_id]
        if page_child_ids
        else blocks
    )

    def walk(node_list: List[Dict]) -> None:
        nonlocal ordered_queue
        for b in node_list:
            bt = int(b.get("block_type", 0) or 0)
            text = _elements_text(b)
            if bt == 1:
                continue  # page
            if bt in _HEADING:
                ordered_queue = 0
                _, prefix = _HEADING[bt]
                lines.append(f"\n{prefix}{text}\n")
            elif bt == 12:  # bullet
                ordered_queue = 0
                lines.append(f"- {text}")
            elif bt == 13:  # ordered
                ordered_queue += 1
                lines.append(f"{ordered_queue}. {text}")
            elif bt == 14:  # code
                ordered_queue = 0
                lines.append(f"```\n{text}\n```")
            elif bt == 15:  # quote
                ordered_queue = 0
                lines.append(f"> {text}")
            elif bt == 17:  # todo
                ordered_queue = 0
                mark = (
                    "x" if (b.get("todo") or {}).get("style", {}).get("done") else " "
                )
                lines.append(f"- [{mark}] {text}")
            elif bt == 22:  # divider
                ordered_queue = 0
                lines.append("\n---\n")
            elif bt == 19:  # callout: render children text
                ordered_queue = 0
                inner = []
                for cid in b.get("children", []) or []:
                    cb = blocks_by_id.get(cid)
                    if cb:
                        inner.append(_elements_text(cb))
                lines.append("> [!NOTE]\n> " + "\n> ".join(filter(None, inner)))
            elif bt == 31:  # table
                ordered_queue = 0
                table = b.get("table") or {}
                cells = _table_cells(blocks_by_id, b)
                col_size = int((table.get("property") or {}).get("col_size", 0) or 0)
                lines.append(
                    "\n" + _render_table(_cells_to_rows(cells, col_size)) + "\n"
                )
            elif bt == 32:  # image
                ordered_queue = 0
                lines.append("![image](feishu-image-placeholder)")
            elif bt == 2:  # plain text／paragraph
                ordered_queue = 0
                lines.append(text)
            else:
                if text:
                    lines.append(text)
            if bt not in (31, 1):
                child_ids = b.get("children", []) or []
                child_blocks = [blocks_by_id[c] for c in child_ids if c in blocks_by_id]
                if child_blocks and bt not in (14,):
                    walk(child_blocks)

    walk(iterator)
    return "\n".join(lines).replace("\n\n\n\n", "\n\n").strip() + "\n"
