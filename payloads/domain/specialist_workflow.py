"""Core child rounds for admitted checks. Only the runtime dispatches work."""
from mn_comparison_evidence_skill import read_ledger
from mn_sdk.blueprint.inputs import configured_input_path
from mn_verification_checks_skill import ROLES, assignment, digest, execute, make_plan, reconcile, scope_config, specialist_report

from .wit_verification import reconcile as wit_reconcile
from . import aspects, delegation
from .assurance_basis import read_basis
from .rule_review import require_approved_rules


def candidate_sources(capture):
    prefix = capture.get("repository_prefix", "")
    return {p.removeprefix(prefix): source for p, source in capture["sources"].items()
            if not p.startswith("knowledge/rules/")}


def baseline_sources(block, capture):
    ref = capture.get("baseline_capture")
    if ref is None:
        return None
    prefix = capture.get("repository_prefix", "")
    return {p.removeprefix(prefix): text for p, text in block.store.read(ref).items()}


def initialize(block, inputs):
    previous = inputs["previous"]
    capture = block.read_evidence(previous["capture"])
    rules = block.store.read_path("rules.json")
    approval = require_approved_rules(block, rules)
    if previous["approval"] != approval or capture["snapshot_id"] != approval["snapshot_id"]:
        raise ValueError("The specialist request requires the approved source and rule revision.")
    request = block.store.read_path("inputs.json")
    sources = candidate_sources(capture)
    comparison = capture.get("comparison")
    if comparison:
        comparison = {**comparison, "changes": [
            {**change, "path": change["path"].removeprefix(capture.get("repository_prefix", ""))}
            for change in comparison["changes"]]}
    plan = make_plan(sources, request.get("verification_scope"), run_id=block.run_id,
                     comparison=comparison, baseline_sources=baseline_sources(block, capture),
                     omitted=capture.get("omitted", ()), evidence_folder=request.get("evidence_folder"))
    ledger = read_ledger(request.get("evidence_folder"), request.get("assurance_evidence_sha256"), plan, sources)
    plan["assurance_basis"] = read_basis(request.get("evidence_folder"), request.get("assurance_basis_sha256"), plan, ledger, sources)
    plan["observation_digest"] = ledger["digest"]
    plan["aspect_roles"] = [role for role in ROLES if aspects.applicable(role, aspects.scope(ledger, role), plan["paths"])]
    plan["plan_id"] = digest({k: v for k, v in plan.items() if k != "plan_id"})
    packet = {"observations": block.store.commit("specialists/observations.json", ledger).to_dict(),
              "plan": block.store.commit("verification-plan.json", plan).to_dict(),
              "capture": previous["capture"], "approval": approval}
    delegated = delegation.assign(block, plan, sources, baseline_sources(block, capture),
                                  ledger=ledger, evidence_folder=request.get("evidence_folder"))
    if delegated:
        packet["delegated"] = delegated
    return {"packet": block.store.commit("specialists/admission.json", packet).to_dict()}


def _result_path(ident, number):
    return f"specialists/attempts/{ident}-{number}.json"


def _attempts(block, plan):
    records = []
    for check in plan["checks"]:
        for number in (1, 2):
            path = _result_path(check["id"], number)
            receipt = path + ".receipt.json"
            if block.store.path(receipt).is_file():
                reference = block.store.read_path(receipt)
                records.append(block.read_checkpoint(reference, expected_path=path))
    return records


def absent_roles(block):
    payload = block.original_config.get("inputs", {}).get("payload", {})
    if not payload.get("collaboration_group_id"):
        return set()
    connected = {peer["blueprintId"] for peer in payload.get("collaboration_peers", [])}
    return {role for role in ROLES if role + "_verifier" not in connected}


def _nodes(block, packet_ref, plan, revision, delegated):
    prior = []
    for i in range(revision):
        prior.extend(block.store.read_path(f"specialists/rounds/{i}.json")["tasks"])
    assignments = [n["input"]["assignment"] for n in prior]
    sent = {(a["check_id"], a["attempt"]) for a in assignments if "check_id" in a}
    records = _attempts(block, plan)
    latest = {row["check_id"]: row for row in records}
    tasks = []
    external = {ident for item in delegated.values() for ident in item["checks"]}
    absent = absent_roles(block)
    for check in plan["checks"]:
        ident = check["id"]
        if ident in external or check["specialist"] in absent:
            continue
        # Measure a schema only after its separately planned behavior examples pass.
        preconditions = [other["id"] for other in plan["checks"] if check["kind"] == "schema_workload"
                         and other["kind"] == "schema_cases" and other["file"] == check["file"]]
        if not all(latest.get(dep, {}).get("status") == "passed" for dep in preconditions):
            continue
        number = 1
        if (ident, 1) in sent:
            if not latest.get(ident, {}).get("retryable") or (ident, 2) in sent:
                continue
            number = 2
        task = assignment(plan, ident, number)
        tasks.append({"id": f"{ident}-{number}", "template": "inspect_" + check["specialist"],
                      "label": f"{ident} · attempt {number}", "needs": [],
                      "input": {"packet": packet_ref, "assignment": task}})
    if tasks:
        return tasks
    selected = {c["specialist"] for c in plan["checks"] if c["id"] not in external} - absent
    selected |= set(plan.get("aspect_roles", ())) - set(delegated) - absent
    reported = {a["specialist"] for a in assignments if a.get("operation") == "report"}
    return [{"id": "report-" + role, "template": "inspect_" + role, "label": ROLES[role] + " report",
             "needs": [], "input": {"packet": packet_ref, "assignment": _report_assignment(plan, role)}}
            for role in ROLES if role in selected - reported]


def _report_assignment(plan, role):
    return {"operation": "report", "specialist": role, "run_id": plan["run_id"], "plan_id": plan["plan_id"]}


def plan_round(block, work):
    block.check()
    packet_ref = work["seed"]["packet"]
    packet = block.read_evidence(packet_ref)
    plan = block.store.read(packet["plan"])
    revision = work["_child"]["revision"]
    path = f"specialists/rounds/{revision}.json"
    if block.store.path(path).is_file():
        saved = block.store.read_path(path)
        if saved["plan_id"] != plan["plan_id"]:
            raise ValueError("Cannot replay a round against a different plan.")
        return saved["decision"]
    tasks = _nodes(block, packet_ref, plan, revision, packet.get("delegated", {}))
    decision = {"done": not tasks, "tasks": tasks, "rationale": "Dispatch eligible checks." if tasks else
                "All eligible checks reached a terminal state or used their retry budget.",
                "evidence_refs": [packet["plan"]]}
    block.store.commit(path, {"plan_id": plan["plan_id"], "tasks": tasks, "decision": decision})
    return decision


def _inspect(block, inputs, specialist):
    packet, task = inputs["packet"], inputs["assignment"]
    plan = block.store.read(packet["plan"])
    if plan["run_id"] != block.run_id:
        raise ValueError("Assignment belongs to another run.")
    capture = block.store.read(packet["capture"])
    if packet["approval"]["snapshot_id"] != capture["snapshot_id"]:
        raise ValueError("Assignment source differs from its approval.")
    if task == _report_assignment(plan, specialist):
        path = f"specialists/reports/{specialist}.json"
        def publish():
            ledger = block.store.read(packet["observations"]) if packet.get("observations") else aspects.EMPTY
            facet = aspects.evaluate(block, specialist, aspects.scope(ledger, specialist), plan, candidate_sources(capture))
            return {"plan_id": plan["plan_id"], "subject": plan["subject"], "aspect": facet,
                    "view": aspects.with_observations(specialist_report(_rollup(block, plan), specialist), facet)}
        ref = block.freeze_checkpoint(path, publish)
        block.store.commit(path + ".receipt.json", ref.to_dict(), kind="specialist_report_receipt")
        return {"result_ref": ref.to_dict()}
    if task != assignment(plan, task["check_id"], task["attempt"]):
        raise ValueError("Assignment does not match the admitted plan.")
    folder = configured_input_path(block.original_config, {}, "evidence_folder", runtime_file=__file__)
    path = _result_path(task["check_id"], task["attempt"])
    ref = block.freeze_checkpoint(path, lambda: execute(plan, task, candidate_sources(capture),
                                                       baseline_sources=baseline_sources(block, capture),
                                                       evidence_folder=folder, specialist=specialist))
    block.store.commit(path + ".receipt.json", ref.to_dict(), kind="attempt_receipt")
    return {"result_ref": ref.to_dict()}


def inspect_functional(block, inputs):
    return _inspect(block, inputs, "functional")


def inspect_security(block, inputs):
    return _inspect(block, inputs, "security")


def inspect_compatibility(block, inputs):
    return _inspect(block, inputs, "compatibility")


def inspect_reliability(block, inputs):
    return _inspect(block, inputs, "reliability")


def _rollup(block, plan, external=()):
    records = [*_attempts(block, plan), *external]
    report = wit_reconcile(block, plan, records)
    completed = {row["id"] for row in report["checks"] if row["status"] == "passed"}
    for row in report["checks"]:
        if row["attempts"] or row["kind"] != "schema_workload":
            continue
        check = next(c for c in plan["checks"] if c["id"] == row["id"])
        deps = [c["id"] for c in plan["checks"] if c["kind"] == "schema_cases" and c["file"] == check["file"]]
        pending = [dep for dep in deps if dep not in completed]
        if pending:
            row["reason"] = "Awaiting successful schema examples: " + ", ".join(pending)
            row["status"] = "blocked"
            if report["verdict"] != "FAIL":
                report["verdict"] = "BLOCKED"
    return report


def summarize(block, inputs):
    packet = block.read_evidence(inputs["input"]["seed"]["packet"])
    plan = block.store.read(packet["plan"])
    delegated = packet.get("delegated", {})
    records, pending, returned = delegation.await_current(block, plan, delegated)
    report = _rollup(block, plan, records)
    absent = absent_roles(block)
    for row in report["checks"]:
        if row["specialist"] in absent:
            row["reason"] = f"{ROLES[row['specialist']]} is outside this collaboration group."
    earlier = delegation.earlier_results(block, delegated)
    if earlier:
        report["earlier_delegations"] = earlier
    if delegated:
        report["delegation"] = {role: {**entry, "status": "queued" if role in pending else "received"}
                                for role, entry in delegated.items()}
        for row in report["checks"]:
            if row["specialist"] in pending and row["id"] in delegated[row["specialist"]]["checks"]:
                row["reason"] = "Awaiting the dedicated verifier’s mailbox reply."
    report["aspects"] = {role: {"status": "received", "data": data} for role, data in returned.items()}
    for role in absent:
        report["aspects"][role] = {"status": "removed"}
    for role in pending:
        report["aspects"][role] = {"status": "pending"}
    refs = {}
    for role in ROLES:
        path = f"specialists/reports/{role}.json"
        if block.store.path(path + ".receipt.json").is_file():
            ref = block.store.read_path(path + ".receipt.json")
            local = block.read_checkpoint(ref, expected_path=path)
            if role not in delegated and role not in absent:
                if "aspect" in local:
                    report["aspects"][role] = {"status": "local", "data": local["aspect"]}
                refs[role] = ref
    ref = block.store.commit("specialists/report.json", report)
    return {"report": ref.to_dict(), "views": refs, "approval": packet["approval"], "capture": packet["capture"]}


def missing_report(block, capture):
    """Keep publication honest if the independent specialist branch produced no evidence."""
    request = block.store.read_path("inputs.json")
    plan = make_plan(candidate_sources(capture), scope_config(request.get("verification_scope")),
                     run_id=block.run_id, comparison=capture.get("comparison"), omitted=capture.get("omitted", []),
                     evidence_folder=request.get("evidence_folder"))
    report = wit_reconcile(block, plan, [])
    report["blockers"].append("The specialist workflow did not return a verified completion record.")
    report["verdict"] = "INCONCLUSIVE"
    return report
