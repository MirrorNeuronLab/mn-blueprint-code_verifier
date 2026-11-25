"""Select independent approved checks for hired specialists and reconcile their receipts."""

import time

from mn_comparison_evidence_skill import pack_files
from mn_sdk.blueprint.services import RunMailbox

from .wit_verification import reconcile as wit_reconcile
from . import aspects
from mn_verification_checks_skill import ROLES, digest, reconcile


def assign(block, plan, sources, baseline, *, ledger=None, evidence_folder=None):
    config = block.original_config.get("inputs", {}).get("payload", {})
    peers = config.get("collaboration_peers", [])
    if not config.get("collaboration_group_id") or not peers:
        return {}
    # The manager retains checks whose admission depends on a sibling's outcome.
    waiting_files = {
        c["file"] for c in plan["checks"] if c["kind"] == "schema_workload"
    } & {c["file"] for c in plan["checks"] if c["kind"] == "schema_cases"}
    assignments = {}
    for role in ROLES:
        jobs = [
            peer["jobId"] for peer in peers if peer["blueprintId"] == role + "_verifier"
        ]
        if len(jobs) > 1:
            raise ValueError("Choose one dedicated verifier for each responsibility.")
        checks = [
            c
            for c in plan["checks"]
            if c["specialist"] == role
            and not (plan["decision"] == "release" and c["kind"] == "execution_record")
            and not (
                c["kind"] in {"schema_workload", "schema_cases"}
                and c["file"] in waiting_files
            )
        ]
        selected = aspects.scope(ledger or aspects.EMPTY, role)
        if not jobs or not (checks or aspects.applicable(role, selected, plan["paths"])):
            continue
        scoped = {key: value for key, value in plan.items() if key != "plan_id"}
        scoped.update(
            checks=checks, observation_scope=digest(selected), skipped=[other for other in ROLES if other != role]
        )
        scoped["plan_id"] = digest(scoped)
        with RunMailbox.open(block) as mailbox:
            packet = {
                "schema": "software-verification.assignment.v1",
                "role": role,
                "recipient_job_id": jobs[0],
                "plan": scoped,
                "sources": sources,
                "baseline": baseline,
                "observations": selected,
                "evidence_files": pack_files(scoped, evidence_folder, mailbox.attach),
            }
            message = mailbox.send(
                recipient_job_id=jobs[0],
                kind="assignment",
                request_id=scoped["plan_id"],
                subject=aspects.TITLES[role],
                text=f"{len(selected['cases'])} recorded cases and {len(checks)} approved checks.",
                attachment=mailbox.attach(packet),
            )
        assignments[role] = {
            "id": message["id"],
            "job": jobs[0],
            "checks": [c["id"] for c in checks],
            "plan_id": scoped["plan_id"],
        }
    return assignments


def _verified_reply(block, mailbox, role, job_id, assignment_id, plan_id, checks, reply):
    if (
        reply["sender_job_id"] != job_id
        or reply["sender_blueprint_id"] != role + "_verifier"
    ):
        raise ValueError("Dedicated verifier reply identity changed.")
    result = mailbox.read_attachment(reply)
    scoped = result["plan"]
    if (
        result.get("assignment_id") != assignment_id
        or scoped["plan_id"] != plan_id
        or scoped["plan_id"]
        != digest({k: v for k, v in scoped.items() if k != "plan_id"})
    ):
        raise ValueError("Dedicated verifier replied to a different approved plan.")
    verified = wit_reconcile(block, scoped, result["records"])
    if (
        set(checks) != {row["id"] for row in verified["checks"]}
        or any(not row["attempts"] for row in verified["checks"])
        or sum(len(row["attempts"]) for row in verified["checks"])
        != len(result["records"])
    ):
        raise ValueError("Dedicated verifier evidence is incomplete.")
    if "observation_scope" in scoped:
        packet = mailbox.read_assignment_for_result(reply)
        selected = packet["observations"]
        if (digest(selected) != scoped["observation_scope"] or packet["plan"] != scoped
                or result.get("aspect") != aspects.evaluate(block, role, selected, scoped, packet["sources"])):
            raise ValueError("Specialist observations differ from the assigned evidence.")
        verified["aspect"] = result["aspect"]
        verified["verdict"] = aspects.verdict(verified["verdict"], result["aspect"])
    return verified, result["records"]


def collect(block, plan, assignments, *, received=None):
    records, pending = [], []
    for role, entry in assignments.items():
        with RunMailbox.open(block) as mailbox:
            replies = mailbox.messages(
                kind="result", reply_to=entry["id"], include_acknowledged=True, limit=1
            )["items"]
            if not replies:
                pending.append(role)
                continue
            reply = replies[0]
            verified, attempts = _verified_reply(
                block, mailbox,
                role,
                entry["job"],
                entry["id"],
                entry["plan_id"],
                entry["checks"],
                reply,
            )
            if received is not None and "aspect" in verified:
                received[role] = verified["aspect"]
            records.extend(
                {**record, "plan_id": plan["plan_id"]} for record in attempts
            )
            mailbox.acknowledge(reply["id"])
    return records, pending


def await_current(block, plan, assignments, *, timeout=180, clock=time.time, sleep=time.sleep):
    """Wait only for dispatched jobs. Replays read the same acknowledged receipts."""
    remaining = dict(assignments)
    records, received = [], {}
    if not remaining:
        return records, [], received
    path = "specialists/reply-deadline.json"
    ref = block.freeze_checkpoint(path, lambda: {"deadline": clock() + timeout, "plan_id": plan["plan_id"]})
    window = block.read_checkpoint(ref, expected_path=path)
    if window["plan_id"] != plan["plan_id"]:
        raise ValueError("The reply window belongs to a different plan.")
    deadline = window["deadline"]
    while remaining:
        block.check()
        batch, pending = collect(block, plan, remaining, received=received)
        records.extend(batch)
        remaining = {role: remaining[role] for role in pending}
        delay = min(2, deadline - clock())
        if not remaining or delay <= 0:
            break
        sleep(delay)
    return records, list(remaining), received


def earlier_results(block, assignments):
    """Preserve verified late evidence under its originating review, across retries."""
    config = block.original_config.get("inputs", {}).get("payload", {})
    if not config.get("collaboration_group_id") or not config.get(
        "collaboration_peers"
    ):
        return []
    active = {item["id"] for item in assignments.values()}
    path = "specialists/earlier-delegations.json"
    with RunMailbox.open(block) as mailbox:

        def review():
            reports = []
            for reply in mailbox.messages(kind="result", limit=25)["items"]:
                if reply["reply_to"] in active:
                    continue
                packet = mailbox.read_assignment_for_result(reply)
                role, plan = packet["role"], packet["plan"]
                verified, _ = _verified_reply(
                    block, mailbox,
                    role,
                    packet["recipient_job_id"],
                    reply["reply_to"],
                    plan["plan_id"],
                    [check["id"] for check in plan["checks"]],
                    reply,
                )
                reports.append(
                    {
                        "message_id": reply["id"],
                        "assignment_id": reply["reply_to"],
                        "run_id": plan["run_id"],
                        "role": role,
                        "report": verified,
                    }
                )
            return {"reports": reports}

        ref = block.freeze_checkpoint(path, review)
        reports = block.read_checkpoint(ref, expected_path=path)["reports"]
        for report in reports:
            mailbox.acknowledge(report["message_id"])
        return reports
