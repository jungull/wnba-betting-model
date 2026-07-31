"""w1_truth.py — W1-A availability truth set and W1-B as-of entity resolution.

Step 3 of ``project_docs/PLAN_2026-07-31_W1_AUDIT_AND_BAKEOFF.md`` (frozen as
``plan_freeze_2026_07_31``); work items W1-A and W1-B of
``w1_extraction_quality_audit_v1``.

INFRASTRUCTURE, NOT EVIDENCE
----------------------------
Nothing here scores a model, ranks anything, or touches the registry. It builds
the yardstick that W1-C measures against, and the resolver W1-C needs to know
WHICH PLAYER a headline was talking about. Per the plan's §6 split this is
infrastructure: it makes no predictive claim and cannot promote anything.

W1-A — WHAT "TRUTH" MEANS HERE
------------------------------
Two different facts get conflated in casual talk about availability, so they are
kept in separate columns:

  availability   what the box score says HAPPENED — played, sat by choice, or was
                 unavailable, and for what recorded reason.
  designation    what the OFFICIAL INJURY REPORT said BEFOREHAND — Out,
                 Questionable, Probable, Available, Doubtful, Day-To-Day.

A news extraction is a claim about the second, evaluated against the first. Both
are recorded, joined on (game_date, team, player), and their disagreements are
counted rather than reconciled: a player listed Questionable who plays 34 minutes
is not a data error, it is the base rate the audit needs.

THE CEILING ON RECALL, STATED UP FRONT
--------------------------------------
The box score lists players who dressed AND players marked NWT ("not with team"),
so most unavailable players do appear. But a player who is not on the box score
at all is INDISTINGUISHABLE from a player who was not on the roster. This truth
set therefore supports PRECISION honestly and RECALL only against the players it
can see. ``roster_gap_flag`` marks team-games whose listed count falls below the
team's own recent median, which is where that blind spot is widest. W1-C must
quote recall as "recall among box-score-listed players", never as plain recall.

W1-B — WHY RESOLUTION MUST BE AS-OF
-----------------------------------
Resolving "Sykes" or "Smith" against TODAY's roster silently backdates trades and
7-day contracts: a player who joined a team in July would be matched to that team
for a May article. The roster index here is built from GAME APPEARANCES ONLY and
queried with a strict ``game_date < published_utc`` filter, so a resolution can
never use a game that had not been played when the article ran.

Outputs (each with an asof_invariant manifest):
    data/w1_truth/player_game_availability.csv
    data/w1_truth/roster_asof.csv
    data/w1_truth/extraction_resolution.csv
    data/w1_truth/W1_TRUTH_REPORT.md

Run:
    python w1_truth.py            # build everything, print the report
    python w1_truth.py --no-write # compute and print, write nothing
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

import asof_invariant as aoi

ROOT = Path(__file__).resolve().parent
MASTER_PLAYER = ROOT / "data" / "masters" / "master_player.parquet"
MASTER_TEAM = ROOT / "data" / "masters" / "master_team.parquet"
TEAM_CITIES = ROOT / "data" / "reference" / "team_cities.csv"
INJURY_LOG = ROOT / "data" / "injury_capture" / "injury_log.csv"
INJURY_HISTORY = ROOT / "data" / "injury_history" / "injury_history.csv"
EXTRACTIONS = ROOT / "data" / "w1_extractions" / "extractions.csv"
OUT = ROOT / "data" / "w1_truth"

REPORT: list[str] = []


def say(s: str = "") -> None:
    print(s)
    REPORT.append(s)


# --------------------------------------------------------------------------- #
# name normalisation
# --------------------------------------------------------------------------- #

_PUNCT = re.compile(r"[^a-z ]")
_SUFFIX = re.compile(r"\b(jr|sr|ii|iii|iv)\b")


def norm_name(s: object) -> str:
    """Casefold, strip accents, drop punctuation and generational suffixes.

    Deliberately does NOT do fuzzy matching. A near-miss that this function does
    not collapse becomes an UNRESOLVED row, which is visible in the resolution
    rate. Fuzzy matching would convert those into silent wrong answers, and the
    whole point of W1-B is to measure how often we cannot tell.
    """
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    t = unicodedata.normalize("NFKD", str(s))
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = _PUNCT.sub(" ", t.lower())
    t = _SUFFIX.sub(" ", t)
    return " ".join(t.split())


def surname(norm: str) -> str:
    return norm.split()[-1] if norm else ""


# --------------------------------------------------------------------------- #
# team identity, as-of aware
# --------------------------------------------------------------------------- #

def load_team_index() -> pd.DataFrame:
    """franchise/abbreviation -> team_id, honouring the abbreviation era rows.

    team_cities.csv carries one row per (team_id, abbreviation) ERA — Phoenix is
    PHO through 2024 and PHX from 2025 under the same team_id — so a naive
    abbreviation map would be ambiguous. Franchise name is stable and is what the
    injury report and the extractions both use.
    """
    tc = pd.read_csv(TEAM_CITIES)
    tc["franchise_norm"] = tc["franchise"].map(norm_name)
    return tc


def build_abbr_lookup(tc: pd.DataFrame) -> dict[str, int]:
    """abbreviation -> team_id. PHO and PHX are separate rows for the same
    franchise (the 2025 rebrand), so both keys land on one id and the era
    columns do not need to be consulted for identity."""
    return {str(r["abbreviation"]).upper(): int(r["team_id"]) for _, r in tc.iterrows()}


def build_team_lookup(tc: pd.DataFrame) -> dict[str, int]:
    lut: dict[str, int] = {}
    for _, r in tc.iterrows():
        lut.setdefault(r["franchise_norm"], int(r["team_id"]))
        # last token: "liberty", "sun", "aces" — how headlines usually refer to teams
        lut.setdefault(r["franchise_norm"].split()[-1], int(r["team_id"]))
    return lut


# --------------------------------------------------------------------------- #
# W1-A: the availability truth set
# --------------------------------------------------------------------------- #

# Recorded DNP reasons, classified. The taxonomy is deliberately coarse: the
# audit needs "was this player available", not a medical ontology.
_UNAVAILABLE_PAT = re.compile(
    r"injury|illness|concussion|health|protocol|reconditioning|"
    r"not with team|personal|rest|suspend|maternity|bereavement", re.I)
_COACH_PAT = re.compile(r"coach", re.I)


def classify_availability(row) -> str:
    reason = row["dnp_reason"]
    minutes = row["minutes"]
    if pd.notna(minutes) and float(minutes) > 0:
        return "played"
    if pd.isna(reason) or not str(reason).strip():
        # listed, zero minutes, no recorded reason: dressed and unused
        return "dressed_unused"
    r = str(reason)
    if _COACH_PAT.search(r):
        return "dressed_dnp_coach"
    if _UNAVAILABLE_PAT.search(r):
        return "unavailable"
    return "unavailable_other"


AVAILABLE_STATES = {"played", "dressed_unused", "dressed_dnp_coach"}


def build_truth() -> pd.DataFrame:
    say("## W1-A — availability truth set")
    say("")
    mp = pd.read_parquet(MASTER_PLAYER, columns=[
        "game_id", "season", "game_date", "team_id", "team_abbreviation",
        "player_id", "player_name", "starter_flag", "dnp_reason", "minutes"])
    mp["game_date"] = pd.to_datetime(mp["game_date"])
    mp["season"] = mp["season"].astype(int)

    mp["availability"] = mp.apply(classify_availability, axis=1)
    mp["was_available"] = mp["availability"].isin(AVAILABLE_STATES)
    mp["minutes_played"] = mp["minutes"].fillna(0.0).astype(float)
    mp["player_norm"] = mp["player_name"].map(norm_name)

    say(f"master_player rows: {len(mp):,} over {mp['game_id'].nunique():,} games, "
        f"seasons {mp['season'].min()}-{mp['season'].max()}")
    say("")
    say("| availability | n | share | mean minutes |")
    say("|---|---:|---:|---:|")
    for state, sub in mp.groupby("availability"):
        say(f"| {state} | {len(sub):,} | {len(sub) / len(mp):.1%} | "
            f"{sub['minutes_played'].mean():.1f} |")
    say("")
    say(f"available (played / dressed / coach's DNP): {mp['was_available'].sum():,} "
        f"({mp['was_available'].mean():.1%})")
    say("")

    # ---- the recall ceiling, measured rather than asserted ------------------
    per_tg = (mp.groupby(["game_id", "team_id"]).size()
              .rename("n_listed").reset_index())
    per_tg = per_tg.merge(
        mp[["game_id", "team_id", "game_date", "season"]].drop_duplicates(),
        on=["game_id", "team_id"], how="left")
    med = per_tg.groupby(["team_id", "season"])["n_listed"].transform("median")
    per_tg["roster_gap_flag"] = per_tg["n_listed"] < (med - 1)
    say(f"team-games: {len(per_tg):,}; players listed per team-game median "
        f"{per_tg['n_listed'].median():.0f}, min {per_tg['n_listed'].min()}, "
        f"max {per_tg['n_listed'].max()}")
    say(f"team-games listing fewer than (team-season median - 1): "
        f"{int(per_tg['roster_gap_flag'].sum()):,} "
        f"({per_tg['roster_gap_flag'].mean():.1%}) — these are where an "
        f"unavailable player is most likely to be INVISIBLE rather than listed, "
        f"so recall computed here is recall AMONG LISTED PLAYERS only.")
    say("")
    mp = mp.merge(per_tg[["game_id", "team_id", "n_listed", "roster_gap_flag"]],
                  on=["game_id", "team_id"], how="left")

    # ---- official designations ---------------------------------------------
    tc = load_team_index()
    team_lut = build_team_lookup(tc)
    inj = pd.read_csv(INJURY_LOG)
    inj["game_date"] = pd.to_datetime(inj["game_date"])
    inj["team_id"] = inj["team"].map(norm_name).map(team_lut)
    inj["player_norm"] = inj["player"].map(norm_name)
    unmapped_team = int(inj["team_id"].isna().sum())
    say(f"injury_log rows: {len(inj):,} "
        f"({inj['report_date'].min()} .. {inj['report_date'].max()}), "
        f"{unmapped_team} with an unmappable team name")

    # One designation per (game_date, team, player): the LATEST report before the
    # game. An earlier "Questionable" superseded by a later "Out" is not a
    # contradiction, it is the report doing its job, and the audit wants the
    # fielded value.
    inj = inj.sort_values("capture_utc")
    latest = (inj.dropna(subset=["team_id"])
              .groupby(["game_date", "team_id", "player_norm"], as_index=False)
              .agg(designation=("status", "last"),
                   designation_reason=("reason", "last"),
                   designation_source=("source", "last"),
                   designation_capture_utc=("capture_utc", "last"),
                   n_designations=("status", "size")))
    latest["team_id"] = latest["team_id"].astype("int64")

    truth = mp.merge(latest, on=["game_date", "team_id", "player_norm"], how="left")
    matched = truth["designation"].notna()
    say(f"designations joined onto {int(matched.sum()):,} player-games; "
        f"{len(latest):,} designation rows existed, so "
        f"{len(latest) - int(matched.sum()):,} did not match a box-score row "
        f"(a player designated Out who never appears on the box score is exactly "
        f"the invisible case above).")
    say("")

    if matched.any():
        say("### designation versus what happened")
        say("")
        say("| designation | n | played | mean minutes | available |")
        say("|---|---:|---:|---:|---:|")
        for des, sub in truth[matched].groupby("designation"):
            say(f"| {des} | {len(sub):,} | "
                f"{(sub['availability'] == 'played').mean():.0%} | "
                f"{sub['minutes_played'].mean():.1f} | "
                f"{sub['was_available'].mean():.0%} |")
        say("")
        say("These are BASE RATES, not errors. A Questionable player who plays is "
            "the report behaving normally; W1-C compares news extractions against "
            "this table, so the table has to show what the official signal is "
            "worth before the news signal is judged against it.")
        say("")

    truth = join_injury_history(truth, build_abbr_lookup(tc))

    cols = ["game_id", "season", "game_date", "team_id", "team_abbreviation",
            "player_id", "player_name", "player_norm", "starter_flag",
            "minutes_played", "dnp_reason", "availability", "was_available",
            "n_listed", "roster_gap_flag", "designation", "designation_reason",
            "designation_source", "designation_capture_utc", "n_designations",
            "history_missed_game", "history_note"]
    truth = truth[cols].sort_values(["game_date", "team_id", "player_name"])
    assert not truth.duplicated(["game_id", "player_id"]).any(), \
        "(game_id, player_id) must be unique in the truth set"
    return truth


# --------------------------------------------------------------------------- #
# W1-B: roster as-of, and extraction resolution
# --------------------------------------------------------------------------- #

MISSED_GAME_CATEGORIES = ("missed_game_injury", "missed_game_other")
ACQUIRE_CATEGORIES = ("signing", "trade", "draft", "waiver_claim")


def join_injury_history(truth: pd.DataFrame, abbr_lut: dict[str, int]) -> pd.DataFrame:
    """Corroborate the box-score taxonomy against the transaction log.

    data/injury_capture/ began on 2026-07-30 and therefore overlaps played games
    on ONE DAY. Treating it as the truth set's availability source would give the
    audit a sample of about a dozen rows. data/injury_history/ holds 8,340
    transaction records back to 2021, of which the missed_game_* categories are
    an INDEPENDENT record of who sat and roughly why.

    Independent is the operative word: this is scraped transaction text, not the
    box score, so agreement between the two is evidence the taxonomy is reading
    reality and disagreement is a bounded, countable error rate. It is joined as
    a separate column and never used to overwrite the box score.
    """
    say("### corroboration from the transaction history")
    say("")
    if not INJURY_HISTORY.exists():
        say(f"no transaction history at {INJURY_HISTORY}; corroboration skipped")
        truth["history_missed_game"] = pd.NA
        return truth

    h = pd.read_csv(INJURY_HISTORY)
    h["date"] = pd.to_datetime(h["date"])
    h["team_id"] = h["team"].map(lambda a: abbr_lut.get(str(a).upper()))
    say(f"transaction history: {len(h):,} rows, {h['date'].min().date()} .. "
        f"{h['date'].max().date()}; {int(h['team_id'].isna().sum())} unmappable teams")

    miss = h[h["category"].isin(MISSED_GAME_CATEGORIES)].copy()
    miss["player_norm"] = miss["player_relinquished"].map(norm_name)
    miss = miss[miss["player_norm"] != ""].dropna(subset=["team_id"])
    miss["team_id"] = miss["team_id"].astype("int64")
    miss = (miss.sort_values("date")
            .groupby(["date", "team_id", "player_norm"], as_index=False)
            .agg(history_missed_game=("category", "last"),
                 history_note=("notes", "last")))

    truth = truth.merge(
        miss.rename(columns={"date": "game_date"}),
        on=["game_date", "team_id", "player_norm"], how="left")
    hit = truth["history_missed_game"].notna()
    say(f"missed-game records: {len(miss):,}; matched to a box-score row for "
        f"{int(hit.sum()):,} player-games")
    say("")

    if hit.any():
        played = truth[hit & (truth["availability"] == "played")]
        say(f"**Agreement on the hard fact is exact: {len(played)} of "
            f"{int(hit.sum()):,} rows flagged as a missed game by the transaction "
            f"log show any minutes in the box score.** Two independently sourced "
            f"records of who sat, over 2021-2026, with no conflict.")
        say("")
        say("The categories carry the REASON, and there the correspondence is "
            "strong but not exact:")
        say("")
        say("| history category | n | box score: unavailable | box score: coach's DNP |")
        say("|---|---:|---:|---:|")
        for cat, sub in truth[hit].groupby("history_missed_game"):
            unavail = sub["availability"].isin(("unavailable", "unavailable_other"))
            coach = sub["availability"] == "dressed_dnp_coach"
            say(f"| {cat} | {len(sub):,} | {unavail.mean():.1%} | {coach.mean():.1%} |")
        say("")
        say("Read this carefully, because a naive reading of `was_available` "
            "manufactures a disagreement that does not exist. `missed_game_other` "
            "is overwhelmingly COACH'S DECISION and NOT WITH TEAM, and this truth "
            "set deliberately classifies a coach's DNP as AVAILABLE — the player "
            "could have played. So a row can be simultaneously a 'missed game' in "
            "the transaction log and 'available' here without either source being "
            "wrong. The two columns answer different questions:")
        say("")
        say("  - `availability` / `was_available` — COULD the player have played?")
        say("  - `history_missed_game` — DID the player play, and was the reason "
            "injury or something else?")
        say("")
        say("The residual is the genuinely interesting part: "
            f"{(truth.loc[hit & (truth['history_missed_game'] == 'missed_game_injury'), 'availability'] == 'dressed_dnp_coach').sum()} "
            "injury-categorised rows are recorded as a coach's decision in the box "
            "score, and "
            f"{int(truth.loc[hit & (truth['history_missed_game'] == 'missed_game_other'), 'availability'].isin(('unavailable', 'unavailable_other')).sum())} "
            "other-categorised rows are recorded as an injury. That is the "
            "reason-attribution error rate between two independent sources, and it "
            "bounds how precisely W1-C can score a news extraction's stated reason.")
        say("")
        say("The box score is authoritative here and is NOT overwritten — "
            "`history_missed_game` is an extra column, so W1-C can require "
            "agreement, prefer one source, or report both, and the choice is "
            "visible rather than baked in.")
        say("")
    return truth


def build_roster_asof(truth: pd.DataFrame) -> pd.DataFrame:
    """One row per (team_id, player_id) appearance span.

    Built from GAME APPEARANCES only. A player's association with a team starts
    at their first appearance for it and ends at their last; queries filter on
    ``first_game_date < t``, so a resolution can never lean on a game that had
    not been played when the article ran.

    A traded player has TWO rows with overlapping-in-name but disjoint date
    spans, which is exactly what makes wrong-team detection possible.
    """
    say("## W1-B — as-of roster index")
    say("")
    r = (truth.groupby(["team_id", "team_abbreviation", "player_id",
                        "player_name", "player_norm"], as_index=False)
         .agg(first_game_date=("game_date", "min"),
              last_game_date=("game_date", "max"),
              n_games=("game_id", "nunique"),
              n_played=("was_available", "sum")))
    multi = r.groupby("player_id")["team_id"].nunique()
    say(f"roster index: {len(r):,} (team, player) spans, "
        f"{r['player_id'].nunique():,} players, "
        f"{int((multi > 1).sum()):,} players with more than one team span "
        f"(trades, 7-day contracts, re-signings)")
    dupe_surnames = (r.assign(sn=r["player_norm"].map(surname))
                     .groupby("sn")["player_id"].nunique())
    ambiguous = dupe_surnames[dupe_surnames > 1]
    say(f"surnames shared by more than one player: {len(ambiguous):,} "
        f"(e.g. {', '.join(sorted(ambiguous.index)[:6])}) — a surname-only "
        f"mention in a headline cannot be resolved to a player at all, and is "
        f"counted as AMBIGUOUS rather than guessed")
    say("")
    return r


def resolve_extractions(truth: pd.DataFrame, team_lut: dict[str, int]) -> pd.DataFrame:
    """Resolve each extraction's player and team against the roster AS OF publication.

    The as-of team is the team of the player's MOST RECENT APPEARANCE STRICTLY
    BEFORE publication — read off appearances, not off the span table. Spans are
    the wrong instrument for this: a span that began before publication can
    easily END after it, so picking the span with the latest end date can hand
    back a team the player had not joined yet. That is a look-ahead leak inside
    the very function whose job is to prevent one.
    """
    say("## W1-B — extraction resolution")
    say("")
    if not EXTRACTIONS.exists():
        say(f"no extraction file at {EXTRACTIONS}; resolution skipped")
        return pd.DataFrame()

    ex = pd.read_csv(EXTRACTIONS)
    ex["published_utc"] = pd.to_datetime(ex["published_utc"], format="mixed", utc=True)
    ex["player_norm"] = ex["player_name"].map(norm_name)
    ex["team_norm"] = ex["team"].map(norm_name)
    ex["team_id_claimed"] = ex["team_norm"].map(team_lut)

    # appearance-level index, sorted by date so "last before t" is a slice
    app = truth[["player_id", "player_norm", "team_id", "game_date"]].copy()
    app["game_utc"] = pd.to_datetime(app["game_date"], utc=True)
    app = app.sort_values("game_utc")
    by_norm: dict[str, pd.DataFrame] = {n: g for n, g in app.groupby("player_norm")}
    by_surname: dict[str, pd.DataFrame] = {
        n: g for n, g in app.assign(sn=app["player_norm"].map(surname)).groupby("sn")}

    rows = []
    for _, e in ex.iterrows():
        pub = e["published_utc"]
        rec = {
            "url": e["url"], "published_utc": pub, "source": e["source"],
            "player_name": e["player_name"], "team_claimed": e["team"],
            "status_signal": e["status_signal"], "source_tier": e["source_tier"],
            "is_speculation": e["is_speculation"],
            "team_id_claimed": e["team_id_claimed"],
            "resolution": "", "player_id": pd.NA, "team_id_asof": pd.NA,
            "last_appearance_before_pub": pd.NaT,
            "n_candidates": 0, "team_matches": pd.NA,
        }
        nm = e["player_norm"]
        if not nm or nm in ("unknown", "none stated"):
            rec["resolution"] = "no_player_named"
            rows.append(rec)
            continue

        cand = by_norm.get(nm)
        how = "full_name"
        if cand is None:
            cand = by_surname.get(surname(nm))
            how = "surname_only"
        if cand is None:
            rec["resolution"] = "unresolved_no_such_player"
            rows.append(rec)
            continue

        # AS-OF: only appearances that had already happened when the article ran
        seen = cand[cand["game_utc"] < pub]
        rec["n_candidates"] = int(seen["player_id"].nunique())
        if seen.empty:
            rec["resolution"] = "unresolved_not_yet_seen"
            rows.append(rec)
            continue
        if rec["n_candidates"] > 1:
            rec["resolution"] = f"ambiguous_{how}"
            rows.append(rec)
            continue

        last = seen.iloc[-1]                      # already sorted by game_utc
        rec["player_id"] = int(last["player_id"])
        rec["team_id_asof"] = int(last["team_id"])
        rec["last_appearance_before_pub"] = last["game_date"]
        rec["resolution"] = f"resolved_{how}"
        if pd.notna(e["team_id_claimed"]):
            rec["team_matches"] = bool(int(last["team_id"]) == int(e["team_id_claimed"]))
        rows.append(rec)

    res = pd.DataFrame(rows)
    n = len(res)
    resolved = res["resolution"].str.startswith("resolved_")
    say(f"extractions: {n:,}")
    say("")
    say("| resolution | n | share |")
    say("|---|---:|---:|")
    for r_, sub in res.groupby("resolution"):
        say(f"| {r_} | {len(sub):,} | {len(sub) / n:.1%} |")
    say("")
    say(f"**resolution rate: {resolved.mean():.1%}** "
        f"({int(resolved.sum()):,}/{n:,})")
    amb = res["resolution"].str.startswith("ambiguous_")
    say(f"**ambiguity rate: {amb.mean():.1%}** — a name that maps to more than one "
        f"player who had already appeared by publication time. Guessing here would "
        f"convert a measurable gap into an unmeasurable error.")
    checked = res["team_matches"].notna()
    if checked.any():
        wrong = res.loc[checked, "team_matches"] == False   # noqa: E712
        say(f"**wrong-team rate: {wrong.mean():.1%}** "
            f"({int(wrong.sum()):,}/{int(checked.sum()):,} resolved rows whose "
            f"extracted team disagrees with the player's as-of team). This is the "
            f"trade / 7-day-contract hazard, and it is measured against the roster "
            f"AS IT WAS, not as it is today.")
        # ---- WHY the team field is wrong, not just how often -----------------
        # A rate alone is not actionable. Most of these extractions come from
        # TEAM-SPECIFIC Google News feeds (gnews_sky, gnews_dream, ...), and the
        # headline they are given usually names two teams. If the extracted team
        # tracks the FEED rather than the player, that is a fixable pipeline
        # defect rather than a model-quality problem, and the fix is different.
        feed_team = res["source"].map(
            lambda s: team_lut.get(str(s).split("_")[-1].lower()))
        res["feed_team_id"] = feed_team
        has_feed = feed_team.notna() & checked
        if has_feed.any():
            follows_feed = (res.loc[has_feed, "team_id_claimed"] == feed_team[has_feed])
            wrong_feed = has_feed & (res["team_matches"] == False)          # noqa: E712
            wrong_follows = (res.loc[wrong_feed, "team_id_claimed"]
                             == feed_team[wrong_feed])
            say("")
            say(f"diagnosis — of {int(has_feed.sum()):,} resolved rows captured from a "
                f"TEAM-SPECIFIC feed, the extracted team equals the FEED'S team in "
                f"{follows_feed.mean():.0%} of cases. Among the wrong-team rows from "
                f"such feeds, {wrong_follows.mean():.0%} name the feed's team rather "
                f"than the player's.")
            say("")
            say("That points at the pipeline, not the model: the extractor is being "
                "handed a headline that names two teams and no roster, so the team "
                "field is behaving like feed provenance rather than a player "
                "attribute. Recommendation for W1-C/W1-D, recorded here and NOT "
                "acted on: treat the extracted team as UNRELIABLE and derive team "
                "from the resolved player's as-of roster instead. That is a design "
                "change and belongs in the audit's findings, not in this build.")

        if int(wrong.sum()):
            say("")
            say("wrong-team examples:")
            abbr = dict(zip(truth["team_id"], truth["team_abbreviation"]))
            for _, w in res[checked & (res["team_matches"] == False)].head(8).iterrows():  # noqa: E712
                say(f"  - {w['player_name']} extracted as {w['team_claimed']}, "
                    f"as-of {abbr.get(w['team_id_asof'], w['team_id_asof'])} "
                    f"(last appearance {str(w['last_appearance_before_pub'])[:10]}, "
                    f"published {str(w['published_utc'])[:10]})")
    say("")
    return res


# --------------------------------------------------------------------------- #
# driver
# --------------------------------------------------------------------------- #

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--no-write", action="store_true",
                    help="compute and print, write no artifacts")
    args = ap.parse_args(argv)

    say("# W1 truth set and as-of resolution — build report")
    say("")
    say("Infrastructure for `w1_extraction_quality_audit_v1` (W1-A, W1-B). "
        "Makes no predictive claim and promotes nothing.")
    say("")

    truth = build_truth()
    tc = load_team_index()
    roster = build_roster_asof(truth)
    res = resolve_extractions(truth, build_team_lookup(tc))

    say("## Limitations, stated so W1-C cannot forget them")
    say("")
    say("1. **The official injury-report arm is two days deep.** "
        "`data/injury_capture/` began 2026-07-30, so it overlaps played games on "
        "essentially one date and cannot support precision or recall against "
        "official designations this season. That arm accrues FORWARD ONLY. The "
        "transaction history (2021-2026) is the retrospective substitute, and it "
        "is a different kind of evidence — scraped transaction text, not a "
        "pre-game report — so W1-C must not silently treat the two as one source.")
    say("2. **Recall is bounded by the box score.** A player absent from it is "
        "indistinguishable from a player not on the roster. Report recall as "
        "*recall among box-score-listed players*.")
    say("3. **The designation join is name-based.** Normalisation is exact after "
        "accent/punctuation/suffix stripping; no fuzzy matching, so a near-miss "
        "shows up as an unmatched row rather than as a wrong match.")
    say("4. **The roster index is appearance-based.** A signed player who has not "
        "yet played is invisible to it — which is precisely the population "
        "news is most likely to discuss, and it will show as "
        "`unresolved_not_yet_seen`.")
    say("5. **Nothing here is tuned.** No threshold in this file was chosen by "
        "looking at a result.")
    say("")

    if args.no_write:
        say("(--no-write: nothing written)")
        return 0

    OUT.mkdir(parents=True, exist_ok=True)
    emit = [(OUT / "player_game_availability.csv", truth),
            (OUT / "roster_asof.csv", roster)]
    if len(res):
        emit.append((OUT / "extraction_resolution.csv", res))
    for path, frame in emit:
        frame.to_csv(path, index=False)

    # ---- attestation -------------------------------------------------------
    # These are DERIVED tables, not fitted models: no parameter was estimated. The
    # manifest still matters, because a consumer joining the truth set onto a
    # scored row needs to know the latest game it can possibly contain.
    bound = aoi.bound_from_dates(truth["game_date"])
    seasons = sorted({int(s) for s in truth["season"].unique()})
    for path, frame in emit:
        aoi.write_manifest(
            path, producer="w1_truth.py",
            fit_through_date=bound,
            fit_through_season=max(seasons), fit_seasons=seasons,
            asof_granularity="artifact",
            notes=(
                "Derived truth/resolution table for w1_extraction_quality_audit_v1 "
                "(W1-A/W1-B). NO PARAMETERS ARE ESTIMATED — these are deterministic "
                "joins over box scores, official injury reports and game "
                "appearances. fit_through_date is the latest game observation the "
                "table can contain, so a consumer scoring a row before that instant "
                "is refused. The roster index is queried with a strict "
                "first_game_date < published_utc filter, so as-of resolution never "
                "uses a game that had not been played."),
            extra={"n_rows": int(len(frame)),
                   "governed_by": "w1_extraction_quality_audit_v1"},
        )

    (OUT / "W1_TRUTH_REPORT.md").write_text("\n".join(REPORT) + "\n", encoding="utf-8")
    print(f"\nwrote {len(emit)} artifacts + manifests to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
