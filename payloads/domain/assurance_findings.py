"""Attribute observed cases to approved passages and consolidate repeat failures."""

from collections import defaultdict

RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}
BEHAVIOR_ROLES = ("functional", "compatibility")


def approved_requirements(report, sections, prefix):
    results = {row["rule_id"]: row["status"] for row in report.get("results", [])}
    by_path = defaultdict(list)
    approved = {}
    edited = set()
    for rule in report.get("rules", []):
        ident = rule["id"]
        approved[ident] = {
            "id": ident,
            "claim": rule["statement"],
            "source": rule.get("source"),
            "source_review": results.get(ident, "unknown"),
            "cases": [],
        }
        if rule.get("review_edit", {}).get("statement_changed"):
            edited.add(ident)
        origins = [rule, *rule.get("additional_origins", [])]
        for origin in origins:
            if ref := origin.get("source"):
                by_path[ref["path"]].append((ref["start_line"], ref["end_line"], ident))
    unmapped = []
    for role in (*BEHAVIOR_ROLES, "security"):
        for case in sections[role]["cases"]:
            ref = case["source"]
            ids = {
                ident for start, end, ident in by_path[prefix + ref["path"]] if start <= ref["line"] <= end
            }
            link = {"role": role, "case_id": case["id"], "status": case["status"]}
            if len(ids) == 1 and ids.isdisjoint(edited):
                approved[ids.pop()]["cases"].append(link)
            else:
                reason = (
                    "Approved requirement changed"
                    if ids & edited
                    else "Ambiguous passage"
                    if ids
                    else "Outside approved passages"
                )
                unmapped.append({**link, "reason": reason})
    for item in approved.values():
        states = {c["status"] for c in item["cases"]}
        item["outcome"] = (
            "unmet"
            if "unmet" in states
            else "met"
            if states == {"met"}
            else "mixed"
            if "mixed" in states
            else "unmeasured"
        )
    return list(approved.values()), unmapped


def clean_candidate(case):
    return [r for r in case["runs"] if r["revision"] == "candidate" and r["clean"]]


def run_key(role, case, run):
    # IDs are local to a case unless its producer explicitly correlates an issue.
    family = case.get("issue") or (role, case["id"])
    return family, case["fixture"], run["id"]


def conflicting_observations(sections):
    # Views of one physical run can apply different assertions. The same observed value
    # or named stage for that run must agree wherever both views recorded it.
    observed = defaultdict(set)
    for role in BEHAVIOR_ROLES:
        for row in sections[role]["cases"]:
            for run in clean_candidate(row):
                key = run_key(role, row, run)
                observed[key, None].add(run["observed"])
                for stage in run.get("stages", []):
                    observed[key, stage["name"]].add(stage["observed"])
    return {key for (key, _), values in observed.items() if len(values) > 1}


def confirmed(sections):
    groups, policy, leads = {}, [], []
    conflicts = conflicting_observations(sections)
    repeats = defaultdict(list)
    for role, section in sections.items():
        for row in section["cases"]:
            proof = {"role": role, "case_id": row["id"]}
            if role == "security" and row["status"] == "unmet":
                policy.append({**proof, "id": row.get("issue") or row["id"]})
                continue
            runs = clean_candidate(row)
            observations = {run_key(role, row, r) for r in runs}
            consistent = observations.isdisjoint(conflicts)
            if role in BEHAVIOR_ROLES and runs and runs[0]["status"] == "unmet":
                for repeat in runs[1:]:
                    repeats[run_key(role, row, repeat)].append(
                        consistent
                        and repeat["status"] == "unmet"
                        and repeat["observed"] == runs[0]["observed"]
                        and repeat.get("stages") == runs[0].get("stages")
                    )
            if row["status"] == "met" and consistent:
                continue
            if role not in BEHAVIOR_ROLES or not row["repeated"] or not consistent:
                leads.append(proof)
                continue
            identity = row.get("issue") or f"{role}/{row['id']}"
            # A reused issue label cannot turn different observations into one failure.
            signature = identity, row["expected"], runs[0]["observed"]
            entry = groups.setdefault(
                signature,
                {
                    "id": identity,
                    "title": row["claim"],
                    "severity": "low",
                    "expected": row["expected"],
                    "observed": runs[0]["observed"],
                    "acceptance": row.get("remedy"),
                    "regression": False,
                    "proofs": [],
                    "observations": set(),
                },
            )
            entry["observations"].update(observations)
            entry["proofs"].append(proof)
            entry["regression"] |= row["regression"]
            entry["severity"] = min(entry["severity"], row.get("severity", "medium"), key=RANK.get)
    for entry in groups.values():
        entry["distinct_runs"] = len(entry.pop("observations"))
    return (
        sorted(groups.values(), key=lambda d: (RANK[d["severity"]], d["id"])),
        policy,
        leads,
        sum(all(matches) for matches in repeats.values()),
        len(repeats),
    )
