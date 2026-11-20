"""Verify the numpy OLS / partial-F code matches statsmodels exactly.
Needs statsmodels installed locally (it is NOT deployed to Vercel).
Usage: python tests/check_against_statsmodels.py data.csv"""
import sys
sys.path.insert(0, ".")
import numpy as np, pandas as pd
import statsmodels.api as sm, statsmodels.formula.api as smf
from statsmodels.stats.anova import anova_lm
from statsmodels.stats.outliers_influence import variance_inflation_factor
import config as CFG, stats_engine as S

d = S.clean(pd.read_csv(sys.argv[1]))
mine = S.mlr(d)
X = sm.add_constant(d[CFG.FACTORS].astype(float)); ref = sm.OLS(d.stress_index, X).fit()
chk = {
 "coefficients": np.allclose(mine["coef"]["Estimate"], ref.params),
 "std errors": np.allclose(mine["coef"]["Std Error"], ref.bse),
 "t values": np.allclose(mine["coef"]["t0"], ref.tvalues),
 "p values": np.allclose(mine["coef"]["P-value"], ref.pvalues),
 "conf. intervals": np.allclose(mine["coef"][["Lower 95%", "Upper 95%"]], ref.conf_int()),
 "R2 / adj R2": np.allclose([mine["r2"], mine["r2_adj"]], [ref.rsquared, ref.rsquared_adj]),
 "F and P": np.allclose([mine["f0"], mine["p"]], [ref.fvalue, ref.f_pvalue]),
 "standardized residuals": np.allclose(mine["std_resid"], ref.get_influence().resid_studentized_internal),
 "VIF": np.allclose(mine["coef"]["VIF"][1:], [variance_inflation_factor(X.values, i) for i in range(1, X.shape[1])]),
}
dd = S.comparison_set(d, 3).rename(columns={CFG.DEPT_COL: "dept"})
rhs = " + ".join(CFG.FACTORS)
red = smf.ols(f"stress_index ~ {rhs} + C(dept)", dd).fit(); full = smf.ols(f"stress_index ~ ({rhs}) * C(dept)", dd).fit()
nod = smf.ols(f"stress_index ~ {rhs}", dd).fit()
a, b = anova_lm(red, full), anova_lm(nod, red)
sd = S.slopes_differ_test(d)
chk["partial F (slopes)"] = np.allclose([sd["F"], sd["p"], *sd["df"]], [a.F[1], a["Pr(>F)"][1], a.df_diff[1], a.df_resid[1]])
chk["partial F (dept)"] = np.allclose([sd["F_dept"], sd["p_dept"]], [b.F[1], b["Pr(>F)"][1]])
chk["model R2s"] = np.allclose([sd["r2_reduced"], sd["r2_full"]], [red.rsquared, full.rsquared])
for k, v in chk.items(): print(f"{'PASS' if v else 'FAIL'}  {k}")
sys.exit(0 if all(chk.values()) else 1)
