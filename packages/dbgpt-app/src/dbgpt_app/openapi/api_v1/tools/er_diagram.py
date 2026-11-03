"""Render an evidence-linked ER model and portable editable diagram files."""

import json
import tempfile
import xml.etree.ElementTree as ET
from html import escape
from pathlib import Path
from typing import Any, Dict
from urllib.parse import quote

from dbgpt.agent.resource.tool.base import tool


def _text(value: Any, label: str, limit: int = 256) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{label} must be a nonempty string of at most {limit} chars")
    if any(ord(char) < 32 for char in value):
        raise ValueError(f"{label} contains control characters")
    return value


def validate_er_model(model: Dict[str, Any], state: Dict[str, Any]) -> dict:
    """Validate graph identity, endpoints, composite mappings and provenance."""
    if not isinstance(model, dict):
        raise ValueError("model must be an object")
    title = _text(model.get("title", "数据库 ER 图"), "title", 128)
    tables = model.get("tables")
    if not isinstance(tables, list) or not 1 <= len(tables) <= 60:
        raise ValueError("tables must contain 1–60 tables; split larger models")
    evidence = model.get("evidence_artifact_ids", [])
    if (
        not isinstance(evidence, list)
        or not evidence
        or any(
            not isinstance(item, str)
            or item not in state.get("_query_artifacts", {})
            or state["_query_artifacts"][item].get("truncated")
            for item in evidence
        )
    ):
        raise ValueError("reference existing untruncated metadata query artifact IDs")
    normalized, columns_by_table = [], {}
    qualified_names = set()
    for item in tables:
        identity = _text(item.get("id"), "table.id")
        if identity in columns_by_table:
            raise ValueError(f"duplicate table id: {identity}")
        name = _text(item.get("name"), "table.name")
        schema = item.get("schema", "")
        if schema:
            schema = _text(schema, "table.schema")
        if (schema, name) in qualified_names:
            raise ValueError(f"duplicate qualified table name: {schema}.{name}")
        qualified_names.add((schema, name))
        columns = item.get("columns")
        if not isinstance(columns, list) or not 1 <= len(columns) <= 150:
            raise ValueError("each table needs 1–150 columns")
        names, normalized_columns = set(), []
        for col in columns:
            column = _text(col.get("name"), "column.name")
            if column in names:
                raise ValueError(f"duplicate column: {identity}.{column}")
            names.add(column)
            primary = col.get("primary_key", False)
            nullable = col.get("nullable")
            if not isinstance(primary, bool) or (
                nullable is not None and not isinstance(nullable, bool)
            ):
                raise ValueError("primary_key must be boolean; nullable boolean/null")
            normalized_columns.append(
                {
                    "name": column,
                    "type": _text(col.get("type", "unknown"), "column.type"),
                    "primary_key": primary,
                    "nullable": nullable,
                }
            )
        columns_by_table[identity] = names
        normalized.append(
            {
                "id": identity,
                "name": name,
                "schema": schema,
                "columns": normalized_columns,
            }
        )
    relations = model.get("relationships", [])
    if not isinstance(relations, list) or len(relations) > 200:
        raise ValueError("relationships must be a list of at most 200 items")
    normalized_relations = []
    for index, relation in enumerate(relations):
        source, target = relation.get("from_table"), relation.get("to_table")
        source_columns, target_columns = (
            relation.get("from_columns"),
            relation.get("to_columns"),
        )
        if source not in columns_by_table or target not in columns_by_table:
            raise ValueError("relationship endpoint missing from tables")
        if (
            not isinstance(source_columns, list)
            or not isinstance(target_columns, list)
            or not source_columns
            or len(source_columns) != len(target_columns)
            or any(c not in columns_by_table[source] for c in source_columns)
            or any(c not in columns_by_table[target] for c in target_columns)
        ):
            raise ValueError("relationship columns must map existing columns equally")
        kind = relation.get("kind")
        if kind not in ("declared", "inferred"):
            raise ValueError("relationship.kind must be declared or inferred")
        normalized_relations.append(
            {
                "name": _text(
                    relation.get("name", f"relation_{index + 1}"), "relation.name"
                ),
                "from_table": source,
                "to_table": target,
                "from_columns": source_columns,
                "to_columns": target_columns,
                "kind": kind,
                "basis": _text(relation.get("basis"), "relationship.basis", 1000),
            }
        )
    return {
        "version": 1,
        "title": title,
        "database": str(state.get("database_name") or ""),
        "evidence_artifact_ids": list(dict.fromkeys(evidence)),
        "tables": normalized,
        "relationships": normalized_relations,
    }


def _layout(model: dict) -> tuple:
    """Use nonoverlapping lanes; all fields remain present in exports."""
    lanes = min(3, len(model["tables"]))
    lane_y = [64] * lanes
    boxes = {}
    for index, table in enumerate(model["tables"]):
        lane = index % lanes
        height = 44 + 25 * len(table["columns"])
        boxes[table["id"]] = (48 + lane * 420, lane_y[lane], 320, height)
        lane_y[lane] += height + 100
    return boxes, lanes * 420, max(lane_y)


def er_svg(model: dict) -> str:
    boxes, width, height = _layout(model)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img">'
        f"<title>{escape(model['title'])}</title>",
        '<rect width="100%" height="100%" fill="#fff"/>',
    ]
    tables = {table["id"]: table for table in model["tables"]}
    for index, relation in enumerate(model["relationships"]):
        sx, sy, sw, _ = boxes[relation["from_table"]]
        tx, ty, tw, _ = boxes[relation["to_table"]]
        start = next(
            i
            for i, c in enumerate(tables[relation["from_table"]]["columns"])
            if c["name"] == relation["from_columns"][0]
        )
        end = next(
            i
            for i, c in enumerate(tables[relation["to_table"]]["columns"])
            if c["name"] == relation["to_columns"][0]
        )
        sy += 57 + start * 25
        ty += 57 + end * 25
        if tx > sx:
            left, right = sx + sw, tx
            gutter = left + 40 + (index % 3) * 8
        elif tx < sx:
            left, right = sx, tx + tw
            gutter = left - 40 - (index % 3) * 8
        else:
            left, right = sx + sw, tx + tw
            gutter = left + 16 + (index % 5) * 8
        path = f"M {left} {sy} H {gutter} V {ty} H {right}"
        dashed = ' stroke-dasharray="6 4"' if relation["kind"] == "inferred" else ""
        description = escape(
            " · ".join([relation["name"], relation["kind"], relation["basis"]])
        )
        parts.append(
            f'<path d="{path}" fill="none" stroke="#64748b" stroke-width="1.5"'
            f"{dashed}><title>{description}</title></path>"
        )
    for table in model["tables"]:
        x, y, w, h = boxes[table["id"]]
        label = ".".join(filter(None, [table["schema"], table["name"]]))
        parts.extend(
            [
                f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8"'
                ' fill="#fff" stroke="#94a3b8"/>',
                f'<path d="M {x} {y + 36} H {x + w}" stroke="#94a3b8"/>',
                f'<text x="{x + 12}" y="{y + 24}" font-size="15"'
                ' font-family="sans-serif" fill="#0f172a">'
                f"<title>{escape(label)}</title>{escape(label[:34])}</text>",
            ]
        )
        for index, column in enumerate(table["columns"]):
            label = (
                ("PK " if column["primary_key"] else "")
                + column["name"]
                + " : "
                + column["type"]
            )
            parts.append(
                f'<text x="{x + 12}" y="{y + 57 + index * 25}" font-size="13"'
                ' font-family="monospace" fill="#334155">'
                f"<title>{escape(label)}</title>{escape(label[:38])}</text>"
            )
    parts.append("</svg>")
    return "".join(parts)


def er_drawio(model: dict) -> str:
    """Native editable mxGraph XML, with column-level connector endpoints."""
    boxes, width, height = _layout(model)
    document = ET.Element("mxfile", host="app.diagrams.net")
    diagram = ET.SubElement(document, "diagram", id="er", name=model["title"])
    graph = ET.SubElement(
        diagram, "mxGraphModel", pageWidth=str(width), pageHeight=str(height)
    )
    root = ET.SubElement(graph, "root")
    ET.SubElement(root, "mxCell", id="0")
    ET.SubElement(root, "mxCell", id="1", parent="0")
    ids = {}
    for index, table in enumerate(model["tables"]):
        identity = f"table_{index}"
        x, y, w, h = boxes[table["id"]]
        label = ".".join(filter(None, [table["schema"], table["name"]]))
        cell = ET.SubElement(
            root,
            "mxCell",
            id=identity,
            value=label,
            vertex="1",
            parent="1",
            style="swimlane;html=0;startSize=36;horizontal=1;rounded=1;fillColor=#f1f5f9;",
        )
        ET.SubElement(
            cell,
            "mxGeometry",
            x=str(x),
            y=str(y),
            width=str(w),
            height=str(h),
            **{"as": "geometry"},
        )
        for ci, column in enumerate(table["columns"]):
            column_id = f"{identity}_column_{ci}"
            ids[(table["id"], column["name"])] = column_id
            text = (
                ("PK " if column["primary_key"] else "")
                + column["name"]
                + " : "
                + column["type"]
            )
            cell = ET.SubElement(
                root,
                "mxCell",
                id=column_id,
                value=text,
                vertex="1",
                parent=identity,
                style="text;html=0;align=left;verticalAlign=middle;spacingLeft=12;",
            )
            ET.SubElement(
                cell,
                "mxGeometry",
                y=str(38 + ci * 25),
                width=str(w),
                height="25",
                **{"as": "geometry"},
            )
    for index, relation in enumerate(model["relationships"]):
        for ci, (source, target) in enumerate(
            zip(relation["from_columns"], relation["to_columns"])
        ):
            label = relation["name"] + (
                " [推断]" if relation["kind"] == "inferred" else " [声明]"
            )
            cell = ET.SubElement(
                root,
                "mxCell",
                id=f"edge_{index}_{ci}",
                value=label,
                edge="1",
                parent="1",
                source=ids[(relation["from_table"], source)],
                target=ids[(relation["to_table"], target)],
                style="edgeStyle=orthogonalEdgeStyle;html=0;endArrow=none;"
                + ("dashed=1;" if relation["kind"] == "inferred" else ""),
            )
            ET.SubElement(cell, "mxGeometry", relative="1", **{"as": "geometry"})
    return ET.tostring(document, encoding="unicode")


def er_mermaid(model: dict) -> str:
    """Stable aliases avoid invalid Mermaid names and fabricated cardinality."""
    aliases = {t["id"]: f"T{i}" for i, t in enumerate(model["tables"])}
    lines = ["erDiagram", "    %% Relationship cardinality is not asserted."]
    for table in model["tables"]:
        label = ".".join(filter(None, [table["schema"], table["name"]]))
        # Encode unsafe label characters rather than inserting Mermaid syntax.
        label = label.replace('"', "_").replace("\\", "_")
        lines.append(f'    {aliases[table["id"]]}["{label}"] {{')
        for index, col in enumerate(table["columns"]):
            comment = (
                (col["name"] + " : " + col["type"]).replace('"', "_").replace("\\", "_")
            )
            lines.append(
                f"        string C{index}"
                + (" PK" if col["primary_key"] else "")
                + f' "{comment}"'
            )
            lines.append(f"        %% C{index} = {json.dumps(col, ensure_ascii=False)}")
        lines.append("    }")
    for index, relation in enumerate(model["relationships"]):
        # Zero-or-more is a broad visual notation, explicitly not a constraint.
        connector = ".." if relation["kind"] == "inferred" else "--"
        lines.append(
            f"    {aliases[relation['from_table']]} }}o{connector}o{{ "
            f'{aliases[relation["to_table"]]} : "R{index}"'
        )
        lines.append(f"    %% R{index} = {json.dumps(relation, ensure_ascii=False)}")
    return "\n".join(lines) + "\n"


def er_dbml(model: dict) -> str:
    """Only declared FKs become DBML constraints; inferred links stay comments."""
    aliases = {
        t["id"]: ".".join(
            json.dumps(part, ensure_ascii=False)
            for part in [t["schema"], t["name"]]
            if part
        )
        for t in model["tables"]
    }
    column_aliases = {}
    lines = [
        "// Physical metadata export; inferred links are comments, not constraints."
    ]
    for table in model["tables"]:
        identity = aliases[table["id"]]
        label = ".".join(filter(None, [table["schema"], table["name"]]))
        lines.extend(
            [f"// {json.dumps(label, ensure_ascii=False)}", f"Table {identity} {{"]
        )
        pk = []
        for index, col in enumerate(table["columns"]):
            alias = json.dumps(col["name"], ensure_ascii=False)
            column_aliases[(table["id"], col["name"])] = alias
            if col["primary_key"]:
                pk.append(alias)
            # Quoted types allow sizes and dialect-specific type names.
            settings = " [not null]" if col["nullable"] is False else ""
            lines.append(
                f"  // {alias} = {json.dumps(col['name'], ensure_ascii=False)}"
            )
            lines.append(f"  {alias} {json.dumps(col['type'])}{settings}")
        if pk:
            lines.extend(["  indexes {", f"    ({', '.join(pk)}) [pk]", "  }"])
        lines.extend(["}", ""])
    for index, r in enumerate(model["relationships"]):
        lines.append(f"// R{index} = {json.dumps(r, ensure_ascii=False)}")
        if r["kind"] == "declared":
            source = ", ".join(
                column_aliases[(r["from_table"], c)] for c in r["from_columns"]
            )
            target = ", ".join(
                column_aliases[(r["to_table"], c)] for c in r["to_columns"]
            )
            lines.append(
                f"Ref R{index}: {aliases[r['from_table']]}.({source}) > "
                f"{aliases[r['to_table']]}.({target})"
            )
    return "\n".join(lines) + "\n"


def er_html(model: dict, svg: str, exports: dict) -> str:
    title = escape(model["title"])
    controls = "".join(
        f'<a download="er-diagram.{extension}" '
        f'href="data:{mime};charset=utf-8,{quote(content, safe="")}">{label}</a>'
        for extension, (label, mime, content) in exports.items()
    )
    declared = sum(r["kind"] == "declared" for r in model["relationships"])
    inferred = len(model["relationships"]) - declared
    details = "".join(
        f"<tr><td>{escape(r['name'])}</td><td>{escape(r['kind'])}</td>"
        f"<td>{escape(r['from_table'])} ({escape(', '.join(r['from_columns']))}) → "
        f"{escape(r['to_table'])} ({escape(', '.join(r['to_columns']))})</td>"
        f"<td>{escape(r['basis'])}</td></tr>"
        for r in model["relationships"]
    )
    return (
        '<!doctype html><html lang="zh"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{title}</title><style>"
        "body{margin:0;font:14px/1.6 system-ui,sans-serif;"
        "color:#172033;background:#fff}"
        "header,footer{padding:12px 16px}h1{font-size:18px;margin:0}"
        "nav{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px}"
        "a,button{padding:5px 10px;border:1px solid #cbd5e1;border-radius:6px;"
        "color:#166534;background:#fff;text-decoration:none;cursor:pointer}"
        ".canvas{height:480px;overflow:auto;border-block:1px solid #e2e8f0}"
        "svg{display:block}table{border-collapse:collapse;width:100%}"
        "td,th{border:1px solid #e2e8f0;padding:8px;text-align:left}"
        '</style></head><body data-dbgpt-er="1">'
        f"<header><h1>{title}</h1><div>{len(model['tables'])} 张表"
        f" · 声明关系 {declared} · 推断关系 {inferred}"
        " · 实线为声明关系，虚线为推断；基数未确认</div>"
        f'<nav>{controls}<button id="smaller">缩小</button>'
        '<button id="bigger">放大</button>'
        '<button id="reset">重置</button></nav></header>'
        f'<div class="canvas">{svg}</div><footer>'
        "draw.io 可在 diagrams.net 打开并编辑；DBML 可导入 dbdiagram，"
        "推断关系仅保留为注释。"
        " Mermaid 源码使用安全别名，原始名称和列映射保留在注释及 JSON 中。"
        "<table><thead><tr><th>关系</th><th>类型</th><th>列映射</th><th>依据</th>"
        f"</tr></thead><tbody>{details}</tbody></table>"
        f"<p>元数据证据：{escape(', '.join(model['evidence_artifact_ids']))}</p>"
        "</footer>"
        "<script>const s=document.querySelector('svg');"
        "const w=Number(s.getAttribute('width'));"
        "const h=Number(s.getAttribute('height'));let z=1;"
        "function resize(){s.setAttribute('width',w*z);"
        "s.setAttribute('height',h*z)}"
        "document.getElementById('smaller').onclick=()=>{"
        "z=Math.max(.25,z-.25);resize()};"
        "document.getElementById('bigger').onclick=()=>{"
        "z=Math.min(3,z+.25);resize()};"
        "document.getElementById('reset').onclick=()=>{z=1;resize()};"
        "</script></body></html>"
    )


def make_generate_er_diagram(state: Dict[str, Any]):
    @tool(
        description=(
            "生成可渲染、可下载导入的 ER 图。model 包含 title、"
            "evidence_artifact_ids（本会话真实未截断元数据查询 ID）、"
            "tables:[{id,name,schema,columns:[{name,type,primary_key,nullable}]}]、"
            "relationships:[{name,from_table,to_table,from_columns,to_columns,"
            "kind:'declared'或'inferred',basis}]。复合键按列对应；不得编造约束。"
            "返回内联 HTML 图、drawio/DBML/Mermaid/SVG/JSON 文件。只生成，不改数据库。"
        )
    )
    def generate_er_diagram(model: Dict[str, Any]) -> str:
        try:
            model = validate_er_model(model, state)
            svg = er_svg(model)
            exports = {
                "drawio": ("draw.io", "application/xml", er_drawio(model)),
                "dbml": ("DBML", "text/plain", er_dbml(model)),
                "mmd": ("Mermaid", "text/plain", er_mermaid(model)),
                "svg": ("SVG", "image/svg+xml", svg),
                "json": (
                    "JSON",
                    "application/json",
                    json.dumps(model, ensure_ascii=False, indent=2),
                ),
            }
            html = er_html(model, svg, exports)
            directory = Path(tempfile.mkdtemp(prefix="dbgpt-er-"))
            chunks = [{"output_type": "html", "content": html, "title": model["title"]}]
            for extension, (_, _, content) in exports.items():
                path = directory / f"er-diagram.{extension}"
                path.write_text(content, encoding="utf-8")
                chunks.append(
                    {
                        "output_type": "file",
                        "content": {
                            "name": path.name,
                            "file_path": str(path),
                            "size": path.stat().st_size,
                            "content": content,
                        },
                    }
                )
            state["_er_diagram"] = model
            return json.dumps(
                {
                    "success": True,
                    "table_count": len(model["tables"]),
                    "relationship_count": len(model["relationships"]),
                    "chunks": chunks,
                },
                ensure_ascii=False,
            )
        except (ValueError, TypeError, KeyError, AttributeError) as error:
            return json.dumps(
                {"success": False, "error": str(error)}, ensure_ascii=False
            )

    return generate_er_diagram
