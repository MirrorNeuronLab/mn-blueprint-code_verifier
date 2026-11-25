"""Rule-specific views on the shared offline report template."""

from pathlib import Path

from mn_web_report_skill import render_document

from .git_comparison import COMPARISON_LABELS
from .rule_document import short_title

WEB_OMISSIONS = {"investigation", "independent_review", "model_confidence"}


def display_result(result):
    value = {key: item for key, item in result.items() if key not in WEB_OMISSIONS}
    if "baseline" in value:
        value["baseline"] = display_result(value["baseline"])
    return value


def render(report, capture, *, baseline=None, downloads=None):
    if report["snapshot_id"] != capture["snapshot_id"]:
        raise ValueError("Report and captured source identities differ")
    assets = Path(__file__).with_name("workspace_assets")
    display = {
        **report,
        "results": [display_result(result) for result in report["results"]],
        "rules": [
            {**rule, "title": rule.get("title") or short_title(rule["statement"])} for rule in report["rules"]
        ],
    }
    content = '<main id="content" tabindex="-1"></main><p id="notice" role="status" aria-live="polite"></p>'
    script = (assets / "workspace.js").read_text()
    style = (assets / "workspace.css").read_text()
    identity = "Captured software"
    if assurance := report.get("assurance"):
        from .assurance_web import render_content

        content = render_content(report, capture["sources"], capture.get("repository_prefix", "")) + content
        style += (assets / "assurance.css").read_text()
        script = (assets / "assurance.js").read_text() + "\n" + script
        origin = {
            "fixture": "Recorded local fixture",
            "supplied": "Supplied observations",
            "source": "Source review",
        }[assurance["origin"]]
        identity = " · ".join(filter(None, [assurance.get("repository"), origin, assurance["revision"][:12]]))
    return render_document(
        title="Software verification",
        identity=identity,
        content_html=content,
        script=script,
        style=style,
        data={
            "report": display,
            "downloads": downloads or {},
            "sources": capture["sources"],
            "baseline": baseline or {},
            "repositoryPrefix": capture.get("repository_prefix", ""),
            "comparisonLabels": COMPARISON_LABELS,
        },
        description=(
            f"Partial extraction: {len(report.get('coverage', {}).get('extraction_gaps', []))} unresolved "
            "source sections. Listed rules only; missing requirements are not assessed. "
            if report.get("coverage", {}).get("extraction_gaps")
            else ""
        )
        + "Source review and recorded observations apply to the selected capture.",
    )
