# -*- coding: utf-8 -*-
"""M44 s01 -- does a TEAM-level margin model beat the spread, and does the OPENING line help?

E0-style diagnostic, NON-CLAIMING. S42 closed.

THE GAP THIS FILLS. M14 scored model-vs-market on PLAYER props and falsified it: the slope is
negative (-0.098), meaning that where our model disagrees with the market, the MARKET is more
often right. M32 scored market-vs-market consensus and found -8.99%. But nothing in the
programme has ever scored a TEAM-LEVEL MARGIN FORECAST against the point spread, which is the
single most obvious model-versus-market bet there is. It was asserted to lose, never measured.

TWO THINGS ARE TESTED AT ONCE, BOTH DECLARED HERE.

H1 -- does a walk-forward team margin model beat the spread? Team ratings are built from
prior games only, within season, seeded from the prior season, with a home advantage
estimated from strictly earlier seasons. Nothing at or after the game is read.

H2 -- DOES THE OPENING LINE HELP? Every M43 test used the LAST pre-tip quote, which is the
CLOSING line -- the most efficient price a market ever shows. Openers are systematically
softer. So each strategy is scored twice: at the first quote we ever saw for that game, and
at the last one before tip. If our model has any content, it should show up at the open
before it shows up at the close, and a strategy that beats the open but not the close is a
real and well-known phenomenon rather than an anomaly.

WHAT WOULD MAKE THIS A FIND. A positive ROI whose interval excludes zero, at the OPEN, that
does not evaporate when the threshold moves. Given M14's negative slope the prior expectation
is that this loses, and saying so in advance is what stops a marginal positive being read as
a discovery.

THE MODEL IS DELIBERATELY SIMPLE and is NOT the promoted structural channel. If a
straightforward team rating shows nothing, that is weak evidence about the sophisticated one,
not proof -- and the file says so rather than generalising.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
M43 = os.path.abspath(os.path.join(HERE, "..", "M43_SIDE_BIAS"))
sys.path.insert(0, M43)

import s01_flat_side_bias as s43  # noqa: E402
import s04_extended_history as s44  # noqa: E402

MTEAM = os.path.join(s43.ROOT, "data", "masters", "master_team.parquet")
ALPHA = 0.25                 # EWMA weight on the most recent game
MIN_PRIOR = 5                # games before a rating is usable
THRESHOLDS = (1.0, 2.0, 3.0, 5.0)      # declared, not searched


def ratings():
    """Walk-forward offence/defence per team, prior games only."""
    mt = pd.read_parquet(MTEAM, columns=["game_id", "game_date", "team_abbreviation",
                                         "opp_team_abbreviation", "is_home", "pts", "season"])
    mt["game_id"] = mt["game_id"].astype(str)
    mt["gd"] = pd.to_datetime(mt["game_date"])
    opp = mt[["game_id", "team_abbreviation", "pts"]].rename(
        columns={"team_abbreviation": "opp_team_abbreviation", "pts": "opp_pts"})
    mt = mt.merge(opp, on=["game_id", "opp_team_abbreviation"], how="left")
    mt = mt.sort_values("gd")

    # shift(1) so a game never sees itself; ewm over strictly prior games
    g = mt.groupby("team_abbreviation", group_keys=False)
    mt["off"] = g["pts"].apply(lambda s: s.shift(1).ewm(alpha=ALPHA).mean())
    mt["deff"] = g["opp_pts"].apply(lambda s: s.shift(1).ewm(alpha=ALPHA).mean())
    mt["n_prior"] = g.cumcount()
    return mt


def build():
    mt = ratings()
    home = mt[mt["is_home"] == 1][["game_id", "gd", "season", "team_abbreviation",
                                   "off", "deff", "n_prior", "pts"]]
    home = home.rename(columns={"team_abbreviation": "h", "off": "h_off",
                                "deff": "h_def", "n_prior": "h_n", "pts": "hp"})
    away = mt[mt["is_home"] == 0][["game_id", "team_abbreviation", "off", "deff",
                                   "n_prior", "pts"]]
    away = away.rename(columns={"team_abbreviation": "a", "off": "a_off",
                                "deff": "a_def", "n_prior": "a_n", "pts": "ap"})
    g = home.merge(away, on="game_id", how="inner").dropna(
        subset=["h_off", "h_def", "a_off", "a_def"])
    g = g[(g["h_n"] >= MIN_PRIOR) & (g["a_n"] >= MIN_PRIOR)]

    # home advantage from STRICTLY EARLIER seasons only
    g = g.sort_values("gd")
    hfa = {}
    for s in sorted(g["season"].unique()):
        prior = g[g["season"] < s]
        hfa[s] = float((prior["hp"] - prior["ap"]).mean()) if len(prior) > 50 else np.nan
    g["hfa"] = g["season"].map(hfa)
    g = g.dropna(subset=["hfa"])

    # expected margin for the HOME side
    g["pred_margin"] = ((g["h_off"] + g["a_def"]) / 2.0
                        - (g["a_off"] + g["h_def"]) / 2.0 + g["hfa"])
    g["actual_margin"] = g["hp"] - g["ap"]
    return g


def market(which):
    """Spread quotes: `which` is 'open' (first seen) or 'close' (last pre-tip)."""
    d = s44.load_hist()          # already pre-tip, last per (event, book, team)
    raw = []
    # load_hist collapses to the last quote; for the open we need the first, so redo lightly
    import json as _json
    with open(s44.HIST, encoding="utf-8") as fh:
        for line in fh:
            try:
                rec = _json.loads(line)
            except Exception:                       # noqa: BLE001
                continue
            payload = rec.get("payload")
            if not isinstance(payload, list):
                continue
            snap = rec.get("vendor_snapshot_ts") or rec.get("requested_ts")
            for ev in payload:
                tip = ev.get("commence_time")
                if not tip:
                    continue
                for bk in ev.get("bookmakers", []):
                    for mk in bk.get("markets", []):
                        if mk.get("key") != "spreads":
                            continue
                        for oc in mk.get("outcomes", []):
                            raw.append({"event_id": ev.get("id"), "tip": tip, "snap": snap,
                                        "home_team": ev.get("home_team"),
                                        "away_team": ev.get("away_team"),
                                        "book": bk.get("key"), "team": oc.get("name"),
                                        "point": oc.get("point"), "price": oc.get("price")})
    d = pd.DataFrame(raw)
    d["tip"] = pd.to_datetime(d["tip"], utc=True, errors="coerce")
    d["snap"] = pd.to_datetime(d["snap"], utc=True, errors="coerce")
    d = d.dropna(subset=["tip", "snap", "point", "price"])
    d = d[d["snap"] < d["tip"]]
    d["abv"] = d["team"].map(s43.NAME2ABV)
    d["h"] = d["home_team"].map(s43.NAME2ABV)
    d["a"] = d["away_team"].map(s43.NAME2ABV)
    d = d.dropna(subset=["abv", "h", "a"])
    d = d.sort_values("snap")
    keep = "first" if which == "open" else "last"
    d = d.groupby(["event_id", "book", "abv"], as_index=False).agg(
        tip=("tip", "first"), h=("h", "first"), a=("a", "first"),
        point=("point", keep), price=("price", keep), snap=("snap", keep))
    return d


def main():
    res = {}
    print("=" * 94)
    print("M44 s01 -- team margin model vs the spread, at the OPEN and at the CLOSE")
    print("=" * 94)

    g = build()
    print("\nmodelled games (walk-forward, >=%d prior each side): %d" % (MIN_PRIOR, len(g)))
    mae = float((g["pred_margin"] - g["actual_margin"]).abs().mean())
    print("model margin MAE vs outcome: %.2f points" % mae)
    res["n_modelled"], res["model_mae"] = int(len(g)), round(mae, 3)

    rng = np.random.default_rng(s43.SEED)
    for which in ("open", "close"):
        m = market(which)
        # attach outcomes + model
        j = m.merge(g[["game_id", "h", "a", "gd", "pred_margin", "actual_margin"]],
                    on=["h", "a"], how="inner")
        j = j[(j["gd"] - j["tip"].dt.tz_localize(None)).abs() < pd.Timedelta(days=2)]
        if j.empty:
            print("\n%s: no joined rows" % which)
            continue
        # the HOME side's handicap; model edge = our margin minus the market's
        home_side = j[j["abv"] == j["h"]].copy()
        home_side["mkt_margin"] = -home_side["point"]      # -(-5.5) = home favoured by 5.5
        home_side["edge"] = home_side["pred_margin"] - home_side["mkt_margin"]
        home_side["ats"] = home_side["actual_margin"] + home_side["point"]
        # bet HOME when the model likes home, AWAY when it likes away
        rows = []
        for _, r in home_side.iterrows():
            if r["edge"] >= 0:
                rows.append({**r, "side": "home", "won": r["ats"] > 0, "push": r["ats"] == 0,
                             "absedge": abs(r["edge"])})
            else:
                rows.append({**r, "side": "away", "won": r["ats"] < 0, "push": r["ats"] == 0,
                             "absedge": abs(r["edge"])})
        b = pd.DataFrame(rows)
        b["profit"] = s43.american_profit(b["price"].to_numpy(float),
                                          b["won"].to_numpy(), b["push"].to_numpy())
        print("\n%s LINE -- %d quotes over %d games"
              % (which.upper(), len(b), b["game_id"].nunique()))
        out = {}
        for th in THRESHOLDS:
            sub = b[b["absedge"] >= th]
            r = s43.clustered_ci(sub, rng) if len(sub) > 30 else None
            if r is None:
                continue
            flag = "  <-- CLEARS ZERO" if r["lo"] > 0 else ""
            print("   model disagrees by >=%4.1f pts: %4d games  hit %5.1f%%  ROI %+6.2f%%"
                  "  [%+.2f%%, %+.2f%%]%s"
                  % (th, r["n_games"], 100 * r["hit"], 100 * r["roi"],
                     100 * r["lo"], 100 * r["hi"], flag))
            out[th] = r
        res[which] = out

    print("\n" + "=" * 94)
    print("Prior expectation, stated before the run: M14 found the model-market residual")
    print("slope NEGATIVE on players, so this was expected to lose. A marginal positive")
    print("here would need the same scrutiny M43 got -- and the same multiple-comparison")
    print("arithmetic, since %d thresholds x 2 line timings is 8 more tests." % len(THRESHOLDS))
    print("=" * 94)

    with open(os.path.join(HERE, "FINDINGS_s01.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, default=float)
    print("\nwrote FINDINGS_s01.json")


if __name__ == "__main__":
    main()
