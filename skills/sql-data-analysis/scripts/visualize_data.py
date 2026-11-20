#!/usr/bin/env python3
"""
Generate data visualizations from query results.
Supports bar charts, line charts, pie charts, and scatter plots.
"""

import sys
import argparse
import json
import os


def generate_chart(data, chart_type, x_column, y_column, title, output_path):
    """Generate a chart from query results."""
    try:
        import matplotlib
        matplotlib.use('Agg')  # Non-interactive backend
        import matplotlib.pyplot as plt
        
        # Extract data
        x_values = [row[x_column] for row in data]
        y_values = [row[y_column] for row in data]
        
        # Create figure
        plt.figure(figsize=(10, 6))
        
        if chart_type == 'bar':
            plt.bar(x_values, y_values)
        elif chart_type == 'line':
            plt.plot(x_values, y_values, marker='o')
        elif chart_type == 'pie':
            plt.pie(y_values, labels=x_values, autopct='%1.1f%%')
        elif chart_type == 'scatter':
            plt.scatter(x_values, y_values)
        else:
            return {"status": "error", "message": f"Unsupported chart type: {chart_type}"}
        
        plt.title(title)
        plt.xlabel(x_column)
        plt.ylabel(y_column)
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        
        # Save chart
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        return {
            "status": "success",
            "chart_type": chart_type,
            "output_path": output_path,
            "message": f"Chart saved to {output_path}"
        }
    except ImportError:
        return {"status": "error", "message": "matplotlib not installed. Run: pip install matplotlib"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def main():
    parser = argparse.ArgumentParser(description='Generate data visualization')
    parser.add_argument('--data', required=True, help='JSON string containing query results')
    parser.add_argument('--chart-type', required=True, choices=['bar', 'line', 'pie', 'scatter'], help='Chart type')
    parser.add_argument('--x-column', required=True, help='Column name for x-axis')
    parser.add_argument('--y-column', required=True, help='Column name for y-axis')
    parser.add_argument('--title', default='Data Visualization', help='Chart title')
    parser.add_argument('--output', default='chart.png', help='Output file path')
    
    args = parser.parse_args()
    
    data = json.loads(args.data)
    result = generate_chart(data, args.chart_type, args.x_column, args.y_column, args.title, args.output)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
