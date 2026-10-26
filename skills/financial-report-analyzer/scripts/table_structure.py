"""Recover logical columns from PDF cells without shifting blank amounts.

PDF rectangle edges can split padding into phantom columns. Numeric cell bounds,
not pdfplumber's global grid indexes, define the logical amount columns. Original
cells remain available for auditing. Ambiguous overlapping layouts are rejected.
"""

import re


def compact(value):
    return re.sub(r"\s+", "", value or "")


def _number(value):
    value = compact(value).replace("，", ",").replace("−", "-").replace("－", "-")
    return value in {"-", "--", "—", "–"} or bool(
        re.fullmatch(r"[（(]?[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?[%）)]?", value)
    )


def _overlap(a, b):
    return max(0, min(a[1], b[1]) - max(a[0], b[0]))


def structure_table(rows, boxes, bbox):
    """Return logical rows, x bounds and references to every original cell."""
    intervals = []
    for row, row_boxes in zip(rows, boxes):
        for text, box in zip(row, row_boxes):
            if box and _number(text):
                interval = (box[0], box[2])
                matched = next(
                    (
                        i
                        for i in intervals
                        if _overlap(i, interval)
                        >= 0.8 * max(i[1] - i[0], interval[1] - interval[0])
                    ),
                    None,
                )
                if matched is None:
                    intervals.append(interval)
    # Header-only continuation starts (and entirely blank amount columns) must
    # retain their column geometry too. Do not invent children of a merged year.
    for row, row_boxes in zip(rows, boxes):
        for text, box in zip(row, row_boxes):
            if box and (
                re.fullmatch(
                    r"20\d{2}(?:年(?:度|末)?|年\d+月\d+日|-\d\d-\d\d)", compact(text)
                )
                or compact(text) in {"调整前", "调整后"}
            ):
                interval = (box[0], box[2])
                if not any(_overlap(i, interval) > 2 for i in intervals):
                    intervals.append(interval)
    intervals.sort()
    if (
        not intervals
        or intervals[0][0] <= bbox[0] + 2
        or any(a[1] > b[0] + 2 for a, b in zip(intervals, intervals[1:]))
    ):
        return {"status": "ambiguous", "reason": "ambiguous_column_geometry"}
    columns = [(bbox[0], intervals[0][0]), *intervals]
    normalized, sources = [], []
    for r, (row, row_boxes) in enumerate(zip(rows, boxes)):
        cells = [None] * len(columns)
        refs = [[] for _ in columns]
        for c, (text, box) in enumerate(zip(row, row_boxes)):
            if not box or not compact(text):
                continue
            interval = (box[0], box[2])
            targets = [
                i
                for i, bounds in enumerate(columns)
                if _overlap(interval, bounds)
                >= 0.75 * min(interval[1] - interval[0], bounds[1] - bounds[0])
            ]
            # Only multi-column headers may be repeated over their actual span.
            if len(targets) != 1 and not re.fullmatch(
                r"20\d{2}(?:年(?:度|末)?|年\d+月\d+日|-\d\d-\d\d)", compact(text)
            ):
                return {"status": "ambiguous", "reason": "ambiguous_cell_span"}
            if not targets:
                return {"status": "ambiguous", "reason": "unmapped_cell"}
            for i in targets:
                cells[i] = (cells[i] or "") + text
                refs[i].append([r, c])
        normalized.append(cells)
        sources.append(refs)
    return {
        "status": "mapped",
        "columns": columns,
        "rows": normalized,
        "sourceCells": sources,
    }


def aligned_columns(previous, current):
    """Continuation columns must have matching positions as well as a count."""
    if len(previous) != len(current):
        return False
    return all(
        abs(a - b) <= 0.02
        for old, new in zip(previous, current)
        for a, b in zip(old, new)
    )


def relative_columns(table):
    bounds = table["bbox"]
    width = bounds[2] - bounds[0]
    return [
        [(a - bounds[0]) / width, (b - bounds[0]) / width]
        for a, b in table["structure"]["columns"]
    ]
