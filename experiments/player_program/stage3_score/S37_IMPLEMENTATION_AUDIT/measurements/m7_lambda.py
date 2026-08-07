"""S37: does the MAE-vs-SQUARED-ERROR train-tail scoring deviation change the selected lambda?

The frozen cards pin: "score the strength-feature head's SQUARED ERROR on the last 20% of
training rows, argmin". S36 computes MEAN ABSOLUTE ERROR. This measures whether the two rules
select different lambdas (and therefore different built feature columns / different shrinkage).
Selection SCORES are never printed -- only the selected lambda, which is a construction constant,
not a performance number.
"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import numpy as np
W = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
N = W + r"\experiments\player_program\stage3_score\S36_IMPLEMENT_ARMS"
sys.path.insert(0, N + r"\runner"); sys.path.insert(0, N + r"\arms")
import runner_constants as K, universe as U
from estimators import fit_ols
import sc01_opp_adj_interacting as SC01
import sc10_form_trend as SC10

u = U.build_universe()

def select(train_idx, grid, score):
    cut = int(round(0.8*len(train_idx))); inner, tail = train_idx[:cut], train_idx[cut:]
    s = {float(l): float(score(l, inner, tail)) for l in grid}
    return min(sorted(s), key=lambda l: (s[l], l))

print("=== SC10 (grid {4,16,64}) ===")
t = SC10.spread_terms(u)
for est, t1, t2 in (("E1_GAME_TOTAL","form_spread_short_env","form_spread_med_env"),
                    ("E2_FINAL_MARGIN_HOME","form_spread_short_net","form_spread_med_net")):
    y = u.games[est].to_numpy(float)
    C = u.games["C_total" if est=="E1_GAME_TOTAL" else "C_margin"].to_numpy(float)
    X = np.column_stack([np.ones(len(y)), C, t[t1], t[t2]])
    pen = np.array([False,False,True,True])
    def mk(loss):
        def f(lam, inner, tail):
            fit = fit_ols(X[inner], y[inner], ridge=lam, penalise=pen)
            r = y[tail] - X[tail] @ fit.coef
            return np.mean(np.abs(r)) if loss=="mae" else np.mean(r**2)
        return f
    for fid in K.FOLD_IDS:
        fold = u.fold(fid)
        a = select(fold["train_idx"], SC10.LAMBDA_GRID, mk("mae"))
        b = select(fold["train_idx"], SC10.LAMBDA_GRID, mk("sse"))
        print("  %-22s %-14s lambda_MAE(as coded)=%g  lambda_SQERR(as carded)=%g  %s" %
              (est, fid, a, b, "DIFFER" if a!=b else "same"))

print()
print("=== SC01 (grid {2,8,32,128}) ===")
cache = {}
for est in ("E2_FINAL_MARGIN_HOME","E1_GAME_TOTAL","E3_HOME_WIN_PROB"):
    col = "strength_total_interacting" if est=="E1_GAME_TOTAL" else "strength_margin_interacting"
    tgt = u.games[est].to_numpy(float)
    C = u.games["C_total" if est=="E1_GAME_TOTAL" else "C_margin"].to_numpy(float)
    def mk(loss):
        def f(lam, inner, tail):
            x = cache.setdefault(lam, SC01.ratings_by_cutoff(u, lam))[col].to_numpy(float)
            X = np.column_stack([np.ones(len(x)), C, x])
            fit = fit_ols(X[inner], tgt[inner])
            r = tgt[tail] - X[tail] @ fit.coef
            return np.mean(np.abs(r)) if loss=="mae" else np.mean(r**2)
        return f
    for fid in K.FOLD_IDS:
        fold = u.fold(fid)
        a = select(fold["train_idx"], SC01.LAMBDA_GRID, mk("mae"))
        b = select(fold["train_idx"], SC01.LAMBDA_GRID, mk("sse"))
        print("  %-22s %-14s lambda_MAE(as coded)=%g  lambda_SQERR(as carded)=%g  %s" %
              (est, fid, a, b, "DIFFER" if a!=b else "same"))
