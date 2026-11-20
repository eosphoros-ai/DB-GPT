import sys, argparse
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import pandas as pd
import numpy as np

# Try to find a Chinese font
zh_font = None
for f in fm.fontManager.ttflist:
    if any(k in f.name for k in ['Heiti','Songti','Kai','CJK','Noto Sans CJK','PingFang','SimHei','Microsoft YaHei']):
        zh_font = f.fname
        break
if zh_font:
    prop = fm.FontProperties(fname=zh_font)
else:
    prop = None

def read_file(path):
    if path.endswith('.csv'): return pd.read_csv(path)
    elif path.endswith(('.xlsx','.xls')): return pd.read_excel(path)
    else: raise ValueError('Unsupported format')

def plot_bar(df, x, y, output, title=''):
    fig, ax = plt.subplots(figsize=(10,6))
    ax.bar(df[x].astype(str), df[y], color='steelblue', edgecolor='white')
    ax.set_xlabel(x, fontproperties=prop)
    ax.set_ylabel(y, fontproperties=prop)
    if title: ax.set_title(title, fontproperties=prop, fontsize=14)
    plt.xticks(rotation=45)
    plt.tight_layout()
    fig.savefig(output, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'Chart saved to {output}')

def plot_line(df, x, y, output, title=''):
    fig, ax = plt.subplots(figsize=(10,6))
    ax.plot(df[x].astype(str), df[y], marker='o', color='coral', linewidth=2)
    ax.set_xlabel(x, fontproperties=prop)
    ax.set_ylabel(y, fontproperties=prop)
    if title: ax.set_title(title, fontproperties=prop, fontsize=14)
    plt.xticks(rotation=45)
    plt.tight_layout()
    fig.savefig(output, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'Chart saved to {output}')

def plot_scatter(df, x, y, output, title=''):
    fig, ax = plt.subplots(figsize=(10,6))
    ax.scatter(df[x], df[y], alpha=0.6, c='teal')
    ax.set_xlabel(x, fontproperties=prop)
    ax.set_ylabel(y, fontproperties=prop)
    if title: ax.set_title(title, fontproperties=prop, fontsize=14)
    plt.tight_layout()
    fig.savefig(output, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'Chart saved to {output}')

def plot_pie(df, label_col, value_col, output, title=''):
    fig, ax = plt.subplots(figsize=(8,8))
    vals = df[value_col]
    labels = df[label_col].astype(str)
    colors = plt.cm.Set2(range(len(vals)))
    ax.pie(vals, labels=labels, autopct='%1.1f%%', colors=colors, textprops={'fontproperties':prop})
    if title: ax.set_title(title, fontproperties=prop, fontsize=14)
    fig.savefig(output, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'Chart saved to {output}')

def plot_box(df, columns, output, title=''):
    # columns: comma-separated list
    cols = [c.strip() for c in columns.split(',')]
    fig, ax = plt.subplots(figsize=(10,6))
    ax.boxplot([df[c].dropna() for c in cols], labels=cols)
    if title: ax.set_title(title, fontproperties=prop, fontsize=14)
    plt.tight_layout()
    fig.savefig(output, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'Chart saved to {output}')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('file', help='Data file path')
    parser.add_argument('--type', required=True, choices=['bar','line','scatter','pie','box'])
    parser.add_argument('--x', help='X-axis / label column')
    parser.add_argument('--y', help='Y-axis / value column')
    parser.add_argument('--columns', help='Columns for boxplot (comma-separated)')
    parser.add_argument('--output', default='chart.png', help='Output image path')
    parser.add_argument('--title', default='', help='Chart title')
    args = parser.parse_args()
    df = read_file(args.file)
    if args.type == 'bar': plot_bar(df, args.x, args.y, args.output, args.title)
    elif args.type == 'line': plot_line(df, args.x, args.y, args.output, args.title)
    elif args.type == 'scatter': plot_scatter(df, args.x, args.y, args.output, args.title)
    elif args.type == 'pie': plot_pie(df, args.x, args.y, args.output, args.title)
    elif args.type == 'box': plot_box(df, args.columns, args.output, args.title)