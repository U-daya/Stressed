"""
stats_engine.py -- Every statistical calculation used by the app and the report.

Methods map to IE 320 lectures (Montgomery & Runger, 7th ed.):
  RQ1  Overall stress     : point estimates, t-CI on the mean (Ch 8.2),
                            chi-square CI on the variance (Ch 8.3),
                            one-sample t test (Ch 9.3), proportion z-CI and
                            z test (Ch 8.4 / 9.5)
  RQ2/5 Department differences : single-factor ANOVA (Ch 13.2),
                            Bartlett test for equal variances, Tukey HSD
                            pairwise comparisons, chi-square test of
                            independence (Ch 9.8)
  RQ3  Contributing factors: correlation t test (Ch 11.8), multiple linear
                            regression with t tests on each coefficient and
                            overall F test (Ch 12.1-12.2), standardized coefs
  RQ4  Do factors differ by dept: one-way ANOVA on each factor, per-department
                            correlations, and a partial (extra-sum-of-squares)
                            F test of department-specific slopes (Ch 12.2.2)

Every function returns plain pandas / dict objects so the same code feeds the
web app and the report script. Functions return None (or a dict with an
"error" key) when there is not enough data.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats
from ols import OLS, partial_f, vif

import config as CFG

ALPHA = CFG.ALPHA


# ---------------------------------------------------------------------------
# Data preparation
# ---------------------------------------------------------------------------
def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce types, drop incomplete/out-of-range rows, recompute SI."""
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=CFG.COLUMNS)
    d = df.copy()
    for q in CFG.QUESTIONS:
        if q["kind"] != "category":
            d[q["key"]] = pd.to_numeric(d[q["key"]], errors="coerce")
    d = d.dropna(subset=[q["key"] for q in CFG.QUESTIONS])
    for q in CFG.QUESTIONS:
        k = q["key"]
        if q["kind"] == "category":
            d = d[d[k].isin(q["options"])]
        else:
            d = d[(d[k] >= q["lo"]) & (d[k] <= q["hi"])]
    d["stress_index"] = [CFG.stress_index(a, b) for a, b in
                         zip(d["q2_stress"], d["q3_overwhelm"])]
    d["classification"] = d["stress_index"].apply(CFG.classify)
    d["under_stress"] = (d["classification"] == "Under Stress").astype(int)
    return d.reset_index(drop=True)


def comparison_set(d: pd.DataFrame, min_n: int = 2) -> pd.DataFrame:
    """Rows used for between-department tests: drop 'Other' and tiny groups."""
    d = d[d[CFG.DEPT_COL] != CFG.OTHER_DEPT]
    counts = d[CFG.DEPT_COL].value_counts()
    keep = counts[counts >= min_n].index
    return d[d[CFG.DEPT_COL].isin(keep)]


def collection_progress(d: pd.DataFrame) -> dict:
    counts = d[CFG.DEPT_COL].value_counts().reindex(CFG.DEPARTMENTS, fill_value=0)
    real = counts.drop(CFG.OTHER_DEPT)
    depts_ok = int((real >= CFG.REQ_PER_DEPT).sum())
    return dict(
        n=len(d), counts=counts, depts_meeting=depts_ok,
        total_ok=len(d) >= CFG.REQ_TOTAL_N, depts_ok=depts_ok >= CFG.REQ_MIN_DEPTS,
    )


def describe(d: pd.DataFrame) -> pd.DataFrame:
    cols = [q["key"] for q in CFG.QUESTIONS if q["kind"] != "category"] + ["stress_index"]
    out = d[cols].agg(["count", "mean", "std", "min", "median", "max"]).T
    out.index = [CFG.SHORT[c] for c in out.index]
    out["count"] = out["count"].astype(int)
    return out.round(3)


# ---------------------------------------------------------------------------
# RQ1 -- overall stress level
# ---------------------------------------------------------------------------
def overall_stress(d: pd.DataFrame, mu0: float = CFG.STRESS_THRESHOLD,
                   p0: float = 0.5) -> dict | None:
    x = d["stress_index"].to_numpy(float)
    n = len(x)
    if n < 3:
        return None
    xbar, s = x.mean(), x.std(ddof=1)
    se = s / np.sqrt(n)
    tcrit = stats.t.ppf(1 - ALPHA / 2, n - 1)
    t0 = (xbar - mu0) / se
    p_t = 2 * stats.t.sf(abs(t0), n - 1)

    # CI on variance / std dev (chi-square)
    chi_lo = stats.chi2.ppf(1 - ALPHA / 2, n - 1)
    chi_hi = stats.chi2.ppf(ALPHA / 2, n - 1)
    var_ci = ((n - 1) * s**2 / chi_lo, (n - 1) * s**2 / chi_hi)

    # Proportion Under Stress
    k = int(d["under_stress"].sum())
    phat = k / n
    zcrit = stats.norm.ppf(1 - ALPHA / 2)
    se_p = np.sqrt(phat * (1 - phat) / n)
    z0 = (k - n * p0) / np.sqrt(n * p0 * (1 - p0))
    p_z = 2 * stats.norm.sf(abs(z0))

    return dict(
        n=n, mean=xbar, sd=s, se=se, median=float(np.median(x)),
        t_crit=tcrit, ci_mean=(xbar - tcrit * se, xbar + tcrit * se),
        mu0=mu0, t0=t0, p_t=p_t,
        var=s**2, ci_var=var_ci, ci_sd=(np.sqrt(var_ci[0]), np.sqrt(var_ci[1])),
        k_under=k, phat=phat, z_crit=zcrit,
        ci_p=(max(0.0, phat - zcrit * se_p), min(1.0, phat + zcrit * se_p)),
        p0=p0, z0=z0, p_z=p_z,
        shapiro_p=stats.shapiro(x).pvalue if 3 <= n <= 5000 else np.nan,
    )


# ---------------------------------------------------------------------------
# RQ2 / RQ5 -- do stress levels differ among departments?
# ---------------------------------------------------------------------------
def dept_anova(d: pd.DataFrame, y: str = "stress_index") -> dict | None:
    """Single-factor ANOVA computed exactly as in Lecture 23."""
    dd = comparison_set(d)
    groups = {g: v[y].to_numpy(float) for g, v in dd.groupby(CFG.DEPT_COL)}
    a = len(groups)
    N = sum(len(v) for v in groups.values())
    if a < 2 or N - a < 1:
        return None
    grand = np.concatenate(list(groups.values())).mean()
    ss_tr = sum(len(v) * (v.mean() - grand) ** 2 for v in groups.values())
    ss_e = sum(((v - v.mean()) ** 2).sum() for v in groups.values())
    ss_t = ss_tr + ss_e
    df_tr, df_e = a - 1, N - a
    ms_tr, ms_e = ss_tr / df_tr, ss_e / df_e
    f0 = ms_tr / ms_e if ms_e > 0 else np.inf
    p = stats.f.sf(f0, df_tr, df_e)
    f_crit = stats.f.ppf(1 - ALPHA, df_tr, df_e)

    table = pd.DataFrame({
        "Source": ["Department", "Error", "Total"],
        "DF": [df_tr, df_e, N - 1],
        "Sum of Squares": [ss_tr, ss_e, ss_t],
        "Mean Square": [ms_tr, ms_e, np.nan],
        "F0": [f0, np.nan, np.nan],
        "P-value": [p, np.nan, np.nan],
    })

    tcrit = stats.t.ppf(1 - ALPHA / 2, df_e)
    means = pd.DataFrame([
        dict(Department=g, n=len(v), Mean=v.mean(), SD=v.std(ddof=1) if len(v) > 1 else np.nan,
             **{"SE (pooled)": np.sqrt(ms_e / len(v)),
                "Lower 95%": v.mean() - tcrit * np.sqrt(ms_e / len(v)),
                "Upper 95%": v.mean() + tcrit * np.sqrt(ms_e / len(v)),
                "Effect tau_i": v.mean() - grand,
                "Meets n>=30": len(v) >= CFG.REQ_PER_DEPT})
        for g, v in groups.items()
    ]).sort_values("Mean", ascending=False).reset_index(drop=True)

    out = dict(table=table, means=means, f0=f0, p=p, f_crit=f_crit,
               df=(df_tr, df_e), r2=ss_tr / ss_t if ss_t > 0 else np.nan,
               grand_mean=grand, ms_e=ms_e, a=a, N=N)

    # Equal-variance check (ANOVA assumption)
    if all(len(v) >= 2 for v in groups.values()):
        b = stats.bartlett(*groups.values())
        lev = stats.levene(*groups.values(), center="median")
        out["bartlett"] = (b.statistic, b.pvalue)
        out["levene"] = (lev.statistic, lev.pvalue)
        out["kruskal"] = stats.kruskal(*groups.values())

    # Tukey HSD pairwise comparisons
    names = list(groups.keys())
    if a >= 2 and all(len(v) >= 2 for v in groups.values()):
        th = stats.tukey_hsd(*groups.values())
        ci = th.confidence_interval(1 - ALPHA)
        rows = []
        for i in range(a):
            for j in range(i + 1, a):
                rows.append({
                    "Comparison": f"{names[i]}  vs  {names[j]}",
                    "Difference": groups[names[i]].mean() - groups[names[j]].mean(),
                    "Lower 95%": ci.low[i, j], "Upper 95%": ci.high[i, j],
                    "P-value (adj.)": th.pvalue[i, j],
                    "Significant": th.pvalue[i, j] < ALPHA,
                })
        out["tukey"] = pd.DataFrame(rows)
    return out


def chi_square_dept(d: pd.DataFrame) -> dict | None:
    """Chi-square test of independence: classification x department."""
    dd = comparison_set(d)
    if dd[CFG.DEPT_COL].nunique() < 2:
        return None
    obs = pd.crosstab(dd[CFG.DEPT_COL], dd["classification"])
    for c in ["Under Stress", "Stress-Free"]:
        if c not in obs.columns:
            obs[c] = 0
    obs = obs[["Under Stress", "Stress-Free"]]
    if (obs.sum(axis=0) == 0).any():
        return None
    chi2, p, dof, exp = stats.chi2_contingency(obs.to_numpy(), correction=False)
    exp = pd.DataFrame(exp, index=obs.index, columns=obs.columns)
    prop = (obs["Under Stress"] / obs.sum(axis=1)).rename("% Under Stress") * 100
    return dict(observed=obs, expected=exp.round(2), chi2=chi2, p=p, dof=dof,
                chi_crit=stats.chi2.ppf(1 - ALPHA, dof),
                min_expected=float(exp.to_numpy().min()), pct=prop.round(1))


# ---------------------------------------------------------------------------
# RQ3 -- which factors contribute most?
# ---------------------------------------------------------------------------
def correlations(d: pd.DataFrame, y: str = "stress_index") -> pd.DataFrame | None:
    n = len(d)
    if n < 4:
        return None
    rows = []
    for f in CFG.FACTORS:
        x = d[f].to_numpy(float)
        if np.std(x) == 0:
            continue
        r = np.corrcoef(x, d[y])[0, 1]
        t0 = r * np.sqrt(n - 2) / np.sqrt(max(1e-12, 1 - r**2))
        p = 2 * stats.t.sf(abs(t0), n - 2)
        rows.append({"Factor": CFG.SHORT[f], "key": f, "r": r, "r^2": r**2,
                     "t0": t0, "P-value": p, "Significant": p < ALPHA})
    out = pd.DataFrame(rows)
    return out.reindex(out["r"].abs().sort_values(ascending=False).index).reset_index(drop=True)


def mlr(d: pd.DataFrame, y: str = "stress_index", factors=None) -> dict | None:
    """Multiple linear regression  SI = b0 + b1*x1 + ... + bk*xk + e."""
    factors = [f for f in (factors or CFG.FACTORS) if d[f].std() > 0]
    k = len(factors)
    n = len(d)
    if n < k + 3:
        return None
    model = OLS(d[factors].astype(float).to_numpy(), d[y].astype(float).to_numpy(), names=factors)
    ci = model.conf_int(ALPHA)

    sx = d[factors].std(ddof=1)
    sy = d[y].std(ddof=1)
    coef = pd.DataFrame({
        "Term": ["Intercept"] + [CFG.SHORT[f] for f in factors],
        "key": ["const"] + factors,
        "Estimate": model.params,
        "Std Error": model.bse,
        "t0": model.tvalues,
        "P-value": model.pvalues,
        "Lower 95%": ci[:, 0],
        "Upper 95%": ci[:, 1],
        "Std. Beta": [np.nan] + [model.params[i + 1] * sx[f] / sy for i, f in enumerate(factors)],
    })
    coef["Significant"] = coef["P-value"] < ALPHA
    if k >= 2:
        coef["VIF"] = [np.nan] + vif(d[factors].astype(float).to_numpy())

    anova = pd.DataFrame({
        "Source": ["Regression", "Error", "Total"],
        "DF": [model.df_model, model.df_resid, n - 1],
        "Sum of Squares": [model.ess, model.ssr, model.centered_tss],
        "Mean Square": [model.ess / model.df_model, model.ssr / model.df_resid, np.nan],
        "F0": [model.fvalue, np.nan, np.nan],
        "P-value": [model.f_pvalue, np.nan, np.nan],
    })
    ranking = coef.iloc[1:].assign(abs_beta=lambda t: t["Std. Beta"].abs()) \
        .sort_values("abs_beta", ascending=False).drop(columns="abs_beta")
    return dict(model=model, coef=coef, anova=anova, ranking=ranking,
                r2=model.rsquared, r2_adj=model.rsquared_adj,
                f0=model.fvalue, p=model.f_pvalue, n=n, k=k,
                s=np.sqrt(model.mse_resid),
                fitted=model.fitted, resid=model.resid,
                std_resid=model.std_resid)


# ---------------------------------------------------------------------------
# RQ4 -- do the contributing factors differ among departments?
# ---------------------------------------------------------------------------
def factor_means_by_dept(d: pd.DataFrame) -> pd.DataFrame | None:
    """Mean of each factor per department + one-way ANOVA F test per factor."""
    dd = comparison_set(d)
    if dd[CFG.DEPT_COL].nunique() < 2:
        return None
    rows = []
    for f in CFG.FACTORS + ["stress_index"]:
        groups = [v[f].to_numpy(float) for _, v in dd.groupby(CFG.DEPT_COL)]
        try:
            fs = stats.f_oneway(*groups)
            F, p = fs.statistic, fs.pvalue
        except Exception:
            F, p = np.nan, np.nan
        row = {"Variable": CFG.SHORT[f], "key": f}
        row.update(dd.groupby(CFG.DEPT_COL)[f].mean().round(2).to_dict())
        row.update({"F0": F, "P-value": p, "Differs?": bool(p < ALPHA) if p == p else False})
        rows.append(row)
    return pd.DataFrame(rows)


def dept_correlations(d: pd.DataFrame, min_n: int = 5) -> tuple[pd.DataFrame, pd.DataFrame] | None:
    """Correlation of each factor with SI inside each department (r and p)."""
    dd = comparison_set(d, min_n=min_n)
    if dd.empty:
        return None
    r_tab, p_tab = {}, {}
    for g, v in dd.groupby(CFG.DEPT_COL):
        r_tab[g], p_tab[g] = {}, {}
        for f in CFG.FACTORS:
            if v[f].std() == 0 or v["stress_index"].std() == 0:
                r_tab[g][CFG.SHORT[f]], p_tab[g][CFG.SHORT[f]] = np.nan, np.nan
                continue
            r, p = stats.pearsonr(v[f], v["stress_index"])
            r_tab[g][CFG.SHORT[f]], p_tab[g][CFG.SHORT[f]] = r, p
    return pd.DataFrame(r_tab), pd.DataFrame(p_tab)


def dept_mlr(d: pd.DataFrame) -> pd.DataFrame | None:
    """Separate MLR inside each department: coefficient (and * if p < alpha)."""
    dd = comparison_set(d, min_n=len(CFG.FACTORS) + 4)
    if dd.empty:
        return None
    cols = {}
    for g, v in dd.groupby(CFG.DEPT_COL):
        res = mlr(v)
        if res is None:
            continue
        c = res["coef"].set_index("key")
        cols[g] = {CFG.SHORT[f]: (f"{c.loc[f, 'Estimate']:+.2f}" +
                                ("*" if c.loc[f, "P-value"] < ALPHA else ""))
                   if f in c.index else "-" for f in CFG.FACTORS}
        cols[g]["R^2"] = f"{res['r2']:.3f}"
        cols[g]["n"] = str(res["n"])
    return pd.DataFrame(cols) if cols else None


def slopes_differ_test(d: pd.DataFrame) -> dict | None:
    """
    Partial F test (extra sum of squares, Montgomery 12.2.2):
      Reduced model : SI ~ factors + department          (same slopes everywhere)
      Full model    : SI ~ (factors) * department        (department-specific slopes)
      H0: all factor x department interaction coefficients are 0
    Rejecting H0 means the factors influence stress differently by department.
    """
    dd = comparison_set(d, min_n=3)
    a = dd[CFG.DEPT_COL].nunique()
    k = len(CFG.FACTORS)
    if a < 2 or len(dd) <= a * (k + 1) + 2:
        return None
    Xf = dd[CFG.FACTORS].astype(float).to_numpy()
    y = dd["stress_index"].astype(float).to_numpy()
    levels = sorted(dd[CFG.DEPT_COL].unique())
    # dummy (indicator) variables for departments, first level = baseline
    D = np.column_stack([(dd[CFG.DEPT_COL] == g).to_numpy(float) for g in levels[1:]])
    inter = np.column_stack([Xf[:, [j]] * D for j in range(k)])   # factor x department terms
    no_dept = OLS(Xf, y)                                          # SI ~ factors
    reduced = OLS(np.column_stack([Xf, D]), y)                    # SI ~ factors + department
    full = OLS(np.column_stack([Xf, D, inter]), y)                # SI ~ factors * department
    F, p, df_num, df_den = partial_f(reduced, full)
    F_dept, p_dept, d1, d2 = partial_f(no_dept, reduced)
    return dict(F=F, p=p, df=(df_num, df_den),
                r2_reduced=reduced.rsquared, r2_full=full.rsquared,
                sse_reduced=reduced.ssr, sse_full=full.ssr,
                F_dept=F_dept, p_dept=p_dept, df_dept=(d1, d2),
                n=len(dd), a=a)


# ---------------------------------------------------------------------------
# Personal feedback shown after a student submits
# ---------------------------------------------------------------------------
def personal_flags(ans: dict) -> list[str]:
    """Plain-language notes on the respondent's own risk factors."""
    notes = []
    if ans["q4_sleep"] < 7:
        notes.append(f"You sleep about {ans['q4_sleep']:g} h/night; adults are "
                     "generally advised to get at least 7.")
    if ans["q7_exercise"] <= 1:
        notes.append("You exercise on 0-1 days a week; regular activity is linked to lower stress.")
    if ans["q8_nutrition"] <= 2:
        notes.append("You rate your eating habits as poor.")
    if ans["q9_finance"] >= 4:
        notes.append("You report high financial worry.")
    if ans["q5_credits"] >= 18:
        notes.append(f"You are taking {ans['q5_credits']:g} credits, a heavy course load.")
    if ans["q6_study"] >= 30:
        notes.append(f"You study about {ans['q6_study']:g} h/week outside class.")
    return notes
