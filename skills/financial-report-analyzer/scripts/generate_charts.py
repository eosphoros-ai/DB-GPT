"""Generate financial analysis charts from JSON data.

Usage:
    python generate_charts.py '<json_data>'

Produces 3 PNG charts in the same directory as this script and outputs
a JSON manifest with the chart file paths.
"""

import json
import os
import sys

import matplotlib

matplotlib.use("Agg")  # Non-interactive backend — must be set before pyplot import

import matplotlib.font_manager as fm  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

# ---------------------------------------------------------------------------
# Color palette (matches the HTML report theme)
# ---------------------------------------------------------------------------
COLOR_NAVY = "#0f3460"
COLOR_DARK = "#16213e"
COLOR_ACCENT = "#e94560"
COLOR_PURPLE = "#533483"
COLOR_GREEN = "#27ae60"
COLOR_LIGHT_BLUE = "#3498db"
COLOR_ORANGE = "#e67e22"

CHART_DPI = 150


# ---------------------------------------------------------------------------
# Font setup
# ---------------------------------------------------------------------------
def setup_font():
    """Configure matplotlib fonts for readable chart labels."""
    candidates = [
        "DejaVu Sans",
        "Arial",
        "Helvetica",
        "Segoe UI",
    ]

    available = {f.name for f in fm.fontManager.ttflist}
    for font_name in candidates:
        if font_name in available:
            plt.rcParams["font.sans-serif"] = [font_name, "sans-serif"]
            plt.rcParams["font.family"] = "sans-serif"
            plt.rcParams["axes.unicode_minus"] = False
            return
    plt.rcParams["font.sans-serif"] = ["DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def format_yi(value):
    """Convert a raw number to 100M CNY scale."""
    return value / 1e8


def safe_float(value, default=0.0):
    """Safely convert *value* to float."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Chart 1 – Key financial metrics comparison (financial_overview.png)
# ---------------------------------------------------------------------------
def chart_financial_overview(data, output_dir):
    """Grouped bar chart of key financial metrics (in 100M CNY)."""
    labels = [
        "Revenue",
        "Cost of Sales",
        "Net Profit",
        "Total Assets",
        "Total Liabilities",
        "Shareholders' Equity",
    ]
    keys = [
        "revenue",
        "cost_of_sales",
        "net_profit",
        "total_assets",
        "total_liabilities",
        "equity",
    ]
    current_values = [format_yi(safe_float(data.get(k))) for k in keys]

    has_prev = any(data.get(f"prev_{k}") is not None for k in keys[:3])
    prev_keys = [
        "prev_revenue",
        "prev_cost_of_sales",
        "prev_net_profit",
        None,
        None,
        None,
    ]

    fig, ax = plt.subplots(figsize=(10, 6))

    bar_width = 0.35
    x_positions = list(range(len(labels)))

    if has_prev:
        prev_values = []
        for pk in prev_keys:
            if pk is not None and data.get(pk) is not None:
                prev_values.append(format_yi(safe_float(data.get(pk))))
            else:
                prev_values.append(0)

        x_curr = [x + bar_width / 2 for x in x_positions]
        x_prev = [x - bar_width / 2 for x in x_positions]

        year = data.get("year", "Current")
        try:
            prev_year = str(int(year) - 1)
        except (ValueError, TypeError):
            prev_year = "Prior"

        bars_prev = ax.bar(
            x_prev,
            prev_values,
            width=bar_width,
            label=f"{prev_year}",
            color=COLOR_LIGHT_BLUE,
            edgecolor="white",
            linewidth=0.5,
        )
        bars_curr = ax.bar(
            x_curr,
            current_values,
            width=bar_width,
            label=f"{year}",
            color=COLOR_NAVY,
            edgecolor="white",
            linewidth=0.5,
        )

        # Value labels for current year
        for bar in bars_curr:
            height = bar.get_height()
            if height != 0:
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    height,
                    f"{height:.1f}",
                    ha="center",
                    va="bottom",
                    fontsize=8,
                    color=COLOR_DARK,
                )
        # Value labels for previous year (non-zero only)
        for bar in bars_prev:
            height = bar.get_height()
            if height != 0:
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    height,
                    f"{height:.1f}",
                    ha="center",
                    va="bottom",
                    fontsize=8,
                    color=COLOR_LIGHT_BLUE,
                )
        ax.legend(loc="upper right", fontsize=9)
    else:
        colors = [
            COLOR_NAVY,
            COLOR_DARK,
            COLOR_ACCENT,
            COLOR_PURPLE,
            COLOR_GREEN,
            COLOR_LIGHT_BLUE,
        ]
        bars = ax.bar(
            x_positions,
            current_values,
            width=bar_width * 1.5,
            color=colors,
            edgecolor="white",
            linewidth=0.5,
        )
        for bar in bars:
            height = bar.get_height()
            if height != 0:
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    height,
                    f"{height:.1f}",
                    ha="center",
                    va="bottom",
                    fontsize=8,
                    color=COLOR_DARK,
                )

    ax.set_xticks(x_positions)
    ax.set_xticklabels(labels, fontsize=10)
    ax.set_ylabel("Amount (100M CNY)", fontsize=11)

    company = data.get("company_name", "")
    year_str = data.get("year", "")
    ax.set_title(
        f"{company} {year_str} Key Financial Metrics Comparison",
        fontsize=14,
        fontweight="bold",
    )

    ax.grid(axis="y", linestyle="--", alpha=0.4, color="#cccccc")
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    plt.tight_layout()
    path = os.path.join(output_dir, "financial_overview.png")
    fig.savefig(path, dpi=CHART_DPI, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# Chart 2 – Profitability metrics (profitability.png)
# ---------------------------------------------------------------------------
def chart_profitability(data, output_dir):
    """Bar chart of profitability / efficiency ratios (%)."""
    revenue = safe_float(data.get("revenue"), default=None)
    cost_of_sales = safe_float(data.get("cost_of_sales"), default=None)
    net_profit = safe_float(data.get("net_profit"), default=None)
    equity = safe_float(data.get("equity"), default=None)
    total_assets = safe_float(data.get("total_assets"), default=None)
    total_liabilities = safe_float(data.get("total_liabilities"), default=None)
    operating_cash_flow = safe_float(data.get("operating_cash_flow"), default=None)

    # Calculate ratios
    gross_margin = 0.0
    if revenue and cost_of_sales is not None:
        gross_margin = (revenue - cost_of_sales) / revenue * 100

    net_margin = 0.0
    if revenue and net_profit is not None:
        net_margin = net_profit / revenue * 100

    roe = 0.0
    if equity and net_profit is not None:
        roe = net_profit / equity * 100

    debt_ratio = 0.0
    if total_assets and total_liabilities is not None:
        debt_ratio = total_liabilities / total_assets * 100

    cash_ratio = 0.0
    if net_profit and operating_cash_flow is not None:
        cash_ratio = operating_cash_flow / net_profit * 100
        # Cap at 200% for display readability
        cash_ratio = min(cash_ratio, 200.0)

    labels = [
        "Gross Margin",
        "Net Margin",
        "ROE",
        "Debt-to-Asset Ratio",
        "Cash Conversion Ratio",
    ]
    values = [gross_margin, net_margin, roe, debt_ratio, cash_ratio]
    colors = [COLOR_NAVY, COLOR_LIGHT_BLUE, COLOR_GREEN, COLOR_ACCENT, COLOR_PURPLE]

    fig, ax = plt.subplots(figsize=(10, 6))

    bars = ax.barh(
        labels, values, color=colors, edgecolor="white", linewidth=0.5, height=0.55
    )

    for bar, val in zip(bars, values):
        ax.text(
            bar.get_width() + 0.5,
            bar.get_y() + bar.get_height() / 2,
            f"{val:.1f}%",
            ha="left",
            va="center",
            fontsize=10,
            fontweight="bold",
            color=COLOR_DARK,
        )

    ax.set_xlabel("Percentage (%)", fontsize=11)

    company = data.get("company_name", "")
    year_str = data.get("year", "")
    ax.set_title(
        f"{company} {year_str} Profitability Metrics",
        fontsize=14,
        fontweight="bold",
    )

    ax.grid(axis="x", linestyle="--", alpha=0.4, color="#cccccc")
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Give some right margin for the labels
    max_val = max(values) if values else 100
    ax.set_xlim(0, max_val * 1.2 if max_val > 0 else 100)

    plt.tight_layout()
    path = os.path.join(output_dir, "profitability.png")
    fig.savefig(path, dpi=CHART_DPI, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# Chart 3 – Asset structure breakdown (asset_structure.png)
# ---------------------------------------------------------------------------
def chart_asset_structure(data, output_dir):
    """Donut chart showing liabilities vs equity composition."""
    total_liabilities = safe_float(data.get("total_liabilities"))
    equity = safe_float(data.get("equity"))

    total = total_liabilities + equity
    if total == 0:
        # Avoid division by zero — create a placeholder chart
        total = 1

    liab_yi = format_yi(total_liabilities)
    equity_yi = format_yi(equity)

    labels = [
        f"Liabilities\n{liab_yi:.1f} 100M CNY",
        f"Shareholders' Equity\n{equity_yi:.1f} 100M CNY",
    ]
    sizes = [total_liabilities, equity]
    colors = [COLOR_ACCENT, COLOR_NAVY]
    explode = (0.03, 0.03)

    fig, ax = plt.subplots(figsize=(8, 8))

    wedges, texts, autotexts = ax.pie(
        sizes,
        labels=labels,
        autopct="%1.1f%%",
        startangle=90,
        colors=colors,
        explode=explode,
        pctdistance=0.75,
        labeldistance=1.15,
        textprops={"fontsize": 12},
        wedgeprops={"linewidth": 2, "edgecolor": "white"},
    )

    for autotext in autotexts:
        autotext.set_fontsize(13)
        autotext.set_fontweight("bold")
        autotext.set_color("white")

    # Draw a white circle in the centre for a donut effect
    centre_circle = plt.Circle((0, 0), 0.55, fc="white")
    ax.add_artist(centre_circle)

    # Centre text
    total_yi = format_yi(total)
    ax.text(
        0,
        0.05,
        "Total Assets",
        ha="center",
        va="center",
        fontsize=13,
        color="#666666",
    )
    ax.text(
        0,
        -0.1,
        f"{total_yi:.1f} 100M CNY",
        ha="center",
        va="center",
        fontsize=16,
        fontweight="bold",
        color=COLOR_DARK,
    )

    company = data.get("company_name", "")
    year_str = data.get("year", "")
    ax.set_title(
        f"{company} {year_str} Asset Structure Breakdown",
        fontsize=14,
        fontweight="bold",
        pad=20,
    )

    ax.axis("equal")
    plt.tight_layout()
    path = os.path.join(output_dir, "asset_structure.png")
    fig.savefig(path, dpi=CHART_DPI, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------
def generate_charts(data, output_dir):
    """Generate all 3 charts and return a manifest dict."""
    setup_font()

    paths = {
        "financial_overview": chart_financial_overview(data, output_dir),
        "profitability": chart_profitability(data, output_dir),
        "asset_structure": chart_asset_structure(data, output_dir),
    }
    return paths


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            json.dumps(
                {"error": "Please provide JSON data as an argument."},
                ensure_ascii=False,
            )
        )
        sys.exit(1)

    try:
        arg = sys.argv[1]
        parsed = json.loads(arg)

        # Unwrap single-key wrappers like {"financial_data": {...}} or {"data": {...}}
        if isinstance(parsed, dict):
            if len(parsed) == 1:
                only_value = next(iter(parsed.values()))
                if isinstance(only_value, dict):
                    parsed = only_value

        # Use OUTPUT_DIR env var if set (injected by manage.py),
        # otherwise fall back to the script's own directory.
        out_dir = os.environ.get("OUTPUT_DIR") or os.path.dirname(
            os.path.abspath(__file__)
        )
        chart_paths = generate_charts(parsed, out_dir)
        result = {
            "charts": chart_paths,
            "output_dir": out_dir,
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))

    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        sys.exit(1)
