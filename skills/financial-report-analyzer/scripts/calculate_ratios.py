import json
import sys
from datetime import datetime


def format_amount(value):
    """Auto-scale a numeric amount to 亿元, 万元, or 元.

    Returns a formatted string like "105.00亿元", "1050.50万元", or "3500.00元".
    Returns "N/A" when *value* is ``None`` or not a valid number.
    """
    if value is None:
        return "N/A"
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "N/A"

    abs_val = abs(value)
    if abs_val >= 1e8:
        return f"{value / 1e8:.2f}亿元"
    if abs_val >= 1e4:
        return f"{value / 1e4:.2f}万元"
    return f"{value:.2f}元"


def format_growth(current, previous):
    """Calculate YoY growth and return (formatted_string, css_class).

    * Returns ("+15.3%", "highlight-positive") when growth >= 0.
    * Returns ("-5.2%", "highlight-negative") when growth < 0.
    * Returns ("N/A", "") when either value is missing or previous is zero.
    """
    if current is None or previous is None:
        return "N/A", ""
    try:
        current = float(current)
        previous = float(previous)
    except (TypeError, ValueError):
        return "N/A", ""

    if previous == 0:
        return "N/A", ""

    growth = (current - previous) / abs(previous) * 100
    if growth >= 0:
        return f"+{growth:.1f}%", "highlight-positive"
    return f"{growth:.1f}%", "highlight-negative"


def format_pct(value):
    """Format a ratio (0-1 scale or already percent-scale) as "XX.XX%".

    Assumes *value* is on a 0-1 scale (e.g. 0.2857 → "28.57%").
    Returns "N/A" when *value* is ``None``.
    """
    if value is None:
        return "N/A"
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "N/A"
    return f"{value * 100:.2f}%"


def format_pp_change(current, previous):
    """Calculate percentage-point change and return (formatted_string, css_class).

    Both *current* and *previous* should be ratios on a 0-1 scale.
    Returns ("+2.3pp", "highlight-positive") or ("-1.5pp", "highlight-negative").
    Returns ("N/A", "") when either value is missing.
    """
    if current is None or previous is None:
        return "N/A", ""
    try:
        current = float(current)
        previous = float(previous)
    except (TypeError, ValueError):
        return "N/A", ""

    change = (current - previous) * 100  # convert to percentage points
    if change >= 0:
        return f"+{change:.2f}pp", "highlight-positive"
    return f"{change:.2f}pp", "highlight-negative"


def calculate_template_data(data):
    """Turn raw financial data into a dict of ALL template placeholder values.

    Parameters
    ----------
    data : dict
        Raw financial data as produced by ``extract_financials.py``.

    Returns
    -------
    dict
        Keys correspond 1-to-1 with ``{{PLACEHOLDER}}`` names in the HTML
        report template.  Every key listed in the spec is always present.
    """

    # ------------------------------------------------------------------ helpers
    def _get(key, default=None):
        """Fetch a numeric value, returning *default* for None / missing."""
        v = data.get(key)
        if v is None:
            return default
        try:
            return float(v)
        except (TypeError, ValueError):
            return default

    # ----------------------------------------------------------- raw values
    revenue = _get("revenue")
    net_profit = _get("net_profit")
    equity = _get("equity")
    cost_of_sales = _get("cost_of_sales")
    non_recurring_net_profit = _get("non_recurring_net_profit")

    prev_revenue = _get("prev_revenue")
    prev_net_profit = _get("prev_net_profit")
    prev_non_recurring = _get("prev_non_recurring_net_profit")
    prev_gross_margin = _get("prev_gross_margin")  # ratio 0-1
    prev_roe = _get("prev_roe")  # ratio 0-1
    prev_cost = _get("prev_cost_of_sales")
    prev_equity = _get("prev_equity")
    if prev_gross_margin is None and prev_revenue and prev_cost is not None:
        prev_gross_margin = (prev_revenue - prev_cost) / prev_revenue
    if prev_roe is None and prev_equity and prev_net_profit is not None:
        prev_roe = prev_net_profit / prev_equity

    # -------------------------------------------------------- derived ratios
    gross_margin = None
    if revenue is not None and cost_of_sales is not None and revenue != 0:
        gross_margin = (revenue - cost_of_sales) / revenue

    roe = None
    if net_profit is not None and equity is not None and equity != 0:
        roe = net_profit / equity

    # -------------------------------------------------------- formatted values
    result = {}

    # --- Basic info ---
    result["COMPANY_NAME"] = data.get("company_name") or "未知公司"
    result["YEAR"] = str(data.get("report_year") or data.get("year") or "N/A")
    result["DATE"] = data.get("report_date") or datetime.now().strftime("%Y年%m月%d日")

    # --- Revenue ---
    result["REVENUE"] = format_amount(revenue)
    rev_growth, rev_cls = format_growth(revenue, prev_revenue)
    result["REVENUE_GROWTH"] = rev_growth
    result["REVENUE_GROWTH_CLASS"] = rev_cls
    result["REVENUE_INDUSTRY_AVG"] = "N/A"

    # --- Net profit ---
    result["NET_PROFIT"] = format_amount(net_profit)
    np_growth, np_cls = format_growth(net_profit, prev_net_profit)
    result["NET_PROFIT_GROWTH"] = np_growth
    result["NET_PROFIT_GROWTH_CLASS"] = np_cls
    result["NET_PROFIT_INDUSTRY_AVG"] = "N/A"

    # --- Non-recurring net profit ---
    result["NON_RECURRING_NET_PROFIT"] = format_amount(non_recurring_net_profit)
    nr_growth, nr_cls = format_growth(non_recurring_net_profit, prev_non_recurring)
    result["NON_RECURRING_GROWTH"] = nr_growth
    result["NON_RECURRING_GROWTH_CLASS"] = nr_cls
    result["NON_RECURRING_INDUSTRY_AVG"] = "N/A"

    # --- Gross margin ---
    result["GROSS_MARGIN"] = format_pct(gross_margin)
    gm_change, gm_cls = format_pp_change(gross_margin, prev_gross_margin)
    result["GROSS_MARGIN_CHANGE"] = gm_change
    result["GROSS_MARGIN_CHANGE_CLASS"] = gm_cls
    result["GROSS_MARGIN_INDUSTRY_AVG"] = "N/A"

    # --- ROE ---
    result["ROE"] = format_pct(roe)
    roe_change, roe_cls = format_pp_change(roe, prev_roe)
    result["ROE_CHANGE"] = roe_change
    result["ROE_CHANGE_CLASS"] = roe_cls
    result["ROE_INDUSTRY_AVG"] = "N/A"

    # Retain machine-readable meaning and inputs separately from presentation.
    # ROE here is net profit / period-end parent equity, not weighted-average ROE.
    result["FINANCIAL_METRICS"] = {
        "net_margin": {
            "value": net_profit / revenue
            if revenue and net_profit is not None
            else None,
            "unit": "ratio",
            "period": data.get("report_year"),
            "formula": "parent_net_profit / revenue",
            "inputs": ["net_profit", "revenue"],
        },
        "debt_ratio": {
            "value": _get("total_liabilities") / _get("total_assets")
            if _get("total_assets") and _get("total_liabilities") is not None
            else None,
            "unit": "ratio",
            "period": data.get("report_year"),
            "formula": "total_liabilities / total_assets",
            "inputs": ["total_liabilities", "total_assets"],
        },
        "cash_profit_ratio": {
            "value": _get("operating_cash_flow") / net_profit
            if net_profit and _get("operating_cash_flow") is not None
            else None,
            "unit": "ratio",
            "period": data.get("report_year"),
            "formula": "operating_cash_flow / parent_net_profit",
            "inputs": ["operating_cash_flow", "net_profit"],
        },
        "gross_margin": {
            "value": gross_margin,
            "unit": "ratio",
            "period": data.get("report_year"),
            "formula": "(revenue - cost_of_sales) / revenue",
            "inputs": ["revenue", "cost_of_sales"],
        },
        "gross_margin_change_pp": {
            "value": (gross_margin - prev_gross_margin) * 100
            if gross_margin is not None and prev_gross_margin is not None
            else None,
            "unit": "percentage_point",
            "period": data.get("report_year"),
            "formula": "(gross_margin - previous_gross_margin) * 100",
            "inputs": [
                "revenue",
                "cost_of_sales",
                "prev_revenue",
                "prev_cost_of_sales",
            ],
        },
        "roe_period_end": {
            "value": roe,
            "unit": "ratio",
            "period": data.get("report_year"),
            "formula": "net_profit / period_end_parent_equity",
            "inputs": ["net_profit", "equity"],
        },
        "roe_period_end_change_pp": {
            "value": (roe - prev_roe) * 100
            if roe is not None and prev_roe is not None
            else None,
            "unit": "percentage_point",
            "period": data.get("report_year"),
            "formula": "(roe_period_end - previous_roe_period_end) * 100",
            "inputs": ["net_profit", "equity", "prev_net_profit", "prev_equity"],
        },
    }

    # --- Analysis placeholders (LLM fills these) ---
    result["PROFITABILITY_ANALYSIS"] = "N/A"
    result["SOLVENCY_ANALYSIS"] = "N/A"
    result["EFFICIENCY_ANALYSIS"] = "N/A"
    result["CASHFLOW_ANALYSIS"] = "N/A"
    result["ADVANTAGES_LIST"] = "N/A"
    result["RISKS_LIST"] = "N/A"
    result["OVERALL_ASSESSMENT"] = "N/A"

    return result


if __name__ == "__main__":
    if len(sys.argv) > 1:
        try:
            arg = sys.argv[1]
            parsed = json.loads(arg)

            # Handle various input shapes from the LLM/adapter:
            #   {"financial_data": {"revenue": ...}}  -> unwrap
            #   {"data": {"revenue": ...}}            -> unwrap
            #   {"revenue": ..., "net_profit": ...}   -> use directly
            if isinstance(parsed, dict):
                # If wrapped in a single key whose value is also a dict,
                # unwrap it.
                if len(parsed) == 1:
                    only_value = next(iter(parsed.values()))
                    if isinstance(only_value, dict):
                        parsed = only_value

            result = calculate_template_data(parsed)
            print(json.dumps(result, indent=2, ensure_ascii=False))
        except Exception as e:
            print(json.dumps({"error": str(e)}, ensure_ascii=False))
    else:
        print("Please provide JSON data as an argument.")
