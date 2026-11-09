"""Create publication figures from the delivered CSV results."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import numpy as np

from analyze import ROOT
from indicators import indexed

OUT = ROOT / "figures"
COLORS = ("#076C6F", "#A55122", "#576982")
SEGMENTS = ("Existing residential", "Presale residential", "Land only")
LABELS = ("Completed-home sales", "Presale homes", "Land-only sales")
GROUPS = ("Tongluo", "Nearby pool", "County excluding Tongluo")
DISPLAY = ("Tongluo", "Nearby pool", "Rest of county (incl. pool)")
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9, "axes.spines.top": False,
    "axes.spines.right": False, "axes.labelcolor": "#26374C", "axes.edgecolor": "#BBC5D0",
    "xtick.color": "#26374C", "ytick.color": "#26374C", "text.color": "#17293D",
    "axes.titleweight": "bold", "axes.axisbelow": True, "svg.fonttype": "none",
    "svg.hashsalt": "miaoli-2026-11-09", "savefig.facecolor": "white",
})


def save(fig, name):
    fig.savefig(OUT / f"{name}.png", dpi=220, bbox_inches="tight", pad_inches=.15)
    fig.savefig(OUT / f"{name}.svg", bbox_inches="tight", pad_inches=.15, metadata={"Date": None})
    plt.close(fig)


def market_trends():
    data = indexed("market_statistics.csv", ("geography", "segment", "stratum", "filter", "period"))
    quarters = [f"{y}Q{q}" for y in range(2023, 2027) for q in range(1, 5) if (y, q) <= (2026, 2)]
    fig, axes = plt.subplots(3, 1, figsize=(8, 6.2), sharex=True, layout="constrained")
    for ax, segment, label in zip(axes, SEGMENTS, LABELS):
        for group, color, display in zip(GROUPS, COLORS, DISPLAY):
            rows = [data[group, segment, "All", "main", q] for q in quarters]
            counts = np.array([int(r["n"]) for r in rows])
            values = np.array([float(r["median_ntd_m2"]) / 1000 if r["median_ntd_m2"] else np.nan for r in rows])
            x = np.arange(len(values))
            ax.plot(x, np.where(counts >= 5, values, np.nan), color=color, marker="o", ms=3, label=display)
            small = (counts > 0) & (counts < 5)
            ax.scatter(x[small], values[small], s=26, facecolors="white", edgecolors=color, zorder=4)
        ax.axvspan(11.5, 13.4, color="#EDF4F2", zorder=0)
        ax.set_title(label, loc="left", fontsize=10)
        ax.set_ylabel("NT$k / m²")
        ax.grid(axis="y", color="#E3EAF0")
        ax.yaxis.set_major_locator(MaxNLocator(4))
    axes[-1].set_xticks(range(len(quarters)), [q.replace("20", "’", 1) for q in quarters])
    axes[0].legend(ncol=3, loc="lower left", bbox_to_anchor=(-.01, 1.14), frameon=False, fontsize=8)
    save(fig, "01_property_prices")


def price_sensitivity():
    rows = indexed("market_comparisons.csv", ("geography", "segment", "stratum", "filter", "before", "after"))
    fig, axes = plt.subplots(1, 2, figsize=(8, 2.9), sharey=True, layout="constrained")
    rules = ["main", "all_priced", "no_remarks", "matched_archive"]
    names = ["Main screen", "All priced", "No remarks", "Matched release"]
    for ax, segment, label, color in zip(axes, [SEGMENTS[0], SEGMENTS[2]], [LABELS[0], LABELS[2]], COLORS):
        for i, rule in enumerate(rules):
            r = rows["Tongluo", segment, "All", rule, "2025 Apr-Jun", "2026 Apr-Jun"]
            change = float(r["median_change_pct"])
            ax.scatter(change, i, color=color, s=43)
            offset = -7 if change > 80 else 7
            ax.annotate(f'{change:+.1f}% ({r["n_before"]} → {r["n_after"]})',
                        (change, i), xytext=(offset, 8), textcoords="offset points",
                        fontsize=8, ha="right" if offset < 0 else "left")
        ax.axvline(0, color="#95A3AF", lw=1)
        ax.set_xlim((-18, 125) if segment == SEGMENTS[0] else (-68, 10))
        ax.set_ylim(3.55, -.7)
        ax.set_title(label, loc="left", fontsize=10)
        ax.set_xlabel("Median unit price change (%)")
        ax.grid(axis="x", color="#E3EAF0")
    axes[0].set_yticks(range(4), names)
    save(fig, "02_price_sensitivity")


def regional():
    rows = indexed("regional_comparisons.csv", ("group", "metric", "before", "after"))
    panels = [("total_sales_ntd_100m", "2025", "2026", "H1 park sales"),
              ("workers", "2025-06", "2026-06", "June park headcount")]
    parks = ["Tongluo", "Zhunan", "SIPA all parks"]
    fig, axes = plt.subplots(1, 2, figsize=(8, 2.7), layout="constrained")
    for ax, (metric, before, after, title) in zip(axes, panels):
        rates = [float(rows[park, metric, before, after]["change_pct"]) for park in parks]
        ax.barh(range(3), rates, color=COLORS, height=.58)
        ax.set_yticks(range(3), parks)
        ax.invert_yaxis()
        ax.set_title(title, loc="left", fontsize=10)
        ax.axvline(0, color="#95A3AF", lw=1)
        ax.set_xlabel("Year over year (%)")
        ax.set_xlim(-9 if metric == "workers" else 0, max(rates)*1.27)
        ax.grid(axis="x", color="#E3EAF0")
        for i, rate in enumerate(rates):
            ax.annotate(f"{rate:+.1f}%", (rate, i), xytext=(4 if rate >= 0 else -4, 0),
                        textcoords="offset points", va="center", ha="left" if rate >= 0 else "right", fontsize=8)
    save(fig, "03_park_comparisons")


def scenario():
    rows = indexed("scenario_grid.csv", ("assumed_net_jobs", "assumed_local_settlement_share"))
    fig, ax = plt.subplots(figsize=(7.5, 2.7), layout="constrained")
    jobs = [250, 500, 1000]
    for share, color in zip((.2, .4, .6), COLORS):
        y = [float(rows[str(j), str(share)]["implied_household_equivalents"]) for j in jobs]
        ax.plot(jobs, y, marker="o", color=color, label=f"{share:.0%} settle locally")
    ax.set(xlabel="Assumed additional net jobs", ylabel="Household equivalents", xticks=jobs, ylim=(0, 550))
    ax.legend(frameon=False, loc="upper left", ncol=3, fontsize=8)
    ax.grid(axis="y", color="#E3EAF0")
    save(fig, "04_housing_scenario")


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    market_trends()
    price_sensitivity()
    regional()
    scenario()
