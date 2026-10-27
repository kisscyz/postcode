#!/usr/bin/env python3
"""Enrich CN postal records with Chinese names from the GeoNames CN dump.

The postal file only carries pinyin names. The per-country gazetteer dump
(data-src/CN.txt, GeoNames export/dump) has a comma-separated alternatenames
column that includes the Chinese-script name for most features.

Output: data/CN.json gains a parallel "zh" array:
  zh[i] = [placeZh, admin1Zh, admin2Zh, admin3Zh]  ("" when unknown)

Matching: normalized asciiname (suffixes stripped) + admin1-code bonus +
nearest coordinates + feature-class preference.
"""
import json
import math
import os
import re

BASE = os.path.dirname(os.path.abspath(__file__))
DUMP = os.path.join(BASE, "data-src", "CN-gazetteer.txt")
CN_JSON = os.path.join(BASE, "data", "CN.json")

# Characters that only appear in Traditional Chinese. Used to prefer the
# Simplified form when GeoNames lists both (自贡市 over 自貢市): a search
# typed in Simplified would otherwise miss the Traditional entry.
TRAD_CHARS = set(
    "貢區縣長門廣廠邊達遠選關頭衛設許認議論戰權觀歡難親讓價錢"
    "鐵銅錫錦鎮鏡顯靈寶實龍龜鳳學國會臺灣嶼巖巒峯嶽崗嶺濱瀋"
    "遼遷遺郵鄉鄰鄭鄧鄂魯齊劉楊張陳黃週幾機飛餘餓憂優傷創產"
    "復齊齋歲歸塵葉葉業極樂樂榮營縈樓夢夢聲處備復複覓覺覽"
    "親親親親"
)

CJK = re.compile(r"[\u4e00-\u9fff]")
SUFFIXES = (" autonomous region", " province", " xian", " shi", " qu",
            " zhen", " xiang", " cun", " county", " city", " district",
            " town", " village", " zhou", " meng", " qi")

# postal-file admin1 names -> gazetteer asciiname keys
ALIASES = {
    "ningxia": "ningxia hui",
    "xinjiang": "xinjiang uygur",
    "guangxi": "guangxi zhuang",
}


def norm(name):
    n = name.strip().lower()
    for s in SUFFIXES:
        if n.endswith(s):
            n = n[: -len(s)]
            break
    return n.strip()


def zh_name(alternates, name):
    # Prefer the longest purely-Chinese alternate: 呼和浩特市 over 呼市,
    # 锡林郭勒盟 over 锡林. This also drops kana/hangul alternates
    # (e.g. オルドス市) that merely contain a CJK suffix character.
    # When both Simplified and Traditional forms exist, prefer Simplified
    # (自贡市 over 自貢市) so Simplified searches match.
    pure = []
    for a in alternates.split(","):
        a = a.strip()
        if a and all("\u4e00" <= ch <= "\u9fff" for ch in a):
            pure.append(a)
    if pure:
        simp = [a for a in pure if not any(ch in TRAD_CHARS for ch in a)]
        pool = simp if simp else pure
        return max(pool, key=len)
    if name and all("\u4e00" <= ch <= "\u9fff" for ch in name.strip()):
        return name.strip()
    return None


def build_index():
    """normkey -> list of candidate dicts."""
    index = {}
    with open(DUMP, encoding="utf-8") as f:
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) < 15:
                continue
            zh = zh_name(p[3], p[1])
            if not zh:
                continue
            try:
                lat, lng = float(p[4]), float(p[5])
                pop = int(p[14]) if p[14] else 0
            except ValueError:
                continue
            cand = {"zh": zh, "fc": p[6], "code": p[7],
                    "adm1": p[10], "pop": pop, "lat": lat, "lng": lng}
            for key in {norm(p[2]), norm(p[1])}:
                if key:
                    index.setdefault(key, []).append(cand)
    return index


def pick(cands, adm1_code, lat, lng, prefer_fc):
    """Score candidates; return best zh name or ''."""
    best, best_score = "", -1e18
    for c in cands:
        s = 0.0
        if c["fc"] in prefer_fc:
            s += 100
        if adm1_code and c["adm1"] == adm1_code:
            s += 80
        s += math.log10(c["pop"] + 1) * 5
        d = math.hypot(c["lat"] - lat, c["lng"] - lng)
        s -= min(d * 20, 60)
        if s > best_score:
            best_score, best = s, c["zh"]
    return best


def key(name):
    n = norm(name)
    return ALIASES.get(n, n)


def main():
    print("building index from CN dump ...")
    index = build_index()
    print(f"index keys: {len(index)}")
    with open(CN_JSON, encoding="utf-8") as f:
        data = json.load(f)
    # postal record: [code, place, admin1, admin2, admin3, lat, lng, acc]
    # admin codes are not in the postal file; recover adm1 code via ADM1 lookup
    adm1_codes = {}
    with open(DUMP, encoding="utf-8") as f:
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) >= 11 and p[7] == "ADM1":
                adm1_codes.setdefault(norm(p[2]), p[10])
    zh_rows = []
    stats = {"place": 0, "a1": 0, "a2": 0, "a3": 0, "total": 0}
    for r in data["records"]:
        _code, place, a1, a2, a3, lat, lng, _acc = r
        adm1_code = adm1_codes.get(key(a1), "")
        place_zh = pick(index.get(key(place), []), adm1_code, lat, lng,
                        ("P", "A")) if place else ""
        a1_zh = pick([c for c in index.get(key(a1), []) if c["fc"] == "A"],
                     adm1_code, lat, lng, ("A",)) if a1 else ""
        a2_zh = pick(index.get(key(a2), []), adm1_code, lat, lng,
                     ("A", "P")) if a2 else ""
        a3_zh = pick(index.get(key(a3), []), adm1_code, lat, lng,
                     ("A", "P")) if a3 else ""
        zh_rows.append([place_zh, a1_zh, a2_zh, a3_zh])
        stats["total"] += 1
        if place_zh:
            stats["place"] += 1
        if a1_zh:
            stats["a1"] += 1
        if a2_zh:
            stats["a2"] += 1
        if a3_zh:
            stats["a3"] += 1
    data["zh"] = zh_rows
    with open(CN_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"records: {stats['total']}, 地名中文 {stats['place']} "
          f"({stats['place'] * 100 // stats['total']}%), "
          f"一级 {stats['a1']}, 二级 {stats['a2']}, 三级 {stats['a3']}")
    for r, z in list(zip(data["records"], zh_rows))[:6]:
        print(r[0], r[1], "->", z[0], "|", r[2], "->", z[1],
              "|", r[3], "->", z[2], "|", r[4], "->", z[3])


if __name__ == "__main__":
    main()
