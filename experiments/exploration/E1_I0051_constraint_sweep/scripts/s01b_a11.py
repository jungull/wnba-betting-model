"""E1_I0051 -- s01b.  A11 diagnostic.  WHICH ROW SET gives E0_I0012's 0.992 / 0.960 / 1.023?

D101: a statistic is meaningless without its row set.  A11 was preregistered without one, which is
this screen's own defect.  This probe enumerates the candidate row sets EXPLICITLY (no name-based
selection, no search over transformations of the statistic) and publishes every one.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cs_base as B  # noqa: E402

pd.set_option("display.width", 200)

MPC = ["game_id", "season", "season_type", "team_id", "player_id", "minutes", "possessions"]
MTC = ["game_id", "season", "season_type", "team_id", "fga", "fta", "oreb", "tov", "dreb"]
mp = pd.read_parquet(B.MP, columns=MPC)
mt = pd.read_parquet(B.MT, columns=MTC)
mp = mp[mp["season"].isin(sorted(B.ALLOWED_SEASONS))].copy()
mt = mt[mt["season"].isin(sorted(B.ALLOWED_SEASONS))].copy()
for c in ("minutes", "possessions"):
    mp[c] = pd.to_numeric(mp[c], errors="coerce").fillna(0.0)
B.assert_partition(mp, "mp")
B.assert_partition(mt, "mt")

B.hdr("A11 -- E0_I0012 published: median 0.992, p05 0.960, p95 1.023")

VARIANTS = [
    ("RS only,  appeared,        poss=FGA-OREB+TOV+0.44FTA", "Regular Season", True, "std"),
    ("RS only,  ALL box rows,    poss=FGA-OREB+TOV+0.44FTA", "Regular Season", False, "std"),
    ("ALL types, appeared,       poss=FGA-OREB+TOV+0.44FTA", None, True, "std"),
    ("ALL types, ALL box rows,   poss=FGA-OREB+TOV+0.44FTA", None, False, "std"),
    ("RS only,  appeared,        poss=FGA-OREB+TOV+0.4FTA ", "Regular Season", True, "p40"),
    ("RS only,  appeared,        poss=FGA+TOV+0.44FTA     ", "Regular Season", True, "nooreb"),
]
assert len(VARIANTS) == 6

rows = []
for label, stype, appeared_only, form in VARIANTS:
    p = mp if stype is None else mp[mp["season_type"] == stype]
    t = mt if stype is None else mt[mt["season_type"] == stype]
    p = p[p["minutes"] > 0] if appeared_only else p
    p = p.copy()
    t = t.copy()
    p["tg"] = p["game_id"].astype(str) + "|" + p["team_id"].astype(str)
    t["tg"] = t["game_id"].astype(str) + "|" + t["team_id"].astype(str)
    fga = t["fga"].astype(float)
    fta = t["fta"].astype(float)
    oreb = t["oreb"].astype(float)
    tov = t["tov"].astype(float)
    if form == "std":
        t["poss"] = fga - oreb + tov + 0.44 * fta
    elif form == "p40":
        t["poss"] = fga - oreb + tov + 0.40 * fta
    else:
        t["poss"] = fga + tov + 0.44 * fta
    pp = p.groupby("tg", sort=False)["possessions"].sum().rename("P")
    j = t.set_index("tg")[["poss"]].join(pp, how="inner")
    r = j["P"] / (5.0 * j["poss"])
    rows.append(dict(variant=label, n_team_games=len(j), median=float(r.median()),
                     p05=float(r.quantile(.05)), p95=float(r.quantile(.95)),
                     match=("MATCH" if (round(float(r.median()), 3) == 0.992
                                        and round(float(r.quantile(.05)), 3) == 0.960
                                        and round(float(r.quantile(.95)), 3) == 1.023) else "")))
out = pd.DataFrame(rows)
print(out.to_string(index=False, float_format=lambda x: "%.6f" % x))
out.to_csv(os.path.join(B.OUT, "A11_ROWSET_DIAGNOSTIC.csv"), index=False)
print("\nwrote A11_ROWSET_DIAGNOSTIC.csv")
