"""
views.py -- Turns the statistical results into page content for the browser.

The results page is a list of tabs; each tab is a list of "blocks"
(heading, text, metrics, table, verdict, warning, plot). The browser
(public/app.js) only draws them -- every calculation happens here in Python,
through stats_engine.py.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

import charts as G
import config as C
import stats_engine as S

RED, GREEN = "#CC0033", "#1F8A7A"
CMAP = {"Under Stress": RED, "Stress-Free": GREEN}


# ---------------------------------------------------------------------------
# Block helpers
# ---------------------------------------------------------------------------
def fmt_p(p) -> str:
    if p is None or (isinstance(p, float) and np.isnan(p)):
        return ""
    return "< 0.0001" if p < 1e-4 else f"{p:.4f}"


def h(text): return {"type": "h", "text": text}
def md(text): return {"type": "md", "text": text}
def warn(text): return {"type": "warn", "text": text}
def metrics(items): return {"type": "metrics", "items": [[a, b] for a, b in items]}


def verdict(p, yes, no):
    if p < C.ALPHA:
        return {"type": "verdict", "ok": True,
                "text": f"**Reject H₀** (P = {fmt_p(p)} < α = {C.ALPHA}). {yes}"}
    return {"type": "verdict", "ok": False,
            "text": f"**Fail to reject H₀** (P = {fmt_p(p)} ≥ α = {C.ALPHA}). {no}"}


def table(df: pd.DataFrame, digits=4, index=False, pcols=("P-value", "P-value (adj.)")):
    t = df.reset_index() if index else df.copy()
    t = t.drop(columns=[c for c in ("key",) if c in t.columns])
    rows = []
    for _, r in t.iterrows():
        row = []
        for c in t.columns:
            v = r[c]
            if c in pcols:
                row.append(fmt_p(v))
            elif isinstance(v, (bool, np.bool_)):
                row.append("✔" if v else "")
            elif isinstance(v, (float, np.floating)):
                row.append("" if np.isnan(v) else f"{v:.{digits}f}".rstrip("0").rstrip("."))
            elif isinstance(v, (int, np.integer)):
                row.append(str(int(v)))
            else:
                row.append("" if v is None else str(v))
        rows.append(row)
    return {"type": "table", "columns": [str(c) for c in t.columns], "rows": rows}


def plot(fig):
    return {"type": "plot", "fig": fig}


def sanitize(o):
    """Make the payload strict-JSON safe: numpy -> Python, NaN/inf -> None."""
    if isinstance(o, dict):
        return {str(k): sanitize(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [sanitize(v) for v in o]
    if isinstance(o, np.ndarray):
        return [sanitize(v) for v in o.tolist()]
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (float, np.floating)):
        return None if not np.isfinite(o) else float(o)
    return o


# ---------------------------------------------------------------------------
# Questionnaire (for building the survey form in the browser)
# ---------------------------------------------------------------------------
def questions_payload():
    return {"title": C.APP_TITLE, "group": C.GROUP_NAME, "questions": C.QUESTIONS,
            "threshold": C.STRESS_THRESHOLD}


# ---------------------------------------------------------------------------
# Result shown to a student right after submitting
# ---------------------------------------------------------------------------
def personal_result(row: dict, d: pd.DataFrame) -> dict:
    out = {"stress_index": row["stress_index"], "classification": row["classification"],
           "threshold": C.STRESS_THRESHOLD, "notes": S.personal_flags(row)}
    if len(d) >= 5:
        same = d[d[C.DEPT_COL] == row["q1_dept"]]
        out.update(
            percentile=float(stats.percentileofscore(d["stress_index"], row["stress_index"], kind="weak")),
            n=len(d), dept=row["q1_dept"], dept_mean=float(same["stress_index"].mean()),
            dept_n=len(same), overall_mean=float(d["stress_index"].mean()))
    return out


# ---------------------------------------------------------------------------
# Results page
# ---------------------------------------------------------------------------
def results_payload(d: pd.DataFrame, storage_name: str) -> dict:
    prog = S.collection_progress(d)
    counts = prog["counts"]
    fig = G.hbar(list(counts.index), counts.values, text=counts.values, xtitle="Responses", height=300)
    G.vline(fig["layout"], C.REQ_PER_DEPT, f"{C.REQ_PER_DEPT} needed", dash="dash", color="#555")
    progress = [
        metrics([("Total responses", f"{prog['n']}  (goal {C.REQ_TOTAL_N})"),
                 (f"Departments with ≥{C.REQ_PER_DEPT}", f"{prog['depts_meeting']}  (goal {C.REQ_MIN_DEPTS})"),
                 ("Requirements met", "Yes ✅" if prog["total_ok"] and prog["depts_ok"] else "Not yet")]),
        plot(fig),
    ]
    payload = {"n": prog["n"], "storage": storage_name, "alpha": C.ALPHA,
               "progress": progress, "tabs": []}
    if prog["n"] < 5:
        return payload
    tabs = payload["tabs"]
    tabs.append({"name": "RQ1 Overall stress", "blocks": _rq1(d)})
    tabs.append({"name": "RQ2/5 Departments", "blocks": _rq2(d)})
    tabs.append({"name": "RQ3 Factors", "blocks": _rq3(d)})
    tabs.append({"name": "RQ4 Factors by department", "blocks": _rq4(d)})
    tabs.append({"name": "Descriptive stats", "blocks": _desc(d)})
    tabs.append({"name": "Classification summary", "blocks": _cls(d)})
    return payload


def _rq1(d):
    r = S.overall_stress(d)
    b = [h("RQ1. What is the overall stress level of the students surveyed?"),
         metrics([("Mean Stress Index", f"{r['mean']:.2f}"),
                   ("95% CI for μ", f"{r['ci_mean'][0]:.1f} – {r['ci_mean'][1]:.1f}"),
                   ("% Under Stress", f"{100 * r['phat']:.1f}%"),
                   ("95% CI for p", f"{100 * r['ci_p'][0]:.0f}% – {100 * r['ci_p'][1]:.0f}%")])]
    fig = G.class_histogram(d["stress_index"], d["classification"], r["mean"], C.STRESS_THRESHOLD)
    b.append(plot(fig))
    b.append(md("**Point estimates and confidence intervals**"))
    b.append(table(pd.DataFrame([
        ["Mean μ", "x̄", r["mean"], f"t-interval, t(0.025, {r['n']-1}) = {r['t_crit']:.3f}", *r["ci_mean"]],
        ["Std. dev. σ", "s", r["sd"], f"χ²-interval, {r['n']-1} df", *r["ci_sd"]],
        ["Variance σ²", "s²", r["var"], f"χ²-interval, {r['n']-1} df", *r["ci_var"]],
        ["Proportion Under Stress p", "p̂", r["phat"], "large-sample z-interval", *r["ci_p"]],
    ], columns=["Parameter", "Estimator", "Estimate", "Method", "Lower 95%", "Upper 95%"])))
    b.append(md(f"**Test 1. One-sample t test.** H₀: μ = {r['mu0']:g} vs H₁: μ ≠ {r['mu0']:g}  \n"
                f"t₀ = (x̄ − μ₀)/(s/√n) = ({r['mean']:.2f} − {r['mu0']:g}) / ({r['sd']:.2f}/√{r['n']}) "
                f"= **{r['t0']:.3f}**, df = {r['n']-1}, critical ±{r['t_crit']:.3f}"))
    b.append(verdict(r["p_t"], f"Mean stress differs from the scale midpoint ({'above' if r['mean'] > r['mu0'] else 'below'} it).",
                     "No evidence that mean stress differs from the scale midpoint."))
    b.append(md(f"**Test 2. Test on a proportion.** H₀: p = {r['p0']} vs H₁: p ≠ {r['p0']}  \n"
                f"z₀ = (X − np₀)/√(np₀(1−p₀)) = ({r['k_under']} − {r['n']}·{r['p0']}) / "
                f"√({r['n']}·{r['p0']}·{1-r['p0']}) = **{r['z0']:.3f}**"))
    b.append(verdict(r["p_z"], f"The share of students Under Stress is {'more' if r['phat'] > r['p0'] else 'less'} than half.",
                     "No evidence that the share Under Stress differs from one half."))
    b.append(md(f"*Normality check (Shapiro–Wilk) P = {fmt_p(r['shapiro_p'])}. With n = {r['n']}, "
                "the CLT makes the t procedures robust to moderate non-normality.*"))
    return b


def _rq2(d):
    b = [h("RQ2 & RQ5. Do stress levels differ among departments, and is it significant?")]
    a = S.dept_anova(d)
    if a is None:
        return b + [warn("Need responses from at least two departments (excluding 'Other').")]
    dd = S.comparison_set(d)
    order = a["means"]["Department"].tolist()
    groups = {g: dd.loc[dd[C.DEPT_COL] == g, "stress_index"].to_numpy() for g in order}
    fig = G.box_by_group(groups, a["means"]["Mean"], title="Stress Index by department (◆ = mean)")
    b.append(plot(fig))
    b.append(md("**Single-factor ANOVA:** Y<sub>ij</sub> = μ + τ<sub>i</sub> + ε<sub>ij</sub>,  "
                "H₀: τ₁ = τ₂ = … = τ<sub>a</sub> = 0  vs  H₁: τ<sub>i</sub> ≠ 0 for at least one i"))
    b.append(table(a["table"]))
    b.append(md(f"F₀ = MS<sub>Treatments</sub> / MS<sub>E</sub> = **{a['f0']:.3f}**, critical "
                f"F(0.05, {a['df'][0]}, {a['df'][1]}) = {a['f_crit']:.3f}, R² = {a['r2']:.3f}"))
    b.append(verdict(a["p"], "Mean stress differs among at least two departments.",
                     "No significant difference in mean stress among departments."))
    b.append(md("**Department means with 95% CIs** (pooled MS<sub>E</sub>, as in Lecture 23)"))
    b.append(table(a["means"]))
    ci = a["means"]
    fig = G.ci_plot(ci["Department"], ci["Mean"], ci["Lower 95%"], ci["Upper 95%"], ref=a["grand_mean"],
                    ref_text="grand mean", title="95% confidence intervals for department means",
                    xtitle="Stress Index")
    b.append(plot(fig))
    if not ci["Meets n>=30"].all():
        b.append(warn("Some departments have fewer than 30 responses; treat their results as preliminary."))
    if "tukey" in a:
        b.append(md("**Tukey HSD pairwise comparisons** (which departments differ?)"))
        b.append(table(a["tukey"]))
    if "bartlett" in a:
        bt, lv, kw = a["bartlett"], a["levene"], a["kruskal"]
        b.append(md(f"**Assumption check, equal variances.** Bartlett χ² = {bt[0]:.3f}, P = {fmt_p(bt[1])}; "
                    f"Levene F = {lv[0]:.3f}, P = {fmt_p(lv[1])}. "
                    f"{'Equal-variance assumption looks reasonable.' if lv[1] >= C.ALPHA else 'Variances differ; confirm with the Kruskal–Wallis test below.'}  \n"
                    f"Nonparametric check: Kruskal–Wallis H = {kw.statistic:.3f}, P = {fmt_p(kw.pvalue)}."))
    chi = S.chi_square_dept(d)
    if chi:
        b.append(md("**Chi-square test of independence:** is the Under Stress / Stress-Free "
                    "classification independent of department?"))
        b.append(md("*Observed counts*"))
        b.append(table(chi["observed"].assign(**{"% Under Stress": chi["pct"]}), index=True, digits=1))
        b.append(md("*Expected counts under H₀*"))
        b.append(table(chi["expected"], index=True, digits=2))
        b.append(md(f"χ²₀ = **{chi['chi2']:.3f}**, df = {chi['dof']}, critical χ²(0.05, {chi['dof']}) = {chi['chi_crit']:.3f}"))
        b.append(verdict(chi["p"], "The proportion Under Stress depends on department.",
                         "No evidence that the proportion Under Stress depends on department."))
        if chi["min_expected"] < 5:
            b.append(warn("Some expected counts are below 5, so the χ² approximation is less reliable."))
    return b


def _rq3(d):
    b = [h("RQ3. Which factors contribute most strongly to student stress?")]
    cor = S.correlations(d)
    m = S.mlr(d)
    if cor is not None:
        b.append(md("**Step 1. Correlation of each factor with the Stress Index** "
                    "(H₀: ρ = 0, t₀ = r√(n−2)/√(1−r²))"))
        fig = G.hbar(cor["Factor"], cor["r"], colors=[RED if v else G.GREY for v in cor["Significant"]],
                     xtitle="Pearson r with Stress Index",
                     legend=[("significant", RED), ("not significant", G.GREY)])
        b.append(plot(fig))
        b.append(table(cor))
    if m is None:
        return b + [warn("Need more responses for the multiple regression.")]
    b.append(md("**Step 2. Multiple linear regression** (each factor's effect holding the others constant)"))
    eq = " ".join(f"{'+' if v >= 0 else '−'} {abs(v):.3f}·{C.SHORT[k].split(' (')[0]}"
                  for k, v in zip(m["coef"]["key"][1:], m["coef"]["Estimate"][1:]))
    b.append(md(f"<code>SI-hat = {m['coef']['Estimate'][0]:.2f} {eq}</code>"))
    b.append(metrics([("R²", f"{m['r2']:.3f}"), ("Adjusted R²", f"{m['r2_adj']:.3f}"),
                      ("F₀ (overall)", f"{m['f0']:.2f}"), ("P-value", fmt_p(m["p"]))]))
    b.append(md("ANOVA for significance of regression (H₀: β₁ = … = β<sub>k</sub> = 0)"))
    b.append(table(m["anova"]))
    b.append(md("Coefficient t tests (H₀: β<sub>j</sub> = 0). **Std. Beta** puts all factors on the same "
                "scale, so |Std. Beta| ranks importance."))
    b.append(table(m["coef"]))
    rk = m["ranking"]
    fig = G.hbar(rk["Term"], rk["Std. Beta"], colors=[RED if v else G.GREY for v in rk["Significant"]],
                 title="Factor importance (standardized coefficients)", xtitle="Std. Beta",
                 legend=[("significant", RED), ("not significant", G.GREY)])
    b.append(plot(fig))
    sig = m["ranking"][m["ranking"]["Significant"]]
    if len(sig):
        b.append({"type": "verdict", "ok": True, "text": "**Significant contributors, strongest first:** " + "; ".join(
            f"{t} ({'raises' if v > 0 else 'lowers'} stress)" for t, v in zip(sig["Term"], sig["Std. Beta"]))})
    else:
        b.append({"type": "verdict", "ok": False,
                  "text": "No individual factor is significant at α = 0.05 in the multiple regression yet."})

    b.append(md("**Model adequacy (residual analysis)**"))
    osm, osr = stats.probplot(m["std_resid"], dist="norm", fit=False)
    f1 = G.scatter(osm, osr, title="Normal probability plot of residuals",
                   xtitle="Theoretical normal quantiles", ytitle="Standardized residuals",
                   line=([osm.min(), osm.max()], [osm.min(), osm.max()]))
    f2 = G.scatter(m["fitted"], m["std_resid"], title="Residuals vs fitted values",
                   xtitle="Fitted Stress Index", ytitle="Standardized residuals", hline0=True)
    b.append({"type": "row", "blocks": [plot(f1), plot(f2)]})
    if "VIF" in m["coef"] and m["coef"]["VIF"].max() > 5:
        b.append(warn("A VIF above 5 signals multicollinearity among predictors."))

    opts = []
    for f in C.FACTORS:
        fig = G.scatter_by_group(d, f, "stress_index", C.DEPT_COL, C.SHORT[f], "Stress Index")
        opts.append({"label": C.SHORT[f], **plot(fig)})
    b.append(md("**Explore one factor (simple linear regression)**"))
    b.append({"type": "plotselect", "options": opts})
    return b


def _rq4(d):
    b = [h("RQ4. Do the factors influencing stress differ among departments?")]
    sd = S.slopes_differ_test(d)
    if sd:
        b.append(md("**Partial F test (extra sum of squares).** Compares a model where every factor has the "
                    "*same* effect in all departments with one where each department has its *own* slopes.  \n"
                    "H₀: all factor × department interaction coefficients = 0"))
        b.append(table(pd.DataFrame([
            ["Reduced: SI ~ factors + department", sd["r2_reduced"], sd["sse_reduced"]],
            ["Full: SI ~ factors × department", sd["r2_full"], sd["sse_full"]]],
            columns=["Model", "R²", "SSE"])))
        b.append(md(f"F₀ = **{sd['F']:.3f}** with ({sd['df'][0]}, {sd['df'][1]}) df"))
        b.append(verdict(sd["p"], "The effect of at least one factor on stress differs between departments.",
                         "No evidence that factor effects differ by department; one common model fits all departments."))
        b.append(md(f"Does department still matter **after** controlling for the factors? "
                    f"F₀ = {sd['F_dept']:.3f} ({sd['df_dept'][0]}, {sd['df_dept'][1]} df), P = {fmt_p(sd['p_dept'])}."))
    else:
        b.append(warn("Need more responses per department for the partial F test."))
    dc = S.dept_correlations(d)
    if dc:
        r_tab, p_tab = dc
        txt = r_tab.map(lambda v: "" if pd.isna(v) else f"{v:.2f}") + np.where(p_tab < C.ALPHA, "*", "")
        fig = G.heatmap(r_tab.values, list(r_tab.columns), list(r_tab.index), txt.values.tolist(),
                        title="Correlation of each factor with Stress Index, within each department (* P < 0.05)")
        b.append(plot(fig))
    dm = S.dept_mlr(d)
    if dm is not None:
        b.append(md("**Separate multiple regression in each department** (coefficient, * = significant)"))
        b.append(table(dm.rename_axis("Factor"), index=True))
    fm = S.factor_means_by_dept(d)
    if fm is not None:
        b.append(md("**Do departments differ in the factors themselves?** (mean per department + one-way ANOVA)"))
        b.append(table(fm))
    return b


def _desc(d):
    b = [h("Descriptive statistics"),
         table(S.describe(d).reset_index().rename(columns={"index": "Variable"}), digits=3)]
    cols = C.FACTORS + ["q2_stress", "q3_overwhelm", "stress_index"]
    corr = d[cols].corr().rename(index=C.SHORT, columns=C.SHORT)
    fig = G.heatmap(corr.values, list(corr.columns), list(corr.index),
                    [[f"{v:.2f}" for v in row] for row in corr.values], title="Correlation matrix", height=560)
    b.append(plot(fig))
    r = np.corrcoef(d["q2_stress"], d["q3_overwhelm"])[0, 1]
    b.append(md(f"*The two stress items correlate at r = {r:.2f}, supporting combining them into one index.*"))
    return b


def _cls(d):
    cnt = d.groupby([C.DEPT_COL, "classification"]).size().reset_index(name="n")
    piv = cnt.pivot(index=C.DEPT_COL, columns="classification", values="n").fillna(0)
    series = {k: piv[k].to_numpy() if k in piv else np.zeros(len(piv)) for k in ["Under Stress", "Stress-Free"]}
    fig = G.stacked_bar(list(piv.index), series, CMAP, title="Classification by department")
    grp = d.groupby("classification")[C.FACTORS].mean().T.rename(index=C.SHORT)
    return [h("Under Stress vs Stress-Free"), plot(fig),
            md("**Average factor values by classification**"), table(grp.rename_axis("Factor"), index=True, digits=2)]
