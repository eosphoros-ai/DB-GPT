"""Fill the HTML report template with data from previous pipeline steps.

Usage:
    python fill_template.py '<json_args>'

The JSON argument should contain:
    ratio_data   : dict – output of calculate_ratios.py (30 template keys)
    chart_paths  : dict – output of generate_charts.py, e.g.
                   {"financial_overview": "/abs/path/financial_overview.png", ...}
    analysis     : dict – LLM-written analysis text, e.g.
                   {"PROFITABILITY_ANALYSIS": "...", "SOLVENCY_ANALYSIS": "...", ...}

Produces a single "html" chunk containing the fully populated report.
Image ``src`` attributes use the **original filename** (e.g.
``financial_overview.png``).  The downstream ``html_interpreter`` post-
processing in ``agentic_data_api.py`` will automatically rewrite these to
the correct ``/images/<uuid8>_<name>.png`` served URLs.
"""

import json
import os
import re
import sys


# ── Locate the template relative to this script ──────────────────────
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_SKILL_DIR = os.path.dirname(_SCRIPT_DIR)
_TEMPLATE_PATH = os.path.join(_SKILL_DIR, "templates", "report_template.html")


def _resolve_chart_src(chart_paths: dict) -> dict:
    """Build CHART_* placeholder values from chart file paths.

    For each chart, use just the basename (e.g. ``financial_overview.png``)
    so that ``html_interpreter``'s image-URL fixer can map it to the
    UUID-prefixed path under ``/images/``.

    Parameters
    ----------
    chart_paths : dict
        Mapping of chart name to absolute file path, as returned by
        ``generate_charts.py``.  Accepted shapes::

            {"financial_overview": "/path/to/financial_overview.png", ...}
            {"charts": {"financial_overview": "/path/...", ...}}

    Returns
    -------
    dict
        e.g. ``{"CHART_FINANCIAL_OVERVIEW": "financial_overview.png", ...}``
    """
    # Unwrap {"charts": {...}} wrapper if present
    if "charts" in chart_paths and isinstance(chart_paths["charts"], dict):
        chart_paths = chart_paths["charts"]

    result = {}
    for name, abs_path in chart_paths.items():
        if not isinstance(abs_path, str):
            continue
        basename = os.path.basename(abs_path)
        key = f"CHART_{name.upper()}"
        result[key] = basename
    return result


def fill_template(
    ratio_data: dict,
    chart_paths: dict,
    analysis: dict,
) -> str:
    """Read the HTML template and replace all ``{{PLACEHOLDER}}`` tokens.

    Merge priority (highest wins):
        1. *analysis*  (LLM-written text – most specific)
        2. *chart placeholders*  (derived from chart_paths)
        3. *ratio_data*  (computed numbers from calculate_ratios.py)

    Any placeholder still unresolved after merging is replaced with ``"NA"``.

    Parameters
    ----------
    ratio_data : dict
        Output of ``calculate_ratios.py`` – 30 template keys.
    chart_paths : dict
        Output of ``generate_charts.py`` – chart name → absolute path.
    analysis : dict
        LLM-provided analysis text for the 7 free-text placeholders.

    Returns
    -------
    str
        Fully populated HTML string.
    """
    if not os.path.isfile(_TEMPLATE_PATH):
        raise FileNotFoundError(f"Template not found: {_TEMPLATE_PATH}")

    with open(_TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = f.read()

    # Build the merged replacements dict
    chart_placeholders = _resolve_chart_src(chart_paths or {})

    replacements: dict = {}
    replacements.update(ratio_data or {})
    replacements.update(chart_placeholders)
    replacements.update(analysis or {})

    def _replace(m: re.Match) -> str:
        key = m.group(1)
        return str(replacements.get(key, "NA"))

    html = re.sub(r"\{\{([A-Z_0-9]+)\}\}", _replace, template)
    return html


# ── CLI entry point ──────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        # No CLI arg — try reading from stdin (handles large JSON)
        if not sys.stdin.isatty():
            arg = sys.stdin.read().strip()
            if not arg:
                print(
                    json.dumps(
                        {"error": "No input provided (stdin was empty)."},
                        ensure_ascii=False,
                    )
                )
                sys.exit(1)
        else:
            print(
                json.dumps(
                    {"error": "Please provide JSON data as an argument or via stdin."},
                    ensure_ascii=False,
                )
            )
            sys.exit(1)
    else:
        arg = sys.argv[1]

    try:
        parsed = json.loads(arg)

        # Handle single-key wrapper: {"data": {...}} or {"fill_template": {...}}
        if isinstance(parsed, dict) and len(parsed) == 1:
            only_value = next(iter(parsed.values()))
            if isinstance(only_value, dict):
                parsed = only_value

        ratio_data = parsed.get("ratio_data", {})
        chart_paths = parsed.get("chart_paths", {})
        analysis = parsed.get("analysis", {})

        html = fill_template(ratio_data, chart_paths, analysis)

        # Output as a chunks structure compatible with execute_skill_script_file
        result = {
            "chunks": [
                {"output_type": "html", "content": html},
            ]
        }
        print(json.dumps(result, ensure_ascii=False))

    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        sys.exit(1)
