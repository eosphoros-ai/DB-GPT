import pandas as pd
import matplotlib.pyplot as plt
from font_setup import setup_chinese_font
import os

def generate_time_series_trend(data_path, output_dir, selected_stores=[1, 4, 20]):
    setup_chinese_font()
    df = pd.read_csv(data_path)
    df["Date"] = pd.to_datetime(df["Date"], dayfirst=True)

    fig, ax1 = plt.subplots(figsize=(12, 6))
    ax2 = ax1.twinx()
    colors = ["blue", "green", "orange"]

    for i, store in enumerate(selected_stores):
        store_data = df[df["Store"] == store].sort_values("Date")
        ax1.plot(store_data["Date"], store_data["Weekly_Sales"], label=f"Store {store} Sales", color=colors[i], alpha=0.7)
        if i == 0:  # Just plot unemployment for one store as it's often regional/similar
            ax2.plot(store_data["Date"], store_data["Unemployment"], label="Unemployment", color="red", linestyle="--", linewidth=2)

    ax1.set_xlabel("Date")
    ax1.set_ylabel("Weekly Sales", color="blue")
    ax2.set_ylabel("Unemployment (%)", color="red")
    plt.title("Weekly Sales and Unemployment Over Time for Selected Stores")
    ax1.legend(loc="upper left")
    ax2.legend(loc="upper right")
    plt.tight_layout()
    
    output_path = os.path.join(output_dir, 'time_series_trend.png')
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()

if __name__ == "__main__":
    import sys, json
    args = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    data_path = args.get('input_file') or args.get('file_path') or args.get('data_path', 'Walmart_Sales.csv')
    out_dir = args.get('output_dir', os.environ.get('OUTPUT_DIR', '.'))
    os.makedirs(out_dir, exist_ok=True)
    generate_time_series_trend(data_path, out_dir)
    print('Time series trend plot generated.')
