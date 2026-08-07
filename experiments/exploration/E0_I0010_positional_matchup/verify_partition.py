"""
E0 I0010 -- PARTITION VERIFICATION ON THE ACTUAL OUTPUT BYTES (GRAPH_POLICY 13.2).

For every file this experiment wrote:
  1. if it has a `season` column, assert the set of values is a subset of {2021,2022,2023,2024}
  2. if it has a date column, assert every value falls in 2021-2024
  3. byte-scan for any ISO date in 2025/2026  -> must be ZERO
  4. byte-scan for the bare tokens 2025/2026 -> reported WITH CONTEXT, because prose mentions
     of the excluded seasons in comments/logs are expected and are not data leakage
"""
import os, re, sys
import pandas as pd

OUT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration\E0_I0010_positional_matchup"
OK = {2021, 2022, 2023, 2024}
DATE_BAD = re.compile(rb"20(25|26)-[0-9]{2}-[0-9]{2}")
TOKEN = re.compile(rb"(?<![0-9.])202[56](?![0-9])")

fail = 0
print("file".ljust(34), "seasons_in_data".ljust(26), "date_range".ljust(26), "bad_dates", "bare_tokens")
print("-" * 122)
for fn in sorted(os.listdir(OUT)):
    p = os.path.join(OUT, fn)
    if not os.path.isfile(p):
        continue
    raw = open(p, "rb").read()
    bad = len(DATE_BAD.findall(raw))
    tok = len(TOKEN.findall(raw))
    seas, drange = "-", "-"
    if fn.endswith(".csv"):
        df = pd.read_csv(p)
        if "season" in df.columns:
            s = set(int(x) for x in pd.unique(df["season"].dropna()))
            seas = str(sorted(s))
            if not s <= OK:
                seas += "  <<< VIOLATION"; fail += 1
        for dc in ("game_date", "gdate"):
            if dc in df.columns:
                dv = pd.to_datetime(df[dc])
                drange = "%s..%s" % (dv.min().date(), dv.max().date())
                if dv.dt.year.min() < 2021 or dv.dt.year.max() > 2024:
                    drange += "  <<< VIOLATION"; fail += 1
                break
    if bad:
        fail += 1
    print(fn.ljust(34), seas.ljust(26), drange.ljust(26), str(bad).ljust(9), tok)

print("\n--- context for every bare 2025/2026 token (must all be prose/comments, not data) ---")
for fn in sorted(os.listdir(OUT)):
    p = os.path.join(OUT, fn)
    if not os.path.isfile(p) or fn.endswith((".csv", ".npy")):
        continue
    for i, line in enumerate(open(p, "r", encoding="utf-8", errors="replace"), 1):
        if TOKEN.search(line.encode("utf-8", "replace")):
            print("  %s:%d  %s" % (fn, i, line.rstrip()[:150]))

print("\nRESULT:", "PARTITION VERIFIED CLEAN" if fail == 0 else "PARTITION VIOLATIONS: %d" % fail)
sys.exit(1 if fail else 0)
