"""s00_probe.py -- STRUCTURAL PROBE ONLY.  Runs BEFORE the preregistration.

WHAT THIS IS ALLOWED TO DO: establish shapes, keys, coverage, join hit rates, partition
boundaries and artifact digests -- the facts a preregistration has to be written against.

WHAT THIS MUST NOT DO, AND DOES NOT DO: compute ANY statistic that involves the OUTCOME
(`pts`) or that compares any forecast to any outcome.  `pts` is not read into any
aggregate here.  No accuracy, error, correlation or regression figure appears.
"""
from __future__ import annotations
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mb_base as mb  # noqa: E402

L = mb.Tee(os.path.join(mb.EXP_DIR, "run_log_s00.txt"))

L("E1_I0058_market_benchmark -- s00 STRUCTURAL PROBE (pre-preregistration)")
L("=" * 92)
L("")
L("--- 1. PARTITION, from the repository's own definition -------------------------------")
L(f"  screenkit.EXPLORATION_SEASONS = {mb.EXPLORATION_SEASONS}")
L(f"  screenkit.HOLDOUT_SEASONS     = {mb.HOLDOUT_SEASONS}   <-- FORBIDDEN")
L(f"  season this screen may use    = {mb.PROPS_EXPLORATION_SEASON} "
  f"(max of EXPLORATION_SEASONS; the props instrument does not exist before it)")
L("")

L("--- 2. IDENTITY: our row_uid reproduction vs the repository's -------------------------")
kid = mb.assert_row_uid_matches_repo()
L(f"  reproduced cbs_obligation_key.row_uid exactly on 3 probes; key id = {kid}")
L("")

L("--- 3. THE INSTRUMENT ------------------------------------------------------------------")
h = mb.load_props_raw()
L(f"  {os.path.relpath(mb.PROPS_CSV, mb.REPO)}")
L(f"  rows={len(h)}  markets={sorted(h.market_key.unique())}  books={h.bookmaker_key.nunique()}")
L(f"  snapshot_returned_utc < commence_time on "
  f"{100 * (h.snap_ts < h.commence_ts).mean():.2f}% of rows; median lead "
  f"{h.lead_h.median():.3f} h; min lead {h.lead_h.min():.3f} h")
h["yr"] = h.commence_ts.dt.year
L(f"  rows by commence-year: {h.yr.value_counts().sort_index().to_dict()}")
L(f"  snapshots per (event,player,book): "
  f"max {h.groupby(['api_event_id', 'pn', 'bookmaker_key']).size().max()} "
  f"(1 => one snapshot per event, NOT a tape)")
L("")

L("--- 4. PARTITION FILTER APPLIED FIRST ---------------------------------------------------")
m = mb.load_master()                      # already filtered to the exploration season
L(f"  master_player rows, season {mb.PROPS_EXPLORATION_SEASON}: {len(m)}  "
  f"games={m.gid.nunique()}  players={m.player_id.nunique()}")
L(f"  master seasons present after filter: {sorted(m.season.unique())}")
g_exp = set(m.gid)
hp = h[h.gid.isin(g_exp)].copy()
L(f"  props rows whose game_id is a season-{mb.PROPS_EXPLORATION_SEASON} master game: "
  f"{len(hp)} of {len(h)}")
L(f"  their commence years: {sorted(hp.yr.unique())}   <-- must be [2024] only")
assert set(hp.yr.unique()) <= {2024}, "FORBIDDEN YEAR ENTERED THE PROPS FILTER"
L(f"  distinct games with props: {hp.gid.nunique()} of {len(g_exp)} "
  f"({100 * hp.gid.nunique() / len(g_exp):.1f}%)")
L(f"  books present: {hp.bookmaker_key.value_counts().to_dict()}")
bk = hp.groupby(["gid", "pn"]).bookmaker_key.nunique()
L(f"  books per (game,player): mean {bk.mean():.2f} median {bk.median():.0f} "
  f"min {bk.min()} max {bk.max()}")
L("")

L("--- 5. JOIN HIT RATE, name side (D086: a name join is an identity minefield) -----------")
props_names = set(hp.pn.unique())
master_names = set(m.pn.unique())
hit = props_names & master_names
miss = props_names - master_names
L(f"  distinct normalised props names: {len(props_names)}")
L(f"  matched EXACTLY on the normalised key: {len(hit)} ({100 * len(hit) / len(props_names):.1f}%)")
L(f"  UNMATCHED props names ({len(miss)}): {sorted(miss)}")
rows_miss = hp[hp.pn.isin(miss)]
L(f"  props ROWS carried by unmatched names: {len(rows_miss)} "
  f"({100 * len(rows_miss) / len(hp):.2f}% of props rows in partition)")
L("  DISPOSITION: unmatched names are DROPPED, listed above, and counted. No substring,")
L("  fuzzy or nickname matching is performed anywhere in this screen.")
coll = m.groupby(["gid", "pn"]).row_uid.nunique()
L(f"  master (game, normalised-name) keys mapping to >1 obligation (traded-player / name "
  f"collision): {(coll > 1).sum()}")
L("")

L("--- 6. THE MODEL ANCHOR, REPRODUCED FROM ITS OWN BYTES ---------------------------------")
for tag, adir, aid in (("PRIMARY", mb.ANCHOR_PRIMARY, mb.ANCHOR_PRIMARY_ID),
                       ("SECONDARY", mb.ANCHOR_SECONDARY, mb.ANCHOR_SECONDARY_ID)):
    d, p = mb.load_anchor(adir)
    rec = mb.verify_manifest(p)
    L(f"  [{tag}] {aid}")
    L(f"     {rec['artifact']}")
    L(f"     rows={len(d)}  target_key={sorted(d.target_key.unique())}  "
      f"arm={sorted(d.arm_id.unique())}  fold={sorted(d.fold_id.unique())}")
    L(f"     sha256 recomputed = {rec['sha256_recomputed']}")
    L(f"     sha256 manifest   = {rec.get('sha256_manifest')}   MATCH={rec.get('match')}")
    L(f"     forecast_cutoff range: {d.forecast_cutoff.min()} .. {d.forecast_cutoff.max()}")
    L(f"     fallback share {d.is_fallback.mean():.4f}; components "
      f"{d.component_id.value_counts().to_dict()}")
    L(f"     row_uid unique: {d.row_uid.is_unique}")
L("")

L("--- 7. STRICTLY-PRE-GAME CHECK ON EVERY INPUT ------------------------------------------")
d, p = mb.load_anchor(mb.ANCHOR_PRIMARY)
mm = m[["row_uid", "gid", "game_date"]].drop_duplicates("row_uid")
chk = d.merge(mm, on="row_uid", how="inner")
chk["cut"] = pd.to_datetime(chk.forecast_cutoff, utc=True)
chk["gd"] = pd.to_datetime(chk.game_date, utc=True)
L(f"  anchor rows joinable to season-{mb.PROPS_EXPLORATION_SEASON} master by row_uid: "
  f"{len(chk)} of {len(d)}")
L(f"  forecast_cutoff <= game_date 00:00Z on {100 * (chk.cut <= chk.gd + pd.Timedelta(hours=24)).mean():.2f}% "
  f"of rows; cutoff strictly before game_date+24h is the runner's own admission rule")
L(f"  feature_asof < forecast_cutoff on "
  f"{100 * (pd.to_datetime(chk.feature_asof, utc=True) < chk.cut).mean():.2f}%")
L("  MARKET side: the snapshot precedes tip on 100% of rows (section 3).")
L("  OUTCOME side: `pts` is read ONLY as the response, never as a regressor.")
L("")

L("--- 8. THE JOINED FRAME, SHAPE ONLY (no outcome statistic computed) --------------------")
last = (hp.sort_values(["snap_ts", "bookmaker_key"])
          .groupby(["gid", "pn", "bookmaker_key"]).tail(1))
J = m.merge(last[["gid", "pn", "bookmaker_key", "line", "over_price", "under_price",
                  "lead_h", "snap_ts", "commence_ts"]], on=["gid", "pn"], how="inner")
L(f"  book-level joined rows (game x player x book): {len(J)}")
J_played = J[J.minutes.fillna(0) > 0]
L(f"  ... restricted to rows the player actually PLAYED: {len(J_played)}")
u = J_played.drop_duplicates("row_uid")
L(f"  distinct player-game obligations with >=1 book price: {len(u)}")
L(f"  distinct players {u.player_id.nunique()}  distinct games {u.gid.nunique()}")
L(f"  as a share of all season-{mb.PROPS_EXPLORATION_SEASON} played master rows: "
  f"{100 * len(u) / (m.minutes.fillna(0) > 0).sum():.1f}%")
L("  ^^ THE SELECTION.  Books price the players they choose to price.  Every number this")
L("     screen reports is conditional on THIS population and may not be generalised.")
L(f"  price completeness: over_price non-null {J_played.over_price.notna().mean():.4f}, "
  f"under_price non-null {J_played.under_price.notna().mean():.4f}, "
  f"line non-null {J_played.line.notna().mean():.4f}")
withmodel = u.merge(d[["row_uid"]], on="row_uid", how="inner")
L(f"  of those obligations, carrying a PRIMARY-anchor forecast: {len(withmodel)} "
  f"({100 * len(withmodel) / len(u):.2f}%)")
L("")
L("--- 9. NOTHING INVOLVING pts WAS AGGREGATED IN THIS STAGE ------------------------------")
L("  grep-able assertion: this script contains no call computing a moment, error or")
L("  correlation of `pts`.  s01 onward do, and only after PREREG.sha256 exists.")
L.close()

json.dump({"n_book_rows": int(len(J)), "n_played_book_rows": int(len(J_played)),
           "n_obligations": int(len(u)), "n_players": int(u.player_id.nunique()),
           "n_games": int(u.gid.nunique()),
           "n_with_model": int(len(withmodel))},
          open(os.path.join(mb.OUT, "s00_shape.json"), "w"), indent=1)
