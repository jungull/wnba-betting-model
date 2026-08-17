"""S03 -- distributional shape of the candidate, and whether it predicts Type-I inflation.

Usage: python s03_shape.py <ARM>

Every feature is measured on the arm's own rows from the arm's own season-z-scored,
season-demeaned candidate column -- the exact column the null permutes.  No feature is
derived from a name.  D101: features are descriptions of one column on one row set; they
are never compared across arms.
"""
import json, os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *          # noqa

ARM = sys.argv[1]
mask = ARM_MASKS[ARM]
ctx = arm_context(mask)
m = ctx["m"]
GP = blocks_on(mask, "player_id")
BLIST = [b for s, bl in GP.items() for b in bl]
NB = len(BLIST)
blockid = np.zeros(m, np.int64)
for i, b in enumerate(BLIST):
    blockid[b] = i
bcount = np.array([len(b) for b in BLIST], float)

s00 = json.load(open(os.path.join(HERE, "scripts", "_s00.json")))
CELLS = s00["cells54"]
CANDS = sorted({c.split("|")[0] for c in CELLS})


def spearman(a, b):
    a = np.asarray(a, float); b = np.asarray(b, float)
    ok = np.isfinite(a) & np.isfinite(b)
    a, b = a[ok], b[ok]
    if len(a) < 4:
        return np.nan
    ra = pd.Series(a).rank().to_numpy(); rb = pd.Series(b).rank().to_numpy()
    ra = ra - ra.mean(); rb = rb - rb.mean()
    d = np.sqrt((ra ** 2).sum() * (rb ** 2).sum())
    return float((ra * rb).sum() / d) if d > 0 else np.nan


def shape_of(v):
    """v: the arm-local season-demeaned candidate column."""
    bm = np.bincount(blockid, weights=v, minlength=NB) / bcount
    dev = v - bm[blockid]
    tot = float(v.var())
    out = dict(
        var_share_between_block=float(bm.var(ddof=0) * 0 + np.average((bm - v.mean()) ** 2,
                                                                     weights=bcount) / tot)
        if tot > 0 else np.nan,
        sd_dev=float(dev.std()),
    )
    d = dev[np.isfinite(dev)]
    sd = d.std()
    if sd > 0:
        zz = (d - d.mean()) / sd
        out["dev_excess_kurtosis"] = float((zz ** 4).mean() - 3.0)
        out["dev_abs_skew"] = float(abs((zz ** 3).mean()))
        out["dev_max_abs_z"] = float(np.abs(zz).max())
        out["dev_frac_abs_z_gt4"] = float((np.abs(zz) > 4).mean())
        out["dev_p999_over_p50_abs"] = float(np.percentile(np.abs(zz), 99.9) /
                                             max(np.percentile(np.abs(zz), 50), 1e-12))
    else:
        for k in ("dev_excess_kurtosis", "dev_abs_skew", "dev_max_abs_z",
                  "dev_frac_abs_z_gt4", "dev_p999_over_p50_abs"):
            out[k] = np.nan
    zv = (v - v.mean()) / (v.std() if v.std() > 0 else 1.0)
    out["excess_kurtosis_whole"] = float(((zv) ** 4).mean() - 3.0)
    out["max_within_block_spread_z"] = float(max(
        (zv[b].max() - zv[b].min()) for b in BLIST))
    out["n_distinct_over_n"] = float(len(np.unique(v)) / m)

    # POSITION structure: how much of the within-block deviation is a function of
    # within-block ordinal position, and how much of THAT profile is shared across blocks.
    cors, ac1 = [], []
    prof_len = int(np.median(bcount))
    prof_acc, prof_cnt = np.zeros(prof_len), np.zeros(prof_len)
    for b in BLIST:
        if len(b) < 5:
            continue
        dv = dev[b]
        pos = np.arange(len(b), dtype=float)
        if dv.std() > 0:
            cors.append(float(np.corrcoef(dv, pos)[0, 1]))
            ac1.append(float(np.corrcoef(dv[:-1], dv[1:])[0, 1]) if dv[:-1].std() > 0 and
                       dv[1:].std() > 0 else np.nan)
            rel = np.clip((pos / max(len(b) - 1, 1) * (prof_len - 1)).round().astype(int),
                          0, prof_len - 1)
            np.add.at(prof_acc, rel, dv / dv.std())
            np.add.at(prof_cnt, rel, 1.0)
    cors = np.array(cors, float)
    out["pos_corr_mean"] = float(np.nanmean(cors))               # SIGNED, shared direction
    out["pos_corr_mean_abs"] = float(np.nanmean(np.abs(cors)))
    out["pos_monotone_share"] = float(np.nanmean(np.abs(cors) > 0.9))
    out["dev_lag1_autocorr"] = float(np.nanmean(np.array(ac1, float)))
    prof = np.where(prof_cnt > 0, prof_acc / np.maximum(prof_cnt, 1), np.nan)
    out["shared_position_profile_sd"] = float(np.nanstd(prof))
    return out


rows = []
for cand in CANDS:
    j = names.index(cand)
    v = ctx["Xzt"][:, j]
    r = dict(arm=ARM, candidate=cand, n=m, n_blocks=NB,
             level_matched_scheme="BETWEEN" if use_between[j] else "WITHIN")
    r.update(shape_of(v))
    r["sxx_after_base"] = float(v @ v)
    rows.append(r)

# response-side: how much shared within-block positional profile the RESPONSE has.
# This is what makes E1_I0044's BLOCKBOOT generator non-null for a position-monotone
# candidate, so it is measured, not asserted.
resp = []
for k, _ in DEPS:
    yt = ctx["Yt"][k]
    s = shape_of(yt)
    resp.append(dict(arm=ARM, dependent=k, resp_pos_corr_mean=s["pos_corr_mean"],
                     resp_pos_corr_mean_abs=s["pos_corr_mean_abs"],
                     resp_shared_position_profile_sd=s["shared_position_profile_sd"],
                     resp_dev_lag1_autocorr=s["dev_lag1_autocorr"],
                     resp_dev_excess_kurtosis=s["dev_excess_kurtosis"],
                     resp_var_share_between_block=s["var_share_between_block"]))

S = pd.DataFrame(rows)
Rr = pd.DataFrame(resp)
S.to_csv(os.path.join(HERE, "_SHAPE_CAND_%s.csv" % ARM), index=False)
Rr.to_csv(os.path.join(HERE, "_SHAPE_RESP_%s.csv" % ARM), index=False)
print("=== CANDIDATE SHAPE, %s ===" % ARM)
print(S[["candidate", "var_share_between_block", "dev_excess_kurtosis", "dev_max_abs_z",
         "max_within_block_spread_z", "pos_corr_mean", "pos_monotone_share",
         "dev_lag1_autocorr", "n_distinct_over_n"]].to_string(index=False))
print("\n=== RESPONSE SHAPE, %s ===" % ARM)
print(Rr.to_string(index=False))

# ---- join to Type-I and correlate ------------------------------------------------
tp = os.path.join(HERE, "_TYPEI_RAW_%s.csv" % ARM)
if os.path.exists(tp):
    T = pd.read_csv(tp)
    T = T[T.get("not_estimable", pd.Series([""] * len(T))).fillna("") == ""]
    M = (T.pivot_table(index=["cell", "candidate", "dependent"], columns="generator",
                       values="typeI_COMPOSED2").reset_index()
         .merge(S, on="candidate", how="left")
         .merge(Rr, left_on="dependent", right_on="dependent", how="left"))
    M.to_csv(os.path.join(HERE, "_SHAPE_JOINED_%s.csv" % ARM), index=False)
    feats = ["var_share_between_block", "dev_excess_kurtosis", "dev_abs_skew",
             "dev_max_abs_z", "dev_frac_abs_z_gt4", "dev_p999_over_p50_abs",
             "excess_kurtosis_whole", "max_within_block_spread_z", "n_distinct_over_n",
             "pos_corr_mean_abs", "pos_monotone_share", "dev_lag1_autocorr",
             "shared_position_profile_sd", "resp_shared_position_profile_sd",
             "resp_pos_corr_mean"]
    print("\n=== SPEARMAN(shape feature, COMPOSED2 Type-I), %s, %d cells ===" % (ARM, len(M)))
    out = []
    for g in ("EXCH", "CIRCSHIFT", "BLOCKBOOT"):
        if g not in M.columns:
            continue
        for ft in feats:
            out.append(dict(arm=ARM, generator=g, feature=ft,
                            spearman=spearman(M[ft], M[g]), n_cells=int(M[g].notna().sum())))
    O = pd.DataFrame(out)
    O.to_csv(os.path.join(HERE, "_SHAPE_CORR_%s.csv" % ARM), index=False)
    print(O.pivot_table(index="feature", columns="generator", values="spearman")
          .round(3).to_string())
print("DONE s03 %s" % ARM)
