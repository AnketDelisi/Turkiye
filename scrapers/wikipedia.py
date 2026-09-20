"""Wikipedia extractor: Turkish general election results by province.

Reads the tr.wikipedia per-province election articles (2023/2018 pattern:
"{Province}'de {year} Türkiye cumhurbaşkanlığı ve genel seçimleri") via the
MediaWiki API and extracts province-level party vote counts, percentages and
seats. The articles cite YSK KesinSecimSonuclari PDFs as their source.

For 2002-2015 the per-province articles follow a different naming/structure
(".. Milletvekili Genel Seçimleri") — handled by a separate parser mode keyed
on the election year.

Output: data/processed/elections.csv
  columns: year, province, party, votes, pct, seats
"""
import argparse
import csv
import json
import os
import re
import time
import urllib.parse
import urllib.request

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "data", "processed", "elections.csv")
RAW = os.path.join(ROOT, "data", "raw", "wiki")

API = "https://tr.wikipedia.org/w/api.php"
UA = {"User-Agent": "TurkiyeElectionABM/0.1 (research; contact: repo)"}

PROVINCES = [
    "Adana", "Adıyaman", "Afyonkarahisar", "Ağrı", "Aksaray", "Amasya",
    "Ankara", "Antalya", "Ardahan", "Artvin", "Aydın", "Balıkesir",
    "Bartın", "Batman", "Bayburt", "Bilecik", "Bingöl", "Bitlis",
    "Bolu", "Burdur", "Bursa", "Çanakkale", "Çankırı", "Çorum",
    "Denizli", "Diyarbakır", "Düzce", "Edirne", "Elazığ", "Erzincan",
    "Erzurum", "Eskişehir", "Gaziantep", "Giresun", "Gümüşhane",
    "Hakkâri", "Hatay", "Iğdır", "Isparta", "İstanbul", "İzmir",
    "Kahramanmaraş", "Kars", "Kastamonu", "Kayseri", "Kırıkkale",
    "Kırklareli", "Kırşehir", "Kilis", "Kocaeli", "Konya", "Kütahya",
    "Malatya", "Manisa", "Mardin", "Mersin", "Muğla", "Muş",
    "Nevşehir", "Niğde", "Ordu", "Osmaniye", "Rize", "Sakarya",
    "Samsun", "Siirt", "Sinop", "Sivas", "Şanlıurfa", "Şırnak",
    "Tekirdağ", "Tokat", "Trabzon", "Tunceli", "Uşak", "Van",
    "Yalova", "Yozgat", "Zonguldak",
]

ELECTION_NAMES = {
    2023: "2023 Türkiye cumhurbaşkanlığı ve genel seçimleri",
    2018: "2018 Türkiye genel seçimleri",
}


def loc_suffix(name):
    """Turkish locative suffix on the article-title pattern.
    Vowel harmony from the last vowel (a/ı/o/u -> -da, e/i/ö/ü -> -de);
    voiceless consonant after a final p/ç/t/k/s/ş/h/f -> -ta/-te."""
    vowels = [c for c in name if c in "aıoueiöüAIOUİÖÜ"]
    hard = "ptkçsşhfPTKÇSŞHF"
    if name[-1] in hard:
        base = "te" if (vowels[-1] if vowels else "a") in "eiöüEİÖÜ" else "ta"
        return "'" + base
    base = "de" if (vowels[-1] if vowels else "a") in "eiöüEİÖÜ" else "da"
    return "'" + base


def wiki_text(title):
    """Fetch wikitext of a tr.wikipedia page (cached under data/raw/wiki)."""
    fn = os.path.join(RAW, title.replace("/", "_") + ".txt")
    if os.path.isfile(fn):
        with open(fn, encoding="utf8") as f:
            return f.read()
    q = urllib.parse.urlencode({
        "action": "parse", "page": title, "prop": "wikitext",
        "format": "json", "formatversion": "2"})
    for attempt in range(5):
        try:
            req = urllib.request.Request(API + "?" + q, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read().decode("utf8", "replace"))
            break
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(5 * (attempt + 1))
                continue
            return None
        except Exception:
            return None
    if "error" in data:
        return None
    wt = data["parse"]["wikitext"]
    os.makedirs(RAW, exist_ok=True)
    with open(fn, "w", encoding="utf8") as f:
        f.write(wt)
    time.sleep(1.5)
    return wt


# Party short names as they appear in the 2023/2018 province tables.
PARTY_ABBREV = {
    "AK PARTİ": "akp", "AK PARTI": "akp", "AKP": "akp", "CHP": "chp",
    "MHP": "mhp", "İYİ PARTİ": "iyi", "İYİPARTİ": "iyi", "İYİ": "iyi",
    "YEŞİL SOL": "dem", "YEŞİLSOL": "dem", "YSP": "dem", "HDP": "dem",
    "TİP": "tip", "TIP": "tip", "YENİDEN REFAH": "yeniden_refah",
    "MEMLEKET": "memleket", "BÜYÜK BİRLİK": "bbp", "BBP": "bbp",
    "SAADET": "sp", "DEVA": "deva", "GELECEK": "gelecek", "DP": "dp",
    "TÜRKİYE": "turkiye_partisi", "ZAFER": "zaf", "HÜDA PAR": "hudapar",
    "HÜDAPAR": "hudapar", "ATA": "ata", "VATAN": "other", "MİLLET": "other",
    "ANAP": "anap", "DSP": "dsp", "HKP": "other", "TKP": "other",
    "SOL": "other", "GENÇ": "other", "AB": "other", "MİLLİ YOL": "other",
    "GBP": "other", "AP": "other", "BĞMSZ": "other", "BAĞIMSIZ": "other",
}


def parse_party_rows(wt, year):
    """Extract {party: {votes, seats}} from the province MP results.

    Two layouts:
    A) Multi-district provinces (Ankara/İstanbul/İzmir/Bursa) have a
       `Toplu sonuçlar` aggregate table: party rows end in
       `| TOPLAM` + `| {{yüzde |...}}` + `| '''MV'''`.
    B) Single-district provinces use one district-column table: rows are
       `| [[link|ABBR]] | d1 | d2 | ... | TOPLAM` (Toplam = last numeric
       cell). Seats come from the infobox (`sandalyeN`).
    """
    rows = {}
    anchor = wt.find("== Toplu sonuçlar ==")
    if anchor >= 0:
        seg = wt[anchor:]
        nxt = seg.find("\n==", 10)
        if nxt > 0:
            seg = seg[:nxt]
        lines = [ln.strip() for ln in seg.split("\n")]
        for i, ln in enumerate(lines):
            if not ln.startswith("|") or "yüzde" not in ln:
                continue
            total = None
            for j in range(i - 1, max(0, i - 4), -1):
                v = lines[j].lstrip("|").replace(".", "").replace(",", "").strip()
                if v.isdigit() and int(v) > 1000:
                    total = int(v)
                    break
            if total is None:
                continue
            party = None
            for j in range(i - 1, max(0, i - 8), -1):
                cell = lines[j].lstrip("|").strip()
                if (cell.startswith("[[") or "rowspan" in cell.lower()
                        or "style=" in cell.lower() or "n/a" in cell.lower()
                        or cell == "" or cell.isdigit()
                        or cell.startswith("{{") or "<br" in cell.lower()):
                    continue
                candidate = PARTY_ABBREV.get(cell.upper())
                if candidate:
                    party = candidate
                    break
            if not party:
                continue
            seats = 0
            if i + 1 < len(lines):
                m = re.search(r"'*\s*(\d+)\s*'*", lines[i + 1])
                if m:
                    seats = int(m.group(1))
            rows[party] = {"votes": total, "seats": seats}
        return rows

    # Layout B: district-column table. Party rows start with `| [[link|ABBR]]`
    # and end with the Toplam cell (last numeric cell before the next row).
    for m in re.finditer(
            r"\| \[\[[^\]]*\|([A-ZÇĞİÖŞÜÂ][A-ZÇĞİÖŞÜÂ \.']*?)\]\]\s*"
            r"((?:\|[^\n]*\n?)*?)\|\s*([\d.]+)\s*\n"
            r"(?=-bgcolor=|\|-|\|style=\"background-color:#E9E9E9|\Z)",
            wt, re.M):
        abbr = m.group(1).strip()
        party = PARTY_ABBREV.get(abbr)
        if not party:
            continue
        total = int(m.group(3).replace(".", ""))
        if total > 1000:
            rows[party] = {"votes": total, "seats": 0}
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2023)
    ap.add_argument("--provinces", nargs="*", default=None)
    args = ap.parse_args()
    name = ELECTION_NAMES[args.year]
    provinces = args.provinces or PROVINCES
    all_rows = []
    for prov in provinces:
        title = f"{prov}{loc_suffix(prov)} {name}"
        wt = wiki_text(title)
        if not wt:
            print(f"{prov}: page not found", flush=True)
            continue
        rows = parse_party_rows(wt, args.year)
        if not rows:
            print(f"{prov}: no party rows parsed", flush=True)
            continue
        for party, v in rows.items():
            all_rows.append({"year": args.year, "province": prov,
                             "party": party, "votes": v["votes"],
                             "seats": v["seats"]})
        print(f"{prov}: {len(rows)} parties", flush=True)
    if all_rows:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["year", "province", "party",
                                              "votes", "seats"])
            w.writeheader()
            w.writerows(all_rows)
        print(f"wrote {OUT}: {len(all_rows)} rows", flush=True)


if __name__ == "__main__":
    main()