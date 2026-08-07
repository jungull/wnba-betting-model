"""
M16_RELATED_MARKET_COHERENCE - Step 2/3: build the working universe of joint
(h2h, spreads, totals) quotes from the same book at the same capture instant,
and test the coherence relations declared in COHERENCE_MODELS (see docstrings
below and REPORT_BODY.md for the prose version).

Data source: data/market_snapshots/historical/featured_backfill.jsonl only.
(snapshots.csv, the live ladder, was inventoried in inventory.py and contains
ZERO h2h/spreads/totals rows as of this run -- see inventory.json and
REPORT_BODY.md for the measured poll_log.csv evidence. It cannot supply this
node's working universe.)

No timing / reaction-time / CLV claim is made anywhere in this script. All
relations are cross-sectional: they compare quotes captured in the SAME poll
batch (same `requested_ts`, which is a timestamp WE issued the request at --
not a vendor-asserted event time). Time-to-tip bucketing uses `commence_time
- requested_ts`, which is a scheduling fact (how far before a known future
tipoff we polled), not an inferred reaction latency.

stdlib only (scipy/pandas/numpy not installed in this environment).
"""
import json
import math
import statistics
from collections import defaultdict, Counter
from datetime import datetime, timezone
from pathlib import Path

DATA_ROOT = Path(r"C:\Users\jgallagher\wnba-betting-model\data\market_snapshots")
FEATURED_JSONL = DATA_ROOT / "historical" / "featured_backfill.jsonl"
OUT_DIR = Path(__file__).parent

NORMAL = statistics.NormalDist()


def american_to_prob(price):
    price = float(price)
    if price < 0:
        return (-price) / (-price + 100.0)
    else:
        return 100.0 / (price + 100.0)


def parse_ts(s):
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


records = []  # one row per (event, book, requested_ts) triple instant
naming_mismatches = 0
n_bookmaker_triples_seen = 0
n_devig_zero_denominator = 0

with open(FEATURED_JSONL, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        requested_ts = rec.get("requested_ts")
        req_dt = parse_ts(requested_ts)
        for ev in rec.get("payload") or []:
            event_id = ev.get("id")
            home_team = ev.get("home_team")
            away_team = ev.get("away_team")
            commence_time = ev.get("commence_time")
            commence_dt = parse_ts(commence_time)
            for bm in ev.get("bookmakers", []):
                book = bm.get("key")
                mkts = {m.get("key"): m for m in bm.get("markets", [])}
                if not ({"h2h", "spreads", "totals"} <= set(mkts.keys())):
                    continue
                n_bookmaker_triples_seen += 1
                h2h = mkts["h2h"]
                spreads = mkts["spreads"]
                totals = mkts["totals"]

                h2h_out = {o["name"]: o.get("price") for o in h2h.get("outcomes", [])}
                spr_out = {o["name"]: (o.get("price"), o.get("point")) for o in spreads.get("outcomes", [])}
                tot_out = {o["name"]: (o.get("price"), o.get("point")) for o in totals.get("outcomes", [])}

                # naming sanity: h2h/spreads outcome names should be home/away team names
                names_ok = (
                    set(h2h_out.keys()) <= {home_team, away_team}
                    and set(spr_out.keys()) <= {home_team, away_team}
                    and home_team in h2h_out and away_team in h2h_out
                    and home_team in spr_out and away_team in spr_out
                )
                if not names_ok:
                    naming_mismatches += 1
                    continue

                # --- moneyline de-vig ---
                p_home_raw = american_to_prob(h2h_out[home_team])
                p_away_raw = american_to_prob(h2h_out[away_team])
                denom = p_home_raw + p_away_raw
                if denom <= 0:
                    n_devig_zero_denominator += 1
                    continue
                p_home_nv = p_home_raw / denom
                p_away_nv = p_away_raw / denom
                overround_h2h = denom - 1.0

                # --- spread favorite ---
                home_pt = spr_out[home_team][1]
                away_pt = spr_out[away_team][1]
                if home_pt is None or away_pt is None:
                    continue
                spread_fav_is_home = home_pt < away_pt  # favorite carries the negative number
                mu = abs(home_pt) if spread_fav_is_home else abs(away_pt)
                p_spr_home_raw = american_to_prob(spr_out[home_team][0]) if spr_out[home_team][0] is not None else None
                p_spr_away_raw = american_to_prob(spr_out[away_team][0]) if spr_out[away_team][0] is not None else None
                overround_spread = None
                if p_spr_home_raw is not None and p_spr_away_raw is not None:
                    overround_spread = p_spr_home_raw + p_spr_away_raw - 1.0

                # --- totals ---
                over_price, over_pt = tot_out.get("Over", (None, None))
                under_price, under_pt = tot_out.get("Under", (None, None))
                T = over_pt if over_pt is not None else under_pt
                overround_total = None
                p_over_nv = None
                if over_price is not None and under_price is not None:
                    p_over_raw = american_to_prob(over_price)
                    p_under_raw = american_to_prob(under_price)
                    denom_t = p_over_raw + p_under_raw
                    if denom_t > 0:
                        p_over_nv = p_over_raw / denom_t
                        overround_total = denom_t - 1.0

                ml_fav_is_home = p_home_nv > p_away_nv
                p_fav_ml = p_home_nv if ml_fav_is_home else p_away_nv

                sign_coherent = (ml_fav_is_home == spread_fav_is_home)

                lu_h2h = parse_ts(h2h.get("last_update"))
                lu_spr = parse_ts(spreads.get("last_update"))
                lu_tot = parse_ts(totals.get("last_update"))
                lus = [x for x in (lu_h2h, lu_spr, lu_tot) if x is not None]
                latency_window_s = (max(lus) - min(lus)).total_seconds() if len(lus) >= 2 else 0.0

                hours_to_tip = None
                if commence_dt is not None and req_dt is not None:
                    hours_to_tip = (commence_dt - req_dt).total_seconds() / 3600.0

                records.append(dict(
                    event_id=event_id, book=book, requested_ts=requested_ts,
                    home_team=home_team, away_team=away_team, commence_time=commence_time,
                    hours_to_tip=hours_to_tip,
                    p_home_nv=p_home_nv, p_away_nv=p_away_nv, overround_h2h=overround_h2h,
                    spread_fav_is_home=spread_fav_is_home, mu=mu, overround_spread=overround_spread,
                    T=T, p_over_nv=p_over_nv, overround_total=overround_total,
                    ml_fav_is_home=ml_fav_is_home, p_fav_ml=p_fav_ml, sign_coherent=sign_coherent,
                    capture_timestamps=dict(
                        h2h_last_update=h2h.get("last_update"),
                        spreads_last_update=spreads.get("last_update"),
                        totals_last_update=totals.get("last_update"),
                        batch_requested_ts=requested_ts,
                    ),
                    cross_quote_latency_window_seconds=latency_window_s,
                ))

print(f"n_bookmaker_triples_seen={n_bookmaker_triples_seen}")
print(f"n_records_built={len(records)}")
print(f"naming_mismatches_dropped={naming_mismatches}")
print(f"devig_zero_denominator_dropped={n_devig_zero_denominator}")

# =============================================================================
# Relation A: favorite-sign coherence (model-free identity)
#   Coherent  <=>  argmax_team(p_home_nv, p_away_nv) == team with the negative
#                  (favorite) spread point, for the SAME book at the SAME poll.
#   Violation <=>  the moneyline favorite and the spread favorite disagree.
# =============================================================================
n_A = len(records)
n_A_coherent = sum(1 for r in records if r["sign_coherent"])
n_A_violation = n_A - n_A_coherent
# IMPORTANT: a strict argmax(p_home_nv, p_away_nv) tie-break mislabels an exact
# moneyline pick'em (p_home_nv == p_away_nv, typically from symmetric -110/-110
# pricing) as "away favored" -- if the spread simultaneously favors home by a
# small margin, that reads as a sign flip even though the moneyline expresses
# NO favorite at all. This was caught by inspecting the violation sample (most
# had p_home_nv == p_away_nv == 0.5 exactly). Split violations into genuine
# disagreements (moneyline has a real favorite that differs from the spread's)
# vs tie-artifacts (moneyline is an exact pick'em).
n_A_tie_artifact = sum(1 for r in records if not r["sign_coherent"] and r["p_home_nv"] == r["p_away_nv"])
n_A_genuine_violation = n_A_violation - n_A_tie_artifact
violations_by_book = Counter(r["book"] for r in records if not r["sign_coherent"])
genuine_violations_by_book = Counter(r["book"] for r in records if not r["sign_coherent"] and r["p_home_nv"] != r["p_away_nv"])
n_by_book = Counter(r["book"] for r in records)
violation_rate_by_book = {b: violations_by_book[b] / n_by_book[b] for b in n_by_book if n_by_book[b] >= 20}
genuine_violation_rate_by_book = {b: genuine_violations_by_book.get(b, 0) / n_by_book[b] for b in n_by_book if n_by_book[b] >= 20}

relation_A = dict(
    name="favorite_sign_coherence",
    assumed_model="NONE (model-free ordinal identity: moneyline favorite team must equal spread favorite team)",
    inequality="team(argmax(p_home_nv, p_away_nv)) == team(argmin(spread_point))",
    N=n_A,
    n_coherent=n_A_coherent,
    n_violation_raw_incl_tie_artifacts=n_A_violation,
    n_violation_tie_artifacts_moneyline_exact_pickem=n_A_tie_artifact,
    n_violation_genuine_favorite_disagreement=n_A_genuine_violation,
    violation_rate_raw=n_A_violation / n_A if n_A else None,
    violation_rate_genuine=n_A_genuine_violation / n_A if n_A else None,
    violation_rate_by_book_min20_raw=violation_rate_by_book,
    violation_rate_by_book_min20_genuine=genuine_violation_rate_by_book,
    note="n_violation_raw includes moneyline exact-pickem cases (p_home_nv==p_away_nv, i.e. no moneyline favorite exists to compare) mechanically mislabeled as disagreements by the argmax tie-break. n_violation_genuine excludes those. See REPORT_BODY.md.",
)

# =============================================================================
# Relation B: normal-margin model cross-check between moneyline and spread
#   MODEL M1 (explicitly assumed, not derived from outcomes):
#     final-game margin (favorite - underdog) ~ Normal(mu, sigma)
#     mu := the book's own posted spread magnitude for the favorite (the
#           standard spread-setting identification: the line is posted at the
#           value that makes both sides equally likely to cover, i.e. mu is
#           identified with the mean/median of a symmetric margin distribution)
#     => model-implied P(favorite wins) = Phi(mu / sigma)
#   sigma is NOT assumed a priori. It is estimated FROM THIS ARCHIVE ONLY
#   (self-calibrated, not sourced from any external season-outcome dataset)
#   as sigma_hat = median( mu_i / Phi^-1(p_fav_ml,i) ) over all sign-coherent
#   instances with p_fav_ml in (0.5, 1.0) and mu > 0.
#   Coherence requires |p_fav_ml,i - Phi(mu_i / sigma_hat)| <= epsilon.
#   epsilon is NOT asserted as a validated noise floor -- exceedance is
#   reported at multiple epsilon so the reader can judge.
# =============================================================================
implied_sigmas = []
for r in records:
    if not r["sign_coherent"]:
        continue
    p = r["p_fav_ml"]
    mu = r["mu"]
    if mu is None or mu <= 0 or p is None or not (0.5 < p < 1.0):
        continue
    z = NORMAL.inv_cdf(p)
    if z <= 0:
        continue
    implied_sigmas.append(mu / z)

sigma_hat = statistics.median(implied_sigmas) if implied_sigmas else None
sigma_mean = statistics.mean(implied_sigmas) if implied_sigmas else None
sigma_stdev = statistics.stdev(implied_sigmas) if len(implied_sigmas) > 1 else None

incoherence_B = []
for r in records:
    if not r["sign_coherent"]:
        continue
    mu = r["mu"]
    p_actual = r["p_fav_ml"]
    if mu is None or mu <= 0 or p_actual is None or sigma_hat is None:
        continue
    p_model = NORMAL.cdf(mu / sigma_hat)
    incoherence_B.append(dict(diff=p_actual - p_model, abs_diff=abs(p_actual - p_model),
                               book=r["book"], hours_to_tip=r["hours_to_tip"], T=r["T"]))

abs_diffs_B = sorted(x["abs_diff"] for x in incoherence_B)


def quantile(sorted_list, q):
    if not sorted_list:
        return None
    n = len(sorted_list)
    idx = min(n - 1, max(0, int(round(q * (n - 1)))))
    return sorted_list[idx]


def exceed_rate(sorted_list, thresh):
    if not sorted_list:
        return None
    return sum(1 for x in sorted_list if x > thresh) / len(sorted_list)


relation_B = dict(
    name="normal_margin_moneyline_spread_coherence",
    assumed_model=(
        "Margin ~ Normal(mu=spread_magnitude, sigma); model P(fav wins)=Phi(mu/sigma); "
        "sigma self-calibrated as median(mu_i / Phi^-1(p_fav_ml,i)) over this archive "
        "(not sourced from realized outcomes or any external dataset)."
    ),
    inequality="abs(p_fav_ml - Phi(mu / sigma_hat)) <= epsilon  [reported at multiple epsilon, none validated as a noise floor]",
    N_used_for_sigma_calibration=len(implied_sigmas),
    sigma_hat_median_points=sigma_hat,
    sigma_mean_points=sigma_mean,
    sigma_stdev_points=sigma_stdev,
    N_tested=len(incoherence_B),
    abs_diff_mean=statistics.mean(abs_diffs_B) if abs_diffs_B else None,
    abs_diff_median=quantile(abs_diffs_B, 0.5),
    abs_diff_p10=quantile(abs_diffs_B, 0.10),
    abs_diff_p90=quantile(abs_diffs_B, 0.90),
    abs_diff_p95=quantile(abs_diffs_B, 0.95),
    abs_diff_p99=quantile(abs_diffs_B, 0.99),
    abs_diff_max=abs_diffs_B[-1] if abs_diffs_B else None,
    exceed_rate_gt_0_02=exceed_rate(abs_diffs_B, 0.02),
    exceed_rate_gt_0_05=exceed_rate(abs_diffs_B, 0.05),
    exceed_rate_gt_0_10=exceed_rate(abs_diffs_B, 0.10),
)

# by-book breakdown (books with >=100 tested instances)
by_book_B = defaultdict(list)
for x in incoherence_B:
    by_book_B[x["book"]].append(x["abs_diff"])
relation_B_by_book = {
    b: dict(N=len(v), median_abs_diff=statistics.median(v), mean_abs_diff=statistics.mean(v))
    for b, v in by_book_B.items() if len(v) >= 100
}

# by-hours-to-tip bucket
def tip_bucket(h):
    if h is None:
        return "unknown"
    if h < 0:
        return "post_commence_or_live"
    if h < 1:
        return "0-1h"
    if h < 4:
        return "1-4h"
    if h < 12:
        return "4-12h"
    if h < 24:
        return "12-24h"
    return "24h+"

by_tip_B = defaultdict(list)
for x in incoherence_B:
    by_tip_B[tip_bucket(x["hours_to_tip"])].append(x["abs_diff"])
relation_B_by_tip_bucket = {
    k: dict(N=len(v), median_abs_diff=statistics.median(v), mean_abs_diff=statistics.mean(v))
    for k, v in by_tip_B.items()
}

# =============================================================================
# Relation B-prime: sigma as a linear function of the total T (sensitivity
# check -- does allowing implied variance to scale with the book's own total
# change the coherence picture?). Simple closed-form OLS, stdlib only.
# =============================================================================
pairs = []
for r in records:
    if not r["sign_coherent"]:
        continue
    p = r["p_fav_ml"]
    mu = r["mu"]
    T = r["T"]
    if mu is None or mu <= 0 or p is None or not (0.5 < p < 1.0) or T is None:
        continue
    z = NORMAL.inv_cdf(p)
    if z <= 0:
        continue
    implied_sigma_i = mu / z
    pairs.append((T, implied_sigma_i))

if len(pairs) >= 10:
    n_p = len(pairs)
    mean_T = sum(t for t, s in pairs) / n_p
    mean_S = sum(s for t, s in pairs) / n_p
    cov = sum((t - mean_T) * (s - mean_S) for t, s in pairs)
    var_T = sum((t - mean_T) ** 2 for t, s in pairs)
    b1 = cov / var_T if var_T > 0 else 0.0
    b0 = mean_S - b1 * mean_T
else:
    b0, b1 = sigma_hat, 0.0

incoherence_Bp = []
for r in records:
    if not r["sign_coherent"]:
        continue
    mu = r["mu"]
    p_actual = r["p_fav_ml"]
    T = r["T"]
    if mu is None or mu <= 0 or p_actual is None or T is None:
        continue
    sigma_T = b0 + b1 * T
    if sigma_T <= 0:
        continue
    p_model = NORMAL.cdf(mu / sigma_T)
    incoherence_Bp.append(abs(p_actual - p_model))

incoherence_Bp.sort()
relation_Bprime = dict(
    name="normal_margin_moneyline_spread_coherence_sigma_scales_with_total",
    assumed_model=f"sigma(T) = {b0:.4f} + {b1:.6f}*T, OLS-fit to (T, implied_sigma) pairs from this archive only",
    N_fit_pairs=len(pairs),
    fit_intercept_b0=b0,
    fit_slope_b1_per_point_of_total=b1,
    N_tested=len(incoherence_Bp),
    abs_diff_mean=statistics.mean(incoherence_Bp) if incoherence_Bp else None,
    abs_diff_median=quantile(incoherence_Bp, 0.5),
    abs_diff_p95=quantile(incoherence_Bp, 0.95),
    exceed_rate_gt_0_05=exceed_rate(incoherence_Bp, 0.05),
    note="Sensitivity check only. If b1 is near 0 and the exceedance profile matches relation_B, the constant-sigma model is not being rescued or contradicted by pace/total information.",
)

# =============================================================================
# Relation C: own-book cross-market vig (overround) consistency -- DESCRIPTIVE,
# not a pass/fail no-arbitrage test (there is no first-principles requirement
# that a book charge the same vig on h2h vs spreads vs totals).
# =============================================================================
ov_h2h = [r["overround_h2h"] for r in records if r["overround_h2h"] is not None]
ov_spr = [r["overround_spread"] for r in records if r["overround_spread"] is not None]
ov_tot = [r["overround_total"] for r in records if r["overround_total"] is not None]

def describe(vals):
    if not vals:
        return None
    s = sorted(vals)
    return dict(N=len(s), mean=statistics.mean(s), median=statistics.median(s),
                stdev=statistics.stdev(s) if len(s) > 1 else 0.0,
                p05=quantile(s, 0.05), p95=quantile(s, 0.95), min=s[0], max=s[-1])

triples_all3 = [(r["overround_h2h"], r["overround_spread"], r["overround_total"])
                for r in records
                if r["overround_h2h"] is not None and r["overround_spread"] is not None and r["overround_total"] is not None]

def pearson(xs, ys):
    n = len(xs)
    if n < 2:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx <= 0 or vy <= 0:
        return None
    return cov / math.sqrt(vx * vy)

corr_h2h_spr = pearson([t[0] for t in triples_all3], [t[1] for t in triples_all3])
corr_h2h_tot = pearson([t[0] for t in triples_all3], [t[2] for t in triples_all3])
corr_spr_tot = pearson([t[1] for t in triples_all3], [t[2] for t in triples_all3])

relation_C = dict(
    name="cross_market_vig_consistency",
    assumed_model="DESCRIPTIVE ONLY -- no inequality asserted as a violation criterion; a book is free to price different market types with different overround.",
    overround_h2h=describe(ov_h2h),
    overround_spread=describe(ov_spr),
    overround_total=describe(ov_tot),
    N_triples_with_all_3_overrounds=len(triples_all3),
    pearson_corr_overround_h2h_vs_spread=corr_h2h_spr,
    pearson_corr_overround_h2h_vs_total=corr_h2h_tot,
    pearson_corr_overround_spread_vs_total=corr_spr_tot,
)

# =============================================================================
# Relation D: cross-book dispersion at the SAME (event_id, requested_ts) instant.
# DESCRIPTIVE dispersion + a judgment-call "large dispersion" flag (thresholds
# declared explicitly, not derived/validated).
# =============================================================================
by_event_instant = defaultdict(list)
for r in records:
    by_event_instant[(r["event_id"], r["requested_ts"])].append(r)

spread_disp = []
total_disp = []
ml_disp = []
n_multi_book_instants = 0
large_dispersion_events = []

for (eid, ts), rs in by_event_instant.items():
    if len(rs) < 2:
        continue
    n_multi_book_instants += 1
    # align spread to home-team signed point (mu with sign: negative if home favored)
    home_signed = []
    for r in rs:
        signed = -r["mu"] if r["spread_fav_is_home"] else r["mu"]
        home_signed.append(signed)
    spread_range = max(home_signed) - min(home_signed)
    spread_disp.append(spread_range)

    totals_here = [r["T"] for r in rs if r["T"] is not None]
    if len(totals_here) >= 2:
        total_range = max(totals_here) - min(totals_here)
        total_disp.append(total_range)
    else:
        total_range = None

    ml_here = [r["p_home_nv"] for r in rs]
    ml_range = max(ml_here) - min(ml_here)
    ml_disp.append(ml_range)

    if spread_range > 2.0 or (total_range is not None and total_range > 3.0):
        large_dispersion_events.append(dict(
            event_id=eid, requested_ts=ts, n_books=len(rs),
            spread_range_points=spread_range, total_range_points=total_range,
            books=[r["book"] for r in rs],
        ))

relation_D = dict(
    name="cross_book_dispersion_same_instant",
    assumed_model="DESCRIPTIVE. 'Large dispersion' flag thresholds (spread range > 2.0 pts OR total range > 3.0 pts) are a judgment call, not a validated arbitrage boundary.",
    N_event_instants_with_2plus_books=n_multi_book_instants,
    spread_home_signed_range_points=describe(spread_disp),
    total_line_range_points=describe(total_disp),
    moneyline_home_prob_range=describe(ml_disp),
    n_flagged_large_dispersion_instants=len(large_dispersion_events),
    sample_flagged_instants=large_dispersion_events[:15],
)

# =============================================================================
# Cross-quote latency window (D023 amendment 4 field, required on every
# incoherence flag). Compute distribution across ALL triple instances, and
# specifically among Relation A violations and large |Relation B| deviations.
# =============================================================================
all_latency = [r["cross_quote_latency_window_seconds"] for r in records]
latency_A_violation = [r["cross_quote_latency_window_seconds"] for r in records if not r["sign_coherent"]]

relation_meta_latency = dict(
    all_instances=describe(all_latency),
    relation_A_violation_instances=describe(latency_A_violation),
    note="Within-poll latency between h2h/spreads/totals last_update timestamps at the SAME book, SAME batch. This is metadata attached to each flag per D023 amendment 4, not a reaction-time claim.",
)

# =============================================================================
# Assemble the sample of Relation-A violation flags with full required metadata
# =============================================================================
violation_flags = []
for r in records:
    if not r["sign_coherent"]:
        violation_flags.append(dict(
            event_id=r["event_id"], book=r["book"], home_team=r["home_team"], away_team=r["away_team"],
            batch_requested_ts=r["requested_ts"], commence_time=r["commence_time"],
            p_home_nv=r["p_home_nv"], p_away_nv=r["p_away_nv"],
            is_moneyline_exact_pickem_tie_artifact=(r["p_home_nv"] == r["p_away_nv"]),
            spread_fav_is_home=r["spread_fav_is_home"], mu=r["mu"],
            capture_timestamps=r["capture_timestamps"],
            cross_quote_latency_window_seconds=r["cross_quote_latency_window_seconds"],
        ))
violation_flags.sort(key=lambda d: d["is_moneyline_exact_pickem_tie_artifact"])

output = dict(
    epistemic_status=(
        "DIAGNOSTIC MEASUREMENT. Tests whether related quotes jointly satisfy the no-arbitrage "
        "relations the M00 taxonomy implies. An incoherence is a timestamped observation about "
        "quotes, not an executable opportunity claim."
    ),
    universe=dict(
        source="data/market_snapshots/historical/featured_backfill.jsonl (T1_VENDOR_ASSERTED)",
        definition="one instant = (event_id, bookmaker key, batch requested_ts) with h2h AND spreads AND totals ALL present in that single poll batch for that book",
        n_bookmaker_market_instants_with_all_3_families=n_bookmaker_triples_seen,
        n_records_usable_after_naming_and_devig_checks=len(records),
        n_naming_mismatches_dropped=naming_mismatches,
        n_devig_zero_denominator_dropped=n_devig_zero_denominator,
        n_distinct_events=len(set(r["event_id"] for r in records)),
        n_distinct_books=len(set(r["book"] for r in records)),
        live_ladder_contribution="ZERO -- data/market_snapshots/snapshots.csv has no h2h/spreads/totals rows; see inventory.json",
    ),
    relations=dict(
        A_favorite_sign_coherence=relation_A,
        B_normal_margin_coherence=relation_B,
        B_normal_margin_coherence_by_book_min100=relation_B_by_book,
        B_normal_margin_coherence_by_hours_to_tip=relation_B_by_tip_bucket,
        Bprime_sigma_scales_with_total_sensitivity=relation_Bprime,
        C_cross_market_vig_consistency_descriptive=relation_C,
        D_cross_book_dispersion_same_instant=relation_D,
    ),
    cross_quote_latency_window=relation_meta_latency,
    relation_A_violation_flags_sample=violation_flags[:50],
    relation_A_violation_flags_total_count=len(violation_flags),
    could_not_establish=[
        "Any reaction-time, stale-window, or CLV claim -- explicitly out of scope per D023 amendment 4 and the node's stop conditions; this archive is T1_VENDOR_ASSERTED and no timing claim is made anywhere in this output.",
        "Whether Relation A/B violations are actually exploitable -- execution feasibility belongs to M21 per this node's acceptance criteria; not assessed here.",
        "M05 event-market linkage keys -- experiments/market_program/M05_EVENT_MARKET_LINKAGE/ does not exist in this worktree at the time of this run, so quotes were joined on the archive's native (event_id, bookmaker key, batch requested_ts) tuple instead. This is a deviation from the acceptance criterion 'quotes are joined through the M05 linkage keys' caused by an upstream dependency gap, not resolved by this node.",
        "Whether featured_backfill.jsonl is or is not the specific 'final-state odds archive' (813-game, one-snapshot-per-game) referenced in the M00 contract prompt text -- experiments/market_program/M00_MARKET_PROGRAM_CONTRACT/ does not exist in this worktree, so the bounded-uses ruling could not be checked against its actual frozen bytes. The archive actually present (1268 distinct events, avg ~3.9 polls/event across a full-season ladder cadence) does not match a 'one-snapshot-per-game' description on its face; flagged, not resolved.",
        "Ground-truth calibration of Relation B (whether the moneyline-vs-spread disagreement reflects real market inefficiency or a wrong normal-margin assumption) -- would require realized game outcomes, which are out of scope for a same-book cross-quote coherence check and were not used.",
    ],
)

with open(OUT_DIR / "COHERENCE.json", "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2, default=str)

# Also write FINDINGS.json (name required by the node's generated contract /
# validated by `python -c "import json;json.load(open(...FINDINGS.json))"` --
# see REPORT_BODY.md for the naming contradiction between the contract and
# the harness instruction that named COHERENCE.json instead). Content is
# identical to COHERENCE.json to satisfy both without inventing different data.
with open(OUT_DIR / "FINDINGS.json", "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2, default=str)

print("sigma_hat_median_points:", sigma_hat)
print("Relation A violation rate (raw):", relation_A["violation_rate_raw"])
print("Relation A violation rate (genuine, excl. pickem ties):", relation_A["violation_rate_genuine"])
print("Relation B N tested:", relation_B["N_tested"], "median abs diff:", relation_B["abs_diff_median"])
print("WROTE COHERENCE.json and FINDINGS.json")
