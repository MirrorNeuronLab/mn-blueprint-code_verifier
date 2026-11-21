"""Select independent approved checks for hired specialists and reconcile their receipts."""

from mn_sdk.blueprint.services import RunMailbox
from mn_verification_checks_skill import ROLES, digest, reconcile


def assign(block, plan, sources, baseline):
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
            and not (
                c["kind"] in {"schema_workload", "schema_cases"}
                and c["file"] in waiting_files
            )
        ]
        if not jobs or not checks:
            continue
        scoped = {key: value for key, value in plan.items() if key != "plan_id"}
        scoped.update(
            checks=checks, skipped=[other for other in ROLES if other != role]
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
            }
            message = mailbox.send(
                recipient_job_id=jobs[0],
                kind="assignment",
                request_id=scoped["plan_id"],
                subject=f"Verify {role} checks",
                text=f"{len(checks)} approved checks.",
                attachment=mailbox.attach(packet),
            )
        assignments[role] = {
            "id": message["id"],
            "job": jobs[0],
            "checks": [c["id"] for c in checks],
            "plan_id": scoped["plan_id"],
        }
    return assignments


def _verified_reply(mailbox, role, job_id, assignment_id, plan_id, checks, reply):
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
    verified = reconcile(scoped, result["records"])
    if (
        set(checks) != {row["id"] for row in verified["checks"]}
        or any(not row["attempts"] for row in verified["checks"])
        or sum(len(row["attempts"]) for row in verified["checks"])
        != len(result["records"])
    ):
        raise ValueError("Dedicated verifier evidence is incomplete.")
    return verified, result["records"]


def collect(block, plan, assignments):
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
            _, attempts = _verified_reply(
                mailbox,
                role,
                entry["job"],
                entry["id"],
                entry["plan_id"],
                entry["checks"],
                reply,
            )
            records.extend(
                {**record, "plan_id": plan["plan_id"]} for record in attempts
            )
            mailbox.acknowledge(reply["id"])
    return records, pending


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
                    mailbox,
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
