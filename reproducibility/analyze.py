"""Build the SQLite dataset, statistics and figures from frozen government inputs."""
import argparse
import csv
from datetime import date
import gzip
import hashlib
from itertools import product
from pathlib import Path
import re
import sqlite3
from zipfile import ZipFile

import numpy as np

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "inputs"
SEASONS = [f"{year}S{q}" for year in range(112, 116) for q in range(1, 5)
           if (year, q) <= (115, 3)]
URL = "https://plvr.land.moi.gov.tw/DownloadSeason?season={}&type=zip&fileName=lvr_landcsv.zip"
TOWNS = dict(zip(
    "銅鑼鄉 苗栗市 公館鄉 三義鄉 西湖鄉 頭屋鄉 頭份市 竹南鎮 苑裡鎮 後龍鎮 通霄鎮 卓蘭鎮 大湖鄉 造橋鄉 南庄鄉 三灣鄉 泰安鄉 獅潭鄉".split(),
    ["Tongluo", "Miaoli City", "Gongguan", "Sanyi", "Xihu", "Touwu", "Toufen", "Zhunan",
     "Yuanli", "Houlong", "Tongxiao", "Zhuolan", "Dahu", "Zaoqiao", "Nanzhuang", "Sanwan", "Tai'an", "Shitan"]))
SPECIAL = re.compile(r"親友|關係人|特殊關係|急買急賣|債權債務|法院拍賣|法拍|毛胚|毛坯|瑕疵|僅土地|僅建物|部分持分|未登記建物|公共設施保留地|包含增建|含增建")
FIELDS = ("archive market serial township contract_date target urban nonurban land_use "
          "building_type purpose land_area building_area price parking_area parking_price "
          "building_count parking_count has_note special").split()
csv.field_size_limit(10_000_000)


def write_csv(path, columns, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(columns)
        writer.writerows(rows)


def freeze(archive_dir):
    """Extract untouched Miaoli sales/presale members plus archive provenance."""
    dest = INPUT / "moi"
    dest.mkdir(exist_ok=True)
    manifest = []
    for season in SEASONS:
        path = archive_dir / f"{season}.zip"
        archive_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        with ZipFile(path) as archive:
            scope = archive.read("build_time.xml").decode("utf-8-sig")
            scope = re.search(r"<lvr_time>(.*?)</lvr_time>", scope).group(1)
            for market in ("a", "b"):
                name = f"k_lvr_land_{market}.csv"
                payload = archive.read(name)
                filename = f"{season}_{name}.gz"
                (dest / filename).write_bytes(gzip.compress(payload, mtime=0))
                manifest.append((season, market, filename, URL.format(season), archive_hash,
                                 hashlib.sha256(payload).hexdigest(), scope))
    write_csv(INPUT / "moi_manifest.csv",
              "archive market file url zip_sha256 csv_sha256 official_scope".split(), manifest)


def number(row, key):
    return float(row.get(key) or 0)


def transaction_rows():
    seen = set()
    audit = []
    accepted = []
    with (INPUT / "moi_manifest.csv").open(encoding="utf-8-sig") as stream:
        entries = list(csv.DictReader(stream))
    for item in entries:
        season, market = item["archive"], item["market"]
        input_path = INPUT / "moi" / item["file"]
        payload = gzip.decompress(input_path.read_bytes())
        if hashlib.sha256(payload).hexdigest() != item["csv_sha256"]:
            raise ValueError(f"Input checksum mismatch for {input_path}")
        counts = dict.fromkeys(("read", "invalid_date", "unknown_township", "outside_dates", "duplicate_id", "loaded"), 0)
        with gzip.open(input_path, "rt", encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            next(reader)  # MOI English header row
            for row in reader:
                counts["read"] += 1
                raw_date = row["交易年月日"].strip()
                try:
                    day = date(int(raw_date[:-4]) + 1911, int(raw_date[-4:-2]), int(raw_date[-2:]))
                except ValueError:
                    counts["invalid_date"] += 1
                    continue
                if not date(2023, 1, 1) <= day <= date(2026, 8, 31):
                    counts["outside_dates"] += 1
                    continue
                if row["鄉鎮市區"] not in TOWNS:
                    counts["unknown_township"] += 1
                    continue
                serial = row["編號"]
                if not serial:
                    raise ValueError(f"Missing MOI serial in {season}")
                key = (market, serial)
                if key in seen:
                    counts["duplicate_id"] += 1
                    continue
                seen.add(key)
                building, parking = map(int, re.fullmatch(r"土地\d+建物(\d+)車位(\d+)", row["交易筆棟數"]).groups())
                note = row["備註"].strip()
                accepted.append((
                    season, market, serial, TOWNS[row["鄉鎮市區"]], day.isoformat(), row["交易標的"],
                    row["都市土地使用分區"], row["非都市土地使用分區"], row["非都市土地使用編定"],
                    row["建物型態"], row["主要用途"], number(row, "土地移轉總面積平方公尺"),
                    number(row, "建物移轉總面積平方公尺"), number(row, "總價元"),
                    number(row, "車位移轉總面積平方公尺"), number(row, "車位總價元"),
                    building, parking, int(bool(note)), int(bool(SPECIAL.search(note)))))
                counts["loaded"] += 1
        audit.append((season, market, *counts.values()))
    return accepted, audit


def summarize(values):
    if not len(values):
        return [0, None, None, None]
    q1, median, q3 = np.quantile(values, [.25, .5, .75])
    return [len(values), round(q1, 2), round(median, 2), round(q3, 2)]


def price_data(db, out):
    periods = {}
    for year in range(2023, 2027):
        for q in range(1, 5 if year < 2026 else 3):
            start = f"{year}-{q * 3 - 2:02d}-01"
            end = f"{year}-{q * 3 + 1:02d}-01" if q < 4 else f"{year+1}-01-01"
            periods[f"{year}Q{q}"] = start, end
        periods[f"{year} Apr-Jun"] = f"{year}-04-01", f"{year}-07-01"
    periods.update({"2025 Apr-May": ("2025-04-01", "2025-06-01"),
                    "2026 Apr-May": ("2026-04-01", "2026-06-01"),
                    "2025 Jan-Mar": ("2025-01-01", "2025-04-01"),
                    "2026 Jan-Mar": ("2026-01-01", "2026-04-01"),
                    "2025 Jul-Aug": ("2025-07-01", "2025-09-01"),
                    "2026 Jul-Aug": ("2026-07-01", "2026-09-01")})
    groups = ("Tongluo", "Nearby pool", "Other Miaoli", "County excluding Tongluo", "Miaoli County", *[x for x in TOWNS.values() if x != "Tongluo"])
    segments = ("Existing residential", "Land only", "Presale residential")
    strata = ("All", "Agriculture", "Industrial proxy", "Residential/building proxy", "Other/unspecified",
              "Townhouse", "Apartment/condo")
    filters = {"main": "sample", "all_priced": "priced", "no_remarks": "sample", "matched_archive": "sample"}
    aggregates = []
    contrasts = []
    data = {}
    for group, segment, stratum, rule in product(groups, segments, strata, filters):
        if stratum in ("Townhouse", "Apartment/condo") and segment == "Land only":
            continue
        if stratum in strata[1:5] and segment != "Land only":
            continue
        if group in TOWNS.values() and group != "Tongluo" and (stratum != "All" or rule != "main"):
            continue
        clauses = ["segment = ?", "ntd_m2 > 0"]
        params = [segment]
        if group == "County excluding Tongluo":
            clauses.append("township <> 'Tongluo'")
        elif group != "Miaoli County":
            clauses.append(("township" if group in TOWNS.values() else "geography") + " = ?")
            params.append(group)
        if stratum in strata[1:5]:
            clauses.append("land_class = ?")
            params.append(stratum)
        if stratum == "Townhouse":
            clauses.append("building_type LIKE '透天厝%'")
        elif stratum == "Apartment/condo":
            clauses.append("(building_type LIKE '公寓%' OR building_type LIKE '華廈%' OR building_type LIKE '住宅大樓%')")
        if rule == "no_remarks":
            clauses.append("has_note = 0")
        if rule == "matched_archive":
            clauses.append("CAST(substr(archive,1,3) AS INT) * 10 + CAST(substr(archive,5,1) AS INT) "
                           "<= (CAST(substr(contract_date,1,4) AS INT) - 1911) * 10 + 3")
        condition = " AND ".join(clauses)
        rows = db.execute(f"SELECT contract_date, ntd_m2 FROM {filters[rule]} WHERE {condition}", params).fetchall()
        for period, (start, end) in periods.items():
            values = np.array([price for day, price in rows if start <= day < end])
            data[group, segment, stratum, rule, period] = values
            aggregates.append((group, segment, stratum, rule, period, start, end, *summarize(values)))
    rng = np.random.default_rng(20261109)
    pairs = (("2025 Apr-Jun", "2026 Apr-Jun"), ("2024 Apr-Jun", "2025 Apr-Jun"),
             ("2025 Apr-May", "2026 Apr-May"), ("2025 Jan-Mar", "2026 Jan-Mar"),
             ("2025 Jul-Aug", "2026 Jul-Aug"))
    for group, segment, stratum, rule, (before, after) in product(
            groups[:4], segments, strata, filters, pairs):
        key = (group, segment, stratum, rule)
        if (*key, before) not in data:
            continue
        a, b = data[(*key, before)], data[(*key, after)]
        change = lo = hi = None
        if len(a) and len(b):
            change = 100 * (np.median(b) / np.median(a) - 1)
        if min(len(a), len(b)) >= 10 and group in ("Tongluo", "Nearby pool") and stratum == "All" and rule == "main":
            a_boot = np.median(rng.choice(a, size=(3000, len(a))), axis=1)
            b_boot = np.median(rng.choice(b, size=(3000, len(b))), axis=1)
            lo, hi = np.quantile(100 * (b_boot / a_boot - 1), [.025, .975])
        contrasts.append((*key, before, after, len(a), len(b), change, lo, hi))
    write_csv(out / "market_statistics.csv",
              "geography segment stratum filter period from_date to_date_exclusive n p25_ntd_m2 median_ntd_m2 p75_ntd_m2".split(), aggregates)
    write_csv(out / "market_comparisons.csv",
              "geography segment stratum filter before after n_before n_after median_change_pct bootstrap_p025 bootstrap_p975".split(), contrasts)
    write_csv(out / "market_monthly_counts.csv", ("month", "township", "segment", "n"),
              db.execute("SELECT substr(contract_date,1,7),township,segment,count(*) FROM sample GROUP BY 1,2,3 ORDER BY 1,2,3"))
    write_csv(out / "classification_audit.csv", ("market", "target", "segment", "loaded", "positive_price", "eligible_main"),
              db.execute("SELECT market,target,segment,count(*),sum(CASE WHEN ntd_m2>0 THEN 1 ELSE 0 END),sum(CASE WHEN ntd_m2>0 AND special=0 THEN 1 ELSE 0 END) FROM priced GROUP BY 1,2,3 ORDER BY 1,2,3"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze-from", type=Path)
    parser.add_argument("--out", type=Path, default=ROOT / "results")
    args = parser.parse_args()
    if args.freeze_from:
        freeze(args.freeze_from)
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    rows, audit = transaction_rows()
    write_csv(out / "load_audit.csv", ("archive", "market", "read", "invalid_date", "unknown_township", "outside_dates", "duplicate_id", "loaded"), audit)
    with sqlite3.connect(out / "miaoli.sqlite") as db:
        db.execute("DROP TABLE IF EXISTS deals")
        for view in ("sample", "priced", "classified"):
            db.execute(f"DROP VIEW IF EXISTS {view}")
        text_fields = set(FIELDS[:11])
        db.execute("CREATE TABLE deals (" + ",".join(f"{f} {'TEXT' if f in text_fields else 'REAL'}" for f in FIELDS) + ")")
        db.executemany("INSERT INTO deals VALUES (" + ",".join("?" for _ in FIELDS) + ")", rows)
        db.execute("CREATE INDEX deals_contract_date ON deals (contract_date)")
        db.executescript((ROOT / "analysis.sql").read_text())
        price_data(db, out)


if __name__ == "__main__":
    main()
