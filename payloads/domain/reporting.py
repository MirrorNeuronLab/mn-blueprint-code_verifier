"""Publish every rule, its admitted citations, and explicit static-review limits."""
from collections import Counter
from urllib.parse import quote
import re
import json
from hashlib import sha256

from mn_sdk.blueprint.hooks import report_activity
from mn_sdk_common.publication import ArtifactWrite
from mn_sdk.blueprint.outputs import publish_artifact_bundle, publish_files

from .artifacts import read, save
from .publication import deliver_reports
from .configuration import BLUEPRINT_ID
from .consolidation import consolidate
from .git_comparison import COMPARISON_LABELS
from .report_findings import ci_view, decision_queue, finding_label, main_evidence, suggested_check
from .rule_document import short_title
from .rule_review import require_approved_rules


def cell(value):
    value = str(value).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('\n', ' ')
    return re.sub(r'([\\`*\[\]|])', r'\\\1', value)


def source_link(evidence, prefix='source'):
    path, start, end = evidence['path'], evidence['start_line'], evidence['end_line']
    return f"[{cell(path)}:{start}–{end}]({prefix}/{quote(path, safe='/')}#L{start})"


def publish(block, inputs):
    report_activity("Writing the rules report", owner_blueprint=BLUEPRINT_ID,
                    step_id=block.step_id, run_dir=block.store.run_dir)
    capture = block.store.read(inputs["previous"]["capture"])
    verification = block.store.read(inputs["previous"]["verification"])
    rules = read(block, "rules.json")
    if not (capture['snapshot_id'] == rules['snapshot_id'] == verification['snapshot_id']):
        raise ValueError('Report inputs have different source identities.')
    results = {r['rule_id']: r for r in verification['results']}
    if len(results) != len(verification['results']) or set(results) != {r['id'] for r in rules['rules']}:
        raise ValueError('Every rule must have exactly one verification result.')
    approval = require_approved_rules(block, rules)
    if verification.get('rules_review') != approval:
        raise ValueError('Verification does not match the approved rules.')
    counts = dict(Counter(r['status'] for r in results.values()))
    comparison = capture.get('comparison')
    if rules.get('comparison') != comparison or bool(comparison) != bool(verification.get('comparison')):
        raise ValueError('Report inputs have different Git comparisons.')
    ci = ci_view(comparison, rules['rules'])
    combined = consolidate(block, inputs, capture, approval, rules, results, ci=ci)
    specialist_checks = {check['id']: check for check in combined['specialist_report']['checks']}
    queue = decision_queue(verification['results'], ci)
    next_checks = {ident: check for ident in queue if (check := suggested_check(results[ident], ci))}
    gaps = rules.get('extraction_gaps', [])
    coverage_note = (f'Partial extraction: {len(gaps)} source sections remain unresolved. '
                     'Missing requirements have not been assessed.' if gaps else
                     'Extraction covered the selected document packets.')
    if not rules['rules']:
        coverage_note += ' No software rules were identified. This report establishes no conformance result.'
    lines = ['# Software rules report', '',
             'Static AI review of a captured source folder. Repository code and tests were not executed. '
             'Pass means the inspected implementation supports the rule within this scope; it is not runtime proof. '
             'Confidence is an uncalibrated AI assessment, capped at 0.85 for static judgments. '
             'Unknown requires more evidence or human review.', '',
             f"Capture: `{capture['snapshot_id']}`. Rules: {len(results)}. "
             f"Pass: {counts.get('pass', 0)}. Fail: {counts.get('fail', 0)}. Unknown: {counts.get('unknown', 0)}.", '',
             'The supervisor approved these exact rules before verification started.', '',
             coverage_note, '']
    if comparison:
        base, head = comparison['base'], comparison['head']
        lines += ['## Git comparison', '',
                  f"Checked the same approved rules on `{base['commit'][:12]}` and `{head['commit'][:12]}`. "
                  f"{len(comparison['changes'])} captured files changed.", '']
        for status, count in verification['comparison']['summary'].items():
            lines.append(f'- {COMPARISON_LABELS[status]} ({count})')
        lines.append('')
    if queue:
        by_id = {rule['id']: rule for rule in rules['rules']}
        lines += ['## What needs attention', '']
        for ident in queue[:5]:
            result, rule = results[ident], by_id[ident]
            label = finding_label(result, ci)
            title = rule.get('title') or short_title(rule['statement'])
            evidence = main_evidence(result)
            lines.append(f"- **{cell(title)}** ({label}). {cell(result['explanation'])}"
                         + (f' {source_link(evidence)}.' if evidence else ''))
            check = next_checks.get(ident)
            if check:
                lines.append(f"  Suggested check — {cell(check)}")
        if len(queue) > 5:
            lines.append(f'\nSee the detailed results for all {len(queue)} rules that need attention.')
        lines.append('')
    if ci:
        lines += ['## Imported CI evidence', '',
                  f"JUnit file `{cell(ci['file'])}` for `{ci['commit'][:12]}`. "
                  'These are supplied test observations alongside the static judgments.', '',
                  '| Rule | Test | CI result | Mapping |', '| --- | --- | --- | --- |']
        mapping_labels = {'linked': 'Linked', 'rule_missing': 'Rule absent from this review',
                          'rule_edited': 'Rule edited after mapping'}
        for check in ci['checks']:
            lines.append(f"| {cell(check['rule_id'])} | {cell(check['test'])} | {check['status'].capitalize()} | "
                         f"{mapping_labels[check['mapping']]} |")
        lines.append('')
    lines += ['## Rule results', '', '| Rule | Pass or not | Evidence with reference | Confidence (0–1) | Specialist checks |',
              '| --- | --- | --- | --- | --- |']
    for rule in rules['rules']:
        result = results[rule['id']]
        references = []
        for evidence in result['evidence']:
            references.append(f"{source_link(evidence)} SHA-256 `{evidence['sha256']}`: {cell(evidence['quote'])}")
        status = result['status'].capitalize()
        if 'baseline' in result:
            prior = result['baseline']
            status += f" (base {prior['status'].capitalize()})"
            if prior_span := main_evidence(prior):
                references.append(f"Base evidence {source_link(prior_span, 'baseline/source')}")
        linked = ', '.join(f"{cell(ident)} ({cell(specialist_checks[ident]['status'])})"
                           for ident in combined['rule_checks'][rule['id']])
        lines.append(f"| {cell(rule['id'] + ': ' + rule['statement'])} | {status} | "
                     f"{'; '.join(references) or 'No admissible implementation evidence.'} "
                     f"{cell(result['explanation'])} {cell(next_checks.get(rule['id'], ''))} "
                     f"| {result['confidence']:.2f} | {linked or 'None linked'} |")
    diagnostics = verification.get('diagnostics', {})
    lines += ['', '## Investigation coverage', '',
              f"Model calls: {diagnostics.get('model_calls', 0)}. "
              'Unknowns retain inspected evidence and a next step; exclusions are not successful assessments.']
    for reason, count in sorted(diagnostics.get('unknown_reasons', {}).items()):
        lines.append(f'- {cell(reason)}: {count}.')
    lines += ['', '## Rule origins', '']
    for rule in rules['rules']:
        origin = rule['source']
        lines.append(f"- {cell(rule['id'])}: {cell(rule['origin'])}, "
                     f"{cell(origin['path'])}:{origin['start_line']}–{origin['end_line']}.")
    lines += ['', '## Coverage and limitations', '',
              f"Captured {len(capture['sources'])} UTF-8 files. Excluded {len(capture['omitted'])} entries. "
              'Excluded folders represent whole subtrees. See capture.json and static-analysis.json for the complete inventory and parser gaps.',
              'Missing literal hits, documentation claims, test source, and unresolved call edges do not prove compliance or violation. '
              'Generated rules are candidates for supervisor review; complete extraction is not a guarantee that AI found every requirement.']
    selection = rules.get('documentation_selection', {})
    excluded_documents = selection.get('excluded_documents', [])
    if selection:
        lines += ['', f"Rule document scope: {cell(selection['scope'])}. "
                  f"Selected {len(selection['selected_documents'])} documents; "
                  f"excluded {len(excluded_documents)} documents from rule extraction."]
        lines += [f"- {cell(item['path'])}: {cell(item['reason'])}." for item in excluded_documents]
    excluded_sections = selection.get('excluded_sections', [])
    excluded_candidates = rules.get('excluded_candidates', [])
    if excluded_sections or excluded_candidates:
        lines += ['', f'Excluded {len(excluded_sections)} non-normative sections and {len(excluded_candidates)} candidates. '
                  'These are outside the assessed ruleset, not passing results.']
        lines += [f"- {cell(item['path'])}:{item['start_line']}–{item['end_line']}: {cell(item['reason'])}."
                  for item in excluded_sections]
    if gaps:
        lines += ['', '## Unresolved extraction coverage', '',
                  'This report covers the approved candidate rules only. Requirements in the following '
                  'source sections remain unresolved; this is not a complete conformance assessment.', '',
                  '| Source section | Status | Reason |', '| --- | --- | --- |']
        lines += [f"| {cell(gap['path'])}:{gap['start_line']}–{gap['end_line']} | Unknown | {cell(gap['reason'])} |"
                  for gap in gaps]
    final = {'schema_version': 'mn.software_rules.report.v1', 'snapshot_id': capture['snapshot_id'],
             'rules': rules['rules'], 'results': verification['results'], 'summary': counts,
             'source_execution': False, 'report': 'report.md', 'rules_markdown': 'rules.md',
             'rules_review': approval,
             'diagnostics': diagnostics, 'verification_policy': verification.get('verification_policy'),
             'attention_rule_ids': queue, 'suggested_checks': next_checks,
             'assessment_status': 'needs_review' if not rules['rules'] or gaps or counts.get('unknown') else 'complete',
             'coverage': {'documents': rules['extraction_coverage'], 'omitted': capture['omitted'],
                          'extraction_status': rules.get('extraction_status', 'complete'), 'extraction_gaps': gaps,
                          'documentation_selection': selection, 'excluded_candidates': excluded_candidates,
                          'review_flags': rules.get('review_flags', [])}}
    if comparison:
        final['comparison'] = {**{key: value for key, value in comparison.items() if key != 'ci'}, **verification['comparison']}
    if ci:
        final['ci_evidence'] = ci
    from mn_web_report_skill import render_report_markdown
    final.update(combined)
    if combined["verdict"] != "PASS":
        final["assessment_status"] = "needs_review"
    summary_lines = ["# Software verification report", "", f"**Verdict: {combined['verdict']}**", ""]
    summary_lines.extend(f"- {cell(reason)}" for reason in combined["reasons"])
    ledger = combined["specialist_report"]
    if ledger.get("earlier_delegations"):
        summary_lines += ["", "## Results from earlier reviews", ""]
        for result in ledger["earlier_delegations"]:
            summary_lines.append(f"- {cell(result['role'].capitalize())} verifier · {cell(result['report']['verdict'])}"
                                 f" · review {cell(result['run_id'])}")
    if ledger["findings"]:
        summary_lines += ["", "## Findings to investigate", ""]
        for item in ledger["findings"][:12]:
            summary_lines.append(f"- **{cell(item.get('title') or item['observed'])}** · "
                                 f"{cell(item['severity'])} severity. {cell(item['recommendation'])}")
    if ledger.get("requirement_traces"):
        summary_lines += ["", "## Specification and generated tests", ""]
        for trace in ledger["requirement_traces"]:
            text = trace.get("observed", trace["reason"])
            summary_lines.append(f"- **{cell(trace['expectation'])}** {cell(trace['change'])}. {cell(text)}")
            for name, ref in [("Specification", trace.get("specification")), ("Generated test", trace.get("test_location")),
                              *(("Implementation", ref) for ref in trace["locations"])]:
                if ref:
                    location = {**ref, "path": capture.get("repository_prefix", "") + ref["path"],
                                "start_line": ref["line"], "end_line": ref.get("end_line", ref["line"])}
                    summary_lines.append(f"  - {name} {source_link(location)}")
    for specialist in combined["specialists"]:
        summary_lines.extend(["", render_report_markdown(specialist["document"]).replace("# ", "## ", 1).strip()])
    lines = [*summary_lines, "", "## Source rule review", "", *lines[2:]]
    # Captured evidence is committed individually; large repositories do not
    # consume the publication bundle's limit of 128 top-level report artifacts.
    for path, content in capture["sources"].items():
        block.check()
        block.store.commit_bytes("source/" + path, content.encode("utf-8"), kind="captured_source")
    baseline = {}
    if comparison:
        baseline = block.store.read(capture['baseline_capture'])
        for path, content in baseline.items():
            block.check()
            block.store.commit_bytes("baseline/source/" + path, content.encode("utf-8"), kind="captured_source")
    encoded = json.dumps(final, sort_keys=True, ensure_ascii=False, allow_nan=False).encode("utf-8")
    revision = sha256(encoded).hexdigest()

    def page():
        try:
            from .workspace_web import render
            return render(final, capture, baseline=baseline).encode("utf-8")
        except Exception as error:
            save(block, "presentation-status.json", {"status": "unavailable", "error_type": type(error).__name__})
            raise

    def handle():
        from mn_sdk_web_ui import static_run_report_handle
        if not block.store.path("web/index.html").is_file():
            raise ValueError("Optional report page is unavailable.")
        return json.dumps(static_run_report_handle(block.store.run_dir, "web/index.html",
            title="Code verification", optional=True)).encode("utf-8")

    receipt = publish_artifact_bundle(block, [
        ArtifactWrite("final_artifact", "final_artifact.json", encoded, kind="json", authoritative=True),
        ArtifactWrite("result", "result.json", encoded, kind="json", authoritative=True),
        ArtifactWrite("report", "report.md", ("\n".join(lines) + "\n").encode("utf-8"), kind="markdown"),
        ArtifactWrite("rules_markdown", "rules.md", block.store.path("rules.md").read_bytes(), kind="markdown", mode=0o644),
        ArtifactWrite("web_report", "web/index.html", page, kind="html", required=False, revision=revision),
        ArtifactWrite("web_ui", "web_ui.json", handle, kind="json", required=False, revision=revision, mode=0o644),
    ], receipt_path=block.root + "/publication.json")
    if receipt["warnings"] and not block.store.path("presentation-status.json").exists():
        save(block, "presentation-status.json", {"status": "unavailable",
            "failed_artifact_ids": [warning["artifact_id"] for warning in receipt["warnings"]]})
    deliver_reports(block, complete=True)
    try:
        deliver_reports(block, presentation=True)
    except Exception as error:
        save(block, "presentation-status.json", {"status": "unavailable", "error_type": type(error).__name__})
        report_activity("The Markdown report is ready. The optional web view could not be delivered.",
                        kind="action", owner_blueprint=BLUEPRINT_ID, run_dir=block.store.run_dir)
    # The native worker exports only declared published files across the worker
    # boundary. Include the page and handle, as well as the authoritative report.
    published_files = publish_files(block, [
        ArtifactWrite(item['id'], item['reference']['path'], block.store.read_bytes(item['reference']),
            kind=item['reference']['kind'], required=item['required'])
        for item in receipt['artifacts']
    ], name='rules_report')
    return {"rules": len(results), "summary": counts, "verdict": final["verdict"], "report": "report.md",
            "artifacts": receipt["artifacts"], "warnings": receipt["warnings"],
            "published_files": published_files}
