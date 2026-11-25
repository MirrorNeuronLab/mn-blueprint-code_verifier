"""Bind optional collection context and reference gates to the already admitted evidence."""

from collections import Counter

from mn_verification_checks_skill.contracts import bounded_text, fields, strict_json
from mn_verification_checks_skill.receipts import verified_file

GATES = {"unit_tests": "Existing unit tests", "lint": "Lint", "ci": "CI pipeline", "ai_review": "AI review"}
BOUNDARIES = {
    "in_process": "Instrumented in-process stages",
    "services": "Supplied service-stage observations",
}
POLICIES = {"configuration": "Declarative policy table", "decisions": "Supplied authorization decisions"}


def read_basis(folder, pin, plan, ledger, sources):
    if not pin:
        return {}
    value = strict_json(verified_file(folder, pin, ".json", 256_000))
    required = {"schema", "subject", "case_digest", "origin"}
    fields(
        value,
        required
        | {"baseline_subject", "boundary", "policy", "collection", "gates", "locations", "repair_checks"},
        required,
    )
    if (
        value["schema"] != "otterdesk.assurance-basis.v1"
        or value["subject"] != plan["subject"]
        or value.get("baseline_subject") != plan.get("baseline_subject")
        or not ledger["digest"]
        or value["case_digest"] != ledger["digest"]
    ):
        raise ValueError("Report context belongs to a different capture or case ledger.")
    if (
        value["origin"] not in ("fixture", "supplied")
        or ("boundary" in value and value["boundary"] not in tuple(BOUNDARIES))
        or ("policy" in value and value["policy"] not in tuple(POLICIES))
    ):
        raise ValueError("Unknown evidence collection method.")
    if "collection" in value:
        bounded_text(value["collection"], "Collection description", 500)
    case_ids = {case["id"] for case in ledger["cases"]}
    records = {c["id"] for c in plan["checks"] if c["kind"] == "execution_record"}
    gates = value.get("gates", {})
    fields(gates, set(GATES))
    repairs = value.get("repair_checks", {})
    controls = {case["id"] for case in ledger["cases"] if case["category"] == "test_control"}
    fields(repairs, controls)
    if any(
        not isinstance(ref, str) or ref not in records for ref in [*gates.values(), *repairs.values()]
    ) or len(set(gates.values())) != len(gates):
        raise ValueError("Each comparison or repair must cite an admitted execution record.")
    locations = value.get("locations", {})
    fields(locations, case_ids)
    paths = set(plan["paths"])
    for refs in locations.values():
        if not isinstance(refs, list) or not 1 <= len(refs) <= 6:
            raise ValueError("Choose up to six implementation locations for a case.")
        for ref in refs:
            fields(ref, {"path", "line"}, {"path", "line"})
            path, line = ref["path"], ref["line"]
            if (
                not isinstance(path, str)
                or path not in paths
                or type(line) is not int
                or not 1 <= line <= len(sources[path].splitlines())
            ):
                raise ValueError("Case implementation location is outside the captured source.")
    return {**value, "sha256": pin}


def gate_receipt(ledger, ident):
    check = next((c for c in ledger["checks"] if c["id"] == ident), None)
    if not check or not check["attempts"]:
        return None
    attempt = check["attempts"][-1]
    planned = next(c for c in ledger["plan"]["checks"] if c["id"] == ident)
    receipt = planned.get("receipt_sha256")
    if (
        not attempt.get("runner_sha256")
        or not attempt.get("cases")
        or not receipt
        or not any(e.get("sha256") == receipt for e in attempt["evidence"])
    ):
        return None
    return {
        "id": ident,
        "status": check["status"],
        "label": check["requirement"],
        "receipt": receipt,
        "target": attempt.get("target"),
        "tool": attempt.get("test_id"),
        "cases": attempt["cases"],
        "runner": attempt["runner_sha256"],
        "counts": attempt.get("observations", {}).get("test_counts"),
        "fixture": attempt.get("fixture_sha256"),
    }


def comparisons(report):
    ledger = report["specialist_report"]
    intent = ledger["plan"].get("assurance_basis", {}).get("gates", {})
    gates = []
    for kind, label in GATES.items():
        entry = {
            "kind": kind,
            "label": label,
            "status": "unmeasured",
            "detail": "No matching evidence supplied.",
        }
        ref = gate_receipt(ledger, intent[kind]) if kind in intent else None
        if ref:
            entry.update(status=ref["status"], detail=ref["label"], record=ref)
        elif kind == "ci" and report.get("ci_evidence"):
            ci = report["ci_evidence"]
            linked = [c for c in ci["checks"] if c.get("mapping") == "linked"]
            if linked:
                summary = ", ".join(
                    f"{count} {state}"
                    for state, count in sorted(Counter(c["status"] for c in linked).items())
                )
                entry.update(
                    status="partial",
                    detail=f"Mapped JUnit results include {summary}. "
                    "The overall pipeline outcome is unmeasured.",
                )
        gates.append(entry)
    return gates
