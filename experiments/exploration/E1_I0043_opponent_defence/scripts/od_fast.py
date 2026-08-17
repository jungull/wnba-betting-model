"""
Fast EXACT walk-forward dR2, and the cells built on it.

WHY IT IS EXACT.  By Frisch-Waugh-Lovell, adding one column d to a base X and refitting gives
    y_hat_aug(te) = X_te b_base + g * d~_te ,   g = (d~_tr . e_tr) / (d~_tr . d~_tr)
where d~ = d - X (X'X)^-1 X' d is d residualised on the TRAINING base and e_tr is the training
base residual.  Nothing is approximated: the same coefficients come out.  The point is that the
base projector is computed ONCE per fold instead of once per null draw, which is what makes an
injection study with 200 replicates x 200 draws affordable.

`assert_fast_equals_lstsq` checks this against a literal `np.linalg.lstsq` refit on real data before
any statistic is produced.  If it ever disagrees past 1e-11 the screen halts.
"""
import numpy as np

FROZEN, UNFROZEN, INTERCEPT_ONLY = "FROZEN", "UNFROZEN", "INTERCEPT_ONLY"


class FoldPack:
    """Everything about a fold that does NOT depend on the candidate column."""

    def __init__(self, Xb_tr, Xb_te, y_tr, y_te, idx_te, P=None):
        self.Xb_tr, self.Xb_te = Xb_tr, Xb_te
        self.y_tr, self.y_te, self.idx_te = y_tr, y_te, idx_te
        self.tr = None
        # P does not depend on the response, so a synthetic-response copy reuses it verbatim.
        self.P = (np.linalg.pinv(Xb_tr.T @ Xb_tr) @ Xb_tr.T) if P is None else P
        self.b_base = self.P @ y_tr
        self.yb_te = Xb_te @ self.b_base
        self.e_tr = y_tr - Xb_tr @ self.b_base
        self.c_intercept = float(self.e_tr.mean())


class FastCell:
    """One preregistered cell.  Response, rows, folds, base and SST are fixed at construction and
    NOTHING but the candidate's VALUES may change between draws (the D101 denominator rule, as an
    object rather than as a promise)."""

    def __init__(self, packs, arm, dvals_full, tr_masks, te_masks):
        self.packs, self.arm = packs, arm
        self.d_full = dvals_full
        self.tr_masks, self.te_masks = tr_masks, te_masks
        self.y = np.concatenate([p.y_te for p in packs])
        self.yb = np.concatenate([p.yb_te for p in packs])
        self.sst = float(((self.y - self.y.mean()) ** 2).sum())
        self.sse_base = float(((self.y - self.yb) ** 2).sum())
        self.n = len(self.y)
        self.n_folds = len(packs)

    def _pred(self, d_full):
        outs, betas = [], []
        for p, trm, tem in zip(self.packs, self.tr_masks, self.te_masks):
            if self.arm == INTERCEPT_ONLY:
                outs.append(p.yb_te + p.c_intercept)
                betas.append(p.c_intercept)
                continue
            d_tr, d_te = d_full[trm], d_full[tem]
            dbar = float(d_tr.mean())
            d_tr = d_tr - dbar
            d_te = d_te - dbar
            if self.arm == UNFROZEN:
                cf = p.P @ d_tr
                dt_tr = d_tr - p.Xb_tr @ cf
                dt_te = d_te - p.Xb_te @ cf
                den = float(dt_tr @ dt_tr)
                g = float(dt_tr @ p.e_tr) / den if den > 1e-12 else 0.0
                outs.append(p.yb_te + g * dt_te)
            elif self.arm == FROZEN:
                den = float(d_tr @ d_tr)
                g = float(d_tr @ p.e_tr) / den if den > 1e-12 else 0.0
                outs.append(p.yb_te + g * d_te)
            else:
                raise ValueError(self.arm)
            betas.append(g)
        return np.concatenate(outs), float(np.mean(betas))

    def dr2(self, d_full=None):
        ya, _ = self._pred(self.d_full if d_full is None else d_full)
        return (self.sse_base - float(((self.y - ya) ** 2).sum())) / self.sst

    def full(self):
        ya, beta = self._pred(self.d_full)
        sse_a = float(((self.y - ya) ** 2).sum())
        return dict(dr2=(self.sse_base - sse_a) / self.sst, sst=self.sst, n=self.n,
                    sse_base=self.sse_base, sse_aug=sse_a, beta=beta, n_folds=self.n_folds,
                    rmse_base=float(np.sqrt(((self.y - self.yb) ** 2).mean())),
                    rmse_aug=float(np.sqrt(((self.y - ya) ** 2).mean())))

    def with_response(self, ynew_by_fold):
        """A copy of this cell with a synthetic response.  Rows, folds and base are untouched."""
        packs = [FoldPack(p.Xb_tr, p.Xb_te, yt, ye, p.idx_te, P=p.P)
                 for p, (yt, ye) in zip(self.packs, ynew_by_fold)]
        return FastCell(packs, self.arm, self.d_full, self.tr_masks, self.te_masks)


def build_packs(v, basecols, yname, mask, eval_seasons, ssn, min_tr=300, min_te=80):
    packs, trm, tem = [], [], []
    for s in eval_seasons:
        tr, te = mask & (ssn < s), mask & (ssn == s)
        if tr.sum() < min_tr or te.sum() < min_te:
            continue
        Xb_tr = np.column_stack([np.ones(int(tr.sum()))] + [v[c][tr] for c in basecols])
        Xb_te = np.column_stack([np.ones(int(te.sum()))] + [v[c][te] for c in basecols])
        packs.append(FoldPack(Xb_tr, Xb_te, v[yname][tr], v[yname][te], np.flatnonzero(te)))
        trm.append(tr)
        tem.append(te)
    return packs, trm, tem


def assert_fast_equals_lstsq(v, basecols, yname, dname, mask, eval_seasons, ssn, tol=1e-11):
    """Machinery validation against a literal refit.  Runs before any statistic is produced."""
    packs, trm, tem = build_packs(v, basecols, yname, mask, eval_seasons, ssn)
    fast = FastCell(packs, UNFROZEN, v[dname], trm, tem).dr2()
    y_all, yb_all, ya_all = [], [], []
    for s in eval_seasons:
        tr, te = mask & (ssn < s), mask & (ssn == s)
        if tr.sum() < 300 or te.sum() < 80:
            continue
        Xb_tr = np.column_stack([np.ones(int(tr.sum()))] + [v[c][tr] for c in basecols])
        Xb_te = np.column_stack([np.ones(int(te.sum()))] + [v[c][te] for c in basecols])
        dbar = float(v[dname][tr].mean())
        Xa_tr = np.column_stack([Xb_tr, v[dname][tr] - dbar])
        Xa_te = np.column_stack([Xb_te, v[dname][te] - dbar])
        bb = np.linalg.lstsq(Xb_tr, v[yname][tr], rcond=None)[0]
        ba = np.linalg.lstsq(Xa_tr, v[yname][tr], rcond=None)[0]
        y_all.append(v[yname][te])
        yb_all.append(Xb_te @ bb)
        ya_all.append(Xa_te @ ba)
    y = np.concatenate(y_all)
    sst = float(((y - y.mean()) ** 2).sum())
    slow = (float(((y - np.concatenate(yb_all)) ** 2).sum())
            - float(((y - np.concatenate(ya_all)) ** 2).sum())) / sst
    d = abs(fast - slow)
    assert d < tol, "FAST/SLOW DISAGREE by %.3e (fast %.12f slow %.12f)" % (d, fast, slow)
    return fast, slow, d
