"use strict";

// Capture the self-contained document before the shared UI mounts its React roots.
const originalReportHtml = "<!doctype html>\n" + document.documentElement.outerHTML;

function downloadReportFile(filename, contents, type) {
  const url = URL.createObjectURL(new Blob([contents], {type}));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function showAssuranceCase(params) {
  if (!params.has("case")) return;
  const panel = document.getElementById(view);
  const entry = Array.from(panel?.querySelectorAll("details[data-case]") || [])
    .find(item => item.dataset.case === params.get("case"));
  if (!entry) return;
  entry.open = true;
  entry.querySelector("summary").focus({preventScroll: true});
  entry.scrollIntoView({block: "nearest"});
}
