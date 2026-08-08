"""S10 -- run the SHIPPED module `d04_protocol.verify_null` end to end at nrep=250.

Two purposes:
  1. the deliverable code is exercised as shipped, not just the in-lab copy;
  2. the demonstration is repeated at a replicate count where the 0.80 CERTIFY/VOID threshold
     is actually stable (se 0.025 rather than 0.052), answering this screen's own defect D-03.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from d04_protocol import DEFAULT_DELTAS, Fit, verify_null      # the SHIPPED module
from lab38 import EXP, OUT, R_DRAWS, SEED, assert_partition, hdr, null_draws, resolve

HEADLINE_SEASONS = (2022, 2023, 2024)
NREP = 250

F = pd.read_parquet(os.path.join(EXP, "E0_I0024_reb_ast_characterisation",
                                 "screen_frame.parquet"))
F["game_date"] = pd.to_datetime(F["game_date"])
assert_partition(F, "E0_I0024")
F = F[F["season"].isin(HEADLINE_SEASONS)].reset_index(drop=True)
BASE = resolve(F, ["ref_mean__y_oreb", "ref_ewma__y_oreb", "ref_trail5__y_oreb",
                   "ref_rate_x_min__y_oreb", "ref_mean_minutes", "ref_trail5_minutes",
                   "ref_pct__y_oreb", "ref_mean_pace", "n_prior", "is_home"],
               10, "B_COMPLETE(y_oreb)")
d = F.dropna(subset=["y_oreb", "R08_player_ra_share"] + BASE).reset_index(drop=True)
assert len(d) == 13784, "row set changed"
y = d["y_oreb"].to_numpy(float)
X = d[BASE].to_numpy(float)
x = d["R08_player_ra_share"].to_numpy(float)
fit = Fit(y, X)
plseas = (d["player_id"].astype(str) + "_" + d["season"].astype(str)).to_numpy()
gd = d["game_date"].to_numpy()
seas = d["season"].to_numpy()

rows, tabs = [], []
for name, (kind, blk) in {"N_CYCLIC": ("N_CYCLIC", None),
                          "N_PSWAP": ("N_SWAP", seas)}.items():
    hdr(f"SHIPPED MODULE, nrep={NREP}  --  {name}  on R08_player_ra_share -> y_oreb")
    rr = np.random.default_rng(SEED + abs(hash(name)) % 100000)
    Xp = null_draws(kind, x, rr, groups=plseas, order_key=gd, blocks=blk, R=R_DRAWS)
    v, pw = verify_null(fit, x, Xp, plseas, seed=SEED + 909, deltas=DEFAULT_DELTAS, nrep=NREP)
    print(pw.pivot_table(index="delta", columns="planted_along", values="power").to_string())
    for k, val in v.items():
        print(f"    {k:38s} = {val}")
    rows.append(dict(null=name, **v))
    tabs.append(pw.assign(null=name))

R = pd.DataFrame(rows)
hdr("CONFIRMATORY SCORECARD AT nrep=250")
cyc = R[R["null"] == "N_CYCLIC"].iloc[0]
psw = R[R["null"] == "N_PSWAP"].iloc[0]
checks = [
    ("ORIGINAL D108 protocol still CERTIFIES N_CYCLIC on the full carrier",
     cyc["ORIGINAL_D108_VERDICT"] == "CERTIFIED",
     f"power_full {cyc['power_on_full_at_best_live']:.3f}, typeI {cyc['type_I_at_zero']:.3f}"),
    ("AMENDED protocol REJECTS N_CYCLIC",
     cyc["VERDICT"] != "USABLE",
     f"{cyc['VERDICT']}; power_dominant {cyc['C2_power_on_dominant_at_best_live']:.3f}, "
     f"null-centre ratio {cyc['null_centre_ratio']:.1f}x"),
    ("AMENDED protocol ACCEPTS N_PSWAP",
     psw["VERDICT"] == "USABLE",
     f"power_dominant {psw['C2_power_on_dominant_at_best_live']:.3f}, "
     f"typeI {psw['type_I_at_zero']:.3f}, null-centre ratio {psw['null_centre_ratio']:.2f}x"),
]
for lab, ok, det in checks:
    print(f"  [{'PASS' if ok else 'FAIL'}]  {lab:62s}  {det}")
print(f"\n  >>> {sum(ok for _, ok, _ in checks)}/3 confirmatory checks landed at nrep={NREP}")

R.to_csv(os.path.join(OUT, "D04_CONFIRM_NREP250.csv"), index=False)
pd.concat(tabs, ignore_index=True).to_csv(
    os.path.join(OUT, "D04_CONFIRM_NREP250_POWER.csv"), index=False)
json.dump(dict(nrep=NREP, checks=[dict(check=a, passed=bool(b), detail=c)
                                  for a, b, c in checks],
               cyclic_verdict=cyc["VERDICT"],
               cyclic_original_verdict=cyc["ORIGINAL_D108_VERDICT"],
               cyclic_power_full=float(cyc["power_on_full_at_best_live"]),
               cyclic_power_dominant=float(cyc["C2_power_on_dominant_at_best_live"]),
               cyclic_null_centre_ratio=float(cyc["null_centre_ratio"]),
               pswap_verdict=psw["VERDICT"],
               pswap_power_dominant=float(psw["C2_power_on_dominant_at_best_live"]),
               pswap_null_centre_ratio=float(psw["null_centre_ratio"])),
          open(os.path.join(OUT, "scripts", "_s10.json"), "w"), indent=1)
print("\nwrote D04_CONFIRM_NREP250.csv, D04_CONFIRM_NREP250_POWER.csv")
