"""S16 -- reduce the UNDETERMINABLE composites by MEASURING, not by guessing.

Target: the 23 composites in E0_I0016 and E0_I0017 that are PRODUCTS or SUMS of a player-level
term and an opponent-level term, declared at `opp_team_season` and permuted there.  The
invariant's question is whether a component varies FINER than the permuting entity, which is a
variance-share measurement on each screen's own frozen frame -- the same move E1_I0040 used to
resolve 44 of its 50 undeterminable cells.

Partition guard: both frames are asserted season <= 2024 before use.
"""
import json, os, re
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPL = os.path.dirname(HERE)

def var_share_between(v, codes):
    v = np.asarray(v, float)
    fin = np.isfinite(v)
    v = v[fin]; codes = np.asarray(codes)[fin]
    if len(v) == 0 or np.var(v) <= 0:
        return np.nan
    gm = v.mean()
    df = pd.DataFrame({"v": v, "g": codes})
    g = df.groupby("g")["v"]
    num = float((g.count() * (g.mean() - gm) ** 2).sum())
    return num / len(v) / float(np.var(v))

rows = []
for scr, frame, entcols in [
        ("E0_I0016_efficiency_predictors", "screen_frame.parquet", ["opp_team_id", "season"]),
        ("E0_I0017_shot_quality_efficiency", None, ["opp_team_id", "season"])]:
    d = os.path.join(EXPL, scr)
    if frame is None:
        cand = [x for x in os.listdir(d) if x.endswith(".parquet")]
        print("%s parquet files: %s" % (scr, cand))
        if not cand:
            print("  no frame on disk -> stays UNDETERMINABLE")
            continue
        frame = cand[0]
    f = pd.read_parquet(os.path.join(d, frame))
    assert f["season"].max() <= 2024, "PARTITION VIOLATION in %s" % scr
    print("\n%s  %s  shape=%s" % (scr, frame, f.shape))
    have = [c for c in entcols if c in f.columns]
    if len(have) < len(entcols):
        print("  entity columns missing (%s); frame has: %s" % (entcols, list(f.columns)[:40]))
        continue
    codes = f[entcols].astype(str).agg("_".join, axis=1).to_numpy()
    pcodes = (f["season"].astype(str) + "_" + f["player_id"].astype(str)).to_numpy() \
        if "player_id" in f.columns else None
    # explicit allowlist of the composite columns and their named components (from s08's parse)
    C = pd.read_csv(os.path.join(HERE, "COMPOSITE_SWEEP.csv"))
    sub = C[(C["screen"] == scr) & (C["composite_verdict"] == "UNDETERMINABLE")
            & C["candidate_class"].astype(str).str.startswith("COMPOSITE")]
    print("  undeterminable composites in this screen: %d" % len(sub))
    for _, r in sub.iterrows():
        cand = r["candidate"]
        comps = re.findall(r'\[\s*[\'"]([A-Za-z0-9_]+)[\'"]\s*\]',
                           str(r["construction_expr"]))
        rec = dict(screen=scr, candidate=cand, construction_expr=r["construction_expr"],
                   components=json.dumps(comps))
        if cand in f.columns:
            rec["assembled_share_between_opp_team_season"] = var_share_between(
                f[cand].to_numpy(float), codes)
            if pcodes is not None:
                rec["assembled_share_between_player_season"] = var_share_between(
                    f[cand].to_numpy(float), pcodes)
        else:
            rec["assembled_share_between_opp_team_season"] = np.nan
        cl = {}
        for c in comps:
            if c in f.columns:
                cl[c] = dict(
                    between_opp_team_season=var_share_between(f[c].to_numpy(float), codes),
                    between_player_season=(var_share_between(f[c].to_numpy(float), pcodes)
                                           if pcodes is not None else np.nan))
        rec["component_shares"] = json.dumps(cl, default=float)
        rec["n_components_measured"] = len(cl)
        rec["n_components_named"] = len(comps)
        rows.append(rec)
        print("   %-24s assembled vsb(opp_team_season)=%s  components measured %d/%d"
              % (cand, ("%.4f" % rec["assembled_share_between_opp_team_season"]
                        if np.isfinite(rec.get("assembled_share_between_opp_team_season", np.nan))
                        else "NA"), len(cl), len(comps)))
        for c, v in cl.items():
            print("        %-28s between_opp_team_season=%.4f  between_player_season=%.4f"
                  % (c, v["between_opp_team_season"], v["between_player_season"]))

M = pd.DataFrame(rows)
M.to_csv(os.path.join(HERE, "MEASURED_COMPONENT_SHARES.csv"), index=False)
print("\nwrote MEASURED_COMPONENT_SHARES.csv", M.shape)
print("DONE s16")
