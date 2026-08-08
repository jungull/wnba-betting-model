import pandas as pd, re, os
HERE=r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration\E1_I0040_audit_extension"
L=pd.read_csv(os.path.join(HERE,"MAX_SIGNATURE_LOOSE.csv"))
print("total loose hits:",len(L))
# strip pure print/format/docstring lines and max-T family-wise (legitimate: max over CELLS within ONE null)
noise=re.compile(r"^\s*(print|#|\"|')|\.max\(\)\s*[,)]|max date|max abs|max_err|max\|reprod|max-T|maxT|max-statistic|max spec|f\"|%s|%d|%.")
cand=L[~L.code.str.contains(r"print\(|max-T|maxT|max-statistic|max date|max abs|max_err|\bmax=|max spec|MAX \|",case=False,regex=True)]
print("after removing prints / max-T family-wise:",len(cand))
# now require TWO distinct p-like tokens or two null-scheme names on the same line
two_p=re.compile(r"p_[a-z0-9]+.*[,\s].*p_[a-z0-9]+",re.I)
schemes=re.compile(r"(cyclic|within).*(swap|eswap|pswap|between|row|signflip)|(swap|eswap|pswap|between|row|signflip).*(cyclic|within)",re.I)
hot=cand[cand.code.str.contains(two_p)|cand.code.str.contains(schemes)]
print("lines combining two p-values or two schemes with max():",len(hot))
pd.set_option("display.width",250)
for _,rr in hot.iterrows(): print(f"  {rr.screen} :: {rr.file}:{rr.line}\n     {rr.code}")
cand.to_csv(os.path.join(HERE,"MAX_SIGNATURE_LOOSE_FILTERED.csv"),index=False)
print("\n--- remaining candidate lines (first 60) ---")
for _,rr in cand.head(60).iterrows(): print(f"  {rr.screen}:{rr.line} | {rr.code[:150]}")
