"""
ols.py -- Ordinary least squares in plain numpy (Montgomery & Runger, Ch 12).

Replaces statsmodels so the Vercel function stays small. The formulas are the
textbook matrix ones:
    b  = (X'X)^-1 X'y                    least-squares estimates
    SSE = e'e,  MSE = SSE / (n - p)      p = number of parameters (incl. intercept)
    se(b_j) = sqrt(MSE * C_jj),  C = (X'X)^-1
    t0 = b_j / se(b_j)                   test of H0: beta_j = 0
    F0 = (SSR / k) / MSE                 test of significance of regression
    r_i = e_i / sqrt(MSE (1 - h_ii))     standardized (internally studentized) residuals
Results were checked against statsmodels to machine precision (see tests/).
"""
from __future__ import annotations

import numpy as np
from scipy import stats


class OLS:
    def __init__(self, X, y, names=None, add_intercept=True):
        X = np.asarray(X, dtype=float)
        y = np.asarray(y, dtype=float)
        if X.ndim == 1:
            X = X[:, None]
        if add_intercept:
            X = np.column_stack([np.ones(len(y)), X])
            names = ["const"] + list(names or [f"x{i}" for i in range(1, X.shape[1])])
        self.names = list(names or [f"x{i}" for i in range(X.shape[1])])
        self.X, self.y = X, y
        n = X.shape[0]
        p = int(np.linalg.matrix_rank(X))       # rank, so redundant columns don't use up df
        self.n, self.p = n, p
        XtX_inv = np.linalg.pinv(X.T @ X)
        self.params = XtX_inv @ X.T @ y
        self.fitted = X @ self.params
        self.resid = y - self.fitted
        self.ssr = float(self.resid @ self.resid)                 # SSE (error sum of squares)
        self.centered_tss = float(((y - y.mean()) ** 2).sum())    # SST
        self.ess = self.centered_tss - self.ssr                   # SSR (regression)
        self.df_resid = n - p
        self.df_model = p - 1 if add_intercept else p
        self.mse_resid = self.ssr / self.df_resid if self.df_resid > 0 else np.nan
        self.bse = np.sqrt(np.clip(np.diag(XtX_inv) * self.mse_resid, 0, None))
        with np.errstate(divide="ignore", invalid="ignore"):
            self.tvalues = self.params / self.bse
        self.pvalues = 2 * stats.t.sf(np.abs(self.tvalues), self.df_resid)
        self.rsquared = self.ess / self.centered_tss if self.centered_tss > 0 else np.nan
        self.rsquared_adj = 1 - (1 - self.rsquared) * (n - 1) / self.df_resid
        if self.df_model > 0 and self.mse_resid > 0:
            self.fvalue = (self.ess / self.df_model) / self.mse_resid
            self.f_pvalue = stats.f.sf(self.fvalue, self.df_model, self.df_resid)
        else:
            self.fvalue, self.f_pvalue = np.nan, np.nan
        hat = np.einsum("ij,jk,ik->i", X, XtX_inv, X)            # leverages h_ii
        with np.errstate(divide="ignore", invalid="ignore"):
            self.std_resid = self.resid / np.sqrt(self.mse_resid * (1 - hat))

    def conf_int(self, alpha=0.05):
        t = stats.t.ppf(1 - alpha / 2, self.df_resid)
        return np.column_stack([self.params - t * self.bse, self.params + t * self.bse])


def partial_f(reduced: OLS, full: OLS):
    """Extra-sum-of-squares F test: does `full` fit significantly better than `reduced`?"""
    df_num = reduced.df_resid - full.df_resid
    F = ((reduced.ssr - full.ssr) / df_num) / (full.ssr / full.df_resid)
    p = stats.f.sf(F, df_num, full.df_resid)
    return float(F), float(p), int(df_num), int(full.df_resid)


def vif(X) -> list[float]:
    """Variance inflation factor of each column: 1 / (1 - R^2_j)."""
    X = np.asarray(X, dtype=float)
    out = []
    for j in range(X.shape[1]):
        others = np.delete(X, j, axis=1)
        r2 = OLS(others, X[:, j]).rsquared
        out.append(float(1 / (1 - r2)) if r2 < 1 else np.inf)
    return out
