"""Calculate park, population, attraction-ledger and scenario comparisons."""
from decimal import Decimal
import csv
from itertools import product

from analyze import INPUT, ROOT, write_csv

OUT = ROOT / "results"


def read(path):
    with path.open(encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def indexed(path, keys):
    return {tuple(row[key] for key in keys): row for row in read(OUT / path)}


def compare(rows, groups, periods, fields):
    for group, (before, after), field in product(groups, periods, fields):
        x, y = (float(rows[p, group][field]) for p in (before, after))
        yield group, field, before, after, x, y, round(y-x, 4), round(100*(y/x-1), 4)


def main():
    all_parks = ("Tongluo", "Zhunan", "SIPA all parks")
    jobs = indexed("park_month_end_jobs.csv", ("month", "park"))
    annual = indexed("park_annual_sales.csv", ("year", "park"))
    half = indexed("park_h1_sales.csv", ("year", "park"))
    pop = indexed("october_population.csv", ("year", "township"))
    fields = ("total_sales_ntd_100m", "ic_sales_ntd_100m")
    rows = [*compare(jobs, all_parks, [("2025-06","2026-06"),("2025-08","2026-08")], ("workers",)),
            *compare(annual, all_parks, [("2024","2025")], fields),
            *compare(half, all_parks, [("2025","2026")], fields),
            *compare(pop, ("Tongluo","Miaoli County","Zhunan","Toufen"), [("2024","2025"),("2025","2026")],
                     ("population", "households"))]
    write_csv(OUT / "regional_comparisons.csv",
              ("group","metric","before","after","before_value","after_value","difference","change_pct"), rows)
    projects = read(INPUT / "county_projects_2025.csv")
    values = sorted((Decimal(row["reported_ntd_100m"]) for row in projects), reverse=True)
    total = sum(values)
    write_csv(OUT / "county_ledger_check.csv", ("measure", "value"),
              [("item_count", len(values)), ("reported_total_ntd_100m", 2462),
               ("recomputed_item_total_ntd_100m", total), ("difference_ntd_100m", total - 2462),
               ("top_2_share_pct_of_item_total", round(100 * sum(values[:2]) / total, 4))])
    baseline = int(pop["2026", "Tongluo"]["households"])
    scenarios = []
    for jobs_net, resident_share in product((250, 500, 1000), (.2, .4, .6)):
        households = jobs_net * resident_share / 1.2
        scenarios.append((jobs_net, resident_share, 1.2, round(households, 1),
                          baseline, round(100 * households / baseline, 2)))
    write_csv(OUT / "scenario_grid.csv",
              ("assumed_net_jobs", "assumed_local_settlement_share", "assumed_workers_per_household",
               "implied_household_equivalents", "october_2026_tongluo_households", "share_of_baseline_pct"), scenarios)


if __name__ == "__main__":
    main()
