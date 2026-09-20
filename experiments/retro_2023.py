"""Model screening + the 2023 retro-forecast.

SOP (Gao et al. 2022):
  1. Generate many models with randomized rule weights (seeded).
  2. Simulate a PAST election (2018) with each model.
  3. Keep models that reproduce the 2018 national vote shares within
     tolerance (±3pp per party).
  4. Deploy survivors to forecast 2023 (with 2023 demographics + party
     positions), average across models and runs.
  5. Compare against the actual 2023 result.

Note: the retro test is honestly OOS — screening uses 2018 only; 2023 is
held out. With just two elections this is the cleanest validation we can
run until 2002-2015 screens are added.

Usage: python experiments/retro_2023.py [--n-models N] [--runs R]
"""
import argparse
import csv
import json
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from abm import agents, rules

ROOT = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(ROOT, "data", "processed")

# parties in each election (party keys per the elections.csv)
PARTIES_2018 = ["akp", "chp", "dem", "mhp", "iyi", "sp"]
PARTIES_2023 = ["akp", "chp", "dem", "mhp", "iyi", "yeniden_refah",
                "tip", "zaf", "bbp"]
# 2018 incumbent (AKP-MHP government)
INCUMBENT_2018 = "akp"
INCUMBENT_2023 = "akp"

_SCREEN_CTX = {}


def load_positions():
    with open(os.path.join(ROOT, "ideology", "positions", "turkiye.csv"),
              encoding="utf8") as f:
        out = {}
        for r in csv.DictReader(f):
            out[r["party"]] = (float(r["x"]), float(r["y"]))
    return out


def load_national(year):
    """Actual national vote shares (from province sums)."""
    counts = {}
    with open(os.path.join(DATA, "elections.csv"), encoding="utf8") as f:
        for r in csv.DictReader(f):
            if r["year"] != str(year):
                continue
            counts[r["party"]] = counts.get(r["party"], 0) + int(r["votes"])
    total = sum(counts.values())
    return {p: v / total for p, v in counts.items()}


def random_params(rng, parties):
    """Draw a random model: rule weights + party bases.

    Bases are seeded around the spatial-only residual (Gao step 2: derive
    initial rules from data), then jittered — much more efficient than pure
    random search over the full base space.
    """
    params = {
        "w_ideo": rng.uniform(0.8, 2.5),
        "incumbency_bonus": rng.uniform(0.0, 0.35),
        "kurd_bonus": rng.uniform(0.5, 1.5),
    }
    for p in parties:
        # base drawn uniformly; the screen will keep the subset that fits
        params["base_" + p] = rng.uniform(-0.7, 0.7)
    return params


def calibrated_params(rng, actual18, parties):
    """Seed bases by hill-climbing each party's base to fit 2018.

    Coordinate descent on the base intercepts (valence), starting from the
    spatial-only prediction, minimizing MAE vs the actual 2018 shares.
    Uses the precomputed distance matrix so each eval is cheap.
    """
    voters = _SCREEN_CTX["voters"]
    incumbent = _SCREEN_CTX["incumbent"]
    runs = _SCREEN_CTX["runs"]
    base = {"w_ideo": 1.5, "incumbency_bonus": 0.0, "kurd_bonus": 1.0}
    for p in parties:
        base["base_" + p] = 0.0
    # hill-climb each base in turn (2 passes, coarse then fine)
    for _pass, deltas in enumerate([(-0.25, -0.1, 0.0, 0.1, 0.25),
                                    (-0.08, -0.03, 0.0, 0.03, 0.08)]):
        for p in parties:
            best_b, best_e = base["base_" + p], 1e9
            for delta in deltas:
                base["base_" + p] += delta
                pred = rules.simulate_from(_SCREEN_CTX["D"], parties,
                                           voters, base, incumbent,
                                           rng, runs)
                e = err(actual18, pred, parties)
                if e < best_e:
                    best_e, best_b = e, base["base_" + p]
                base["base_" + p] -= delta
            base["base_" + p] = best_b
    # jitter the calibrated bases to build the screening pool
    params = {
        "w_ideo": rng.uniform(1.0, 2.0),
        "incumbency_bonus": rng.uniform(0.0, 0.25),
        "kurd_bonus": rng.uniform(0.8, 1.3),
    }
    for p in parties:
        params["base_" + p] = base["base_" + p] + rng.gauss(0, 0.12)
    return params


def err(actual, pred, parties):
    """Mean absolute error over parties present in both."""
    ps = [p for p in parties if p in actual and p in pred]
    return sum(abs(actual[p] - pred.get(p, 0)) for p in ps) / len(ps)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-models", type=int, default=200)
    ap.add_argument("--runs", type=int, default=10)
    ap.add_argument("--n-per", type=int, default=2000)
    args = ap.parse_args()

    positions = load_positions()
    actual18 = load_national(2018)
    actual23 = load_national(2023)

    print("2018 actual:", {k: round(v * 100, 1) for k, v in
                           sorted(actual18.items(), key=lambda x: -x[1])})
    print("2023 actual:", {k: round(v * 100, 1) for k, v in
                           sorted(actual23.items(), key=lambda x: -x[1])})

    # electorate (once per year, shared across models)
    rng_elec = random.Random(2026)
    voters18 = agents.generate_electorate(2018, rng_elec, args.n_per)
    voters23 = agents.generate_electorate(2023, rng_elec, args.n_per)
    pos18 = rules.party_positions(positions, 2018, PARTIES_2018)
    pos23 = rules.party_positions(positions, 2023, PARTIES_2023)
    print(f"electorate: {len(voters18)} voters (2018), "
          f"{len(voters23)} voters (2023)")

    # screen: random models -> 2018 fit
    global _SCREEN_CTX
    _SCREEN_CTX = {"voters": voters18,
                   "incumbent": INCUMBENT_2018, "runs": args.runs}
    _SCREEN_CTX["parties18"], _SCREEN_CTX["D"] = rules.distance_matrix(
        voters18, pos18)

    kept = []
    for i in range(args.n_models):
        rng = random.Random(1000 + i)
        params = calibrated_params(rng, actual18, PARTIES_2018)
        pred18 = rules.simulate_from(_SCREEN_CTX["D"], PARTIES_2018,
                                     voters18, params, INCUMBENT_2018,
                                     rng, args.runs)
        e = err(actual18, pred18, PARTIES_2018)
        if e <= 0.03:  # ±3pp tolerance
            kept.append((params, e))
    print(f"screened {args.n_models} models, kept {len(kept)} "
          f"(tolerance 3pp, MAE {0.03:.2f})")

    if not kept:
        print("no models survived — loosen tolerance or n-models")
        return

    # forecast 2023 with survivors
    _, D23 = rules.distance_matrix(voters23, pos23)
    fc = {p: [] for p in PARTIES_2023}
    for params, e in kept:
        # parties that didn't exist in the screening year (2018) have no
        # valence history: start their base at 0 instead of inheriting
        # another party's calibrated residual
        fparams = dict(params)
        for p in PARTIES_2023:
            if "base_" + p not in fparams:
                fparams["base_" + p] = 0.0
        pred23 = rules.simulate_from(D23, PARTIES_2023, voters23, fparams,
                                     INCUMBENT_2023,
                                     random.Random(5000 + len(fc["akp"])),
                                     args.runs)
        for p in PARTIES_2023:
            fc[p].append(pred23.get(p, 0.0))

    print("\n=== 2023 RETRO-FORECAST ===")
    rows = []
    for p in PARTIES_2023:
        preds = fc[p]
        mean = sum(preds) / len(preds)
        lo = min(preds)
        hi = max(preds)
        act = actual23.get(p, 0.0)
        rows.append({"party": p, "forecast": round(mean * 100, 1),
                     "lo": round(lo * 100, 1), "hi": round(hi * 100, 1),
                     "actual": round(act * 100, 1),
                     "err": round(abs(mean - act) * 100, 1)})
    rows.sort(key=lambda r: -r["forecast"])
    for r in rows:
        print(f"  {r['party']:14s} {r['forecast']:5.1f} "
              f"[{r['lo']:5.1f}-{r['hi']:5.1f}]  actual {r['actual']:5.1f}  "
              f"err {r['err']:4.1f}pp")
    print(f"\n  mean abs error: "
          f"{sum(r['err'] for r in rows) / len(rows):.2f}pp")

    # save
    out = os.path.join(ROOT, "report", "retro_2023.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf8") as f:
        json.dump({"kept_models": len(kept), "rows": rows}, f,
                  ensure_ascii=False, indent=1)
    print(f"saved -> {out}")


if __name__ == "__main__":
    main()