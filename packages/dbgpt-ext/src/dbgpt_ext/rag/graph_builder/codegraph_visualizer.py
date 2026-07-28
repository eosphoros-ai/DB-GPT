"""Code graph interactive HTML visualization.

Generates a self-contained HTML page with vis-network force-directed graph.
Features:
  - Dark theme with sidebar (search, info panel, legend, stats)
  - Node coloring by type (repository/module/class/function/method/variable)
  - Edge styling by type and confidence
  - Community detection with color coding
  - Click-to-inspect, search, and legend filtering
  - Auto-aggregation for large graphs (>5000 nodes)
"""

import html
import json
import logging
from collections import defaultdict
from typing import Dict, List, Tuple

from dbgpt.storage.graph_store.graph import MemoryGraph

logger = logging.getLogger(__name__)

# Node type colors
NODE_TYPE_COLORS = {
    "repository": "#BAB0AC",
    "module": "#4E79A7",
    "class": "#F28E2B",
    "function": "#59A14F",
    "method": "#76B7B2",
    "variable": "#FF9DA7",
    "file": "#4E79A7",
    "unknown": "#888888",
}

# Edge type colors
EDGE_TYPE_COLORS = {
    "contains": "#4E79A7",
    "imports": "#9C755F",
    "calls": "#E15759",
    "inherits": "#B07AA1",
    "implements": "#EDC948",
    "references": "#BAB0AC",
    "defines": "#59A14F",
    "unknown": "#555555",
}

# Community colors
COMMUNITY_COLORS = [
    "#4E79A7",
    "#F28E2B",
    "#E15759",
    "#76B7B2",
    "#59A14F",
    "#EDC948",
    "#B07AA1",
    "#FF9DA7",
    "#9C755F",
    "#BAB0AC",
]

DEFAULT_NODE_COLOR = "#888888"
DEFAULT_EDGE_COLOR = "#555555"


# ---------------------------------------------------------------------------
# Degree computation
# ---------------------------------------------------------------------------


def _compute_degrees(graph: MemoryGraph) -> Dict[str, int]:
    """Compute degree (in + out) for each vertex."""
    degree: Dict[str, int] = defaultdict(int)
    for edge in graph.edges():
        degree[edge.sid] += 1
        degree[edge.tid] += 1
    return dict(degree)


# ---------------------------------------------------------------------------
# Community detection wrapper
# ---------------------------------------------------------------------------


def _detect_communities(
    graph: MemoryGraph,
) -> Tuple[Dict[str, List[str]], Dict[str, str]]:
    """Run community detection and return (communities, summaries).

    Returns:
        communities: {community_id: [vertex_id, ...]}
        summaries: {community_id: "Community community_0 (N nodes) -- ..."}
    """
    try:
        from dbgpt_ext.rag.graph_builder.community_detector import CodeCommunityDetector

        logger.info(
            f"[codegraph] Starting community detection for graph with {graph.vertex_count} vertices"
        )
        detector = CodeCommunityDetector(graph)
        communities = detector.detect()
        if communities:
            logger.info(
                f"[codegraph] Community detection found {len(communities)} communities"
            )
        else:
            logger.warning(
                "[codegraph] Community detection returned no communities (networkx may be missing)"
            )
        summaries = detector.get_community_summary(communities)
        return communities, summaries
    except ImportError as e:
        logger.warning(f"[codegraph] Community detection not available: {e}")
        return {}, {}


# ---------------------------------------------------------------------------
# Node / edge conversion to vis-network format
# ---------------------------------------------------------------------------


def _truncate_label(name: str, max_len: int = 30) -> str:
    """Truncate long labels for readability."""
    if len(name) <= max_len:
        return name
    return name[: max_len - 3] + "..."


def _build_vis_nodes(
    graph: MemoryGraph,
    degree: Dict[str, int],
    communities: Dict[str, List[str]],
    summaries: Dict[str, str],
    use_community_color: bool = False,
) -> Tuple[list, list]:
    """Build vis-network node list and legend data.

    Args:
        graph: The MemoryGraph.
        degree: Precomputed degree dict.
        communities: Community assignments.
        summaries: Community summaries.
        use_community_color: If True, color by community instead of node_type.

    Returns:
        (nodes_list, legend_list)
    """
    max_deg = max(degree.values()) if degree else 1

    # Build vertex → community mapping
    vid_to_community: Dict[str, str] = {}
    for cid, members in communities.items():
        for vid in members:
            vid_to_community[vid] = cid

    nodes = []
    type_counts: Dict[str, int] = defaultdict(int)

    for v in graph.vertices():
        node_type = v.get_prop("node_type") or v.get_prop("type") or "unknown"
        source_file = v.get_prop("source_file") or v.get_prop("file_path") or ""
        deg = degree.get(v.vid, 1)

        # Size: 10-40 based on degree
        size = 10 + 30 * (deg / max_deg) if max_deg > 0 else 15
        # Font size: hide label for very small nodes
        font_size = 12 if deg >= max_deg * 0.15 else 0

        # Color
        if use_community_color:
            cid = vid_to_community.get(v.vid, "")
            cid_int = int(cid.split("_")[-1]) if cid.startswith("community_") else 0
            color = COMMUNITY_COLORS[cid_int % len(COMMUNITY_COLORS)]
        else:
            color = NODE_TYPE_COLORS.get(node_type, DEFAULT_NODE_COLOR)

        community_id = vid_to_community.get(v.vid, "")
        community_name = (
            summaries.get(community_id, "").split("--")[0].strip()
            if community_id
            else ""
        )

        node = {
            "id": v.vid,
            "label": _truncate_label(v.name or v.vid),
            "color": {
                "background": color,
                "border": color,
                "highlight": {"background": "#ffffff", "border": color},
            },
            "size": round(size, 1),
            "font": {"size": font_size, "color": "#ffffff"},
            "title": html.escape(v.name or v.vid),
            "community": community_id,
            "community_name": community_name,
            "source_file": source_file,
            "node_type": node_type,
            "degree": deg,
            "props": {k: html.escape(str(vv)) for k, vv in (v.props or {}).items()},
        }
        nodes.append(node)
        type_counts[node_type] += 1

    # Legend
    legend = []
    for ntype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        legend.append(
            {
                "type": ntype,
                "color": NODE_TYPE_COLORS.get(ntype, DEFAULT_NODE_COLOR),
                "count": count,
            }
        )

    return nodes, legend


def _build_vis_edges(graph: MemoryGraph) -> list:
    """Build vis-network edge list."""
    edges = []
    for e in graph.edges():
        confidence = e.get_prop("confidence") or ""
        edge_color = EDGE_TYPE_COLORS.get(
            e.name, EDGE_TYPE_COLORS.get(e.get_prop("type"), DEFAULT_EDGE_COLOR)
        )

        edge = {
            "from": e.sid,
            "to": e.tid,
            "label": e.name,
            "title": html.escape(f"{e.name} [{confidence}]"),
            "dashes": confidence != "EXTRACTED",
            "width": 2 if confidence == "EXTRACTED" else 1,
            "color": {
                "color": edge_color,
                "opacity": 0.7 if confidence == "EXTRACTED" else 0.35,
            },
            "confidence": confidence,
            "props": {k: html.escape(str(vv)) for k, vv in (e.props or {}).items()},
        }
        edges.append(edge)
    return edges


# ---------------------------------------------------------------------------
# Large graph aggregation
# ---------------------------------------------------------------------------


def _aggregate_to_communities(
    graph: MemoryGraph,
    communities: Dict[str, List[str]],
    summaries: Dict[str, str],
) -> Tuple[list, list]:
    """Aggregate graph into community-level meta-nodes for large graphs.

    Returns (meta_nodes, meta_edges) in vis-network format.
    """
    # Build vid → community mapping
    vid_to_community: Dict[str, str] = {}
    for cid, members in communities.items():
        for vid in members:
            vid_to_community[vid] = cid

    # Count members per community
    member_counts = {cid: len(members) for cid, members in communities.items()}
    max_mc = max(member_counts.values()) if member_counts else 1

    # Meta-nodes
    meta_nodes = []
    for cid, members in communities.items():
        mc = member_counts[cid]
        size = 10 + 30 * (mc / max_mc) if max_mc > 0 else 15
        cid_int = int(cid.split("_")[-1]) if cid.startswith("community_") else 0
        color = COMMUNITY_COLORS[cid_int % len(COMMUNITY_COLORS)]
        label = summaries.get(cid, cid).split("--")[0].strip()

        meta_nodes.append(
            {
                "id": cid,
                "label": _truncate_label(label, 40),
                "color": {
                    "background": color,
                    "border": color,
                    "highlight": {"background": "#ffffff", "border": color},
                },
                "size": round(size, 1),
                "font": {"size": 12, "color": "#ffffff"},
                "title": html.escape(summaries.get(cid, cid)),
                "community": cid,
                "community_name": label,
                "source_file": "",
                "node_type": "community",
                "degree": mc,
            }
        )

    # Meta-edges: count cross-community edges
    cross_edges: Dict[Tuple[str, str], int] = defaultdict(int)
    for e in graph.edges():
        src_comm = vid_to_community.get(e.sid, "")
        tgt_comm = vid_to_community.get(e.tid, "")
        if src_comm and tgt_comm and src_comm != tgt_comm:
            cross_edges[(src_comm, tgt_comm)] += 1

    meta_edges = []
    for (src, tgt), count in cross_edges.items():
        meta_edges.append(
            {
                "from": src,
                "to": tgt,
                "label": f"{count} cross-community edges",
                "title": f"{count} cross-community edges [AGGREGATED]",
                "dashes": True,
                "width": 1,
                "color": {"opacity": 0.35},
                "confidence": "AGGREGATED",
            }
        )

    return meta_nodes, meta_edges


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------


def _html_styles() -> str:
    return """
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0f0f1a; color: #e0e0e0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; display: flex; height: 100vh; overflow: hidden; }
  #graph { flex: 1; }
  #sidebar { width: 300px; background: #1a1a2e; border-left: 1px solid #2a2a4e; display: flex; flex-direction: column; overflow: hidden; }
  #search-wrap { padding: 12px; border-bottom: 1px solid #2a2a4e; }
  #search { width: 100%; background: #0f0f1a; border: 1px solid #3a3a5e; color: #e0e0e0; padding: 7px 10px; border-radius: 6px; font-size: 13px; outline: none; }
  #search:focus { border-color: #4E79A7; }
  #search-results { max-height: 180px; overflow-y: auto; padding: 4px 12px; border-bottom: 1px solid #2a2a4e; display: none; }
  .search-item { padding: 4px 6px; cursor: pointer; border-radius: 4px; font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .search-item:hover { background: #2a2a4e; }
  #stats { padding: 12px; border-bottom: 1px solid #2a2a4e; font-size: 12px; color: #888; }
  #legend { padding: 12px; border-bottom: 1px solid #2a2a4e; }
  #legend h3 { font-size: 12px; color: #888; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px; }
  .legend-item { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; font-size: 12px; cursor: pointer; }
  .legend-color { width: 12px; height: 12px; border-radius: 50%; }
  .legend-item:hover .legend-color { transform: scale(1.2); }
  #info { flex: 1; overflow-y: auto; padding: 12px; }
  #info h3 { font-size: 14px; margin-bottom: 8px; color: #fff; }
  #info .prop { font-size: 12px; margin-bottom: 4px; color: #aaa; }
  #info .prop span { color: #ccc; }
  #info .empty { color: #666; font-style: italic; }
  #info h4 { font-size: 12px; color: #888; margin: 8px 0 4px; text-transform: uppercase; letter-spacing: 0.5px; }
  .stat-row { margin-bottom: 3px; }
  #type-stats { color: #aaa; }
  .loading { position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); color: #666; }
"""


def _html_scripts(nodes: list, edges: list, legend: list) -> str:
    nodes_json = json.dumps(nodes, ensure_ascii=False)
    edges_json = json.dumps(edges, ensure_ascii=False)
    legend_json = json.dumps(legend, ensure_ascii=False)
    return f"""
  const nodes = new vis.DataSet({nodes_json});
  const edges = new vis.DataSet({edges_json});
  const legend = {legend_json};

  const container = document.getElementById('graph');
  const data = {{ nodes, edges }};
  const options = {{
    nodes: {{
      shape: 'dot',
      font: {{ color: '#ffffff', face: 'monospace' }},
      borderWidth: 1,
      shadow: true,
    }},
    edges: {{
      font: {{ align: 'middle', size: 10, color: '#666' }},
      arrows: {{ to: {{ enabled: true, scaleFactor: 0.5 }} }},
      smooth: {{ type: 'continuous' }},
    }},
    physics: {{
      enabled: true,
      solver: 'forceAtlas2Based',
      forceAtlas2Based: {{ gravitationalConstant: -50, centralGravity: 0.01, springLength: 100, springConstant: 0.08 }},
      stabilization: {{ iterations: 150 }},
    }},
      interaction: {{ hover: true, tooltipDelay: 200, zoomView: true, dragView: true, hoverConnectedEdges: true }},
  }};
  const network = new vis.Network(container, data, options);

  // Search
  const searchInput = document.getElementById('search');
  const searchResults = document.getElementById('search-results');
  searchInput.addEventListener('input', function() {{
    const q = this.value.toLowerCase();
    searchResults.style.display = q ? 'block' : 'none';
    searchResults.innerHTML = '';
    if (!q) return;
    const matches = nodes.get().filter(n => n.label.toLowerCase().includes(q)).slice(0, 20);
    matches.forEach(n => {{
      const div = document.createElement('div');
      div.className = 'search-item';
      div.textContent = n.label + ' (' + n.node_type + ')';
      div.onclick = function() {{
        network.focus(n.id, {{ scale: 0.8, animation: true }});
        network.selectNodes([n.id]);
      }};
      searchResults.appendChild(div);
    }});
  }});

  // Click to inspect (nodes and edges)
  network.on('click', function(params) {{
    showInfo(params);
  }});

  // Hover tooltip uses metadata for edges too
  network.setOptions({{
    edges: {{ title: undefined }}
  }});

  function renderProps(obj) {{
    if (!obj) return '';
    let out = '';
    Object.entries(obj).forEach(function(entry) {{
      const k = entry[0], v = entry[1];
      const display = typeof v === 'object' ? JSON.stringify(v) : String(v);
      out += '<div class="prop">' + htmlEscape(k) + ': <span>' + htmlEscape(display) + '</span></div>';
    }});
    return out;
  }}

  function showInfo(params) {{
    const info = document.getElementById('info');
    let html = '';
    if (params.nodes && params.nodes.length > 0) {{
      const nodeId = params.nodes[0];
      const node = nodes.get(nodeId);
      html += '<h3>' + htmlEscape(node.label) + '</h3>';
      html += '<div class="prop">ID: <span>' + htmlEscape(node.id) + '</span></div>';
      html += '<div class="prop">Type: <span>' + htmlEscape(node.node_type) + '</span></div>';
      if (node.source_file) html += '<div class="prop">File: <span>' + htmlEscape(node.source_file) + '</span></div>';
      html += '<div class="prop">Degree: <span>' + node.degree + '</span></div>';
      if (node.community_name) html += '<div class="prop">Community: <span>' + htmlEscape(node.community_name) + '</span></div>';
      html += '<h4 style="margin-top:12px;">Metadata</h4>';
      html += renderProps(node.props);
    }} else if (params.edges && params.edges.length > 0) {{
      const edgeId = params.edges[0];
      const edge = edges.get(edgeId);
      html += '<h3>' + htmlEscape(edge.label) + '</h3>';
      html += '<div class="prop">From: <span>' + htmlEscape(edge.from) + '</span></div>';
      html += '<div class="prop">To: <span>' + htmlEscape(edge.to) + '</span></div>';
      html += '<div class="prop">Confidence: <span>' + htmlEscape(edge.confidence || 'N/A') + '</span></div>';
      html += '<h4 style="margin-top:12px;">Metadata</h4>';
      html += renderProps(edge.props);
    }} else {{
      html = '<div class="empty">Click a node or edge to view details</div>';
    }}
    info.innerHTML = html;
  }}

  function htmlEscape(s) {{
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }}

  // Render legend
  const legendEl = document.getElementById('legend-items');
  legend.forEach(item => {{
    const div = document.createElement('div');
    div.className = 'legend-item';
    div.innerHTML = '<div class="legend-color" style="background:' + item.color + '"></div>' + item.type + ' (' + item.count + ')';
    div.onclick = function() {{
      const filtered = nodes.get().filter(n => n.node_type === item.type);
      if (filtered.length > 0) {{
        network.focus(filtered[0].id, {{ scale: 0.5, animation: true }});
      }}
    }};
    legendEl.appendChild(div);
  }});

  // Update stats (metadata + per-type counts)
  document.getElementById('node-count').textContent = nodes.length;
  document.getElementById('edge-count').textContent = edges.length;
  const typeStatMap = {{}};
  nodes.get().forEach(n => {{ typeStatMap[n.node_type] = (typeStatMap[n.node_type] || 0) + 1; }});
  const typeStatsEl = document.getElementById('type-stats');
  typeStatsEl.textContent = Object.entries(typeStatMap)
    .sort((a, b) => b[1] - a[1])
    .map(entry => entry[0] + ': ' + entry[1])
    .join(' · ') || '';
"""


def codegraph_to_html(graph: MemoryGraph, knowledge_id: str = "") -> str:
    """Generate interactive HTML visualization for a code knowledge graph.

    Args:
        graph: The MemoryGraph to visualize.
        knowledge_id: Optional knowledge space ID for display.

    Returns:
        Complete HTML page as string.
    """
    # Compute degrees
    degree = _compute_degrees(graph)

    # Detect communities (optional, may fail if networkx not installed)
    communities, summaries = _detect_communities(graph)

    # Decide: full graph or aggregated
    AGGREGATION_THRESHOLD = 5000
    use_aggregation = graph.vertex_count > AGGREGATION_THRESHOLD

    if use_aggregation:
        logger.info(
            f"[codegraph] Aggregating {graph.vertex_count} nodes into communities"
        )
        nodes, edges = _aggregate_to_communities(graph, communities, summaries)
    else:
        nodes, legend = _build_vis_nodes(
            graph, degree, communities, summaries, use_community_color=False
        )
        edges = _build_vis_edges(graph)

    # Build page
    title = f"Code Graph: {knowledge_id}" if knowledge_id else "Code Graph"

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
  <style>{_html_styles()}</style>
</head>
<body>
  <div id="graph"></div>
  <div id="sidebar">
    <div id="search-wrap">
      <input type="text" id="search" placeholder="Search nodes..." autocomplete="off">
      <div id="search-results"></div>
    </div>
    <div id="stats">
      <div class="stat-row"><span id="node-count">0</span> nodes · <span id="edge-count">0</span> edges {"(aggregated)" if use_aggregation else ""}</div>
      <div class="stat-row" id="type-stats"></div>
    </div>
    <div id="legend">
      <h3>Node Types</h3>
      <div id="legend-items"></div>
    </div>
    <div id="info">
      <div class="empty">Click a node or edge to view details</div>
    </div>
  </div>
  <script>{_html_scripts(nodes, edges, legend if not use_aggregation else [])}</script>
</body>
</html>"""
