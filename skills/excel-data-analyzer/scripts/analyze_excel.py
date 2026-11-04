"""Excel Data Analyzer - Core Analysis Script

Reads an Excel file and outputs comprehensive data analysis as JSON.
Usage: python analyze_excel.py <file_path> [--sheet <sheet_name>] [--max-rows <n>]
"""

import sys
import json
import argparse
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    print(json.dumps({"error": "pandas is required. Install with: pip install pandas openpyxl"}))
    sys.exit(1)


def analyze_column(series, col_name):
    """Analyze a single column and return its profile."""
    dtype = str(series.dtype)
    total = len(series)
    missing = int(series.isna().sum())
    non_missing = total - missing
    unique = int(series.nunique())
    
    result = {
        "name": col_name,
        "dtype": dtype,
        "total_rows": total,
        "missing": missing,
        "missing_pct": round(missing / total * 100, 2) if total > 0 else 0,
        "non_missing": non_missing,
        "unique_values": unique,
    }
    
    # Numeric analysis
    if pd.api.types.is_numeric_dtype(series):
        valid = series.dropna()
        result["numeric_stats"] = {
            "mean": round(float(valid.mean()), 4) if len(valid) > 0 else None,
            "median": round(float(valid.median()), 4) if len(valid) > 0 else None,
            "std": round(float(valid.std()), 4) if len(valid) > 0 else None,
            "min": round(float(valid.min()), 4) if len(valid) > 0 else None,
            "max": round(float(valid.max()), 4) if len(valid) > 0 else None,
            "q25": round(float(valid.quantile(0.25)), 4) if len(valid) > 0 else None,
            "q75": round(float(valid.quantile(0.75)), 4) if len(valid) > 0 else None,
            "sum": round(float(valid.sum()), 4) if len(valid) > 0 else None,
        }
    
    # Categorical analysis
    if pd.api.types.is_string_dtype(series) or pd.api.types.is_categorical_dtype(series) or pd.api.types.is_object_dtype(series):
        valid = series.dropna()
        if len(valid) > 0:
            top_values = valid.value_counts().head(10).to_dict()
            # Convert keys to strings for JSON serialization
            result["categorical_stats"] = {
                "top_values": {str(k): int(v) for k, v in top_values.items()},
                "empty_strings": int((valid == "").sum()) if pd.api.types.is_string_dtype(series) else 0,
            }
    
    # Datetime analysis
    if pd.api.types.is_datetime64_any_dtype(series):
        valid = series.dropna()
        if len(valid) > 0:
            result["datetime_stats"] = {
                "min_date": str(valid.min()),
                "max_date": str(valid.max()),
                "range_days": (valid.max() - valid.min()).days,
            }
    
    return result


def analyze_excel(file_path, sheet_name=None, max_rows=None):
    """Analyze an Excel file and return a comprehensive JSON report."""
    path = Path(file_path)
    if not path.exists():
        return {"error": f"File not found: {file_path}"}
    
    try:
        xls = pd.ExcelFile(file_path, engine="openpyxl")
    except Exception as e:
        return {"error": f"Cannot open Excel file: {str(e)}"}
    
    sheet_names = xls.sheet_names
    sheets_to_analyze = [sheet_name] if sheet_name else sheet_names
    
    report = {
        "file": str(path.absolute()),
        "file_name": path.name,
        "file_size_bytes": path.stat().st_size,
        "total_sheets": len(sheet_names),
        "sheet_names": sheet_names,
        "sheets": {}
    }
    
    for sname in sheets_to_analyze:
        if sname not in sheet_names:
            report["sheets"][sname] = {"error": f"Sheet '{sname}' not found"}
            continue
        
        try:
            df = pd.read_excel(file_path, sheet_name=sname, engine="openpyxl")
        except Exception as e:
            report["sheets"][sname] = {"error": f"Failed to read sheet: {str(e)}"}
            continue
        
        if max_rows and len(df) > max_rows:
            df = df.head(max_rows)
            note = f" (limited to first {max_rows} rows)"
        else:
            note = ""
        
        columns = []
        for col in df.columns:
            columns.append(analyze_column(df[col], str(col)))
        
        # Sample data (first 5 rows)
        sample = df.head(5).fillna("").to_dict(orient="records")
        
        report["sheets"][sname] = {
            "rows": len(df),
            "columns_count": len(df.columns),
            "column_names": [str(c) for c in df.columns],
            "columns": columns,
            "sample_data": sample,
            "memory_usage_mb": round(df.memory_usage(deep=True).sum() / (1024 * 1024), 2),
            "note": note
        }
    
    xls.close()
    return report


def main():
    parser = argparse.ArgumentParser(description="Analyze Excel file and output JSON report")
    parser.add_argument("file", help="Path to the Excel file")
    parser.add_argument("--sheet", "-s", default=None, help="Specific sheet name to analyze")
    parser.add_argument("--max-rows", "-m", type=int, default=None, help="Max rows to read per sheet")
    args = parser.parse_args()
    
    result = analyze_excel(args.file, args.sheet, args.max_rows)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
