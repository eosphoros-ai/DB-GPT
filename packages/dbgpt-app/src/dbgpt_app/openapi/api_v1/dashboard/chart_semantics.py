"""Conservative checks for incompatible aggregates on a stacked value axis."""

import sqlglot
from sqlglot import exp


def validate_stacked_measures(widget, dialect=None):
    visual = widget.presentation.visualization
    if not (
        widget.presentation.stacked or (visual and visual.value == "stacked_column")
    ):
        return
    if not widget.query.sql or not widget.encoding.y:
        return
    try:
        tree = sqlglot.parse_one(widget.query.sql, read=dialect)
    except (sqlglot.errors.ParseError, ValueError):
        # The SQL/security validator reports parsing failures separately.
        return
    # Inspect actual UNION projections, not words in descriptions or SQL comments.
    for union in tree.find_all(exp.Union):
        signatures = set()
        for branch in union.find_all(exp.Select):
            value = next(
                (
                    p
                    for p in branch.expressions
                    if p.alias_or_name.casefold() == widget.encoding.y.casefold()
                ),
                None,
            )
            if value is None:
                continue
            if isinstance(value, exp.Alias):
                value = value.this
            if value.find(exp.Div):
                signatures.add("ratio")
            elif value.find(exp.Avg):
                signatures.add("average")
            elif value.find(exp.Sum):
                signatures.add("sum")
            elif value.find(exp.Count):
                signatures.add("count")
        if len(signatures) > 1:
            raise ValueError(
                f"{widget.title}：堆叠图混合了不同口径的总额、均值、比率或计数。"
                "这些指标不能相加。请各自绘图，或只保留同一指标按同一单位拆分的系列；"
                "不要用‘元 / 条’等混合单位掩盖不同指标。"
            )
