"use strict";

const data = JSON.parse(document.getElementById("report-data").textContent);
const report = data.report;
const snapshots = { head: data.sources, base: data.baseline || {} };
const rules = new Map(report.rules.map((rule) => [rule.id, rule]));
const results = new Map(
  report.results.map((result) => [result.rule_id, result]),
);
const ci = report.ci_evidence;
const ciByRule = new Map();
for (const check of ci?.checks || []) {
  if (check.mapping !== "linked") continue;
  if (!ciByRule.has(check.rule_id)) ciByRule.set(check.rule_id, []);
  ciByRule.get(check.rule_id).push(check);
}
const gaps = report.coverage.extraction_gaps || [];
const comparison = report.comparison;
const changeLabels = data.comparisonLabels || {};
const statuses = { fail: "Fail", unknown: "Unknown", pass: "Pass" };
const mappingLabels = {
  rule_edited: "Rule edited after mapping",
  rule_missing: "Rule absent from this review",
};
const initial = new URLSearchParams(location.hash.slice(1));
const viewNames = [
  "overview",
  "results",
  "rules",
  "scope",
  ...(ci ? ["ci"] : []),
];
let view = viewNames.includes(initial.get("view"))
  ? initial.get("view")
  : "overview";
let filter = "all";
let query = "";
let page = 0;
const pageSize = 50;

const counts = { fail: 0, unknown: 0, pass: 0 };
for (const result of results.values()) counts[result.status] += 1;
const attention = report.attention_rule_ids || [
  ...report.results
    .filter(({ status }) => status === "fail")
    .map(({ rule_id }) => rule_id),
  ...report.results
    .filter(({ status }) => status === "unknown")
    .map(({ rule_id }) => rule_id),
];
const attentionSet = new Set(attention);
const ordered = [
  ...attention,
  ...report.rules.map(({ id }) => id).filter((id) => !attentionSet.has(id)),
];

function esc(value) {
  return String(value ?? "").replace(
    /[&<>"']/g,
    (char) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      })[char],
  );
}

function title(rule) {
  return rule.title || rule.statement;
}

function plural(count, word) {
  return `${count} ${word}${count === 1 ? "" : "s"}`;
}

function description(key) {
  return String(key || "").replaceAll("_", " ");
}

function button(text, action, id = "", options = {}) {
  const { primary, path, start, end, side, ruleId } = options;
  return `<button type="button" data-action="${esc(action)}" data-id="${esc(id)}"${primary ? ' data-variant="primary"' : ""}${path ? ` data-path="${esc(path)}"` : ""}${side ? ` data-side="${esc(side)}"` : ""}${start ? ` data-start="${esc(start)}" data-end="${esc(end || start)}"` : ""}${ruleId ? ` data-rule-id="${esc(ruleId)}"` : ""}>${esc(text)}</button>`;
}

function statusBadge(label, tone) {
  return `<span class="verdict verdict-${esc(tone)}">${esc(label)}</span>`;
}

function shortCommit(revision) {
  return revision?.commit.slice(0, 12);
}

function checkFor(result) {
  return (
    report.suggested_checks?.[result.rule_id] ||
    result.recommended_check ||
    result.next_step
  );
}

function flaggedByCi(id) {
  return ciByRule
    .get(id)
    ?.some(({ status }) => status === "failed" || status === "mixed");
}

function resultBadge(result) {
  const label = changeLabels[result.comparison_status];
  if (result.status !== "fail" && flaggedByCi(result.rule_id)) {
    return statusBadge("CI needs attention", "unknown");
  }
  const tone =
    result.comparison_status === "inconclusive" ||
    result.comparison_status === "needs_change_evidence"
      ? "unknown"
      : result.status;
  return statusBadge(label || statuses[result.status], tone);
}

function sourceButton(ref, side, ruleId, label) {
  const start = ref.start_line;
  const end = ref.end_line;
  return button(
    label || `${ref.path}:${start}${end && end !== start ? `–${end}` : ""}`,
    "source",
    "",
    { path: ref.path, start, end, side, ruleId },
  );
}

function emptyRules() {
  const failed = gaps.some(({ reason }) => reason === "model_unavailable");
  return `<section class="finding-card" role="status">
    <h3>${failed ? "Rule extraction failed" : "No rules to verify"}</h3>
    <p>${
      failed
        ? "The model could not extract rules. No rules were verified. Start a new run after the model is ready."
        : "Review the selected specification files or add rules in Knowledge before starting a new run."
    }</p>
    ${gaps.length ? `<p>${plural(gaps.length, "source section")} ${gaps.length === 1 ? "remains" : "remain"} unresolved.</p>` : ""}
    ${button("Review source coverage", "view", "scope", { primary: true })}
  </section>`;
}

function metrics() {
  const regressions = comparison?.summary.regression || 0;
  const values = [
    ...(comparison
      ? [
          [regressions, "New regressions", "regression"],
          [counts.fail - regressions, "Other failures", "other_failures"],
        ]
      : [[counts.fail, "Failed rules", "fail"]]),
    [
      counts.unknown,
      comparison ? "Proposed unknowns" : "Unknown rules",
      "unknown",
    ],
    [counts.pass, comparison ? "Proposed passes" : "Passing rules", "pass"],
  ];
  return `<div class="review-metrics">${values
    .map(
      ([count, label, id]) =>
        `<button type="button" class="review-metric" data-action="filter" data-id="${id}">
      <strong>${count}</strong><span>${esc(label)}</span></button>`,
    )
    .join("")}</div>`;
}

function ciStatusSummary() {
  const checks = ci.checks;
  const failed = checks.filter(({ status }) => status === "failed").length;
  const unresolved = checks.filter(
    ({ mapping, status }) =>
      mapping !== "linked" || ["missing", "mixed", "skipped"].includes(status),
  ).length;
  return [
    plural(checks.length, "test mapping"),
    ...(failed ? [`${failed} failed`] : []),
    ...(unresolved ? [`${unresolved} to review`] : []),
  ].join(" · ");
}

function overview() {
  if (!report.rules.length) return `<h2>Overview</h2>${emptyRules()}`;
  const count = attention.length;
  const heading = count
    ? `${plural(count, "rule")} ${count === 1 ? "needs" : "need"} attention`
    : "Review complete within this scope";
  const summary = comparison
    ? `Base <code>${esc(shortCommit(comparison.base))}</code> <span aria-hidden="true">→</span>
       proposed <code>${esc(shortCommit(comparison.head))}</code> · ${plural(comparison.changes.length, "captured file")} changed`
    : `Static review of ${plural(report.rules.length, "approved rule")}`;
  return `<section class="review-intro">
    <h2>${heading}</h2><p class="review-meta">${summary}</p>
    ${!count ? "<p>The inspected source supports the reviewed rules within the captured scope.</p>" : ""}
    ${metrics()}
  </section>
  ${
    count
      ? `<section class="finding-list" aria-labelledby="attention-heading">
    <h3 id="attention-heading">Start here</h3>
    ${attention
      .slice(0, 4)
      .map((id) => {
        const rule = rules.get(id);
        const result = results.get(id);
        return `<article class="finding-card">
        <div class="finding-heading"><h4>${esc(title(rule))}</h4>${resultBadge(result)}</div>
        <p class="finding-preview">${esc(result.explanation)}</p>
        ${result.evidence?.length ? `<p class="check-preview"><strong>Source evidence</strong> ${sourceButton(result.evidence[0], "head", id)}</p>` : ""}
        ${checkFor(result) ? `<p class="check-preview"><strong>Suggested check</strong> ${esc(checkFor(result))}</p>` : ""}
        ${button("Inspect finding", "rule", id)}
      </article>`;
      })
      .join("")}
    ${count > 4 ? button("See all rules that need attention", "filter", "attention") : ""}
  </section>`
      : button("View rule results", "view", "results")
  }
  ${
    ci
      ? `<section class="summary-strip"><div><h3>CI evidence</h3><p>${esc(ciStatusSummary())}</p></div>
    ${button("Review CI evidence", "view", "ci")}</section>`
      : ""
  }
  <details class="report-details"><summary>Investigation details</summary>
    <p>${Number(report.diagnostics?.model_calls || 0)} model calls · ${Number(report.diagnostics?.empty_searches || 0)} empty searches${comparison ? ` · ${Number(comparison.baseline_diagnostics?.model_calls || 0)} base model calls` : ""}</p>
    ${Object.entries(report.diagnostics?.unknown_reasons || {})
      .map(([reason, n]) => `<p>${esc(description(reason))}: ${Number(n)}</p>`)
      .join("")}
  </details>`;
}

function selected() {
  const term = query.trim().toLocaleLowerCase();
  return ordered.filter((id) => {
    const result = results.get(id);
    if (filter === "attention" && !attentionSet.has(id)) return false;
    if (filter === "regression" && result.comparison_status !== "regression")
      return false;
    if (
      filter === "other_failures" &&
      (result.status !== "fail" || result.comparison_status === "regression")
    )
      return false;
    if (Object.hasOwn(statuses, filter) && result.status !== filter)
      return false;
    const rule = rules.get(id);
    return [
      id,
      title(rule),
      rule.statement,
      rule.source?.path,
      ...(result.evidence || []).map((ref) => ref.path),
    ].some((value) =>
      String(value ?? "")
        .toLocaleLowerCase()
        .includes(term),
    );
  });
}

function pagination(total, action) {
  if (total <= pageSize) return "";
  const pages = Math.ceil(total / pageSize);
  return `<nav class="pages" aria-label="Result pages">
    ${page ? button("Previous", action, page - 1) : ""}
    <span>Page ${page + 1} of ${pages}</span>
    ${page + 1 < pages ? button("Next", action, page + 1) : ""}
  </nav>`;
}

function resultRows() {
  if (!report.rules.length) return `<h2>Rule results</h2>${emptyRules()}`;
  const filters = {
    all: "All results",
    attention: "Needs attention",
    ...(comparison
      ? { regression: "New regressions", other_failures: "Other failures" }
      : {}),
    ...statuses,
  };
  const ids = selected();
  const visible = ids.slice(page * pageSize, (page + 1) * pageSize);
  return `<h2>Rule results</h2>
    <form id="result-filters" class="toolbar">
      <label>Find a rule<input id="rule-query" type="search" placeholder="Title, rule ID or source file" value="${esc(query)}"></label>
      <label>Status<select id="rule-status">${Object.entries(filters)
        .map(
          ([key, label]) =>
            `<option value="${key}" ${key === filter ? "selected" : ""}>${esc(label)}</option>`,
        )
        .join("")}</select></label>
      <button type="submit">Apply</button>
    </form>
    <p class="review-meta">${ids.length} of ${report.rules.length} rules shown</p>
    ${
      visible.length
        ? `<div class="result-list">${visible
            .map((id) => {
              const rule = rules.get(id);
              const result = results.get(id);
              return `<button type="button" class="result-row" data-action="rule" data-id="${esc(id)}">
        <span class="result-identity"><strong>${esc(title(rule))}</strong>
        <small>${esc(rule.source?.path || id)}</small></span>
        <span class="result-outcome">${resultBadge(result)}${
          result.baseline
            ? `<small>Base ${statuses[result.baseline.status]} · Proposed ${statuses[result.status]}</small>`
            : ""
        }</span>
      </button>`;
            })
            .join("")}</div>${pagination(ids.length, "page")}`
        : "<p>No rules match these filters.</p>"
    }`;
}

function ruleBook() {
  if (!report.rules.length) return `<h2>Approved rules</h2>${emptyRules()}`;
  return `<h2>Approved rules</h2><div class="result-list">${report.rules
    .slice(page * pageSize, (page + 1) * pageSize)
    .map(
      (
        rule,
      ) => `<button type="button" class="result-row" data-action="rule" data-id="${esc(rule.id)}">
      <span class="result-identity"><strong>${esc(title(rule))}</strong>
      <small>${esc(rule.id)} · ${esc(rule.source?.path || rule.origin)}</small></span>
      <span aria-hidden="true">›</span></button>`,
    )
    .join("")}</div>${pagination(report.rules.length, "page")}`;
}

function scope() {
  const coverage = report.coverage;
  const selection = coverage.documentation_selection || {};
  const omitted = coverage.omitted || [];
  const selectedDocs = selection.selected_documents || [];
  const excludedDocs = [
    ...(selection.excluded_documents || []),
    ...(selection.excluded_sections || []),
  ];
  const changes = comparison?.changes || [];
  return `<h2>Scope and limits</h2>
    <p>Pass means the inspected source supports the approved rule. Runtime behavior needs its own evidence.</p>
    ${
      comparison
        ? `<section class="finding-card"><h3>Compared commits</h3>
      <dl class="scope-facts"><div><dt>Base</dt><dd><code>${esc(comparison.base.commit)}</code></dd></div>
      <div><dt>Proposed</dt><dd><code>${esc(comparison.head.commit)}</code></dd></div>
      <div><dt>Captured changes</dt><dd>${changes.length}</dd></div>
      <div><dt>Git entries outside the capture</dt><dd>${comparison.base.omitted} base · ${comparison.head.omitted} proposed</dd></div></dl>
      ${comparison.includes.length ? `<p>Included paths · ${esc(comparison.includes.join(", "))}</p>` : ""}
      ${
        changes.length
          ? `<details><summary>Changed files</summary><ul class="source-list">${changes
              .map(
                ({ path, kind }) =>
                  `<li>${button(path, "source", "", { path, side: kind === "removed" ? "base" : "head" })}<small>${esc(kind)}</small></li>`,
              )
              .join("")}</ul></details>`
          : ""
      }
    </section>`
        : ""
    }
    ${
      gaps.length
        ? `<section class="finding-card"><h3>Unresolved source sections</h3><ul class="source-list">
      ${gaps.map((ref) => `<li>${sourceButton(ref, "head")}<small>${esc(description(ref.reason))}</small></li>`).join("")}
    </ul></section>`
        : ""
    }
    <details class="report-details"><summary>Selected documents (${selectedDocs.length})</summary>
      <ul class="source-list">${selectedDocs.map((path) => `<li>${button(path, "source", "", { path })}</li>`).join("")}</ul>
    </details>
    <details class="report-details"><summary>Excluded documents and sections (${excludedDocs.length})</summary>
      <ul class="source-list">${excludedDocs
        .map(
          (
            ref,
          ) => `<li>${sourceButton(ref, "head", null, ref.start_line ? "" : ref.path)}
        <small>${esc(description(ref.reason))}</small></li>`,
        )
        .join("")}</ul>
      ${coverage.excluded_candidates?.length ? `<p>${plural(coverage.excluded_candidates.length, "candidate")} excluded by extraction policy.</p>` : ""}
    </details>
    <details class="report-details"><summary>Omitted entries (${omitted.length})</summary>
      <ul class="source-list">${omitted.map(({ path, reason }) => `<li><code>${esc(path)}</code><small>${esc(description(reason))}</small></li>`).join("")}</ul>
    </details>
    <details class="report-details"><summary>Captured source files (${Object.keys(snapshots.head).length})</summary>
      <ul class="source-list">${Object.keys(snapshots.head)
        .map((path) => `<li>${button(path, "source", "", { path })}</li>`)
        .join("")}</ul>
    </details>
    <p class="review-meta">The capture and analysis artifacts include the full inventory and any parser gaps.</p>`;
}

function ciRows(checks, showRule = true) {
  return `<ul class="ci-list">${checks
    .map(
      (check) => `<li><div class="ci-identity">
    <strong>${esc(check.test)}</strong>
    ${
      !showRule
        ? ""
        : check.mapping === "linked"
          ? button(title(rules.get(check.rule_id)), "rule", check.rule_id)
          : `<small>${esc(check.rule_id)} · ${esc(mappingLabels[check.mapping])}</small>`
    }</div>
    ${statusBadge(check.status, check.status === "passed" ? "pass" : check.status === "failed" ? "fail" : "unknown")}
  </li>`,
    )
    .join("")}</ul>`;
}

function ciView() {
  return `<h2>CI evidence</h2>
    <p>${esc(ciStatusSummary())}. These are supplied JUnit observations for the proposed commit.</p>
    ${ciRows(ci.checks)}
    <details class="report-details"><summary>CI report and commit</summary>
      <dl class="scope-facts"><div><dt>File</dt><dd>${esc(ci.file)}</dd></div>
      <div><dt>Commit</dt><dd><code>${esc(ci.commit)}</code></dd></div>
      <div><dt>File SHA-256</dt><dd><code>${esc(ci.sha256)}</code></dd></div></dl>
    </details>`;
}

const views = {
  overview,
  results: resultRows,
  rules: ruleBook,
  scope,
  ci: ciView,
};
const ui = MNWebReport.createReport({
  tabs: [
    ["overview", "Overview", "content"],
    ["results", "Rule results", "content"],
    ["rules", "Approved rules", "content"],
    ["scope", "Scope and limits", "content"],
    ...(ci ? [["ci", "CI evidence", "content"]] : []),
  ],
  primaryCount: 5,
  navigationLabel: "Verification views",
  actions: [
    {
      id: "report",
      label: "Download Markdown",
      icon: "download",
      href: "../report.md",
    },
    { id: "rules", label: "Download editable rules", href: "../rules.md" },
    { id: "details", label: "Report details", icon: "info" },
  ],
  onView(next) {
    setView(next);
  },
  onAction(_id, trigger) {
    ui.openInspector(
      "Report details",
      `<p>${plural(report.rules.length, "approved rule")}</p>
      <dl class="scope-facts"><div><dt>Snapshot</dt><dd><code>${esc(report.snapshot_id)}</code></dd></div></dl>`,
      trigger,
    );
  },
  onDismiss() {
    saveLocation();
  },
});

function saveLocation(ruleId) {
  const params = new URLSearchParams({ view });
  if (ruleId) params.set("rule", ruleId);
  const hash = "#" + params;
  if (location.hash !== hash) history.replaceState(null, "", hash);
}

function setView(next) {
  if (!viewNames.includes(next)) return;
  view = next;
  page = 0;
  render();
}

function render() {
  ui.setView(view);
  ui.setInspectorOpen(false);
  const host = document.getElementById("content");
  const notice =
    gaps.length && report.rules.length
      ? `<aside class="coverage-notice" role="status">
    <p><strong>Partial extraction</strong> · ${plural(gaps.length, "document section")} still need review.</p>
    ${button("Review scope", "view", "scope")}</aside>`
      : "";
  host.innerHTML = notice + views[view]();
  ui.enhance(host);
  saveLocation();
}

function evidenceList(result, side, ruleId) {
  return (
    result.evidence
      .map(
        (ref) => `<section class="evidence-record">
    ${sourceButton(ref, side, ruleId)}
    <pre class="evidence-quote"><code>${esc(ref.quote)}</code></pre>
    <details><summary>Source SHA-256</summary><code>${esc(ref.sha256)}</code></details>
  </section>`,
      )
      .join("") || "<p>More implementation evidence is needed.</p>"
  );
}

function inspectRule(id, trigger) {
  const rule = rules.get(id);
  const result = results.get(id);
  if (!rule || !result) return;
  const pending = result.assessment?.missing_evidence?.trim();
  const check = checkFor(result);
  const checks = ciByRule.get(id);
  const base = result.baseline;
  const origins = [
    { ...rule.source, quote: rule.quote || rule.source?.quote },
    ...(rule.additional_origins || []).map((item) => ({
      ...item.source,
      quote: item.quote,
    })),
  ];
  ui.openInspector(
    title(rule),
    `<div class="inspected-finding">
    ${resultBadge(result)}
    <section><h3>Expected behavior</h3><p class="rule-statement">${esc(rule.statement)}</p></section>
    <section><h3>${base ? "Proposed source" : "Source finding"}</h3><p>${esc(result.explanation)}</p>
      ${result.reason_code ? `<p class="review-meta">${esc(description(result.reason_code))}</p>` : ""}
      ${pending ? `<p><strong>Missing evidence</strong> ${esc(pending)}</p>` : ""}
    </section>
    ${check ? `<section class="next-check"><h3>Suggested check</h3><p>${esc(check)}</p></section>` : ""}
    ${base ? `<p class="revision-summary"><strong>Base ${statuses[base.status]}</strong> · <strong>Proposed ${statuses[result.status]}</strong></p>` : ""}
    <section><h3>Inspected evidence</h3>${evidenceList(result, "head", id)}</section>
    ${
      base
        ? `<details class="report-details"><summary>Base source and evidence</summary><p>${esc(base.explanation)}</p>
      ${base.assessment?.missing_evidence ? `<p>${esc(base.assessment.missing_evidence)}</p>` : ""}
      ${evidenceList(base, "base", id)}</details>`
        : ""
    }
    ${checks?.length ? `<section><h3>Imported CI evidence</h3>${ciRows(checks, false)}</section>` : ""}
    <details class="report-details"><summary>Rule origin and review details</summary>
      <p><code>${esc(id)}</code> · ${esc(rule.origin)} · Confidence ${Number(result.confidence).toFixed(2)}</p>
      ${origins
        .filter((ref) => ref.path)
        .map(
          (
            ref,
          ) => `<div class="evidence-record">${sourceButton(ref, "head", id)}
        ${ref.quote ? `<blockquote>${esc(ref.quote)}</blockquote>` : ""}</div>`,
        )
        .join("")}
      <p class="review-meta">Static review · Tests not executed by Code verifier</p>
    </details>
  </div>`,
    trigger,
  );
  saveLocation(id);
}

function inspectSource(
  path,
  trigger,
  { side = "head", start, end, ruleId, full = false } = {},
) {
  const files = snapshots[side];
  if (!files || !Object.hasOwn(files, path)) return;
  const source = files[path];
  const lines = source.split(/\r\n|[\n\r\v\f\x1c-\x1e\x85\u2028\u2029]/);
  if (lines.length > 1 && lines.at(-1) === "") lines.pop();
  const hasRange =
    Number.isInteger(start) &&
    Number.isInteger(end) &&
    start >= 1 &&
    end >= start &&
    end <= lines.length;
  const from = hasRange && !full ? Math.max(1, start - 4) : 1;
  const to = hasRange && !full ? Math.min(lines.length, end + 4) : lines.length;
  const identity = comparison
    ? side === "base"
      ? "Base snapshot"
      : "Proposed snapshot"
    : "Captured source";
  const excerpt =
    hasRange && !full
      ? lines
          .slice(from - 1, to)
          .map((line, index) => {
            const number = from + index;
            return `<span class="code-line${number >= start && number <= end ? " cited-line" : ""}"><span aria-hidden="true" class="line-number">${number}</span><span>${esc(line) || " "}</span></span>`;
          })
          .join("")
      : esc(source);
  ui.openInspector(
    path,
    `<p class="review-meta">${identity}${hasRange && !full ? ` · Lines ${start}–${end}` : ""}</p>
    <div class="source-actions">${ruleId ? button("Back to finding", "rule", ruleId) : ""}
    ${
      hasRange
        ? button(
            full ? "Show cited lines" : "View entire file",
            full ? "source" : "full-source",
            "",
            { path, start, end, side, ruleId },
          )
        : ""
    }</div>
    <pre class="source-lines" tabindex="0" aria-label="${hasRange && !full ? `Source lines ${from} through ${to}` : "Captured source file"}"><code>${excerpt}</code></pre>`,
    trigger,
  );
}

document.addEventListener("click", (event) => {
  const target = event.target.closest("[data-action]");
  if (!target) return;
  const { action, id, path, side, start, end, ruleId } = target.dataset;
  if (action === "rule") inspectRule(id, target);
  else if (action === "source" || action === "full-source") {
    inspectSource(path, target, {
      side,
      start: Number(start),
      end: Number(end),
      ruleId,
      full: action === "full-source",
    });
  } else if (action === "view") {
    setView(id);
    document.getElementById("content").focus();
  } else if (action === "filter") {
    filter = id;
    query = "";
    setView("results");
    document.getElementById("rule-query")?.focus();
  } else if (action === "page") {
    page = Number(id);
    render();
    document.getElementById("content").focus();
  }
});
document.addEventListener("submit", (event) => {
  if (event.target.id !== "result-filters") return;
  event.preventDefault();
  query = document.getElementById("rule-query").value;
  filter = document.getElementById("rule-status").value;
  page = 0;
  render();
  document.getElementById("rule-query")?.focus();
});

ui.ready();
render();
if (initial.has("rule")) inspectRule(initial.get("rule"));
