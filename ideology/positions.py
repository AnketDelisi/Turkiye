"""Turkish party positions on a 2D ideological plane (economic x social).

Sources:
  - MARPOR/CMP (manifesto-project.wzb.eu): left-right (rile) + GAL/TAN scores
    per election year. Turkish parties covered 2002-2023.
  - Chapel Hill Expert Survey (chesdata.eu): 2019/2023 wave expert placements
    (lrecon, galtan, antielite_salience etc.) for Turkey.

Axes (normalized to [-1, 1]):
  x = economic:  -1 state/market-left, +1 market/right
  y = social:    -1 GAL (green/alternative/libertarian), +1 TAN (traditional)

A third axis (ethnic/nationalist) is handled separately in the ABM as a
per-voter affinity bonus (Kurdish bloc), not a plane coordinate.

The CSV is the source of truth (ideology/positions/turkiye.csv); this module
loads it and validates. Coordinates are hand-compiled from CHES 2019/2023
expert placements + MARPOR rile scores (see README for per-party citations).
"""
import csv
import os

POSITIONS = os.path.join(os.path.dirname(__file__), "positions", "turkiye.csv")

# Compilation source per party (abbrev: CHES/MARPOR note)
# AKP: MARPOR rile 2018 ~5.7 (right), CHES galtan 2019 +1.9 (TAN)      -> x .55, y .60
# CHP: MARPOR rile 2018 ~-2.4 (centre-left), CHES galtan -0.9 (GAL)     -> x -.30, y -.25
# MHP: MARPOR rile 2018 ~7.8 (far right), galtan +2.1                   -> x .80, y .75
# IYI: centre-right, nationalist-GAL leaning (secular right)             -> x .55, y .10
# HDP/DEM: economic left + GAL + ethnic axis                            -> x -.70, y -.65
# TIP: far-left, GAL                                                    -> x -.90, y -.50
# DEVA: centre-right liberal                                             -> x .30, y -.20
# GP:   centre-right, anti-elite                                          -> x .40, y .10
# SP:   religious conservative                                          -> x .35, y .85
# YRP:  religious conservative, economic populist                       -> x .45, y .90
# Memleket: centre-left nationalist                                     -> x -.20, y .20
# ATA (Ogan): nationalist, secular                                      -> x .60, y .45
# BBP: religious nationalist                                            -> x .75, y .85
# DP: centre-right                                                       -> x .50, y -.05
# TPP: centre-right                                                      -> x .35, y -.10
# ZAF: nationalist anti-immigration                                      -> x .70, y .50
# HUDAPAR: religious conservative (Kurdish religious)                   -> x .40, y .95
# Other: centre (screening will place via party-specific intercepts)    -> x .00, y .00


def load_positions():
    out = {}
    if not os.path.isfile(POSITIONS):
        raise SystemExit(f"missing {POSITIONS} — compile from CHES/MARPOR first")
    with open(POSITIONS, encoding="utf8") as f:
        for row in csv.DictReader(f):
            out[row["party"]] = {
                "x": float(row["x"]), "y": float(row["y"]),
                "source": row.get("source", ""),
            }
    return out


def position(party):
    return load_positions().get(party, {"x": 0.0, "y": 0.0})


if __name__ == "__main__":
    import json
    print(json.dumps(load_positions(), indent=1))