import pandas as pd
import numpy as np
import os
import json
import warnings
import sys

warnings.filterwarnings("ignore")


def log(*args, **kwargs):
    """Send logs to stderr to avoid polluting JSON stdout output."""
    print(*args, file=sys.stderr, **kwargs)


def safe_div(numerator, denominator):
    if denominator in (0, None):
        return 0.0
    return float(numerator) / float(denominator)


def classify_skewness(value):
    abs_val = abs(value)
    if abs_val >= 1:
        return "Strongly skewed"
    if abs_val >= 0.5:
        return "Moderately skewed"
    return "Approximately symmetric"


def classify_cv(value):
    if value >= 100:
        return "Very high volatility"
    if value >= 50:
        return "High volatility"
    if value >= 20:
        return "Moderate volatility"
    return "Low volatility"


def select_primary_metric(df, numeric_cols):
    if not numeric_cols:
        return None

    preferred_keywords = [
        "score",
        "value",
        "amount",
        "sales",
        "revenue",
        "profit",
        "price",
        "rate",
        "index",
        "metric",
        "total",
        "count",
    ]
    skip_keywords = ["rank", "ranking", "id", "index_id"]

    candidates = []
    for col in numeric_cols:
        col_lower = str(col).lower()
        unique_cnt = int(df[col].nunique())
        score = 0
        if unique_cnt > 5:
            score += 2
        if not any(kw in col_lower for kw in skip_keywords):
            score += 2
        if any(kw in col_lower for kw in preferred_keywords):
            score += 4
        series = df[col].dropna()
        if len(series) > 0:
            score += 1
            if float(series.std()) > 0:
                score += 1
        candidates.append((score, col))

    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1] if candidates else numeric_cols[0]


def select_label_col(df):
    for col in df.columns:
        if df[col].dtype == "object" and df[col].nunique() > 1:
            return col
    return None


def analyze_csv(file_path):
    """
    Analyze a CSV file and extract data structures for ECharts rendering
    and statistical summaries for LLM analysis.
    Output includes: overview, data_quality, distributions, correlations,
    categories, time_series, scatter, stats_table, box_plots, outliers, top_bottom
    """
    try:
        log(f"Reading file: {file_path}")
        ext = os.path.splitext(file_path)[1].lower()
        if ext in (".xls", ".xlsx"):
            df = pd.read_excel(file_path)
        elif ext == ".tsv":
            df = pd.read_csv(file_path, sep="\t")
        else:
            df = pd.read_csv(file_path)

        # ==========================================
        # 1. Basic overview data
        # ==========================================
        total_cells = int(df.shape[0] * df.shape[1])
        missing_cells = int(df.isnull().sum().sum())
        missing_pct = (
            round((missing_cells / total_cells) * 100, 2) if total_cells > 0 else 0
        )
        duplicate_rows = int(df.duplicated().sum())

        overview = {
            "rows": int(df.shape[0]),
            "cols": int(df.shape[1]),
            "missing_cells": missing_cells,
            "missing_pct": missing_pct,
            "duplicate_rows": duplicate_rows,
            "memory_kb": round(df.memory_usage(deep=True).sum() / 1024, 1),
        }

        # ==========================================
        # 1b. Data quality analysis (missing rate + dtypes per column)
        # ==========================================
        data_quality = {
            "columns": [],
            "missing_rates": [],
            "dtypes": [],
            "unique_counts": [],
            "dtype_summary": {},
        }
        for col in df.columns:
            data_quality["columns"].append(str(col))
            col_missing = int(df[col].isnull().sum())
            rate = round((col_missing / len(df)) * 100, 1) if len(df) > 0 else 0
            data_quality["missing_rates"].append(rate)
            data_quality["dtypes"].append(str(df[col].dtype))
            data_quality["unique_counts"].append(int(df[col].nunique()))

        # dtype breakdown for overview
        dtype_counts = {}
        for dt in data_quality["dtypes"]:
            cat = (
                "numeric"
                if "int" in dt or "float" in dt
                else ("datetime" if "datetime" in dt else "text")
            )
            dtype_counts[cat] = dtype_counts.get(cat, 0) + 1
        data_quality["dtype_summary"] = dtype_counts
        missing_by_col = sorted(
            [
                (col, rate, int(df[col].isnull().sum()))
                for col, rate in zip(df.columns, data_quality["missing_rates"])
            ],
            key=lambda x: x[1],
            reverse=True,
        )

        # ==========================================
        # 2. Numeric column analysis (histogram distributions & correlations)
        # ==========================================
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        primary_metric = select_primary_metric(df, numeric_cols)
        label_col = select_label_col(df)
        distributions = {}
        correlations = {"cols": numeric_cols, "data": []}
        numeric_summary = {}
        correlation_highlights = {"positive": [], "negative": []}

        if numeric_cols:
            # Use up to the first 8 numeric columns for distribution charts
            for col in numeric_cols[:8]:
                s = df[col].dropna()
                if len(s) > 0:
                    # Compute histogram with numpy (10 bins)
                    hist, bin_edges = np.histogram(s, bins=10)
                    bins = [
                        f"{bin_edges[i]:.1f}~{bin_edges[i + 1]:.1f}"
                        for i in range(len(hist))
                    ]
                    distributions[col] = {
                        "bins": bins,
                        "counts": [int(x) for x in hist],
                    }
                    # Skewness & Kurtosis
                    skew_val = float(s.skew()) if len(s) > 2 else 0.0
                    kurt_val = float(s.kurtosis()) if len(s) > 3 else 0.0
                    mean_val = float(s.mean())
                    std_val = float(s.std())
                    cv = (
                        round(abs(std_val / mean_val) * 100, 1)
                        if mean_val != 0
                        else 0.0
                    )
                    spread = float(s.max()) - float(s.min())
                    numeric_summary[col] = {
                        "min": float(s.min()),
                        "max": float(s.max()),
                        "mean": round(mean_val, 4),
                        "median": float(s.median()),
                        "std": round(std_val, 4),
                        "q25": float(s.quantile(0.25)),
                        "q75": float(s.quantile(0.75)),
                        "p5": float(s.quantile(0.05)),
                        "p95": float(s.quantile(0.95)),
                        "cv": cv,
                        "spread": round(spread, 4),
                        "skewness": round(skew_val, 3),
                        "kurtosis": round(kurt_val, 3),
                    }

            # Correlation matrix (all numeric columns)
            if len(numeric_cols) > 1:
                corr_df = df[numeric_cols].corr(method="pearson").fillna(0).round(2)  # type: ignore[call-overload]
                corr_pairs = []
                for i, col1 in enumerate(numeric_cols):
                    for j, col2 in enumerate(numeric_cols):
                        correlations["data"].append([i, j, float(corr_df.iloc[i, j])])
                        if i < j:
                            corr_pairs.append((col1, col2, float(corr_df.iloc[i, j])))
                corr_pairs = sorted(corr_pairs, key=lambda x: x[2], reverse=True)
                correlation_highlights["positive"] = corr_pairs[:3]
                correlation_highlights["negative"] = sorted(
                    corr_pairs, key=lambda x: x[2]
                )[:3]

        # ==========================================
        # 3. Categorical column analysis (pie/bar charts + entropy/concentration)
        # ==========================================
        categorical_cols = df.select_dtypes(
            include=["object", "category"]
        ).columns.tolist()
        categories = {}
        cat_summary = {}
        segment_breakdown = []
        segment_comparison = {}

        if categorical_cols:
            # Use up to the first 6 categorical columns
            for col in categorical_cols[:6]:
                if df[col].nunique() <= 50:
                    val_counts = df[col].value_counts().head(10)
                    if len(val_counts) > 0:
                        categories[col] = {
                            "labels": [str(x) for x in val_counts.index.tolist()],
                            "values": [int(x) for x in val_counts.values],
                        }
                        top1 = val_counts.index[0]
                        top1_count = val_counts.values[0]
                        n_unique = df[col].nunique()
                        total_non_null = int(df[col].notna().sum())
                        # Shannon entropy (log2)
                        probs = np.array(val_counts.values, dtype=float)
                        if total_non_null > 0:
                            probs = probs / float(total_non_null)
                        entropy = -float(np.sum(probs * np.log2(probs + 1e-12)))
                        # Concentration ratio: top-3 share
                        top3_share = (
                            round(val_counts.head(3).sum() / total_non_null * 100, 1)
                            if total_non_null > 0
                            else 0
                        )
                        cat_summary[col] = {
                            "n_unique": n_unique,
                            "top1": str(top1),
                            "top1_count": int(top1_count),
                            "top1_share": round(
                                safe_div(top1_count, total_non_null) * 100, 1
                            )
                            if total_non_null > 0
                            else 0,
                            "entropy": round(entropy, 3),
                            "top3_share": top3_share,
                        }

            if primary_metric:
                for col in categorical_cols[:3]:
                    grouped = (
                        df[[col, primary_metric]]
                        .dropna()
                        .groupby(col)[primary_metric]
                        .agg(["count", "mean", "sum"])
                    )
                    grp = (
                        pd.DataFrame(grouped)
                        .reset_index()
                        .sort_values("sum", ascending=False)
                        .head(5)
                    )
                    if not grp.empty:
                        segment_breakdown.append(
                            {
                                "dimension": col,
                                "metric": primary_metric,
                                "leaders": [
                                    {
                                        "name": str(row[col]),
                                        "count": int(row["count"]),
                                        "mean": round(float(row["mean"]), 2),
                                        "sum": round(float(row["sum"]), 2),
                                    }
                                    for _, row in grp.iterrows()
                                ],
                            }
                        )
                if segment_breakdown:
                    lead_segment = segment_breakdown[0]
                    leaders = lead_segment["leaders"][:8]
                    segment_comparison = {
                        "dimension": lead_segment["dimension"],
                        "metric": lead_segment["metric"],
                        "labels": [item["name"] for item in leaders],
                        "values": [item["mean"] for item in leaders],
                        "counts": [item["count"] for item in leaders],
                    }

        # ==========================================
        # 4. Time series analysis (supports multiple numeric columns)
        # ==========================================
        time_series = {"name": "", "dates": [], "values": []}
        time_series_multi = []  # Additional time series data
        time_series_diagnostics = {}

        if numeric_cols:
            date_col = None
            for col in df.columns:
                if df[col].dtype == "object":
                    try:
                        pd.to_datetime(df[col].dropna().head(100))
                        date_col = col
                        break
                    except Exception:
                        pass

            if date_col:
                df_ts = df.copy()
                df_ts[date_col] = pd.to_datetime(df_ts[date_col], errors="coerce")
                df_ts = df_ts.dropna(subset=[date_col])

                # Primary time series: first numeric column
                num_col = primary_metric or numeric_cols[0]
                df_ts_main = df_ts.dropna(subset=[num_col]).copy()
                if not df_ts_main.empty:
                    df_ts_main = df_ts_main.set_index(date_col)
                    try:
                        monthly = df_ts_main[num_col].resample("M").mean().dropna()
                        if len(monthly) < 3:
                            monthly = df_ts_main[num_col].resample("D").mean().dropna()
                        monthly = monthly.tail(100)

                        time_series["name"] = num_col
                        time_series["dates"] = [
                            x.strftime("%Y-%m-%d") for x in monthly.index
                        ]
                        time_series["values"] = [
                            round(float(x), 2) for x in monthly.values
                        ]
                        if len(monthly) >= 2:
                            idx = np.arange(len(monthly), dtype=float)
                            slope = float(
                                np.polyfit(idx, monthly.values.astype(float), 1)[0]
                            )
                            first_val = float(monthly.iloc[0])
                            last_val = float(monthly.iloc[-1])
                            peak_idx = int(np.argmax(monthly.values))
                            trough_idx = int(np.argmin(monthly.values))
                            pct_change = (
                                safe_div(last_val - first_val, abs(first_val)) * 100
                            )
                            time_series_diagnostics = {
                                "date_col": date_col,
                                "metric": num_col,
                                "points": int(len(monthly)),
                                "start": round(first_val, 2),
                                "end": round(last_val, 2),
                                "change_pct": round(pct_change, 1),
                                "slope": round(slope, 4),
                                "volatility_pct": round(
                                    safe_div(monthly.std(), abs(monthly.mean())) * 100,
                                    1,
                                )
                                if float(monthly.mean()) != 0
                                else 0,
                                "peak_date": monthly.index[peak_idx].strftime(
                                    "%Y-%m-%d"
                                ),
                                "peak_value": round(float(monthly.iloc[peak_idx]), 2),
                                "trough_date": monthly.index[trough_idx].strftime(
                                    "%Y-%m-%d"
                                ),
                                "trough_value": round(
                                    float(monthly.iloc[trough_idx]), 2
                                ),
                            }
                    except Exception as e:
                        log(f"Time series processing failed: {e}")

                # Additional time series (up to 2 more)
                for extra_col in numeric_cols[1:3]:
                    df_ts_extra = df_ts.dropna(subset=[extra_col]).copy()
                    if not df_ts_extra.empty:
                        df_ts_extra = df_ts_extra.set_index(date_col)
                        try:
                            monthly_e = (
                                df_ts_extra[extra_col].resample("M").mean().dropna()
                            )
                            if len(monthly_e) < 3:
                                monthly_e = (
                                    df_ts_extra[extra_col].resample("D").mean().dropna()
                                )
                            monthly_e = monthly_e.tail(100)
                            if len(monthly_e) >= 2:
                                time_series_multi.append(
                                    {
                                        "name": extra_col,
                                        "dates": [
                                            x.strftime("%Y-%m-%d")
                                            for x in monthly_e.index
                                        ],
                                        "values": [
                                            round(float(x), 2) for x in monthly_e.values
                                        ],
                                    }
                                )
                        except Exception:
                            pass

        # ==========================================
        # 5. Scatter plot data (first two numeric columns)
        # ==========================================
        scatter = {}
        if len(numeric_cols) >= 2:
            if primary_metric and correlations["data"]:
                corr_candidates = []
                for i, j, val in correlations["data"]:
                    left = numeric_cols[i]
                    right = numeric_cols[j]
                    if left == right:
                        continue
                    if left == primary_metric:
                        corr_candidates.append((abs(val), right, primary_metric))
                    elif right == primary_metric:
                        corr_candidates.append((abs(val), left, primary_metric))
                corr_candidates.sort(key=lambda x: x[0], reverse=True)
                if corr_candidates:
                    _, partner, metric = corr_candidates[0]
                    col_x, col_y = partner, metric
                else:
                    col_x, col_y = numeric_cols[0], numeric_cols[1]
            else:
                col_x, col_y = numeric_cols[0], numeric_cols[1]
            df_scatter = df[[col_x, col_y]].dropna()
            # Limit to 500 points to avoid oversized payloads
            if len(df_scatter) > 500:
                df_scatter = df_scatter.sample(500, random_state=42)
            scatter = {
                "x_name": col_x,
                "y_name": col_y,
                "x": [round(float(v), 4) for v in df_scatter[col_x].tolist()],
                "y": [round(float(v), 4) for v in df_scatter[col_y].tolist()],
            }

        # ==========================================
        # 5b. Box plot data — first 8 numeric columns
        # ==========================================
        box_plots = {}
        if numeric_cols:
            for col in numeric_cols[:8]:
                s = df[col].dropna()
                if len(s) > 0:
                    q1 = float(s.quantile(0.25))
                    q3 = float(s.quantile(0.75))
                    iqr = q3 - q1
                    lower_fence = q1 - 1.5 * iqr
                    upper_fence = q3 + 1.5 * iqr
                    outlier_vals = s[(s < lower_fence) | (s > upper_fence)]
                    # Limit outlier points to 50 for rendering
                    outlier_list = [
                        round(float(v), 4)
                        for v in outlier_vals.head(50).tolist()  # type: ignore[union-attr]
                    ]
                    box_plots[col] = {
                        "min": round(float(s.min()), 4),
                        "q1": round(q1, 4),
                        "median": round(float(s.median()), 4),
                        "q3": round(q3, 4),
                        "max": round(float(s.max()), 4),
                        "lower_fence": round(max(float(s.min()), lower_fence), 4),
                        "upper_fence": round(min(float(s.max()), upper_fence), 4),
                        "outliers": outlier_list,
                    }

        # ==========================================
        # 5c. Outlier detection summary (IQR method)
        # ==========================================
        outliers = {}
        if numeric_cols:
            for col in numeric_cols[:8]:
                s = df[col].dropna()
                if len(s) > 0:
                    q1 = float(s.quantile(0.25))
                    q3 = float(s.quantile(0.75))
                    iqr = q3 - q1
                    lower = q1 - 1.5 * iqr
                    upper = q3 + 1.5 * iqr
                    n_outliers = int(((s < lower) | (s > upper)).sum())
                    outliers[col] = {
                        "count": n_outliers,
                        "pct": round((n_outliers / len(s)) * 100, 1)
                        if len(s) > 0
                        else 0,
                        "lower_bound": round(lower, 4),
                        "upper_bound": round(upper, 4),
                    }

        # ==========================================
        # 5d. Top/Bottom rankings (Top5 / Bottom5 for numeric columns)
        # ==========================================
        top_bottom = {}
        ranking_signal = {}
        if numeric_cols and len(df) > 0:
            rank_col = primary_metric or numeric_cols[0]

            if rank_col:
                df_sorted = df.dropna(subset=[rank_col]).sort_values(
                    rank_col, ascending=False
                )
                top5 = df_sorted.head(5)
                bottom5 = df_sorted.tail(5).iloc[::-1]  # reverse so worst first

                def extract_ranked(subset):
                    labels = []
                    values = []
                    for _, row in subset.iterrows():
                        lbl = str(row[label_col])[:30] if label_col else str(row.name)
                        labels.append(lbl)
                        values.append(round(float(row[rank_col]), 2))
                    return {"labels": labels, "values": values}

                top_bottom = {
                    "rank_col": rank_col,
                    "label_col": label_col or "index",
                    "top5": extract_ranked(top5),
                    "bottom5": extract_ranked(bottom5),
                }
                if top_bottom["top5"]["values"] and top_bottom["bottom5"]["values"]:
                    top_avg = float(np.mean(top_bottom["top5"]["values"]))
                    bottom_avg = float(np.mean(top_bottom["bottom5"]["values"]))
                    ranking_signal = {
                        "top_avg": round(top_avg, 2),
                        "bottom_avg": round(bottom_avg, 2),
                        "gap": round(top_avg - bottom_avg, 2),
                    }

        # ==========================================
        # 6b. Primary metric anomaly overview and attribution structure
        # ==========================================
        anomaly_overview = {}
        driver_analysis = {"metric": "", "items": []}
        if primary_metric and primary_metric in df.columns:
            metric_series = df[primary_metric].dropna()
            if len(metric_series) > 0:
                q10 = float(metric_series.quantile(0.1))
                q25 = float(metric_series.quantile(0.25))
                q50 = float(metric_series.quantile(0.5))
                q75 = float(metric_series.quantile(0.75))
                q90 = float(metric_series.quantile(0.9))
                band_labels = ["P0-P25", "P25-P50", "P50-P75", "P75-P100"]
                band_values = [
                    int((metric_series <= q25).sum()),
                    int(((metric_series > q25) & (metric_series <= q50)).sum()),
                    int(((metric_series > q50) & (metric_series <= q75)).sum()),
                    int((metric_series > q75).sum()),
                ]
                top_group = df[df[primary_metric] >= q90]
                bottom_group = df[df[primary_metric] <= q10]
                primary_outlier = outliers.get(primary_metric, {})
                anomaly_overview = {
                    "metric": primary_metric,
                    "mean": round(float(metric_series.mean()), 2),
                    "median": round(float(metric_series.median()), 2),
                    "std": round(float(metric_series.std()), 2),
                    "q10": round(q10, 2),
                    "q90": round(q90, 2),
                    "top_group_size": int(len(top_group)),
                    "bottom_group_size": int(len(bottom_group)),
                    "top_group_mean": round(float(top_group[primary_metric].mean()), 2)
                    if len(top_group) > 0
                    else 0,
                    "bottom_group_mean": round(
                        float(bottom_group[primary_metric].mean()), 2
                    )
                    if len(bottom_group) > 0
                    else 0,
                    "gap": round(
                        float(top_group[primary_metric].mean())
                        - float(bottom_group[primary_metric].mean()),
                        2,
                    )
                    if len(top_group) > 0 and len(bottom_group) > 0
                    else 0,
                    "band_labels": band_labels,
                    "band_values": band_values,
                    "outlier_count": int(primary_outlier.get("count", 0)),
                    "outlier_pct": float(primary_outlier.get("pct", 0)),
                }

                driver_items = []
                metric_std = float(metric_series.std()) if len(metric_series) > 1 else 0
                for col in numeric_cols:
                    if col == primary_metric:
                        continue
                    pair = df[[primary_metric, col]].dropna()
                    if len(pair) < 5:
                        continue
                    metric_pair_series = pair.iloc[:, 0]
                    col_pair_series = pair.iloc[:, 1]
                    corr_val = float(metric_pair_series.corr(col_pair_series))
                    top_mean = (
                        float(top_group[col].mean())
                        if len(top_group) > 0 and col in top_group.columns
                        else 0
                    )
                    bottom_mean = (
                        float(bottom_group[col].mean())
                        if len(bottom_group) > 0 and col in bottom_group.columns
                        else 0
                    )
                    col_std = float(col_pair_series.std()) if len(pair) > 1 else 0
                    gap_ratio = safe_div(
                        top_mean - bottom_mean, col_std if col_std else 1
                    )
                    score = round(
                        min(100, abs(corr_val) * 55 + min(abs(gap_ratio), 3) * 15), 1
                    )
                    driver_items.append(
                        {
                            "name": col,
                            "corr": round(corr_val, 3),
                            "top_mean": round(top_mean, 2),
                            "bottom_mean": round(bottom_mean, 2),
                            "gap_ratio": round(gap_ratio, 2),
                            "score": score,
                        }
                    )
                driver_items.sort(key=lambda x: x["score"], reverse=True)
                driver_analysis = {"metric": primary_metric, "items": driver_items[:8]}

        # ==========================================
        # 6. Statistical summary table (includes P5/P95/CV columns)
        # ==========================================
        stats_table = {"headers": [], "rows": []}
        if numeric_summary:
            stats_table["headers"] = [
                "Variable",
                "Min",
                "P5",
                "Q25",
                "Median",
                "Mean",
                "Q75",
                "P95",
                "Max",
                "Std Dev",
                "CV%",
                "Skewness",
                "Kurtosis",
            ]
            for col, s in numeric_summary.items():
                stats_table["rows"].append(
                    [
                        col,
                        round(s["min"], 2),
                        round(s["p5"], 2),
                        round(s["q25"], 2),
                        round(s["median"], 2),
                        round(s["mean"], 2),
                        round(s["q75"], 2),
                        round(s["p95"], 2),
                        round(s["max"], 2),
                        round(s["std"], 2),
                        s["cv"],
                        s["skewness"],
                        s["kurtosis"],
                    ]
                )

        # ==========================================
        # Build complete JSON data structure for ECharts rendering
        # ==========================================
        chart_data = {
            "overview": overview,
            "data_quality": data_quality,
            "numeric_cols": numeric_cols,
            "distributions": distributions,
            "correlations": correlations,
            "correlation_highlights": correlation_highlights,
            "categories": categories,
            "segment_breakdown": segment_breakdown,
            "time_series": time_series,
            "time_series_multi": time_series_multi,
            "time_series_diagnostics": time_series_diagnostics,
            "scatter": scatter,
            "box_plots": box_plots,
            "outliers": outliers,
            "primary_metric": primary_metric,
            "anomaly_overview": anomaly_overview,
            "driver_analysis": driver_analysis,
            "segment_comparison": segment_comparison,
            "top_bottom": top_bottom,
            "ranking_signal": ranking_signal,
            "stats_table": stats_table,
        }

        chart_data_json_str = json.dumps(chart_data, ensure_ascii=False)

        # ==========================================
        # Build text summary for LLM deep analysis
        # ==========================================
        summary_lines = [
            "==================================================",
            "[Data Overview]",
            f"- Dataset size: {overview['rows']} rows x {overview['cols']} columns",
            f"- Missing values: {overview['missing_cells']} cells missing, overall completeness {100 - overview['missing_pct']}%",
            f"- Duplicate rows: {overview['duplicate_rows']} rows",
            f"- Memory usage: {overview['memory_kb']} KB",
            f"- Numeric columns ({len(numeric_cols)}): {', '.join(numeric_cols[:10])}",
            f"- Categorical columns ({len(categorical_cols)}): {', '.join(categorical_cols[:10])}",
            f"- Data type distribution: {dtype_counts}",
            "",
            "[Quality Focus Areas]",
        ]
        quality_focus = [
            (col, rate, miss_count)
            for col, rate, miss_count in missing_by_col[:5]
            if rate > 0
        ]
        if quality_focus:
            for col, rate, miss_count in quality_focus:
                summary_lines.append(f"- {col}: {miss_count} missing, {rate}% of values")
        else:
            summary_lines.append("- All fields are complete; data integrity is high")

        summary_lines.extend(
            [
                "",
                "[Numeric Feature Statistics (Top 8)]",
            ]
        )
        for col, s in numeric_summary.items():
            summary_lines.append(
                f"- {col}: min={s['min']:.2f}, P5={s['p5']:.2f}, Q25={s['q25']:.2f}, "
                f"median={s['median']:.2f}, mean={s['mean']:.2f}, Q75={s['q75']:.2f}, "
                f"P95={s['p95']:.2f}, max={s['max']:.2f}, std={s['std']:.2f}, "
                f"CV={s['cv']}%({classify_cv(s['cv'])}), spread={s['spread']:.2f}, "
                f"skew={s['skewness']}({classify_skewness(s['skewness'])}), kurtosis={s['kurtosis']}"
            )

        if numeric_summary:
            volatile_cols = sorted(
                numeric_summary.items(), key=lambda x: x[1]["cv"], reverse=True
            )[:3]
            summary_lines.append("")
            summary_lines.append("[Volatility and Skewness Highlights]")
            for col, s in volatile_cols:
                summary_lines.append(
                    f"- {col}: volatility={classify_cv(s['cv'])}, CV={s['cv']}%, skewness={classify_skewness(s['skewness'])}"
                )

        # Outlier summary
        if outliers:
            summary_lines.append("")
            summary_lines.append("[Outlier Detection (IQR Method)]")
            for col, info in outliers.items():
                if info["count"] > 0:
                    summary_lines.append(
                        f"- {col}: {info['count']} outliers ({info['pct']}%), "
                        f"normal range [{info['lower_bound']}, {info['upper_bound']}]"
                    )
            if not any(info["count"] > 0 for info in outliers.values()):
                summary_lines.append("- No significant outliers detected")

        # Top/Bottom rankings
        if top_bottom:
            summary_lines.append("")
            summary_lines.append(
                f"[Top 5 / Bottom 5 Rankings (by {top_bottom['rank_col']})]"
            )
            summary_lines.append(
                f"  Top 5: {list(zip(top_bottom['top5']['labels'], top_bottom['top5']['values']))}"
            )
            summary_lines.append(
                f"  Bottom 5: {list(zip(top_bottom['bottom5']['labels'], top_bottom['bottom5']['values']))}"
            )
            if ranking_signal:
                summary_lines.append(
                    f"  Ranking gap: Top5 mean={ranking_signal['top_avg']}, Bottom5 mean={ranking_signal['bottom_avg']}, difference={ranking_signal['gap']}"
                )

        if anomaly_overview:
            summary_lines.append("")
            summary_lines.append("[Data Anomaly Overview]")
            summary_lines.append(
                f"- Primary metric: {anomaly_overview['metric']}, mean={anomaly_overview['mean']}, median={anomaly_overview['median']}, P10={anomaly_overview['q10']}, P90={anomaly_overview['q90']}"
            )
            summary_lines.append(
                f"- High group ({anomaly_overview['top_group_size']} samples) mean={anomaly_overview['top_group_mean']}, low group ({anomaly_overview['bottom_group_size']} samples) mean={anomaly_overview['bottom_group_mean']}, gap={anomaly_overview['gap']}"
            )
            summary_lines.append(
                f"- Primary metric outliers={anomaly_overview['outlier_count']}, share={anomaly_overview['outlier_pct']}%, percentile band distribution={list(zip(anomaly_overview['band_labels'], anomaly_overview['band_values']))}"
            )

        if driver_analysis.get("items"):
            summary_lines.append("")
            summary_lines.append("[Attribution Analysis Clues]")
            for item in driver_analysis["items"][:5]:
                summary_lines.append(
                    f"- {item['name']}: driver score={item['score']}, correlation with {driver_analysis['metric']}={item['corr']}, high group mean={item['top_mean']}, low group mean={item['bottom_mean']}, inter-group gap ratio={item['gap_ratio']}"
                )

        summary_lines.append("")
        summary_lines.append("[Categorical Feature Summary (Top 6)]")
        for col, stats in cat_summary.items():
            summary_lines.append(
                f"- {col}: unique values={stats['n_unique']}, most common={stats['top1']} "
                f"(count={stats['top1_count']}, share={stats['top1_share']}%), entropy={stats['entropy']}, "
                f"Top3 concentration={stats['top3_share']}%"
            )

        if segment_breakdown:
            summary_lines.append("")
            summary_lines.append("[Categorical Dimension Slice Performance]")
            for segment in segment_breakdown:
                leaders = segment["leaders"][:3]
                leader_text = "; ".join(
                    [
                        f"{item['name']}(samples={item['count']}, mean={item['mean']}, total={item['sum']})"
                        for item in leaders
                    ]
                )
                summary_lines.append(
                    f"- Dimension {segment['dimension']} high-contribution groups for metric {segment['metric']}: {leader_text}"
                )

        summary_lines.append("")
        summary_lines.append("[Key Correlations]")
        if correlations["data"]:
            strong_corrs = []
            for item in correlations["data"]:
                i, j, val = item
                if i < j and abs(val) >= 0.5:
                    strong_corrs.append(
                        f"{numeric_cols[i]} and {numeric_cols[j]} (correlation: {val})"
                    )
            if strong_corrs:
                summary_lines.extend([f"- {c}" for c in strong_corrs])
            else:
                summary_lines.append("- No strongly correlated numeric variable pairs found (|r| >= 0.5).")
            if correlation_highlights["positive"]:
                summary_lines.append("- Highest positive correlations:")
                for c1, c2, val in correlation_highlights["positive"]:
                    summary_lines.append(f"  * {c1} vs {c2}: {val}")
            if correlation_highlights["negative"]:
                summary_lines.append("- Lowest correlations:")
                for c1, c2, val in correlation_highlights["negative"]:
                    summary_lines.append(f"  * {c1} vs {c2}: {val}")

        if scatter:
            summary_lines.append("")
            summary_lines.append(
                f"[Scatter Plot] Generated scatter data for {scatter['x_name']} vs {scatter['y_name']}"
            )

        # Time series summary
        if time_series["dates"]:
            summary_lines.append("")
            summary_lines.append(
                f"[Time Series] Detected time column; aggregated {time_series['name']} trend by month/day"
            )
            if time_series_diagnostics:
                summary_lines.append(
                    f"- Time field={time_series_diagnostics['date_col']}, observations={time_series_diagnostics['points']}, "
                    f"start={time_series_diagnostics['start']}, end={time_series_diagnostics['end']}, "
                    f"overall change={time_series_diagnostics['change_pct']}%, slope={time_series_diagnostics['slope']}, "
                    f"volatility={time_series_diagnostics['volatility_pct']}%"
                )
                summary_lines.append(
                    f"- Peak at {time_series_diagnostics['peak_date']} ({time_series_diagnostics['peak_value']}), "
                    f"trough at {time_series_diagnostics['trough_date']} ({time_series_diagnostics['trough_value']})"
                )
            if time_series_multi:
                extra_names = [ts_m["name"] for ts_m in time_series_multi]
                summary_lines.append(f"  Additional trend columns: {', '.join(extra_names)}")

        summary_lines.append("==================================================")
        summary_lines.append(
            "As a data analysis expert, write deep data insights based on the statistical summary above. Each module should cover observation, possible causes, business impact, and action recommendations, and avoid merely repeating statistical values."
        )
        summary_lines.append(
            "Note: CHART_DATA_JSON wrapped in markers is injected automatically by the backend; you do not need to pass it manually."
        )
        summary_lines.append("###CHART_DATA_JSON_START###")
        summary_lines.append(chart_data_json_str)
        summary_lines.append("###CHART_DATA_JSON_END###")

        final_text = "\n".join(summary_lines)

        # Output standard chunks
        print(
            json.dumps(
                {"chunks": [{"output_type": "text", "content": final_text}]},
                ensure_ascii=False,
            )
        )

    except Exception as e:
        import traceback

        err_msg = f"Error during analysis: {str(e)}\n{traceback.format_exc()}"
        print(
            json.dumps(
                {"chunks": [{"output_type": "text", "content": err_msg}]},
                ensure_ascii=False,
            )
        )


def main():
    if len(sys.argv) < 2:
        result = {
            "chunks": [
                {
                    "output_type": "text",
                    "content": 'Usage: python csv_analyzer.py \'{"input_file": "data.csv"}\'',
                }
            ]
        }
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(1)

    try:
        args = json.loads(sys.argv[1])
        csv_file = (
            args.get("input_file") or args.get("file_path") or args.get("csv_file", "")
        )
    except (ValueError, TypeError):
        csv_file = sys.argv[1]

    if not csv_file or not os.path.exists(csv_file):
        result = {
            "chunks": [{"output_type": "text", "content": f"File not found: {csv_file}"}]
        }
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(1)

    SUPPORTED_EXTENSIONS = (".csv", ".xls", ".xlsx", ".tsv")
    if not csv_file.lower().endswith(SUPPORTED_EXTENSIONS):
        result = {
            "chunks": [
                {
                    "output_type": "text",
                    "content": (
                        f"Unsupported file format: {csv_file}. "
                        f"Supported formats: {', '.join(SUPPORTED_EXTENSIONS)}"
                    ),
                }
            ]
        }
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(1)

    analyze_csv(csv_file)


if __name__ == "__main__":
    main()
