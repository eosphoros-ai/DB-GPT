import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from font_setup import setup_chinese_font
import os

def generate_store_avg_comparison(data_path, output_dir):
    setup_chinese_font()
    df = pd.read_csv(data_path)
    
    store_agg = df.groupby("Store").agg({"Weekly_Sales": "mean", "Unemployment": "mean"}).reset_index()
    plt.figure(figsize=(10, 6))
    sns.scatterplot(data=store_agg, x="Unemployment", y="Weekly_Sales", hue="Store", palette="viridis", s=100)
    plt.title("Average Weekly Sales vs. Average Unemployment by Store")
    plt.xlabel("Average Unemployment (%)")
    plt.ylabel("Average Weekly Sales")
    plt.tight_layout()
    
    output_path = os.path.join(output_dir, "store_avg_comparison.png")
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()

if __name__ == "__main__":
    import sys, json
    args = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    data_path = args.get('input_file') or args.get('file_path') or args.get('data_path', 'Walmart_Sales.csv')
    out_dir = args.get('output_dir', os.environ.get('OUTPUT_DIR', '.'))
    os.makedirs(out_dir, exist_ok=True)
    generate_store_avg_comparison(data_path, out_dir)
    print('Store average comparison plot generated.')
