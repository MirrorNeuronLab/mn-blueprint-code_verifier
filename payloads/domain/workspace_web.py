"""Rule-specific views on the shared offline report template."""
from pathlib import Path

from mn_web_report_skill import render_document

from .git_comparison import COMPARISON_LABELS
from .rule_document import short_title

WEB_OMISSIONS = {'investigation', 'independent_review', 'model_confidence'}


def display_result(result):
    value = {key: item for key, item in result.items() if key not in WEB_OMISSIONS}
    if 'baseline' in value:
        value['baseline'] = display_result(value['baseline'])
    return value


def render(report, capture, *, baseline=None):
    if report["snapshot_id"] != capture["snapshot_id"]:
        raise ValueError("Report and captured source identities differ")
    assets = Path(__file__).with_name("workspace_assets")
    display = {**report, 'results': [display_result(result) for result in report['results']],
               'rules': [{**rule, 'title': rule.get('title') or short_title(rule['statement'])}
                         for rule in report['rules']]}
    return render_document(
        title="Code verification", identity="Captured software",
        content_html='<main id="content" tabindex="-1"></main><p id="notice" role="status" aria-live="polite"></p>',
        script=(assets / "workspace.js").read_text(),
        style=(assets / "workspace.css").read_text(),
        data={"report": display, "sources": capture["sources"], "baseline": baseline or {},
              "comparisonLabels": COMPARISON_LABELS},
        description=(f"Partial extraction: {len(report.get('coverage', {}).get('extraction_gaps', []))} unresolved "
                     "source sections. Listed rules only; missing requirements are not assessed. "
                     if report.get('coverage', {}).get('extraction_gaps') else '')
                    + "Static source review · Repository code and tests were not executed.",
    )
