"""E0 I0011 -- build the shifted estimator family, select on 2021-2022, score on 2023-2024.

PARTITION: 2021-2024 only. Input frame.parquet is already filtered; re-asserted here.
Selection/scoring split is pre-declared in PRE_DECLARED_SLICES.md.
"""
import itertools
import numpy as np
import pandas as pd

SEED = 20260807
rng = np.random.default_rng(SEED)

PARTITION = [2021, 2022, 2023, 2024]
SELECT = [2021, 2022]
SCORE = [2023, 2024]
HERE = (r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees"
        r"\player-model-program\experiments\exploration\E0_I0011_tendency_estimator")

ALPHAS = [0.05, 0.08, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 0.70]
WINDOWS = [1, 3, 5, 10, 20]
SHRINK_K = [2, 5, 10]
TARGETS = ["pts", "reb", "ast", "minutes"]
MIN_PRIOR = 3

# The two declared reference points the GAP is measured against:
NAIVE = "STD_expanding"                 # season-to-date mean of the per-game total
# props_edge.py lines 13-23 / 312-350, ALPHA = 0.30 "registered frozen family":
#   proj = EWMA_0.30(pts/minutes*36) * EWMA_0.30(minutes) / 36, gate >= 3 prior
#   played appearances in the season. NOTE this is an EWMA OF THE RATIO, which is
#   NOT the same object as a ratio of EWMAs; PER36_* below reproduces it faithfully.
INCUMBENT = "PER36_a0.30_m0.30"

df = pd.read_parquet(HERE + r"\frame.parquet")
assert set(df["season"].unique()) <= set(PARTITION), df["season"].unique()
print("[partition-check] frame:", sorted(df["season"].unique()), df.shape)

df = df.sort_values(["player_id", "season", "game_date", "game_id"]).reset_index(drop=True)
KEY = ["player_id", "season"]
gk = [df["player_id"], df["season"]]


def prior_shift(col):
    """Series whose value at t is the observation at t-1 (within player-season)."""
    return df.groupby(KEY, sort=False)[col].shift(1)


def ewm_of(s, alpha):
    return s.groupby(gk, sort=False).transform(
        lambda x: x.ewm(alpha=alpha, adjust=True, ignore_na=True).mean())


def roll_of(s, w):
    return s.groupby(gk, sort=False).transform(
        lambda x: x.rolling(w, min_periods=1).mean())


def exp_of(s):
    return s.groupby(gk, sort=False).transform(lambda x: x.expanding(min_periods=1).mean())


def reversed_ewm(s, alpha):
    """Negative control: same prior history, recency weights INVERTED."""
    out = np.full(len(s), np.nan)
    vals = s.values
    for _, idx in s.groupby(gk, sort=False).groups.items():
        pos = df.index.get_indexer(idx)
        hist = []
        for j, p in enumerate(pos):
            v = vals[p]
            if len(hist) > 0:
                h = np.asarray(hist, dtype=float)          # oldest first
                w = (1 - alpha) ** np.arange(len(h))       # oldest gets weight 1
                out[p] = float((h * w).sum() / w.sum())
            if not np.isnan(v):
                hist.append(v)
    return pd.Series(out, index=s.index)


# donor mapping for NEG_other_player: shuffle player-seasons within season
ps = df[KEY].drop_duplicates().reset_index(drop=True)
donor_map = {}
for season, grp in ps.groupby("season"):
    pids = grp["player_id"].values.copy()
    perm = rng.permutation(len(pids))
    # derange-ish: rotate by 1 after shuffle so nobody maps to self
    shuffled = pids[perm]
    rolled = np.roll(shuffled, 1)
    for a, b in zip(shuffled, rolled):
        donor_map[(a, season)] = b

print("built donor map for NEG_other_player, entries:", len(donor_map))

results_rows = []
pred_store = {}

for tgt in TARGETS:
    print(f"\n=== building estimators for target={tgt} ===")
    y = df[tgt].astype(float)
    sh_y = prior_shift(tgt)
    sh_min = prior_shift("minutes")
    sh_poss = prior_shift("possessions")
    cg = df["c_g_" + tgt]
    ct = df["c_t_" + tgt]
    sh_y_ctx = prior_shift("_tmp_ctx") if False else None
    df["_ynorm"] = df[tgt].astype(float) / cg
    sh_ynorm = prior_shift("_ynorm")

    P = {}
    # ---- naive default: season-to-date mean of the per-game total
    P[NAIVE] = exp_of(sh_y)
    # ---- fixed-window rolling means on the raw total
    for w in WINDOWS:
        P[f"ROLL_w{w}"] = roll_of(sh_y, w)
    # ---- EWMA on the raw per-game total
    ewm_y = {a: ewm_of(sh_y, a) for a in ALPHAS}
    ewm_min = {a: ewm_of(sh_min, a) for a in ALPHAS}
    ewm_poss = {a: ewm_of(sh_poss, a) for a in ALPHAS}
    ewm_ynorm = {a: ewm_of(sh_ynorm, a) for a in ALPHAS}
    for a in ALPHAS:
        P[f"TOT_a{a:.2f}"] = ewm_y[a]
    # ---- context-normalised total (THE THESIS ARM)
    P["CTXSTD_expanding"] = exp_of(sh_ynorm) * ct
    for a in ALPHAS:
        P[f"CTX_a{a:.2f}"] = ewm_ynorm[a] * ct
    for w in WINDOWS:
        P[f"CTXROLL_w{w}"] = roll_of(sh_ynorm, w) * ct
    # ---- prior-season shrunk on the raw total
    n = df["n_prior"].astype(float)
    for a in ALPHAS:
        for k in SHRINK_K:
            P[f"SHRINK_a{a:.2f}_k{k}"] = (n * ewm_y[a] + k * df["prior_" + tgt]) / (n + k)
    # ---- INCUMBENT-FAITHFUL arm: EWMA of the per-36 RATE x EWMA of minutes.
    #      (props_edge.py). Distinct from RATE36 below, which is a ratio of EWMAs.
    if tgt != "minutes":
        df["_per36"] = df[tgt].astype(float) / df["minutes"] * 36.0
        df["_per36ctx"] = df["_per36"] / cg
        poss_safe = df["possessions"].where(df["possessions"] > 0)
        df["_per100"] = df[tgt].astype(float) / poss_safe * 100.0
        sh_per36 = prior_shift("_per36")
        sh_per36ctx = prior_shift("_per36ctx")
        sh_per100 = prior_shift("_per100")
        ewm_per36 = {a: ewm_of(sh_per36, a) for a in ALPHAS}
        ewm_per36ctx = {a: ewm_of(sh_per36ctx, a) for a in ALPHAS}
        ewm_per100 = {a: ewm_of(sh_per100, a) for a in ALPHAS}
        for ar, am in itertools.product(ALPHAS, ALPHAS):
            P[f"PER36_a{ar:.2f}_m{am:.2f}"] = ewm_per36[ar] * ewm_min[am] / 36.0
            P[f"PER36CTX_a{ar:.2f}_m{am:.2f}"] = ewm_per36ctx[ar] * ewm_min[am] / 36.0 * ct
            P[f"PER100_a{ar:.2f}_p{am:.2f}"] = ewm_per100[ar] * ewm_poss[am] / 100.0
        df.drop(columns=["_per36", "_per36ctx", "_per100"], inplace=True)
    # ---- rate x exposure arms (opportunity separated from efficiency)
    if tgt != "minutes":
        for ar, am in itertools.product(ALPHAS, ALPHAS):
            P[f"RATE36_a{ar:.2f}_m{am:.2f}"] = (ewm_y[ar] / ewm_min[ar]) * ewm_min[am]
            P[f"RATE36CTX_a{ar:.2f}_m{am:.2f}"] = (
                (ewm_ynorm[ar] / ewm_min[ar]) * ewm_min[am] * ct)
        for ar, am in itertools.product(ALPHAS, ALPHAS):
            denom = ewm_poss[ar].replace(0, np.nan)
            P[f"RATE100_a{ar:.2f}_p{am:.2f}"] = (ewm_y[ar] / denom) * ewm_poss[am]
    # ---- negative controls
    P["NEG_reversed_a0.30"] = reversed_ewm(sh_y, 0.30)
    P["NEG_league_const"] = pd.Series(
        float(df.loc[df["season"].isin(SELECT), tgt].mean()), index=df.index)
    std_by_idx = exp_of(sh_y)
    lut = {}
    for (pid, ssn), grp in df.groupby(KEY, sort=False):
        lut[(pid, ssn)] = std_by_idx.loc[grp.index].values
    neg_other = np.full(len(df), np.nan)
    for (pid, ssn), grp in df.groupby(KEY, sort=False):
        d = donor_map.get((pid, ssn))
        arr = lut.get((d, ssn))
        if arr is None:
            continue
        pos = df.index.get_indexer(grp.index)
        for j, p in enumerate(pos):
            neg_other[p] = arr[min(j, len(arr) - 1)]
    P["NEG_other_player"] = pd.Series(neg_other, index=df.index)

    pred_store[tgt] = P
    print(f"  {len(P)} estimator configs built for {tgt}")

df.drop(columns=["_ynorm"], inplace=True)

# --------------------------------------------------------------------- scoring
mask_eval = (df["n_prior"] >= MIN_PRIOR) & (df["minutes"] > 0)
print("\neval universe rows (n_prior>=3):", int(mask_eval.sum()))
print(df.loc[mask_eval].groupby("season").size().to_dict())


def metrics(tgt, pred, mask):
    y = df[tgt].astype(float)
    m = mask & pred.notna() & y.notna()
    e = (pred[m] - y[m]).values
    return len(e), float(np.abs(e).mean()), float(np.sqrt((e ** 2).mean()))


rows = []
for tgt in TARGETS:
    for name, pred in pred_store[tgt].items():
        for label, seasons in [("SELECT_2021_2022", SELECT), ("2023", [2023]),
                               ("2024", [2024]), ("SCORE_pooled", SCORE)]:
            m = mask_eval & df["season"].isin(seasons)
            n, mae, rmse = metrics(tgt, pred, m)
            rows.append(dict(target=tgt, estimator=name, split=label, n=n, mae=mae, rmse=rmse))
res = pd.DataFrame(rows)
res.to_csv(HERE + r"\all_estimator_metrics.csv", index=False)
print("\nwrote all_estimator_metrics.csv", res.shape)

sel_mae = res[res.split == "SELECT_2021_2022"].set_index(["target", "estimator"])["mae"]


def family(name):
    if name.startswith("NEG_"):
        return "NEG"
    for f in ["STD_expanding", "CTXSTD_expanding", "ROLL_", "CTXROLL_", "TOT_", "CTX_",
              "SHRINK_", "RATE36CTX_", "RATE36_", "RATE100_", "PER36CTX_", "PER36_",
              "PER100_"]:
        if name.startswith(f):
            return f.rstrip("_")
    return "OTHER"


res["family"] = res["estimator"].map(family)

# ----- family-wise selection on 2021-2022 only, then score on 2023/2024
picks = []
for tgt in TARGETS:
    sub = res[(res.target == tgt) & (res.split == "SELECT_2021_2022")]
    for fam, g in sub.groupby("family"):
        best = g.loc[g["mae"].idxmin()]
        picks.append(dict(target=tgt, family=fam, selected=best["estimator"],
                          select_mae=best["mae"]))
picks = pd.DataFrame(picks)
picks.to_csv(HERE + r"\family_selections.csv", index=False)

print("\n" + "=" * 100)
print("FAMILY SELECTION (chosen on 2021-2022 ONLY) and OUT-OF-SAMPLE SCORE on 2023/2024")
print("=" * 100)
skill_rows = []
for tgt in TARGETS:
    naive = res[(res.target == tgt) & (res.estimator == NAIVE)].set_index("split")
    print(f"\n--- target = {tgt} ---")
    print(f"{'family':<18}{'selected config':<30}{'sel MAE':>9}{'2023 MAE':>10}"
          f"{'2024 MAE':>10}{'pool MAE':>10}{'pool RMSE':>11}"
          f"{'skill23':>9}{'skill24':>9}{'skillP':>9}")
    tp = picks[picks.target == tgt].sort_values("select_mae")
    for _, r in tp.iterrows():
        e = res[(res.target == tgt) & (res.estimator == r["selected"])].set_index("split")
        sk = {s: 100 * (naive.loc[s, "mae"] - e.loc[s, "mae"]) / naive.loc[s, "mae"]
              for s in ["2023", "2024", "SCORE_pooled"]}
        print(f"{r['family']:<18}{r['selected']:<30}{r['select_mae']:>9.4f}"
              f"{e.loc['2023','mae']:>10.4f}{e.loc['2024','mae']:>10.4f}"
              f"{e.loc['SCORE_pooled','mae']:>10.4f}{e.loc['SCORE_pooled','rmse']:>11.4f}"
              f"{sk['2023']:>8.2f}%{sk['2024']:>8.2f}%{sk['SCORE_pooled']:>8.2f}%")
        skill_rows.append(dict(target=tgt, family=r["family"], selected=r["selected"],
                               mae_2023=e.loc["2023", "mae"], mae_2024=e.loc["2024", "mae"],
                               mae_pool=e.loc["SCORE_pooled", "mae"],
                               rmse_pool=e.loc["SCORE_pooled", "rmse"],
                               skill_2023=sk["2023"], skill_2024=sk["2024"],
                               skill_pool=sk["SCORE_pooled"]))
pd.DataFrame(skill_rows).to_csv(HERE + r"\family_scored.csv", index=False)

# ----- the GAP: tuned best vs the two declared defaults
print("\n" + "=" * 100)
print("THE GAP -- tuned (selected on 2021-22) vs NAIVE default vs PROGRAM INCUMBENT")
print("NAIVE     = " + NAIVE + "  (season-to-date mean of the per-game total)")
print("INCUMBENT = " + INCUMBENT + "  (props_edge.py ALPHA=0.30 per-36 rate x EWMA minutes)")
print("=" * 100)
gap_rows = []
for tgt in TARGETS:
    sub = res[(res.target == tgt) & (res.split == "SELECT_2021_2022") &
              (~res.estimator.str.startswith("NEG_"))]
    best_name = sub.loc[sub["mae"].idxmin(), "estimator"]
    inc = INCUMBENT if tgt != "minutes" else "TOT_a0.30"
    print(f"\n--- {tgt} --- tuned pick = {best_name}"
          + (f"   (incumbent for minutes taken as TOT_a0.30)" if tgt == "minutes" else ""))
    print(f"{'estimator':<32}{'2023 MAE':>10}{'2024 MAE':>10}{'pool MAE':>10}"
          f"{'2023 RMSE':>11}{'2024 RMSE':>11}")
    for nm in [best_name, inc, NAIVE]:
        e = res[(res.target == tgt) & (res.estimator == nm)].set_index("split")
        print(f"{nm:<32}{e.loc['2023','mae']:>10.4f}{e.loc['2024','mae']:>10.4f}"
              f"{e.loc['SCORE_pooled','mae']:>10.4f}{e.loc['2023','rmse']:>11.4f}"
              f"{e.loc['2024','rmse']:>11.4f}")
    eb = res[(res.target == tgt) & (res.estimator == best_name)].set_index("split")
    ei = res[(res.target == tgt) & (res.estimator == inc)].set_index("split")
    en = res[(res.target == tgt) & (res.estimator == NAIVE)].set_index("split")
    for s in ["2023", "2024", "SCORE_pooled"]:
        g_naive = 100 * (en.loc[s, "mae"] - eb.loc[s, "mae"]) / en.loc[s, "mae"]
        g_inc = 100 * (ei.loc[s, "mae"] - eb.loc[s, "mae"]) / ei.loc[s, "mae"]
        print(f"   GAP {s:<14} vs naive {g_naive:+6.2f}%   vs incumbent {g_inc:+6.2f}%")
        gap_rows.append(dict(target=tgt, split=s, tuned=best_name,
                             mae_tuned=eb.loc[s, "mae"], mae_incumbent=ei.loc[s, "mae"],
                             mae_naive=en.loc[s, "mae"], gap_vs_naive_pct=g_naive,
                             gap_vs_incumbent_pct=g_inc))
pd.DataFrame(gap_rows).to_csv(HERE + r"\gap_table.csv", index=False)

# ----- normalisation contrast: matched pairs, same family/alpha, ctx vs raw
print("\n" + "=" * 100)
print("NORMALISATION CONTRAST -- identical estimator, context-normalised vs raw")
print("(negative delta = normalisation HELPS)")
print("=" * 100)
norm_rows = []
for tgt in TARGETS:
    print(f"\n--- {tgt} ---")
    print(f"{'pair':<40}{'2023 dMAE':>11}{'2024 dMAE':>11}{'pool dMAE%':>12}")
    pairs = [(f"CTX_a{a:.2f}", f"TOT_a{a:.2f}") for a in ALPHAS]
    pairs += [("CTXSTD_expanding", "STD_expanding")]
    if tgt != "minutes":
        # NOTE: RATE36CTX_a_m vs RATE36_a_m at EQUAL alphas degenerates to
        # CTX vs TOT (ratio of EWMAs with a common alpha cancels), so the
        # informative pairs are the off-diagonal ones actually selected.
        pairs += [(f"RATE36CTX_a{ar:.2f}_m{am:.2f}", f"RATE36_a{ar:.2f}_m{am:.2f}")
                  for ar in [0.05, 0.10] for am in [0.20, 0.30]]
        pairs += [(f"PER36CTX_a{ar:.2f}_m{am:.2f}", f"PER36_a{ar:.2f}_m{am:.2f}")
                  for ar in [0.05, 0.10, 0.30] for am in [0.20, 0.30]]
    for cn, rn in pairs:
        ec = res[(res.target == tgt) & (res.estimator == cn)].set_index("split")
        er = res[(res.target == tgt) & (res.estimator == rn)].set_index("split")
        if ec.empty or er.empty:
            continue
        d23 = ec.loc["2023", "mae"] - er.loc["2023", "mae"]
        d24 = ec.loc["2024", "mae"] - er.loc["2024", "mae"]
        dp = 100 * (ec.loc["SCORE_pooled", "mae"] - er.loc["SCORE_pooled", "mae"]) / \
            er.loc["SCORE_pooled", "mae"]
        print(f"{cn + ' vs ' + rn:<40}{d23:>+11.4f}{d24:>+11.4f}{dp:>+11.3f}%")
        norm_rows.append(dict(target=tgt, ctx=cn, raw=rn, d_mae_2023=d23, d_mae_2024=d24,
                              d_mae_pool_pct=dp))
pd.DataFrame(norm_rows).to_csv(HERE + r"\normalisation_contrast.csv", index=False)

# ----- negative control ranking
print("\n" + "=" * 100)
print("NEGATIVE CONTROL RANKING -- pooled 2023+2024 MAE, headline estimators + controls")
print("=" * 100)
neg_rows = []
for tgt in TARGETS:
    head = [NAIVE] + [p for p in picks[picks.target == tgt]["selected"].tolist()
                      if not p.startswith("NEG_")]
    head = list(dict.fromkeys(head)) + ["NEG_reversed_a0.30", "NEG_league_const",
                                        "NEG_other_player"]
    e = res[(res.target == tgt) & (res.split == "SCORE_pooled") &
            (res.estimator.isin(head))].sort_values("mae").reset_index(drop=True)
    print(f"\n--- {tgt} ---")
    for i, r in e.iterrows():
        flag = "  <-- NEGATIVE CONTROL" if r["estimator"].startswith("NEG_") else ""
        print(f"  rank {i+1:>2}  {r['estimator']:<32} MAE {r['mae']:.4f}{flag}")
        neg_rows.append(dict(target=tgt, rank=i + 1, estimator=r["estimator"], mae=r["mae"]))
pd.DataFrame(neg_rows).to_csv(HERE + r"\negative_control_ranking.csv", index=False)

# ----- heterogeneity on the PRE-DECLARED slices
print("\n" + "=" * 100)
print("HETEROGENEITY -- best alpha re-selected WITHIN each pre-declared slice on 2021-2022,")
print("then scored in-slice on 2023 and 2024 separately. Families: TOT (raw EWMA total).")
print("=" * 100)
u = df.loc[df["season"].isin(SELECT) & mask_eval, "std_usage"].dropna()
q1, q2 = u.quantile([1 / 3, 2 / 3])
print(f"usage terciles cut on SELECTION seasons only: q33={q1:.4f} q67={q2:.4f}")

slices = {}
slices["S1_starter=1"] = df["starter_flag"] == 1
slices["S1_starter=0"] = df["starter_flag"] == 0
slices["S2_min<15"] = df["std_minutes"] < 15
slices["S2_min15-25"] = (df["std_minutes"] >= 15) & (df["std_minutes"] < 25)
slices["S2_min>=25"] = df["std_minutes"] >= 25
slices["S3_usage_low"] = df["std_usage"] < q1
slices["S3_usage_mid"] = (df["std_usage"] >= q1) & (df["std_usage"] < q2)
slices["S3_usage_high"] = df["std_usage"] >= q2
slices["S4_nprior3-7"] = (df["n_prior"] >= 3) & (df["n_prior"] <= 7)
slices["S4_nprior8-19"] = (df["n_prior"] >= 8) & (df["n_prior"] <= 19)
slices["S4_nprior>=20"] = df["n_prior"] >= 20
slices["S5_regular"] = df["season_type"] == "Regular Season"
slices["S5_playoffs"] = df["season_type"] == "Playoffs"

het_rows = []
for tgt in TARGETS:
    print(f"\n--- {tgt} ---")
    print(f"{'slice':<20}{'best alpha (sel)':>18}{'n sel':>8}{'n 23':>7}{'n 24':>7}"
          f"{'skill23 vs naive':>18}{'skill24 vs naive':>18}")
    for sname, smask in slices.items():
        msel = mask_eval & smask & df["season"].isin(SELECT)
        if msel.sum() < 200:
            print(f"{sname:<20}{'(too few sel rows)':>18}{int(msel.sum()):>8}")
            continue
        best_a, best_m = None, np.inf
        for a in ALPHAS:
            _, m, _ = metrics(tgt, pred_store[tgt][f"TOT_a{a:.2f}"], msel)
            if m < best_m:
                best_a, best_m = a, m
        out = {}
        for s in ["2023", "2024"]:
            mm = mask_eval & smask & (df["season"] == int(s))
            n_b, mae_b, _ = metrics(tgt, pred_store[tgt][f"TOT_a{best_a:.2f}"], mm)
            n_n, mae_n, _ = metrics(tgt, pred_store[tgt][NAIVE], mm)
            out[s] = (n_b, 100 * (mae_n - mae_b) / mae_n if mae_n else np.nan, mae_b, mae_n)
        print(f"{sname:<20}{best_a:>18.2f}{int(msel.sum()):>8}{out['2023'][0]:>7}"
              f"{out['2024'][0]:>7}{out['2023'][1]:>17.2f}%{out['2024'][1]:>17.2f}%")
        het_rows.append(dict(target=tgt, slice=sname, best_alpha_selected=best_a,
                             n_select=int(msel.sum()), n_2023=out["2023"][0],
                             n_2024=out["2024"][0], skill_2023=out["2023"][1],
                             skill_2024=out["2024"][1], mae_2023=out["2023"][2],
                             mae_2024=out["2024"][2], naive_mae_2023=out["2023"][3],
                             naive_mae_2024=out["2024"][3]))
pd.DataFrame(het_rows).to_csv(HERE + r"\heterogeneity.csv", index=False)

# ----- early-season report (n_prior 1-2), outside the main eval universe
print("\n" + "=" * 100)
print("EARLY SEASON (n_prior in 1-2) -- does prior-season shrinkage buy anything?")
print("=" * 100)
early = (df["n_prior"] >= 1) & (df["n_prior"] <= 2) & (df["minutes"] > 0)
early_rows = []
for tgt in TARGETS:
    sub = []
    cands = [NAIVE, "TOT_a0.30", "ROLL_w1"] + [f"SHRINK_a{a:.2f}_k{k}"
                                               for a in [0.30, 0.50] for k in SHRINK_K]
    print(f"\n--- {tgt} ---  (n early 2023/2024 = "
          f"{int((early & (df.season==2023)).sum())}/{int((early & (df.season==2024)).sum())})")
    for nm in cands:
        r = {}
        for s, seasons in [("sel", SELECT), ("2023", [2023]), ("2024", [2024])]:
            _, mae, _ = metrics(tgt, pred_store[tgt][nm], early & df["season"].isin(seasons))
            r[s] = mae
        print(f"  {nm:<24} sel {r['sel']:.4f}   2023 {r['2023']:.4f}   2024 {r['2024']:.4f}")
        early_rows.append(dict(target=tgt, estimator=nm, mae_select=r["sel"],
                               mae_2023=r["2023"], mae_2024=r["2024"]))
pd.DataFrame(early_rows).to_csv(HERE + r"\early_season.csv", index=False)

# ----- descriptive stability of the GAP: player-clustered paired bootstrap.
# NOT a significance test and NOT reported as one -- it exists only to answer
# "is this difference distinguishable from noise, or is the comparison too
# noisy to say anything at all" (discipline 4).
print("\n" + "=" * 100)
print("GAP STABILITY -- player-clustered paired bootstrap of the MAE difference")
print("(1000 resamples of PLAYERS with replacement, per scored season; descriptive only,")
print(" 'win share' = fraction of resamples where the tuned estimator has lower MAE)")
print("=" * 100)
gapdf = pd.read_csv(HERE + r"\gap_table.csv")
boot_rows = []
for tgt in TARGETS:
    tuned = gapdf[gapdf.target == tgt]["tuned"].iloc[0]
    inc = INCUMBENT if tgt != "minutes" else "TOT_a0.30"
    print(f"\n--- {tgt} --- tuned={tuned}")
    for s in [2023, 2024]:
        m = mask_eval & (df["season"] == s)
        idx = df.index[m]
        pid = df.loc[idx, "player_id"].values
        y = df.loc[idx, tgt].astype(float).values
        et = np.abs(pred_store[tgt][tuned].loc[idx].values - y)
        for ref_name, ref in [("naive", NAIVE), ("incumbent", inc)]:
            er = np.abs(pred_store[tgt][ref].loc[idx].values - y)
            d = er - et                      # positive => tuned better
            ok = ~(np.isnan(d))
            players = np.unique(pid[ok])
            by_p = {p: d[ok][pid[ok] == p] for p in players}
            brng = np.random.default_rng(SEED + s)
            wins, means = 0, []
            for _ in range(1000):
                samp = brng.choice(players, size=len(players), replace=True)
                v = np.concatenate([by_p[p] for p in samp])
                mv = v.mean()
                means.append(mv)
                wins += mv > 0
            means = np.array(means)
            print(f"  {s} vs {ref_name:<10} mean dMAE {d[ok].mean():+.4f}  "
                  f"boot 5-95% [{np.percentile(means,5):+.4f},{np.percentile(means,95):+.4f}]  "
                  f"win share {wins/1000:.3f}")
            boot_rows.append(dict(target=tgt, season=s, tuned=tuned, reference=ref_name,
                                  ref_estimator=ref, mean_d_mae=float(d[ok].mean()),
                                  p05=float(np.percentile(means, 5)),
                                  p95=float(np.percentile(means, 95)),
                                  win_share=wins / 1000))
pd.DataFrame(boot_rows).to_csv(HERE + r"\gap_bootstrap.csv", index=False)

print("\nDONE.")
