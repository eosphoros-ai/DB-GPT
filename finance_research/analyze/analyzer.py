"""Financial analysis: trends, YoY growth, and cross-company comparison."""

from typing import Dict, List

import pandas as pd


def _to_series(rows: List[dict]) -> pd.Series:
    """Build a period-indexed Series from ``{fiscal_period, value}`` rows.

    Duplicate fiscal periods (e.g. the same metric reported by two sources) are
    collapsed to a single observation so growth calculations never measure
    source-to-source variance. ``keep="last"`` gives a deterministic result:
    the last-seen source value wins.
    """
    if not rows:
        return pd.Series(dtype=float)
    df = pd.DataFrame(rows)
    df = df.sort_values("fiscal_period")
    df = df.drop_duplicates(subset="fiscal_period", keep="last")
    return pd.Series(df["value"].values, index=df["fiscal_period"])


def compute_yoy(series: pd.Series) -> pd.Series:
    """Compute year-over-year growth (%) for a period-indexed series."""
    if len(series) < 2:
        return pd.Series(dtype=float)
    return series.pct_change() * 100


def compute_qoq(series: pd.Series) -> pd.Series:
    """Compute quarter-over-quarter growth (%) for a quarterly series.

    Semantically identical to :func:`compute_yoy` (``pct_change``), but named
    explicitly and intended for single-quarter, consecutive-quarter series.
    """
    if len(series) < 2:
        return pd.Series(dtype=float)
    return series.pct_change() * 100


def derive_single_quarter(cumulative: pd.Series) -> pd.Series:
    """Derive single-quarter values from a cumulative (YTD) quarterly series.

    Chinese A-share interim figures are year-to-date. Single-quarter values
    are recovered by differencing consecutive cumulative periods; the first
    quarter of each year is already single-quarter (YTD == single quarter).
    The input series must be sorted ascending by fiscal period.
    """
    if len(cumulative) < 2:
        return cumulative.copy()
    s = cumulative.sort_index()
    single = s.diff()
    for i, period in enumerate(s.index):
        if i == 0 or str(period).endswith("Q1") or str(period).endswith("-03-31"):
            single.iloc[i] = s.iloc[i]
    return single


def analyze_company_metrics(metrics: List[dict]) -> Dict[str, pd.Series]:
    """Group metric rows by name and reporting frequency.

    Annual and quarterly rows are partitioned into separate series so a
    quarterly value is never trended against an annual value. Annual series
    keep the bare metric name; other frequencies get a ``(<report_type>)``
    suffix.
    """
    by_key: Dict[tuple, List[dict]] = {}
    for m in metrics:
        report_type = m.get("report_type") or "annual"
        key = (m["metric_name"], report_type)
        by_key.setdefault(key, []).append(
            {"fiscal_period": m["fiscal_period"], "value": m["metric_value"]}
        )
    result = {}
    for (name, report_type), rows in by_key.items():
        series = _to_series(rows)
        label = name if report_type == "annual" else f"{name} ({report_type})"
        result[label] = series
    return result


def compare_companies(
    company_a: Dict[str, pd.Series], company_b: Dict[str, pd.Series]
) -> pd.DataFrame:
    """Build a comparison table of shared metrics between two companies."""
    shared = set(company_a) & set(company_b)
    rows = []
    for name in sorted(shared):
        a = company_a[name]
        b = company_b[name]
        rows.append(
            {
                "metric": name,
                "company_a_latest": a.iloc[-1] if len(a) else None,
                "company_b_latest": b.iloc[-1] if len(b) else None,
                "company_a_mean": a.mean() if len(a) else None,
                "company_b_mean": b.mean() if len(b) else None,
            }
        )
    return pd.DataFrame(rows)
