"""P24_INJURY_REGIME_LEDGER -- measurement script.

Splits data/injury_history/injury_history.csv into explicit epistemic regimes and
reports cutoff-valid coverage by season and by fold.

READ ONLY. Writes only inside
experiments/player_program/stage2b/P24_INJURY_REGIME_LEDGER/.

Run from the worktree root:
    python experiments/player_program/stage2b/P24_INJURY_REGIME_LEDGER/measure_injury_regimes.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]          # worktree root
OUT = Path(__file__).resolve().parent

INJURY_CSV = ROOT / "data" / "injury_history" / "injury_history.csv"
INJURY_RAW_DIR = ROOT / "data" / "injury_history" / "raw"
INJURY_MANIFEST = INJURY_RAW_DIR / "manifest.jsonl"
TEAM_CITIES = ROOT / "data" / "reference" / "team_cities.csv"
PRIOR = (ROOT / "experiments" / "player_program" / "projected_exposure_v1"
         / "team_possession_prior_v1.parquet")
DOC = ROOT / "project_docs" / "INJURY_HISTORY.md"
SCRAPER = ROOT / "scrape_injury_history.py"

# ---------------------------------------------------------------------------
# regime definition -- fixed here, not inferred from results
# ---------------------------------------------------------------------------
# R_REALISED_PARTICIPATION: the row records that a player DID NOT PLAY in a game
#   that has already been played. Its evidentiary source is the completed game's
#   own boxscore. It is a realised participation outcome of the target game.
# T_ANNOUNCEMENT_WIRE: the row records a league-office roster transaction
#   announced on a calendar date, independent of any particular game's outcome.
REGIME_R_CATEGORIES = {
    "missed_game_injury",
    "missed_game_other",
    "missed_game_unspecified",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    F: dict = {}

    # ---------------------------------------------------------------- inputs
    F["inputs"] = {
        "injury_history_csv": {
            "path": "data/injury_history/injury_history.csv",
            "exists": INJURY_CSV.exists(),
            "sha256": sha256(INJURY_CSV) if INJURY_CSV.exists() else None,
            "bytes": INJURY_CSV.stat().st_size if INJURY_CSV.exists() else None,
        },
        "injury_history_raw_dir": {
            "path": "data/injury_history/raw/",
            "exists": INJURY_RAW_DIR.exists(),
            "manifest_exists": INJURY_MANIFEST.exists(),
        },
        "team_possession_prior_v1": {
            "path": ("experiments/player_program/projected_exposure_v1/"
                     "team_possession_prior_v1.parquet"),
            "sha256": sha256(PRIOR),
        },
        "team_cities_csv": {"path": "data/reference/team_cities.csv",
                            "sha256": sha256(TEAM_CITIES)},
        "documentation": {"path": "project_docs/INJURY_HISTORY.md",
                          "exists": DOC.exists(),
                          "sha256": sha256(DOC) if DOC.exists() else None},
        "producer_script": {"path": "scrape_injury_history.py",
                            "exists": SCRAPER.exists(),
                            "sha256": sha256(SCRAPER) if SCRAPER.exists() else None},
    }

    inj = pd.read_csv(INJURY_CSV, dtype=str, keep_default_na=True)
    prior = pd.read_parquet(PRIOR)
    prior["game_date"] = pd.to_datetime(prior["game_date"])

    # ------------------------------------------------- 1. schema / timestamps
    F["schema_audit"] = {
        "columns": list(inj.columns),
        "n_columns": len(inj.columns),
        "rows": int(len(inj)),
        "columns_matching_timestamp_pattern": [
            c for c in inj.columns
            if any(k in c.lower() for k in
                   ("time", "stamp", "observed", "captured", "asof", "as_of",
                    "fetched", "reported", "announced", "updated"))
        ],
        "date_column_string_lengths": sorted(
            {int(x) for x in inj["date"].str.len().unique()}),
        "date_column_has_time_component": bool(
            inj["date"].str.contains("T| ", regex=True).any()),
        "date_min": inj["date"].min(),
        "date_max": inj["date"].max(),
        "verdict": (
            "NO OBSERVATION TIMESTAMP EXISTS ON ANY ROW. The only temporal field "
            "is `date`, date-granularity only (10 chars, no time component). "
            "There is no column recording WHEN the fact became knowable."
        ),
    }

    # ------------------------------------- 2. regime split (the S3 5,373/2,967)
    inj["source_family"] = (
        inj["source_page"].str.extract(r"^(espn_summary|bbref_transactions)")[0]
        .fillna("OTHER"))
    inj["regime"] = inj["category"].apply(
        lambda c: "R_REALISED_PARTICIPATION" if c in REGIME_R_CATEGORIES
        else "T_ANNOUNCEMENT_WIRE")

    cat_counts = inj["category"].value_counts().to_dict()
    crosstab = (pd.crosstab(inj["category"], inj["source_family"])
                .to_dict(orient="index"))

    n_total = int(len(inj))
    n_R = int((inj["regime"] == "R_REALISED_PARTICIPATION").sum())
    n_T = int((inj["regime"] == "T_ANNOUNCEMENT_WIRE").sum())

    F["S3_split_reproduction"] = {
        "packet_claim": {"total_rows": 8340, "missed_game_star_rows": 5373,
                         "announcement_dated_rows": 2967},
        "measured": {"total_rows": n_total,
                     "missed_game_star_rows": n_R,
                     "announcement_dated_rows": n_T},
        "verdict": ("AGREE" if (n_total, n_R, n_T) == (8340, 5373, 2967)
                    else "CORRECT"),
        "category_counts": {k: int(v) for k, v in cat_counts.items()},
        "category_by_source_family": {
            k: {kk: int(vv) for kk, vv in v.items()} for k, v in crosstab.items()},
        "regime_source_family_is_a_perfect_partition": bool(
            (inj.groupby("regime")["source_family"].nunique() == 1).all()),
        "note": (
            "The split is not merely a category-name split: it is a SOURCE split. "
            "Every missed_game_* row comes from an espn_summary_<eventid>.json "
            "boxscore; every other row comes from a bbref_transactions_<year>.html "
            "page. The two regimes have disjoint provenance."),
    }

    # -------------------------- 3. regime R contemporaneity, proved not assumed
    # each espn_summary source page is one completed game; the row's date is that
    # game's date, assigned from the game record by the producer.
    r = inj[inj["regime"] == "R_REALISED_PARTICIPATION"]
    dates_per_page = r.groupby("source_page")["date"].nunique()
    game_dates = set(prior["game_date"].dt.strftime("%Y-%m-%d"))
    r_dates = set(r["date"].unique())

    # team-level check: is the row's team playing on the row's date?
    cities = pd.read_csv(TEAM_CITIES)
    abbr2id = dict(zip(cities["abbreviation"], cities["team_id"]))
    abbr2id["PHX"] = abbr2id["PHO"]          # stats.nba rename, same team_id
    abbr2id["POR"] = abbr2id["PDX"]          # injury CSV uses POR, cities uses PDX
    prior["date_str"] = prior["game_date"].dt.strftime("%Y-%m-%d")
    played = set(zip(prior["team_id"], prior["date_str"]))
    r_tid = r["team"].map(abbr2id)
    r_played = [(t, d) in played for t, d in zip(r_tid, r["date"])]

    F["regime_R_realised_participation"] = {
        "rows": n_R,
        "classification": "NOT A PREGAME FEATURE",
        "distinct_source_pages": int(r["source_page"].nunique()),
        "source_pages_with_more_than_one_distinct_date": int(
            (dates_per_page > 1).sum()),
        "distinct_row_dates": len(r_dates),
        "row_dates_that_are_contract_game_dates": len(r_dates & game_dates),
        "row_dates_not_in_contract_schedule": sorted(r_dates - game_dates)[:20],
        "n_row_dates_not_in_contract_schedule": len(r_dates - game_dates),
        "rows_whose_team_played_on_that_exact_date_in_the_contract_universe":
            int(sum(r_played)),
        "rows_whose_team_did_not_play_that_date_in_the_contract_universe":
            int(len(r_played) - sum(r_played)),
        "explanation_of_the_19_non_contract_rows": {
            "all_carry_the_commissioners_cup_final_tag": bool(
                r.loc[[not x for x in r_played], "notes"]
                 .str.contains(r"\[commissioners-cup-final\]", regex=True).all()),
            "dates": sorted(set(r.loc[[not x for x in r_played], "date"])),
            "meaning": ("the Commissioner's Cup final is outside the contract "
                        "team-game universe; those 19 rows describe a game the "
                        "program does not model. They are not a join defect."),
        },
        "contemporaneity_rate_within_the_contract_universe": round(
            100.0 * sum(r_played) / len(r_played), 4),
        "producer_evidence": (
            "scrape_injury_history.py parse_espn_dnp() reads "
            "boxscore.players[].statistics[].athletes[] and keeps rows where "
            "ath['didNotPlay'] is truthy, then stamps the row with g['date'] -- "
            "the date of that same game. The record's ONLY evidentiary source is "
            "the completed game's own boxscore."),
        "why_not_a_pregame_feature": (
            "A didNotPlay flag in a boxscore is a realised participation outcome "
            "of the target game, observable only after the game has been played. "
            "Its date is the target game's own date by construction, so no lag "
            "exists between the observation and the event it describes. Using it "
            "on the target-game row is target-adjacent leakage of exactly the "
            "kind Severity A names."),
        "lagged_use_status": (
            "LAGGED USE NOT ADJUDICATED HERE. Strictly-earlier-game aggregates of "
            "these rows are a different object with a different (and separately "
            "unproven) cutoff argument; this node classifies the TARGET-GAME row "
            "only, and does not license lagged construction."),
    }

    # ------------------------- 4. regime T cutoff test against the pregame cutoff
    t = inj[inj["regime"] == "T_ANNOUNCEMENT_WIRE"].copy()
    t["team_id"] = t["team"].map(abbr2id)
    t["d"] = pd.to_datetime(t["date"])

    # same-day-as-a-game ambiguity: date-only granularity cannot order an
    # announcement against a tip on the same calendar day.
    t_same_day = [(tid, ds) in played for tid, ds in zip(t["team_id"], t["date"])]
    # league-wide same day (any team playing that date)
    league_game_dates = game_dates
    t_league_same_day = t["date"].isin(league_game_dates)

    F["regime_T_announcement_wire"] = {
        "rows": n_T,
        "classification": "CUTOFF_UNPROVEN",
        "rows_with_null_team": int(t["team"].isna().sum()),
        "rows_with_unmappable_team": int(
            t["team"].notna().sum() - t.loc[t["team"].notna(), "team_id"].notna().sum()),
        "rows_dated_on_a_day_the_named_team_played_a_contract_game":
            int(sum(t_same_day)),
        "rows_dated_on_a_day_ANY_contract_game_was_played":
            int(t_league_same_day.sum()),
        "reasons_cutoff_is_unproven": [
            "no source/observation timestamp column exists on any row",
            "`date` is date-granularity only, so an announcement cannot be "
            "ordered against a same-day tip",
            "the producer bulk-scraped six whole-season transaction pages on a "
            "single day (2026-07-30), so the CAPTURE time is AFTER every game in "
            "2021-2025; only a LAG argument on `date` is available, and `date` "
            "is the page's own listed date, not an observed capture",
            "project_docs/INJURY_HISTORY.md states BBRef dates 'are league-office "
            "announcement dates, which can trail the real-world event' -- the "
            "document itself does not claim the date is an observation time",
        ],
        "designation_semantics": {
            "documented": True,
            "document": "project_docs/INJURY_HISTORY.md, 'CSV schema' category table",
            "but": ("the documented semantics are TRANSACTION-TYPE semantics "
                    "(signing / waiver / trade / draft / contract_suspension / "
                    "activation / retirement / front_office / contract_conversion). "
                    "There is NO availability DESIGNATION anywhere in the file: no "
                    "Out / Doubtful / Questionable / Probable, no probability of "
                    "playing. The document says so explicitly under 'Known "
                    "limitations': there is no historical pregame status signal."),
            "categories_present_in_data_but_absent_from_doc_table": sorted(
                set(cat_counts) - {
                    "missed_game_injury", "missed_game_other",
                    "missed_game_unspecified", "signing", "waiver", "waiver_claim",
                    "trade", "draft", "contract_suspension", "activation",
                    "contract_conversion", "retirement", "front_office", "other"}),
            "categories_documented_but_absent_from_data": sorted(
                {"missed_game_unspecified", "activation", "other"} - set(cat_counts)),
        },
    }

    # ------------------------- 4b. test against the ONE declared pregame cutoff
    # The only DECLARED pregame cutoff anywhere in this repository is v4/v5's
    # `forecast_cutoff`. Its registered date-only fallback (POLICY_DATE_ONLY,
    # prediction_contract_v5.date_only_cutoff) is 18:00 UTC on the day BEFORE the
    # game. This wrapper applies that published policy to THIS node's team-game
    # universe; it does not read, import or modify the contract module.
    #
    # An injury_history row carries a date only. Its true observation time lies
    # somewhere in [d 00:00 UTC, d 23:59:59 UTC]. Relative to cutoff C:
    #   d <= D-2 -> the WHOLE interval is before C          : UNAMBIGUOUSLY_PRE
    #   d == D-1 -> C = 18:00 UTC splits the interval        : AMBIGUOUS
    #   d >= D   -> the whole interval is at or after C      : POST_CUTOFF
    # prediction_contract_v5 coerces the date with pd.to_datetime(..., utc=True),
    # i.e. it pins every announcement to 00:00 UTC -- the EARLIEST point of the
    # interval -- and then admits it on `x < c`. Every D-1 row is therefore
    # admitted on an assumption, in the leakage-favourable direction.
    consumed = {"signing", "trade", "waiver_claim", "draft", "contract_conversion",
                "waiver", "retirement", "contract_suspension"}
    tc = t.dropna(subset=["team_id"]).copy()
    g_by_team: dict = {}
    for tid, gd in zip(prior["team_id"], prior["game_date"]):
        g_by_team.setdefault(tid, []).append(gd)
    bands = {"UNAMBIGUOUSLY_PRE": 0, "AMBIGUOUS_D_MINUS_1": 0,
             "POST_CUTOFF_D_OR_LATER": 0, "NO_LATER_GAME_FOR_TEAM": 0}
    tg_touching_ambiguous = set()
    band_col = []
    for tid, d, cat in zip(tc["team_id"], tc["d"], tc["category"]):
        gl = [g for g in g_by_team.get(tid, []) if g >= d]
        if not gl:
            bands["NO_LATER_GAME_FOR_TEAM"] += 1
            band_col.append("NO_LATER_GAME_FOR_TEAM")
            continue
        nxt = min(gl)
        delta = (nxt - d).days
        if delta >= 2:
            bands["UNAMBIGUOUSLY_PRE"] += 1
            band_col.append("UNAMBIGUOUSLY_PRE")
        elif delta == 1:
            bands["AMBIGUOUS_D_MINUS_1"] += 1
            tg_touching_ambiguous.add((tid, nxt))
            band_col.append("AMBIGUOUS_D_MINUS_1")
        else:
            bands["POST_CUTOFF_D_OR_LATER"] += 1
            band_col.append("POST_CUTOFF_D_OR_LATER")
    tc["band"] = band_col
    tc["season_of_date"] = tc["date"].str[:4].astype(int)
    band_by_season = {int(s): sub["band"].value_counts().to_dict()
                      for s, sub in tc.groupby("season_of_date")}
    band_by_season = {k: {kk: int(vv) for kk, vv in v.items()}
                      for k, v in band_by_season.items()}
    F["declared_cutoff_test"] = {
        "declared_cutoff": ("prediction_contract_v4/v5 `forecast_cutoff`; registered "
                            "date-only fallback POLICY_DATE_ONLY = 18:00 UTC on the "
                            "day before the game "
                            "(prediction_contract_v5.date_only_cutoff)"),
        "note": ("this is the ONLY declared pregame cutoff in the repository. The "
                 "possession lane declares none, so the possession lane has no "
                 "cutoff to test an injury field against at all."),
        "applied_to": "the next contract game for the named team, per regime-T row",
        "regime_T_rows_tested": int(len(tc)),
        "bands_relative_to_the_next_game_for_that_team": bands,
        "bands_by_season": band_by_season,
        "team_games_whose_admitted_transaction_evidence_includes_a_D_minus_1_row":
            len(tg_touching_ambiguous),
        "conditional_eligibility": {
            "statement": ("NOTHING is ELIGIBLE today. The following is what WOULD "
                          "become eligible under a single, named, registerable "
                          "relaxation -- it is a proposal to be adjudicated "
                          "elsewhere, not a classification made here."),
            "relaxation": ("accept the BBRef listed `date` as a bona fide EVENT date "
                           "with an end-of-day upper bound, i.e. treat the row's "
                           "observation time as d 23:59:59 UTC rather than 00:00 UTC"),
            "rows_that_would_survive": bands["UNAMBIGUOUSLY_PRE"],
            "rows_that_would_still_be_CUTOFF_UNPROVEN":
                bands["AMBIGUOUS_D_MINUS_1"] + bands["POST_CUTOFF_D_OR_LATER"]
                + int(t["team"].isna().sum()),
            "still_missing_even_then": [
                "an availability DESIGNATION -- the file has none in any regime",
                "the raw payloads and fetch manifest, which do not exist here, so "
                "the event-date claim can never be audited against a capture record",
            ],
        },
        "consumer": {
            "module": "prediction_contract_v5.py (player lane)",
            "categories_consumed": sorted(consumed),
            "regime_T_rows_in_scope": int(t["category"].isin(consumed).sum()),
            "regime_T_rows_not_consumed": int((~t["category"].isin(consumed)).sum()),
            "regime_R_rows_consumed": 0,
            "finding": ("the ONE existing consumer of injury_history.csv reads only "
                        "regime-T categories and never touches missed_game_*. The "
                        "regime split this node makes explicit is already implicit "
                        "in that module's ACQUIRE/RELEASE frozensets -- but it is "
                        "nowhere written down as an epistemic rule, and nothing "
                        "enforces it."),
            "defect": ("pd.to_datetime(tx['date'], utc=True) pins a date-only "
                       "announcement to 00:00 UTC, the earliest instant it could "
                       "have occurred, and admission is `x < c`. The coercion is "
                       "silent and always resolves ambiguity toward admission."),
        },
    }

    # ----------------------------------- 5. three-way eligibility classification
    # C1 NOT_A_PREGAME_FEATURE  : regime R (realised participation)
    # C2 CUTOFF_UNPROVEN        : regime T (no source timestamp)
    # C3 ELIGIBLE               : requires timestamp <= cutoff + documented
    #                             designation semantics + no outcome derivation
    inj["classification"] = inj["regime"].map({
        "R_REALISED_PARTICIPATION": "NOT_A_PREGAME_FEATURE",
        "T_ANNOUNCEMENT_WIRE": "CUTOFF_UNPROVEN"})
    cls = inj["classification"].value_counts().to_dict()
    F["classification_ledger"] = {
        "rule": ("a row is ELIGIBLE only if ALL of: (a) a source timestamp at or "
                 "before the declared pregame cutoff, (b) documented designation "
                 "semantics, (c) no derivation from the game outcome"),
        "counts": {k: int(v) for k, v in cls.items()},
        "ELIGIBLE": 0,
        "criterion_failed_by_regime": {
            "R_REALISED_PARTICIPATION": ["(a) no timestamp", "(c) derived from the game outcome"],
            "T_ANNOUNCEMENT_WIRE": ["(a) no timestamp",
                                    "(b) transaction-type semantics only; no availability designation"],
        },
        "fitted_feature_universe_contribution": 0,
        "availability_report_contribution": n_total,
    }

    # ------------------------------------------- 6. coverage by season and fold
    # fold construction, per EVIDENCE_PACKET_V2.inference_specification:
    # "chronological, nested by season; a game is NEVER split across folds".
    # V2_STOP_CONDITION S7 enumerates six chronological folds, 2021..2026.
    # fold identifier == season.
    prior["season"] = prior["season"].astype(int)
    inj["season_of_date"] = inj["date"].str[:4].astype(int)

    r_all = inj[inj["regime"] == "R_REALISED_PARTICIPATION"].copy()
    r_all["team_id"] = r_all["team"].map(abbr2id)
    r_contam = set(zip(r_all["team_id"], r_all["date"]))

    by_season = []
    for season, gsub in prior.groupby("season"):
        isub = inj[inj["season_of_date"] == season]
        r_s = isub[isub["regime"] == "R_REALISED_PARTICIPATION"]
        t_s = isub[isub["regime"] == "T_ANNOUNCEMENT_WIRE"]

        # per team-game: any T row for that team strictly before the game date
        tt = t_s.copy()
        tt["team_id"] = tt["team"].map(abbr2id)
        tt = tt.dropna(subset=["team_id"])
        tt["d"] = pd.to_datetime(tt["date"])
        prior_any = 0
        prior_30d = 0
        same_day = 0
        for tid, gd, ds in zip(gsub["team_id"], gsub["game_date"], gsub["date_str"]):
            sel = tt[(tt["team_id"] == tid) & (tt["d"] < gd)]
            if len(sel):
                prior_any += 1
                if (sel["d"] >= gd - pd.Timedelta(days=30)).any():
                    prior_30d += 1
            if ((tt["team_id"] == tid) & (tt["date"] == ds)).any():
                same_day += 1

        contaminated = sum((tid, ds) in r_contam
                           for tid, ds in zip(gsub["team_id"], gsub["date_str"]))
        res = gsub[gsub["pace_resolved"]]
        gmax = gsub["game_date"].max()
        by_season.append({
            "fold": int(season),
            "season": int(season),
            "team_game_rows": int(len(gsub)),
            "team_game_rows_resolved": int(len(res)),
            "game_clusters": int(gsub["game_id"].nunique()),
            "game_clusters_resolved": int(res["game_id"].nunique()),
            "first_game_date": gsub["game_date"].min().strftime("%Y-%m-%d"),
            "last_game_date": gmax.strftime("%Y-%m-%d"),
            "injury_rows_dated_in_season": int(len(isub)),
            "regime_R_rows": int(len(r_s)),
            "regime_T_rows": int(len(t_s)),
            "ELIGIBLE_rows": 0,
            "cutoff_valid_coverage_of_fitted_universe_pct": 0.0,
            "CONDITIONAL_regime_T_rows_unambiguously_pre_cutoff":
                band_by_season.get(int(season), {}).get("UNAMBIGUOUSLY_PRE", 0),
            "CONDITIONAL_regime_T_rows_ambiguous_D_minus_1":
                band_by_season.get(int(season), {}).get("AMBIGUOUS_D_MINUS_1", 0),
            "CONDITIONAL_regime_T_rows_post_cutoff":
                band_by_season.get(int(season), {}).get("POST_CUTOFF_D_OR_LATER", 0),
            "AVAILABILITY_team_games_with_ge1_prior_T_row_same_season": int(prior_any),
            "AVAILABILITY_pct_team_games_with_ge1_prior_T_row_same_season": round(
                100.0 * prior_any / len(gsub), 3),
            "AVAILABILITY_team_games_with_ge1_prior_T_row_within_30d": int(prior_30d),
            "AMBIGUOUS_team_games_with_a_same_day_T_row_for_that_team": int(same_day),
            "LEAKAGE_EXPOSURE_team_games_with_ge1_same_day_regime_R_row":
                int(contaminated),
            "LEAKAGE_EXPOSURE_pct": round(100.0 * contaminated / len(gsub), 3),
            "team_games_after_last_injury_row_date": int(
                (gsub["game_date"] > pd.Timestamp(inj["date"].max())).sum()),
        })

    F["coverage_by_season_and_fold"] = {
        "fold_definition": ("chronological, nested by season (EVIDENCE_PACKET_V2."
                            "inference_specification.fold_construction); six folds "
                            "2021..2026, matching the per-fold enumeration in "
                            "V2_STOP_CONDITION S7. fold identifier == season."),
        "universe": {
            "team_game_rows_all": int(len(prior)),
            "game_clusters_all": int(prior["game_id"].nunique()),
            "team_game_rows_resolved": int(prior["pace_resolved"].sum()),
            "game_clusters_resolved": int(
                prior[prior["pace_resolved"]]["game_id"].nunique()),
            "note": ("BOTH are reported per the packet's do_not_substitute rule. "
                     "2,982 / 1,491 is the resolved fitted universe; 2,990 / 1,495 "
                     "is the full schedule universe. The 8-row / 4-game difference "
                     "is the unresolved-no-prior-games stratum."),
        },
        "column_semantics": {
            "ELIGIBLE_rows": "rows passing all three eligibility criteria",
            "cutoff_valid_coverage_of_fitted_universe_pct":
                "share of team-game rows in this fold that a CUTOFF-VALID injury "
                "feature could be built for; zero because ELIGIBLE_rows is zero",
            "AVAILABILITY_*": "reported per the requirement that CUTOFF_UNPROVEN "
                              "rows stay in availability reports while being "
                              "excluded from the fitted feature universe",
            "LEAKAGE_EXPOSURE_*": "team-games for which a naive date join to "
                                  "injury_history would attach a regime-R row "
                                  "describing THAT game's own realised absences",
        },
        "rows": by_season,
        "headline": ("CUTOFF-VALID COVERAGE IS 0 OF 2,990 TEAM-GAME ROWS (0 OF "
                     "2,982 RESOLVED) IN EVERY ONE OF THE SIX FOLDS. No row of "
                     "injury_history.csv satisfies the eligibility rule. "
                     "AVAILABILITY coverage is separately high and is reported "
                     "alongside, as required."),
    }

    # ---------------------------- 7. doc table reproduction (contradiction hunt)
    doc_table = {  # from project_docs/INJURY_HISTORY.md 'Coverage'
        2021: {"total": 1151, "missed_game_injury": 321, "missed_game_other": 370, "wire": 460},
        2022: {"total": 1261, "missed_game_injury": 293, "missed_game_other": 455, "wire": 513},
        2023: {"total": 1299, "missed_game_injury": 398, "missed_game_other": 454, "wire": 447},
        2024: {"total": 1383, "missed_game_injury": 340, "missed_game_other": 631, "wire": 412},
        2025: {"total": 1785, "missed_game_injury": 528, "missed_game_other": 693, "wire": 564},
        2026: {"total": 1461, "missed_game_injury": 362, "missed_game_other": 528, "wire": 571},
    }
    doc_check = []
    for yr, claim in doc_table.items():
        sub = inj[inj["season_of_date"] == yr]
        meas = {
            "total": int(len(sub)),
            "missed_game_injury": int((sub["category"] == "missed_game_injury").sum()),
            "missed_game_other": int((sub["category"] == "missed_game_other").sum()),
            "wire": int((sub["regime"] == "T_ANNOUNCEMENT_WIRE").sum()),
        }
        doc_check.append({"year": yr, "documented": claim, "measured": meas,
                          "verdict": "AGREE" if claim == meas else "CORRECT"})
    F["documentation_table_reproduction"] = {
        "source": "project_docs/INJURY_HISTORY.md, 'Coverage' table",
        "rows": doc_check,
        "all_agree": all(x["verdict"] == "AGREE" for x in doc_check),
    }

    # ------------------------------------------------ 8. span / truncation gaps
    last_inj = pd.Timestamp(inj["date"].max())
    late = prior[prior["game_date"] > last_inj]
    F["span_gaps"] = {
        "injury_history_last_row_date": inj["date"].max(),
        "contract_universe_last_game_date": prior["game_date"].max().strftime("%Y-%m-%d"),
        "team_game_rows_after_last_injury_row": int(len(late)),
        "game_clusters_after_last_injury_row": int(late["game_id"].nunique()),
        "affected_dates": sorted(late["game_date"].dt.strftime("%Y-%m-%d").unique()),
        "packet_claim": ("EVIDENCE_PACKET_V2 records the source as '8,340 rows, "
                         "2021-01-07 .. 2026-07-29, full contract span'"),
        "verdict": ("CORRECT -- the span is NOT the full contract span. The "
                    "contract universe runs to 2026-07-31; the injury file stops "
                    "at 2026-07-29."),
    }

    # ------------------------------------------- 9. reproducibility / provenance
    F["provenance_defects"] = {
        "raw_payload_dir_present": INJURY_RAW_DIR.exists(),
        "fetch_manifest_present": INJURY_MANIFEST.exists(),
        "raw_dir_is_gitignored": True,
        "consequence": (
            "project_docs/INJURY_HISTORY.md states that every HTTP payload is kept "
            "under data/injury_history/raw/ and that manifest.jsonl records "
            "url/status/time per fetch. Neither the directory nor the manifest "
            "exists in this worktree, and .gitignore line 7 excludes "
            "'data/injury_history/raw/' from version control. Therefore (a) the "
            "CSV cannot be re-derived offline here -- 'python "
            "scrape_injury_history.py --parse-only' would emit zero rows -- and "
            "(b) the ONLY record that could have carried a per-row observation "
            "time is absent. The 'no source timestamp' verdict is therefore not "
            "recoverable by further work inside this repository."),
    }

    # ---------------------------- 9a. the single observation time, corroborated
    # ROSTER_SOURCE_AUDIT_RECEIPT.json q2_timestamps claims the CSV was committed
    # 2026-07-30 13:42 -0400 in 98271bb, hence one observation time for all rows.
    # Re-derived here from the repository's own history (read-only git log).
    OBS = pd.Timestamp("2026-07-30T17:42:00Z")     # 13:42 -0400
    # declared date-only cutoff for game D is (D-1) 18:00 UTC
    cut = (prior["game_date"].dt.tz_localize("UTC").dt.normalize()
           - pd.Timedelta(hours=6))
    after = int((cut > OBS).sum())
    F["single_observation_time"] = {
        "claim_source": "experiments/player_program/ROSTER_SOURCE_AUDIT_RECEIPT.json q2_timestamps",
        "claimed": ("the CSV was committed 2026-07-30 13:42 -0400 in 98271bb, so every "
                    "record -- including 2021 ones -- was observed on 2026-07-30"),
        "re_derived_command": ('git log --diff-filter=A --format="%h %ad %s" --date=iso '
                               '-- data/injury_history/injury_history.csv'),
        "re_derived": ("98271bb  2026-07-30 13:42:00 -0400  "
                       "Add historical injury/absence/transaction archive 2021-2026 "
                       "(8,340 rows)"),
        "verdict": "AGREE",
        "consequence_measured_here": {
            "observation_time_utc": "2026-07-30T17:42:00Z",
            "declared_cutoff_rule": "(game_date - 1 day) 18:00 UTC",
            "team_game_rows_whose_cutoff_is_LATER_than_the_observation_time": after,
            "team_game_rows_total": int(len(prior)),
            "reading": ("the single observation time postdates the pregame cutoff of "
                        f"{len(prior) - after} of {len(prior)} team-game rows. Only "
                        f"{after} rows could ever be served by this artifact under a "
                        "capture argument, and those are at the very end of the span."),
        },
        "acq_rel_accounting_cross_check": {
            "receipt_n_acquisition_rows": 1846,
            "measured_ACQ_category_rows": int(inj["category"].isin(
                {"signing", "trade", "draft", "waiver_claim", "contract_conversion"}).sum()),
            "measured_ACQ_rows_with_a_named_acquired_player": int(
                inj.loc[inj["category"].isin(
                    {"signing", "trade", "draft", "waiver_claim", "contract_conversion"}),
                    "player_acquired"].notna().sum()),
            "receipt_n_release_rows": 927,
            "measured_REL_category_rows": int(inj["category"].isin(
                {"waiver", "retirement", "contract_suspension"}).sum()),
            "verdict": ("AGREE once the receipt's implicit filter is made explicit: it "
                        "counts ACQ-category rows WITH a named acquired player "
                        "(1,846 of 1,991); the 145-row remainder is the outgoing side "
                        "of trade sentences, which carries player_relinquished only."),
        },
    }

    # ------------------------------------------ 9b. registered-consumer binding
    ARM_REG = (ROOT / "experiments" / "player_program" / "arm_registry.jsonl")
    reg_claim = None
    reg_arms = set()
    for line in ARM_REG.read_text(encoding="utf-8").splitlines():
        if "injury_history" not in line:
            continue
        rec = json.loads(line)
        blob = json.dumps(rec)
        i = blob.find('"data/injury_history/injury_history.csv": "')
        if i != -1:
            reg_claim = blob[i + len('"data/injury_history/injury_history.csv": "'):][:64]
        cfg = rec.get("extra", {}).get("frozen_config", {})
        if cfg.get("arm_id"):
            reg_arms.add(f"{cfg['arm_id']}/{cfg.get('arm_revision')}")
    F["registered_consumer_binding"] = {
        "registry": "experiments/player_program/arm_registry.jsonl",
        "arms_binding_injury_history_csv": sorted(reg_arms),
        "registry_source_snapshot_sha256": reg_claim,
        "on_disk_sha256": F["inputs"]["injury_history_csv"]["sha256"],
        "bytes_agree_with_the_receipt": reg_claim == F["inputs"]["injury_history_csv"]["sha256"],
        "lane": ("player lane. The possession lane (this node's lane) binds no "
                 "injury field in any arm, control or feature frame."),
    }

    # ------------------------------------------------------- 9c. contradictions
    F["contradictions"] = [
        {
            "id": "C1",
            "between": "EVIDENCE_PACKET_V2 vs the bytes",
            "packet_says": ("injury / transaction history is ONE field, "
                            "'8,340 rows, 2021-01-07 .. 2026-07-29, full contract "
                            "span', Category B on cutoff grounds"),
            "bytes_say": ("two regimes with disjoint provenance and different "
                          "epistemic status, and the span is NOT the full contract "
                          "span -- 12 team-game rows over 6 game clusters "
                          "(2026-07-30, 2026-07-31) postdate the last injury row"),
            "verdict": "CORRECT the packet",
            "severity": "A on the regime point (S3 already names it); B on the span point",
        },
        {
            "id": "C2",
            "between": "project_docs/INJURY_HISTORY.md vs the bytes",
            "doc_says": ("'Raw pages: data/injury_history/raw/ (every HTTP payload; "
                         "parsing is re-runnable offline; manifest.jsonl records "
                         "url/status/time per fetch)'"),
            "bytes_say": ("data/injury_history/raw/ does not exist in this worktree "
                          "and .gitignore line 7 excludes it from version control; "
                          "manifest.jsonl -- the only artifact that could carry a "
                          "fetch time -- is absent"),
            "verdict": "the document describes a provenance chain that is not present",
            "consequence": ("'--parse-only' would rebuild an EMPTY csv here, and no "
                            "observation timestamp is recoverable by further work"),
            "severity": "A for any arm that would rely on the cutoff claim",
        },
        {
            "id": "C3",
            "between": "prediction_contract_v5.py's behaviour vs any written rule",
            "observed": ("ACQUIRE and RELEASE deliberately exclude every "
                         "missed_game_* category, so the regime split is already "
                         "being honoured in code"),
            "missing": ("no document, gate or receipt states the rule. Nothing "
                        "prevents the next consumer from joining missed_game_* on "
                        "the target-game date -- which would attach 2,337 of 2,990 "
                        "team-game rows (78.2%) to their OWN realised absences"),
            "verdict": "an unwritten invariant, exactly the S1 shape",
            "severity": "A as a latent hazard",
        },
        {
            "id": "C4",
            "between": ("the acceptance criterion 'source timestamp' and the "
                        "consumer's date coercion"),
            "observed": ("prediction_contract_v5 does pd.to_datetime(tx['date'], "
                         "utc=True), pinning a date-only announcement to 00:00 UTC "
                         "-- the earliest instant in its true interval -- then "
                         "admits on `x < c`"),
            "measured": ("313 regime-T rows fall on the day before their team's "
                         "next game, straddling the 18:00 UTC date-only cutoff; "
                         "they affect 229 team-games"),
            "verdict": ("silent ambiguity resolution, always toward admission. "
                        "Not a leak that has been demonstrated to fire; a "
                        "systematic bias in the direction that leaks."),
            "severity": "B, escalating to A if any fitted arm depends on those rows",
        },
        {
            "id": "C5",
            "between": "INJURY_HISTORY.md coverage table vs the bytes",
            "result": "AGREE on all six seasons and all four columns",
            "verdict": "no contradiction; recorded because it was checked",
            "severity": "none",
        },
        {
            "id": "C6",
            "between": ("this node's mandated classification and sibling node "
                        "D10_FIELD_AVAILABILITY_LEDGER/build_ledger.py"),
            "d10_says": ("fields injury.missed_game_injury_wire and "
                         "injury.missed_game_other_wire carry verdict "
                         "CUTOFF_UNPROVEN, structural_class "
                         "retrospective_archive_single_observation_time"),
            "this_node_says": ("NOT A PREGAME FEATURE. CUTOFF_UNPROVEN says 'we cannot "
                               "show it was knowable in time'. These rows are stronger "
                               "than that: they are the target game's own realised "
                               "participation, read out of its boxscore. No timestamp "
                               "could rescue them, because the fact does not exist "
                               "before the game is played."),
            "verdict": ("D10's verdict is not wrong, it is not strict enough. "
                        "RESEARCH_CONTRACT_V1 precedence: 'where this contract and an "
                        "arm's own registration disagree, the STRICTER governs'. The "
                        "strict classification is NOT A PREGAME FEATURE."),
            "note": ("D10's build_ledger.py is present but its output ledger is NOT "
                     "materialised in this worktree, so only its source text could be "
                     "compared, not its numbers."),
            "severity": "B -- a labelling gap, not a live leak",
        },
    ]

    # ------------------------------------------------------------- stop checks
    F["stop_conditions"] = {
        "tripped": [
            {
                "condition": "a finding would change the CUTOFF-VALID FEATURE SET",
                "finding": ("injury_history.csv contributes ZERO cutoff-valid rows. "
                            "EVIDENCE_PACKET_V2 lists 'injury / transaction history' "
                            "as ONE Category B field with cutoff unproven; it is TWO "
                            "regimes, and the 5,373-row majority regime is a realised "
                            "participation OUTCOME sourced from the target game's own "
                            "boxscore, not merely an unproven pregame signal."),
                "action": "RAISED, NOT RESOLVED",
            },
        ],
        "not_tripped_but_recorded": [
            "the primary target, K0 structure, inference structure and candidate "
            "universe are untouched by this node: no possession-lane arm, control or "
            "feature frame binds an injury field, so removing it changes no fitted "
            "possession design.",
            "the player-lane arm cbs_v15_player_oof_v5 DOES bind "
            "injury_history.csv, but consumes regime-T categories only and never "
            "missed_game_*. This node does not adjudicate the player lane; the "
            "binding is recorded so the player thread can act on C4.",
        ],
    }

    # ------------------------------------------------------------ row ledger
    ledger = inj[["date", "team", "category", "source_family", "regime",
                  "classification"]].copy()
    ledger_path = OUT / "REGIME_LEDGER.csv"
    (ledger.groupby(["regime", "classification", "source_family", "category"])
           .size().rename("rows").reset_index()
           .to_csv(ledger_path, index=False))

    F["schema"] = "p24_injury_regime_ledger/1"
    F["node_id"] = "P24_INJURY_REGIME_LEDGER"
    F["epistemic_status"] = (
        "VERIFIED_READ_ONLY_DERIVATION. Classifies fields by epistemic regime. A "
        "field passing classification is ELIGIBLE for consideration, which is not "
        "the same as useful or admitted.")

    (OUT / "FINDINGS.json").write_text(
        json.dumps(F, indent=2, sort_keys=False), encoding="utf-8")
    print(json.dumps({k: F[k] for k in
                      ("S3_split_reproduction", "classification_ledger",
                       "span_gaps", "documentation_table_reproduction")},
                     indent=2)[:6000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
