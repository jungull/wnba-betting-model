"""E1_I0039 s02 -- ANCHORS FIRST, THEN ROW OVERLAP.  No modelling, no forecast statistic.

Order is deliberate and is the brief's instruction: reproduce prior screens' numbers on bytes
BEFORE generating any new statistic, then compute the exact row-set intersections, and let the
overlap decide how much of the lattice is worth running.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import stk_base as B  # noqa: E402

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 80)

RES = {}

# =====================================================================================
B.hdr("0. LOAD -- read-only, from three prior screens' stored frames")
# =====================================================================================
P_TIER = os.path.join(B.SRC_TIER, "tier_frame.parquet")
P_PLAYER = os.path.join(B.SRC_REDIST, "_player_frame.parquet")
P_REM = os.path.join(B.SRC_REDIST, "_rem_frame.parquet")
P_TG = os.path.join(B.SRC_REDIST, "_tg_frame.parquet")
P_WORK = os.path.join(B.SRC_STACK, "_work.parquet")

for p in (P_TIER, P_PLAYER, P_REM, P_TG, P_WORK):
    print("  sha256 %s  %s" % (B.sha256_file(p)[:16], os.path.relpath(p, B.EXP)))

tier = pd.read_parquet(P_TIER)
player = pd.read_parquet(P_PLAYER)
rem = pd.read_parquet(P_REM)
tg = pd.read_parquet(P_TG)
work = pd.read_parquet(P_WORK)

for nm, d in (("tier", tier), ("player", player), ("rem", rem), ("tg", tg), ("work", work)):
    B.assert_partition(d, nm)

# =====================================================================================
B.hdr("1. ANCHORS -- reproduced on bytes BEFORE any new statistic is generated")
# =====================================================================================
A = {}

# --- A1  D076 / D092: tier-A appeared player-games 2022-2024
A["A1_D076_tierA_player_games"] = B.anchor(
    "A1  D076 tier-A appeared player-games 2022-2024", len(tier), 13879)

# --- A2  D092: the champion's fallback rows on that frame
n_fb_tier = int(tier["pts__is_fallback"].astype(bool).sum())
A["A2_D092_fallback_rows"] = B.anchor(
    "A2  D092 champion fallback rows (pts)", n_fb_tier, 1061)

# --- A3  D092: skill on those fallback rows = -0.1863
fb = tier[tier["pts__is_fallback"].astype(bool)]
y = fb["y_pts"].to_numpy(float)
ch = fb["champ_pts"].to_numpy(float)
rf = fb["ref_pts"].to_numpy(float)
ok = np.isfinite(y) & np.isfinite(ch) & np.isfinite(rf)
skill_mae = 1.0 - np.abs(y[ok] - ch[ok]).sum() / np.abs(y[ok] - rf[ok]).sum()
skill_sse = 1.0 - ((y[ok] - ch[ok]) ** 2).sum() / ((y[ok] - rf[ok]) ** 2).sum()
print("    candidate skills on n=%d : MAE-basis %.6f   SSE-basis %.6f" % (ok.sum(), skill_mae, skill_sse))
A["A3_D092_fallback_skill"] = B.anchor(
    "A3  D092 fallback-row points skill", round(skill_mae, 4), -0.1863, tol=1e-9)

# --- A4  D109 / E1_I0032: the common scored row set and the decision stratum
n_common = int(work["COMMON"].astype(bool).sum())
n_dec = int((work["COMMON"].astype(bool) & work["DECISION"].astype(bool)).sum())
A["A4a_D109_common"] = B.anchor("A4a D109 common scored row set", n_common, 13808)
A["A4b_D109_decision"] = B.anchor("A4b D109 decision stratum", n_dec, 5107)

# --- A5  D102 / D109: the routed population, fallback_level == 2
cm = work["COMMON"].astype(bool).to_numpy()
routed = cm & (pd.to_numeric(work["fbl_pts"], errors="coerce").to_numpy(float) == 2.0)
A["A5a_D102_routed"] = B.anchor("A5a D102 fallback_level==2 routed rows", int(routed.sum()), 947)
A["A5b_D109_routed_in_decision"] = B.anchor(
    "A5b D109 routed rows inside decision stratum",
    int((routed & work["DECISION"].astype(bool).to_numpy()).sum()), 0)
A["A5c_D109_max_nprior_routed"] = B.anchor(
    "A5c D109 max n_prior among routed rows",
    float(np.nanmax(pd.to_numeric(work.loc[routed, "n_prior"], errors="coerce").to_numpy(float))), 5.0)

# --- A6  E1_I0034 / D116: RSP-W2 and the >=25-minute-freed stratum
rem_w2 = rem[rem["season"].isin(B.SCORED_W2)].copy()
A["A6a_I0034_RSPW2_rows"] = B.anchor("A6a E1_I0034 RSP-W2 remaining-player rows", len(rem_w2), 8118)
A["A6b_I0034_RSPW2_blocks"] = B.anchor("A6b E1_I0034 RSP-W2 team-game blocks",
                                       int(rem_w2["tg"].nunique()), 888)
hi = rem_w2[rem_w2["freed_minutes"] >= 25.0]
A["A6c_I0034_freed25_rows"] = B.anchor("A6c D116 >=25min-freed rows", len(hi), 2475)
A["A6d_I0034_freed25_blocks"] = B.anchor("A6d D116 >=25min-freed team-games",
                                         int(hi["tg"].nunique()), 282)

# --- A7  E1_I0034 PREREG s3: the DECLARED SECONDARY window RSP-W1
# NOTE, recorded rather than smoothed: the first draft of this script anchored `_tg_frame` to
# E1_I0033's 1,392 RS1 team-games and it returned 1,284.  That was MY error, not a discrepancy:
# 1,392 is the count of RS1 team-games in master_team, whereas `_tg_frame` carries only the
# team-games that have at least one ESTABLISHED player.  1,284 is E1_I0034's own published
# RSP-W1 block count (PREREG s3), so the frame is right and the anchor was pointed at the wrong
# published number.  Retargeted to the number this artefact actually backs.
rem_w1 = rem[rem["season"].isin((2022, 2023, 2024))]
A["A7a_I0034_RSPW1_rows"] = B.anchor("A7a E1_I0034 RSP-W1 remaining-player rows", len(rem_w1), 11721)
A["A7b_I0034_RSPW1_blocks"] = B.anchor("A7b E1_I0034 RSP-W1 team-game blocks",
                                       int(rem_w1["tg"].nunique()), 1284)

RES["anchors"] = A
print("\n  ALL %d ANCHORS REPRODUCED." % len(A))

# =====================================================================================
B.hdr("2. THE COMMON ROW SET -- one universe, W2, on which every lattice cell is measured")
# =====================================================================================
# D101: two skill numbers are comparable only if identical response, row set, SST basis,
# weighting and base.  Each component's PUBLISHED gain is on ITS OWN row set; those gains
# CANNOT be added.  Everything below is re-measured on ONE row set.
#
# The universe is the champion's scored, APPEARED player-games in 2023-2024 -- the union
# universe, not any component's own target set.  Each component is a transform of the champion
# forecast that is the IDENTITY outside its own treated rows.

PLAYER_KEEP = ("row_uid", "season", "game_id", "team_id", "player_id", "game_date",
               "appeared", "minutes", "pts", "fga",
               "min_hat", "pts_hat", "fga_hat",
               "is_fallback", "fallback_level", "is_cold_start", "n_prior_games",
               "base5_minutes", "base5_pts", "base5_fga",
               "nprior_minutes", "nprior_pts", "nprior_fga")
B.assert_allowlist(player, PLAYER_KEEP, 23, "PLAYER_KEEP")

u = player[list(PLAYER_KEEP)].copy()
u = u[u["season"].isin(B.SCORED_W2)].copy()
B.assert_partition(u, "universe_pre")
print("  scored seasons W2 rows          : %d" % len(u))
# REGULAR SEASON ONLY.  E1_I0034's RS1 -- the row set every D116 number is measured on -- is
# regular season.  The champion frame also carries playoff rows (game_id prefix 1042x).  The
# D087 completeness assertion below is what surfaced this: the inherited team-game reference
# covered 888 of 1,044 W2 team-games, and the 156 missing ones were ALL playoff team-games,
# some with 12 established players and up to 90.5 freed minutes -- i.e. NOT vacuous, and
# silently mixing them in would have extended D116's row set without licence.
u["_gid5"] = u["game_id"].astype(str).str[:4]
print("  game_id prefixes present        : %s" % sorted(pd.unique(u["_gid5"]).tolist()))
u = u[u["game_id"].astype(str).str[:4] == "1022"].copy()
print("  + REGULAR SEASON only           : %d" % len(u))
u = u[u["appeared"].astype(int) == 1].copy()
print("  + appeared == 1                 : %d" % len(u))
for c in ("minutes", "pts", "min_hat", "pts_hat"):
    u = u[np.isfinite(pd.to_numeric(u[c], errors="coerce"))].copy()
print("  + finite y/champ on min & pts   : %d   <-- THE COMMON ROW SET (U)" % len(u))

u["tg"] = u["game_id"].astype(str) + "_" + u["team_id"].astype(str)

# ---- D087 REFERENCE INCOMPLETENESS, caught live and repaired rather than worked around.
# The inherited `_tg_frame` covers only team-games that contain at least one ESTABLISHED player.
# Merging it onto U leaves 14.7% of rows with a MISSING freed_minutes -- a reference silently
# covering part of the row set, which is exactly D087's trap and passes every other guard.
# A COMPLETE reference is rebuilt here from the full champion candidate frame, using E1_I0034's
# own definition (s03d_probe4.py L31): established = nprior_minutes >= 3 AND base5_minutes finite;
# FREED = sum of base5 over established players who did not appear.  A team-game with NO
# established player has FREED = 0 BY CONSTRUCTION (the sum is empty), which is why those rows
# were absent rather than unknown.  The rebuild is then asserted to agree EXACTLY with the
# inherited frame wherever the inherited frame has a value.
MINPRIOR = 3.0
pall = player[player["season"].isin(B.SCORED_W2)].copy()
pall = pall[pall["game_id"].astype(str).str[:4] == "1022"].copy()   # RS1, as E1_I0034 defines it
pall["established"] = ((pd.to_numeric(pall["nprior_minutes"], errors="coerce") >= MINPRIOR)
                       & pall["base5_minutes"].notna()).astype(int)
pall["_absent"] = ((pall["established"] == 1) & (pall["appeared"].astype(int) == 0)).astype(int)
pall["_f_minutes"] = np.where(pall["_absent"] == 1,
                              pd.to_numeric(pall["base5_minutes"], errors="coerce"), 0.0)
pall["tg"] = pall["game_id"].astype(str) + "_" + pall["team_id"].astype(str)
G = (pall.groupby("tg")
     .apply(lambda d: pd.Series({
         "freed_minutes": float(d["_f_minutes"].sum()),
         "n_absent": int(d["_absent"].sum()),
         "n_elig": int((d["established"] == 1).sum()),
         "n_rem": int(((d["established"] == 1) & (d["appeared"].astype(int) == 1)).sum())}),
         include_groups=False)
     .reset_index())
print("  rebuilt COMPLETE team-game reference: %d team-games in W2" % len(G))

tgw = tg[tg["season"].isin(B.SCORED_W2)].copy()
tgw["tg"] = tgw["game_id"].astype(str) + "_" + tgw["team_id"].astype(str)
chk = tgw[["tg", "freed_minutes", "n_absent", "n_elig", "n_rem"]].merge(
    G, on="tg", how="inner", suffixes=("_inh", "_new"))
print("  inherited team-games in W2: %d; overlap with rebuild: %d" % (len(tgw), len(chk)))
for c in ("freed_minutes", "n_absent", "n_elig", "n_rem"):
    d = np.abs(chk[c + "_inh"].to_numpy(float) - chk[c + "_new"].to_numpy(float)).max()
    # 1e-9, not 0: freed_minutes is a float sum and the two builds add in different row orders.
    # Observed max deviation 1.42e-14, i.e. floating-point summation order, not a disagreement.
    print("    max |inherited - rebuilt| %-14s = %.3e" % (c, d))
    assert d < 1e-9, "rebuilt team-game reference disagrees with E1_I0034 on %s" % c
missing = set(G["tg"]) - set(tgw["tg"])
print("  team-games present in rebuild but NOT in the inherited frame: %d" % len(missing))
if missing:
    mm = G[G["tg"].isin(missing)]
    print("    their n_elig: max %d ; their freed_minutes: max %.6f  (must both be 0)"
          % (int(mm["n_elig"].max()), float(mm["freed_minutes"].max())))
    assert int(mm["n_elig"].max()) == 0 and float(mm["freed_minutes"].max()) == 0.0

u = u.merge(G, on="tg", how="left")
cov = float(np.isfinite(u["freed_minutes"].to_numpy(float)).mean())
print("  D087 coverage AFTER repair: freed_minutes present on %.4f of U (%d/%d)"
      % (cov, int(np.isfinite(u['freed_minutes'].to_numpy(float)).sum()), len(u)))
assert cov == 1.0, "D087: team-game reference does not cover the whole common row set"

# the decision-stratum ingredients, taken from the champion's own pre-game fields plus the
# strictly-prior trailing-5 minutes that E1_I0034 built and asserted NaN-on-first-row.
u["n_prior"] = pd.to_numeric(u["n_prior_games"], errors="coerce").astype(float)
u["prior5_minutes"] = pd.to_numeric(u["base5_minutes"], errors="coerce").astype(float)
u["DECISION"] = (u["n_prior"] >= 8) & (u["prior5_minutes"] >= 24)
print("  DECISION stratum (n_prior>=8 & prior5_minutes>=24): %d rows" % int(u["DECISION"].sum()))

# =====================================================================================
B.hdr("3. THE THREE TREATED ROW SETS, on the common row set U")
# =====================================================================================
fl = pd.to_numeric(u["fallback_level"], errors="coerce").to_numpy(float)
isfb = u["is_fallback"].astype(bool).to_numpy()

u["TREAT_A_coldstart"] = (fl == 2.0)                       # D092 retargeted by D102
u["TREAT_B_fallback"] = isfb                               # D094
u["TREAT_C_redistrib"] = (u["freed_minutes"].to_numpy(float) >= 25.0)   # D116

for k, lbl in (("TREAT_A_coldstart", "A  cold-start tiering  (fallback_level == 2)"),
               ("TREAT_B_fallback", "B  fallback routing    (is_fallback)"),
               ("TREAT_C_redistrib", "C  redistribution      (team-game freed >= 25 min)")):
    n = int(u[k].sum())
    nd = int((u[k] & u["DECISION"]).sum())
    print("  %-52s n=%6d  (%.2f%% of U)   in DECISION: %6d" % (lbl, n, 100.0 * n / len(u), nd))

# fallback_level composition, so the A-vs-B relationship is visible rather than asserted
print("\n  fallback_level composition on U:")
print(pd.Series(fl).value_counts(dropna=False).sort_index().to_string())

# =====================================================================================
B.hdr("4. ROW OVERLAP -- the exact intersections.  THIS DECIDES THE REST OF THE SCREEN.")
# =====================================================================================
sets = {"A": u["TREAT_A_coldstart"].to_numpy(),
        "B": u["TREAT_B_fallback"].to_numpy(),
        "C": u["TREAT_C_redistrib"].to_numpy()}
dec = u["DECISION"].to_numpy()

rows = []
names = {"A": "coldstart_tiering_D092_D102", "B": "fallback_routing_D094",
         "C": "minutes_redistribution_D116"}
NU = len(u)
for k, v in sets.items():
    rows.append(dict(set_id=k, definition=names[k], kind="single",
                     n=int(v.sum()), pct_of_universe=100.0 * v.sum() / NU,
                     n_in_decision=int((v & dec).sum()),
                     pct_of_set_in_decision=100.0 * (v & dec).sum() / max(v.sum(), 1)))
import itertools  # noqa: E402
for a, b in itertools.combinations("ABC", 2):
    inter = sets[a] & sets[b]
    union = sets[a] | sets[b]
    rows.append(dict(set_id="%s&%s" % (a, b), definition="%s INTERSECT %s" % (names[a], names[b]),
                     kind="pair_intersection",
                     n=int(inter.sum()), pct_of_universe=100.0 * inter.sum() / NU,
                     n_in_decision=int((inter & dec).sum()),
                     pct_of_set_in_decision=100.0 * (inter & dec).sum() / max(inter.sum(), 1),
                     jaccard=float(inter.sum()) / max(int(union.sum()), 1),
                     pct_of_A_side=100.0 * inter.sum() / max(int(sets[a].sum()), 1),
                     pct_of_B_side=100.0 * inter.sum() / max(int(sets[b].sum()), 1)))
tri = sets["A"] & sets["B"] & sets["C"]
rows.append(dict(set_id="A&B&C", definition="all three", kind="triple_intersection",
                 n=int(tri.sum()), pct_of_universe=100.0 * tri.sum() / NU,
                 n_in_decision=int((tri & dec).sum()),
                 pct_of_set_in_decision=100.0 * (tri & dec).sum() / max(tri.sum(), 1)))
rows.append(dict(set_id="UNIVERSE", definition="common row set U (W2, appeared, finite)",
                 kind="universe", n=NU, pct_of_universe=100.0,
                 n_in_decision=int(dec.sum()), pct_of_set_in_decision=100.0 * dec.sum() / NU))
ov = pd.DataFrame(rows)
ov.to_csv(os.path.join(B.OUT, "ROW_OVERLAP.csv"), index=False)
print(ov.to_string(index=False))

# --- WHY.  The mechanism behind each intersection, printed rather than asserted.
B.hdr("5. WHY THE INTERSECTIONS ARE WHAT THEY ARE")
print("  A is a strict subset of B?  %s   (A minus B = %d rows)"
      % (bool((sets['A'] & ~sets['B']).sum() == 0), int((sets['A'] & ~sets['B']).sum())))
print("  B minus A = %d rows; their fallback_level values:" % int((sets['B'] & ~sets['A']).sum()))
print(pd.Series(fl[sets["B"] & ~sets["A"]]).value_counts().sort_index().to_string())

npr = u["n_prior"].to_numpy(float)
for k in "ABC":
    v = sets[k]
    if v.sum():
        print("  %s: n_prior  min %.0f  median %.0f  max %.0f   |  prior5_minutes median %.2f"
              % (k, np.nanmin(npr[v]), np.nanmedian(npr[v]), np.nanmax(npr[v]),
                 np.nanmedian(u['prior5_minutes'].to_numpy(float)[v])))

print("\n  E1_I0034's REM definition requires >= 3 strictly-prior same-season appearances")
print("  AND a finite trailing-5.  The champion's fallback flag fires BELOW 3 priors.")
print("  Those two conditions are close to complementary BY CONSTRUCTION -- which is the")
print("  mechanism the intersection numbers above are measuring, not a coincidence.")

RES["universe"] = dict(n=NU, seasons=list(B.SCORED_W2), n_teamgames=int(u["tg"].nunique()),
                       n_decision=int(dec.sum()))
RES["overlap"] = ov.to_dict("records")
B.dump(RES, "_s02.json")
u.to_parquet(os.path.join(B.OUT, "_universe.parquet"), index=False)
print("\n  wrote ROW_OVERLAP.csv, _universe.parquet, _s02.json")
