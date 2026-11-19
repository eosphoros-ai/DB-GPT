import sys, json, argparse
import pandas as pd
import numpy as np

def analyze(file_path, output_json=True):
    # Read file
    if file_path.endswith('.csv'):
        df = pd.read_csv(file_path)
    elif file_path.endswith(('.xlsx', '.xls')):
        df = pd.read_excel(file_path)
    else:
        raise ValueError('Unsupported format. Use .csv, .xlsx, or .xls')

    result = {}
    result['shape'] = list(df.shape)
    result['columns'] = df.columns.tolist()
    result['dtypes'] = df.dtypes.apply(str).to_dict()
    result['missing'] = df.isna().sum().to_dict()
    result['missing_pct'] = (df.isna().sum()/len(df)*100).round(2).to_dict()
    result['describe'] = df.describe(include='all').to_dict()
    result['nunique'] = df.nunique().to_dict()

    # Detect outliers using IQR
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    outliers = {}
    for col in numeric_cols:
        Q1, Q3 = df[col].quantile(0.25), df[col].quantile(0.75)
        IQR = Q3 - Q1
        lower, upper = Q1 - 1.5*IQR, Q3 + 1.5*IQR
        cnt = ((df[col] < lower) | (df[col] > upper)).sum()
        if cnt: outliers[col] = int(cnt)
    result['outliers'] = outliers

    # Correlation matrix (numerical only)
    if len(numeric_cols) > 1:
        result['correlation'] = df[numeric_cols].corr().round(4).to_dict()
    else:
        result['correlation'] = {}

    if output_json:
        print(json.dumps(result, ensure_ascii=False, default=str))
    return result

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('file', help='Path to CSV or Excel file')
    args = parser.parse_args()
    analyze(args.file)