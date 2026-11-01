"""Build deterministic SQLite databases for the Dashboard v1 demos."""

import argparse
import json
import math
import sqlite3
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCES_PATH = ROOT / "sources" / "apple-sec-sources.json"


def _reset_database(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    return sqlite3.connect(path)


def build_walmart(path: Path) -> None:
    """Create a synthetic, Walmart-shaped store/week dataset."""

    connection = _reset_database(path)
    connection.executescript(
        """
        CREATE TABLE walmart_sales (
            store INTEGER NOT NULL,
            sale_date TEXT NOT NULL,
            weekly_sales REAL NOT NULL,
            holiday_flag INTEGER NOT NULL,
            temperature REAL NOT NULL,
            fuel_price REAL NOT NULL,
            cpi REAL NOT NULL,
            unemployment REAL NOT NULL,
            PRIMARY KEY (store, sale_date)
        );
        CREATE INDEX idx_walmart_sales_date ON walmart_sales(sale_date);
        """
    )

    rows = []
    current = date(2011, 1, 7)
    end = date(2012, 12, 28)
    while current <= end:
        week = current.isocalendar().week
        month = current.month
        holiday = int((month == 11 and week >= 47) or month == 12)
        for store in range(1, 6):
            seasonal = 1 + 0.18 * math.sin((month - 1) / 12 * math.tau)
            holiday_boost = 1.28 if holiday else 1.0
            trend = 1 + (current - date(2011, 1, 1)).days / 3650
            weekly_sales = round(
                (780_000 + store * 145_000 + week * 2_100)
                * seasonal
                * holiday_boost
                * trend,
                2,
            )
            rows.append(
                (
                    store,
                    current.isoformat(),
                    weekly_sales,
                    holiday,
                    round(8 + month * 2.4 + store * 0.7, 1),
                    round(2.75 + month * 0.035 + store * 0.012, 3),
                    round(212 + month * 0.42 + (current.year - 2011) * 5.1, 3),
                    round(8.7 - store * 0.18 - (current.year - 2011) * 0.5, 2),
                )
            )
        current += timedelta(days=7)

    connection.executemany(
        "INSERT INTO walmart_sales VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows
    )
    connection.commit()
    connection.close()


def build_financial(path: Path) -> None:
    """Create a compact Apple/SEC fiscal-year dataset in USD millions."""

    connection = _reset_database(path)
    connection.executescript(
        """
        CREATE TABLE annual_financials (
            fiscal_year INTEGER PRIMARY KEY,
            revenue_usd_millions REAL NOT NULL,
            operating_income_usd_millions REAL NOT NULL,
            net_income_usd_millions REAL NOT NULL,
            assets_usd_millions REAL NOT NULL,
            liabilities_usd_millions REAL NOT NULL,
            equity_usd_millions REAL NOT NULL
        );
        CREATE TABLE product_revenue (
            fiscal_year INTEGER NOT NULL,
            product TEXT NOT NULL,
            revenue_usd_millions REAL NOT NULL,
            PRIMARY KEY (fiscal_year, product)
        );
        CREATE TABLE source_metadata (
            fiscal_year INTEGER NOT NULL,
            filing_url TEXT NOT NULL,
            accession_number TEXT NOT NULL,
            extracted_at TEXT NOT NULL,
            units TEXT NOT NULL
        );
        """
    )
    connection.executemany(
        "INSERT INTO annual_financials VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            (2022, 394328, 119437, 99803, 352755, 302083, 50672),
            (2023, 383285, 114301, 96995, 352583, 290437, 62146),
            (2024, 391035, 123216, 93736, 364980, 308030, 56950),
        ],
    )
    product_rows = {
        2022: [205489, 40177, 29292, 41241, 78129],
        2023: [200583, 29357, 28300, 39845, 85200],
        2024: [201183, 29984, 26694, 37005, 96169],
    }
    products = ["iPhone", "Mac", "iPad", "Wearables/Home/Accessories", "Services"]
    connection.executemany(
        "INSERT INTO product_revenue VALUES (?, ?, ?)",
        [
            (year, product, value)
            for year, values in product_rows.items()
            for product, value in zip(products, values)
        ],
    )
    sources = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
    connection.executemany(
        "INSERT INTO source_metadata VALUES (?, ?, ?, ?, ?)",
        [
            (
                item["fiscal_year"],
                item["filing_url"],
                item["accession_number"],
                item["extracted_at"],
                item["units"],
            )
            for item in sources
        ],
    )
    connection.commit()
    connection.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "generated",
        help="Directory for generated SQLite databases.",
    )
    args = parser.parse_args()
    build_walmart(args.output / "walmart_sales_demo.db")
    build_financial(args.output / "apple_financial_demo.db")
    print(f"Dashboard demo databases written to {args.output.resolve()}")


if __name__ == "__main__":
    main()
