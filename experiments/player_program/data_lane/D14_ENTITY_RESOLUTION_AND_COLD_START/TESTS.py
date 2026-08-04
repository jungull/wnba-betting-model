"""D14 — entity resolution and cold start: executable boundary tests.

Epistemic status: DESIGN ARTIFACT + TESTS. Defines behaviour at the boundaries. Establishes
no effect.

What this file is
-----------------
Every assertion below pins a *measured* property of artifacts that already exist in this
repository. Nothing here fits, scores, tunes or compares any arm. No outcome is compared to any
forecast. The tests exist so that a future change to the identity layer, the candidate universe
or the cold-start ladder cannot pass silently.

Two classes of test are present and are labelled distinctly in the output:

  ``INVARIANT``  — a property the contract requires. A failure is a defect.
  ``PINNED_GAP`` — a property that DIVERGES from ``PREDICTION_CONTRACT_V5_SPEC.md`` or is an
                   undeclared hazard. The test asserts the CURRENT behaviour so the divergence
                   is visible in CI rather than rediscovered. A failure means the behaviour
                   changed and the report must be revisited.

Run:  python TESTS.py     (exit 0 = all pass, 1 = any failure)
pytest is NOT installed in this environment; this is a standalone runner by repo convention.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PROGRAM = HERE.parents[1]                      # experiments/player_program

EXPOSURE = PROGRAM / "projected_exposure_v1" / "projected_player_possessions_v1.parquet"
ROTATION = PROGRAM / "projected_exposure_v1" / "projected_team_rotations_v1.parquet"
PACE = PROGRAM / "projected_exposure_v1" / "team_possession_prior_v1.parquet"
EVENTS = PROGRAM / "event_contract_v1" / "canonical_player_events_v1.parquet"
TOV_TARGETS = PROGRAM / "turnover_targets_v1" / "player_turnover_targets_v1.parquet"
TOV_RECON = PROGRAM / "turnover_targets_v1" / "team_turnover_reconciliation_v1.parquet"
POSS_SEASON = PROGRAM / "possessions_v2" / "player_season_possessions_v2.parquet"
POSS_RAW = PROGRAM / "possessions_v2" / "possessions_raw_v2.parquet"
EXPOSURE_VALIDATION = PROGRAM / "projected_exposure_v1" / "PROJECTED_EXPOSURE_VALIDATION.json"

RESULTS: list[dict] = []


# --------------------------------------------------------------------------- #
# harness
# --------------------------------------------------------------------------- #
def check(test_id: str, kind: str, criterion: str, description: str,
          ok: bool, measured) -> None:
    RESULTS.append({
        "test_id": test_id,
        "kind": kind,
        "acceptance_criterion": criterion,
        "description": description,
        "passed": bool(ok),
        "measured": measured,
    })


def _obligations() -> pd.DataFrame:
    """One row per obligation. The exposure artifact repeats every obligation once per
    evidence regime; ``row_uid`` is the obligation key."""
    return pd.read_parquet(EXPOSURE).drop_duplicates("row_uid").reset_index(drop=True)


def _realised_appearances(dates: pd.Series) -> pd.DataFrame:
    """POSTGAME AUDIT ONLY. Realised (player, team, game) appearances with a running count of
    strictly-earlier same-season appearances.

    PREDICTION_CONTRACT_V5_SPEC.md section 6 permits the box score to audit the pregame universe
    and forbids it from constructing the universe. Nothing derived here is written into any
    forecast path; it is used only to compare the contract's declared counters against reality.
    """
    tt = pd.read_parquet(TOV_TARGETS, columns=["player_id", "team_id", "game_id", "minutes"])
    app = tt[tt["minutes"] > 0][["player_id", "team_id", "game_id"]].drop_duplicates()
    app["game_date"] = app["game_id"].map(dates)
    app = app.dropna(subset=["game_date"]).sort_values("game_date")
    app["season"] = app["game_date"].dt.year
    app["prior_any_team"] = app.groupby(["player_id", "season"]).cumcount()
    app["prior_this_team"] = app.groupby(["player_id", "team_id", "season"]).cumcount()
    return app


# --------------------------------------------------------------------------- #
# A. identity resolution — aliases resolve to one identity, with evidence
# --------------------------------------------------------------------------- #
def test_identity(d: pd.DataFrame) -> None:
    crit = "transferred-player aliases resolve to one identity with evidence"

    # A1 — the identity key is a positive integer id, not a name, on every registered artifact.
    frames = {
        "projected_player_possessions_v1": d,
        "player_turnover_targets_v1": pd.read_parquet(TOV_TARGETS, columns=["player_id"]),
        "player_season_possessions_v2": pd.read_parquet(POSS_SEASON, columns=["player_id"]),
    }
    key_ok, detail = True, {}
    for name, f in frames.items():
        col = f["player_id"]
        good = str(col.dtype).lower().startswith("int") and bool((col > 0).all())
        detail[name] = {"dtype": str(col.dtype), "min": int(col.min()), "all_positive": bool((col > 0).all())}
        key_ok &= good
    # no free-text player-name column exists anywhere in the registered player artifacts
    name_cols = sorted({c for f in (pd.read_parquet(p).head(0) for p in
                                    (EXPOSURE, TOV_TARGETS, POSS_SEASON))
                        for c in f.columns if "name" in c.lower()})
    detail["free_text_name_columns_found"] = name_cols
    check("A1", "INVARIANT", crit,
          "player identity is a positive integer player_id on every registered player artifact, "
          "and no free-text name column exists to be aliased",
          key_ok and not name_cols, detail)

    # A2 — no orphan identity: every player who realised possessions or turnovers is in the
    # candidate universe under the same id. An alias split would show up here as an id present
    # in a realised artifact and absent from the universe.
    E = set(d["player_id"].unique())
    T = set(pd.read_parquet(TOV_TARGETS, columns=["player_id"])["player_id"].unique())
    P = set(pd.read_parquet(POSS_SEASON, columns=["player_id"])["player_id"].unique())
    check("A2", "INVARIANT", crit,
          "every realised player id resolves into the candidate universe (no orphan identity)",
          not (T - E) and not (P - E),
          {"universe_players": len(E), "turnover_target_players": len(T),
           "possession_players": len(P), "orphan_from_turnovers": sorted(T - E),
           "orphan_from_possessions": sorted(P - E)})

    # A3 — player1_id in the canonical event contract is POLYMORPHIC. It holds a person id, a
    # team id, an official-shaped id or a non-roster person id depending on event family. A join
    # on player1_id alone silently attributes non-player events to a player.
    ev = pd.read_parquet(EVENTS, columns=["player1_id", "player3_id", "event_family",
                                          "event_team_id"])
    teams = set(ev["event_team_id"].dropna().astype("int64").unique())
    s1 = ev["player1_id"].dropna().astype("int64")
    s1 = s1[s1 > 0]
    ids1 = set(s1.unique())
    unresolved = ids1 - E
    team_actors = unresolved & teams
    residual = np.array(sorted(unresolved - teams))
    official_shaped = residual[residual < 100_000]
    person_shaped = residual[residual >= 100_000]
    n_team_rows = int(s1.isin(list(teams)).sum())
    n_official_rows = int(s1.isin(official_shaped.tolist()).sum())
    n_person_rows = int(s1.isin(person_shaped.tolist()).sum())
    fam_team = ev[ev["player1_id"].isin(list(teams))]["event_family"].value_counts().to_dict()
    check("A3", "PINNED_GAP", crit,
          "player1_id in canonical_player_events/1 is a polymorphic actor id spanning four "
          "entity classes; the exact partition is pinned so a silent change is detectable",
          (len(team_actors) == 15 and n_team_rows == 38_726
           and len(official_shaped) == 629 and n_official_rows == 3_117
           and len(person_shaped) == 39 and n_person_rows == 187),
          {"nonnull_player1_values": int(len(s1)), "distinct_player1_ids": len(ids1),
           "resolve_to_universe_player": len(ids1 & E),
           "team_actor_ids": len(team_actors), "team_actor_rows": n_team_rows,
           "team_actor_families": {k: int(v) for k, v in fam_team.items()},
           "official_shaped_ids": int(len(official_shaped)),
           "official_shaped_rows": n_official_rows,
           "non_roster_person_ids": int(len(person_shaped)),
           "non_roster_person_rows": n_person_rows,
           "unresolved_row_share_pct": round(100 * (n_team_rows + n_official_rows + n_person_rows)
                                             / len(s1), 4)})

    # A4 — the one entity class that IS resolved explicitly: team-actor turnovers are carried as
    # team_unattributed rather than charged to a player. This is the pattern the other classes
    # need.
    recon = pd.read_parquet(TOV_RECON)
    team_tov_events = int(((ev["event_family"] == "turnover")
                           & ev["player1_id"].isin(list(teams))).sum())
    check("A4", "INVARIANT", crit,
          "team-actor turnovers are reconciled as team_unattributed, never attributed to a player",
          team_tov_events == int(recon["team_unattributed"].sum()),
          {"team_actor_turnover_events": team_tov_events,
           "team_unattributed_in_reconciliation": int(recon["team_unattributed"].sum()),
           "player_attributed": int(recon["player_attributed"].sum()),
           "team_total": int(recon["team_turnovers_total"].sum())})

    # A5 — the obligation key is one row per (player, game, team); identity never fractures
    # inside a team-game.
    dup = int(d.duplicated(["player_id", "game_id", "team_id"]).sum())
    check("A5", "INVARIANT", crit,
          "row_uid is unique and one obligation exists per (player_id, game_id, team_id)",
          dup == 0 and d["row_uid"].is_unique,
          {"obligations": int(len(d)), "duplicate_player_game_team": dup})


# --------------------------------------------------------------------------- #
# B. team-history transitions
# --------------------------------------------------------------------------- #
def test_transitions(d: pd.DataFrame) -> None:
    crit = "team-history transitions are handled explicitly"

    # B1 — a transferred player keeps ONE id. Measured on realised play, where the transition is
    # a fact rather than a candidacy artefact.
    ps = pd.read_parquet(POSS_SEASON, columns=["player_id", "season", "teams"])
    multi = ps[ps["teams"] > 1]
    raw = pd.read_parquet(POSS_RAW, columns=["season", "offense_team_id", "defense_team_id",
                                             "off_p1", "off_p2", "off_p3", "off_p4", "off_p5",
                                             "def_p1", "def_p2", "def_p3", "def_p4", "def_p5"])
    off = raw.melt(id_vars=["season", "offense_team_id"],
                   value_vars=["off_p1", "off_p2", "off_p3", "off_p4", "off_p5"],
                   value_name="player_id")[["season", "offense_team_id", "player_id"]] \
        .rename(columns={"offense_team_id": "team_id"})
    dfn = raw.melt(id_vars=["season", "defense_team_id"],
                   value_vars=["def_p1", "def_p2", "def_p3", "def_p4", "def_p5"],
                   value_name="player_id")[["season", "defense_team_id", "player_id"]] \
        .rename(columns={"defense_team_id": "team_id"})
    al = pd.concat([off, dfn], ignore_index=True).dropna()
    al["player_id"] = al["player_id"].astype("int64")
    al = al[al["player_id"] > 0]
    recomputed = al.groupby(["player_id", "season"])["team_id"].nunique()
    check("B1", "INVARIANT", crit,
          "the registered per-player-season team count is reproducible from the raw possession "
          "lineups, so a mid-season transfer is one player_id carrying two team_ids",
          int((recomputed > 1).sum()) == int(len(multi)),
          {"player_seasons": int(len(ps)),
           "multi_team_player_seasons_registered": int(len(multi)),
           "multi_team_player_seasons_recomputed": int((recomputed > 1).sum()),
           "distribution_registered": {int(k): int(v) for k, v in
                                       ps["teams"].value_counts().sort_index().items()}})

    # B2 — dual obligation. Spec section 8: at the cutoff the contract cannot know a player has
    # gone, so both clubs owe an obligation. Both must exist, distinctly keyed.
    dc = d[d["candidate_claimed_by_multiple_teams"]]
    per_pg = dc.groupby(["player_id", "game_id"])["team_id"].nunique()
    check("B2", "INVARIANT", crit,
          "a player claimed by more than one club for one game yields exactly two distinct "
          "obligations, both present",
          bool((per_pg == 2).all()) and len(dc) == 2 * len(per_pg),
          {"dual_claim_rows": int(len(dc)),
           "distinct_player_games": int(len(per_pg)),
           "teams_per_claimed_player_game": {int(k): int(v) for k, v in
                                             per_pg.value_counts().items()},
           "players": int(dc["player_id"].nunique()),
           "games": int(dc["game_id"].nunique()),
           "by_tier": {str(k): int(v) for k, v in dc["universe_tier"].value_counts().items()},
           "by_team_assignment_source": {str(k): int(v) for k, v in
                                         dc["team_assignment_source"].value_counts().items()}})

    # B3 — the flag is not decorative: it is exactly the >1-team condition.
    n_teams = d.groupby(["player_id", "game_id"])["team_id"].transform("nunique")
    check("B3", "INVARIANT", crit,
          "candidate_claimed_by_multiple_teams equals the >1-club condition on every row",
          bool((d["candidate_claimed_by_multiple_teams"] == (n_teams > 1)).all()),
          {"mismatched_rows": int((d["candidate_claimed_by_multiple_teams"] != (n_teams > 1)).sum())})

    # B4 — candidate inflation from the weak sources is a transition-handling property and must
    # be reported per tier, never as one blended figure.
    per_tier = {}
    for tier, sub in [("A", d[d["universe_tier"] == "A"]), ("B", d[d["universe_tier"] == "B"])]:
        pt = sub.groupby(["player_id", "season"])["team_id"].nunique()
        per_tier[tier] = {"player_seasons": int(len(pt)),
                          "gt_one_team": int((pt > 1).sum()),
                          "max_teams_in_one_season": int(pt.max())}
    check("B4", "INVARIANT", crit,
          "multi-club candidacy is separable by tier; Tier A stays near the realised transfer "
          "rate while the weak tiers inflate it, so a blended figure would misdescribe transitions",
          per_tier["A"]["max_teams_in_one_season"] <= 3 and per_tier["B"]["max_teams_in_one_season"] >= 5,
          per_tier)

    # B5 — PINNED GAP. Spec section 3 defines is_cold_start as "no prior appearance for THIS TEAM
    # this season". The bytes implement a player-season definition. A player's debut for a new
    # club therefore carries is_cold_start = False while her history belongs to another club.
    dates = d[["game_id", "game_date"]].drop_duplicates().set_index("game_id")["game_date"]
    app = _realised_appearances(dates)
    j = d.merge(app[["player_id", "team_id", "game_id", "prior_any_team", "prior_this_team"]],
                on=["player_id", "team_id", "game_id"], how="inner")
    debut = j[(j["prior_any_team"] > 0) & (j["prior_this_team"] == 0)]
    check("B5", "PINNED_GAP", crit,
          "team-transition debut rows (prior appearance elsewhere, none for this club) are NOT "
          "flagged cold start; the implemented definition is player-season, the spec's wording "
          "is player-team-season",
          len(debut) == 75 and int((~debut["is_cold_start"]).sum()) == 75,
          {"team_transition_debut_obligations": int(len(debut)),
           "of_which_is_cold_start_false": int((~debut["is_cold_start"]).sum()),
           "distinct_players": int(debut["player_id"].nunique()),
           "by_season": {int(k): int(v) for k, v in
                         debut["season"].value_counts().sort_index().items()},
           "by_tier": {str(k): int(v) for k, v in debut["universe_tier"].value_counts().items()},
           "audited_obligations": int(len(j))})


# --------------------------------------------------------------------------- #
# C. cold start is a declared fallback, never a silent default
# --------------------------------------------------------------------------- #
def test_cold_start(d: pd.DataFrame) -> None:
    crit = "cold-start behaviour is a declared fallback, never a silent default"
    crit2 = "new signings and players with no historical rows have declared, tested behaviour"

    # C1 — the flag has exactly one definition and it is not conditioned on fold or target.
    check("C1", "INVARIANT", crit2,
          "is_cold_start is exactly (n_prior_appearances == 0), with no exceptions",
          bool((d["is_cold_start"] == (d["n_prior_appearances"] == 0)).all()),
          {"obligations": int(len(d)),
           "is_cold_start_true": int(d["is_cold_start"].sum()),
           "n_prior_appearances_zero": int((d["n_prior_appearances"] == 0).sum()),
           "disagreements": int((d["is_cold_start"] != (d["n_prior_appearances"] == 0)).sum())})

    # C2 — no zero-history player is ever served by the fitted path in silence. The conditional
    # target must declare a fallback level on every cold-start row.
    viol = d[d["is_cold_start"] & (d["e_min_fallback_level"] == 0)]
    check("C2", "INVARIANT", crit,
          "every zero-history obligation carries a declared conditional-minutes fallback level "
          "(> 0); none is served silently by the fitted estimator",
          len(viol) == 0,
          {"cold_start_rows": int(d["is_cold_start"].sum()),
           "cold_start_with_level_0": int(len(viol)),
           "e_min_level_on_cold_start": {int(k): int(v) for k, v in
                                         d[d["is_cold_start"]]["e_min_fallback_level"]
                                         .value_counts().sort_index().items()}})

    # C3 — flag and level agree on both targets, in both directions.
    bad_pa = int(((d["p_active_is_fallback"]) != (d["p_active_fallback_level"] > 0)).sum())
    bad_em = int(((d["e_min_is_fallback"]) != (d["e_min_fallback_level"] > 0)).sum())
    bad_any = int((d["pred_is_fallback"] !=
                   (d["p_active_is_fallback"] | d["e_min_is_fallback"])).sum())
    check("C3", "INVARIANT", crit,
          "is_fallback and fallback_level agree in both directions on both targets, and "
          "pred_is_fallback is their disjunction",
          bad_pa == 0 and bad_em == 0 and bad_any == 0,
          {"p_active_disagreements": bad_pa, "e_min_disagreements": bad_em,
           "pred_is_fallback_disagreements": bad_any})

    # C4 — the declaration fields exist and are never null. A null is a silent default.
    decl = ["universe_tier", "evaluation_tier", "candidate_source", "team_assignment_source",
            "team_assignment_confidence", "roster_evidence_regime", "cutoff_source",
            "cutoff_policy", "is_cold_start", "contract_version", "n_prior_appearances",
            "n_prior_team_games", "p_active_is_fallback", "p_active_fallback_level",
            "e_min_is_fallback", "e_min_fallback_level", "candidate_claimed_by_multiple_teams"]
    nulls = {c: int(d[c].isna().sum()) for c in decl}
    check("C4", "INVARIANT", crit,
          "every entity-resolution and cold-start declaration field is present and non-null on "
          "every obligation",
          all(v == 0 for v in nulls.values()),
          {"fields_checked": len(decl), "null_counts": nulls})

    # C5 — the ladder has two ORTHOGONAL cold-start axes and conflating them is the failure mode.
    # Level 4 is a FOLD degeneracy (the first season has no earlier season to fit on), not a
    # player-history property: it fires on every 2021 obligation regardless of the player.
    l4 = d[d["p_active_fallback_level"] == 4]
    check("C5", "INVARIANT", crit,
          "fallback level 4 is a fold-level degeneracy (season 2021, no prior season to fit on), "
          "not a player-history property: it fires on every 2021 obligation and on no other",
          set(l4["season"].unique()) == {2021}
          and len(l4) == int((d["season"] == 2021).sum())
          and int(((d["p_active_fallback_level"] == 4)
                   != (d["e_min_fallback_level"] == 4)).sum()) == 0,
          {"level4_rows": int(len(l4)), "level4_seasons": sorted(int(s) for s in l4["season"].unique()),
           "all_2021_obligations": int((d["season"] == 2021).sum()),
           "level4_is_cold_start_false": int((~l4["is_cold_start"]).sum()),
           "median_n_prior_appearances_on_level4": float(l4["n_prior_appearances"].median()),
           "target_disagreements": int(((d["p_active_fallback_level"] == 4)
                                        != (d["e_min_fallback_level"] == 4)).sum())})

    # C6 — the two targets key their cold start on DIFFERENT questions and must not be collapsed.
    # p_active keys on prior candidate obligations (a rostered non-appearance is informative);
    # the conditional targets key on prior appearances.
    nz = d[d["season"] != 2021]
    pa_fitted_cold = nz[(nz["p_active_fallback_level"] == 0) & nz["is_cold_start"]]
    em_fitted_cold = nz[(nz["e_min_fallback_level"] == 0) & nz["is_cold_start"]]
    check("C6", "INVARIANT", crit2,
          "availability and conditional minutes ask different history questions: a candidate "
          "with prior obligations but no appearance keeps a fitted p_active and must fall back "
          "for conditional minutes",
          len(em_fitted_cold) == 0 and len(pa_fitted_cold) > 0,
          {"ex_2021_obligations": int(len(nz)),
           "cold_start_with_fitted_p_active": int(len(pa_fitted_cold)),
           "median_n_prior_team_games_there": float(pa_fitted_cold["n_prior_team_games"].median()),
           "cold_start_with_fitted_e_minutes": int(len(em_fitted_cold))})

    # C7 — the conditional-minutes ladder is a ONE-WAY bound on the fields this artifact carries.
    # Level 3 implies at most one prior appearance, but the converse fails: 1,697 rows with
    # exactly one prior appearance sit at level 2. The ladder's exact rule lives in cbs_v15,
    # outside this node's read scope, and is NOT reconstructible from the emitted fields. The
    # test asserts only what the bytes support.
    lvl3 = nz[nz["e_min_fallback_level"] == 3]
    le1 = nz[nz["n_prior_appearances"] <= 1]
    check("C7", "INVARIANT", crit2,
          "outside the degenerate 2021 fold, conditional-minutes level 3 implies at most one "
          "prior appearance; the converse does not hold and the ladder rule is not derivable "
          "from the emitted fields",
          bool((lvl3["n_prior_appearances"] <= 1).all()),
          {"level3_rows_ex_2021": int(len(lvl3)),
           "rows_with_n_prior_appearances_le_1": int(len(le1)),
           "n_prior_appearances_max_on_level3": int(lvl3["n_prior_appearances"].max()),
           "n_prior_appearances_eq_1_by_level":
               {int(k): int(v) for k, v in
                nz[nz["n_prior_appearances"] == 1]["e_min_fallback_level"]
                .value_counts().sort_index().items()},
           "converse_holds": False,
           "ladder_rule_source_readable_in_scope": False})

    # C8 — coverage, not silence. A zero-history obligation still receives a finite projection,
    # and where a downstream quantity cannot be formed it is null WITH a declared reason rather
    # than imputed. This is the team-level cold start: a club with no prior games has no pace
    # estimate, so minutes are projected and possessions are withheld.
    cs = d[d["is_cold_start"]]
    nullposs = d[d["projected_off_possessions"].isna()]
    check("C8", "INVARIANT", crit2,
          "a zero-history obligation receives a finite non-negative minutes projection; where "
          "possessions cannot be formed they are null with a declared status and pace_source, "
          "never imputed",
          bool(cs["projected_minutes"].notna().all())
          and bool(np.isfinite(cs["projected_minutes"]).all())
          and bool((cs["projected_minutes"] >= 0).all())
          and set(nullposs["team_game_status"].unique()) == {"minutes_only_no_pace"}
          and set(nullposs["pace_source"].unique()) == {"unresolved_no_prior_games"}
          and int(nullposs["projected_minutes"].isna().sum()) == 0,
          {"cold_start_rows": int(len(cs)),
           "null_projected_minutes_on_cold_start": int(cs["projected_minutes"].isna().sum()),
           "negative_projected_minutes_on_cold_start": int((cs["projected_minutes"] < 0).sum()),
           "max_projected_minutes_on_cold_start": round(float(cs["projected_minutes"].max()), 6),
           "rows_with_null_projected_off_possessions": int(len(nullposs)),
           "their_team_game_status": sorted(nullposs["team_game_status"].unique()),
           "their_pace_source": sorted(nullposs["pace_source"].unique()),
           "of_which_also_null_minutes": int(nullposs["projected_minutes"].isna().sum())})

    # C9 — PINNED GAP. n_prior_appearances counts ADMITTED prior obligations that appeared, not
    # prior appearances. A player whose earlier game was a candidate-universe miss can be flagged
    # cold start while having played. Bounded here, and it is small but non-zero.
    dates = d[["game_id", "game_date"]].drop_duplicates().set_index("game_id")["game_date"]
    app = _realised_appearances(dates)
    j = d.merge(app[["player_id", "team_id", "game_id", "prior_any_team"]],
                on=["player_id", "team_id", "game_id"], how="inner")
    undercount = j[j["n_prior_appearances"] != j["prior_any_team"]]
    false_cold = j[j["is_cold_start"] & (j["prior_any_team"] > 0)]
    check("C9", "PINNED_GAP", crit2,
          "n_prior_appearances counts admitted prior appearances, so it under-counts true prior "
          "appearances wherever an earlier game was a candidate-universe miss; the resulting "
          "false-cold-start rate is bounded here",
          len(undercount) == 474
          and set((undercount["n_prior_appearances"] - undercount["prior_any_team"]).unique()) == {-1}
          and len(false_cold) == 2,
          {"audited_obligations": int(len(j)),
           "counter_mismatches": int(len(undercount)),
           "mismatch_direction_contract_minus_realised":
               {int(k): int(v) for k, v in
                (undercount["n_prior_appearances"] - undercount["prior_any_team"])
                .value_counts().items()},
           "false_cold_start_rows": int(len(false_cold)),
           "false_cold_start_rate_pct": round(100 * len(false_cold) / len(j), 5)})


# --------------------------------------------------------------------------- #
# D. tier and evidence declarations for new signings / zero-history candidates
# --------------------------------------------------------------------------- #
def test_tier_and_evidence(d: pd.DataFrame) -> None:
    crit = "new signings and players with no historical rows have declared, tested behaviour"

    # D1 — a Tier A row is assigned by a Tier A source and nothing else; a Tier B source never
    # produces a Tier A assignment; the reserved S4 never appears.
    A = d[d["universe_tier"] == "A"]
    B = d[d["universe_tier"] == "B"]
    src_all = set()
    for v in d["candidate_source"].unique():
        src_all |= set(str(v).split("|"))
    check("D1", "INVARIANT", crit,
          "tier integrity: Tier A is assigned only by S1/S3, Tier B only by S_TX/S2, and the "
          "reserved S4 appears nowhere",
          set(A["team_assignment_source"].unique()) <= {"S1", "S3"}
          and set(B["team_assignment_source"].unique()) <= {"S_TX", "S2"}
          and "S4" not in src_all,
          {"tier_A_rows": int(len(A)), "tier_B_rows": int(len(B)),
           "A_assignment_sources": sorted(A["team_assignment_source"].unique()),
           "B_assignment_sources": sorted(B["team_assignment_source"].unique()),
           "all_candidate_source_tokens": sorted(src_all)})

    # D2 — confidence, regime and assignment source are one bijection, so an operator cannot read
    # "verified" off a retrospective source.
    xt = d.groupby("team_assignment_source")[["team_assignment_confidence",
                                              "roster_evidence_regime"]].nunique()
    mapping = (d[["team_assignment_source", "team_assignment_confidence",
                  "roster_evidence_regime"]].drop_duplicates()
               .sort_values("team_assignment_source"))
    check("D2", "INVARIANT", crit,
          "team_assignment_source determines team_assignment_confidence and "
          "roster_evidence_regime exactly one-to-one",
          bool((xt == 1).all().all()),
          {"mapping": mapping.to_dict("records")})

    # D3 — era rule. S3, the only source that can create an obligation for a player with no
    # prior box row, may not admit before 2026-07-30.
    s3 = d[d["candidate_source"].str.contains("S3", na=False)]
    earliest = s3["game_date"].min()
    check("D3", "INVARIANT", crit,
          "the captured-report source S3 never admits a candidate before 2026-07-30",
          len(s3) == 0 or earliest >= pd.Timestamp("2026-07-30"),
          {"s3_rows": int(len(s3)),
           "earliest_s3_game_date": None if len(s3) == 0 else str(earliest.date()),
           "s3_players": int(s3["player_id"].nunique())})

    # D4 — the structural full-team cold start. Every club's season opener has zero Tier A
    # candidates, and that is surfaced as an unresolved rotation rather than an invented one.
    rot = pd.read_parquet(ROTATION)
    pace = pd.read_parquet(PACE)
    tg_all = set(map(tuple, pace[["game_id", "team_id"]].drop_duplicates().values))
    tg_A = set(map(tuple, d[d["universe_tier"] == "A"][["game_id", "team_id"]]
                   .drop_duplicates().values))
    no_A = tg_all - tg_A
    ra = rot[rot["regime"] == "tier_a_only"]
    unresolved_A = ra[ra["status"] == "unresolved_insufficient_candidates"]
    per_season = (pace.merge(pd.DataFrame(sorted(no_A), columns=["game_id", "team_id"]),
                             on=["game_id", "team_id"])["season"]
                  .value_counts().sort_index())
    check("D4", "INVARIANT", crit,
          "season openers carry zero Tier A candidates and are declared unresolved rather than "
          "given a manufactured rotation",
          len(no_A) == len(unresolved_A)
          and bool((unresolved_A["n_candidates"] == 0).all())
          and bool((unresolved_A["n_allocated"] == 0).all()),
          {"team_games_in_universe": len(tg_all),
           "team_games_with_no_tier_A_candidate": len(no_A),
           "unresolved_tier_A_rotations": int(len(unresolved_A)),
           "by_season": {int(k): int(v) for k, v in per_season.items()},
           "note": "one per club per season; league size 12/12/12/12/13/15"})

    # D5 — the weak tiers rescue the opener but two 2021 openers stay unresolved, because 2021
    # has no prior season for S2 to reach into. This is the hard boundary of the cold start.
    rw = rot[rot["regime"] == "tier_a_plus_tx_b_plus_s2"]
    still = rw[rw["status"] == "unresolved_insufficient_candidates"]
    check("D5", "INVARIANT", crit,
          "adding the weak evidence tiers resolves all but two team-games, both 2021 openers, "
          "where no prior season exists for S2 to reach into",
          len(still) == 2 and set(still["season"].unique()) == {2021}
          and bool((still["n_allocated"] == 0).all()),
          {"unresolved_under_widest_regime": int(len(still)),
           "seasons": sorted(int(s) for s in still["season"].unique()),
           "dates": sorted(str(x.date()) for x in still["game_date"]),
           "n_candidates": [int(x) for x in still["n_candidates"]],
           "n_allocated": [int(x) for x in still["n_allocated"]]})

    # D6 — obligations stranded by an unresolved team-game are counted, not lost.
    val = json.loads(EXPOSURE_VALIDATION.read_text(encoding="utf-8"))
    txt = json.dumps(val)
    declared_contract = 44_851
    widest = int(d[d["universe_tier"].notna()].shape[0])
    check("D6", "INVARIANT", crit,
          "obligations stranded in an unresolved team-game are declared, not dropped silently",
          widest == 44_843 and '"stranded": 8' in txt.replace(" ", "").replace('"stranded":8', '"stranded": 8'),
          {"contract_obligations_declared": declared_contract,
           "obligations_present_in_exposure_artifact": widest,
           "stranded": declared_contract - widest,
           "stranded_declared_in_validation_receipt": "stranded" in txt})


# --------------------------------------------------------------------------- #
def main() -> int:
    d = _obligations()
    test_identity(d)
    test_transitions(d)
    test_cold_start(d)
    test_tier_and_evidence(d)

    n = len(RESULTS)
    failed = [r for r in RESULTS if not r["passed"]]
    out = {
        "schema": "d14_entity_resolution_and_cold_start_tests/1",
        "epistemic_status": ("DESIGN ARTIFACT + TESTS. Defines behaviour at the boundaries. "
                             "Establishes no effect."),
        "generated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "scope": ("structural and identity assertions over existing artifacts only. Nothing is "
                  "fitted, tuned, scored or compared to any outcome. No arm performance is read."),
        "postgame_use_declaration": ("realised box membership is used ONLY to audit the pregame "
                                     "universe's own counters, per PREDICTION_CONTRACT_V5_SPEC "
                                     "section 6. No candidate is created from it."),
        "n_tests": n,
        "n_passed": n - len(failed),
        "n_failed": len(failed),
        "failed_test_ids": [r["test_id"] for r in failed],
        "tests": RESULTS,
    }
    (HERE / "TEST_RESULTS.json").write_text(json.dumps(out, indent=2), encoding="utf-8")

    for r in RESULTS:
        print(f"[{'PASS' if r['passed'] else 'FAIL'}] {r['test_id']:4s} {r['kind']:11s} "
              f"{r['description'][:88]}")
    print(f"\n{n - len(failed)}/{n} passed -> {HERE / 'TEST_RESULTS.json'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
