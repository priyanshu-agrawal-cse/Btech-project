"""
Phase 4 / Task A1 + B check - report what the NGDR layers really contain (DATA-037).

For every shapefile found: CRS, geometry types and validity, feature count, attribute fields,
share of the Mizoram land area covered and the distinct values of descriptive fields.
Field names are not assumed. Nothing here looks at landslide labels for geology.

Output: data/phase4/verification/ngdr_layer_report.txt
"""

import glob
import os
import warnings

import geopandas as gpd
import pandas as pd

warnings.filterwarnings("ignore")
pd.set_option("display.width", 160, "display.max_columns", 60, "display.max_colwidth", 70, "display.max_rows", 200)

OUT = "data/phase4/verification/ngdr_layer_report.txt"
os.makedirs(os.path.dirname(OUT), exist_ok=True)
bnd = gpd.read_file("data/raw/mizoram_boundary.geojson").to_crs(32646)
region = bnd.union_all()
lines = []


def say(s=""):
    print(s.encode("ascii", "replace").decode())
    lines.append(str(s))


for p in sorted(glob.glob("data/raw/geology/ngdr/extracted/**/*.shp", recursive=True) +
                glob.glob("data/raw/landslide_inventory/ngdr/extracted/**/*.shp", recursive=True)):
    say("=" * 100)
    say(p.replace("\\", "/"))
    g = gpd.read_file(p)
    say(f"features {len(g)}  crs {g.crs}  geometry {dict(g.geom_type.value_counts())}")
    say(f"invalid geometries {(~g.is_valid).sum()}  empty {g.is_empty.sum()}")
    say(f"bounds {[round(float(x), 4) for x in g.total_bounds]}")
    say(f"fields {list(g.columns)}")
    gu = g.to_crs(32646)
    gu["geometry"] = gu.buffer(0) if g.geom_type.iloc[0].endswith("Polygon") else gu.geometry
    if g.geom_type.iloc[0].endswith("Polygon"):
        cl = gpd.clip(gu, bnd.to_crs(32646))
        say(f"area inside Mizoram {cl.area.sum() / 1e6:,.0f} km2 = {cl.area.sum() / region.area * 100:.1f} % of the state ({region.area / 1e6:,.0f} km2)")
    else:
        say(f"features inside Mizoram {int(gu.intersects(region).sum())}")
    for c in g.columns:
        if c == "geometry":
            continue
        n = g[c].nunique(dropna=True)
        vals = g[c].dropna().astype(str).value_counts().head(8)
        say(f"  {c:<24} {str(g[c].dtype):<9} nulls {int(g[c].isna().sum()):>5}  unique {n:>5}  top {dict(vals)}"[:230])

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
