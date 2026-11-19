"""Verify the staged comparison and describe differences across frozen source."""
from collections import Counter
from hashlib import sha256
import json

from .ci_evidence import DIGEST, read_bounded, validate_ci, validate_commit
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
    descriptor = root / BUNDLE_NAME
    if not descriptor.exists() and not descriptor.is_symlink():
        return None
    if descriptor.is_symlink() or not descriptor.is_file():
        raise ValueError('Use a comparison folder prepared by Code verifier.')
    bundle = json.loads(read_bounded(descriptor, 512_000))
    if (not isinstance(bundle, dict) or set(bundle) - {'schema_version', 'base', 'head', 'includes', 'ci'}
            or bundle.get('schema_version') != BUNDLE_SCHEMA):
        raise ValueError('Use a comparison folder prepared by Code verifier.')
    includes = bundle.get('includes', [])
    if not isinstance(includes, list) or len(includes) > 100:
        raise ValueError('Choose at most 100 repository paths per comparison.')
    includes = [relative_path(path) for path in includes]
    comparison, snapshots = {'includes': includes}, {}
    for side in ('base', 'head'):
        revision = bundle.get(side)
        if (not isinstance(revision, dict) or set(revision) != {'commit', 'sha256', 'omitted'}
                or not isinstance(revision['sha256'], str) or not DIGEST.fullmatch(revision['sha256'])
                or type(revision['omitted']) is not int or not 0 <= revision['omitted'] <= 30_000):
            raise ValueError(f'The comparison is missing a valid {side} snapshot descriptor.')
        commit = validate_commit(revision['commit'])
        folder = root / side
        if folder.is_symlink() or (folder.exists() and not folder.is_dir()):
            raise ValueError(f'The {side} snapshot must be a directory inside the comparison.')
        sources, omitted = capture_folder(folder) if folder.exists() else ({}, [])
        if (omitted or source_digest(sources) != revision['sha256']
                or any(includes and not any(path == p or path.startswith(p + '/') for p in includes)
                       for path in sources)):
            raise ValueError(f'The staged {side} snapshot differs from the prepared comparison. Prepare it again.')
        snapshots[side] = sources
        comparison[side] = {'commit': commit, 'sha256': revision['sha256'], 'omitted': revision['omitted'],
                            'files': len(sources)}
    if 'ci' in bundle:
        comparison['ci'] = validate_ci(bundle['ci'], comparison['head']['commit'])
    return comparison, snapshots


def changed_files(base, head):
    changed = []
    for path in sorted(base.keys() | head.keys()):
        if path not in base:
            changed.append({'path': path, 'kind': 'added'})
        elif path not in head:
            changed.append({'path': path, 'kind': 'removed'})
        elif base[path] != head[path]:
            changed.append({'path': path, 'kind': 'modified'})
    return changed


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
