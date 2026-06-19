import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from font_setup import setup_chinese_font
import os

def generate_sales_unemployment_scatter(data_path, output_dir):
    setup_chinese_font()
    df = pd.read_csv(data_path)
    
    plt.figure(figsize=(10, 6))
    sns.regplot(data=df, x='Unemployment', y='Weekly_Sales', scatter_kws={'alpha':0.3}, line_kws={'color':'red'})
    plt.title('Weekly Sales vs. Unemployment (Scatter + Regression)')
    plt.xlabel('Unemployment (%)')
    plt.ylabel('Weekly Sales')
    plt.tight_layout()
    
    output_path = os.path.join(output_dir, 'sales_vs_unemployment_scatter.png')
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()

if __name__ == '__main__':
    import sys, json
    args = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    data_path = args.get('input_file') or args.get('file_path') or args.get('data_path', 'Walmart_Sales.csv')
    out_dir = args.get('output_dir', os.environ.get('OUTPUT_DIR', '.'))
    os.makedirs(out_dir, exist_ok=True)
    generate_sales_unemployment_scatter(data_path, out_dir)
    print('Sales vs unemployment scatter plot generated.')
