"""Domain content for the shared offline report shell."""

from html import escape
from urllib.parse import urlencode

from .aspects import TITLES


def e(value):
    return escape(str(value), quote=True)


def paragraph(value):
    return f'<p class="report-paragraph">{e(value)}</p>'


def group(title, body):
    return f'<section class="assurance-group"><h3>{e(title)}</h3>{body}</section>'


def table(label, columns, rows, empty):
    rows = list(rows)
    if not rows:
        return paragraph(empty)
    heads = "".join(f'<th scope="col">{e(col)}</th>' for col in columns)
    body = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    return (
        f'<div class="report-table vbg-table-wrap" data-density="compact" role="region" '
        f'aria-label="{e(label)}" tabindex="0"><table><thead><tr>{heads}</tr></thead>'
        f"<tbody>{body}</tbody></table></div>"
    )


def case_link(ref, label=None):
    href = urlencode({"section": ref["role"], "case": ref["case_id"]})
    return f'<a class="vbg-link" href="#{e(href)}">{e(label or ref["case_id"])}</a>'


def source(ref, sources, prefix=""):
    path, line = ref["path"], ref.get("line", ref.get("start_line"))
    label = e(f"{path}:{line}")
    key = prefix + path
    if key not in sources:
        return label
    return (
        f'<button type="button" class="source-ref" data-action="source" data-side="head" '
        f'data-path="{e(key)}" data-start="{int(line)}" data-end="{int(ref.get("end_line", line))}">{label}</button>'
    )


def observed(case, revision="candidate"):
    return (
        ", ".join(dict.fromkeys(r["observed"] for r in case["runs"] if r["revision"] == revision))
        or "Unmeasured"
    )


def case_records(section, sources, prefix):
    items = []
    order = {"unmet": 0, "mixed": 1, "unmeasured": 2, "met": 3}
    for row in sorted(section["cases"], key=lambda c: order[c["status"]]):
        locations = [row["source"], *section["locations"].get(row["id"], [])]
        citations = " · ".join(source(ref, sources, prefix) for ref in locations)
        evidence = table(
            "Run observations",
            ["Run", "Revision", "Fixture reset", "Observation"],
            (
                (
                    e(r["id"]),
                    e(r["revision"].capitalize()),
                    "Clean" if r["clean"] else "Unverified",
                    e(r["observed"]) + (f" · Original {e(r['original'])}" if "original" in r else ""),
                )
                for r in row["runs"]
            ),
            "No run was recorded.",
        )
        staged_runs = [(r["id"], s) for r in row["runs"] for s in r.get("stages", [])]
        if staged_runs:
            evidence += (
                "<details><summary>Stage observations for every run</summary>"
                + table(
                    "All observed stages",
                    ["Run", "Stage", "Expected", "Observed"],
                    ((e(rid), e(s["name"]), e(s["expected"]), e(s["observed"])) for rid, s in staged_runs),
                    "",
                )
                + "</details>"
            )
        acceptance = (
            f"<p><strong>Acceptance check</strong> {e(row['remedy'])}</p>"
            if row.get("remedy") and row["status"] != "met"
            else ""
        )
        items.append(
            f'<details class="report-details assurance-case" data-case="{e(row["id"])}"><summary>'
            f"<strong>{e(row['claim'])}</strong> · {e(row['status'].capitalize())}</summary>"
            f"<p>Expected <strong>{e(row['expected'])}</strong>. Candidate <strong>{e(observed(row))}</strong>.</p>"
            f'{acceptance}<p>{citations}</p>{evidence}<small class="vbg-meta">'
            f"Fixture SHA-256 <code>{e(row['fixture'])}</code></small></details>"
        )
    if not items:
        return ""
    printed = table(
        "Case observations",
        ["Case", "Expected", "Candidate", "Source"],
        (
            (
                e(row["id"]),
                e(row["expected"]),
                e(observed(row)),
                e(f"{row['source']['path']}:{row['source']['line']}"),
            )
            for row in section["cases"]
        ),
        "",
    )
    return group("Case evidence", "".join(items) + '<div class="assurance-print">' + printed + "</div>")


def metrics(section):
    return (
        '<div class="assurance-metrics">'
        + "".join(
            f'<dl class="report-metric vbg-metric"><dt class="vbg-metric-label">{e(m["label"])}</dt>'
            f'<dd class="vbg-metric-value">{e(m["value"])}</dd><dd class="vbg-metric-detail">{e(m["note"])}</dd></dl>'
            for m in section["metrics"]
        )
        + "</div>"
    )


def receipt_details(record):
    counts = record.get("counts") or {}
    count = f" · {e(counts['passed'])} passed of {sum(counts.values())}" if counts else ""
    cases = "".join(
        f"<li>{e(name)} · {e(', '.join(states))}</li>" for name, states in record["cases"].items()
    )
    return (
        f'<details class="assurance-receipt"><summary>{e(record.get("tool") or record["id"])}{count}</summary>'
        f"<ul>{cases}</ul>"
        f'<small class="vbg-meta">Receipt SHA-256 <code>{e(record["receipt"])}</code></small></details>'
    )


def comparison_table(gates):
    return group(
        "What the existing checks established",
        table(
            "Comparison evidence",
            ["Check", "Result", "Evidence on this candidate"],
            (
                (
                    e(g["label"]),
                    e(g["status"].capitalize()),
                    e(g["detail"]) + (receipt_details(g["record"]) if g.get("record") else ""),
                )
                for g in gates
            ),
            "No comparison records were supplied.",
        ),
    )


def functional(section, sources):
    rows = []
    for r in section["requirements"]:
        labels = {"functional": "Workflow", "compatibility": "Integration trace", "security": "Policy case"}
        links = " · ".join(case_link(ref, labels[ref["role"]]) for ref in r["cases"]) or "No linked case"
        passage = f"<br>{source(r['source'], sources)}" if r.get("source") else ""
        rows.append((e(r["claim"]) + passage, e(r["outcome"].capitalize()), links))
    body = table(
        "Requirements and evidence",
        ["Approved requirement", "Linked case outcome", "Evidence"],
        rows,
        "No approved requirements were available for this capture.",
    )
    if section["unmapped"]:
        body += table(
            "Cases without an approved match",
            ["Case", "Reason"],
            ((case_link(ref), e(ref["reason"])) for ref in section["unmapped"]),
            "",
        )
    if section["requirements"] and all(r["source_review"] == "unknown" for r in section["requirements"]):
        body += paragraph("Independent source assessment is unresolved for every listed requirement.")
    return group("Approved requirements", body)


def defects(section, sections):
    items = []
    for row in section["defects"]:
        links = " · ".join(case_link(p, TITLES[p["role"]]) for p in row["proofs"])
        acceptance = (
            f"<p><strong>Acceptance check</strong> {e(row['acceptance'])}</p>"
            if row.get("acceptance")
            else ""
        )
        items.append(
            f'<article class="assurance-finding"><h4>{e(row["id"])} · {e(row["severity"].capitalize())}</h4>'
            f"<p>{e(row['title'])}</p><p>Expected <strong>{e(row['expected'])}</strong>. "
            f"Observed <strong>{e(row['observed'])}</strong> across {row['distinct_runs']} distinct clean candidate runs.</p>"
            f"{acceptance}<p>{links}</p></article>"
        )
    body = group(
        "Reproduced behavior", "".join(items) or paragraph("No behavior met the repeat-evidence threshold.")
    )
    rows = {(s["id"], r["id"]): r for s in sections for r in s.get("cases", [])}
    other = []
    for category, proofs in [
        ("Policy mismatch", section["policy_mismatches"]),
        ("Further review", section["leads"]),
    ]:
        for ref in proofs:
            case = rows[ref["role"], ref["case_id"]]
            other.append((e(category), case_link(ref, ref.get("id") or case["claim"]), e(observed(case))))
    return body + (
        group("Other evidence", table("Other evidence", ["Classification", "Case", "Candidate"], other, ""))
        if other
        else ""
    )


def integration(section):
    rows = []
    for case in section["cases"]:
        candidate = next(
            (r for r in case["runs"] if r["revision"] == "candidate" and r["first_divergence"]),
            next((r for r in case["runs"] if r["revision"] == "candidate"), {}),
        )
        stages = candidate.get("stages", [])
        baseline = next((r for r in case["runs"] if r["revision"] == "baseline" and r["clean"]), {})
        historical = (
            {s["name"]: s["observed"] for s in baseline.get("stages", [])} if case["comparable"] else {}
        )
        rows.append(f"<h4>{case_link({'role': 'compatibility', 'case_id': case['id']}, case['claim'])}</h4>")
        if candidate.get("first_divergence"):
            rows.append(f"<p>First divergent stage · <strong>{e(candidate['first_divergence'])}</strong></p>")
        rows.append(
            table(
                "Stage observations",
                ["Observed stage", "Expected", "Baseline", "Candidate"],
                (
                    (
                        e(s["name"]),
                        e(s["expected"]),
                        e(historical.get(s["name"], "Unmeasured")),
                        e(s["observed"]),
                    )
                    for s in stages
                ),
                "No stage observations were supplied.",
            )
        )
    if not rows:
        rows.append(
            table(
                "Compared checks",
                ["Check", "Baseline", "Candidate", "Change"],
                (
                    (e(c["check_id"]), e(c["base"]), e(c["candidate"]), e(c["classification"]))
                    for c in section["changes"]
                ),
                "No paired journeys were supplied.",
            )
        )
    if section["method"] == "Instrumented in-process stages":
        rows.append(
            paragraph("These stages ran in one process. Deployed service boundaries remain unmeasured.")
        )
    return group(section["method"], "".join(rows))


def security(section):
    evidence = table(
        "Access-control matrix",
        ["Actor", "Action / resource", "Expected", "Baseline", "Candidate"],
        (
            (
                e(c["context"]["actor"]),
                case_link(
                    {"role": "security", "case_id": c["id"]},
                    f"{c['context']['action']} / {c['context']['resource']}",
                ),
                e(c["expected"]),
                e(observed(c, "baseline")),
                e(observed(c)),
            )
            for c in section["cases"]
        ),
        "No scoped access decisions were supplied.",
    )
    if section["method"] == "Declarative policy table":
        evidence += paragraph(
            "This comparison reads configured permissions. Runtime enforcement remains unmeasured."
        )
    return group(section["method"], evidence)


def quality(section, sources, prefix):
    inventory = section["inventory"] or {}
    coverage = section["coverage"] or {}
    rows = [
        (
            e(t["name"]),
            e(", ".join(t["signals"]) or "No signal identified"),
            source(t["source"], sources, prefix),
        )
        for t in inventory.get("tests", [])
    ]
    body = group(
        "Test assertions",
        table(
            "Test assertions",
            ["Test", "Static observation", "Source"],
            rows,
            "No test functions were inspected.",
        ),
    )
    if inventory.get("omitted"):
        body += paragraph("Inventory omitted " + ", ".join(inventory["omitted"]))
    if coverage:
        body += paragraph(
            f"Coverage was measured for {', '.join(coverage['paths'])} "
            f"({coverage['covered_lines']} of {coverage['total_lines']} lines)."
        )
    evidence = []
    for c in section["cases"]:
        candidate = case_link({"role": "reliability", "case_id": c["id"]}, observed(c).capitalize())
        repair = e(c.get("remedy") or "No repair recorded.") if c["status"] != "met" else "—"
        if record := section["repairs"].get(c["id"]):
            repair += (
                f"<p><strong>Repair check · {e(record['status'].capitalize())}</strong></p>"
                + receipt_details(record)
            )
        evidence.append((e(c["context"]["change"]), candidate, repair))
    return body + group(
        "Independent test controls",
        table(
            "Independent controls",
            ["Controlled change", "Existing tests", "Repair and evidence"],
            evidence,
            "No independent control outcomes were supplied.",
        ),
    )


def render_content(report, sources, prefix):
    assurance = report["assurance"]
    sections = assurance["sections"]
    finding_view = next(s for s in sections if s["id"] == "defects")
    parts = []
    for section in sections:
        role = section["id"]
        introduction = ""
        if role == "functional":
            decision = "Fixture decision" if assurance["origin"] == "fixture" else "Review decision"
            qualification = (
                assurance.get("collection") or "Scope follows the captured sources and supplied observations."
            )
            behaviors, policies = len(finding_view["defects"]), len(finding_view["policy_mismatches"])
            summary = (
                f"{behaviors} reproduced behavioral {'defect' if behaviors == 1 else 'defects'} · "
                f"{policies} policy {'mismatch' if policies == 1 else 'mismatches'}"
            )
            introduction = (
                f'<aside class="report-warning vbg-callout" role="note" '
                f'data-tone="{"warning" if report["verdict"] != "PASS" else "info"}">'
                f"<strong>{e(assurance['decision_label'])}</strong> · {decision}. "
                f'<a class="vbg-link" href="#section=defects">{e(summary)}</a><br>{e(qualification)}</aside>'
            )
            if finding_view["defects"]:
                first = finding_view["defects"][0]
                introduction += (
                    f'<p class="report-paragraph"><strong>{e(first["id"])}</strong> · Requirement under test — {e(first["title"])}. '
                    f"Expected {e(first['expected'])}. Observed <strong>{e(first['observed'])}</strong> "
                    f"across {first['distinct_runs']} distinct clean candidate runs.</p>"
                )
                passed = [g["label"] for g in assurance["comparisons"] if g["status"] == "passed"]
                if passed:
                    introduction += paragraph(
                        "Passing checks on the same candidate included " + ", ".join(passed) + "."
                    )
            body = comparison_table(assurance["comparisons"]) + functional(section, sources)
        elif role == "defects":
            body = defects(section, sections)
        elif role == "compatibility":
            body = integration(section)
        elif role == "security":
            body = security(section)
        else:
            body = quality(section, sources, prefix)
        if section.get("delivery") in {"removed", "pending"}:
            introduction += paragraph(
                "Specialist removed from this collaboration."
                if section["delivery"] == "removed"
                else "Awaiting the specialist’s reply."
            )
        if role != "defects":
            body += case_records(section, sources, prefix)
            if section["checks"]:
                body += (
                    f'<details class="report-details"><summary>Specialist checks ({len(section["checks"])})</summary>'
                    + table(
                        "Specialist checks",
                        ["Check", "Result", "Evidence"],
                        ((e(c["requirement"]), e(c["status"]), e(c["reason"])) for c in section["checks"]),
                        "",
                    )
                    + "</details>"
                )
        parts.append(
            f'<section class="vbg-surface assurance-section" data-variant="contained" '
            f'id="assurance-{role}" role="tabpanel" aria-labelledby="heading-{role}" tabindex="0" '
            f'{"data-report-inactive" if role != "functional" else ""}><h2 id="heading-{role}">{e(section["title"])}</h2>'
            f"{introduction}{metrics(section)}{body}</section>"
        )
    return '<main id="report-content">' + "".join(parts) + "</main>"
