"""Record the two fixed, fictional revisions shipped with this example."""

import dis
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from hashlib import sha256
from xml.etree import ElementTree

from mn_verification_checks_skill import digest, snapshot_id

ROOT = Path(__file__).resolve().parent
PAIR = ROOT / "comparison"
REPO = "fixture/dispatch-queue"
PROFILE = "E4,E7,E9,F"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    prior = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = prior
    return module


def encoded(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()


def pin(value):
    return sha256(encoded(value)).hexdigest()


def reference_tools():
    root = PAIR / "head"
    env = {
        **os.environ,
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "PYTEST_ADDOPTS": "",
    }

    def run(args):
        return subprocess.run(
            args, cwd=root, env=env, check=True, capture_output=True, text=True, timeout=30
        ).stdout

    with tempfile.TemporaryDirectory() as temp:
        junit = Path(temp) / "tests.xml"
        run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                "--junitxml",
                str(junit),
                "test_dispatch.py",
            ]
        )
        cases = {}
        for item in ElementTree.parse(junit).iter("testcase"):
            status = (
                "failed"
                if item.find("failure") is not None or item.find("error") is not None
                else "skipped"
                if item.find("skipped") is not None
                else "passed"
            )
            cases[item.attrib["name"]] = [status]
    ruff = shutil.which("ruff") or str(Path(sys.executable).with_name("ruff"))
    lint = run([ruff, "check", "--no-cache", "--select", PROFILE, "--output-format", "json", "."])
    if json.loads(lint) != [] or not cases:
        raise ValueError("The example requires an observed clean lint result and a nonempty test inventory.")
    return cases, run([sys.executable, "-m", "pytest", "--version"]).strip(), run([ruff, "--version"]).strip()


def record():
    captures, modules, pipelines, descriptor = (
        {},
        {},
        {},
        {"schema_version": "mn.code_verifier.comparison.v1"},
    )
    for side in ("base", "head"):
        directory = PAIR / side
        source = {p.name: p.read_text() for p in sorted(directory.iterdir()) if p.is_file()}
        captures[side] = source
        modules[side] = load("example_dispatch_" + side, directory / "dispatch.py")
        pipelines[side] = load("example_delivery_" + side, directory / "delivery.py")
        tree = digest([[p, sha256(t.encode()).hexdigest()] for p, t in sorted(source.items())])
        descriptor[side] = {"commit": tree[:40], "sha256": tree, "omitted": 0}
    previous = sys.modules.get("dispatch")
    sys.modules["dispatch"] = modules["head"]
    try:
        tests = load("example_dispatch_tests", PAIR / "head/test_dispatch.py")
    finally:
        if previous is None:
            sys.modules.pop("dispatch")
        else:
            sys.modules["dispatch"] = previous

    rows, locations = [], {}

    def observations(name, observe, *, both=True, repeats=2):
        return [
            {
                "id": f"{name}-{side}-{attempt}",
                "revision": "candidate" if side == "head" else "baseline",
                "clean": True,
                **observe(side),
            }
            for side in (("base", "head") if both else ("head",))
            for attempt in range(1, repeats + 1)
        ]

    def case(
        ident,
        category,
        claim,
        expected,
        line,
        context,
        fixture,
        runs,
        refs,
        *,
        issue=None,
        remedy=None,
        severity="medium",
    ):
        row = {
            "id": ident,
            "category": category,
            "claim": claim,
            "expected": expected,
            "context": context,
            "source": {"path": "SPEC.md", "line": line},
            "fixture": digest(fixture),
            "runs": runs,
            "severity": severity,
        }
        if issue:
            row["issue"] = issue
        if remedy:
            row["remedy"] = remedy
        rows.append(row)
        locations[ident] = [{"path": path, "line": lineno} for path, lineno in refs]

    def journey(side, copies):
        pipe, entries = pipelines[side], []
        wire = pipe.accept("dispatch-17")
        inbox = pipe.deliver(wire, copies)
        delivered = pipe.consume(inbox, entries, modules[side].enqueue)
        value = f"{len(entries)} queue " + ("entry" if len(entries) == 1 else "entries")
        return {
            "observed": value,
            "stages": [
                {"name": "Producer", "expected": "dispatch-17", "observed": json.loads(wire)["request_id"]},
                {"name": "Retry transport", "expected": str(copies), "observed": str(len(delivered))},
                {"name": "Queue consumer", "expected": "1 queue entry", "observed": value},
            ],
        }

    for n, key, claim, line in [
        (2, "retry", "Retrying creates one queue entry", 3),
        (1, "new", "A new dispatch reaches the queue once", 4),
    ]:
        fixture = {"request_id": "dispatch-17", "copies": n, "initial_queue": []}
        trace = observations("dispatch-" + key, lambda side: journey(side, n))
        for category in ("workflow", "boundary"):
            runs = (
                trace
                if category == "boundary"
                else [{k: v for k, v in r.items() if k != "stages"} for r in trace]
            )
            case(
                category + "-" + key,
                category,
                claim,
                "1 queue entry",
                line,
                {"workflow": "Dispatch requests"},
                fixture,
                runs,
                [("dispatch.py", 5), ("delivery.py", 18)],
                issue="DISPATCH-17" if n == 2 else None,
                severity="high",
                remedy="Deliver one request twice from an empty queue. The final queue must contain exactly one entry.",
            )

    def label(side, value):
        try:
            return {"observed": modules[side].display_label(value)}
        except ValueError:
            return {"observed": "rejected"}

    for key, value, expected, line in [("trim", "  North  ", "North", 5), ("blank", "   ", "rejected", 6)]:
        case(
            "label-" + key,
            "workflow",
            "Trim the label" if key == "trim" else "Reject a blank label",
            expected,
            line,
            {"workflow": "Labels"},
            {"input": value},
            observations("label-" + key, lambda side: label(side, value)),
            [("dispatch.py", 10)],
        )
    for actor, action, expected, line in [
        ("reviewer", "read", "allow", 7),
        ("reviewer", "archive", "deny", 8),
        ("supervisor", "archive", "allow", 9),
    ]:
        ident = actor + "-" + action
        ctx = {"actor": actor, "action": action, "resource": "draft"}
        runs = observations(
            ident,
            lambda side: {"observed": json.loads(captures[side]["policy.json"])[actor][action + " draft"]},
            repeats=1,
        )
        case(
            ident,
            "policy",
            f"{actor.capitalize()} {action} permission",
            expected,
            line,
            ctx,
            ctx,
            runs,
            [("policy.json", 2 if actor == "reviewer" else 3)],
            issue="POLICY-04" if expected == "deny" else None,
            remedy="The reviewer row must deny archiving. The supervisor row must retain its approved permission.",
        )

    original_cases, pytest_version, ruff_version = reference_tools()
    suite_tests = [getattr(tests, name) for name in original_cases]
    observed_lines = set()
    file = modules["head"].display_label.__code__.co_filename

    def trace(frame, event, arg):
        if event == "line" and frame.f_code.co_filename == file:
            observed_lines.add(frame.f_lineno)
        return trace

    def suite(fn, *, measure=False):
        prev_impl, prev_trace = tests.display_label, sys.gettrace()
        tests.display_label = fn
        try:
            if measure:
                sys.settrace(trace)
            for test in suite_tests:
                test()
        except AssertionError:
            return "failed"
        finally:
            sys.settrace(prev_trace)
            tests.display_label = prev_impl
        return "passed"

    original = suite(modules["head"].display_label, measure=True)
    for key, change, mutant, line in [
        ("padding", "Keep surrounding whitespace", lambda raw: raw, 5),
        ("blank", "Accept a blank label", lambda raw: raw.strip(), 6),
    ]:
        cases = observations(
            "control-" + key,
            lambda _: {
                "original": original,
                "observed": "killed" if suite(mutant) == "failed" else "survived",
            },
            both=False,
        )
        case(
            "control-" + key,
            "test_control",
            f"Existing tests detect the change: {change.lower()}",
            "killed",
            line,
            {"test": "test_dispatch.py", "change": change},
            {"change": change, "tests": sorted(original_cases)},
            cases,
            [("test_dispatch.py", 4), ("dispatch.py", 10)],
            remedy="Add a test that requires a blank display label to raise ValueError."
            if key == "blank"
            else None,
        )

    def rejects_blank(fn):
        try:
            fn("   ")
        except ValueError:
            return True
        return False

    repair = {
        "original-label-rejects-blank": [
            "passed" if rejects_blank(modules["head"].display_label) else "failed"
        ],
        "detects-accept-blank-control": [
            "passed" if not rejects_blank(lambda raw: raw.strip()) else "failed"
        ],
    }
    executable = {
        line
        for fn in (modules["head"].display_label, modules["head"].enqueue)
        for _, line in dis.findlinestarts(fn.__code__)
        if line is not None and line > fn.__code__.co_firstlineno
    }
    subject, baseline = snapshot_id(captures["head"]), snapshot_id(captures["base"])
    ledger = {
        "schema": "mn.comparison-evidence.v1",
        "subject": subject,
        "baseline_subject": baseline,
        "cases": rows,
        "coverage": {
            "tool": "Python line trace · existing tests",
            "paths": ["dispatch.py"],
            "covered_lines": len(observed_lines & executable),
            "total_lines": len(executable),
        },
    }
    files = {pin(ledger): ledger}
    checks = []
    for ident, tool, criterion, cases in [
        ("existing-units", pytest_version, "Existing pytest suite on the candidate", original_cases),
        (
            "existing-lint",
            ruff_version + " · " + PROFILE,
            "Ruff E4, E7, E9 and F on the candidate Python files",
            {"selected-lint-rules": ["passed"]},
        ),
        (
            "blank-label-repair",
            "Python",
            "Suggested blank-label assertion accepts the original and detects the control",
            repair,
        ),
    ]:
        scope = {"tool": tool, "criterion": criterion, "cases": sorted(cases)}
        record = {
            "schema_version": "mn.verification.execution.v1",
            "check_id": ident,
            "subject": subject,
            "base_commit": descriptor["base"]["commit"],
            "revision": descriptor["head"]["commit"],
            "artifact_sha256": None,
            "target": "local-fixture",
            "repository": REPO,
            "suite_sha256": digest(scope),
            "runner_sha256": digest(
                {"tool": tool, "harness": sha256(Path(__file__).read_bytes()).hexdigest()}
            ),
            "fixture_sha256": subject,
            "cases": cases,
            "test_id": tool,
        }
        if ident == "existing-units":
            record["observations"] = {
                "test_counts": {
                    state: sum(result == [state] for result in cases.values())
                    for state in ("passed", "failed", "skipped", "inconclusive")
                }
            }
        files[pin(record)] = record
        checks.append(
            {
                "id": ident,
                "kind": "execution_record",
                "specialist": "reliability",
                "requirement": criterion,
                "target": record["target"],
                "suite_sha256": record["suite_sha256"],
                "receipt_sha256": pin(record),
                "cases": list(cases),
            }
        )
    basis = {
        "schema": "otterdesk.assurance-basis.v1",
        "subject": subject,
        "baseline_subject": baseline,
        "case_digest": pin(ledger),
        "origin": "fixture",
        "boundary": "in_process",
        "policy": "configuration",
        "collection": "The bundled recorder exercised two fictional revisions locally. Workflow and integration views share the same dispatch runs.",
        "gates": {"unit_tests": "existing-units", "lint": "existing-lint"},
        "locations": locations,
        "repair_checks": {"control-blank": "blank-label-repair"},
    }
    files[pin(basis)] = basis
    return descriptor, files, checks, pin(ledger), pin(basis)


if __name__ == "__main__":
    descriptor, files, checks, ledger, basis = record()
    (PAIR / "code-verifier-comparison.json").write_bytes(encoded(descriptor))
    for identity, content in files.items():
        (ROOT / "evidence" / (identity + ".json")).write_bytes(encoded(content))
    print(
        json.dumps(
            {"assurance_evidence_sha256": ledger, "assurance_basis_sha256": basis, "checks": checks}, indent=2
        )
    )
