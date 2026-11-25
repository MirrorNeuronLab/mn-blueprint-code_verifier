"""Apply the approved scope to deterministic evidence and attach the source review."""
from mn_verification_checks_skill import ROLES, digest, snapshot_id, specialist_report

from . import aspects
from .report_findings import conflicting_ci_rules
from .specialist_workflow import candidate_sources, missing_report


def consolidate(block, inputs, capture, approval, rules, results, *, ci):
    branch = inputs.get("specialists")
    if not branch:
        report = missing_report(block, capture)
    else:
        if branch["approval"] != approval or branch["capture"] != inputs["previous"]["capture"]:
            raise ValueError("Specialist results belong to another capture or approval.")
        report = block.read_evidence(branch["report"])
    plan = report["plan"]
    if (plan["run_id"] != block.run_id or plan["subject"] != snapshot_id(candidate_sources(capture))
            or plan["plan_id"] != digest({k: v for k, v in plan.items() if k != "plan_id"})):
        raise ValueError("Specialist report does not match this run's source and plan.")
    verdict = report["verdict"]
    reasons = list(report["blockers"])
    views = []
    references = branch.get("views", {}) if branch else {}
    for role in ROLES:
        ref = references.get(role)
        if ref is None:
            selected = any(c["specialist"] == role for c in plan["checks"])
            received = report.get("delegation", {}).get(role, {}).get("status") == "received"
            missing = selected and not received
            view = specialist_report(report, role, missing=missing)
            measured = report.get("aspects", {}).get(role, {}).get("data")
            views.append(aspects.with_observations(view, measured))
            if missing:
                reasons.append(f"{ROLES[role]} did not return its report.")
            continue
        received = block.read_checkpoint(ref, expected_path=f"specialists/reports/{role}.json")
        measured = report.get("aspects", {}).get(role, {}).get("data")
        expected = aspects.with_observations(specialist_report(report, role), measured)
        if (received["plan_id"] != plan["plan_id"] or received["subject"] != plan["subject"]
                or received["view"] != expected):
            raise ValueError("Specialist report differs from its verified assignment evidence.")
        views.append({**received["view"], "report_ref": ref})
    mapped = {r["id"]: [] for r in rules["rules"]}
    for check in plan["checks"]:
        for rule_id in check.get("rule_ids", []):
            if rule_id in mapped:
                mapped[rule_id].append(check["id"])
            else:
                reasons.append(f"Check {check['id']} names an unapproved rule: {rule_id}")
    # Source analysis is advisory. It cannot independently satisfy a required check.
    unresolved = [r for r in results if results[r]["status"] != "pass"]
    if unresolved:
        reasons.append(f"Source review requires a decision on {len(unresolved)} approved rule(s).")
    if any(row.get("comparison_status") in {"needs_baseline", "needs_change_evidence", "inconclusive"}
           for row in results.values()):
        reasons.append("The static rule review could not establish the change for every rule on both revisions.")
    for rule_id in sorted(conflicting_ci_rules(ci)):
        reasons.append(f"Imported CI reported a failed or mixed result for approved rule {rule_id}.")
    if not rules["rules"] or rules.get("extraction_gaps"):
        reasons.append("Rule discovery is incomplete or the approved rule inventory is empty.")
    if plan["decision"] in {"merge", "release"} and any(not checks for checks in mapped.values()):
        reasons.append("Every approved rule requires an independently planned check for this decision.")
    if reasons and verdict == "PASS":
        verdict = "INCONCLUSIVE"
    return {"verdict": verdict, "reasons": reasons, "rule_checks": mapped, "specialist_report": report,
            "specialists": views}
