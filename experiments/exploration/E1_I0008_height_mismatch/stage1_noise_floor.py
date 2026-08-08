"""
E1 I0008 -- STAGE 1 (THE GATE): permutation noise floor for the height/size-mismatch lead.

The E0 lead reports +0.018 to +0.020 incremental R2 from adding
    rung1_height_diff = (player height) - (opponent's season minutes-weighted roster height)
to a model containing the player's own recent rebound rate. That number has never been
compared to a null of any kind. This script builds one.

R-SQUARED CONVENTION (declared): plain UNWEIGHTED OLS R2,
    R2 = 1 - SS_res / SS_tot,  SS_tot about the unweighted mean of y, no sample weights.
This is NOT the shared E0 `wls_r2` helper (which computes SST of the sqrt-weight-transformed
response about its own mean and therefore returns dR2 ~8% too small). Numbers here are not
comparable to wls_r2 numbers to three significant figures.

TWO CONTROLS ARE RUN.

  (A) NO-OP CONTROL -- RUN ON PURPOSE AS A POSITIVE DIAGNOSTIC. Permutes the GROUPING KEY
      (relabels team ids within season by a random bijection, applied consistently to
      team_id and opp_team_id) and then RECOMPUTES the roster-height aggregate from the
      permuted key. The permuted cell is the same row set renamed, so every row still gets
      its own true opponent's value. Expected diagnostic signature: it reproduces the real
      dR2 EXACTLY, sd == 0.000000. This is the trap; it is shown failing.

  (B) REAL CONTROL. The aggregate stays keyed on TRUE opponents (computed once, from the
      real rosters, never recomputed). What is permuted is the ASSIGNMENT of an
      already-computed value to rows: within each season the 12 team-season aggregates are
      permuted across team labels, then joined on the row's TRUE opp_team_id. Each row
      therefore receives some other real team's roster-height aggregate. The clustering
      structure of the feature (every row facing the same opponent shares one value) is
      preserved, which is what makes this the honest null for a team-season-level feature.
      A row-level within-season shuffle is run alongside as a secondary variant.

PARTITION GUARD: frame.parquet is 2021-2024 only; re-asserted on season COLUMN VALUES here.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

OUT = os.path.dirname(os.path.abspath(__file__))
EXPLORATION_SEASONS = [2021, 2022, 2023, 2024]
FORBIDDEN_SEASONS = {2025, 2026}
N_DRAWS = 400
SEED = 20260807

R2_CONVENTION = "plain_unweighted_ols_r2"


def assert_partition(df, name):
    seasons = sorted(int(s) for s in pd.unique(df["season"]))
    print(f"  [partition] {name}: seasons = {seasons}  rows = {len(df)}")
    bad = FORBIDDEN_SEASONS.intersection(seasons)
    if bad:
        sys.exit(f"PARTITION VIOLATION in {name}: {sorted(bad)}")
    return seasons


def ols_r2(y, X):
    """Plain unweighted OLS R2. y: (n,), X: (n,k) WITHOUT intercept column."""
    n = len(y)
    A = np.column_stack([np.ones(n)] + [X[:, j] for j in range(X.shape[1])]) if X.size else np.ones((n, 1))
    beta, *_ = np.linalg.lstsq(A, y, rcond=None)
    resid = y - A @ beta
    ss_res = float(resid @ resid)
    ss_tot = float(((y - y.mean()) ** 2).sum())
    return (1.0 - ss_res / ss_tot) if ss_tot > 0 else np.nan, beta


def d_r2(y, base_cols, add_col):
    """Incremental plain-OLS R2 from adding add_col to a model containing base_cols."""
    r2_base, _ = ols_r2(y, np.column_stack(base_cols))
    r2_full, beta = ols_r2(y, np.column_stack(list(base_cols) + [add_col]))
    return r2_full - r2_base, r2_base, r2_full, float(beta[-1])


print("=" * 78)
print("E1 I0008 STAGE 1 -- NOISE FLOOR (THE GATE)")
print("=" * 78)
print("R2 convention:", R2_CONVENTION,
      "| plain unweighted OLS, SST about the unweighted mean. NOT the E0 wls_r2 helper.")
print()

df = pd.read_parquet(os.path.join(OUT, "frame.parquet"))
assert_partition(df, "frame.parquet on load")

# ---------------------------------------------------------------------------
# Sanity: recompute the roster aggregate from the frame and confirm it reproduces
# the column built by build_frame.py. Required before the no-op control, which
# recomputes the same aggregate from a permuted key.
# ---------------------------------------------------------------------------
def roster_profile(frame, team_col):
    g = frame.copy()
    g["_hm"] = g["height_inches"] * g["minutes"]
    p = g.groupby([team_col, "season"], as_index=False).agg(_n=("_hm", "sum"), _d=("minutes", "sum"))
    p["prof"] = p["_n"] / p["_d"]
    return p[[team_col, "season", "prof"]]


prof_true = roster_profile(df, "team_id")
chk = df.merge(prof_true.rename(columns={"team_id": "opp_team_id"}), on=["opp_team_id", "season"], how="left")
max_abs = float((chk["prof"] - chk["opp_roster_mean_height"]).abs().max())
print(f"aggregate recomputation check: max|recomputed - stored| = {max_abs:.3e}  (must be ~0)")
assert max_abs < 1e-9, "recomputation of the roster aggregate does not reproduce build_frame.py"
print(f"distinct team-season aggregates: {len(prof_true)}  "
      f"(teams per season: {prof_true.groupby('season').size().to_dict()})")
print(f"opponent roster mean height: min={prof_true['prof'].min():.3f} "
      f"max={prof_true['prof'].max():.3f} sd={prof_true['prof'].std(ddof=0):.3f} inches")
print(f"player own height:           min={df['height_inches'].min():.1f} "
      f"max={df['height_inches'].max():.1f} sd={df['height_inches'].std(ddof=0):.3f} inches")
print()

TARGETS = [
    ("offensive_rebound_percentage", "own_recent_oreb_pct", "OREB%"),
    ("defensive_rebound_percentage", "own_recent_dreb_pct", "DREB%"),
]
FEATURES = [("rung1_height_diff", "opp_roster_mean_height", "rung1 (whole roster)"),
            ("rung2_height_diff", "opp_rotation_mean_height", "rung2 (top-8 rotation)")]

rng = np.random.default_rng(SEED)
results = {}

for feat_col, opp_col, feat_label in FEATURES:
    prof_feat = roster_profile(df, "team_id") if feat_col == "rung1_height_diff" else None
    for target, own, tlabel in TARGETS:
        key = f"{feat_col}|{target}"
        sub = df.dropna(subset=[target, own, feat_col, "height_inches", opp_col]).copy()
        assert_partition(sub, f"analysis rows {feat_label} / {tlabel}")
        y = sub[target].to_numpy(float)
        own_v = sub[own].to_numpy(float)
        feat_v = sub[feat_col].to_numpy(float)
        n = len(sub)

        real_dr2, r2_base, r2_full, beta = d_r2(y, [own_v], feat_v)
        print("-" * 78)
        print(f"REAL EFFECT -- {feat_label} on {tlabel}   n={n}")
        print(f"  R2(own recent rate only)          = {r2_base:.6f}")
        print(f"  R2(own recent rate + height diff) = {r2_full:.6f}")
        print(f"  REAL incremental R2               = {real_dr2:+.6f}   beta={beta:+.6f}")

        # -------------------------------------------------------------------
        # (A) NO-OP CONTROL -- deliberate defect, positive diagnostic
        #     permute the GROUPING KEY, then RECOMPUTE the aggregate from it
        # -------------------------------------------------------------------
        # Reference for the no-op: the SAME recompute path but on the TRUE (unpermuted) key.
        # The aggregate is recomputed from the analysis-row subset, so it differs from the
        # stored full-frame column by ~1e-5; that offset is a property of the recompute, not
        # of the permutation, and the no-op draws must match THIS number exactly.
        _w0 = sub[["season", "team_id", "opp_team_id", "height_inches", "minutes"]].copy()
        _p0 = roster_profile(_w0, "team_id")
        _m0 = _w0.merge(_p0.rename(columns={"team_id": "opp_team_id"}),
                        on=["opp_team_id", "season"], how="left")
        noop_ref, _, _, _ = d_r2(y, [own_v], (_m0["height_inches"] - _m0["prof"]).to_numpy(float))

        noop_dr2 = []
        n_noop = 50  # cheap; the point is the exact-reproduction signature, not a distribution
        for _ in range(n_noop):
            work = sub[["season", "team_id", "opp_team_id", "height_inches", "minutes"]].copy()
            # random bijection of team ids WITHIN season, applied to BOTH key columns
            new_team = np.empty(len(work), dtype=object)
            new_opp = np.empty(len(work), dtype=object)
            for s, idx in work.groupby("season").groups.items():
                teams = np.array(sorted(work.loc[idx, "team_id"].unique()))
                sigma = dict(zip(teams, rng.permutation(teams)))
                mask = work["season"].to_numpy() == s
                new_team[mask] = work.loc[mask, "team_id"].map(sigma).to_numpy()
                new_opp[mask] = work.loc[mask, "opp_team_id"].map(sigma).to_numpy()
            work["team_id_perm"] = new_team
            work["opp_team_id_perm"] = new_opp
            # RECOMPUTE the aggregate from the permuted key -- this is the defect
            p = roster_profile(work, "team_id_perm")
            merged = work.merge(
                p.rename(columns={"team_id_perm": "opp_team_id_perm"}),
                on=["opp_team_id_perm", "season"], how="left",
            )
            fake_feat = (merged["height_inches"] - merged["prof"]).to_numpy(float)
            dr2, _, _, _ = d_r2(y, [own_v], fake_feat)
            noop_dr2.append(dr2)
        noop_dr2 = np.array(noop_dr2)
        print(f"  [A] NO-OP CONTROL (permute grouping key, recompute aggregate), {n_noop} draws")
        print(f"      mean = {noop_dr2.mean():+.6f}   sd = {noop_dr2.std(ddof=0):.6f}  "
              f"(sd exact = {noop_dr2.std(ddof=0):.3e})")
        print(f"      distinct values across all {n_noop} draws = {len(np.unique(noop_dr2))}")
        print(f"      unpermuted-key reference (same recompute path) = {noop_ref:+.6f}")
        print(f"      max|draw - unpermuted reference| = {np.abs(noop_dr2 - noop_ref).max():.3e}")
        print(f"      (stored-column real dR2 = {real_dr2:+.6f}; the ~1e-5 offset is the "
              f"subset recompute, not the permutation)")
        noop_is_noop = bool(noop_dr2.std(ddof=0) < 1e-12
                            and np.abs(noop_dr2 - noop_ref).max() < 1e-12)
        print(f"      DIAGNOSTIC (sd exactly 0.000000, every draw identical, real number "
              f"reproduced) -> {'CONFIRMED NO-OP (as predicted -- this control tests nothing)' if noop_is_noop else 'NOT a no-op'}")

        # -------------------------------------------------------------------
        # (B) REAL CONTROL -- aggregate stays keyed on TRUE opponents; permute
        #     WHICH already-computed aggregate each row receives.
        # -------------------------------------------------------------------
        # B1: team-level permutation of the aggregate across team labels, within season
        prof = roster_profile(df, "team_id") if feat_col == "rung1_height_diff" else None
        if prof is None:
            # rung2 aggregate lives on the frame already; rebuild the team-season lookup
            prof = (df[["opp_team_id", "season", opp_col]]
                    .drop_duplicates()
                    .rename(columns={"opp_team_id": "team_id", opp_col: "prof"}))
        season_arr = sub["season"].to_numpy()
        opp_arr = sub["opp_team_id"].to_numpy()
        own_h = sub["height_inches"].to_numpy(float)

        # per-season lookup tables
        lut = {}
        for s, g in prof.groupby("season"):
            teams = g["team_id"].to_numpy()
            vals = g["prof"].to_numpy(float)
            lut[int(s)] = (teams, vals, {t: i for i, t in enumerate(teams)})

        idx_of_opp = np.empty(len(sub), dtype=int)
        for s in np.unique(season_arr):
            m = season_arr == s
            pos = lut[int(s)][2]
            idx_of_opp[m] = [pos[t] for t in opp_arr[m]]

        b1 = np.empty(N_DRAWS)
        b1_identity = 0
        for d in range(N_DRAWS):
            fake_opp_val = np.empty(len(sub))
            ident = True
            for s in np.unique(season_arr):
                m = season_arr == s
                teams, vals, _ = lut[int(s)]
                perm = rng.permutation(len(vals))
                if not np.array_equal(perm, np.arange(len(vals))):
                    ident = False
                fake_opp_val[m] = vals[perm][idx_of_opp[m]]
            b1_identity += int(ident)
            fake_feat = own_h - fake_opp_val
            dr2, _, _, _ = d_r2(y, [own_v], fake_feat)
            b1[d] = dr2

        # B2: row-level shuffle of the opponent aggregate within season
        b2 = np.empty(N_DRAWS)
        true_opp_val = sub[opp_col].to_numpy(float)
        for d in range(N_DRAWS):
            fake_opp_val = true_opp_val.copy()
            for s in np.unique(season_arr):
                m = season_arr == s
                v = fake_opp_val[m]
                fake_opp_val[m] = rng.permutation(v)
            dr2, _, _, _ = d_r2(y, [own_v], own_h - fake_opp_val)
            b2[d] = dr2

        frac_b1 = float((b1 >= real_dr2).mean())
        frac_b2 = float((b2 >= real_dr2).mean())
        print(f"  [B1] REAL CONTROL, team-level permutation of the aggregate, {N_DRAWS} draws")
        print(f"       mean = {b1.mean():+.6f}   sd = {b1.std(ddof=0):.6f}   "
              f"min = {b1.min():+.6f}   max = {b1.max():+.6f}")
        print(f"       frac_ge_real = {frac_b1:.4f}   (identity permutations drawn: {b1_identity})")
        print(f"  [B2] REAL CONTROL, row-level within-season shuffle, {N_DRAWS} draws")
        print(f"       mean = {b2.mean():+.6f}   sd = {b2.std(ddof=0):.6f}   "
              f"min = {b2.min():+.6f}   max = {b2.max():+.6f}")
        print(f"       frac_ge_real = {frac_b2:.4f}")
        z1 = (real_dr2 - b1.mean()) / b1.std(ddof=0) if b1.std(ddof=0) > 0 else np.nan
        print(f"       z(real vs B1 null) = {z1:+.3f}")

        # -------------------------------------------------------------------
        # Supplementary decomposition -- WHY the null looks the way it does.
        # rung*_height_diff = own_height - opp_aggregate. Split the two parts.
        # -------------------------------------------------------------------
        dr2_ownh, _, _, _ = d_r2(y, [own_v], own_h)
        r2_own_plus_h, _ = ols_r2(y, np.column_stack([own_v, own_h]))
        r2_own_plus_h_plus_opp, beta3 = ols_r2(y, np.column_stack([own_v, own_h, true_opp_val]))
        dr2_opp_given_ownh = r2_own_plus_h_plus_opp - r2_own_plus_h
        print(f"  [decomposition] dR2 from OWN HEIGHT alone over own-rate      = {dr2_ownh:+.6f}")
        print(f"  [decomposition] dR2 from OPPONENT aggregate, given own height = {dr2_opp_given_ownh:+.6f}"
              f"   beta_opp={float(beta3[-1]):+.6f}")

        results[key] = dict(
            feature=feat_col, feature_label=feat_label, target=target, target_label=tlabel,
            own_rate_col=own, n=int(n),
            r2_own_only=r2_base, r2_own_plus_feature=r2_full,
            real_incremental_r2=real_dr2, beta_feature=beta,
            noop_control=dict(
                construction=("permute team_id grouping key within season (bijection applied to "
                              "team_id and opp_team_id), then RECOMPUTE the roster aggregate from "
                              "the permuted key -- deliberately defective"),
                draws=n_noop, mean=float(noop_dr2.mean()), sd=float(noop_dr2.std(ddof=0)),
                distinct_values_across_draws=int(len(np.unique(noop_dr2))),
                unpermuted_key_reference=float(noop_ref),
                max_abs_diff_from_unpermuted_reference=float(np.abs(noop_dr2 - noop_ref).max()),
                max_abs_diff_from_stored_column_real=float(np.abs(noop_dr2 - real_dr2).max()),
                confirmed_noop=noop_is_noop,
                signature=("sd exactly 0.000000 across draws; all draws take a single distinct "
                           "value equal to the unpermuted-key result -- the permutation changes "
                           "nothing, so this control tests nothing"),
            ),
            real_control_B1=dict(
                construction=("aggregate computed ONCE on TRUE opponent rosters; within each season "
                              "the 12 team-season aggregate VALUES are permuted across team labels "
                              "and joined on the row's TRUE opp_team_id"),
                draws=N_DRAWS, mean=float(b1.mean()), sd=float(b1.std(ddof=0)),
                min=float(b1.min()), max=float(b1.max()), frac_ge_real=frac_b1,
                z_real_vs_null=float(z1), identity_draws=int(b1_identity),
            ),
            real_control_B2=dict(
                construction="row-level within-season shuffle of the already-computed opponent aggregate",
                draws=N_DRAWS, mean=float(b2.mean()), sd=float(b2.std(ddof=0)),
                min=float(b2.min()), max=float(b2.max()), frac_ge_real=frac_b2,
            ),
            decomposition=dict(
                dr2_own_height_alone_over_own_rate=dr2_ownh,
                dr2_opponent_aggregate_given_own_height=dr2_opp_given_ownh,
                beta_opponent_aggregate=float(beta3[-1]),
            ),
        )
        print()

# ---------------------------------------------------------------------------
# GATE DECISION
# ---------------------------------------------------------------------------
print("=" * 78)
print("GATE DECISION")
print("=" * 78)
ALPHA = 0.05
cells = []
for k, r in results.items():
    inside = r["real_control_B1"]["frac_ge_real"] > ALPHA
    cells.append((k, r["real_incremental_r2"], r["real_control_B1"]["mean"],
                  r["real_control_B1"]["frac_ge_real"], inside))
    print(f"  {k:58s} real={r['real_incremental_r2']:+.6f}  "
          f"null_mean={r['real_control_B1']['mean']:+.6f}  "
          f"frac_ge_real={r['real_control_B1']['frac_ge_real']:.4f}  "
          f"-> {'INSIDE NOISE FLOOR' if inside else 'clears null'}")

headline_cells = [c for c in cells if c[0].startswith("rung1_height_diff")]
gate_pass = all(not c[4] for c in headline_cells)
decision = "PASS -- proceed to Stage 2" if gate_pass else "KILL -- lead is DEAD, do not proceed to Stage 2"
print()
print(f"  GATE: {decision}")

with open(os.path.join(OUT, "stage1_noise_floor.json"), "w", encoding="utf-8") as fh:
    json.dump(dict(r2_convention=R2_CONVENTION, seed=SEED, draws=N_DRAWS,
                   alpha_for_gate=ALPHA, gate_pass=gate_pass, gate_decision=decision,
                   cells=results), fh, indent=2)
print("wrote stage1_noise_floor.json")
print("DONE stage1_noise_floor")
