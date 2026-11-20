/* app.js -- shared page code: navigation, survey form, results renderer. */

const PAGES = [["/", "Take the Survey"], ["/results", "Results & Analysis"],
               ["/methodology", "Methodology"], ["/admin", "Team / Admin"]];

function header() {
  const here = location.pathname.replace(/\.html$/, "").replace(/\/index$/, "/") || "/";
  const links = PAGES.map(([href, t]) =>
    `<a href="${href}" class="${here === href ? "active" : ""}">${t}</a>`).join("");
  document.body.insertAdjacentHTML("afterbegin",
    `<header><div class="bar"><a class="brand" href="/">RU <span>Stressed?</span></a>
     <nav>${links}</nav></div></header>`);
  document.body.insertAdjacentHTML("beforeend",
    `<footer>IE 320 Engineering Statistics · Group 12: Udaya Raja (leader), Dhruv Nagpal,
     Akshita Krishnakumar, Poorvi Shekar</footer>`);
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
  if (!r.ok) throw new Error((body && body.detail) || `Server error (${r.status})`);
  return body;
}

/* ------------------------------------------------------------------ */
/* Survey page                                                         */
/* ------------------------------------------------------------------ */
function questionHTML(q) {
  const k = q.key, title = `<label class="qt" id="t_${k}"><span class="num">Q${q.num}.</span>${esc(q.text)}</label>`;
  if (q.kind === "category") {
    return title + `<select name="${k}" aria-labelledby="t_${k}"><option value="">Select…</option>` +
      q.options.map(o => `<option>${esc(o)}</option>`).join("") + `</select>`;
  }
  if (q.kind === "scale") {
    const vals = []; for (let v = q.lo; v <= q.hi; v++) vals.push(v);
    const lab = v => q.labels ? q.labels[v - q.lo] : v;
    const pills = vals.map(v => `<input type="radio" id="${k}_${v}" name="${k}" value="${v}">` +
      `<label for="${k}_${v}">${esc(lab(v))}</label>`).join("");
    const ends = q.labels ? "" : `<div class="ends"><span>${esc(q.lo_label)}</span><span>${esc(q.hi_label)}</span></div>`;
    return title + `<div class="pills ${q.labels ? "" : "ten"}" role="radiogroup" aria-labelledby="t_${k}">${pills}</div>` + ends;
  }
  return title + `<input type="number" name="${k}" min="${q.lo}" max="${q.hi}" step="${q.step}"
    inputmode="decimal" placeholder="e.g. ${q.default}" aria-labelledby="t_${k}"><span class="unit">${esc(q.unit)}</span>`;
}

async function surveyPage() {
  const root = document.getElementById("root");
  let cfg;
  try { cfg = await api("/api/questions"); }
  catch (e) { root.innerHTML = `<div class="error">${esc(e.message)}</div>`; return; }

  const prior = localStorage.getItem("stress_submitted");
  root.innerHTML = `
    <h1>${esc(cfg.title)}</h1>
    <p class="sub">${esc(cfg.group)} · IE 320 Engineering Statistics · Rutgers University.
      Anonymous: no name, NetID or email is collected. Takes about 1 minute.</p>
    ${prior ? `<div class="warn">It looks like you already submitted from this device. Please submit only once.</div>` : ""}
    <form id="f" novalidate>
      ${cfg.questions.map(q => `<div class="q" data-key="${q.key}">${questionHTML(q)}</div>`).join("")}
      <label class="consent"><input type="checkbox" name="consent">
        <span>I am a current Rutgers student and agree that my anonymous answers may be used for this class project.</span></label>
      <div id="err"></div>
      <button class="primary" type="submit">Submit</button>
    </form>`;

  const f = document.getElementById("f");
  f.addEventListener("change", e => e.target.closest(".q")?.classList.remove("missing"));
  f.addEventListener("submit", async e => {
    e.preventDefault();
    const err = document.getElementById("err"); err.innerHTML = "";
    const body = { consent: f.consent.checked };
    const missing = [];
    for (const q of cfg.questions) {
      const el = f.elements[q.key];
      const v = el instanceof RadioNodeList ? el.value : el.value;
      const box = f.querySelector(`.q[data-key="${q.key}"]`);
      if (v === "" || v == null) { missing.push(`Q${q.num}`); box.classList.add("missing"); continue; }
      if (q.kind !== "category") {
        const x = Number(v);
        if (Number.isNaN(x) || x < q.lo || x > q.hi) {
          missing.push(`Q${q.num} (${q.lo}–${q.hi})`); box.classList.add("missing"); continue;
        }
        body[q.key] = x;
      } else body[q.key] = v;
    }
    if (missing.length) { err.innerHTML = `<div class="error">Please answer: ${esc(missing.join(", "))}</div>`;
      f.querySelector(".q.missing")?.scrollIntoView({behavior: "smooth", block: "center"}); return; }
    if (!body.consent) { err.innerHTML = `<div class="error">Please tick the consent box to submit.</div>`; return; }
    const btn = f.querySelector("button"); btn.disabled = true; btn.textContent = "Saving…";
    try {
      const res = await api("/api/submit", { method: "POST", headers: {"Content-Type": "application/json"},
                                             body: JSON.stringify(body) });
      localStorage.setItem("stress_submitted", "1");
      showResult(res);
    } catch (ex) {
      err.innerHTML = `<div class="error">${esc(ex.message)}</div>`;
      btn.disabled = false; btn.textContent = "Submit";
    }
  });
}

function showResult(r) {
  const under = r.classification === "Under Stress";
  const color = under ? "var(--red)" : "var(--green)";
  let compare = "";
  if (r.n) {
    compare = `<p>Your Stress Index is higher than or equal to <b>${r.percentile.toFixed(0)}%</b> of the
      ${r.n} students surveyed so far. The average for <b>${esc(r.dept)}</b> is <b>${r.dept_mean.toFixed(1)}</b>
      (n = ${r.dept_n}); the overall average is <b>${r.overall_mean.toFixed(1)}</b>.</p>`;
  }
  const notes = r.notes.length ? `<p><b>Things in your answers that are linked with higher stress:</b></p>
      <ul>${r.notes.map(n => `<li>${esc(n)}</li>`).join("")}</ul>` : "";
  document.getElementById("root").innerHTML = `
    <h1>Thank you!</h1><p class="sub">✅ Your response was saved.</p>
    <div class="result" style="background:${color}">
      <div class="lbl">Your stress assessment</div>
      <div class="cls">${esc(r.classification)}</div>
      <div class="lbl">Stress Index = ${r.stress_index.toFixed(1)} / 100</div>
    </div>
    <div class="card" style="margin-top:16px">
      <div class="meter"><div class="mid"></div><div class="fill" style="left:calc(${r.stress_index}% - 2px)"></div></div>
      <div class="scale"><span>0 · no stress</span><span>${r.threshold} · threshold</span><span>100 · extreme</span></div>
      <p class="muted">Rule: Under Stress if Stress Index ≥ ${r.threshold}. The Stress Index averages your
        Q2 (stress 1–10) and Q3 (overwhelmed 1–5) answers, each rescaled to 0–100.</p>
      ${compare}${notes}
      <p class="muted">This is a class-project screening, not a medical assessment. Rutgers CAPS (Counseling,
        ADAP &amp; Psychiatric Services) offers free support to students.</p>
      <p><a href="/results">See the results so far →</a></p>
    </div>`;
  scrollTo(0, 0);
}

/* ------------------------------------------------------------------ */
/* Results page: draws blocks sent by /api/results                     */
/* ------------------------------------------------------------------ */
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
      node.innerHTML = `<table><thead><tr>${b.columns.map(c => `<th>${esc(c)}</th>`).join("")}</tr></thead><tbody>` +
        b.rows.map(r => `<tr>${r.map(c => `<td>${esc(c)}</td>`).join("")}</tr>`).join("") + `</tbody></table>`;
    } else if (b.type === "plot") {
      node = document.createElement("div"); node.className = "plot";
      el.appendChild(node);
      Plotly.newPlot(node, b.fig.data, b.fig.layout, {responsive: true, displaylogo: false});
      continue;
    } else if (b.type === "row") {
      node = document.createElement("div"); node.className = "row2";
      el.appendChild(node); renderBlocks(b.blocks, node); continue;
    } else if (b.type === "plotselect") {
      node = document.createElement("div");
      const sel = document.createElement("select");
      b.options.forEach((o, i) => sel.add(new Option(o.label, i)));
      const holder = document.createElement("div"); holder.className = "plot";
      node.append(sel, holder); el.appendChild(node);
      const draw = () => { const o = b.options[sel.value]; Plotly.react(holder, o.fig.data, o.fig.layout, {responsive: true, displaylogo: false}); };
      sel.addEventListener("change", draw); draw();
      continue;
    } else continue;
    el.appendChild(node);
  }
}

async function resultsPage() {
  const root = document.getElementById("root");
  root.innerHTML = `<h1>Results &amp; Statistical Analysis</h1><div class="loading">Running the analyses…</div>`;
  let r;
  try { r = await api("/api/results"); }
  catch (e) { root.innerHTML += `<div class="error">${esc(e.message)}</div>`; root.querySelector(".loading").remove(); return; }
  root.innerHTML = `<h1>Results &amp; Statistical Analysis</h1>
    <p class="sub">Live: recomputed from all ${r.n} valid responses · α = ${r.alpha} · storage: ${esc(r.storage)}</p>
    <details id="prog" ${r.n < 150 ? "open" : ""}><summary>Data-collection progress vs. project requirements</summary><div></div></details>
    <div class="tabs" id="tabs"></div><div id="tab"></div>`;
  renderBlocks(r.progress, document.querySelector("#prog div"));
  if (!r.tabs.length) {
    document.getElementById("tab").innerHTML = `<div class="warn">Analyses appear once at least 5 responses have been collected.</div>`;
    return;
  }
  const tabs = document.getElementById("tabs"), body = document.getElementById("tab");
  const show = i => {
    [...tabs.children].forEach((b, j) => b.classList.toggle("active", i === j));
    body.innerHTML = ""; renderBlocks(r.tabs[i].blocks, body);
    history.replaceState(null, "", "#" + i);
  };
  r.tabs.forEach((t, i) => { const b = document.createElement("button"); b.textContent = t.name; b.onclick = () => show(i); tabs.appendChild(b); });
  const start = Math.min(r.tabs.length - 1, parseInt(location.hash.slice(1)) || 0);
  show(start);
}

/* ------------------------------------------------------------------ */
/* Methodology page                                                     */
/* ------------------------------------------------------------------ */
async function methodologyPage() {
  const cfg = await api("/api/questions");
  const rows = cfg.questions.map(q => {
    let resp;
    if (q.kind === "category") resp = "Choice: " + q.options.join(", ");
    else if (q.labels) resp = q.labels.map((l, i) => `${i + 1} = ${l}`).join(" / ");
    else if (q.kind === "scale") resp = `${q.lo_label} to ${q.hi_label}`;
    else resp = `Number, ${q.lo}–${q.hi} ${q.unit}`;
    const role = {group: "Grouping", stress: "Stress (response)", factor: "Factor"}[q.role];
    return `<tr><td>Q${q.num}</td><td style="white-space:normal;text-align:left">${esc(q.text)}</td>
            <td style="white-space:normal;text-align:left">${esc(resp)}</td><td>${role}</td></tr>`;
  }).join("");
  document.getElementById("qtable").innerHTML =
    `<table><thead><tr><th>#</th><th style="text-align:left">Question</th><th style="text-align:left">Response format</th><th>Role</th></tr></thead><tbody>${rows}</tbody></table>`;
}

/* ------------------------------------------------------------------ */
/* Admin page                                                            */
/* ------------------------------------------------------------------ */
function adminPage() {
  const f = document.getElementById("af"), msg = document.getElementById("amsg");
  f.addEventListener("submit", async e => {
    e.preventDefault(); msg.innerHTML = "";
    const r = await fetch("/api/export", { headers: { "X-Admin-Password": f.pw.value } });
    if (!r.ok) {
      let d = "Error"; try { d = (await r.json()).detail; } catch {}
      msg.innerHTML = `<div class="error">${esc(d)}</div>`; return;
    }
    const text = await r.text();
    const n = Math.max(0, text.trim().split("\n").length - 1);
    const url = URL.createObjectURL(new Blob([text], {type: "text/csv"}));
    const a = Object.assign(document.createElement("a"), {href: url, download: "stress_survey_responses.csv"});
    document.body.appendChild(a); a.click(); a.remove();
    msg.innerHTML = `<div class="verdict ok">Downloaded ${n} responses.</div>`;
  });
}

header();
