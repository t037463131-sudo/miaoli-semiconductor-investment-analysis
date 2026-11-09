"""Export price-eligible observations from the original reproducible pipeline."""
import argparse
import csv
from pathlib import Path
import sqlite3

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("database", type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parent
with sqlite3.connect(args.database.resolve().as_uri() + "?mode=ro", uri=True) as db:
    cursor = db.execute((root / "extract.sql").read_text())
    with (root / "inputs" / "r_price_sample.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([item[0] for item in cursor.description])
        writer.writerows(cursor)
