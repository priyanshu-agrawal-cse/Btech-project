"""
Phase 4 / Step 00 - register the NGDR downloads (DATA-037).

Copies each zip the author received by email into data/raw/, leaving the originals in
place, records its SHA-256, and unpacks it. Nothing already in the target is overwritten.

usage: python 00_register_ngdr_downloads.py ZIP [ZIP ...]
Output: data/raw/geology/ngdr/, data/raw/landslide_inventory/ngdr/,
        data/phase4/logs/ngdr_download_manifest.csv
"""

import csv
import hashlib
import os
import shutil
import sys
import zipfile
from datetime import datetime, timezone

DEST = {"LANDSLIDE": "data/raw/landslide_inventory/ngdr"}
DEFAULT = "data/raw/geology/ngdr"
MANIFEST = "data/phase4/logs/ngdr_download_manifest.csv"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def unpack(path, out):
    """Unpack one zip, refusing unsafe names, then unpack any zips found inside it."""
    with zipfile.ZipFile(path) as z:
        for i in z.infolist():
            assert not (i.filename.startswith(("/", "\\")) or ".." in i.filename or ":" in i.filename), i.filename
        os.makedirs(out, exist_ok=True)
        z.extractall(out)
        names = z.namelist()
    for n in names:
        if n.lower().endswith(".zip"):
            inner = os.path.join(out, n)
            unpack(inner, os.path.splitext(inner)[0])


rows = []
for src in sys.argv[1:]:
    name = os.path.basename(src)
    d = next((v for k, v in DEST.items() if name.startswith(k)), DEFAULT)
    os.makedirs(d, exist_ok=True)
    dst = os.path.join(d, name)
    if not os.path.exists(dst):
        shutil.copy2(src, dst)
    assert sha256(src) == sha256(dst), "copy differs from the original"
    unpack(dst, os.path.join(d, "extracted", os.path.splitext(name)[0]))
    rows.append({"file": dst.replace("\\", "/"), "bytes": os.path.getsize(dst), "sha256": sha256(dst),
                 "registered_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")})
    print(rows[-1])

new = not os.path.exists(MANIFEST)
with open(MANIFEST, "a", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    if new:
        w.writeheader()
    w.writerows(rows)
