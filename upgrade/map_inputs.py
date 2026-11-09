"""Extract the 18 official Miaoli township polygons for mapping."""
import argparse
import csv
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

import shapefile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("boundary_archive", type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parent
target = root / "inputs" / "miaoli_boundaries"
target.mkdir(exist_ok=True)
name = "TOWN_MOI_1140318"
towns = {
    "銅鑼鄉": "Tongluo", "苗栗市": "Miaoli City", "公館鄉": "Gongguan", "三義鄉": "Sanyi",
    "西湖鄉": "Xihu", "頭屋鄉": "Touwu",
}
points = []
with TemporaryDirectory() as tmp, ZipFile(args.boundary_archive) as archive:
    stem = Path(tmp) / name
    for suffix in (".shp", ".shx", ".dbf"):
        stem.with_suffix(suffix).write_bytes(archive.read(name + suffix))
    with shapefile.Reader(str(stem), encoding="utf-8") as reader, shapefile.Writer(
        str(target / "miaoli_townships"), shapeType=reader.shapeType, encoding="utf-8"
    ) as writer:
        writer.field("towncode", "C", size=12)
        writer.field("townname", "C", size=32)
        writer.field("label_en", "C", size=32)
        writer.field("study_grp", "C", size=24)
        for item in reader.iterShapeRecords():
            rec = item.record.as_dict()
            if rec["COUNTYNAME"] != "苗栗縣":
                continue
            code, town = rec["TOWNCODE"], rec["TOWNNAME"]
            label = towns.get(town, "")
            group = "Tongluo" if town == "銅鑼鄉" else "Nearby comparison" if label else "Other Miaoli"
            writer.shape(item.shape)
            writer.record(code, town, label, group)
            breaks = [*item.shape.parts, len(item.shape.points)]
            for ring, (start, end) in enumerate(zip(breaks[:-1], breaks[1:])):
                points.extend((code, ring, lon, lat, group) for lon, lat in item.shape.points[start:end])
        assert writer.recNum == 18
    (target / "miaoli_townships.prj").write_bytes(archive.read(name + ".prj"))
    (target / "miaoli_townships.cpg").write_text("UTF-8", encoding="ascii")
with (root / "inputs" / "boundary_vertices.csv").open("w", encoding="utf-8", newline="") as f:
    csv_writer = csv.writer(f)
    csv_writer.writerow(["towncode", "ring", "lon", "lat", "group"])
    csv_writer.writerows(points)
sha = hashlib.sha256(args.boundary_archive.read_bytes()).hexdigest()
(root / "inputs" / "boundary_source.txt").write_text(
    f"National Land Surveying and Mapping Center, Taiwan MOI\n"
    f"https://data.gov.tw/dataset/7441\nOriginal archive member: {name}.shp\n"
    f"Original ZIP SHA-256: {sha}\n"
    f"CRS: GCS_TWD97[2020], as supplied\n"
    f"Government Open Data License v1.0: https://data.gov.tw/license\n"
    f"Miaoli subset with study labels. Town-level geometries only.\n", encoding="utf-8"
)
