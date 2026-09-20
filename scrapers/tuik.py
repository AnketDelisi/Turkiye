"""TÜİK Nüfus İstatistikleri Portalı (nip.tuik.gov.tr) scraper.

Pulls province-level demographic data for the ABM's synthetic-voter
generation via the portal's AJAX endpoint:

    POST /Home/GetInformation
      status = 1 (table), 0 (chart), 2 (map)
      name   = statistic page id (CinsiyeteGoreNufus, NufusYogunlugu, ...)
      value  = province code (uppercase, e.g. ADANA) or TÜRKİYE / year

Verified working (province x year, 2007-2025 history):
  CinsiyeteGoreNufus  Yıl | Düzey | Toplam | Erkek | Kadın
  NufusYogunlugu      Yıl | Düzey | Nüfus Yoğunluğu
  OrtancaYas          Yıl | Düzey | Toplam | Erkek | Kadın
  MedeniDurum         Yıl | Düzey | 18 columns (marital x sex)

Output: data/processed/demographics_{name}.csv
"""
import argparse
import csv
import html
import os
import re
import time
import urllib.parse
import urllib.request

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT_DIR = os.path.join(ROOT, "data", "processed")
API = "https://nip.tuik.gov.tr/Home/GetInformation"

# Province codes as used by the portal (uppercase, Turkish characters)
PROVINCES = [
    "ADANA", "ADIYAMAN", "AFYONKARAHİSAR", "AĞRI", "AKSARAY", "AMASYA",
    "ANKARA", "ANTALYA", "ARDAHAN", "ARTVİN", "AYDIN", "BALIKESİR",
    "BARTIN", "BATMAN", "BAYBURT", "BİLECİK", "BİNGÖL", "BİTLİS",
    "BOLU", "BURDUR", "BURSA", "ÇANAKKALE", "ÇANKIRI", "ÇORUM",
    "DENİZLİ", "DİYARBAKIR", "DÜZCE", "EDİRNE", "ELAZIĞ", "ERZİNCAN",
    "ERZURUM", "ESKİŞEHİR", "GAZİANTEP", "GİRESUN", "GÜMÜŞHANE",
    "HAKKARİ", "HATAY", "IĞDIR", "ISPARTA", "İSTANBUL", "İZMİR",
    "KAHRAMANMARAŞ", "KARABÜK", "KARAMAN", "KARS", "KASTAMONU", "KAYSERİ", "KIRIKKALE",
    "KIRKLARELİ", "KIRŞEHİR", "KİLİS", "KOCAELİ", "KONYA", "KÜTAHYA",
    "MALATYA", "MANİSA", "MARDİN", "MERSİN", "MUĞLA", "MUŞ",
    "NEVŞEHİR", "NİĞDE", "ORDU", "OSMANİYE", "RİZE", "SAKARYA",
    "SAMSUN", "SİİRT", "SİNOP", "SİVAS", "ŞANLIURFA", "ŞIRNAK",
    "TEKİRDAĞ", "TOKAT", "TRABZON", "TUNCELİ", "UŞAK", "VAN",
    "YALOVA", "YOZGAT", "ZONGULDAK",
]

STATS = {
    "sex": "CinsiyeteGoreNufus",
    "density": "NufusYogunlugu",
    "median_age": "OrtancaYas",
    "marital": "MedeniDurum",
}


def fetch_table(name, value):
    """POST GetInformation and return the parsed table rows."""
    body = urllib.parse.urlencode({"status": "1", "name": name,
                                   "value": value})
    req = urllib.request.Request(API, data=body.encode(), headers={
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://nip.tuik.gov.tr/",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        b = r.read().decode("utf8", "replace")
    # parse <tr> rows into cell lists
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", b, re.S):
        cells = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip()
                 for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr)]
        if cells and any(cells):
            rows.append(cells)
    return rows


def scrape(stat_key, provinces, sleep=0.4):
    name = STATS[stat_key]
    out = []
    for prov in provinces:
        try:
            rows = fetch_table(name, prov)
        except Exception as e:
            print(f"{prov}: ERR {e}", flush=True)
            continue
        data_rows = [r for r in rows if r and r[0].isdigit()]
        if not data_rows:
            print(f"{prov}: no data rows", flush=True)
            continue
        for r in data_rows:
            out.append({"province": prov, **{f"c{i}": v for i, v in enumerate(r)}})
        print(f"{prov}: {len(data_rows)} rows", flush=True)
        time.sleep(sleep)
    fn = os.path.join(OUT_DIR, f"demographics_{stat_key}.csv")
    os.makedirs(OUT_DIR, exist_ok=True)
    fieldnames = ["province"] + [f"c{i}" for i in range(20)]
    with open(fn, "w", encoding="utf8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(out)
    print(f"wrote {fn}: {len(out)} rows", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stat", choices=list(STATS) + ["all"], default="all")
    ap.add_argument("--provinces", nargs="*", default=None)
    args = ap.parse_args()
    provs = args.provinces or PROVINCES
    keys = list(STATS) if args.stat == "all" else [args.stat]
    for k in keys:
        scrape(k, provs)


if __name__ == "__main__":
    main()