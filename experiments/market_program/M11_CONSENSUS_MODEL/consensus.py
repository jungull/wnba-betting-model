"""M11_CONSENSUS_MODEL -- multi-book consensus / fair-value machinery.

Builds, under MARKET_PROGRAM_CONTRACT.md (sha256 1152dcd3...265de) and
TAXONOMY.json (sha256 c83e25e7...940a12c):

  * no-vig conversion, per a vig-removal method PREREGISTERED in this file
    (frozen before any evaluation is run against real bytes -- see
    PREREGISTRATION below);
  * cross-book consensus fair line / probability, with an uncertainty
    measure and a disagreement score;
  * a book-vs-consensus residual definition (the F5 "consensus residual"
    family's *input feature* -- never itself a stale-line or reaction-time
    claim; those require event-linked TRUSTED T0 interval-censored analysis
    this module does not perform, per contract section 1.3);
  * book-reliability weighting hooks that enforce, IN CODE, that any fitted
    weighting uses data strictly before the evaluation window it is applied
    to (a WeightFittingViolation is raised otherwise).

EPISTEMIC STATUS (write verbatim wherever this module's output is cited):
"MARKET-REACTION SYSTEM COMPONENT under the four-system separation.
Estimates a consensus fair line from multi-book quotes. It models the
market, not the game; its output is never a fundamental prediction and is
labelled per the M00 ladder."

Every object this module emits carries the amendment-4 field set (contract
section 6.1) even though a consensus snapshot is NOT itself a reaction-time
claim; see `is_reaction_time_claim` (always False here) and the REPORT.md
note on this interpretive choice. No object this module emits ever claims
an evidence-ladder label (`evidence_ladder_labels_held` is always `[]`):
this is machinery, not a preregistered family-endpoint result.

The ladder-off honesty rule (orchestrator instructions): the high-frequency
tape does not exist yet. This module is tested machinery over fixtures and
the existing coarse (T2) tape samples. Nothing here is a finding; the
book-reliability weighting hooks are activation-checklisted, not switched on.

Stdlib only.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import datetime as _dt

# ---------------------------------------------------------------------------
# Epistemic status line -- verbatim, cited by every REPORT.md and every
# demo/test output that carries this module's objects.
# ---------------------------------------------------------------------------
EPISTEMIC_STATUS_LINE = (
    "MARKET-REACTION SYSTEM COMPONENT under the four-system separation. "
    "Estimates a consensus fair line from multi-book quotes. It models the "
    "market, not the game; its output is never a fundamental prediction and "
    "is labelled per the M00 ladder."
)

CONTRACT_SHA256 = "1152dcd3bf74000f700844bc8bfc0df25de61a067f59534a714ac4f2f20265de"
TAXONOMY_SHA256 = "c83e25e783a4ee8642a26dd416362e46c2c34196ff8f8354977c28b72940a12c"

UNBOUNDED = "UNBOUNDED"
UNMEASURED = "UNMEASURED"
INF = "INF"
TIER_ORDER = {"T0": 0, "T1": 1, "T2": 2}

REASON_TIER_INSUFFICIENT = "TIER_INSUFFICIENT"     # mirrors M05 vocabulary


# ---------------------------------------------------------------------------
# Canonical serialization / hashing (same convention as M05_EVENT_MARKET_LINKAGE)
# ---------------------------------------------------------------------------

def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True)


def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


_TS_RE = re.compile(r"^(\d{4})-?(\d{2})-?(\d{2})[T ]?(\d{2}):?(\d{2}):?(\d{2})")
_EPOCH = _dt.datetime(1970, 1, 1)


def parse_ts(s) -> int:
    if isinstance(s, int):
        return s
    m = _TS_RE.match(str(s).strip())
    if not m:
        raise ValueError(f"unparseable timestamp: {s!r}")
    y, mo, d, h, mi, se = (int(g) for g in m.groups())
    return int((_dt.datetime(y, mo, d, h, mi, se) - _EPOCH).total_seconds())


def fmt_ts(t: int) -> str:
    return (_EPOCH + _dt.timedelta(seconds=int(t))).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Price conversions
# ---------------------------------------------------------------------------

def american_to_decimal(price) -> float:
    p = float(price)
    if p == 0:
        raise ValueError("American price of 0 is not a valid quote")
    return 1.0 + p / 100.0 if p > 0 else 1.0 + 100.0 / abs(p)


def raw_implied_prob(price) -> float:
    """The un-devigged implied probability of a single American price."""
    return 1.0 / american_to_decimal(price)


def decimal_to_american(dec: float) -> float:
    if dec <= 1.0:
        raise ValueError("decimal odds must exceed 1.0")
    b = dec - 1.0
    return round(b * 100.0, 4) if b >= 1.0 else round(-100.0 / b, 4)


# ---------------------------------------------------------------------------
# Vig-removal methods -- PREREGISTRATION
#
# Three estimators are implemented and named in the registry. Exactly one is
# selected as PRIMARY below. The selection is frozen in this file, before
# any evaluation is run against real bytes (the coarse-tape demo and any
# future prospective use). Changing PREREGISTERED_VIG_METHOD after seeing
# results on real data is exactly the tuning-on-results this acceptance
# criterion forbids; a change is only legitimate as a new, separately dated
# preregistration.
# ---------------------------------------------------------------------------

VIG_METHOD_MULTIPLICATIVE = "multiplicative_proportional"
VIG_METHOD_POWER = "power_devig"
VIG_METHOD_SHIN = "shin"

VIG_METHOD_REGISTRY = {
    VIG_METHOD_MULTIPLICATIVE: {
        "description": "p_i = raw_i / sum(raw). Simplest, most standard "
                        "no-vig transform; assumes the overround is spread "
                        "proportionally across outcomes.",
        "assumptions": "Overround is proportional across outcomes; no "
                        "informed-money / favorite-longshot adjustment.",
    },
    VIG_METHOD_POWER: {
        "description": "p_i = raw_i ** k, k chosen so sum(p_i) = 1 "
                        "(bisection). Compresses the overround "
                        "multiplicatively in log-space rather than linearly.",
        "assumptions": "Same family of bias as multiplicative for "
                        "near-even two-way markets; diverges on lopsided "
                        "books.",
    },
    VIG_METHOD_SHIN: {
        "description": "Shin (1992) closed form solving for an insider-"
                        "trading fraction z: "
                        "p_i = (sqrt(z^2 + 4(1-z) r_i^2/S) - z) / (2(1-z)), "
                        "S = sum(raw), z chosen so sum(p_i) = 1.",
        "assumptions": "Favorite-longshot bias exists and is explained by a "
                        "fixed insider fraction z common to all outcomes in "
                        "the market; more parameters than the market has "
                        "outcomes to identify z robustly on a two-way book.",
    },
}

PREREGISTERED_VIG_METHOD = VIG_METHOD_MULTIPLICATIVE

PREREGISTRATION = {
    "schema": "market_program/M11/vig_preregistration/1",
    "primary_method": PREREGISTERED_VIG_METHOD,
    "alternates_in_registry_not_used": [VIG_METHOD_POWER, VIG_METHOD_SHIN],
    "frozen_before_evaluation": True,
    "rationale": (
        "Multiplicative-proportional is selected as PRIMARY because it is "
        "parameter-free (no fitted exponent or insider fraction), so it "
        "cannot itself be tuned on results -- there is nothing in it to "
        "tune. Power and Shin remain in the registry as documented "
        "alternates for a future, separately-dated preregistration; neither "
        "is invoked by consensus_fair_value() unless the caller explicitly "
        "overrides `method=`, which the coarse-tape demo and TESTS.py do "
        "not do for the acceptance-criteria-bearing path."
    ),
    "acceptance_criterion": (
        "the vig-removal method is preregistered before evaluation, not "
        "tuned on results (M11_CONSENSUS_MODEL mandate)"
    ),
}
PREREGISTRATION_HASH = sha256_hex(canonical_json(PREREGISTRATION))


def no_vig_multiplicative(prices):
    raw = [raw_implied_prob(p) for p in prices]
    s = sum(raw)
    if s <= 0:
        raise ValueError("degenerate market: sum of raw implied probs <= 0")
    return [r / s for r in raw], s


def no_vig_power(prices, tol=1e-10, max_iter=200):
    raw = [raw_implied_prob(p) for p in prices]

    def total(k):
        return sum(r ** k for r in raw) - 1.0

    lo, hi = 0.0, 20.0
    if total(lo) < 0:
        # book is already sub-100%: no compression needed, return raw
        return list(raw), 1.0
    f_hi = total(hi)
    tries = 0
    while f_hi > 0 and tries < 10:
        hi *= 2
        f_hi = total(hi)
        tries += 1
    for _ in range(max_iter):
        mid = (lo + hi) / 2.0
        if total(mid) > 0:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    k = (lo + hi) / 2.0
    return [r ** k for r in raw], k


def no_vig_shin(prices, tol=1e-12, max_iter=300):
    raw = [raw_implied_prob(p) for p in prices]
    S = sum(raw)

    def probs_for_z(z):
        if z <= 0.0:
            return [r / S for r in raw]
        out = []
        for r in raw:
            inner = z * z + 4.0 * (1.0 - z) * (r * r) / S
            inner = max(inner, 0.0)
            out.append((math.sqrt(inner) - z) / (2.0 * (1.0 - z)))
        return out

    def total(z):
        return sum(probs_for_z(z)) - 1.0

    lo, hi = 0.0, 0.999999
    if total(lo) <= 0:
        return probs_for_z(0.0), 0.0
    for _ in range(max_iter):
        mid = (lo + hi) / 2.0
        t = total(mid)
        if t > 0:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    z = (lo + hi) / 2.0
    return probs_for_z(z), z


VIG_METHOD_FN = {
    VIG_METHOD_MULTIPLICATIVE: no_vig_multiplicative,
    VIG_METHOD_POWER: no_vig_power,
    VIG_METHOD_SHIN: no_vig_shin,
}


def no_vig(prices, method=PREREGISTERED_VIG_METHOD):
    """Returns (probs, overround_or_param, method, preregistration_hash)."""
    if method not in VIG_METHOD_REGISTRY:
        raise ValueError(f"unregistered vig method: {method!r}; the "
                          "registry is frozen -- add a dated preregistration "
                          "entry, never an ad hoc method")
    probs, param = VIG_METHOD_FN[method](prices)
    return probs, param, method, PREREGISTRATION_HASH


# ---------------------------------------------------------------------------
# Quote object -- one book's price for one outcome, with full provenance
# ---------------------------------------------------------------------------

def make_quote(*, bookmaker, price, capture_ts, tier="T0",
               vendor_ts=None, vendor_ts_semantics="unknown_unverified",
               market="h2h", outcome=None, point=None):
    """A single book's witnessed (or vendor-asserted) quote.

    capture_ts is OUR witness time for T0/T1; for T2 rows it is the
    archive's vendor-asserted snapshot stamp, carried but never treated as
    witnessed (contract section 4.3 / TAXONOMY.json tier rules).
    """
    if tier not in TIER_ORDER:
        raise ValueError(f"unknown tier {tier!r}")
    return {
        "bookmaker": bookmaker,
        "price": price,
        "capture_ts": capture_ts,             # int epoch seconds
        "tier": tier,
        "vendor_ts": vendor_ts,
        "vendor_ts_semantics": vendor_ts_semantics,
        "market": market,
        "outcome": outcome,
        "point": point,
    }


# ---------------------------------------------------------------------------
# Cross-book consensus fair value
# ---------------------------------------------------------------------------

class ConsensusError(Exception):
    pass


def consensus_fair_value(quotes, *, method=PREREGISTERED_VIG_METHOD,
                          weights=None, weights_status="PREREGISTERED_UNIFORM",
                          clock_skew=UNMEASURED, vendor_latency_bounds=None,
                          default_vendor_latency=UNBOUNDED,
                          allow_t1=False, game_id=None):
    """Build ONE consensus object from a set of same-side, same-poll-window
    book quotes plus the market's opposite-side quotes needed to devig each
    book (paired_prices on each quote entry via `opposite_price`).

    `quotes`: list of dicts, each a `make_quote(...)` PLUS an
    `opposite_price` key (the same book's price on the other side of a
    two-way market, needed to remove that book's vig). Every quote must
    share `market` and `outcome` (the side being priced).

    `weights`: optional {bookmaker: weight}; defaults to uniform
    (PREREGISTERED_UNIFORM -- never fitted unless the caller supplies
    weights produced by `fit_book_weights` and sets weights_status
    accordingly).

    Returns a consensus object carrying the full amendment-4 field set
    (contract section 6.1), the M00 evidence-ladder fields (always empty --
    this is machinery, not a family-endpoint result), and the capture
    timestamp of every contributing quote (M11 acceptance criterion).
    """
    if not quotes:
        raise ConsensusError("consensus_fair_value: no quotes supplied")
    outcomes = {q["outcome"] for q in quotes}
    markets = {q["market"] for q in quotes}
    if len(outcomes) != 1 or len(markets) != 1:
        raise ConsensusError(
            "consensus_fair_value: all quotes must share one market and "
            "one outcome (side); mixing sides here would silently blend "
            "distinct markets")

    vendor_latency_bounds = vendor_latency_bounds or {}
    tiers_seen = {q["tier"] for q in quotes}
    min_tier = max(tiers_seen, key=lambda t: TIER_ORDER[t])   # weakest tier
    # tier inheritance (contract section 4.3): a derived quantity inherits
    # the weakest tier of any input.
    tier_admissible = (TIER_ORDER[min_tier] < TIER_ORDER["T2"]
                        and (min_tier == "T0" or allow_t1))

    n_excluded = 0
    exclusion_reasons = {}
    trusted_quotes = []
    for q in quotes:
        if TIER_ORDER[q["tier"]] >= TIER_ORDER["T2"]:
            n_excluded += 1
            exclusion_reasons[REASON_TIER_INSUFFICIENT] = \
                exclusion_reasons.get(REASON_TIER_INSUFFICIENT, 0) + 1
            continue
        if q["tier"] == "T1" and not allow_t1:
            n_excluded += 1
            exclusion_reasons[REASON_TIER_INSUFFICIENT] = \
                exclusion_reasons.get(REASON_TIER_INSUFFICIENT, 0) + 1
            continue
        trusted_quotes.append(q)

    per_book = []
    for q in trusted_quotes:
        probs, param, used_method, prereg_hash = no_vig(
            [q["price"], q["opposite_price"]], method=method)
        p_side = probs[0]
        per_book.append({
            "bookmaker": q["bookmaker"],
            "capture_ts": q["capture_ts"],
            "capture_ts_iso": fmt_ts(q["capture_ts"]) if isinstance(
                q["capture_ts"], int) else q["capture_ts"],
            "tier": q["tier"],
            "vendor_ts": q.get("vendor_ts"),
            "vendor_ts_semantics": q.get("vendor_ts_semantics"),
            "price": q["price"],
            "opposite_price": q["opposite_price"],
            "point": q.get("point"),
            "no_vig_prob": p_side,
            "overround_or_param": param,
        })

    if weights is None:
        w = {b["bookmaker"]: 1.0 for b in per_book}
    else:
        missing = [b["bookmaker"] for b in per_book if b["bookmaker"] not in weights]
        if missing:
            raise ConsensusError(
                f"weights supplied but missing entries for books {missing}; "
                "a partial weight map would silently reweight by omission")
        w = weights
    wsum = sum(w[b["bookmaker"]] for b in per_book) if per_book else 0.0

    if per_book and wsum > 0:
        consensus_prob = sum(w[b["bookmaker"]] * b["no_vig_prob"]
                              for b in per_book) / wsum
        # weighted variance / std (uncertainty)
        var = sum(w[b["bookmaker"]] * (b["no_vig_prob"] - consensus_prob) ** 2
                   for b in per_book) / wsum
        uncertainty_std = math.sqrt(max(var, 0.0))
        probs_list = [b["no_vig_prob"] for b in per_book]
        disagreement_score = (max(probs_list) - min(probs_list)) \
            if len(probs_list) > 1 else 0.0
    else:
        consensus_prob = None
        uncertainty_std = None
        disagreement_score = None

    book_residuals = {}
    if consensus_prob is not None:
        for b in per_book:
            book_residuals[b["bookmaker"]] = book_vs_consensus_residual(
                b["no_vig_prob"], consensus_prob)

    skew = clock_skew
    eps = None if skew == UNMEASURED else int(skew.get("epsilon_max_s"))
    vlb = {b["bookmaker"]: vendor_latency_bounds.get(
        b["bookmaker"], default_vendor_latency) for b in per_book}

    capture_timestamps = sorted(
        {fmt_ts(q["capture_ts"]) if isinstance(q["capture_ts"], int)
         else str(q["capture_ts"]) for q in quotes})
    poll_gaps = None
    ints = sorted(q["capture_ts"] for q in trusted_quotes
                  if isinstance(q["capture_ts"], int))
    if len(ints) > 1:
        poll_gaps = ints[-1] - ints[0]

    obj = {
        "schema": "market_program/M11/consensus_object/1",
        "claim_type": "CONSENSUS_FAIR_VALUE_SNAPSHOT",
        "is_reaction_time_claim": False,
        "epistemic_status": EPISTEMIC_STATUS_LINE,
        "not_a_fundamental_prediction": True,
        "evidence_ladder_labels_held": [],
        "evidence_ladder_note": (
            "No evidence-ladder label is claimed by this object. It is "
            "machinery output (a consensus snapshot), not the result of a "
            "preregistered family endpoint run against TRUSTED T0 data "
            "(contract section 3)."
        ),
        "game_id": game_id,
        "market": next(iter(markets)),
        "outcome": next(iter(outcomes)),
        "vig_method": method,
        "vig_method_preregistration_hash": PREREGISTRATION_HASH,
        "n_books_supplied": len(quotes),
        "n_books_admitted": len(per_book),
        "contributing_quotes": per_book,
        "capture_timestamps_all_contributing_quotes": capture_timestamps,
        "consensus_fair_prob": consensus_prob,
        "consensus_fair_price_american": (
            None if consensus_prob in (None, 0)
            else decimal_to_american(1.0 / consensus_prob)),
        "uncertainty_std": uncertainty_std,
        "disagreement_score": disagreement_score,
        "book_residuals": book_residuals,
        "book_residuals_note": (
            "F5 (consensus residual) family INPUT FEATURE only -- a "
            "book-vs-consensus deviation at one snapshot. This is never "
            "itself a STALE_LINE_DELAYED_REACTION claim (taxonomy 1.3): "
            "that class requires event-linked, TRUSTED, T0, interval-"
            "censored reaction analysis this function does not perform."
        ),
        "weights_used": dict(w),
        "weights_status": weights_status,
        # --- amendment-4 field set, contract section 6.1 (see module
        # docstring for why a non-reaction-time snapshot still carries them)
        "t_lower": "NOT_A_REACTION_TIME_CLAIM",
        "t_upper": "NOT_A_REACTION_TIME_CLAIM",
        "poll_interval_event": "N/A_NO_EVENT_STREAM",
        "poll_interval_quote": poll_gaps if poll_gaps is not None else "UNKNOWN",
        "vendor_latency_bound": vlb,
        "clock_skew_bound": skew,
        "censor_type": "N/A",
        "tier": min_tier,
        "n_trusted": len(per_book),
        "n_excluded": n_excluded,
        "exclusion_reasons": exclusion_reasons,
        "channel": "WITNESSED" if min_tier == "T0" else "VENDOR_ASSERTED",
        "tier_admissible": tier_admissible,
    }
    obj["result_hash"] = sha256_hex(canonical_json(
        {k: v for k, v in obj.items() if k != "result_hash"}))
    return obj


def book_vs_consensus_residual(book_no_vig_prob, consensus_prob):
    """The stale-book residual definition (F5 input feature).

    residual = book_no_vig_prob - consensus_prob (signed, in probability
    units). A large |residual| is a CANDIDATE for later F5/F1/F2-style
    investigation; it is NOT by itself evidence the book is stale or slow
    (see book_residuals_note on the consensus object). No threshold is
    applied here: any threshold or STALE_CANDIDATE flag is left to a future,
    separately preregistered F5 endpoint, per the no-tuning-on-results
    discipline this module applies to the vig method.
    """
    signed = book_no_vig_prob - consensus_prob
    return {"signed": signed, "abs": abs(signed)}


# ---------------------------------------------------------------------------
# Book-reliability weighting hooks -- preregistered-not-fitted until tape
# exists. The hook enforces the train/evaluation separation IN CODE.
# ---------------------------------------------------------------------------

class WeightFittingViolation(Exception):
    pass


def fit_book_weights(observations, *, fit_window_end_ts,
                      evaluation_window_start_ts, min_obs_per_book=5):
    """Fit per-book weights from historical book_vs_consensus_residual
    observations, using inverse-variance weighting (lower historical
    variance around consensus -> higher weight). This is a HOOK: it is not
    invoked by the coarse-tape demo or by consensus_fair_value()'s default
    path, because no tape exists yet to fit on honestly (ladder OFF).

    `observations`: list of {"bookmaker": str, "capture_ts": int,
    "residual": float}. Every observation must be strictly before
    `fit_window_end_ts`, and `fit_window_end_ts` must be <=
    `evaluation_window_start_ts` -- both enforced here, not left to the
    caller's discipline, per the acceptance criterion: "any book weighting
    is fitted only on data strictly before the evaluation window."

    Returns (weights, provenance) where provenance records exactly what was
    fit on, for audit.
    """
    if fit_window_end_ts > evaluation_window_start_ts:
        raise WeightFittingViolation(
            "fit_window_end_ts must be <= evaluation_window_start_ts: book "
            "weighting may only be fitted on data strictly before the "
            "evaluation window it will be applied to")
    for o in observations:
        if o["capture_ts"] >= fit_window_end_ts:
            raise WeightFittingViolation(
                f"observation for {o['bookmaker']!r} at capture_ts "
                f"{o['capture_ts']} is not strictly before fit_window_end_ts "
                f"{fit_window_end_ts}; using it would leak evaluation-window "
                "information into the fitted weight")

    by_book = {}
    for o in observations:
        by_book.setdefault(o["bookmaker"], []).append(o["residual"])

    inv_var = {}
    fallback_uniform = []
    for book, resids in by_book.items():
        if len(resids) < min_obs_per_book:
            fallback_uniform.append(book)
            continue
        mean = sum(resids) / len(resids)
        var = sum((r - mean) ** 2 for r in resids) / len(resids)
        inv_var[book] = 1.0 / var if var > 0 else None

    books = list(by_book)
    if not books:
        raise WeightFittingViolation("no observations supplied to fit on")

    fittable = {b: v for b, v in inv_var.items() if v is not None}
    if not fittable:
        weights = {b: 1.0 / len(books) for b in books}
        method = "UNIFORM_FALLBACK_ALL_BOOKS_INSUFFICIENT_DATA"
    else:
        total = sum(fittable.values())
        weights = {}
        # books with too few observations or zero variance fall back to the
        # mean of the fitted weights, never to an unfitted zero
        mean_fitted = total / len(fittable)
        for b in books:
            if b in fittable:
                weights[b] = fittable[b]
            else:
                weights[b] = mean_fitted
        wsum = sum(weights.values())
        weights = {b: v / wsum for b, v in weights.items()}
        method = "INVERSE_VARIANCE_OF_BOOK_VS_CONSENSUS_RESIDUAL"

    provenance = {
        "schema": "market_program/M11/weight_fit_provenance/1",
        "method": method,
        "fit_window_end_ts": fit_window_end_ts,
        "fit_window_end_iso": fmt_ts(fit_window_end_ts),
        "evaluation_window_start_ts": evaluation_window_start_ts,
        "evaluation_window_start_iso": fmt_ts(evaluation_window_start_ts),
        "strictly_before_evaluation_window_enforced": True,
        "n_observations_per_book": {b: len(v) for b, v in by_book.items()},
        "books_uniform_fallback_insufficient_data": fallback_uniform,
        "min_obs_per_book": min_obs_per_book,
    }
    provenance["provenance_hash"] = sha256_hex(canonical_json(provenance))
    return weights, provenance
