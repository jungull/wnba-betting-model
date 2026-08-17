"""s01b -- dump the LEDGER + prose (md/FINDINGS) hits for each constant, deduplicated.
CSV hits are dropped here: substring matching against float text produces incidental
matches (e.g. '0.00102' inside '0.001023...'). They are counted in s01 but are not
evidence of a *quoted benchmark*; the prose record is.
"""
import json, os, collections

EXPL = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration"
OUT = os.path.join(EXPL, "E1_I0049_benchmark_constants", "raw")
hits = json.load(open(os.path.join(OUT, "_s01_census_hits.json")))

for key in hits:
    rows = [h for h in hits[key] if not h["source"].startswith("CSV:")]
    print("=" * 100)
    print(f"### {key}   non-CSV hits: {len(rows)}")
    print("=" * 100)
    # ledger first
    led = [h for h in rows if h["source"].startswith("LEDGER")]
    seen = set()
    for h in led:
        k = (h["source"], h.get("field"), h["excerpt"][:120])
        if k in seen:
            continue
        seen.add(k)
        print(f"\n--- {h['source']}  field={h.get('field')}  form={h['form']}")
        print("    " + h["excerpt"].replace("\n", "\n    "))
    # prose sources, just names + one excerpt each
    other = [h for h in rows if not h["source"].startswith("LEDGER")]
    bysrc = collections.OrderedDict()
    for h in other:
        bysrc.setdefault(h["source"], []).append(h)
    print(f"\n  [prose sources: {len(bysrc)}]")
    for s, hs in bysrc.items():
        print(f"    {s}  x{len(hs)}   e.g. | {hs[0]['excerpt'][:190]}")
    print()
