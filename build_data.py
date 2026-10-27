#!/usr/bin/env python3
"""Build per-country postcode JSON from GeoNames postal-code txt files.

Input : data-src/<CC>.txt  (GeoNames export/zip, tab-separated)
Output: data/<CC>.json     compact arrays
        data/index.json    country list + meta

GeoNames txt columns:
  0 country code, 1 postal code, 2 place name,
  3 admin1 name, 4 admin1 code, 5 admin2 name, 6 admin2 code,
  7 admin3 name, 8 admin3 code, 9 latitude, 10 longitude, 11 accuracy
Record kept: [postcode, place, admin1, admin2, admin3, lat, lng, accuracy]
"""
import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(BASE, "data-src")
OUT_DIR = os.path.join(BASE, "data")

# Display order + names for the demo subset. Full build extends this list.
COUNTRIES = [
    ("US", "美国", "United States"),
    ("CN", "中国", "China"),
    ("GB", "英国", "United Kingdom"),
    ("DE", "德国", "Germany"),
    ("FR", "法国", "France"),
    ("JP", "日本", "Japan"),
    ("KR", "韩国", "South Korea"),
    ("IN", "印度", "India"),
    ("CA", "加拿大", "Canada"),
    ("AU", "澳大利亚", "Australia"),
    ("BR", "巴西", "Brazil"),
]

UPDATED = "2026-10-27"


def build_country(cc):
    path = os.path.join(SRC_DIR, cc + ".txt")
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 11:
                continue
            code = parts[1].strip()
            place = parts[2].strip()
            if not code or not place:
                continue
            try:
                lat = round(float(parts[9]), 4)
                lng = round(float(parts[10]), 4)
            except ValueError:
                continue
            acc = parts[11].strip() if len(parts) > 11 else ""
            try:
                acc = int(acc) if acc else None
            except ValueError:
                acc = None
            records.append([
                code,
                place,
                parts[3].strip(),
                parts[5].strip(),
                parts[7].strip(),
                lat,
                lng,
                acc,
            ])
    records.sort(key=lambda r: (r[0], r[1]))
    return records


def main(only=None):
    os.makedirs(OUT_DIR, exist_ok=True)
    index = {"updated": UPDATED, "source": "GeoNames",
             "license": "CC BY 4.0", "countries": []}
    total = 0
    for cc, name, name_en in COUNTRIES:
        if only and cc not in only:
            continue
        src = os.path.join(SRC_DIR, cc + ".txt")
        if not os.path.exists(src):
            print(f"skip {cc}: no source file", file=sys.stderr)
            continue
        records = build_country(cc)
        out = {"cc": cc, "name": name, "nameEn": name_en,
               "count": len(records), "records": records}
        with open(os.path.join(OUT_DIR, cc + ".json"), "w",
                  encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
        index["countries"].append(
            {"cc": cc, "name": name, "nameEn": name_en,
             "count": len(records)})
        total += len(records)
        print(f"{cc}: {len(records)} 条")
    index["total"] = total
    with open(os.path.join(OUT_DIR, "index.json"), "w",
              encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, separators=(",", ":"))
    print(f"合计: {total} 条")


if __name__ == "__main__":
    main(set(sys.argv[1:]) or None)
