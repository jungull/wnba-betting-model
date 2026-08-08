"""S03 -- PROBE.  EXPLORATORY, DECLARED, PRE-PREREGISTRATION.

Everything in this file is DESCRIPTIVE and is used to CHOOSE the preregistered cells.  It is run
BEFORE PREREG.md is written and hashed, and PREREG.md says exactly which of these quantities were
looked at first.  Nothing here carries a verdict and nothing here is a hypothesis test.

WHAT IT ANSWERS
  1  is the team minute budget actually fixed?  (D104 says yes; verify on these rows)
  2  what is a defensible PRE-GAME ROTATION set, and how big is it?
  3  how many absence team-games are there, and how many freed minutes / attempts / points?
  4  THE ARITHMETIC CEILING, per channel, computed BEFORE anything is fitted
  5  what does the raw redistribution look like -- concentrated or diffuse?
"""
import json, os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import redist_base as rb

pd.set_option("display.width", 250); pd.set_option("display.max_columns", 60)


def main():
    rb.hdr("S03 PROBE (EXPLORATORY, DECLARED)")
    P = {}
    tg = pd.read_parquet(os.path.join(rb.OUT, "_team_frame.parquet"))
    pf = pd.read_parquet(os.path.join(rb.OUT, "_player_frame.parquet"))
    rs1 = tg[tg["RS1"]][["game_id", "team_id", "season", "game_date", "pts", "fga", "minutes"]]
    p = pf.merge(rs1[["game_id", "team_id"]], on=["game_id", "team_id"], how="inner")
    print("  RS1 team-games %d, champion rows on RS1 %d" % (len(rs1), len(p)))

    # ------------------------------------------------------------------ 1. the minute budget
    rb.hdr("1. IS THE TEAM MINUTE BUDGET FIXED?")
    s = p.groupby(["game_id", "team_id"])["minutes"].sum().rename("sum_player_min").reset_index()
    s = s.merge(rs1, on=["game_id", "team_id"])
    print("  sum of player minutes per team-game: mean %.4f  sd %.4f  min %.1f  max %.1f"
          % (s["sum_player_min"].mean(), s["sum_player_min"].std(),
             s["sum_player_min"].min(), s["sum_player_min"].max()))
    print("  value counts of round(sum):")
    print(s["sum_player_min"].round(0).value_counts().sort_index().head(12).to_string())
    print("  master_team.minutes: mean %.4f sd %.4f" % (s["minutes"].mean(), s["minutes"].std()))
    P["minute_budget"] = {"mean": float(s["sum_player_min"].mean()),
                          "sd": float(s["sum_player_min"].std()),
                          "frac_exactly_200": float((s["sum_player_min"].round(2) == 200.0).mean())}
    print("  fraction exactly 200.00: %.4f" % P["minute_budget"]["frac_exactly_200"])

    # ------------------------------------------------------------------ 2. rotation set
    rb.hdr("2. CANDIDATE PRE-GAME ROTATION DEFINITIONS")
    p = p.copy()
    p["exp_minutes"] = p["p_active_hat"] * p["min_hat"]
    p["rank_exp_min"] = (p.groupby(["game_id", "team_id"])["exp_minutes"]
                         .rank(ascending=False, method="first"))
    realised_roster = p.groupby(["game_id", "team_id"])["appeared"].sum()
    print("  realised roster size: mean %.4f  sd %.4f  min %d  max %d"
          % (realised_roster.mean(), realised_roster.std(),
             realised_roster.min(), realised_roster.max()))
    print("  champion rows per team-game: mean %.4f" % p.groupby(["game_id", "team_id"]).size().mean())
    rows = []
    for k in [8, 9, 10, 11, 12]:
        sub = p[p["rank_exp_min"] <= k]
        rows.append(dict(k=k, n_rows=len(sub),
                         appearance_rate=float(sub["appeared"].mean()),
                         mean_minutes_when_present=float(
                             sub.loc[sub["appeared"] == 1, "minutes"].mean()),
                         share_of_team_minutes=float(
                             sub.groupby(["game_id", "team_id"])["minutes"].sum().mean() / 200.0),
                         n_absent_rows=int((sub["appeared"] == 0).sum()),
                         teamgames_with_absence=int(
                             (sub.assign(o=(sub["appeared"] == 0).astype(int))
                              .groupby(["game_id", "team_id"])["o"].sum() >= 1).sum())))
    rot = pd.DataFrame(rows)
    print(rot.to_string(index=False))
    P["rotation_definitions"] = rot.to_dict("records")

    # ------------------------------------------------------------------ 3. absence volumes
    rb.hdr("3. ABSENCE VOLUMES AT ROTATION k=10")
    K = 10
    r = p[p["rank_exp_min"] <= K].copy()
    print("  baseline coverage among rotation rows:")
    for ch in rb.CHANNELS:
        print("    base5_%-8s notna %.4f   nprior>=3 %.4f"
              % (ch, r["base5_" + ch].notna().mean(), (r["nprior_" + ch] >= 3).mean()))
    P["baseline_coverage"] = {ch: {"notna": float(r["base5_" + ch].notna().mean()),
                                   "nprior_ge3": float((r["nprior_" + ch] >= 3).mean())}
                              for ch in rb.CHANNELS}
    r["is_absent"] = (r["appeared"] == 0).astype(int)
    agg = {"n_absent": ("is_absent", "sum")}
    for ch in rb.CHANNELS:
        r["_freed_" + ch] = np.where(r["is_absent"] == 1, r["base5_" + ch].fillna(0.0), 0.0)
        r["_freed_ok_" + ch] = np.where(r["is_absent"] == 1,
                                        r["base5_" + ch].notna().astype(int), 1)
        agg["freed_" + ch] = ("_freed_" + ch, "sum")
        agg["freedok_" + ch] = ("_freed_ok_" + ch, "min")
    agg["n_rot"] = ("is_absent", "size")
    agg["n_remaining"] = ("appeared", "sum")
    G = r.groupby(["game_id", "team_id"]).agg(**agg).reset_index()
    G = G.merge(rs1[["game_id", "team_id", "season"]], on=["game_id", "team_id"])
    print("\n  team-games by n_absent among the pre-game top-%d:" % K)
    print(G["n_absent"].value_counts().sort_index().to_string())
    hit = G["n_absent"] >= 1
    print("\n  ABSENCE team-games: %d of %d (%.3f)" % (hit.sum(), len(G), hit.mean()))
    for ch in rb.CHANNELS:
        print("    mean freed %-8s in absence games: %.4f   (all games %.4f)"
              % (ch, G.loc[hit, "freed_" + ch].mean(), G["freed_" + ch].mean()))
    print("  all absentees have a usable baseline in %.4f of absence games"
          % G.loc[hit, ["freedok_" + c for c in rb.CHANNELS]].min(axis=1).mean())
    P["absence_volumes"] = {
        "K": K, "n_teamgames": int(len(G)), "n_absence_teamgames": int(hit.sum()),
        "counts": {str(k): int(v) for k, v in G["n_absent"].value_counts().sort_index().items()},
        "mean_freed": {ch: float(G.loc[hit, "freed_" + ch].mean()) for ch in rb.CHANNELS},
        "mean_n_remaining_in_absence": float(G.loc[hit, "n_remaining"].mean())}
    print("  mean remaining (appeared) players in absence games: %.4f"
          % G.loc[hit, "n_remaining"].mean())

    # ------------------------------------------------------------------ 4. ARITHMETIC CEILING
    rb.hdr("4. THE ARITHMETIC CEILING -- COMPUTED BEFORE ANYTHING IS FITTED")
    rem = r[(r["appeared"] == 1)].merge(
        G[["game_id", "team_id", "n_absent", "n_remaining"]
          + ["freed_" + c for c in rb.CHANNELS]],
        on=["game_id", "team_id"], how="left")
    rem = rem[rem["base5_minutes"].notna()]
    ceil_rows = []
    for ch in rb.CHANNELS:
        sub = rem[rem["base5_" + ch].notna()].copy()
        sub["_d"] = sub[ch] - sub["base5_" + ch]
        a = sub[sub["n_absent"] >= 1]
        b = sub[sub["n_absent"] == 0]
        unif = (a["freed_" + ch] / a["n_remaining"]).to_numpy()
        base_mae = float(np.mean(np.abs(a["_d"])))
        # the LARGEST MAE reduction a perfect uniform redistribution term could give is bounded
        # above by its own mean absolute size
        ceil_rows.append(dict(
            channel=ch, n_remaining_rows_absence=int(len(a)), n_remaining_rows_noabsence=int(len(b)),
            sd_delta=float(a["_d"].std()),
            mean_delta_absence=float(a["_d"].mean()),
            mean_delta_noabsence=float(b["_d"].mean()),
            raw_contrast=float(a["_d"].mean() - b["_d"].mean()),
            mean_uniform_share=float(unif.mean()),
            mae_of_base5_on_absence_rows=base_mae,
            ceiling_frac_of_base_mae=float(unif.mean() / base_mae)))
    ce = pd.DataFrame(ceil_rows)
    print(ce.to_string(index=False))
    P["arithmetic_ceiling"] = ce.to_dict("records")

    # ------------------------------------------------------------------ 5. concentration
    rb.hdr("5. RAW SHAPE OF THE REDISTRIBUTION -- CONCENTRATED OR DIFFUSE?")
    a = rem[(rem["n_absent"] >= 1) & rem["base5_minutes"].notna()].copy()
    a["_d"] = a["minutes"] - a["base5_minutes"]
    a["_share"] = a["_d"] / a["freed_minutes"].replace(0.0, np.nan)
    a["_rank_share"] = a.groupby(["game_id", "team_id"])["_share"].rank(ascending=False,
                                                                       method="first")
    tabl = a.groupby("_rank_share").agg(n=("_share", "size"), mean_share=("_share", "mean"),
                                        mean_delta=("_d", "mean")).reset_index()
    print("  per-team-game, remaining players sorted by realised share of the freed minutes:")
    print(tabl.head(12).to_string(index=False))
    P["concentration_raw"] = tabl.head(12).to_dict("records")
    # top-1 / top-3 share of the POSITIVE part
    gg = a.groupby(["game_id", "team_id"])
    top1 = gg.apply(lambda d: d.nlargest(1, "_d")["_d"].sum() / max(d["freed_minutes"].iloc[0], 1e-9),
                    include_groups=False)
    top3 = gg.apply(lambda d: d.nlargest(3, "_d")["_d"].sum() / max(d["freed_minutes"].iloc[0], 1e-9),
                    include_groups=False)
    print("\n  mean top-1 beneficiary share of freed minutes: %.4f" % top1.mean())
    print("  mean top-3 beneficiary share of freed minutes: %.4f" % top3.mean())
    print("  uniform expectation for top-3 of ~%.1f remaining: %.4f"
          % (a.groupby(['game_id', 'team_id']).size().mean(),
             3.0 / a.groupby(['game_id', 'team_id']).size().mean()))
    P["concentration_top"] = {"top1_mean": float(top1.mean()), "top3_mean": float(top3.mean()),
                              "mean_n_remaining": float(a.groupby(['game_id', 'team_id']).size().mean())}

    # ------------------------------------------------------------------ 6. positions available
    rb.hdr("6. POSITION AND DEPTH SIGNALS AVAILABLE")
    print("  position_raw values:")
    print(pf["position_raw"].value_counts(dropna=False).to_string())
    print("\n  master_player.position values:")
    print(pf["position"].value_counts(dropna=False).head(12).to_string())
    P["position_raw_values"] = {str(k): int(v) for k, v in
                                pf["position_raw"].value_counts(dropna=False).items()}

    with open(os.path.join(rb.OUT, "_s03_probe.json"), "w", encoding="utf-8") as fh:
        json.dump(rb.jsonable(P), fh, indent=1)
    print("\n  wrote _s03_probe.json")


if __name__ == "__main__":
    main()
