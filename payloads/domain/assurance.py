"""Five decision views over the same admitted specialist receipts."""

from collections import Counter
from .aspects import CATEGORIES, TITLES
from .assurance_basis import BOUNDARIES, POLICIES, comparisons, gate_receipt
from .assurance_findings import approved_requirements, confirmed

DESCRIPTIONS = {
    "functional": "Compare promised user outcomes with the behavior recorded for each workflow.",
    "defects": "Inspect distinct defects with consistent evidence from at least two clean candidate runs of the same case and fixture.",
    "compatibility": "Follow each service handoff and compare the first divergent stage with the recorded baseline.",
    "security": "Compare observed access decisions with the approved expectation for each actor, action and resource.",
    "reliability": "Inspect test oracles, measured line coverage and whether independent controls detected changed behavior.",
}
HEADINGS = {
    "functional": "Does the software do what was promised?",
    "defects": "Which defects held up on repeat?",
    "compatibility": "Where did the journey change?",
    "security": "Who was allowed to do what?",
    "reliability": "Would these tests catch a defect?",
}
LABELS = {"met": "Met", "unmet": "Unmet", "mixed": "Mixed", "unmeasured": "Unmeasured"}


def _metric(label, value, note):
    return {"label": label, "value": str(value) if value is not None else "—", "note": note}


def _percent(numerator, denominator):
    return f"{100 * numerator / denominator:.1f}".rstrip("0").rstrip(".") + "%" if denominator else None


def _ci_state(ci):
    statuses = {row["status"] for row in (ci or {}).get("checks", []) if row.get("mapping") == "linked"}
    if not statuses:
        return None
    if statuses & {"failed", "mixed", "fail"}:
        return "Failed"
    if statuses <= {"passed", "pass"}:
        return "Passed"
    return "Partial"


def _specialist(role, report):
    ledger, ci = report["specialist_report"], report.get("ci_evidence")
    entry = ledger.get("aspects", {}).get(role, {})
    data = entry.get("data", {})
    rows = data.get("cases", [])
    checks = [r for r in ledger["checks"] if r["specialist"] == role]
    counts = Counter(row["status"] for row in rows)
    runs = sum(row["candidate_runs"] for row in rows)
    qualified = counts["met"] + counts["unmet"]
    note = "Cases in the pinned observation ledger"
    if role == "functional":
        metrics = [
            _metric(
                "Workflow cases met",
                f"{counts['met']} / {len(rows)}" if rows else None,
                "Recorded workflow cases",
            ),
            _metric("Broken promises", counts["unmet"] if rows else None, "Consistent candidate mismatches"),
            _metric("Journey runs", runs if rows else None, "Candidate run observations"),
            _metric("Existing CI", _ci_state(ci), "Linked imported test results"),
        ]
    elif role == "compatibility":
        stages = {s["name"] for row in rows for r in row["runs"] for s in r.get("stages", [])}
        metrics = [
            _metric("Recorded journeys", len(rows) or None, note),
            _metric("Journeys passed", counts["met"] if rows else None, "Candidate outcomes"),
            _metric(
                "New regressions",
                sum(r["regression"] for r in rows) if any(r["comparable"] for r in rows) else None,
                "Passing baseline, failing candidate",
            ),
            _metric("Recorded stages", len(stages) or None, "Named points in the trace"),
        ]
    elif role == "security":
        metrics = [
            _metric("Policy cases", qualified or None, "Conclusive actor and action cases"),
            _metric("Policy mismatches", counts["unmet"] if qualified else None, "Recorded decision differs"),
            _metric("Policy matched", counts["met"] if qualified else None, "Recorded decision as expected"),
            _metric(
                "Unresolved cases", len(rows) - qualified if rows else None, "Mixed or unmeasured decisions"
            ),
        ]
    else:
        inventory = data.get("inventory", {})
        tests = inventory.get("tests", [])
        coverage = data.get("coverage")
        metrics = [
            _metric(
                "Tests inspected",
                len(tests) if "tests" in inventory else None,
                "Captured Python test functions",
            ),
            _metric(
                "Tests to review",
                sum(bool(t["signals"]) for t in tests) if "tests" in inventory else None,
                "Static oracle signals",
            ),
            _metric(
                "Line coverage",
                _percent(coverage["covered_lines"], coverage["total_lines"]) if coverage else None,
                f"{coverage['covered_lines']} of {coverage['total_lines']} lines · {coverage['tool']}"
                if coverage
                else "No pinned line measurement",
            ),
            _metric(
                "Mutation resistance",
                _percent(counts["met"], qualified),
                f"{counts['met']} killed / {qualified} qualified controls"
                if qualified
                else "Requires original passing tests and control outcomes",
            ),
        ]
    source_rules = []
    unavailable = entry.get("status") in {"removed", "pending"}
    if role == "functional" and not unavailable:
        result_by_id = {r["rule_id"]: r for r in report.get("results", ())}
        for rule in report.get("rules", ()):
            if rule["id"] in result_by_id:
                result = result_by_id[rule["id"]]
                source_rules.append(
                    {
                        "id": rule["id"],
                        "claim": rule["statement"],
                        "status": result["status"],
                        "source": rule.get("source"),
                        "reason": result.get("explanation", ""),
                    }
                )
        if not rows and source_rules:
            states = Counter(r["status"] for r in source_rules)
            metrics = [
                _metric("Approved rules", len(source_rules), "Source review scope"),
                _metric("Supported in source", states["pass"], "Static assessment"),
                _metric(
                    "Rules needing review", len(source_rules) - states["pass"], "Contradicted or unresolved"
                ),
                _metric("Existing CI", _ci_state(ci), "Linked imported test results"),
            ]
    changes = [r for r in ledger.get("change_results", ()) if r["specialist"] == role]
    if not rows and checks and not unavailable and role in {"compatibility", "security"}:
        completed = [r for r in checks if r["attempts"]]
        metrics = [
            _metric("Scoped checks", len(checks), "Admitted to this specialist"),
            _metric(
                "Checks passed",
                sum(r["status"] == "passed" for r in completed),
                "Bounded checks on the capture",
            ),
            _metric("Checks failed", sum(r["status"] == "failed" for r in completed), "See check evidence"),
            _metric("Compared checks", len(changes), "Paired baseline and candidate")
            if role == "compatibility"
            else _metric("Policy decisions", None, "No recorded decision matrix"),
        ]
    if role == "reliability" and not data.get("coverage") and not unavailable:
        measured = [
            (r["id"], r["attempts"][-1]["observations"]["coverage_percent"])
            for r in ledger["checks"]
            if r["attempts"] and "coverage_percent" in r["attempts"][-1].get("observations", {})
        ]
        if len(measured) == 1:
            key, percent = measured[0]
            metrics[2] = _metric("Line coverage", f"{percent:g}%", f"Pinned runner measurement · {key}")
        elif measured:
            metrics[2] = _metric(
                "Coverage reports", len(measured), "Separate runner scopes in check evidence"
            )
    return {
        "id": role,
        "title": TITLES[role],
        "heading": HEADINGS[role],
        "description": DESCRIPTIONS[role],
        "owner": role.capitalize() + " verifier",
        "delivery": entry.get("status", "unmeasured"),
        "metrics": metrics,
        "cases": rows,
        "counts": dict(counts),
        "digest": data.get("digest"),
        "source_rules": source_rules,
        "changes": changes,
        "checks": [{k: r[k] for k in ("id", "requirement", "reason", "status")} for r in checks],
        "traces": [t for t in ledger.get("requirement_traces", []) if t["specialist"] == role],
        "inventory": data.get("inventory"),
        "coverage": data.get("coverage"),
    }


def assemble(report, *, prefix=""):
    ledger = report["specialist_report"]
    sections = {role: _specialist(role, report) for role in CATEGORIES}
    plan = ledger["plan"]
    basis = plan.get("assurance_basis", {})
    gates = comparisons(report)
    requirements, unmapped = approved_requirements(report, sections, prefix)
    defects, policy, leads, reproduced, repeats = confirmed(sections)
    for role, section in sections.items():
        section["locations"] = {
            r["id"]: basis.get("locations", {}).get(r["id"], []) for r in section["cases"]
        }
    sections["functional"]["requirements"] = requirements
    sections["functional"]["unmapped"] = unmapped
    if sections["functional"]["cases"]:
        linked = sum(bool(rule["cases"]) for rule in requirements)
        sections["functional"]["metrics"][-1] = _metric(
            "Approved requirements linked",
            f"{linked} / {len(requirements)}" if requirements else None,
            "Each links to a unique approved passage",
        )
    sections["compatibility"]["method"] = BOUNDARIES.get(
        basis.get("boundary"), "Collection method unspecified"
    )
    sections["security"]["method"] = POLICIES.get(basis.get("policy"), "Recorded policy comparison")
    sections["reliability"]["repairs"] = {
        case: ref
        for case, ident in basis.get("repair_checks", {}).items()
        if any(r["id"] == case for r in sections["reliability"]["cases"])
        and (ref := gate_receipt(ledger, ident))
    }
    defects_view = {
        "id": "defects",
        "title": TITLES["defects"],
        "owner": "Software verifier suite",
        "heading": "Which behavior failed on repeat?",
        "description": "Distinct behavioral failures with consistent observations across clean candidate runs.",
        "defects": defects,
        "policy_mismatches": policy,
        "leads": leads,
        "metrics": [
            _metric("Reproduced defects", len(defects), "Distinct behavior findings"),
            _metric(
                "Repeat confirmations",
                f"{reproduced} / {repeats}" if repeats else None,
                "Unique clean repeats of initial failures",
            ),
            _metric("Policy mismatches", len(policy), "Recorded access-control differences"),
            _metric(
                "Cases for review", len(leads), "Includes incomplete evidence and surviving test controls"
            ),
        ],
    }
    sections["defects"] = defects_view
    return {
        "schema": "otterdesk.software-assurance.v1",
        "origin": basis.get("origin", "supplied" if plan.get("observation_digest") else "source"),
        "collection": basis.get("collection"),
        "basis_digest": basis.get("sha256"),
        "comparisons": gates,
        "run": ledger["plan"]["run_id"],
        "repository": ledger["plan"].get("repository"),
        "revision": ledger["plan"].get("revision") or ledger["plan"]["subject"],
        "baseline": ledger["plan"].get("base_commit") or ledger["plan"].get("baseline_subject"),
        "decision": ledger["plan"]["decision"],
        "digest": ledger["plan"].get("observation_digest"),
        "sections": [sections[role] for role in TITLES],
    }


def apply_decision(report, assurance):
    sections = [s for s in assurance["sections"] if s["id"] != "defects"]
    unmet = sum(s["counts"].get("unmet", 0) for s in sections)
    incomplete = any(
        s["delivery"] in {"removed", "pending"}
        or any(s["counts"].get(state, 0) for state in ("mixed", "unmeasured"))
        for s in sections
    )
    if unmet:
        report["verdict"] = "FAIL"
        findings = next(s for s in assurance["sections"] if s["id"] == "defects")
        report["reasons"].append(
            f"Reproduced behavioral defects: {len(findings['defects'])}. "
            f"Recorded policy mismatches: {len(findings['policy_mismatches'])}."
        )
    elif incomplete and report["verdict"] == "PASS":
        report["verdict"] = "INCONCLUSIVE"
        report["reasons"].append("The selected collaboration has outstanding or unresolved evidence.")
    return {"FAIL": "Hold release", "PASS": "Scoped checks passed"}.get(report["verdict"], "Review required")


def markdown(assurance, escape):
    lines = ["", "## Software assurance", "", f"**{assurance['decision_label']}**"]
    if assurance.get("collection"):
        lines += ["", escape(assurance["collection"])]
    lines += [
        "",
        "### Comparison with existing checks",
        "",
        "| Check | Result | Scope |",
        "| --- | --- | --- |",
    ]
    for gate in assurance["comparisons"]:
        record = gate.get("record") or {}
        counts = record.get("counts") or {}
        detail = gate["detail"]
        if counts:
            detail += f" ({counts['passed']} of {sum(counts.values())} passed)"
        if record.get("receipt"):
            detail += " · " + record["receipt"]
        lines.append(f"| {escape(gate['label'])} | {escape(gate['status'])} | {escape(detail)} |")
    for section in assurance["sections"]:
        lines += [
            "",
            "### " + section["title"],
            "",
            " · ".join(f"{m['label']} **{escape(m['value'])}**" for m in section["metrics"]),
            "",
        ]
        if section["id"] == "defects":
            for defect in section["defects"]:
                refs = ", ".join(f"{TITLES[p['role']]} / {p['case_id']}" for p in defect["proofs"])
                lines.append(
                    f"- **{escape(defect['id'])}** · {escape(defect['severity'])}. "
                    f"Expected {escape(defect['expected'])}. Observed {escape(defect['observed'])} "
                    f"across {defect['distinct_runs']} distinct clean candidate runs. {escape(refs)}."
                )
                if defect.get("acceptance"):
                    lines.append(f"  - Acceptance check · {escape(defect['acceptance'])}")
            for ref in section["policy_mismatches"]:
                lines.append(f"- **{escape(ref['id'])}** · Policy mismatch in {escape(ref['case_id'])}.")
            for ref in section["leads"]:
                lines.append(f"- Further review · {escape(ref['case_id'])} ({TITLES[ref['role']]}).")
            continue
        if section["delivery"] in {"pending", "removed"}:
            lines.append(
                "Awaiting the specialist’s reply."
                if section["delivery"] == "pending"
                else "Specialist removed from this collaboration."
            )
        if section.get("method"):
            lines.append(section["method"] + ".")
            if section["method"] == "Declarative policy table":
                lines.append("Runtime enforcement remains unmeasured.")
        for rule in section.get("requirements", []):
            refs = ", ".join(c["case_id"] for c in rule["cases"]) or "no linked case"
            lines.append(f"- {escape(rule['claim'])} · {LABELS[rule['outcome']]} ({escape(refs)}).")
        for case in section["cases"]:
            candidate = [r for r in case["runs"] if r["revision"] == "candidate"]
            observed = ", ".join(dict.fromkeys(r["observed"] for r in candidate))
            lines.append(
                f"- **{escape(case['id'])}** · {LABELS[case['status']]} · {escape(case['claim'])}. "
                f"Expected {escape(case['expected'])}. Observed {escape(observed or 'unmeasured')}."
            )
            if stage := next((r["first_divergence"] for r in candidate if r["first_divergence"]), None):
                lines.append(f"  - First divergent stage · {escape(stage)}.")
            if case.get("remedy") and case["status"] != "met":
                lines.append(f"  - Acceptance check · {escape(case['remedy'])}")
        for record in section.get("repairs", {}).values():
            lines.append(
                f"- Repair check · **{escape(record['status'])}**. {escape(record['label'])}. "
                f"Receipt SHA-256 `{record['receipt']}`."
            )
        for test in (section["inventory"] or {}).get("tests", []):
            if test["signals"]:
                lines.append(f"- {escape(test['name'])} · {escape(', '.join(test['signals']))}.")
        if coverage := section["coverage"]:
            lines.append(
                f"- Measured line coverage · {coverage['covered_lines']} of {coverage['total_lines']} "
                f"in {escape(', '.join(coverage['paths']))}."
            )
    return lines
