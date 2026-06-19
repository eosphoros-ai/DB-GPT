import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from font_setup import setup_chinese_font
import os

def generate_correlation_heatmap(data_path, output_dir):
    setup_chinese_font()
    df = pd.read_csv(data_path)
    
    plt.figure(figsize=(10, 8))
    corr = df.corr(numeric_only=True)
    sns.heatmap(corr, annot=True, cmap='coolwarm', fmt=".2f")
    plt.title('Walmart Sales Data Correlation Heatmap')
    plt.tight_layout()
    
    output_path = os.path.join(output_dir, 'correlation_heatmap.png')
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()

if __name__ == '__main__':
    import sys, json
    args = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    data_path = args.get('input_file') or args.get('file_path') or args.get('data_path', 'Walmart_Sales.csv')
    out_dir = args.get('output_dir', os.environ.get('OUTPUT_DIR', '.'))
    os.makedirs(out_dir, exist_ok=True)
    generate_correlation_heatmap(data_path, out_dir)
    print('Correlation heatmap generated.')
