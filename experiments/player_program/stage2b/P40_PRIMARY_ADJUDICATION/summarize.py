import json
from pathlib import Path

OUT = Path(r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\player_program\stage2b\P40_PRIMARY_ADJUDICATION")
ex = json.loads((OUT / "EXTRACTION.json").read_text(encoding="utf-8"))

for name, e in ex["elements"].items():
    r = e.get("receipt")
    if not r:
        print(f"{name}: NO RECEIPT (records only)")
        continue
    res = r["results"] or {}
    pooled = res.get("pooled") or {}
    print(f"{name}")
    print(f"  evaluable={res.get('evaluable_folds')} deactivated={res.get('structurally_deactivated_folds')}")
    print(f"  pooled delta_mae={pooled.get('delta_mae')} p={pooled.get('p_two_sided')} n_rows={pooled.get('n_rows')} mae_arm={pooled.get('mae_arm')} mae_null={pooled.get('mae_null')}")
    if r.get("extra_top_level"):
        print(f"  EXTRA TOP KEYS: {list(r['extra_top_level'].keys())}")
    for fid, fb in (r.get("folds") or {}).items():
        t = fb.get("test") or {}
        ivs = fb.get("arm_intervals") or {}
        iv_s = {k: (round(v['lo'], 5), round(v['hi'], 5)) for k, v in ivs.items()} if ivs else {}
        beta = fb.get("arm_point_beta")
        beta_r = [round(b, 5) for b in beta] if beta else beta
        extra = fb.get("extra_keys")
        print(f"    {fid}: status={fb.get('status')} dmae={t.get('delta_mae')} p={t.get('p_two_sided')} beta={beta_r} cols={fb.get('arm_point_columns')} iv={iv_s} na={fb.get('n_na_draws')} extra={extra}")
    print()
