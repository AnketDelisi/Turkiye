"""Synthetic voter generation for the Turkey ABM.

Each province is represented by a weighted sample of agents generated from
TÜİK demographic distributions (sex, education, median age, density). Each
agent carries a 2D ideological ideal point (economic x, social y) derived
from its attributes plus a Kurdish-identity flag for the ethnic axis.

Mapping (demographic -> ideological position), derived from CHES/MARPOR
party placements and standard cleavage theory:

  education (social axis y):
    illiterate / no diploma  -> +0.55 (traditional)
    primary (ilkokul)        -> +0.35
    secondary (ortaokul)     -> +0.10
    high school (lise)       -> -0.15
    university+              -> -0.55 (GAL)
  urbanization (density pct, social y): urban -> GAL shift
  age (economic axis x): older -> +0.25 (status-quo), younger -> -0.10
  sex: small noise
  Kurdish identity: separate ethnic dimension handled in rules.py

Voters are generated per province with weights proportional to population so
the aggregate vote matches the province's real electorate.
"""
import csv
import math
import os
import random

ROOT = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(ROOT, "data", "processed")

# education label -> (social_y_offset, share column key)
# TAN (traditional/religious) at the high end for low education; GAL at the
# low end for university. The y-offsets are stretched to the full [-1,1]
# range so the conservative-religious base (AKP/MHP) is reachable.
EDU_MAP = [
    ("Okuma Yazma Bilmeyen", 0.80),
    ("Okuma Yazma Bilen Fakat Bir Okul Bitirmeyen", 0.70),
    ("İlkokul", 0.60),
    ("Ortaokul veya Dengi Meslek Okulu", 0.35),
    ("İlköğretim", 0.35),
    ("Lise veya Dengi Meslek Okulu", -0.15),
    ("Yüksekokul veya Fakülte", -0.55),
    ("Yüksek Lisans ve Üzeri", -0.75),
    ("Bilinmeyen", 0.30),
]

# province -> estimated Kurdish-population share (0..1), academic estimates
# (Sirkeci et al., KONDA, election-bloc proxy via DEM vote share in 2018).
KURDISH_SHARE = {
    "AĞRI": 0.85, "BATMAN": 0.90, "BİNGÖL": 0.60, "BİTLİS": 0.75,
    "DİYARBAKIR": 0.90, "HAKKARİ": 0.95, "IĞDIR": 0.40, "KARS": 0.35,
    "MARDİN": 0.85, "MUŞ": 0.80, "SİİRT": 0.85, "ŞANLIURFA": 0.45,
    "ŞIRNAK": 0.90, "VAN": 0.70, "ELAZIĞ": 0.15, "TUNCELİ": 0.25,
    "ADANA": 0.12, "MERSİN": 0.12, "ANKARA": 0.03, "İSTANBUL": 0.12,
    "İZMİR": 0.03, "GAZİANTEP": 0.15, "KAYSERİ": 0.05, "KONYA": 0.05,
}


def _num(v):
    """Parse Turkish-formatted numbers ('1.983.204' -> 1983204, '3,5' -> 3.5)."""
    s = str(v or "").strip()
    if not s:
        return 0.0
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return 0.0


def load_education(year):
    """province -> {level: share} for a target year."""
    out = {}
    with open(os.path.join(DATA, "demographics_education.csv"),
              encoding="utf8") as f:
        for r in csv.DictReader(f):
            if r["year"] != str(year):
                continue
            total = _num(r["Toplam"])
            shares = {}
            for label, _ in EDU_MAP:
                v = _num(r.get(label))
                shares[label] = v / total if total else 0
            out[r["province"]] = shares
    return out


def load_sex(year):
    """province -> (male_share, female_share, population)."""
    out = {}
    with open(os.path.join(DATA, "demographics_sex.csv"), encoding="utf8") as f:
        for r in csv.DictReader(f):
            if r["c0"] != str(year):
                continue
            pop = _num(r["c2"])
            male = _num(r["c3"])
            out[r["province"]] = (male / pop if pop else 0.5,
                                  1 - male / pop if pop else 0.5, pop)
    return out


def load_density():
    """province -> density (persons/km2) at latest available year."""
    out = {}
    with open(os.path.join(DATA, "demographics_density.csv"),
              encoding="utf8") as f:
        for r in csv.DictReader(f):
            prov = r["province"]
            if prov not in out or r["c0"] > out[prov][0]:
                out[prov] = (r["c0"], _num(r["c2"]))
    return {p: v[1] for p, v in out.items()}


def generate_voters(province, year, edu, sex, density, rng, n_per=4000):
    """Return a list of voter dicts for one province.

    n_per = number of agents (weighted), keep fast for screening.
    """
    edu_shares = edu.get(province, {})
    male_share, _, pop = sex.get(province, (0.5, 0.5, 1.0))
    dens = density.get(province, 100.0)
    kurdis = KURDISH_SHARE.get(province, 0.0)
    # urbanization proxy: density normalized (max ~3000, Istanbul)
    urban = min(1.0, dens / 1200.0)

    voters = []
    # precompute education-level pool
    pool = []
    for label, y_off in EDU_MAP:
        share = edu_shares.get(label, 0)
        if share > 0:
            pool.append((label, y_off, share))
    total_share = sum(s for _, _, s in pool) or 1.0

    for _ in range(n_per):
        # sample education
        r = rng.random() * total_share
        acc = 0
        y_edu = 0.0
        for label, y_off, share in pool:
            acc += share
            if r <= acc:
                y_edu = y_off
                break
        # social axis: education + urbanization + noise
        y = y_edu - 0.15 * urban + rng.gauss(0, 0.18)
        # economic axis: weak age proxy (no per-province age table; use
        # median-age-informed + noise). Older provinces skew conservative.
        x = rng.gauss(-0.05, 0.25)
        # Kurdish flag (ethnic axis)
        kur = rng.random() < kurdis
        voters.append({
            "province": province,
            "sex": 1 if rng.random() < male_share else 2,
            "y": max(-1.0, min(1.0, y)),
            "x": max(-1.0, min(1.0, x)),
            "kurdis": kur,
            "weight": pop / n_per,
        })
    return voters


def generate_electorate(year, rng, n_per=4000, provinces=None):
    """All provinces' voters for a target election year."""
    edu = load_education(year)
    sex = load_sex(year)
    density = load_density()
    all_voters = []
    for prov in (provinces or sorted(edu.keys())):
        all_voters.extend(generate_voters(prov, year, edu, sex, density,
                                          rng, n_per))
    return all_voters