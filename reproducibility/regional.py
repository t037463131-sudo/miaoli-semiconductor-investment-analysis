"""Extract park statistics and household registration counts from frozen source files."""
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path
import re

from pypdf import PdfReader

from analyze import INPUT, ROOT, TOWNS, write_csv

PARKS = {"銅鑼園區": "Tongluo", "竹南園區": "Zhunan", "合計": "SIPA all parks", "小計": "SIPA all parks"}
SIPA_URL = "https://www.sipa.gov.tw/ap/staticm_view1.jsp?dataserno="


class Rows(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.row = []
        self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
        if tag in ("td", "th"):
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        if tag == "tr" and self.row:
            self.rows.append(self.row)
            self.row = []


def park_rows():
    monthly = {}
    annual = {}
    jobs = {}
    for path in sorted((INPUT / "sipa").glob("*.html")):
        edition, kind, source_id = path.stem.split("_")
        parser = Rows()
        parser.feed(path.read_text(encoding="utf-8-sig"))
        url = SIPA_URL + source_id
        period = None
        park = None
        for row in parser.rows:
            first = row[0]
            if kind == "monthly":
                found = re.search(r"資料期間[：:]\s*(20\d\d)年\s*(\d+)月", " ".join(row))
                if found:
                    period = f"{found[1]}-{int(found[2]):02}"
                if period and first in PARKS and len(row) == 9:
                    monthly[period, PARKS[first]] = (float(row[1].replace(",", "")), float(row[-1].replace(",", "")), url)
            elif kind == "jobs" and first in PARKS and len(row) == 8 and row[-1].replace(",", "").isdigit():
                jobs[f"{edition[:4]}-{edition[4:]}", PARKS[first]] = (int(row[-1].replace(",", "")), url)
            elif kind == "revenue":
                if len(row) >= 10:
                    park = PARKS.get(first)
                found = re.search(r"(\d{3})\s*年\s*\(\s*01\s*~\s*12\s*月", " ".join(row))
                if found and park and len(row) in (9, 10):
                    year = int(found[1]) + 1911
                    annual[year, park] = (float(row[-8].replace(",", "")), float(row[-1].replace(",", "")), url)
    return monthly, jobs, annual


def population_rows():
    for path in sorted((INPUT / "population").glob("pop*.pdf")):
        year = 2000 + int(path.stem[-2:])
        text = PdfReader(path).pages[0].extract_text()
        for line in text.splitlines():
            parts = line.split()
            if parts and parts[0] in (*TOWNS, "苗栗縣"):
                town = TOWNS.get(parts[0], "Miaoli County")
                values = [int(x.replace(",", "")) for x in parts[1:7]]
                villages, neighborhoods, households, population, male, female = values
                assert male + female == population
                yield year, town, population, households, path.name


def main():
    out = ROOT / "results"
    out.mkdir(exist_ok=True)
    monthly, jobs, annual = park_rows()
    write_csv(out / "park_monthly_sales.csv", ("month", "park", "ic_sales_ntd_100m", "total_sales_ntd_100m", "source"),
              ((*key, *value) for key, value in sorted(monthly.items())))
    write_csv(out / "park_month_end_jobs.csv", ("month", "park", "workers", "source"),
              ((*key, *value) for key, value in sorted(jobs.items())))
    write_csv(out / "park_annual_sales.csv", ("year", "park", "ic_sales_ntd_100m", "total_sales_ntd_100m", "source"),
              ((*key, *value) for key, value in sorted(annual.items())))
    write_csv(out / "october_population.csv", ("year", "township", "population", "households", "source_file"), population_rows())
    half_year = defaultdict(list)
    for (period, park), (ic_sales, sales, _) in monthly.items():
        if period[-2:] <= "06":
            half_year[int(period[:4]), park].append((ic_sales, sales))
    write_csv(out / "park_h1_sales.csv", ("year", "park", "months_observed", "ic_sales_ntd_100m", "total_sales_ntd_100m"),
              ((*key, len(values), round(sum(v[0] for v in values), 2), round(sum(v[1] for v in values), 2))
               for key, values in sorted(half_year.items()) if len(values) == 6))


if __name__ == "__main__":
    main()
