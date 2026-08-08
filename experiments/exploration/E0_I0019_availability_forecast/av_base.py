"""
E0_I0019 AVAILABILITY FORECAST (`p_active`) -- shared loader / feature builder / metrics.

PARTITION (GRAPH_POLICY 13.2): seasons 2021-2024 ONLY, and the SCREEN is 2022-2024 because the
    2021 fold is degenerate (n_train_rows=0, model_was_fitted=false) in BOTH arms.  Enforced by
    VALUE tests via screenkit.assert_partition plus an explicit max(game_date) < 2025-01-01
    assertion at every load and before every write.  No byte/regex scan is used as a check.

FORECAST SOURCE:
    PRIMARY  experiments/cbs_v15_player_oof_v5/attempt_001/predictions__p_active__<S>.parquet
    SECOND   experiments/cbs_v14_player_oof/attempt_001/predictions__p_active__<S>.parquet
    Both are season-chronological walk-forwards: the fold for season S is fitted only on seasons
    < S (fold_receipt__<S>.json :: train_seasons, model_was_fitted, fold_boundary receipt ok,
    provenance_history receipt ok, own_outcome_never_informed_its_forecast = true,
    forecast_scored_against_outcome = false).

    Each per-season artifact is asof_granularity "artifact" -- screenkit.check_manifest therefore
    returns UNUSABLE, which is the correct generic verdict.  D076's reasoning is that each file is
    bound at its OWN season (fit_through_season == S <= 2024), so the whole artifact sits inside
    the exploration partition and no row filtering is relied upon.  THIS SCREEN VERIFIES THAT
    RATHER THAN INHERITING IT: every row_uid in each file is joined to the manifest-carrying
    contract and the resulting season / game_date VALUES are asserted to equal the file's own
    season.  See s01.

ROW UNIVERSE:
    v15's declared row universe is `prediction_contract_v5`, which has NO SIBLING MANIFESTS at all
    (experiments/prediction_contract_v5/ contains player_game.parquet with no .manifest.json).
    Under this program's own discipline (D076 refused minutes_baselines/test_predictions.csv on
    exactly that ground) contract v5 is UNVERIFIABLE and is NOT OPENED.  The screen therefore uses
    experiments/prediction_contract_v4/player_game.parquet (asof_granularity "row", manifest
    present, USABLE_IF_FILTERED) and keeps only p_active rows whose row_uid appears in it -- which
    is exactly v15's Tier-A_primary subset.  The v14 arm's universe IS contract v4, so both arms
    are scored on the SAME rows.

FORBIDDEN ARTIFACTS (GRAPH_POLICY 13.2.1):
    data/w1_truth/player_game_availability.csv  -- asof_granularity "artifact",
    fit_through_season 2026.  data/w1_truth/roster_asof.csv -- same.  Filtering does NOT help.
    BOTH ARE EXACTLY WHAT AN AVAILABILITY SCREEN REACHES FOR FIRST, AND NEITHER IS OPENED.  Only
    their manifests are read.  Availability is rebuilt from master_player BOX MEMBERSHIP, as D076
    did, and cross-checked against the contract's own `appeared` column.

RETROSPECTIVE-BASELINE RULE: every constructed candidate AND every reference is a STRICTLY-PRIOR
    expanding or trailing window, built by sort-by-date then .shift(1) before any cumsum/rolling.
    No full-season aggregate, no leave-one-out, no entity-season mean, anywhere -- including
    inside the inference machinery (D085's sixth instance entered through exactly that door).
    See the TIME-WINDOW TABLE in NOTES.md, which covers inference steps as well as features.

NO MODEL FITTING: nothing is retrained.  References are strictly-prior means and Beta-shrunk
    strictly-prior means with an a-priori pseudo-count; no coefficients are estimated from the
    scored rows.  The only regressions run are the FWL slope t-statistics of the screen itself.
"""
import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
OUT = os.path.join(ROOT, r"experiments\exploration\E0_I0019_availability_forecast")
KIT = os.path.join(ROOT, r"experiments\exploration\_screen_kit")
if KIT not in sys.path:
    sys.path.insert(0, KIT)
import screenkit as sk  # noqa: E402

ARM_DIR = {
    "v15": os.path.join(ROOT, r"experiments\cbs_v15_player_oof_v5\attempt_001"),
    "v14": os.path.join(ROOT, r"experiments\cbs_v14_player_oof\attempt_001"),
}
CONTRACT = os.path.join(ROOT, r"experiments\prediction_contract_v4\player_game.parquet")
MASTER = os.path.join(ROOT, r"data\masters\master_player.parquet")

PARTITION = [2021, 2022, 2023, 2024]
SCREEN_SEASONS = [2022, 2023, 2024]
HOLDOUT = {2025, 2026}

EPS = 1e-6           # probability clip for log loss
PSEUDO_K = 5.0       # a-priori Beta pseudo-count for the shrunk prior-appearance reference


def hdr(s):
    print("\n" + "=" * 100)
    print(s)
    print("=" * 100)


def guard(df, where, col="season"):
    """VALUE-level partition guard: seasons and, where present, dates."""
    s = set(int(x) for x in pd.unique(df[col]))
    bad = s & HOLDOUT
    if bad:
        raise SystemExit("PARTITION VIOLATION at %s: %s" % (where, sorted(bad)))
    dmax = None
    for c in ["gdate", "game_date"]:
        if c in df.columns:
            d = pd.to_datetime(df[c], errors="coerce")
            if d.notna().any():
                dmax = d.max()
                if dmax >= pd.Timestamp("2025-01-01"):
                    raise SystemExit("PARTITION VIOLATION (date) at %s: %s" % (where, dmax))
            break
    print("  guard ok  %-46s n=%-7d seasons=%s max_date=%s"
          % (where, len(df), sorted(s), None if dmax is None else str(dmax.date())))


def safe_write_csv(df, name):
    if "season" in df.columns:
        guard(df, "write:" + name)
    df.to_csv(os.path.join(OUT, name), index=False)
    print("  wrote %s (%d rows)" % (name, len(df)))


def defect(tag, text):
    """Write a self-identified defect to disk IMMEDIATELY (constraint 10)."""
    p = os.path.join(OUT, "DEFECTS.md")
    with open(p, "a", encoding="utf-8") as fh:
        fh.write("\n## %s\n\n%s\n" % (tag, text))
    print("  !! DEFECT RECORDED [%s] -> DEFECTS.md" % tag)


# --------------------------------------------------------------------------- loaders
def load_contract():
    r = sk.check_manifest(CONTRACT)
    print("  contract_v4 manifest status = %s" % r.get("status"))
    assert r.get("status") == "USABLE_IF_FILTERED", r.get("status")
    c = pd.read_parquet(CONTRACT)
    c = c[c["season"].isin(PARTITION)].copy()               # FILTER-POINT (granularity row)
    c["gdate"] = pd.to_datetime(c["game_date"])
    guard(c, "contract_v4 after load")
    return c


def load_master():
    r = sk.check_manifest(MASTER)
    print("  master_player manifest status = %s" % r.get("status"))
    assert r.get("status") == "USABLE_IF_FILTERED", r.get("status")
    mp = pd.read_parquet(MASTER)
    mp = mp[mp["season"].isin(PARTITION)].copy()            # FILTER-POINT (granularity row)
    mp["gdate"] = pd.to_datetime(mp["game_date"])
    mp["minutes"] = pd.to_numeric(mp["minutes"], errors="coerce").fillna(0.0)
    mp["appeared"] = mp["minutes"] > 0                      # BOX MEMBERSHIP, D076's rebuild
    mp = mp.drop(columns=[c for c in ["observed_time"] if c in mp.columns])
    guard(mp, "master_player after load")
    return mp


PA_COLS = ["row_uid", "pred_point", "is_fallback", "fallback_level", "is_cold_start",
           "n_prior_games", "component_id", "forecast_cutoff", "model_hash", "config_hash",
           "data_snapshot_hash", "exclusion_reason"]


def load_p_active(arm, seasons=SCREEN_SEASONS, verbose=True):
    """Load per-season p_active artifacts for one arm.  Each file's OWN manifest is inspected;
    fit_through_season must be <= 2024 so the whole artifact lies inside the partition."""
    out = []
    meta = {}
    for s in seasons:
        p = os.path.join(ARM_DIR[arm], "predictions__p_active__%d.parquet" % s)
        m = json.load(open(p + ".manifest.json"))
        fts = m.get("fit_through_season")
        kit = sk.check_manifest(p)
        meta[s] = dict(asof_granularity=m.get("asof_granularity"), fit_through_season=fts,
                       fit_seasons=m.get("fit_seasons"),
                       fit_through_date=m.get("fit_through_date"),
                       scores_computed=m.get("scores_computed"),
                       generation_only=m.get("generation_only"),
                       kit_status=kit.get("status"),
                       content_sha256=m.get("content_sha256"))
        if fts is None or int(fts) > 2024:
            raise SystemExit("REFUSED: %s bound at season %s" % (p, fts))
        d = pd.read_parquet(p)[PA_COLS].copy()
        d["__file_season"] = s
        out.append(d)
        if verbose:
            print("  %s p_active %d  rows=%-6d asof=%-9s fit_seasons=%-16s fit_through_season=%s"
                  % (arm, s, len(d), m.get("asof_granularity"), m.get("fit_seasons"), fts))
    return pd.concat(out, ignore_index=True), meta


# --------------------------------------------------------------------------- metrics (no scipy)
def brier(y, p):
    y = np.asarray(y, float)
    p = np.asarray(p, float)
    return float(np.mean((y - p) ** 2))


def logloss(y, p):
    y = np.asarray(y, float)
    p = np.clip(np.asarray(p, float), EPS, 1 - EPS)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def auc_mw(y, p):
    """Mann-Whitney AUC with mid-ranks for ties.  numpy only."""
    y = np.asarray(y, float)
    p = np.asarray(p, float)
    m = np.isfinite(y) & np.isfinite(p)
    y, p = y[m], p[m]
    n1 = float((y == 1).sum())
    n0 = float((y == 0).sum())
    if n1 == 0 or n0 == 0:
        return np.nan
    order = np.argsort(p, kind="mergesort")
    ps = p[order]
    ranks = np.empty(len(ps), float)
    i = 0
    while i < len(ps):
        j = i
        while j + 1 < len(ps) and ps[j + 1] == ps[i]:
            j += 1
        ranks[i:j + 1] = 0.5 * (i + j) + 1.0
        i = j + 1
    r = np.empty(len(ps), float)
    r[order] = ranks
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))


def murphy(y, p, n_bins=20):
    """Brier = reliability - resolution + uncertainty, on equal-width probability bins.
    Returns the three terms plus the bin table.  Nothing is fitted."""
    y = np.asarray(y, float)
    p = np.asarray(p, float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.clip(np.digitize(p, edges[1:-1], right=False), 0, n_bins - 1)
    ybar = y.mean()
    rel = 0.0
    res = 0.0
    rows = []
    n = len(y)
    for b in range(n_bins):
        m = idx == b
        nb = int(m.sum())
        if nb == 0:
            continue
        pb = float(p[m].mean())
        yb = float(y[m].mean())
        rel += nb * (pb - yb) ** 2
        res += nb * (yb - ybar) ** 2
        rows.append(dict(bin=b, lo=float(edges[b]), hi=float(edges[b + 1]), n=nb,
                         mean_pred=pb, obs_rate=yb, gap=yb - pb))
    return (dict(brier=brier(y, p), reliability=rel / n, resolution=res / n,
                 uncertainty=float(ybar * (1 - ybar)), base_rate=float(ybar), n=int(n)),
            pd.DataFrame(rows))


def ece(y, p, n_bins=20):
    y = np.asarray(y, float)
    p = np.asarray(p, float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.clip(np.digitize(p, edges[1:-1], right=False), 0, n_bins - 1)
    tot = 0.0
    for b in range(n_bins):
        m = idx == b
        if m.sum() == 0:
            continue
        tot += m.sum() * abs(float(y[m].mean()) - float(p[m].mean()))
    return float(tot / len(y))


# --------------------------------------------------------------------------- inference
def demean_within(v, seas):
    v = np.asarray(v, float)
    out = v.copy()
    for s in np.unique(seas):
        m = seas == s
        out[m] = v[m] - np.nanmean(v[m])
    return out


def tstat(ytil, x, seas, k_extra):
    """FWL slope t of x on an ALREADY season-demeaned y.  x is demeaned within season here.

    TIME-WINDOW NOTE (D085 trap): the ONLY demeaning used anywhere in this screen is
    WITHIN-SEASON, i.e. a season fixed effect.  No entity-season mean, no player mean, no team
    mean is ever subtracted -- those read the entity's own future and that is exactly how the
    sixth retrospective-baseline instance entered through the inference machinery.  A season
    fixed effect is itself retrospective, and is used ONLY as a nuisance absorber that is applied
    IDENTICALLY to the model, to every reference, and to every permutation draw, so it cannot
    manufacture a differential.  This is stated in the TIME-WINDOW TABLE.
    """
    xt = demean_within(x, seas)
    ok = np.isfinite(xt) & np.isfinite(ytil)
    xt = np.where(ok, xt, 0.0)
    yt = np.where(ok, ytil, 0.0)
    sxx = float(xt @ xt)
    if sxx <= 0:
        return np.nan, np.nan, np.nan
    sxy = float(xt @ yt)
    beta = sxy / sxx
    sse = float(yt @ yt) - beta * sxy
    n = int(ok.sum())
    df = n - k_extra - 1
    if df <= 0:
        return np.nan, np.nan, np.nan
    se = np.sqrt(max(sse, 0.0) / df / sxx)
    t = beta / se if se > 0 else np.nan
    sst = float(yt @ yt)
    dr2 = (sst - sse) / sst if sst > 0 else np.nan
    return beta, t, dr2


def make_blocks(frame, keycols):
    df = pd.DataFrame({"i": np.arange(len(frame)), "s": frame["season"].to_numpy()})
    df["k"] = list(map(tuple, frame[keycols].to_numpy()))
    df = df.sort_values(["s", "k"])
    groups = {}
    for (s, k), g in df.groupby(["s", "k"], sort=False):
        groups.setdefault(s, []).append(g["i"].to_numpy())
    return groups


def block_index(groups, n, rng):
    """BETWEEN-block gather index: whole (season,key) blocks of ALREADY-COMPUTED values are
    reassigned to other blocks inside the same season.  Nothing is recomputed inside a draw."""
    idx = np.arange(n)
    for s, blocks in groups.items():
        order = rng.permutation(len(blocks))
        for i, b in enumerate(blocks):
            don = blocks[order[i]]
            idx[b] = don[np.arange(len(b)) % len(don)]
    return idx


def within_block_index(groups, n, rng):
    idx = np.arange(n)
    for s, blocks in groups.items():
        for b in blocks:
            idx[b] = b[rng.permutation(len(b))]
    return idx


def row_index(seas, rng):
    """The NAIVE row-level null.  Reported ONLY to expose the inflation factor."""
    idx = np.arange(len(seas))
    for s in np.unique(seas):
        m = np.where(seas == s)[0]
        idx[m] = m[rng.permutation(len(m))]
    return idx


def var_share_between(v, groups):
    v = np.asarray(v, float)
    tot = np.nanvar(v)
    if not np.isfinite(tot) or tot <= 0:
        return np.nan
    gm = np.nanmean(v)
    num = 0.0
    cnt = 0
    for s, blocks in groups.items():
        for b in blocks:
            x = v[b]
            x = x[np.isfinite(x)]
            if len(x) == 0:
                continue
            num += len(x) * (x.mean() - gm) ** 2
            cnt += len(x)
    return float(num / cnt / tot) if cnt else np.nan


def sha256_text(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()
