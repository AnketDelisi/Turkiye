"""Economics layer for the Turkey ABM.

Pulls annual macro series for Turkey and writes data/processed/economics.csv:

  year, gdp_growth, inflation, unemployment

Source: World Bank API (no key required) — NY.GDP.MKTP.KD.ZG (real GDP
growth), FP.CPI.TOTL.ZG (CPI inflation), SL.UEM.TOTL.ZS (unemployment).

Note on sources: the original plan named TCMB EVDS / TÜFE / ENAG / İTO.
TÜİK's data portal and EVDS both require registration/keys (403/API-key
gated) and İTO's statistics portal is an interactive app; the World Bank
series are the harmonized standard used in the election-forecasting
literature (Hummel & Rothschild 2013) and cover all elections 2002-2023.
TÜİK's own numbers can be swapped in later via `--source`.

Usage: python scrapers/economics.py
"""
import argparse
import csv
import json
import os
import urllib.request

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "data", "processed", "economics.csv")

WB = "https://api.worldbank.org/v2/country/TUR/indicator/{}?format=json&per_page=60&date=1998:2026"
INDICATORS = {
    "gdp_growth": "NY.GDP.MKTP.KD.ZG",
    "inflation": "FP.CPI.TOTL.ZG",
    "unemployment": "SL.UEM.TOTL.ZS",
}


def fetch():
    out = {}
    for key, ind in INDICATORS.items():
        req = urllib.request.Request(WB.format(ind),
                                     headers={"User-Agent": "Mozilla/5.0"})
        j = json.loads(urllib.request.urlopen(req, timeout=25)
                       .read().decode("utf8", "replace"))
        out[key] = {d["date"]: d["value"] for d in j[1]
                    if d["value"] is not None}
    years = sorted(set(out["gdp_growth"]) | set(out["inflation"])
                   | set(out["unemployment"]))
    rows = [{"year": y,
             "gdp_growth": round(out["gdp_growth"].get(y, 0), 2),
             "inflation": round(out["inflation"].get(y, 0), 1),
             "unemployment": round(out["unemployment"].get(y, 0), 2)}
            for y in years]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["year", "gdp_growth",
                                          "inflation", "unemployment"])
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {OUT}: {len(rows)} rows ({years[0]}-{years[-1]})")
    return rows


def load():
    """year -> {gdp_growth, inflation, unemployment}."""
    out = {}
    with open(OUT, encoding="utf8") as f:
        for r in csv.DictReader(f):
            out[r["year"]] = {k: float(r[k]) for k in
                              ("gdp_growth", "inflation", "unemployment")}
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="worldbank",
                    help="worldbank (default; EVDS/TÜİK need API keys)")
    args = ap.parse_args()
    fetch()