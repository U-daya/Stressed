"""
charts.py -- Builds plotly.js figures as plain dictionaries.

The browser draws them with plotly.js (public/plotly.min.js), so the server
does not need the Python plotly package. Every function returns
{"data": [traces], "layout": {...}}.
"""
from __future__ import annotations

import numpy as np

RED, GREEN, GREY, INK = "#CC0033", "#2E7D32", "#BBBBBB", "#1F2328"
DEPT_COLORS = ["#CC0033", "#1A56B0", "#2E7D32", "#E08A00", "#7B3FB2", "#00838F", "#6D4C41"]
FONT = dict(family="Inter, system-ui, sans-serif", size=12, color=INK)


def L(x):
    """numpy/pandas -> plain Python list (NaN -> None)."""
    arr = np.asarray(x, dtype=object).tolist() if not isinstance(x, list) else x
    out = []
    for v in arr:
        if isinstance(v, (float, np.floating)):
            out.append(None if np.isnan(v) else float(v))
        elif isinstance(v, (np.integer,)):
            out.append(int(v))
        else:
            out.append(v)
    return out


def layout(title="", xtitle="", ytitle="", height=360, **kw):
    lay = dict(title=dict(text=title, x=0.01, font=dict(size=15)), height=height,
               font=FONT, paper_bgcolor="white", plot_bgcolor="white",
               margin=dict(t=50 if title else 20, b=50, l=10, r=10),
               xaxis=dict(title=dict(text=xtitle), gridcolor="#EEE", zeroline=False, automargin=True),
               yaxis=dict(title=dict(text=ytitle), gridcolor="#EEE", zeroline=False, automargin=True),
               legend=dict(orientation="h", yanchor="bottom", y=1.0, x=1, xanchor="right"),
               shapes=[], annotations=[])
    lay.update(kw)
    return lay


def vline(lay, x, text="", dash="solid", color=INK, pos="top"):
    lay["shapes"].append(dict(type="line", x0=x, x1=x, y0=0, y1=1, yref="paper",
                              line=dict(color=color, width=1.5, dash=dash)))
    if text:
        lay["annotations"].append(dict(x=x, y=1 if pos == "top" else 0, yref="paper", text=text,
                                       showarrow=False, xanchor="left", yanchor="bottom" if pos == "top" else "bottom",
                                       font=dict(size=11, color=color), bgcolor="rgba(255,255,255,.8)"))


def hline(lay, y, dash="dash"):
    lay["shapes"].append(dict(type="line", x0=0, x1=1, xref="paper", y0=y, y1=y,
                              line=dict(color=INK, width=1, dash=dash)))


def fig(data, lay):
    return {"data": data, "layout": lay}


# ---------------------------------------------------------------------------
def hbar(labels, values, colors=None, text=None, title="", xtitle="", height=330, legend=None):
    """Horizontal bars, first label at the top."""
    tr = dict(type="bar", orientation="h", x=L(values), y=L(labels),
              marker=dict(color=colors if isinstance(colors, list) else (colors or RED)),
              hovertemplate="%{y}: %{x:.3f}<extra></extra>", showlegend=False)
    if text is not None:
        tr.update(text=L(text), textposition="outside", cliponaxis=False)
    data = [tr]
    if legend:   # fake legend entries, e.g. significant / not significant
        for name, col in legend:
            data.append(dict(type="bar", x=[None], y=[None], name=name, marker=dict(color=col),
                             orientation="h", showlegend=True))
    lay = layout(title, xtitle, "", height)
    lay["yaxis"]["autorange"] = "reversed"
    return fig(data, lay)


def class_histogram(si, cls, mean, threshold, title="Distribution of the Stress Index"):
    edges = np.arange(0, 101, 10)
    si = np.clip(np.asarray(si, float), 0, 99.999)       # SI = 100 goes in the 90-100 bar
    centers = edges[:-1] + 5
    data = []
    for name, col in [("Stress-Free", GREEN), ("Under Stress", RED)]:
        counts, _ = np.histogram(si[np.asarray(cls) == name], bins=edges)
        data.append(dict(type="bar", x=L(centers), y=L(counts), width=[9.6] * len(centers),
                         name=name, marker=dict(color=col),
                         customdata=[f"{a}–{a+10}" for a in edges[:-1]],
                         hovertemplate="SI %{customdata}: %{y}<extra>" + name + "</extra>"))
    lay = layout(title, "Stress Index (0–100)", "Number of students", 340, barmode="stack")
    lay["xaxis"].update(range=[-0.5, 100.5], dtick=10)
    vline(lay, mean, f"mean {mean:.1f}")
    vline(lay, threshold, "threshold", dash="dash", color="#555", pos="bottom")
    return fig(data, lay)


def box_by_group(groups: dict, means, title="", ytitle="Stress Index", height=400):
    data = []
    names = list(groups)
    for g in names:
        data.append(dict(type="box", y=L(groups[g]), name=g, boxpoints="all", jitter=0.4, pointpos=0,
                         marker=dict(color=RED, size=4, opacity=0.5), line=dict(color=RED),
                         fillcolor="rgba(204,0,51,0.12)", showlegend=False))
    data.append(dict(type="scatter", x=names, y=L(means), mode="markers", name="mean",
                     marker=dict(symbol="diamond", size=11, color=INK), showlegend=False))
    return fig(data, layout(title, "", ytitle, height))


def ci_plot(labels, means, lo, hi, ref=None, ref_text="", title="", xtitle=""):
    means, lo, hi = map(lambda a: np.asarray(a, float), (means, lo, hi))
    data = [dict(type="scatter", x=L(means), y=L(labels), mode="markers",
                 marker=dict(size=10, color=RED),
                 error_x=dict(type="data", symmetric=False, array=L(hi - means),
                              arrayminus=L(means - lo), color=RED, thickness=2, width=6),
                 hovertemplate="%{y}: %{x:.2f}<extra></extra>", showlegend=False)]
    lay = layout(title, xtitle, "", 110 + 45 * len(labels))
    lay["yaxis"]["autorange"] = "reversed"
    if ref is not None:
        vline(lay, ref, ref_text, dash="dot", color="#555")
    return fig(data, lay)


def scatter(x, y, title="", xtitle="", ytitle="", line=None, hline0=False, height=330):
    data = [dict(type="scatter", x=L(x), y=L(y), mode="markers", showlegend=False,
                 marker=dict(color=RED, size=6, opacity=0.7))]
    if line is not None:
        data.append(dict(type="scatter", x=L(line[0]), y=L(line[1]), mode="lines",
                         line=dict(color=INK), showlegend=False))
    lay = layout(title, xtitle, ytitle, height)
    if hline0:
        hline(lay, 0)
    return fig(data, lay)


def scatter_by_group(df, x, y, group, xtitle, ytitle, title=""):
    data = []
    for i, (g, sub) in enumerate(df.groupby(group)):
        data.append(dict(type="scatter", x=L(sub[x]), y=L(sub[y]), mode="markers", name=g,
                         marker=dict(size=7, opacity=0.75, color=DEPT_COLORS[i % len(DEPT_COLORS)])))
    xv, yv = df[x].astype(float).to_numpy(), df[y].astype(float).to_numpy()
    if np.std(xv) > 0:
        b1, b0 = np.polyfit(xv, yv, 1)
        xs = np.array([xv.min(), xv.max()])
        r = np.corrcoef(xv, yv)[0, 1]
        data.append(dict(type="scatter", x=L(xs), y=L(b0 + b1 * xs), mode="lines",
                         name=f"Least-squares line: ŷ = {b0:.2f} {'+' if b1 >= 0 else '−'} {abs(b1):.2f}x (r = {r:.2f})",
                         line=dict(color=INK, width=2)))
    lay = layout(title, xtitle, ytitle, 440)
    lay["legend"] = dict(orientation="h", y=-0.25, x=0)
    lay["margin"]["b"] = 110
    return fig(data, lay)


def heatmap(z, x, y, text, title="", height=420, zrange=(-1, 1)):
    data = [dict(type="heatmap", z=[L(r) for r in np.asarray(z, float)], x=L(x), y=L(y),
                 zmin=zrange[0], zmax=zrange[1], colorscale="RdBu", reversescale=False,
                 text=[L(r) for r in text], texttemplate="%{text}", hoverongaps=False,
                 colorbar=dict(title=dict(text="r"), thickness=12))]
    lay = layout(title, "", "", height)
    lay["yaxis"]["autorange"] = "reversed"
    lay["xaxis"]["gridcolor"] = lay["yaxis"]["gridcolor"] = "rgba(0,0,0,0)"
    return fig(data, lay)


def stacked_bar(categories, series: dict, colors: dict, title="", ytitle="Number of students"):
    data = [dict(type="bar", x=L(categories), y=L(v), name=k, marker=dict(color=colors[k]))
            for k, v in series.items()]
    return fig(data, layout(title, "", ytitle, 400, barmode="stack"))
