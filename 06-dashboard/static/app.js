// CCA-F Study Dashboard — static, offline, vanilla.
// Reads ../data/dashboard-data.json and renders the seven pinned widgets.
// No external libraries, no build step.

"use strict";

const SVG_NS = "http://www.w3.org/2000/svg";
const PASS_MARK_DEFAULT = 720;
const WEAK_LIMIT = 8;

// ---------- bootstrap ----------

document.addEventListener("DOMContentLoaded", () => {
  fetch('../data/dashboard-data.json', { cache: "no-store" })
    .then((r) => {
      if (!r.ok) throw new Error("dashboard-data.json HTTP " + r.status);
      return r.json();
    })
    .then(render)
    .catch((err) => renderError(err));
});

// ---------- helpers ----------

function $(sel, root) {
  return (root || document).querySelector(sel);
}

function clear(node) {
  while (node && node.firstChild) node.removeChild(node.firstChild);
}

function el(tag, attrs, children) {
  const node = document.createElement(tag);
  if (attrs) {
    for (const k in attrs) {
      if (k === "class") node.className = attrs[k];
      else if (k === "text") node.textContent = attrs[k];
      else node.setAttribute(k, attrs[k]);
    }
  }
  if (children) {
    for (const c of children) {
      if (c == null) continue;
      node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    }
  }
  return node;
}

function svgEl(tag, attrs) {
  const node = document.createElementNS(SVG_NS, tag);
  if (attrs) {
    for (const k in attrs) node.setAttribute(k, attrs[k]);
  }
  return node;
}

function fmtPct(n) {
  if (n == null || Number.isNaN(n)) return "—";
  return Math.round(n * 100) + "%";
}

function fmtScore(n) {
  if (n == null || Number.isNaN(n)) return "—";
  return String(Math.round(n));
}

function fmtSignedGap(gap) {
  if (gap == null || Number.isNaN(gap)) return "—";
  if (gap > 0) return "+" + gap + " over pass mark";
  if (gap < 0) return gap + " to pass mark";
  return "at pass mark";
}

function fmtDateTime(iso) {
  if (!iso) return "—";
  // Render as compact ISO-ish without seconds. No locale to keep deterministic.
  const m = /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/.exec(iso);
  return m ? m[1] + " " + m[2] + "Z" : iso;
}

function clamp(n, lo, hi) {
  return Math.max(lo, Math.min(hi, n));
}

function barColorClass(accuracy) {
  if (accuracy == null) return "bar-row__fill--low";
  if (accuracy >= 0.75) return "bar-row__fill";
  if (accuracy >= 0.5) return "bar-row__fill--mid";
  return "bar-row__fill--low";
}

// ---------- render entry ----------

function render(data) {
  const passMark = data && data.pass_mark ? data.pass_mark : PASS_MARK_DEFAULT;
  const latest_attempt = data ? data.latest_attempt : null;

  renderHeader(data, passMark);
  renderBanner(latest_attempt, passMark);
  renderProgress(latest_attempt, passMark);
  renderTrend(data && data.trend ? data.trend : [], passMark);
  renderDomains(data && data.domain_breakdown ? data.domain_breakdown : []);
  renderScenarios(data && data.scenario_breakdown ? data.scenario_breakdown : []);
  renderWeakConcepts(data && data.weak_concepts ? data.weak_concepts : []);
  renderLabs(data && data.lab_progress ? data.lab_progress : null);
}

function renderError(err) {
  const root = document.getElementById("dashboard-root");
  if (!root) return;
  clear(root);
  root.appendChild(
    el("section", { class: "card", role: "alert" }, [
      el("h2", { class: "card__head", text: "Unable to load dashboard-data.json" }),
      el("p", { class: "empty", text: String(err && err.message ? err.message : err) }),
      el("p", { class: "empty", text: "Run the exporter, then reload this page." }),
    ])
  );
}

// ---------- header meta ----------

function renderHeader(data, passMark) {
  const passMarkEl = document.getElementById("meta-pass-mark");
  if (passMarkEl) passMarkEl.textContent = String(passMark);

  const gen = document.getElementById("meta-generated-at");
  if (gen) gen.textContent = fmtDateTime(data && data.generated_at);

  const attempt = document.getElementById("meta-attempt-id");
  if (attempt) {
    const a = data && data.latest_attempt;
    attempt.textContent = a && a.attempt_id ? a.attempt_id : "(no attempts yet)";
  }
}

// ---------- 1) pass banner ----------

function renderBanner(latest_attempt, passMark) {
  const banner = document.getElementById("pass-banner");
  if (!banner) return;
  const verdict = $(".banner__verdict", banner);
  const scoreNum = $(".banner__score-num", banner);
  const gap = $(".banner__gap", banner);

  banner.classList.remove("banner--pass", "banner--fail", "banner--unknown");

  if (!latest_attempt) {
    banner.classList.add("banner--unknown");
    verdict.textContent = "NO DATA";
    scoreNum.textContent = "—";
    gap.textContent = "no attempts yet · pass mark " + passMark;
    return;
  }

  const isPass = !!latest_attempt.pass;
  banner.classList.add(isPass ? "banner--pass" : "banner--fail");
  verdict.textContent = isPass ? "PASS" : "FAIL";
  scoreNum.textContent = fmtScore(latest_attempt.scaled_score);
  gap.textContent = fmtSignedGap(latest_attempt.pass_gap);
}

// ---------- 2) pass progress ----------

function renderProgress(latest_attempt, passMark) {
  const card = document.getElementById("pass-progress");
  if (!card) return;
  const fill = $(".progress__fill", card);
  const cur = $(".progress__current", card);
  const tgt = $(".progress__target", card);

  card.classList.remove("progress--fail");
  if (tgt) tgt.textContent = String(passMark);

  if (!latest_attempt) {
    fill.style.width = "0%";
    if (cur) cur.textContent = "0";
    fill.setAttribute("aria-valuenow", "0");
    return;
  }

  const score = latest_attempt.scaled_score || 0;
  const ratio = passMark > 0 ? score / passMark : 0;
  const widthPct = clamp(ratio * 100, 0, 100);
  fill.style.width = widthPct.toFixed(1) + "%";
  if (cur) cur.textContent = fmtScore(score);

  if (!latest_attempt.pass) card.classList.add("progress--fail");
}

// ---------- 3) domain breakdown ----------

function renderDomains(domains) {
  const card = document.getElementById("domain-breakdown");
  if (!card) return;
  const list = $(".bars", card);
  clear(list);

  // Spec: always 5 rows (D1-D5). Build a stable scaffold even when data missing.
  const slots = ["D1", "D2", "D3", "D4", "D5"];
  const byId = {};
  for (const d of domains || []) byId[d.domain] = d;

  // Sort visually by accuracy ascending (weakest first) so the eye finds the
  // weakest domain instantly, while keeping the D-ids visible.
  const rows = slots.map((id) => byId[id] || { domain: id, title: "", accuracy: null, correct: 0, total: 0, weight: null });
  rows.sort((a, b) => {
    const aa = a.accuracy == null ? 1.1 : a.accuracy;
    const bb = b.accuracy == null ? 1.1 : b.accuracy;
    return aa - bb;
  });

  for (const d of rows) {
    list.appendChild(buildBarRow({
      idText: d.domain,
      title: d.title || "",
      accuracy: d.accuracy,
      correct: d.correct,
      total: d.total,
    }));
  }
}

// ---------- 4) scenario breakdown ----------

function renderScenarios(scenarios) {
  const card = document.getElementById("scenario-breakdown");
  if (!card) return;
  const list = $(".bars", card);
  clear(list);

  if (!scenarios || scenarios.length === 0) {
    list.appendChild(el("li", { class: "empty", text: "no scenario data yet" }));
    return;
  }

  const sorted = scenarios.slice().sort((a, b) => {
    const aa = a.accuracy == null ? 1.1 : a.accuracy;
    const bb = b.accuracy == null ? 1.1 : b.accuracy;
    return aa - bb;
  });

  for (const s of sorted) {
    list.appendChild(buildBarRow({
      idText: s.scenario,
      title: "",
      accuracy: s.accuracy,
      correct: s.correct,
      total: s.total,
    }));
  }
}

function buildBarRow({ idText, title, accuracy, correct, total }) {
  const li = el("li", { class: "bar-row" });

  const labelChildren = [el("span", { class: "lbl-id", text: idText })];
  if (title) labelChildren.push(el("span", { class: "lbl-title", text: title }));
  li.appendChild(el("div", { class: "bar-row__label" }, labelChildren));

  const svg = svgEl("svg", {
    class: "bar-row__svg",
    viewBox: "0 0 100 14",
    preserveAspectRatio: "none",
    role: "img",
    "aria-label": idText + " accuracy " + (accuracy == null ? "n/a" : fmtPct(accuracy)),
  });
  svg.appendChild(svgEl("rect", { class: "bar-row__track", x: "0", y: "2", width: "100", height: "10", rx: "1" }));
  const w = accuracy == null ? 0 : clamp(accuracy, 0, 1) * 100;
  const fillRect = svgEl("rect", {
    class: barColorClass(accuracy),
    x: "0", y: "2", width: String(w.toFixed(2)), height: "10", rx: "1",
  });
  svg.appendChild(fillRect);
  li.appendChild(svg);

  const valueText = (accuracy == null ? "—" : fmtPct(accuracy)) +
    (total ? "  " + (correct != null ? correct : 0) + "/" + total : "");
  li.appendChild(el("div", { class: "bar-row__value", text: valueText }));

  return li;
}

// ---------- 5) weak concepts ----------

function renderWeakConcepts(weak) {
  const card = document.getElementById("weak-concepts");
  if (!card) return;
  const list = $(".weak", card);
  clear(list);

  if (!weak || weak.length === 0) {
    list.appendChild(el("li", { class: "empty", text: "no weak concepts yet" }));
    return;
  }

  const sorted = weak.slice().sort((a, b) => {
    if (b.miss_rate !== a.miss_rate) return b.miss_rate - a.miss_rate;
    return (b.missed || 0) - (a.missed || 0);
  }).slice(0, WEAK_LIMIT);

  for (const w of sorted) {
    list.appendChild(el("li", { class: "weak__row" }, [
      el("span", { class: "weak__tag", text: w.concept_tag }),
      el("span", { class: "weak__seen", text: (w.missed || 0) + "/" + (w.seen || 0) + " missed" }),
      el("span", { class: "weak__rate", text: fmtPct(w.miss_rate) }),
    ]));
  }
}

// ---------- 6) lab progress ----------

function renderLabs(labs) {
  const card = document.getElementById("lab-progress");
  if (!card) return;
  const counts = $(".labs__counts", card);
  const list = $(".labs__list", card);
  clear(list);

  const safe = labs || { completed: 0, in_progress: 0, not_started: 0, total_labs: 0, recommended_next: [] };
  for (const node of counts.querySelectorAll("[data-key]")) {
    const k = node.getAttribute("data-key");
    node.textContent = String(safe[k] != null ? safe[k] : 0);
  }

  const rec = safe.recommended_next || [];
  if (rec.length === 0) {
    list.appendChild(el("li", { class: "empty", text: "no lab recommendations" }));
    return;
  }
  for (const r of rec) {
    list.appendChild(el("li", { class: "labs__list-item" }, [
      el("span", { class: "labs__list-id", text: r.lab_id }),
      el("span", { class: "labs__list-reason", text: r.reason || "" }),
    ]));
  }
}

// ---------- 7) score trend ----------

function renderTrend(trend, passMark) {
  const card = document.getElementById("score-trend");
  if (!card) return;
  const host = $(".trend", card);
  clear(host);

  if (!trend || trend.length === 0) {
    host.appendChild(el("p", { class: "empty", text: "no attempts yet" }));
    return;
  }

  const points = trend.map((t) => ({
    id: t.attempt_id,
    iso: t.finished_at,
    score: t.scaled_score == null ? 0 : t.scaled_score,
    pass: t.scaled_score != null && t.scaled_score >= passMark,
  }));

  // Geometry: 320 viewBox wide, 100 tall, padding for axes.
  const W = 320, H = 100;
  const padL = 28, padR = 8, padT = 8, padB = 18;
  const innerW = W - padL - padR;
  const innerH = H - padT - padB;

  const scores = points.map((p) => p.score);
  const minScore = Math.min(passMark - 40, ...scores);
  const maxScore = Math.max(passMark + 40, ...scores, 1000);
  const yScale = (s) => padT + innerH - ((s - minScore) / (maxScore - minScore || 1)) * innerH;
  const xScale = (i) => {
    if (points.length === 1) return padL + innerW / 2;
    return padL + (i / (points.length - 1)) * innerW;
  };

  const svg = svgEl("svg", {
    class: "trend__svg",
    viewBox: "0 0 " + W + " " + H,
    preserveAspectRatio: "none",
    role: "img",
    "aria-label": "scaled score trend across " + points.length + " attempts",
  });

  // y axis baseline
  svg.appendChild(svgEl("line", {
    class: "trend__axis",
    x1: padL, y1: padT + innerH, x2: W - padR, y2: padT + innerH,
  }));
  // pass mark threshold
  const tY = yScale(passMark);
  svg.appendChild(svgEl("line", {
    class: "trend__threshold",
    x1: padL, y1: tY, x2: W - padR, y2: tY,
  }));
  svg.appendChild(svgEl("text", {
    x: padL - 4, y: tY + 3, "text-anchor": "end",
    "font-family": "ui-monospace, monospace", "font-size": "8", fill: "#6b6e78",
  })).textContent = String(passMark);

  // y-axis end labels (min and max)
  const minLabel = svgEl("text", {
    x: padL - 4, y: padT + innerH, "text-anchor": "end",
    "font-family": "ui-monospace, monospace", "font-size": "8", fill: "#6b6e78",
  });
  minLabel.textContent = String(Math.round(minScore));
  svg.appendChild(minLabel);

  const maxLabel = svgEl("text", {
    x: padL - 4, y: padT + 6, "text-anchor": "end",
    "font-family": "ui-monospace, monospace", "font-size": "8", fill: "#6b6e78",
  });
  maxLabel.textContent = String(Math.round(maxScore));
  svg.appendChild(maxLabel);

  // area + line path
  if (points.length >= 2) {
    let areaD = "M " + xScale(0) + " " + (padT + innerH);
    for (let i = 0; i < points.length; i++) {
      areaD += " L " + xScale(i) + " " + yScale(points[i].score);
    }
    areaD += " L " + xScale(points.length - 1) + " " + (padT + innerH) + " Z";
    svg.appendChild(svgEl("path", { class: "trend__area", d: areaD }));

    let lineD = "M " + xScale(0) + " " + yScale(points[0].score);
    for (let i = 1; i < points.length; i++) {
      lineD += " L " + xScale(i) + " " + yScale(points[i].score);
    }
    svg.appendChild(svgEl("path", { class: "trend__line", d: lineD }));
  }

  // dots
  for (let i = 0; i < points.length; i++) {
    const p = points[i];
    svg.appendChild(svgEl("circle", {
      class: "trend__dot" + (p.pass ? "" : " trend__dot--fail"),
      cx: xScale(i), cy: yScale(p.score), r: "3.2",
    }));
  }

  host.appendChild(svg);

  // small legend / range
  const first = points[0];
  const last = points[points.length - 1];
  const delta = last.score - first.score;
  const deltaTxt = (delta > 0 ? "+" : "") + delta;
  const legend = el("div", { class: "trend__legend" }, [
    el("span", { text: fmtDateTime(first.iso) + " · " + first.score }),
    el("span", { text: "Δ " + deltaTxt }),
    el("span", { text: fmtDateTime(last.iso) + " · " + last.score }),
  ]);
  host.appendChild(legend);
}
