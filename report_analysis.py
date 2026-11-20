"""
report_analysis.py -- Generate every table and figure for the 7-page report.

Usage:
    python report_analysis.py stress_survey_responses.csv
Output (folder report_output/):
    fig1_histogram.png ... fig8_residuals.png   (300-dpi figures for the report)
    tables/*.csv                                (every statistical table)
    results_summary.md                          (all test results in words + numbers)

Download the CSV from the app's "Team / Admin" page (or from the Google Sheet).
Uses the SAME stats_engine as the web app, so numbers always match the app.
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

import config as C
import stats_engine as S

RED, GREEN, GREY = "#CC0033", "#2E7D32", "#9E9E9E"
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "figure.dpi": 110, "savefig.dpi": 300, "savefig.bbox": "tight"})


def p(v):
    return "< 0.0001" if v < 1e-4 else f"{v:.4f}"


def short_dept(name):
    return name.split("(")[-1].rstrip(")") if "(" in name else name


def main(csv_path):
    out = Path("report_output"); (out / "tables").mkdir(parents=True, exist_ok=True)
    d = S.clean(pd.read_csv(csv_path))
    raw_n = len(pd.read_csv(csv_path))
    md = [f"# Results summary (auto-generated)\n",
          f"Responses in file: {raw_n}; valid responses analysed: {len(d)}; alpha = {C.ALPHA}\n"]

    # ---------- data collection ----------
    prog = S.collection_progress(d)
    prog["counts"].rename("n").to_csv(out / "tables/sample_by_department.csv")
    md.append("## Sample\n" + prog["counts"].to_frame("n").to_markdown() + "\n")
    md.append(f"Requirement check: total >= {C.REQ_TOTAL_N}: {prog['total_ok']}; "
              f"departments with >= {C.REQ_PER_DEPT}: {prog['depts_meeting']} (need {C.REQ_MIN_DEPTS})\n")
    S.describe(d).to_csv(out / "tables/descriptive_stats.csv")
    md.append("## Descriptive statistics\n" + S.describe(d).to_markdown() + "\n")

    # ---------- RQ1 ----------
    r = S.overall_stress(d)
    md.append("## RQ1 Overall stress\n"
              f"- Mean SI = {r['mean']:.2f}, s = {r['sd']:.2f}, n = {r['n']}\n"
              f"- 95% CI for mu: [{r['ci_mean'][0]:.2f}, {r['ci_mean'][1]:.2f}] (t = {r['t_crit']:.3f})\n"
              f"- 95% CI for sigma: [{r['ci_sd'][0]:.2f}, {r['ci_sd'][1]:.2f}]\n"
              f"- One-sample t test H0: mu = {r['mu0']:g}: t0 = {r['t0']:.3f}, P = {p(r['p_t'])}\n"
              f"- Under Stress: {r['k_under']}/{r['n']} = {100*r['phat']:.1f}%, 95% CI "
              f"[{100*r['ci_p'][0]:.1f}%, {100*r['ci_p'][1]:.1f}%]\n"
              f"- z test H0: p = 0.5: z0 = {r['z0']:.3f}, P = {p(r['p_z'])}\n"
              f"- Shapiro-Wilk normality P = {p(r['shapiro_p'])}\n")

    fig, ax = plt.subplots(figsize=(6.5, 3.2))
    bins = np.arange(0, 110, 10)
    ax.hist([d.loc[d.classification == "Stress-Free", "stress_index"],
             d.loc[d.classification == "Under Stress", "stress_index"]],
            bins=bins, stacked=True, color=[GREEN, RED], edgecolor="white",
            label=["Stress-Free", "Under Stress"])
    ax.axvline(r["mean"], color="black", lw=1.5, label=f"mean = {r['mean']:.1f}")
    ax.axvspan(*r["ci_mean"], color="black", alpha=0.12, label="95% CI for mean")
    ax.axvline(C.STRESS_THRESHOLD, color="black", ls="--", lw=1, label="threshold = 50")
    ax.set(xlabel="Stress Index (0-100)", ylabel="Number of students",
           title=f"Figure 1. Distribution of Stress Index (n = {r['n']})")
    ax.legend(frameon=False, fontsize=8)
    fig.savefig(out / "fig1_histogram.png"); plt.close(fig)

    # ---------- RQ2 / RQ5 ----------
    a = S.dept_anova(d)
    if a:
        a["table"].to_csv(out / "tables/anova_stress_by_department.csv", index=False)
        a["means"].to_csv(out / "tables/department_means_ci.csv", index=False)
        md.append("## RQ2/RQ5 Department differences (one-way ANOVA)\n" +
                  a["table"].round(4).to_markdown(index=False) + "\n\n" +
                  a["means"].round(3).to_markdown(index=False) + "\n\n"
                  f"F0 = {a['f0']:.3f}, F crit = {a['f_crit']:.3f}, P = {p(a['p'])}, R^2 = {a['r2']:.3f}\n")
        if "bartlett" in a:
            md.append(f"- Bartlett P = {p(a['bartlett'][1])}; Levene P = {p(a['levene'][1])}; "
                      f"Kruskal-Wallis H = {a['kruskal'].statistic:.3f}, P = {p(a['kruskal'].pvalue)}\n")
        if "tukey" in a:
            a["tukey"].to_csv(out / "tables/tukey_hsd.csv", index=False)
            md.append("### Tukey HSD\n" + a["tukey"].round(4).to_markdown(index=False) + "\n")

        dd = S.comparison_set(d)
        order = a["means"]["Department"].tolist()
        fig, axs = plt.subplots(1, 2, figsize=(7.5, 3.4), gridspec_kw={"width_ratios": [1.3, 1]})
        axs[0].boxplot([dd.loc[dd[C.DEPT_COL] == g, "stress_index"] for g in order],
                       tick_labels=[short_dept(g) for g in order], patch_artist=True,
                       boxprops=dict(facecolor="#F6C6D0", color=RED), medianprops=dict(color=RED))
        axs[0].plot(range(1, len(order) + 1), a["means"]["Mean"], "kD", ms=5, label="mean")
        axs[0].set(ylabel="Stress Index", title="Stress Index by department")
        ci = a["means"]
        axs[1].errorbar(ci["Mean"], range(len(ci)), xerr=[ci["Mean"] - ci["Lower 95%"],
                        ci["Upper 95%"] - ci["Mean"]], fmt="o", color=RED, capsize=4)
        axs[1].axvline(a["grand_mean"], color=GREY, ls=":")
        axs[1].set_yticks(range(len(ci)), [short_dept(g) for g in ci["Department"]])
        axs[1].invert_yaxis()
        axs[1].set(xlabel="Mean SI with 95% CI", title=f"ANOVA F = {a['f0']:.2f}, P = {p(a['p'])}")
        fig.suptitle("Figure 2. Stress by academic department", y=1.02)
        fig.tight_layout(); fig.savefig(out / "fig2_departments.png"); plt.close(fig)

    chi = S.chi_square_dept(d)
    if chi:
        chi["observed"].assign(pct_under=chi["pct"]).to_csv(out / "tables/chisq_observed.csv")
        chi["expected"].to_csv(out / "tables/chisq_expected.csv")
        md.append("## Chi-square test of independence (classification x department)\n" +
                  chi["observed"].assign(**{"% Under": chi["pct"]}).to_markdown() + "\n\n"
                  f"chi2 = {chi['chi2']:.3f}, df = {chi['dof']}, crit = {chi['chi_crit']:.3f}, "
                  f"P = {p(chi['p'])}, min expected = {chi['min_expected']:.1f}\n")
        fig, ax = plt.subplots(figsize=(6.5, 3))
        o = chi["observed"]
        ax.barh([short_dept(i) for i in o.index], o["Under Stress"], color=RED, label="Under Stress")
        ax.barh([short_dept(i) for i in o.index], o["Stress-Free"], left=o["Under Stress"],
                color=GREEN, label="Stress-Free")
        for i, (u, t) in enumerate(zip(o["Under Stress"], o.sum(axis=1))):
            ax.text(t + 0.5, i, f"{100*u/t:.0f}% under stress", va="center", fontsize=8)
        ax.set(xlabel="Number of students",
               title=f"Figure 3. Classification by department (chi2 = {chi['chi2']:.2f}, P = {p(chi['p'])})")
        ax.set_xlim(0, o.sum(axis=1).max() * 1.35)
        ax.legend(frameon=False, fontsize=8, ncol=2, loc="upper center", bbox_to_anchor=(0.5, -0.22))
        fig.savefig(out / "fig3_classification.png"); plt.close(fig)

    # ---------- RQ3 ----------
    cor = S.correlations(d)
    m = S.mlr(d)
    if cor is not None:
        cor.drop(columns="key").to_csv(out / "tables/correlations.csv", index=False)
        md.append("## RQ3 Correlations with SI\n" + cor.drop(columns="key").round(4).to_markdown(index=False) + "\n")
    if m:
        m["coef"].drop(columns="key").to_csv(out / "tables/mlr_coefficients.csv", index=False)
        m["anova"].to_csv(out / "tables/mlr_anova.csv", index=False)
        md.append("## RQ3 Multiple linear regression\n" +
                  m["anova"].round(4).to_markdown(index=False) + "\n\n" +
                  m["coef"].drop(columns="key").round(4).to_markdown(index=False) + "\n\n"
                  f"R^2 = {m['r2']:.4f}, adj R^2 = {m['r2_adj']:.4f}, F0 = {m['f0']:.3f}, "
                  f"P = {p(m['p'])}, s = {m['s']:.3f}\n\n"
                  "Ranking by |standardized beta|: " +
                  ", ".join(f"{t} ({b:+.3f}{'*' if s else ''})" for t, b, s in
                            zip(m["ranking"]["Term"], m["ranking"]["Std. Beta"], m["ranking"]["Significant"])) + "\n")

        rk = m["ranking"].iloc[::-1]
        fig, ax = plt.subplots(figsize=(6.5, 3.2))
        ax.barh(rk["Term"], rk["Std. Beta"], color=[RED if s else GREY for s in rk["Significant"]])
        ax.axvline(0, color="black", lw=0.8)
        ax.set(xlabel="Standardized coefficient (effect of +1 SD change)",
               title=f"Figure 4. Factor importance, MLR (R² = {m['r2']:.3f}); red = P < 0.05")
        fig.savefig(out / "fig4_factor_importance.png"); plt.close(fig)

        # scatter matrix of top 4 factors
        top = [k for k in m["ranking"]["key"]][:4]
        fig, axs = plt.subplots(1, 4, figsize=(9, 2.6), sharey=True)
        for ax, f in zip(axs, top):
            jitter = np.random.default_rng(0).normal(0, 0.08, len(d))
            ax.scatter(d[f] + jitter, d["stress_index"], s=8, alpha=0.5, color=RED)
            b1, b0, rr, pp, _ = stats.linregress(d[f], d["stress_index"])
            xs = np.linspace(d[f].min(), d[f].max(), 2)
            ax.plot(xs, b0 + b1 * xs, color="black")
            ax.set(xlabel=C.SHORT[f], title=f"r = {rr:.2f}, P = {p(pp)}")
        axs[0].set_ylabel("Stress Index")
        fig.suptitle("Figure 5. Stress Index vs. the four strongest factors", y=1.04)
        fig.tight_layout(); fig.savefig(out / "fig5_scatter_top_factors.png"); plt.close(fig)

        fig, axs = plt.subplots(1, 2, figsize=(7.5, 3))
        stats.probplot(m["std_resid"], dist="norm", plot=axs[0])
        axs[0].get_lines()[0].set(color=RED, ms=3); axs[0].set_title("Normal probability plot")
        axs[1].scatter(m["fitted"], m["std_resid"], s=8, color=RED, alpha=0.6)
        axs[1].axhline(0, color="black", ls="--", lw=0.8)
        axs[1].set(xlabel="Fitted SI", ylabel="Standardized residual", title="Residuals vs fitted")
        fig.suptitle("Figure 8. Regression model adequacy", y=1.03)
        fig.tight_layout(); fig.savefig(out / "fig8_residuals.png"); plt.close(fig)

    # ---------- RQ4 ----------
    sd = S.slopes_differ_test(d)
    if sd:
        md.append("## RQ4 Partial F test (department-specific slopes)\n"
                  f"- Reduced SI ~ factors + dept: R^2 = {sd['r2_reduced']:.4f}, SSE = {sd['sse_reduced']:.2f}\n"
                  f"- Full SI ~ factors x dept: R^2 = {sd['r2_full']:.4f}, SSE = {sd['sse_full']:.2f}\n"
                  f"- F0 = {sd['F']:.3f}, df = {sd['df']}, P = {p(sd['p'])}\n"
                  f"- Department effect after controlling for factors: F0 = {sd['F_dept']:.3f}, "
                  f"df = {sd['df_dept']}, P = {p(sd['p_dept'])}\n")
    dc = S.dept_correlations(d)
    if dc:
        r_tab, p_tab = dc
        r_tab.to_csv(out / "tables/dept_correlations_r.csv"); p_tab.to_csv(out / "tables/dept_correlations_p.csv")
        md.append("## RQ4 Within-department correlations (r)\n" + r_tab.round(3).to_markdown() + "\n")
        fig, ax = plt.subplots(figsize=(6.5, 3.6))
        im = ax.imshow(r_tab.values, cmap="RdBu_r", vmin=-0.8, vmax=0.8, aspect="auto")
        ax.set_xticks(range(r_tab.shape[1]), [short_dept(c) for c in r_tab.columns])
        ax.set_yticks(range(r_tab.shape[0]), r_tab.index)
        for i in range(r_tab.shape[0]):
            for j in range(r_tab.shape[1]):
                ax.text(j, i, f"{r_tab.iat[i, j]:.2f}{'*' if p_tab.iat[i, j] < C.ALPHA else ''}",
                        ha="center", va="center", fontsize=8)
        fig.colorbar(im, ax=ax, label="r")
        ax.set_title("Figure 6. Correlation with Stress Index within each department (* P < 0.05)")
        fig.savefig(out / "fig6_dept_correlations.png"); plt.close(fig)
    dm = S.dept_mlr(d)
    if dm is not None:
        dm.to_csv(out / "tables/dept_mlr.csv")
        md.append("## RQ4 Separate MLR by department\n" + dm.to_markdown() + "\n")
    fm = S.factor_means_by_dept(d)
    if fm is not None:
        fm.drop(columns="key").to_csv(out / "tables/factor_means_by_dept.csv", index=False)
        md.append("## RQ4 Factor means by department + ANOVA\n" +
                  fm.drop(columns="key").round(4).to_markdown(index=False) + "\n")
        fig, axs = plt.subplots(1, len(C.FACTORS), figsize=(11, 3.0))
        dd = S.comparison_set(d)
        depts = sorted(dd[C.DEPT_COL].unique())
        pv = fm.set_index("key")["P-value"]
        for ax, f in zip(axs, C.FACTORS):
            g = dd.groupby(C.DEPT_COL)[f]
            mu, se = g.mean().reindex(depts), (g.std() / np.sqrt(g.count())).reindex(depts)
            ax.bar(range(len(depts)), mu, yerr=1.96 * se, color=RED if pv[f] < C.ALPHA else GREY,
                   capsize=2)
            ax.set_xticks(range(len(depts)), [short_dept(x) for x in depts], rotation=90, fontsize=7)
            ax.set_title(f"{C.SHORT[f]}\nP = {p(pv[f])}", fontsize=7)
        fig.suptitle("Figure 7. Factor means by department (red = differs, ANOVA P < 0.05)", y=1.08)
        fig.tight_layout(); fig.savefig(out / "fig7_factor_means.png"); plt.close(fig)

    (out / "results_summary.md").write_text("\n".join(md))
    print(f"Done. {len(d)} valid responses. Output in {out.resolve()}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "stress_survey_responses.csv")
