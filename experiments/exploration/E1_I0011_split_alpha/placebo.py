"""E1 I0011 -- negative controls, WITH the no-op-placebo diagnostic run explicitly.

THE DEFECT THIS PROGRAM HAS SEEN BEFORE: a "placebo" that permutes a GROUPING KEY
and then RECOMPUTES the aggregate from the permuted key is a NO-OP. Permuting a
label is a bijection on labels, so the permuted cell is the same row set under a
new name and every row still receives its own true value. Diagnostic signature:
it reproduces the real number with sd EXACTLY 0.000000 across seeds.

This script therefore runs BOTH forms and reports the sd of each:

  NOOP_regroup        (the DEFECTIVE form, run on purpose as a diagnostic)
                      permute player_id, then recompute the season-to-date mean
                      within the permuted key. MUST reproduce STD_expanding with
                      sd 0.000000. If it does not, the diagnostic itself is wrong.
  NEG_other_player    (the CORRECT form) permute the ASSIGNMENT of an
                      already-computed season-to-date series to rows.
  NEG_channel_scramble (correct form, aimed at THIS lead) keep each row's own
                      efficiency state, but assign it a DIFFERENT player's
                      already-computed exposure state. If the split-alpha
                      estimator's advantage were an artefact of the arithmetic
                      rather than of player-specific exposure, this would not hurt.
  NEG_reversed        same history, recency weights inverted. Deterministic:
                      sd 0 BY CONSTRUCTION (no permutation), not a defect.
  NEG_league_const    partition-mean constant. Deterministic, same note.

N_PERM = 40 seeds for every permutation control; mean and sd of the resulting MAE
are reported. A permutation control whose sd is 0.000000 is a no-op and is called
one in the output.

PARTITION: 2021-2024 only.
"""
import numpy as np
import pandas as pd

SEED = 20260807
N_PERM = 40
PARTITION = [2021, 2022, 2023, 2024]
HERE = (r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees"
        r"\player-model-program\experiments\exploration\E1_I0011_split_alpha")
TARGETS = ["pts", "reb", "ast"]
MIN_PRIOR = 3
FROZEN_EFF, FROZEN_EXP = 0.03, 0.30

df = pd.read_parquet(HERE + r"\frame.parquet")
if not set(df["season"].unique()) <= set(PARTITION):
    raise SystemExit("PARTITION VIOLATION")
print("[partition-check] frame:", sorted(int(x) for x in df["season"].unique()))
df = df.sort_values(["player_id", "season", "game_date", "game_id"]).reset_index(drop=True)

KEY = ["player_id", "season"]
gk = [df["player_id"], df["season"]]
mask = ((df["n_prior"] >= MIN_PRIOR) & (df["minutes"] > 0)).values


def sh(col, frame=None, keycols=KEY):
    f = df if frame is None else frame
    return f.groupby(keycols, sort=False)[col].shift(1)


def smooth(s, alpha, keys=None):
    k = gk if keys is None else keys
    if alpha == 0.0:
        return s.groupby(k, sort=False).transform(
            lambda x: x.expanding(min_periods=1).mean()).values.astype(float)
    return s.groupby(k, sort=False).transform(
        lambda x: x.ewm(alpha=alpha, adjust=True, ignore_na=True).mean()).values.astype(float)


def mae(pred, y):
    v = np.abs(pred - y)[mask]
    v = v[np.isfinite(v)]
    return float(v.mean())


# player-season block boundaries, used by every permutation control
blocks = {k: df.index.get_indexer(v) for k, v in df.groupby(KEY, sort=False).groups.items()}
block_keys = list(blocks.keys())
by_season = {}
for (pid, s) in block_keys:
    by_season.setdefault(s, []).append((pid, s))


def permute_assignment(state, rng):
    """CORRECT placebo form: leave the computed state alone, permute WHICH ROWS get
    which player's state. Aligned by within-player-season game index, clamped."""
    out = np.full(len(state), np.nan)
    for s, keys in by_season.items():
        donors = list(keys)
        rng.shuffle(donors)
        donors = donors[1:] + donors[:1]          # rotate so nobody donates to itself
        for tgt_k, don_k in zip(keys, donors):
            ti, di = blocks[tgt_k], blocks[don_k]
            src = state[di]
            out[ti] = src[np.minimum(np.arange(len(ti)), len(src) - 1)]
    return out


def regroup_noop(col, rng):
    """DEFECTIVE placebo form, run deliberately: permute the GROUPING KEY and then
    RECOMPUTE the season-to-date mean from the permuted key."""
    d2 = df[["player_id", "season", col]].copy()
    for s, keys in by_season.items():
        pids = np.array([k[0] for k in keys])
        newp = pids.copy()
        rng.shuffle(newp)
        rmap = dict(zip(pids, newp))
        sel = d2["season"] == s
        d2.loc[sel, "player_id"] = d2.loc[sel, "player_id"].map(rmap)
    d2 = d2.sort_values(["player_id", "season"], kind="stable")
    g2 = [d2["player_id"], d2["season"]]
    v = d2.groupby(["player_id", "season"], sort=False)[col].shift(1)
    out = v.groupby(g2, sort=False).transform(
        lambda x: x.expanding(min_periods=1).mean())
    return out.sort_index().values.astype(float)


rows = []
print("\n" + "=" * 104)
print(f"NEGATIVE CONTROLS -- pooled 2021-2024 eval universe (n={int(mask.sum())}), "
      f"{N_PERM} seeds per permutation control")
print("=" * 104)
for tgt in TARGETS:
    y = df[tgt].astype(float).values
    sh_y, sh_min = sh(tgt), sh("minutes")
    std_state = smooth(sh_y, 0.00)
    exp_state = smooth(sh_min, FROZEN_EXP)
    df["_p36"] = df[tgt].astype(float) / df["minutes"] * 36.0
    eff_state = smooth(sh("_p36"), FROZEN_EFF)
    df.drop(columns=["_p36"], inplace=True)

    df["_p36"] = df[tgt].astype(float) / df["minutes"] * 36.0
    inc = smooth(sh("_p36"), 0.30) * smooth(sh_min, 0.30) / 36.0
    df.drop(columns=["_p36"], inplace=True)
    real = {
        "REAL_BASELINE_split(0.03,0.30)": eff_state * exp_state / 36.0,
        "REAL_incumbent(0.30,0.30)": inc,
        "REAL_naive_std": std_state,
    }

    print(f"\n--- {tgt} ---")
    for nm, p in real.items():
        v = mae(p, y)
        print(f"  {nm:<36} MAE {v:.4f}")
        rows.append(dict(target=tgt, control=nm, kind="reference", mae_mean=v,
                         mae_sd=0.0, n_perm=1, is_noop=False))

    # ---- deterministic controls (no permutation; sd 0 by construction, not a defect)
    lc = np.full(len(df), float(df.loc[mask, tgt].mean()))
    print(f"  {'NEG_league_const':<36} MAE {mae(lc, y):.4f}   (deterministic)")
    rows.append(dict(target=tgt, control="NEG_league_const", kind="deterministic",
                     mae_mean=mae(lc, y), mae_sd=0.0, n_perm=1, is_noop=False))

    rev = np.full(len(df), np.nan)
    vals = df[tgt].astype(float).values
    for k, ix in blocks.items():
        hist = []
        for p in ix:
            if hist:
                h = np.asarray(hist, float)
                w = (1 - 0.30) ** np.arange(len(h))     # oldest gets the most weight
                rev[p] = float((h * w).sum() / w.sum())
            if not np.isnan(vals[p]):
                hist.append(vals[p])
    print(f"  {'NEG_reversed':<36} MAE {mae(rev, y):.4f}   (deterministic)")
    rows.append(dict(target=tgt, control="NEG_reversed", kind="deterministic",
                     mae_mean=mae(rev, y), mae_sd=0.0, n_perm=1, is_noop=False))

    # ---- permutation controls
    for nm, fn in [
        ("NEG_other_player", lambda r: permute_assignment(std_state, r)),
        ("NEG_channel_scramble", lambda r: eff_state * permute_assignment(exp_state, r) / 36.0),
        ("NOOP_regroup", lambda r: regroup_noop(tgt, r)),
    ]:
        vs = np.array([mae(fn(np.random.default_rng(SEED + i)), y) for i in range(N_PERM)])
        sd = float(vs.std(ddof=1))
        noop = sd < 1e-12
        tag = "  <== NO-OP (sd is exactly zero)" if noop else ""
        print(f"  {nm:<36} MAE {vs.mean():.4f}  sd {sd:.6f}  "
              f"[{vs.min():.4f},{vs.max():.4f}]{tag}")
        rows.append(dict(target=tgt, control=nm, kind="permutation",
                         mae_mean=float(vs.mean()), mae_sd=sd, n_perm=N_PERM,
                         mae_min=float(vs.min()), mae_max=float(vs.max()), is_noop=noop))

out = pd.DataFrame(rows)
out.to_csv(HERE + r"\placebo.csv", index=False)

print("\n" + "=" * 104)
print("RANKING (pooled 2021-2024 MAE, worse = larger). Controls must rank BELOW every "
      "real estimator.")
print("=" * 104)
for tgt in TARGETS:
    d = out[(out.target == tgt) & (out.control != "NOOP_regroup")].sort_values("mae_mean")
    print(f"\n--- {tgt} ---")
    for i, (_, r) in enumerate(d.iterrows(), 1):
        flag = "  <-- NEGATIVE CONTROL" if r.control.startswith("NEG_") else ""
        print(f"  rank {i}  {r.control:<36} MAE {r.mae_mean:.4f} "
              f"sd {r.mae_sd:.6f}{flag}")

print("\n" + "=" * 104)
print("NO-OP DIAGNOSTIC VERDICT")
print("=" * 104)
for tgt in TARGETS:
    a = float(out[(out.target == tgt) & (out.control == "NOOP_regroup")]["mae_mean"].iloc[0])
    sd = float(out[(out.target == tgt) & (out.control == "NOOP_regroup")]["mae_sd"].iloc[0])
    b = float(out[(out.target == tgt) & (out.control == "REAL_naive_std")]["mae_mean"].iloc[0])
    c = float(out[(out.target == tgt) & (out.control == "NEG_other_player")]["mae_mean"].iloc[0])
    csd = float(out[(out.target == tgt) & (out.control == "NEG_other_player")]["mae_sd"].iloc[0])
    print(f"  {tgt}: NOOP_regroup {a:.6f} (sd {sd:.6f}) vs the REAL naive {b:.6f} -> "
          f"delta {a - b:+.9f}  {'IDENTICAL: confirmed no-op' if abs(a - b) < 1e-9 else 'differs'}")
    print(f"       correct-form NEG_other_player {c:.4f} (sd {csd:.6f}) -> "
          f"{'non-degenerate spread, valid placebo' if csd > 1e-6 else 'DEGENERATE'}")
print("\nDONE. wrote placebo.csv")
