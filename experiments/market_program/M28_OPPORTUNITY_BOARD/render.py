"""render.py -- the opportunity board as a self-contained HTML dashboard.

Reads a board dict from `board.build_board` and writes one standalone file. No external
CSS, no fonts, no scripts fetched from anywhere: the page must render from a file:// URL
on a machine with no network.

DESIGN INTENT. This is an operating surface, not a document, so it is built to be scanned:
the answer ("what would you bet, in what order, how much") sits above the evidence, state
is encoded in colour AND in a written label so it survives a monochrome screenshot, and
every number that cannot be justified is replaced by the name of the gate blocking it
rather than quietly omitted.
"""
from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path

import board as _board

TIER_CLASS = {1: "locked", 2: "subsidy", 3: "bounded", 4: "info", 9: "gated"}
TIER_LABEL = {1: "Locked", 2: "Subsidised", 3: "Bounded risk", 4: "Informational",
              9: "Gated"}

CLASS_LABEL = {
    "TRUE_CROSS_BOOK_ARBITRAGE": "Arbitrage",
    "MIDDLES_AND_DISLOCATIONS": "Middle",
    "PURE_MICROSTRUCTURE": "Line shopping",
    "STALE_LINE_DELAYED_REACTION": "Stale line",
    "MODEL_VS_MARKET_VALUE": "Model vs market",
    "THIRD_PARTY_PROJECTION_VALUE": "Vendor projection",
    "PROMOTIONAL_VALUE": "Promo",
}

CSS = """
:root{
  --bg:#F4F5F7; --panel:#FFFFFF; --panel-2:#EDEFF2; --line:#DCE0E6; --line-2:#C6CCD4;
  --ink:#12161C; --ink-2:#4C5561; --ink-3:#7A8494;
  --accent:#2D5BA8; --accent-bg:#E6EDF9;
  --locked:#1C7A4C; --locked-bg:#E2F2E9;
  --bounded:#9A6512; --bounded-bg:#FBEFDC;
  --subsidy:#5B3FA6; --subsidy-bg:#EDE8F7;
  --info:#4C5561; --info-bg:#E9ECF0;
  --gated:#8C3A42; --gated-bg:#F7E8E9;
  --shop:#146B72; --shop-bg:#E0F0F1;
  --mono:ui-monospace,"Cascadia Mono","SF Mono",Menlo,Consolas,monospace;
  --sans:system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --bg:#0E1116; --panel:#161A21; --panel-2:#1E232B; --line:#252B34; --line-2:#333B46;
  --ink:#E6E9ED; --ink-2:#A5AEBB; --ink-3:#78838F;
  --accent:#7FA8E8; --accent-bg:#182335;
  --locked:#5FC48D; --locked-bg:#12271C;
  --bounded:#D9A75A; --bounded-bg:#2A2113;
  --subsidy:#B29BE0; --subsidy-bg:#1F1930;
  --info:#A5AEBB; --info-bg:#1E232B;
  --gated:#DE8C94; --gated-bg:#2A1719;
  --shop:#63B8C0; --shop-bg:#0F262A;
}}
:root[data-theme="dark"]{
  --bg:#0E1116; --panel:#161A21; --panel-2:#1E232B; --line:#252B34; --line-2:#333B46;
  --ink:#E6E9ED; --ink-2:#A5AEBB; --ink-3:#78838F;
  --accent:#7FA8E8; --accent-bg:#182335;
  --locked:#5FC48D; --locked-bg:#12271C;
  --bounded:#D9A75A; --bounded-bg:#2A2113;
  --subsidy:#B29BE0; --subsidy-bg:#1F1930;
  --info:#A5AEBB; --info-bg:#1E232B;
  --gated:#DE8C94; --gated-bg:#2A1719;
  --shop:#63B8C0; --shop-bg:#0F262A;
}
*{box-sizing:border-box}
body{margin:0;padding:0 1.25rem 5rem;background:var(--bg);color:var(--ink);
  font-family:var(--sans);font-size:15px;line-height:1.55;-webkit-font-smoothing:antialiased}
.wrap{max-width:74rem;margin:0 auto}
a{color:var(--accent)}
h1{font-size:1.6rem;letter-spacing:-.02em;margin:0 0 .3rem;font-weight:680}
.sub{color:var(--ink-2);font-size:.92rem;margin:0}
header.top{padding:2.5rem 0 1.25rem;display:flex;flex-wrap:wrap;gap:1rem;
  align-items:flex-end;justify-content:space-between;border-bottom:1px solid var(--line)}
.mode{font-family:var(--mono);font-size:.68rem;letter-spacing:.1em;text-transform:uppercase;
  padding:.35rem .6rem;border:1px solid var(--locked);color:var(--locked);
  background:var(--locked-bg);border-radius:3px;white-space:nowrap}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(7.5rem,1fr));
  border:1px solid var(--line);background:var(--line);gap:1px;margin:1.5rem 0}
.stat{background:var(--panel);padding:.85rem .9rem}
.stat .k{font-family:var(--mono);font-size:.62rem;letter-spacing:.09em;text-transform:uppercase;
  color:var(--ink-3);margin-bottom:.35rem}
.stat .v{font-size:1.35rem;font-variant-numeric:tabular-nums;line-height:1.1;font-weight:600}
.stat .v small{display:block;font-size:.72rem;font-weight:400;color:var(--ink-2);margin-top:.2rem}
.notice{border:1px solid var(--bounded);background:var(--bounded-bg);color:var(--ink);
  padding:1rem 1.1rem;border-radius:4px;margin:1.5rem 0;font-size:.9rem}
.notice b{color:var(--bounded)}
h2{font-size:1.02rem;margin:2.5rem 0 .2rem;font-weight:660;letter-spacing:-.01em}
h2 .count{font-family:var(--mono);font-weight:400;color:var(--ink-3);font-size:.8rem;margin-left:.4rem}
.h2sub{color:var(--ink-2);font-size:.87rem;margin:.15rem 0 1rem}
.opp{background:var(--panel);border:1px solid var(--line);border-left-width:4px;
  border-radius:4px;margin-bottom:.75rem;overflow:hidden}
.opp.locked{border-left-color:var(--locked)}
.opp.subsidy{border-left-color:var(--subsidy)}
.opp.bounded{border-left-color:var(--bounded)}
.opp.info{border-left-color:var(--info)}
.opp-head{display:flex;flex-wrap:wrap;gap:.5rem 1rem;align-items:baseline;
  padding:.85rem 1rem .6rem}
.rank{font-family:var(--mono);font-size:.75rem;color:var(--ink-3);min-width:1.6rem}
.matchup{font-weight:640;font-size:.98rem}
.mkt{font-family:var(--mono);font-size:.78rem;color:var(--ink-2)}
.tip{font-family:var(--mono);font-size:.72rem;color:var(--ink-3);margin-left:auto;white-space:nowrap}
.badge{font-family:var(--mono);font-size:.62rem;letter-spacing:.08em;text-transform:uppercase;
  padding:.18rem .45rem;border-radius:3px;white-space:nowrap}
.b-locked{background:var(--locked-bg);color:var(--locked)}
.b-subsidy{background:var(--subsidy-bg);color:var(--subsidy)}
.b-bounded{background:var(--bounded-bg);color:var(--bounded)}
.b-info{background:var(--info-bg);color:var(--info)}
.b-gated{background:var(--gated-bg);color:var(--gated)}
.headline{padding:0 1rem .5rem;font-size:.95rem}
.detail{padding:0 1rem .7rem;color:var(--ink-2);font-size:.87rem}
.legs{width:100%;border-collapse:collapse;font-size:.85rem;
  border-top:1px solid var(--line);background:var(--panel-2)}
.legs th{font-family:var(--mono);font-size:.6rem;letter-spacing:.08em;text-transform:uppercase;
  color:var(--ink-3);font-weight:500;text-align:left;padding:.45rem 1rem}
.legs td{padding:.45rem 1rem;border-top:1px solid var(--line)}
.legs td.n{font-family:var(--mono);font-variant-numeric:tabular-nums;text-align:right}
.stake{font-weight:660;color:var(--locked)}
.gatebox{margin:0;padding:.7rem 1rem;border-top:1px solid var(--line);
  background:var(--panel-2);color:var(--ink-2);font-size:.83rem}
.gatebox b{color:var(--gated)}
.caveats{margin:0;padding:.6rem 1rem .8rem 2.1rem;border-top:1px solid var(--line);
  color:var(--ink-3);font-size:.79rem}
.caveats li{margin:.15rem 0}
.gatelanes{display:grid;gap:1px;background:var(--line);border:1px solid var(--line);
  border-radius:4px;overflow:hidden}
@media(min-width:52rem){.gatelanes{grid-template-columns:1fr 1fr}}
.lane{background:var(--panel);padding:1rem 1.1rem}
.lane h3{margin:.4rem 0 .35rem;font-size:.95rem;font-weight:640}
.lane p{margin:0;color:var(--ink-2);font-size:.85rem}
.lane .gate{font-family:var(--mono);font-size:.7rem;color:var(--gated);margin-top:.5rem}
.empty{background:var(--panel);border:1px dashed var(--line-2);border-radius:4px;
  padding:1.4rem 1.2rem;color:var(--ink-2);font-size:.9rem}
.shop{width:100%;border-collapse:collapse;font-size:.85rem;background:var(--panel);
  border:1px solid var(--line);margin-bottom:1.2rem}
.shop th{font-family:var(--mono);font-size:.6rem;letter-spacing:.08em;text-transform:uppercase;
  color:var(--ink-3);font-weight:500;text-align:left;padding:.5rem .8rem;
  background:var(--panel-2);border-bottom:1px solid var(--line)}
.shop td{padding:.5rem .8rem;border-bottom:1px solid var(--line)}
.shop td.n{font-family:var(--mono);font-variant-numeric:tabular-nums;text-align:right}
.shop tr:last-child td{border-bottom:0}
.shop .bk{font-weight:640;color:var(--shop)}
.shop .gain{font-family:var(--mono);color:var(--shop);font-variant-numeric:tabular-nums}
.gm{font-weight:640;font-size:.9rem;margin:1.4rem 0 .4rem}
footer{margin-top:3.5rem;padding-top:1rem;border-top:1px solid var(--line);
  font-family:var(--mono);font-size:.72rem;color:var(--ink-3);line-height:1.8}
"""


def _esc(x) -> str:
    return html.escape(str(x), quote=True)


def _fmt_price(p) -> str:
    return f"{p:+g}"


def _tip_local(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        delta = (dt - datetime.now(timezone.utc)).total_seconds() / 3600.0
        when = dt.strftime("%H:%M UTC")
        if -3 < delta < 0:
            return f"{when} · in progress"
        if delta < 0:
            return f"{when} · started"
        return f"{when} · {delta:.1f}h"
    except Exception:
        return iso


def _opp_html(o: dict, rank: int) -> str:
    tier_cls = TIER_CLASS.get(o["tier"], "info")
    badge = f'<span class="badge b-{tier_cls}">{_esc(CLASS_LABEL.get(o["class_id"], o["class_id"]))}</span>'
    rows = []
    for leg in o["legs"]:
        pt = f' {leg["point"]:g}' if leg.get("point") is not None else ""
        stake = leg.get("stake")
        stake_cell = (f'<td class="n stake">${stake:,.2f}</td>' if stake is not None
                      else '<td class="n" style="color:var(--ink-3)">—</td>')
        rows.append(
            f'<tr><td>{_esc(leg["book"])}</td>'
            f'<td>{_esc(leg["outcome"])}{_esc(pt)}</td>'
            f'<td class="n">{_esc(_fmt_price(leg["price"]))}</td>'
            f'{stake_cell}</tr>'
        )

    stake_block = ""
    if o.get("suggested_stake"):
        st = o["suggested_stake"]
        stake_block = (
            f'<p class="gatebox"><b style="color:var(--locked)">Stake ${st["total"]:,.2f} total</b> — '
            f'worst-case profit <b style="color:var(--locked)">${st["worst_case_profit"]:,.2f}</b> '
            f'({st["worst_case_return_pct"]:.2f}%). {_esc(st["basis"])}.</p>'
        )
    elif o.get("stake_gate"):
        stake_block = f'<p class="gatebox"><b>No stake suggested.</b> {_esc(o["stake_gate"])}</p>'

    caveats = ""
    if o.get("caveats"):
        items = "".join(f"<li>{_esc(c)}</li>" for c in o["caveats"])
        caveats = f'<ul class="caveats">{items}</ul>'

    return f"""<article class="opp {tier_cls}">
  <div class="opp-head">
    <span class="rank">#{rank}</span>
    <span class="matchup">{_esc(o["matchup"])}</span>
    <span class="mkt">{_esc(o["market"])}</span>
    {badge}
    <span class="tip">{_esc(_tip_local(o["commence_time"]))}</span>
  </div>
  <div class="headline">{_esc(o["headline"])}</div>
  <div class="detail">{_esc(o["detail"])}</div>
  <table class="legs"><thead><tr>
    <th>Book</th><th>Selection</th><th style="text-align:right">Price</th>
    <th style="text-align:right">Stake</th>
  </tr></thead><tbody>{"".join(rows)}</tbody></table>
  {stake_block}{caveats}
</article>"""


def render(b: dict) -> str:
    opps = b["opportunities"]
    by_tier: dict[int, list] = {}
    for o in opps:
        by_tier.setdefault(o["tier"], []).append(o)

    age_min = b["age_seconds"] / 60.0

    # Describe the grid we MEASURED, never a remembered one. This page asserted "hourly"
    # for a day after the cadence was raised, which is exactly the drift it warns about.
    cad = b.get("cadence") or {}
    gap_min = cad.get("median_gap_min")
    if gap_min is None:
        grid = "an unmeasured polling grid"
    elif gap_min >= 30:
        grid = f"a coarse polling grid (median {gap_min:g} min between captures)"
    elif gap_min >= 10:
        grid = f"a {gap_min:g}-minute polling grid"
    else:
        grid = f"a fast polling grid (median {gap_min:g} min between captures)"

    cadence_note = (
        f"Captured on {grid}. A price seen here existed at some point inside that window; "
        "it is <b>not</b> a claim that you could still take it. Detecting a locked "
        "combination and being able to strike both legs are different assertions, and the "
        "second needs measured limits and latency (M21/M22), which this node does not have."
    )
    excluded = b.get("n_games_in_play_excluded", 0)
    if excluded:
        cadence_note += (
            f" <b>{excluded} game(s) already under way are excluded</b> from the arbitrage "
            "and middle detectors: measured over 179 snapshots, 24.56% of in-play markets "
            "show a negative cross-book overround against 0.27% pre-game, because a book "
            "that has not moved off its pre-game price after tip re-stamps its update time "
            "without changing the number."
        )

    sections = []
    order = [
        (1, "Locked opportunities",
         "Guaranteed positive in every settlement outcome, pushes included. These carry a concrete stake because the split is arithmetic, not a forecast."),
        (2, "Subsidised opportunities — your promotions",
         "Venue-subsidised positive expected value, capped by the offer itself. No informational edge is required to take these, and the probability comes from the market consensus rather than our model. Positive in expectation, NOT locked."),
        (3, "Bounded-risk opportunities",
         "Both legs can win. The downside is the vig rather than a full stake — but the profit is probabilistic, so this is not arbitrage and carries no suggested stake."),
        (4, "Informational",
         "Where the books most disagree. Descriptive only: no position is implied."),
    ]
    rank = 0
    for tier, title, sub in order:
        rows = by_tier.get(tier, [])
        sections.append(f'<h2>{_esc(title)}<span class="count">{len(rows)}</span></h2>'
                        f'<p class="h2sub">{_esc(sub)}</p>')
        if not rows:
            if tier == 1:
                reason = ("No locked combination exists across these books right now. That is "
                          "the normal state of a mature market — arbitrage is rare, brief, "
                          "and rarer still on an hourly grid.")
            elif tier == 2:
                reason = ("No promotions entered. Add your real offers to promos.json and they "
                          "will be valued here against the market's own consensus.")
            else:
                reason = "Nothing detected in this snapshot."
            sections.append(f'<div class="empty">{_esc(reason)}</div>')
        for o in rows:
            rank += 1
            sections.append(_opp_html(o, rank))

    # ---- best-price / line-shopping section
    bp = b.get("best_prices") or []
    shop_html = ""
    if bp:
        by_game: dict[str, list] = {}
        for r in bp:
            by_game.setdefault(r["matchup"], []).append(r)
        parts = []
        for matchup, rows_ in list(by_game.items())[:8]:
            body = []
            for r in rows_:
                for sd in r["sides"]:
                    # Show the SIDE's own signed line. The row is keyed on magnitude so
                    # mirrored spreads pair at all, but "Spread 8.5" alone does not say which
                    # team is -8.5 -- and a table whose job is to tell you where to bet must
                    # not be ambiguous about what to bet.
                    spt = sd.get("point", r.get("point"))
                    pt = ""
                    if spt is not None:
                        pt = f' {spt:+g}' if r["market"] == "Spread" else f' {spt:g}'
                    body.append(
                        f'<tr><td>{_esc(r["market"])}</td>'
                        f'<td>{_esc(sd["outcome"])}{_esc(pt)}</td>'
                        f'<td class="bk">{_esc(sd["best_book"])}</td>'
                        f'<td class="n">{_esc(_fmt_price(sd["best_price"]))}</td>'
                        f'<td class="n" style="color:var(--ink-3)">'
                        f'{_esc(_fmt_price(sd["median_price"]))}</td>'
                        f'<td class="n gain">+{sd["gain_vs_median_pct"]:.2f}%</td>'
                        f'<td class="n" style="color:var(--ink-3)">{sd["n_books"]}</td></tr>')
            parts.append(
                f'<div class="gm">{_esc(matchup)}</div>'
                f'<table class="shop"><thead><tr>'
                f'<th>Market</th><th>Side</th><th>Best book</th>'
                f'<th style="text-align:right">Best</th>'
                f'<th style="text-align:right">Typical</th>'
                f'<th style="text-align:right">Gain</th>'
                f'<th style="text-align:right">Books</th>'
                f'</tr></thead><tbody>{"".join(body)}</tbody></table>')
        shop_html = (
            f'<h2>Where to bet each side<span class="count">{len(bp)}</span></h2>'
            f'<p class="h2sub">{_esc(b.get("best_prices_note", ""))}</p>'
            + "".join(parts))

    lanes = "".join(
        f'<div class="lane"><span class="badge b-gated">Gated</span>'
        f'<h3>{_esc(g["label"])}</h3><p>{_esc(g["why"])}</p>'
        f'<p class="gate">Blocked by: {_esc(g["gate"])}</p></div>'
        for g in b["gated_lanes"]
    )

    return f"""<title>WNBA Opportunity Board</title>
<style>{CSS}</style>
<div class="wrap">
<header class="top">
  <div>
    <h1>WNBA Opportunity Board</h1>
    <p class="sub">Every priced WNBA market across {b['n_books']} books, ranked by what the
    arithmetic actually supports.</p>
  </div>
  <span class="mode">Execution: {_esc(b['execution_mode'])} · flags only</span>
</header>

<div class="stats">
  <div class="stat"><div class="k">Snapshot</div><div class="v">{age_min:.0f}m<small>{_esc(b['snapshot_utc'])}</small></div></div>
  <div class="stat"><div class="k">Games</div><div class="v">{b['n_games']}</div></div>
  <div class="stat"><div class="k">Books</div><div class="v">{b['n_books']}</div></div>
  <div class="stat"><div class="k">Quotes</div><div class="v">{b['n_quotes']}</div></div>
  <div class="stat"><div class="k">Locked</div><div class="v" style="color:var(--locked)">{b['counts']['TRUE_CROSS_BOOK_ARBITRAGE']}</div></div>
  <div class="stat"><div class="k">Promos</div><div class="v" style="color:var(--subsidy)">{b['counts'].get('PROMOTIONAL_VALUE', 0)}</div></div>
  <div class="stat"><div class="k">Middles</div><div class="v" style="color:var(--bounded)">{b['counts']['MIDDLES_AND_DISLOCATIONS']}</div></div>
  <div class="stat"><div class="k">Grid</div><div class="v">{(str(b.get('cadence',{}).get('median_gap_min','?')) + 'm') if b.get('cadence',{}).get('median_gap_min') is not None else '?'}<small>median capture gap</small></div></div>
  <div class="stat"><div class="k">Bankroll</div><div class="v">${b['bankroll']:,.0f}<small>sizing basis</small></div></div>
</div>

<div class="notice"><b>Read this before acting on anything below.</b> {cadence_note}</div>

{"".join(sections)}

{shop_html}

<h2>Not shown, and why<span class="count">{len(b['gated_lanes'])}</span></h2>
<p class="h2sub">A board that silently omits a category is indistinguishable from one that
found nothing there. These lanes are built and dark.</p>
<div class="gatelanes">{lanes}</div>

<footer>
  Snapshot {_esc(b['snapshot_utc'])} · captured {_esc(b['captured_at'])} · age {b['age_seconds']:.0f}s<br>
  Data root {_esc(b['data_root'])} · resolved via {_esc(b['data_root_how'])}<br>
  {_esc(b['execution_mode_note'])}<br>
  M28_OPPORTUNITY_BOARD · M00 taxonomy {_esc(b.get('contract_base_sha256',''))[:16]}… + amendment v{b.get('contract_amendment_version')} (D144) · every class id verified against the contract<br>
  this page places nothing and never will
</footer>
</div>"""


def write(b: dict, path: str | Path) -> Path:
    path = Path(path)
    path.write_text(render(b), encoding="utf-8")
    return path


if __name__ == "__main__":
    import feed
    snap = feed.load_latest()
    bd = _board.build_board(snap)
    out = write(bd, Path(__file__).parent / "board.html")
    js = Path(__file__).parent / "board.json"
    js.write_text(json.dumps(bd, indent=1), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size:,} bytes)")
    print(f"wrote {js} ({js.stat().st_size:,} bytes)")
    print("counts:", bd["counts"])
