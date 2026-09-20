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
import glob
import json
import os
import re
import time
import urllib.parse
import urllib.request

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "data", "processed", "elections.csv")
OUT_YEAR = os.path.join(ROOT, "data", "processed", "elections_{}.csv")
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
    "Kahramanmaraş", "Karabük", "Karaman", "Kars", "Kastamonu", "Kayseri", "Kırıkkale",
    "Kırklareli", "Kırşehir", "Kilis", "Kocaeli", "Konya", "Kütahya",
    "Malatya", "Manisa", "Mardin", "Mersin", "Muğla", "Muş",
    "Nevşehir", "Niğde", "Ordu", "Osmaniye", "Rize", "Sakarya",
    "Samsun", "Siirt", "Sinop", "Sivas", "Şanlıurfa", "Şırnak",
    "Tekirdağ", "Tokat", "Trabzon", "Tunceli", "Uşak", "Van",
    "Yalova", "Yozgat", "Zonguldak",
]

ELECTION_NAMES = {
    "2023": "2023 Türkiye cumhurbaşkanlığı ve genel seçimleri",
    "2018": "2018 Türkiye cumhurbaşkanlığı ve genel seçimleri",
    "2015": "Haziran 2015 Türkiye genel seçimleri",
    "2015b": "Kasım 2015 Türkiye genel seçimleri",
    "2011": "2011 Türkiye genel seçimleri",
    "2007": "2007 Türkiye genel seçimleri",
    "2002": "2002 Türkiye genel seçimleri",
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
            cached = f.read()
        # a cached redirect stub is useless — refetch (redirects are followed)
        if not cached.startswith("#YÖNLENDİRME") and "YÖNLENDİRME" not in cached[:50]:
            return cached
    q = urllib.parse.urlencode({
        "action": "parse", "page": title, "prop": "wikitext",
        "format": "json", "formatversion": "2", "redirects": "1"})
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
    # cache under the resolved title if the API followed a redirect
    res = data["parse"].get("title") or title
    os.makedirs(RAW, exist_ok=True)
    with open(os.path.join(RAW, res.replace("/", "_") + ".txt"),
              "w", encoding="utf8") as f:
        f.write(wt)
    time.sleep(1.5)
    return wt


# Party short names as they appear in the 2023/2018 province tables.
PARTY_ABBREV = {
    "AK PARTİ": "akp", "AK PARTI": "akp", "AKP": "akp", "CHP": "chp",
    "MHP": "mhp", "İYİ PARTİ": "iyi", "İYİPARTİ": "iyi", "İYİ": "iyi",
    "YEŞİL SOL": "dem", "YEŞİLSOL": "dem", "YSP": "dem", "HDP": "dem",
    "YEŞİL SOL": "dem", "YEŞİLSOL": "dem", "YSP": "dem", "HDP": "dem",
    "TİP": "tip", "TIP": "tip", "YENİDEN REFAH": "yeniden_refah",
    "MEMLEKET": "memleket", "BÜYÜK BİRLİK": "bbp", "BBP": "bbp",
    "SAADET": "sp", "SP": "sp", "DEVA": "deva", "GELECEK": "gelecek", "DP": "dp",
    "TÜRKİYE": "turkiye_partisi", "ZAFER": "zaf", "HÜDA PAR": "hudapar",
    "HÜDAPAR": "hudapar", "ATA": "ata", "VATAN": "other", "VP": "other", "MİLLET": "other",
    "ANAP": "anap", "DSP": "dsp", "HKP": "other", "TKP": "other",
    "SOL": "other", "GENÇ": "other", "AB": "other", "MİLLİ YOL": "other",
    "GBP": "other", "AP": "other", "BĞMSZ": "other", "BAĞIMSIZ": "other",
}

# Full party names -> key (for the 2002-2011 `||`-format tables, which use
# only the full name without an abbreviation cell).
FULL_NAME_MAP = {
    "Adalet ve Kalkınma Partisi": "akp",
    "Cumhuriyet Halk Partisi": "chp",
    "Milliyetçi Hareket Partisi": "mhp",
    "İYİ Parti": "iyi",
    "Halkların Demokratik Partisi": "dem",
    "Demokratik Halk Partisi (Türkiye)": "dem",  # HADEP/DEHAP lineage 2002
    "Halkın Demokrasi Partisi": "dem",
    "Emek Partisi": "dem",
    "Saadet Partisi": "sp",
    "Doğru Yol Partisi": "dyp",
    "Doğru Yol Partisi (2007)": "dyp",
    "Anavatan Partisi": "anap",
    "Demokratik Sol Parti": "dsp",
    "Büyük Birlik Partisi": "bbp",
    "Demokrat Parti (2007)": "dp",
    "Yeni Türkiye Partisi (2002)": "ytp",
    "Türkiye Komünist Partisi (2001)": "other",
    "Bağımsız siyasetçi": "other",
    "Bağımsız": "other",
    "Genç Parti": "other",
    "Millet Partisi (1992)": "other",
    "Liberal Demokrat Parti (Türkiye)": "other",
    "Halkın Sesi Partisi": "other",
    "Hak ve Eşitlik Partisi": "other",
    "Aydınlık Türkiye Partisi": "other",
    "Bağımsız Türkiye Partisi": "other",
    "Halkın Yükselişi Partisi": "other",
    "Özgürlük ve Dayanışma Partisi": "other",
    "İşçi Partisi (Türkiye)": "other",
    "Milliyetçi ve Muhafazakar Parti": "other",
    "Emek Partisi": "other",
}


def parse_party_rows_old(wt, year):
    """Parser for the 2002-2011 `||`-separated tables.

    Row format: `| [[Full Party Name]] || çevre || gümrük || TOPLAM ||
    % || ... || MV`. Party identified by full name only. Anchor on the
    `!Parti` column header (heading varies: Toplam Sonuçlar / Sonuçlar).
    Some pages use single-pipe multi-line rows instead; handled below.
    """
    rows = {}
    anchor = wt.find("!Parti")
    if anchor < 0:
        return rows
    seg = wt[anchor:]
    nxt = seg.find("\n==", 10)
    if nxt > 0:
        seg = seg[:nxt]

    # --- variant A: `||`-separated single-line rows ---
    found = False
    for line in seg.split("\n"):
        if "||" not in line or "[[" not in line:
            continue
        found = True
        cells = [c.strip() for c in line.split("||")]
        m = re.match(r"\|\s*\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", cells[0].strip())
        if not m:
            continue
        name = m.group(1).strip()
        party = FULL_NAME_MAP.get(name)
        if not party:
            continue
        nums = [re.sub(r"[^\d]", "", c) for c in cells[1:]]
        nums = [int(x) for x in nums if x]
        if len(nums) < 3:
            continue
        total = nums[0] if len(nums) == 3 else nums[2]
        seats = 0
        for c in reversed(cells[3:]):
            if re.fullmatch(r"\d+", c.strip()):
                seats = int(c.strip())
                break
        rows[party] = {"votes": total, "seats": seats}
    if found:
        return rows

    # --- variant B: single-pipe multi-line rows (party link line then
    # çevre / gümrük / TOPLAM / % / MV lines) ---
    lines = [ln.strip() for ln in seg.split("\n")]
    for i, ln in enumerate(lines):
        m = re.match(r"\|\s*\[\[([^\]|]+)(?:\|[^\]]+)?\]\]$", ln)
        if not m:
            continue
        name = m.group(1).strip()
        party = FULL_NAME_MAP.get(name)
        if not party:
            continue
        # collect the following numeric lines until the next row
        nums = []
        for j in range(i + 1, min(len(lines), i + 10)):
            v = lines[j].lstrip("|").replace(".", "").strip()
            if v.isdigit():
                nums.append(int(v))
            elif lines[j].startswith("|") and not lines[j].startswith("|-"):
                pass  # % / +/- cells — skip non-numeric
            if lines[j].startswith("|-") and nums:
                break
        if len(nums) >= 3:
            total = nums[0] if len(nums) == 3 else nums[2]
            rows[party] = {"votes": total, "seats": 0}
    return rows


def parse_party_rows_template(wt, year):
    """Parser for the {{Seçim tablosu}} template format (some 2015 pages).

    Row pattern: `| ABBR` / `| [[Full Name]]` then a {{Daraltılabilir
    liste}} candidate block, then `| VOTES` / `| %` / `| MV`. Only the
    province-wide (İl geneli) section has the candidate lists; district
    tables are skipped.
    """
    anchor = wt.find("İl geneli")
    if anchor < 0:
        anchor = wt.find("Seçim tablosu")
    if anchor < 0:
        return {}
    seg = wt[anchor:]
    rows = {}
    lines = [ln.strip() for ln in seg.split("\n")]
    for i, ln in enumerate(lines):
        # abbreviation cell: `| AK Parti` or `|bgcolor="..." | AK Parti`
        m = re.match(r"^\|\s*(?:bgcolor=\"[^\"]*\"\s*)?\|\s*([A-ZÇĞİÖŞÜÂ][A-Za-zÇĞİÖŞÜÂçğıiöşüâ \.]*)$",
                     ln)
        if not m:
            continue
        abbr = m.group(1).strip().upper()
        party = PARTY_ABBREV.get(abbr)
        if not party:
            continue
        # only rows followed by a candidate list are province-wide
        found_list = False
        for j in range(i + 1, min(len(lines), i + 6)):
            if "{{Daraltılabilir liste" in lines[j]:
                found_list = True
                break
        if not found_list:
            continue
        votes = None
        seats = None
        in_list = False
        for j in range(i + 1, min(len(lines), i + 40)):
            cell = lines[j].lstrip("|").strip()
            if "{{Daraltılabilir liste" in lines[j]:
                # if the candidate list opens AND closes on this line,
                # it's self-contained; otherwise enter skip mode
                if "}}" not in lines[j]:
                    in_list = True
                continue
            if in_list:
                if "}}" in lines[j]:
                    in_list = False
                continue
            v = cell.replace(".", "").replace(",", "").strip()
            if v.isdigit():
                if votes is None:
                    votes = int(v)
                else:
                    seats = int(v)
                    break
            if lines[j].startswith("|-") and votes is not None:
                break
        if votes is not None:
            rows[party] = {"votes": votes, "seats": seats or 0}
    return rows


def parse_party_rows(wt, year):
    """Extract {party: {votes, seats}} from a province's MP results.

    Modern format (2015-2023): abbreviation line + `| [[link]]` + votes,
    anchored on the `| Çevre oyu` column marker.
    Template format (some 2015 pages): `{{Seçim tablosu}}` with
    `| ABBR | [[link]] | (candidate list) | votes | % | MV`.
    Legacy format (2002-2011): `| [[Full Name]] || v || v || TOPLAM || % ||
    MV` under `==Toplam Sonuçlar==`.
    """
    if "| Çevre oyu" not in wt:
        if "Seçim tablosu" in wt and "{{Daraltılabilir liste" in wt:
            return parse_party_rows_template(wt, year)
        return parse_party_rows_old(wt, year)
    rows = {}
    anchor = wt.find("| Çevre oyu")
    if anchor < 0:
        return rows
    seg = wt[anchor:]
    nxt = seg.find("\n==", 10)
    if nxt > 0:
        seg = seg[:nxt]
    lines = [ln.strip() for ln in seg.split("\n")]
    for i, ln in enumerate(lines):
        # the % cell: `{{yüzde |...}}` template (2023) or plain `%40,4` (2018)
        if not ln.startswith("|"):
            continue
        if "yüzde" not in ln and not re.search(r"\|\s*(?:align=\"(?:center|right)\"\s*)?\|\s*%\s*|^\|\s*%\s*", ln):
            continue
        total = None
        for j in range(i - 1, max(0, i - 4), -1):
            v = lines[j].lstrip("|").strip()
            v = re.sub(r"^align=\"(?:center|right)\"\s*\|\s*", "", v)
            v = v.replace(".", "").replace(",", "").strip()
            if v.isdigit() and int(v) > 1000:
                total = int(v)
                break
        if total is None:
            continue
        party = None
        for j in range(i - 1, max(0, i - 8), -1):
            cell = lines[j].lstrip("|").strip()
            cell = re.sub(r"^align=\"(?:center|right)\"\s*\|\s*", "", cell)
            if (cell.startswith("[[") or "rowspan" in cell.lower()
                    or "style=" in cell.lower() or "n/a" in cell.lower()
                    or cell == "" or cell.isdigit()
                    or cell.startswith("{{") or "<br" in cell.lower()
                    or cell.startswith("bgcolor")):
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=str, default="2023")
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
        with open(OUT_YEAR.format(args.year), "w", encoding="utf8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["year", "province", "party",
                                              "votes", "seats"])
            w.writeheader()
            w.writerows(all_rows)
        print(f"wrote {OUT_YEAR.format(args.year)}: {len(all_rows)} rows",
              flush=True)
        # also merge into the combined elections.csv
        combined = {}
        for fn in glob.glob(OUT_YEAR.format("[0-9][0-9][0-9][0-9]*")):
            if not os.path.isfile(fn):
                continue
            with open(fn, encoding="utf8") as f:
                for r in csv.DictReader(f):
                    key = (r["year"], r["province"], r["party"])
                    combined[key] = r
        with open(OUT, "w", encoding="utf8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["year", "province", "party",
                                              "votes", "seats"])
            w.writeheader()
            w.writerows(sorted(combined.values(),
                               key=lambda r: (r["year"], r["province"],
                                              r["party"])))
        print(f"merged -> {OUT}: {len(combined)} rows", flush=True)


if __name__ == "__main__":
    main()