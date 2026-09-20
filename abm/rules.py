"""Voting rules for the Turkey ABM (numpy-vectorized).

Each voter's utility for party p:

    U_p = -w_ideo * dist(voter_ideal, party_pos)
          + incumbency_bonus * I(p == incumbent)
          + kurd_bonus * I(p == dem) * voter.kurdis
          + party_base_p           (party-specific intercept, learned)

The voter votes for the party maximizing U, subject to a turnout
probability that rises with |U| (engaged voters turn out more). Noise on
utilities makes the outcome probabilistic; we average many runs.

Screening (Gao et al.): rules are seeded from correlations in the data
then the weights (w_ideo, incumbency_bonus, kurd_bonus, party bases) are
randomized across models; models reproducing historical results within
tolerance are kept and averaged for the forecast.

Performance: voter coordinates and weights are compiled to numpy arrays
once per electorate; utilities are a vectorized distance matrix, so each
simulation run is a handful of array ops.
"""
import numpy as np


def party_positions(positions, year, parties):
    """party -> (x, y) for the target year (positions CSV is static)."""
    return {p: positions.get(p, (0.0, 0.0)) for p in parties}


def compile_voters(voters, pos, params, incumbent):
    """Precompute per-voter per-party deterministic utility matrix."""
    parties = list(pos)
    xs = np.array([v["x"] for v in voters])
    ys = np.array([v["y"] for v in voters])
    weights = np.array([v["weight"] for v in voters])
    kurd = np.array([1.0 if v["kurdis"] else 0.0 for v in voters])
    n = len(voters)
    U = np.empty((n, len(parties)))
    for j, p in enumerate(parties):
        px, py = pos[p]
        dist = np.sqrt((xs - px) ** 2 + (ys - py) ** 2)
        U[:, j] = -params["w_ideo"] * dist
        if p == incumbent:
            U[:, j] += params["incumbency_bonus"]
        if p == "dem":
            U[:, j] += params["kurd_bonus"] * kurd
        U[:, j] += params.get("base_" + p, 0.0)
    return parties, U, weights


def distance_matrix(voters, pos):
    """per-voter x per-party euclidean distances (positions are static)."""
    parties = list(pos)
    xs = np.array([v["x"] for v in voters])
    ys = np.array([v["y"] for v in voters])
    D = np.empty((len(voters), len(parties)))
    for j, p in enumerate(parties):
        px, py = pos[p]
        D[:, j] = np.sqrt((xs - px) ** 2 + (ys - py) ** 2)
    return parties, D


def econ_incumbency(econ, year, w_growth, w_inflation):
    """Economic swing for the incumbent in a given year.

    Hummel-Rothschild: growth helps the incumbent, inflation hurts.
    Returns a utility shift applied to the incumbent party's utility
    (or None when no economic data for that year -> 0).
    """
    if econ is None:
        return 0.0
    e = econ.get(str(year)[:4])
    if not e:
        return 0.0
    # growth in pp helps; inflation (log scale, 5% baseline) hurts
    return (w_growth * e["gdp_growth"]
            - w_inflation * max(0.0, e["inflation"] - 5.0))


def simulate_from(D, parties, voters, params, incumbent, rng, n_runs=20,
                  incumbency_shift=0.0):
    """Vectorized simulation from a precomputed distance matrix.

    incumbency_shift: per-election economic swing added to the incumbent's
    utility (from econ_incumbency).
    """
    xs = np.array([v["x"] for v in voters])
    weights = np.array([v["weight"] for v in voters])
    kurd = np.array([1.0 if v["kurdis"] else 0.0 for v in voters])
    n = len(voters)
    U = np.empty((n, len(parties)))
    for j, p in enumerate(parties):
        U[:, j] = -params["w_ideo"] * D[:, j]
        if p == incumbent:
            U[:, j] += params["incumbency_bonus"] + incumbency_shift
        if p == "dem":
            U[:, j] += params["kurd_bonus"] * kurd
        U[:, j] += params.get("base_" + p, 0.0)
    totals = np.zeros(len(parties))
    total_weight = 0.0
    gen = np.random.default_rng(seed=rng.randrange(1 << 30))
    for _ in range(n_runs):
        U_noisy = U + gen.normal(0, 0.6, U.shape)
        best = U_noisy.argmax(axis=1)
        best_u = U_noisy[np.arange(n), best]
        turn = 1.0 / (1.0 + np.exp(-(np.abs(best_u) - 0.5)))
        voted = gen.random(n) < turn
        w = weights[voted]
        totals += np.bincount(best[voted], weights=w, minlength=len(parties))
        total_weight += w.sum()
    out = {}
    for j, p in enumerate(parties):
        out[p] = totals[j] / total_weight if total_weight else 0.0
    return out


def simulate(voters, pos, params, incumbent, rng, n_runs=20):
    """Run n_runs elections, return mean vote shares (vectorized)."""
    parties, D = distance_matrix(voters, pos)
    return simulate_from(D, parties, voters, params, incumbent, rng, n_runs)