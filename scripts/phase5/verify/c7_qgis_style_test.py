"""
Phase 5 verification / C7 - test the zone style in real QGIS (DATA-046).

Run with QGIS's own Python, from the project root:
  "C:\\Program Files\\QGIS 3.44.15\\bin\\python-qgis-ltr.bat" scripts\\phase5\\verify\\c7_qgis_style_test.py

For each zone map it loads the raster, applies gis/styles/susceptibility_zones_v3.qml, reads back
the renderer, draws the map to a PNG and counts the rendered pixels of each palette colour.
A map fails if QGIS rejects the style, the renderer is not paletted with classes 1 to 5,
or any of the five colours does not appear.

Outputs: data/phase5/verification/qgis_test/*.png, qgis_style_test.json
"""

import json
import os
import sys

from qgis.core import Qgis, QgsApplication, QgsMapRendererParallelJob, QgsMapSettings, QgsRasterLayer
from qgis.PyQt.QtCore import QSize
from qgis.PyQt.QtGui import QColor

STYLE = os.path.abspath("gis/styles/susceptibility_zones_v3.qml")
OUT = "data/phase5/verification/qgis_test"
os.makedirs(OUT, exist_ok=True)
MAPS = ["data/final/mizoram_landslide_zones_v3_natural.tif", "data/final/mizoram_landslide_zones_v3.tif",
        "data/final/mizoram_landslide_zones_v5_natural.tif"]
EXPECT = {1: "#fbe3d0", 2: "#f6b68c", 3: "#eb6834", 4: "#b8431c", 5: "#6f2108"}

app = QgsApplication([], False)
app.initQgis()
print("QGIS", Qgis.version(), flush=True)
results = {"qgis_version": Qgis.version(), "style": STYLE, "maps": {}}
failed = False
for path in MAPS:
    name = os.path.splitext(os.path.basename(path))[0]
    r = {"path": path}
    layer = QgsRasterLayer(os.path.abspath(path), name)
    r["layer_valid"] = layer.isValid()
    if not layer.isValid():
        failed = True
        results["maps"][name] = r
        print("FAIL", name, "layer not valid", flush=True)
        continue
    r["crs"] = layer.crs().authid()
    r["size"] = [layer.width(), layer.height()]
    message, ok = layer.loadNamedStyle(STYLE)
    r["style_loaded"], r["style_message"] = bool(ok), message
    rd = layer.renderer()
    r["renderer"] = rd.type() if rd else None
    classes = rd.classes() if rd and rd.type() == "paletted" else []
    got = {int(c.value): (c.color.name(), c.label) for c in classes}
    r["classes"] = {str(k): {"colour": v[0], "label": v[1]} for k, v in sorted(got.items())}
    colours_ok = {k: v[0] for k, v in got.items()} == EXPECT

    ms = QgsMapSettings()
    ms.setLayers([layer])
    ms.setExtent(layer.extent())
    ms.setDestinationCrs(layer.crs())
    ms.setBackgroundColor(QColor(255, 255, 255))
    ms.setOutputSize(QSize(int(1200 * layer.width() / layer.height()), 1200))
    job = QgsMapRendererParallelJob(ms)
    job.start()
    job.waitForFinished()
    img = job.renderedImage()
    png = f"{OUT}/{name}_qgis.png"
    r["png_saved"] = bool(img.save(png))
    r["png"] = png

    counts = {v: 0 for v in EXPECT.values()}
    for y in range(0, img.height(), 2):
        for x in range(0, img.width(), 2):
            c = QColor(img.pixel(x, y)).name()
            if c in counts:
                counts[c] += 1
    r["rendered_pixels_by_colour"] = counts
    seen = all(v > 0 for v in counts.values())
    r["pass"] = bool(ok and colours_ok and seen and r["png_saved"])
    failed = failed or not r["pass"]
    results["maps"][name] = r
    print("PASS" if r["pass"] else "FAIL", name, r["renderer"], r["classes"], counts, flush=True)

with open(f"{OUT}/qgis_style_test.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)
app.exitQgis()
print("RESULT", "FAIL" if failed else "PASS", flush=True)
sys.exit(1 if failed else 0)
