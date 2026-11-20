/* app.js -- shared page code: navigation, survey form, result gauge, results renderer. */

const PAGES = [["/", "Take the survey"], ["/results", "Results"],
               ["/methodology", "Methodology"], ["/admin", "Team"]];

function header() {
  const here = location.pathname.replace(/\.html$/, "").replace(/\/index$/, "/") || "/";
  const links = PAGES.map(([href, t]) =>
    `<a href="${href}"${here === href ? ' class="active" aria-current="page"' : ""}>${t}</a>`).join("");
  document.body.insertAdjacentHTML("afterbegin",
    `<header><div class="bar"><a class="brand" href="/"><span class="mark" aria-hidden="true"></span>RU Stressed?</a>
     <nav aria-label="Main">${links}</nav></div></header>`);
  document.body.insertAdjacentHTML("beforeend",
    `<footer>An IE 320 Engineering Statistics class project, Rutgers University, Fall 2026.</footer>`);
}

const esc = s => String(s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

/* Tiny markdown: **bold**, *italic*, "  \n" line breaks. Text comes from our own API. */
function md(t) {
  return t.replace(/\*\*(.+?)\*\*/g, "<b>$1</b>")
          .replace(/(^|[^*])\*([^*\n]+?)\*/g, "$1<i>$2</i>")
          .replace(/ {2}\n/g, "<br>").replace(/\n/g, "<br>");
}

async function api(path, opts) {
  const r = await fetch(path, opts);
  let body = null;
  try { body = await r.json(); } catch { /* non-JSON */ }
  if (!r.ok) throw new Error((body && body.detail) || `The server returned an error (${r.status}). Try again in a moment.`);
  return body;
}

/* heat colour for step i of n: teal -> amber -> scarlet */
function heat(i, n) {
  const stops = [[31, 138, 122], [233, 162, 59], [204, 0, 51]];
  const t = n <= 1 ? 0 : i / (n - 1), seg = t < 0.5 ? 0 : 1, u = (t - seg * 0.5) / 0.5;
  const c = stops[seg].map((v, k) => Math.round(v + (stops[seg + 1][k] - v) * u));
  return `rgb(${c.join(",")})`;
}

/* ------------------------------------------------------------------ */
/* Survey page                                                         */
/* ------------------------------------------------------------------ */
function questionHTML(q) {
  const k = q.key, id = `t_${k}`;
  const title = `<span class="qt" id="${id}">${esc(q.text)}</span>`;
  if (q.kind === "category") {
    return title + `<div class="chips" role="radiogroup" aria-labelledby="${id}">` +
      q.options.map((o, i) => `<input type="radio" id="${k}_${i}" name="${k}" value="${esc(o)}">` +
        `<label for="${k}_${i}">${esc(o)}</label>`).join("") + `</div>`;
  }
  if (q.kind === "scale" && !q.labels) {          // the 1–10 heat strip
    const n = q.hi - q.lo + 1;
    let cells = "";
    for (let v = q.lo; v <= q.hi; v++) {
      cells += `<input type="radio" id="${k}_${v}" name="${k}" value="${v}">` +
               `<label for="${k}_${v}" style="--h:${heat(v - q.lo, n)}">${v}</label>`;
    }
    return title + `<div class="heat" role="radiogroup" aria-labelledby="${id}">${cells}</div>` +
      `<div class="ends"><span>${esc(q.lo_label.replace(/^1 = /, ""))}</span><span>${esc(q.hi_label.replace(/^10 = /, ""))}</span></div>`;
  }
  if (q.kind === "scale") {
    return title + `<div class="seg" role="radiogroup" aria-labelledby="${id}">` +
      q.labels.map((l, i) => `<input type="radio" id="${k}_${i + q.lo}" name="${k}" value="${i + q.lo}">` +
        `<label for="${k}_${i + q.lo}">${esc(l)}</label>`).join("") + `</div>`;
  }
  return title + `<div class="numrow"><div class="num">
      <button type="button" data-step="-1" data-for="${k}" aria-label="Decrease">−</button>
      <input type="number" name="${k}" min="${q.lo}" max="${q.hi}" step="${q.step}" inputmode="decimal"
             placeholder="–" aria-labelledby="${id}">
      <button type="button" data-step="1" data-for="${k}" aria-label="Increase">+</button>
    </div><span class="unit">${esc(q.unit)}</span></div>`;
}

async function surveyPage() {
  const root = document.getElementById("root");
  let cfg;
  try { cfg = await api("/api/questions"); }
  catch (e) { root.innerHTML = `<div class="error">${esc(e.message)}</div>`; return; }
  const total = cfg.questions.length;
  const prior = localStorage.getItem("stress_submitted");

  root.innerHTML = `
    <section class="hero">
      <h1>RU Stressed<span class="qm">?</span></h1>
      <p class="lede">Ten quick questions about your sleep, classes, money and how you've been holding up.
        You'll see your own stress score the moment you finish.</p>
      <ul class="facts"><li>Anonymous: no name or NetID</li><li>About a minute</li><li>For a Rutgers statistics class</li></ul>
    </section>
    ${prior ? `<div class="notice">This device has already sent a response. Please take the survey only once.</div>` : ""}
    <div class="progress" aria-live="polite"><div class="track"><div class="fill" id="pfill"></div></div>
      <span class="count" id="pcount">0 of ${total} answered</span></div>
    <form id="f" novalidate>
      <ol class="qs">${cfg.questions.map(q =>
        `<li class="q" data-key="${q.key}"><span class="n" aria-hidden="true">${q.num}</span><div>${questionHTML(q)}</div></li>`).join("")}</ol>
      <div class="finish">
        <label class="consent"><input type="checkbox" name="consent">
          <span>I'm a current Rutgers student, and my anonymous answers can be used for this class project.</span></label>
        <div id="err" role="alert"></div>
        <button class="primary" type="submit">See my stress score</button>
      </div>
    </form>`;

  const f = document.getElementById("f");
  const valueOf = q => { const el = f.elements[q.key]; return el ? el.value : ""; };

  const refresh = () => {
    let done = 0;
    for (const q of cfg.questions) {
      const ok = valueOf(q) !== "";
      f.querySelector(`.q[data-key="${q.key}"]`).classList.toggle("done", ok);
      if (ok) done++;
    }
    document.getElementById("pfill").style.width = `${(done / total) * 100}%`;
    document.getElementById("pcount").textContent = `${done} of ${total} answered`;
  };

  // light the heat strip up to the chosen value
  f.querySelectorAll(".heat").forEach(strip => strip.addEventListener("change", e => {
    const v = Number(e.target.value);
    strip.querySelectorAll("label").forEach((lab, i) => lab.classList.toggle("lit", i + 1 <= v));
  }));
  // − / + buttons
  f.addEventListener("click", e => {
    const b = e.target.closest("button[data-step]"); if (!b) return;
    const q = cfg.questions.find(x => x.key === b.dataset.for);
    const inp = f.elements[q.key];
    const cur = inp.value === "" ? Number(q.default) : Number(inp.value) + Number(b.dataset.step) * Number(q.step);
    inp.value = Math.min(q.hi, Math.max(q.lo, cur));
    inp.dispatchEvent(new Event("input", {bubbles: true}));
  });
  const clear = e => { e.target.closest(".q")?.classList.remove("missing"); refresh(); };
  f.addEventListener("change", clear);
  f.addEventListener("input", clear);

  f.addEventListener("submit", async e => {
    e.preventDefault();
    const err = document.getElementById("err"); err.innerHTML = "";
    const body = { consent: f.consent.checked };
    let firstBad = null;
    for (const q of cfg.questions) {
      const v = valueOf(q), row = f.querySelector(`.q[data-key="${q.key}"]`);
      let bad = v === "";
      if (!bad && q.kind !== "category") {
        const x = Number(v);
        bad = Number.isNaN(x) || x < q.lo || x > q.hi;
        if (!bad) body[q.key] = x;
      } else if (!bad) body[q.key] = v;
      row.classList.toggle("missing", bad);
      if (bad && !firstBad) firstBad = row;
    }
    if (firstBad) {
      const n = f.querySelectorAll(".q.missing").length;
      err.innerHTML = `<div class="error">${n} question${n > 1 ? "s need" : " needs"} an answer. They're marked in red.</div>`;
      firstBad.scrollIntoView({behavior: "smooth", block: "center"}); return;
    }
    if (!body.consent) { err.innerHTML = `<div class="error">Tick the box above to confirm you're a Rutgers student and agree to take part.</div>`; return; }
    const btn = f.querySelector("button.primary"); btn.disabled = true; btn.textContent = "Saving your answers…";
    try {
      const res = await api("/api/submit", { method: "POST", headers: {"Content-Type": "application/json"},
                                             body: JSON.stringify(body) });
      localStorage.setItem("stress_submitted", "1");
      showResult(res);
    } catch (ex) {
      err.innerHTML = `<div class="error">${esc(ex.message)}</div>`;
      btn.disabled = false; btn.textContent = "See my stress score";
    }
  });
}

function gaugeSVG(si, threshold) {
  // semicircle 0..100, centre (150,150), radius 120
  const ticks = [0, 25, 50, 75, 100].map(v => {
    const a = Math.PI * (1 - v / 100), x1 = 150 + 132 * Math.cos(a), y1 = 150 - 132 * Math.sin(a),
          x2 = 150 + 142 * Math.cos(a), y2 = 150 - 142 * Math.sin(a);
    return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="#7B869C" stroke-width="2"/>`;
  }).join("");
  const ta = Math.PI * (1 - threshold / 100);
  return `<svg viewBox="0 0 300 172" role="img" aria-label="Stress Index ${si.toFixed(1)} out of 100">
    <defs><linearGradient id="g" x1="0" x2="1" y1="0" y2="0">
      <stop offset="0" stop-color="#1F8A7A"/><stop offset=".55" stop-color="#E9A23B"/><stop offset="1" stop-color="#CC0033"/></linearGradient></defs>
    <path d="M30 150 A120 120 0 0 1 270 150" fill="none" stroke="url(#g)" stroke-width="26" stroke-linecap="round"/>
    ${ticks}
    <line x1="${150 + 104 * Math.cos(ta)}" y1="${150 - 104 * Math.sin(ta)}" x2="${150 + 150 * Math.cos(ta)}" y2="${150 - 150 * Math.sin(ta)}"
          stroke="#14213D" stroke-width="2" stroke-dasharray="4 3"/>
    <g class="needle" style="transform: rotate(-90deg)">
      <line x1="150" y1="150" x2="150" y2="44" stroke="#14213D" stroke-width="6" stroke-linecap="round"/>
      <circle cx="150" cy="150" r="13" fill="#14213D"/><circle cx="150" cy="150" r="5" fill="#fff"/>
    </g>
    <text x="30" y="170" font-size="12" fill="#4A5672" text-anchor="middle">0</text>
    <text x="270" y="170" font-size="12" fill="#4A5672" text-anchor="middle">100</text>
  </svg>`;
}

function showResult(r) {
  const under = r.classification === "Under Stress";
  const notes = r.notes.length
    ? `<div class="panel"><h2>What stood out in your answers</h2><ul>${r.notes.map(n => `<li>${esc(n)}</li>`).join("")}</ul></div>` : "";
  const compare = r.n ? `<div class="compare">
      <div><b>${r.percentile.toFixed(0)}%</b><span>of the ${r.n} students so far scored at or below you</span></div>
      <div><b>${r.dept_mean.toFixed(1)}</b><span>average for ${esc(r.dept)} (${r.dept_n} ${r.dept_n === 1 ? "student" : "students"})</span></div>
      <div><b>${r.overall_mean.toFixed(1)}</b><span>average across everyone</span></div></div>` : "";
  document.getElementById("root").innerHTML = `
    <section class="result-top ${under ? "under" : "free"}">
      <div>
        <p class="saved">Your answers are saved. Thank you.</p>
        <h1>${under ? "Under stress" : "Stress-free"}</h1>
        <p class="score">Stress Index ${r.stress_index.toFixed(1)} out of 100</p>
      </div>
      <div class="gauge">${gaugeSVG(r.stress_index, r.threshold)}</div>
    </section>
    <p class="muted">The Stress Index averages your answers to question 2 (stress, 1–10) and question 3 (feeling
      overwhelmed, 1–5), each rescaled to 0–100. A score of ${r.threshold} or more counts as under stress; the dashed line marks it.</p>
    ${compare}${notes}
    <div class="panel"><h2>If things feel heavy</h2>
      <p style="margin:0">This is a class-project screening, not a medical assessment. Rutgers CAPS (Counseling, ADAP and
      Psychiatric Services) offers free, confidential support to students.</p></div>
    <div class="next"><a class="btn solid" href="/results">See everyone's results</a></div>`;
  scrollTo(0, 0);
  const needle = document.querySelector(".needle");
  requestAnimationFrame(() => requestAnimationFrame(() => {
    needle.style.transform = `rotate(${-90 + 180 * Math.min(100, Math.max(0, r.stress_index)) / 100}deg)`;
  }));
}

/* ------------------------------------------------------------------ */
/* Results page: draws blocks sent by /api/results                     */
/* ------------------------------------------------------------------ */
const PLOT_CFG = {responsive: true, displaylogo: false, modeBarButtonsToRemove: ["lasso2d", "select2d"]};
function styleFig(fig) {
  const l = fig.layout;
  l.font = Object.assign({}, l.font, {family: "Figtree, Segoe UI, sans-serif", color: "#14213D"});
  if (l.title) l.title.font = {family: "Bricolage Grotesque, Segoe UI, sans-serif", size: 16, color: "#14213D"};
  return fig;
}

function renderBlocks(blocks, el) {
  for (const b of blocks) {
    let node;
    if (b.type === "h") { node = document.createElement("h2"); node.textContent = b.text; }
    else if (b.type === "md") { node = document.createElement("div"); node.className = "md"; node.innerHTML = md(b.text); }
    else if (b.type === "warn") { node = document.createElement("div"); node.className = "warn"; node.innerHTML = md(b.text); }
    else if (b.type === "verdict") { node = document.createElement("div"); node.className = "verdict " + (b.ok ? "ok" : "no"); node.innerHTML = md(b.text); }
    else if (b.type === "metrics") {
      node = document.createElement("div"); node.className = "metrics";
      node.innerHTML = b.items.map(([k, v]) => `<div class="metric"><div class="k">${esc(k)}</div><div class="v">${esc(v)}</div></div>`).join("");
    } else if (b.type === "table") {
      node = document.createElement("div"); node.className = "tablewrap";
      node.innerHTML = `<table><thead><tr>${b.columns.map(c => `<th scope="col">${esc(c)}</th>`).join("")}</tr></thead><tbody>` +
        b.rows.map(r => `<tr>${r.map(c => `<td>${esc(c)}</td>`).join("")}</tr>`).join("") + `</tbody></table>`;
    } else if (b.type === "plot") {
      node = document.createElement("div"); node.className = "plot";
      el.appendChild(node);
      const fig = styleFig(b.fig);
      Plotly.newPlot(node, fig.data, fig.layout, PLOT_CFG);
      continue;
    } else if (b.type === "row") {
      node = document.createElement("div"); node.className = "row2";
      el.appendChild(node); renderBlocks(b.blocks, node); continue;
    } else if (b.type === "plotselect") {
      node = document.createElement("div");
      const lab = document.createElement("label"); lab.className = "muted"; lab.textContent = "Factor ";
      const sel = document.createElement("select"); sel.className = "factor";
      b.options.forEach((o, i) => sel.add(new Option(o.label, i)));
      lab.appendChild(sel);
      const holder = document.createElement("div"); holder.className = "plot";
      node.append(lab, holder); el.appendChild(node);
      const draw = () => { const o = b.options[sel.value]; const fig = styleFig(o.fig);
                           Plotly.react(holder, fig.data, fig.layout, PLOT_CFG); };
      sel.addEventListener("change", draw); draw();
      continue;
    } else continue;
    el.appendChild(node);
  }
}

async function resultsPage() {
  const root = document.getElementById("root");
  root.innerHTML = `<h1>Results</h1><p class="loading">Running the analyses on every response so far…</p>`;
  let r;
  try { r = await api("/api/results"); }
  catch (e) { root.innerHTML = `<h1>Results</h1><div class="error">${esc(e.message)}</div>`; return; }
  root.innerHTML = `
    <div class="reshead">
      <div><h1>Results</h1>
        <p>Every test below is recomputed from all responses each time this page loads. Significance level α = ${r.alpha}.</p></div>
      <div><div class="pill-n">${r.n}</div><div class="muted">responses so far</div></div>
    </div>
    <details class="prog" ${r.n < 150 ? "open" : ""}><summary>Progress toward the sample-size goal</summary><div></div></details>
    <div class="tabs" id="tabs" role="tablist"></div><div id="tab" role="tabpanel"></div>`;
  renderBlocks(r.progress, document.querySelector(".prog div"));
  if (!r.tabs.length) {
    document.getElementById("tab").innerHTML = `<div class="notice" style="margin-top:20px">The analyses start once 5 responses are in.
      <a href="/">Take the survey</a> or share the link to get there.</div>`;
    return;
  }
  const tabs = document.getElementById("tabs"), body = document.getElementById("tab");
  const show = i => {
    [...tabs.children].forEach((b, j) => { b.classList.toggle("active", i === j); b.setAttribute("aria-selected", i === j); });
    body.innerHTML = ""; renderBlocks(r.tabs[i].blocks, body);
    history.replaceState(null, "", "#" + i);
  };
  r.tabs.forEach((t, i) => { const b = document.createElement("button"); b.type = "button"; b.setAttribute("role", "tab");
    b.textContent = t.name; b.onclick = () => show(i); tabs.appendChild(b); });
  show(Math.min(r.tabs.length - 1, parseInt(location.hash.slice(1)) || 0));
}

/* ------------------------------------------------------------------ */
/* Methodology page                                                     */
/* ------------------------------------------------------------------ */
async function methodologyPage() {
  const cfg = await api("/api/questions");
  const rows = cfg.questions.map(q => {
    let resp;
    if (q.kind === "category") resp = q.options.join(", ");
    else if (q.labels) resp = q.labels.map((l, i) => `${i + 1} ${l}`).join(", ");
    else if (q.kind === "scale") resp = `${q.lo_label} to ${q.hi_label}`;
    else resp = `Number from ${q.lo} to ${q.hi} (${q.unit})`;
    const role = {group: "Grouping", stress: "Stress measure", factor: "Possible cause"}[q.role];
    return `<tr><td>${q.num}</td><td style="white-space:normal;text-align:left;min-width:260px">${esc(q.text)}</td>
            <td style="white-space:normal;text-align:left;min-width:200px">${esc(resp)}</td><td style="text-align:left">${role}</td></tr>`;
  }).join("");
  document.getElementById("qtable").innerHTML =
    `<table><thead><tr><th scope="col">#</th><th scope="col" style="text-align:left">Question</th>
     <th scope="col" style="text-align:left">Answer options</th><th scope="col" style="text-align:left">Role</th></tr></thead><tbody>${rows}</tbody></table>`;
}

/* ------------------------------------------------------------------ */
/* Team page                                                             */
/* ------------------------------------------------------------------ */
function adminPage() {
  const f = document.getElementById("af"), msg = document.getElementById("amsg");
  f.addEventListener("submit", async e => {
    e.preventDefault(); msg.innerHTML = "";
    const r = await fetch("/api/export", { headers: { "X-Admin-Password": f.pw.value } });
    if (!r.ok) {
      let d = "The download didn't work. Try again."; try { d = (await r.json()).detail; } catch {}
      msg.innerHTML = `<div class="error" style="margin-top:14px">${esc(d)}</div>`; return;
    }
    const text = await r.text();
    const n = Math.max(0, text.trim().split("\n").length - 1);
    const url = URL.createObjectURL(new Blob([text], {type: "text/csv"}));
    const a = Object.assign(document.createElement("a"), {href: url, download: "stress_survey_responses.csv"});
    document.body.appendChild(a); a.click(); a.remove();
    msg.innerHTML = `<div class="verdict ok" style="margin-top:14px">Downloaded ${n} responses.</div>`;
  });
}

header();
