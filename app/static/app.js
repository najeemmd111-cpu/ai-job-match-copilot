// Job-Match Copilot frontend: plain JavaScript, no build step.

const $ = (sel) => document.querySelector(sel);

const state = { resume: "", job: "", result: null, versions: [], history: [], notes: "" };

// ---------- Small, safe markdown renderer ----------

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function inline(s) {
  return escapeHtml(s)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*])\*(?!\s)(.+?)\*/g, "$1<em>$2</em>")
    .replace(/`([^`]+)`/g, "<code>$1</code>");
}

function renderMarkdown(md) {
  const out = [];
  let list = null; // "ul" | "ol" | null
  const closeList = () => { if (list) { out.push(`</${list}>`); list = null; } };

  for (const raw of md.split("\n")) {
    const line = raw.trim();
    let m;
    if (!line || /^-{3,}$/.test(line)) { closeList(); continue; }
    if ((m = line.match(/^(#{1,4})\s+(.*)$/))) {
      closeList();
      const level = Math.min(m[1].length, 3);
      out.push(`<h${level}>${inline(m[2])}</h${level}>`);
    } else if ((m = line.match(/^[-*•]\s+(.*)$/))) {
      if (list !== "ul") { closeList(); out.push("<ul>"); list = "ul"; }
      out.push(`<li>${inline(m[1])}</li>`);
    } else if ((m = line.match(/^\d+[.)]\s+(.*)$/))) {
      if (list !== "ol") { closeList(); out.push("<ol>"); list = "ol"; }
      out.push(`<li>${inline(m[1])}</li>`);
    } else {
      closeList();
      out.push(`<p>${inline(line)}</p>`);
    }
  }
  closeList();
  return out.join("");
}

// ---------- Helpers ----------

async function api(path, options) {
  const res = await fetch(path, options);
  if (!res.ok) {
    let msg = `Something went wrong (error ${res.status}).`;
    try { msg = (await res.json()).detail || msg; } catch { /* not JSON */ }
    throw new Error(msg);
  }
  return res;
}

function setLoading(btn, loading, label) {
  btn.disabled = loading;
  btn.classList.toggle("is-loading", loading);
  if (label) btn.textContent = label;
}

function countUp(el, to) {
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduce) { el.textContent = Math.round(to); return; }
  const start = performance.now();
  const dur = 900;
  const step = (t) => {
    const p = Math.min((t - start) / dur, 1);
    el.textContent = Math.round(to * (1 - Math.pow(1 - p, 3)));
    if (p < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

function verdictFor(score) {
  if (score >= 70) return ["Strong match", "Your resume already speaks this job's language. Tailoring it will sharpen the details."];
  if (score >= 50) return ["Good match, with gaps", "You cover a lot of what they want. Close the missing skills below, or show them more clearly."];
  if (score >= 30) return ["Partial match", "Some of your experience fits. Tailoring your resume can make the overlap much easier to see."];
  return ["Weak match", "This role asks for a lot your resume doesn't show yet. Check the missing skills, or make sure you pasted the requirements and not the company text."];
}

// ---------- Resume upload ----------

const fileInput = $("#resume-input");
const dropzone = $("#dropzone");

function showFile(file) {
  dropzone.classList.toggle("has-file", !!file);
  $("#drop-main").textContent = file ? file.name : "Drop your PDF here or browse";
  $("#drop-sub").textContent = file ? `${(file.size / 1024).toFixed(0)} KB · click to choose another file` : "PDF or TXT, up to 5 MB";
}

fileInput.addEventListener("change", () => showFile(fileInput.files[0]));

["dragenter", "dragover"].forEach((ev) =>
  dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.add("is-over"); }));
["dragleave", "drop"].forEach((ev) =>
  dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.remove("is-over"); }));
dropzone.addEventListener("drop", (e) => {
  if (e.dataTransfer.files.length) {
    fileInput.files = e.dataTransfer.files;
    showFile(fileInput.files[0]);
  }
});

// ---------- Analyze ----------

$("#analyze-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const err = $("#form-error");
  const btn = $("#analyze-btn");
  err.textContent = "";

  const file = fileInput.files[0];
  const job = $("#job-input").value.trim();
  if (!file) { err.textContent = "Add your resume first."; return; }
  if (!job) { err.textContent = "Paste the job description first."; $("#job-input").focus(); return; }

  const body = new FormData();
  body.append("resume", file);
  body.append("job", job);

  setLoading(btn, true, "Comparing…");
  try {
    const data = await (await api("/api/analyze", { method: "POST", body })).json();
    state.resume = data.resume_text;
    state.job = job;
    state.result = data;

    showReport(data);
  } catch (ex) {
    err.textContent = ex.message;
  } finally {
    setLoading(btn, false, "Compare resume with job");
  }
});

function fillSkills(el, items, emptyText) {
  el.innerHTML = items.length
    ? items.map((s) => `<li>${escapeHtml(s)}</li>`).join("")
    : `<li class="empty">${emptyText}</li>`;
}

function showReport(r) {
  const report = $("#report");
  report.hidden = false;

  const [title, sub] = verdictFor(r.score);
  $("#verdict-title").textContent = title;
  $("#verdict-sub").textContent = sub;

  const sem = Math.round(r.semantic * 100);
  const cov = Math.round(r.coverage * 100);
  $("#val-sem").textContent = `${sem}%`;
  $("#val-cov").textContent = `${cov}%`;
  requestAnimationFrame(() => {
    $("#meter-sem").style.width = `${sem}%`;
    $("#meter-cov").style.width = `${cov}%`;
  });
  countUp($("#score-num"), r.score);

  fillSkills($("#matched"), r.matched, "None of the listed skills found yet");
  fillSkills($("#missing"), r.missing, "Nothing missing. Nice.");

  ["tailor", "bullets", "questions"].forEach((k) => { $(`#out-${k}`).innerHTML = ""; });
  resetEditor();

  report.scrollIntoView({ behavior: "smooth", block: "start" });
}

// ---------- Tabs (keyboard accessible) ----------

const tabs = [...document.querySelectorAll('[role="tab"]')];

function selectTab(tab) {
  tabs.forEach((t) => {
    const on = t === tab;
    t.setAttribute("aria-selected", on);
    t.tabIndex = on ? 0 : -1;
    $(`#${t.getAttribute("aria-controls")}`).hidden = !on;
  });
  tab.focus();
}

tabs.forEach((tab, i) => {
  tab.addEventListener("click", () => selectTab(tab));
  tab.addEventListener("keydown", (e) => {
    if (e.key === "ArrowRight") selectTab(tabs[(i + 1) % tabs.length]);
    if (e.key === "ArrowLeft") selectTab(tabs[(i - 1 + tabs.length) % tabs.length]);
  });
});

// ---------- Resume versions (tailoring + your own edits) ----------
// Every change pushes a version, so it can be undone.
// version = { kind: "tailor" | "edit", md, score, matched, missing }

const pts = (n) => Math.round(n);

const current = () => state.versions[state.versions.length - 1] || null;

function renderResume() {
  const v = current();
  const out = $("#out-tailor");
  $("#download").hidden = !v;
  if (!v) { out.innerHTML = ""; return; }

  const diff = pts(v.score) - pts(state.result.score);
  const change = diff > 0 ? `<b>+${diff} points</b>` : `${diff} points`;
  out.innerHTML =
    `<p class="score-change">Match score: ${pts(v.score)}/100 (${change} compared with your original resume).</p>` +
    `<article class="page">${renderMarkdown(v.md)}</article>` +
    (state.notes && v.kind === "tailor"
      ? `<aside class="notes"><h2>Skills this version couldn't honestly include</h2>${renderMarkdown(state.notes)}</aside>`
      : "");
}

function renderEditor() {
  const v = current();
  const missing = v ? v.missing : state.result.missing;
  $("#live-score").textContent = pts(v ? v.score : state.result.score);
  $("#undo-btn").hidden = !(v && v.kind === "edit");

  const ideas = [];
  if (missing.length > 1) ideas.push(`Add these skills from the job: ${missing.join(", ")}`);
  missing.slice(0, 4).forEach((s) => ideas.push(`Add ${s} to my skills. I used it in `));
  ideas.push("Make the professional summary match this job in 2 lines");
  ideas.push("Put my most relevant project first");
  ideas.push("Write the whole resume in English");

  $("#suggestions").innerHTML = ideas
    .map((t) => `<button type="button" class="chip">${escapeHtml(t.trim())}</button>`)
    .join("");
}

$("#suggestions").addEventListener("click", (e) => {
  const chip = e.target.closest(".chip");
  if (!chip) return;
  const input = $("#edit-input");
  // "I used it in" ideas are left open so you can finish the sentence
  input.value = chip.textContent.endsWith(" in") ? chip.textContent + " " : chip.textContent;
  input.focus();
  input.setSelectionRange(input.value.length, input.value.length);
});

function resetEditor() {
  state.versions = [];
  state.history = [];
  state.notes = "";
  $("#edit-log").innerHTML = "";
  $("#edit-input").value = "";
  renderResume();
  renderEditor();
}

// ---------- AI tools ----------

const labels = { tailor: "Tailor my resume", bullets: "Rewrite bullet points", questions: "Get interview questions" };

async function postJSON(path, payload) {
  const res = await api(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return res.json();
}

document.querySelectorAll("[data-run]").forEach((btn) => {
  btn.addEventListener("click", async () => {
    const kind = btn.dataset.run;
    const out = $(`#out-${kind}`);
    setLoading(btn, true, "Writing…");
    try {
      const data = await postJSON(`/api/${kind}`, { resume: state.resume, job: state.job, missing: state.result.missing });

      if (kind === "tailor") {
        state.notes = data.notes;
        state.versions.push({ kind: "tailor", md: data.resume_md, score: data.new_score, matched: data.matched, missing: data.missing });
        $("#edit-log").insertAdjacentHTML("beforeend",
          `<li class="log-entry log-entry--system"><p>Tailored the whole resume for this job.</p>` +
          `<p class="log-score">Score ${pts(state.result.score)} → <b>${pts(data.new_score)}</b></p></li>`);
        renderResume();
        renderEditor();
      } else {
        out.innerHTML = `<div class="prose">${renderMarkdown(data.markdown)}</div>`;
      }
      setLoading(btn, false, "Write it again");
    } catch (ex) {
      if (kind === "tailor") $("#out-tailor").innerHTML = `<p class="error">${escapeHtml(ex.message)}</p>`;
      else out.innerHTML = `<p class="error">${escapeHtml(ex.message)}</p>`;
      setLoading(btn, false, labels[kind]);
    }
  });
});

// ---------- Edit with AI ----------

$("#edit-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = $("#edit-input");
  const btn = $("#edit-btn");
  const instruction = input.value.trim();
  if (!instruction) { input.focus(); return; }

  const before = current();
  const beforeScore = before ? before.score : state.result.score;
  const log = $("#edit-log");
  log.insertAdjacentHTML("beforeend",
    `<li class="log-entry log-entry--you"><p>${escapeHtml(instruction)}</p></li>`);
  const pending = document.createElement("li");
  pending.className = "log-entry log-entry--ai is-pending";
  pending.innerHTML = "<p>Updating your resume…</p>";
  log.appendChild(pending);

  setLoading(btn, true, "Applying…");
  try {
    const data = await postJSON("/api/edit", {
      resume_md: before ? before.md : state.resume,
      job: state.job,
      instruction,
      history: state.history,
    });
    state.versions.push({ kind: "edit", md: data.resume_md, score: data.score, matched: data.matched, missing: data.missing });
    state.history.push(instruction);

    const diff = pts(data.score) - pts(beforeScore);
    const sign = diff > 0 ? "+" : "";
    pending.classList.remove("is-pending");
    pending.innerHTML =
      `<div class="log-text">${renderMarkdown(data.summary)}</div>` +
      `<p class="log-score">Score ${pts(beforeScore)} → <b>${pts(data.score)}</b> <span class="${diff >= 0 ? "up" : "down"}">(${sign}${diff})</span></p>`;
    input.value = "";
    renderResume();
    renderEditor();
  } catch (ex) {
    pending.classList.remove("is-pending");
    pending.classList.add("is-error");
    pending.innerHTML = `<p>${escapeHtml(ex.message)}</p>`;
  } finally {
    setLoading(btn, false, "Apply change");
  }
});

$("#edit-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) $("#edit-form").requestSubmit();
});

$("#undo-btn").addEventListener("click", () => {
  if (!current() || current().kind !== "edit") return;
  state.versions.pop();
  state.history.pop();
  const log = $("#edit-log");
  // remove the AI reply and your instruction
  log.lastElementChild?.remove();
  log.lastElementChild?.remove();
  log.insertAdjacentHTML("beforeend", `<li class="log-entry log-entry--system"><p>Undid the last change.</p></li>`);
  renderResume();
  renderEditor();
});

// ---------- Download ----------

$("#download-btn").addEventListener("click", async () => {
  const btn = $("#download-btn");
  const fmt = document.querySelector('input[name="fmt"]:checked').value;
  setLoading(btn, true, "Preparing file…");
  try {
    const res = await api("/api/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ markdown: current().md, format: fmt }),
    });
    const url = URL.createObjectURL(await res.blob());
    const a = Object.assign(document.createElement("a"), { href: url, download: `tailored_resume.${fmt}` });
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (ex) {
    $("#out-tailor").insertAdjacentHTML("beforeend", `<p class="error">${escapeHtml(ex.message)}</p>`);
  } finally {
    setLoading(btn, false, "Download resume");
  }
});
