"""Prioritize developer decisions while retaining the source and CI verdicts."""

from .evidence import evidence_handle
from .git_comparison import COMPARISON_LABELS


def ci_view(comparison, rules):
    receipt = comparison.get('ci') if comparison else None
    if receipt is None:
        return None
    by_id = {rule['id']: rule for rule in rules}
    checks = []
    for check in receipt['checks']:
        rule = by_id.get(check['rule_id'])
        if rule is None:
            mapping = 'rule_missing'
        elif rule.get('review_edit', {}).get('statement_changed'):
            mapping = 'rule_edited'
        else:
            mapping = 'linked'
        checks.append({**check, 'mapping': mapping})
    return {**receipt, 'checks': checks}


def conflicting_ci_rules(ci):
    return {check['rule_id'] for check in (ci or {}).get('checks', [])
            if check['mapping'] == 'linked' and check['status'] in {'failed', 'mixed'}}


def decision_queue(results, ci):
    flagged = conflicting_ci_rules(ci)
    queue = []
    for result in results:
        change = result.get('comparison_status')
        if change == 'regression':
            priority = 0
        elif result['status'] == 'fail':
            priority = 1
        elif result['rule_id'] in flagged:
            priority = 2
        elif result['status'] == 'unknown' or change in {'inconclusive', 'needs_baseline', 'needs_change_evidence'}:
            priority = 3
        else:
            continue
        queue.append((priority, result))
    queue.sort(key=lambda item: item[0])
    return [result['rule_id'] for _, result in queue]


def finding_label(result, ci):
    change = result.get('comparison_status')
    if result['status'] != 'fail' and any(
        check['rule_id'] == result['rule_id'] and check['mapping'] == 'linked' and check['status'] in {'failed', 'mixed'}
        for check in (ci or {}).get('checks', [])
    ):
        return 'CI needs attention'
    return COMPARISON_LABELS.get(change, result['status'].capitalize())


def suggested_check(result, ci):
    if check := result.get('recommended_check'):
        return check
    change = result.get('comparison_status')
    if change == 'needs_change_evidence':
        return 'Trace the cited behavior through the changed source and identify the change that affects it.'
    if change == 'needs_baseline' or (change == 'inconclusive' and result['status'] == 'pass'):
        return result['baseline'].get('recommended_check') or (
            'Check the same scenario on the base commit to establish the earlier behavior.'
        )
    if finding_label(result, ci) == 'CI needs attention':
        return 'Review the mapped CI checks on the proposed commit and reproduce the observed failure.'
    return result.get('next_step')


def main_evidence(result):
    spans = result['evidence']
    ids = set(result.get('assessment', {}).get('enforcement_evidence_ids', []))
    return next((span for span in spans if evidence_handle(span) in ids), spans[0] if spans else None)
