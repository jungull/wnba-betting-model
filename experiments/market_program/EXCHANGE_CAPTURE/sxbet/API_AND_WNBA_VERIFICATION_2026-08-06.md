# SX Bet — public market-data API and WNBA-existence verification

**Date:** 2026-08-06 (this session) · **Track:** D033 SXBET · **Contract:** M00_MARKET_PROGRAM_CONTRACT.md
(sha256 `1152dcd3bf74000f700844bc8bfc0df25de61a067f59534a714ac4f2f20265de`, verified at track start)

## 1. Does SX Bet document a public REST market-data API?

Yes. `docs.sx.bet` (redirect target of the older `api.docs.sx.bet`) is the current API reference.
Key facts as fetched this session:

- **Base URLs:** mainnet `https://api.sx.bet`; testnet `https://api.toronto.sx.bet`.
- **Auth for market data:** none. The docs state "Read markets, odds, trades" requires authentication
  "None." An API key is only needed to subscribe to realtime WebSocket channels; posting/canceling
  orders needs wallet-signed credentials (irrelevant to this read-only capture track).
- **Rate limits (as documented):** trade-data endpoints 200 req/min; most other endpoints 500 req/min;
  order-related GET requests 20 req/10s. This track's discipline (1 rps ≈ 60 req/min) sits well inside
  every one of these bands.
- **Help Center confirmation** (`help.sx.bet/en/articles/12984899-api`): "You can access endpoints,
  pull markets/odds, and post or fill orders without an API key... SX Bet provides free access to the
  API."

## 2. Do WNBA markets exist on SX Bet, right now?

**Yes, confirmed live.** Three read-only GET requests were made against the documented public
endpoints (see §4 for the honesty note on sequencing):

- `GET https://api.sx.bet/sports` → `{"sportId":1,"label":"Basketball"}` present.
- `GET https://api.sx.bet/leagues?sportId=1` → three WNBA-labeled leagues present:
  - `leagueId 1384` — **"WNBA"** (the main league — game markets)
  - `leagueId 10014` — "WNBA - MVP" (futures)
  - `leagueId 10028` — "WNBA - Series Outrights" (futures)
- `GET https://api.sx.bet/markets/active?leagueId=1384` → **60 active markets** returned right now,
  spanning multiple upcoming games (Indiana Fever @ Las Vegas Aces, Portland Fire @ Toronto Tempo,
  and others), across three market types observed: moneyline (`type 226`), spread (`type 342`), and
  totals (`type 28`). Each row carries `marketHash`, team names, `gameTime` (unix seconds),
  `sportXeventId` (fixture linkage key — e.g. `L19654296`), and per-side outcome labels.

This confirms the SX Bet public market-data surface has real, current WNBA game markets — not just a
league placeholder with zero listings — and that order-book and trade endpoints exist per the docs
architecture (`/orders?marketHashes=...`, `/trades?marketHashes=...`) for the same `marketHash` keys.
Order-book/trade endpoint *responses* were not fetched this session (see §4/§5) pending the ToS
disposition in `TERMS_OF_USE_VERIFIED_2026-08-06.md`.

## 3. What this does NOT establish

- No claim is made about odds quality, liquidity, or executability — that is S-EXEC territory (M26),
  out of scope for this capture-only track, and untouched by anything above.
- No trading eligibility or jurisdiction determination is made. SX Bet is a decentralized/crypto-collateral
  exchange (USDC); the M00 contract's §7 venue policy (exchange APIs as sandbox/shadow research tracks
  pending NY resolution) applies to *trading*, not to reading public market data — but see the ToS file
  for why *reading* itself is not fully clear either.

## 4. Honesty note on request sequencing

The three GETs in §2 were made during initial technical reconnaissance, in parallel with drafting the
WebSearch queries that surfaced SX Bet's Terms and Conditions. The ToS text (§5 below, and the
companion `TERMS_OF_USE_VERIFIED_2026-08-06.md`) was fully retrieved and read only *after* those three
calls, not before. This is disclosed rather than concealed: unlike the sibling Kalshi track (which
verified ToS text before making any request), this track's ordering was technical-capability-first.
No further requests against `api.sx.bet` were made once the ToS tension below was identified, and no
order-book, trade, or polling capture was built or run. Three lightweight, rate-limit-compliant,
publicly-documented GETs is the full extent of this track's contact with SX Bet's live systems.
