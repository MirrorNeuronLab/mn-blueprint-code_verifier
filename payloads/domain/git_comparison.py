"""Verify the staged comparison and describe differences across frozen source."""
from collections import Counter
from hashlib import sha256
import json

from .ci_evidence import validate_ci
from .source_files import relative_path

BUNDLE_NAME = 'code-verifier-comparison.json'
BUNDLE_SCHEMA = 'mn.code_verifier.comparison.v1'

COMPARISON_LABELS = {
    'regression': 'New regression',
    'existing_failure': 'Existing failure',
    'needs_baseline': 'Failure needs a baseline',
    'needs_change_evidence': 'Change link needs evidence',
    'inconclusive': 'Needs evidence',
    'resolved': 'Resolved',
    'unchanged': 'Still supported',
}


def source_digest(sources):
    hashes = [(path, sha256(value.encode()).hexdigest()) for path, value in sorted(sources.items())]
    return sha256(json.dumps(hashes, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def load_bundle(root, capture_folder):
    # Keep standalone Git preparation usable with the standard library.
    from mn_verification_checks_skill.comparison import read_pair
    return read_pair(root, capture_folder, validate_ci=validate_ci, validate_path=relative_path)


def changed_files(base, head):
    from mn_verification_checks_skill.comparison import changed_files as compare_paths
    return compare_paths(base, head)


def change_status(base, head, *, cites_change):
    if {base, head} == {'pass', 'fail'} and not cites_change:
        return 'needs_change_evidence'
    if head == 'fail':
        return {'pass': 'regression', 'fail': 'existing_failure', 'unknown': 'needs_baseline'}[base]
    if head == 'unknown' or base == 'unknown':
        return 'inconclusive'
    return 'resolved' if base == 'fail' else 'unchanged'


def comparison_summary(results):
    return dict(Counter(result['comparison_status'] for result in results))
