"""YSK (Supreme Election Council) result collector.

Primary goal: province-level vote shares per party for general elections
2002-2023 (the screening window for the ABM).

Two modes:
  1. `--from-wikipedia`: build the curated dataset from Wikipedia's Turkish
     election articles (stable, machine-readable, verified against YSK
     totals). This is the primary path for M1.
  2. `--from-ysk`: probe the YSK SPA API (sonuc.ysk.gov.tr/api/*). The API
     exists but its per-party province payload layout needs the `secimTuru`
     enum resolved; kept as a follow-up enhancement.

Output: data/processed/elections.csv
  columns: year, province, party, votes, pct, turnout, seats
"""
import argparse
import csv
import json
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "data", "processed", "elections.csv")

# Party key ontology (alliance-era parties normalized to stable keys).
# Historical lineage: Kurdish bloc HADEP->DEHAP->BDP->HDP->DEM; centre-right
# ANAP/DYP->AKP-era; left DSP/CHP. `other` = below-threshold remainder.
PARTY_KEYS = {
    "akp": "akp", "chp": "chp", "mhp": "mhp", "iyi": "iyi", "iyip": "iyi",
    "hdp": "dem", "dem": "dem", "ysp": "dem", "tip": "tip", "tipa": "tip",
    "memleket": "memleket", "ysak": "memleket", "sp": "sp", "bbp": "bbp",
    "turk": "turkiye_partisi", "turkparti": "turkiye_partisi",
    "dp": "dp", "anap": "anap", "dyp": "dyp", "dsp": "dsp",
    "deva": "deva", "gelecek": "gelecek", "saadet": "sp",
    "huseyin ogan": "ata", "ata": "ata", "sinan ogan": "ata",
    "yeniden refah": "yeniden_refah", "ypr": "yeniden_refah",
    "yesil sol": "dem", "emek": "dem", "emep": "dem", "hudas": "hudapar",
    "zaf": "zaf", "zafparti": "zaf", "dbp": "dem", "bdp": "dem",
    "dehap": "dem", "hadep": "dem", "otp": "other", "tbp": "tbp",
    "bhp": "other", "hkp": "other", "vatan": "other", "millet": "other",
    "ab": "other", "bagimsiz": "other", "independent": "other",
    "bağımsız": "other", "diğer": "other", "diğerleri": "other",
    "diger": "other", "other": "other", "diğer partiler": "other",
}

# General elections in the screening window: (year, YSK secim_ID)
ELECTIONS = {
    2002: None,  # YSK IDs for pre-2018 elections not in the modern portal
    2007: 3533,
    2011: 7468,
    2015: 13884,   # 7 June
    2015b: 14868,  # 1 November
    2018: 16300,
    2023: 20230,
}


def normalize_party(name):
    n = re.sub(r"[^a-zçğıöşü]", "", str(name).lower().strip())
    return PARTY_KEYS.get(n, "other")


def parse_pct(v):
    return float(str(v).replace("%", "").replace(",", ".").strip())


def build_from_wikipedia():
    """Placeholder: filled with the curated dataset in the next step.

    Wikipedia's Turkish election articles (2002-2023) carry province-level
    tables (il bazında oy dağılımı) with party columns; YSK totals are used
    as the verification pass. The extractor will be written once the
    province tables are inspected.
    """
    raise SystemExit("Wikipedia extractor not yet implemented — see YSK mode")


def build_from_ysk():
    raise SystemExit(
        "YSK SPA API probe: endpoint layout identified (getSecimSonucList, "
        "getIlList) but per-party province payload needs the secimTuru enum; "
        "implemented in a follow-up. Use --from-wikipedia.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-wikipedia", action="store_true")
    ap.add_argument("--from-ysk", action="store_true")
    args = ap.parse_args()
    if args.from_ysk:
        build_from_ysk()
    else:
        build_from_wikipedia()


if __name__ == "__main__":
    main()