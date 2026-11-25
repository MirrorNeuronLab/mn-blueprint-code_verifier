"""Evidence ownership and admission for the suite's four review sections."""

from pathlib import PurePosixPath

from .wit_verification import assess
from mn_comparison_evidence_skill import evidence_blocks, select

CATEGORIES = {
    "functional": "workflow",
    "compatibility": "boundary",
    "security": "policy",
    "reliability": "test_control",
}
TITLES = {
    "functional": "Functional intent",
    "defects": "Verified defects",
    "compatibility": "Integration and regression",
    "security": "Security and authorization",
    "reliability": "Independent test quality",
}
EMPTY = {"digest": None, "cases": [], "coverage": None}


def scope(ledger, role):
    return select(ledger, CATEGORIES[role])


def applicable(role, selected, paths):
    return bool(
        selected["cases"]
        or selected["coverage"]
        or (
            role == "reliability"
            and any(
                (p.name.startswith("test_") or p.name.endswith("_test.py")) and p.suffix == ".py"
                for p in map(PurePosixPath, paths)
            )
        )
    )


def evaluate(block, role, selected, plan, sources):
    return assess(block, selected, test_sources=sources if role == "reliability" else None, paths=plan["paths"])


def verdict(original, measured):
    states = {row["status"] for row in measured["cases"]}
    if "unmet" in states:
        return "FAIL"
    if states & {"unmeasured", "mixed"} and original in {"PASS", "SKIPPED"}:
        return "INCONCLUSIVE"
    return "PASS" if original == "SKIPPED" and states == {"met"} else original


def with_observations(view, measured):
    """Produce the same specialist document when issuing and checking its receipt."""
    if measured is None:
        return view
    result = verdict(view["verdict"], measured)
    original = view["document"]
    sections = list(original["sections"])
    if blocks := evidence_blocks(measured):
        sections.insert(0, {"id": "measured-aspect", "title": TITLES[view["id"]], "blocks": blocks})
    document = {
        **original,
        "summary": result + " · " + original["summary"].partition(" · ")[2],
        "sections": sections,
    }
    return {**view, "verdict": result, "document": document}
