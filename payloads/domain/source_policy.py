"""Software verifier suite's source authority policy; retrieval mechanics live in skills."""
from collections import Counter
from pathlib import PurePosixPath

GENERATED = frozenset({'benchmark-results', 'benchmark_results', 'test-results',
                       'test_results', 'playwright-report', 'coverage'})
CONFIG_EXTENSIONS = {'.json', '.yaml', '.yml', '.toml', '.ini', '.cfg'}


def source_role(path):
    parts = [p.casefold() for p in PurePosixPath(path).parts]
    name, suffix = parts[-1], PurePosixPath(path).suffix.casefold()
    if any(p in GENERATED for p in parts[:-1]):
        return 'generated_artifact'
    if path.startswith('knowledge/') or suffix in {'.md', '.rst', '.txt'}:
        return 'documentation'
    if any(p in {'test', 'tests', '__tests__', 'fixtures', '__fixtures__'} for p in parts[:-1]) or any(
            token in name for token in ('.test.', '.spec.', '_test.')) or name.startswith('test_'):
        return 'test_source'
    if any(p in {'example', 'examples', 'samples', 'tutorials'} for p in parts[:-1]):
        return 'example'
    if suffix in CONFIG_EXTENSIONS:
        return 'operational_configuration'
    return 'production_source'


def in_scope(path, scope):
    return path == scope or path.startswith(scope.rstrip('/') + '/')


def evidence_paths(rule, sources):
    scope = rule.get('scope', '')
    kind = rule.get('requirement_kind', 'behavior')
    scoped = bool(scope and scope != 'product')
    eligible = []
    for path in sources:
        if scoped and not in_scope(path, scope):
            continue
        role = source_role(path)
        suffix = PurePosixPath(path).suffix.casefold()
        workflow = suffix in {'.yml', '.yaml'} and PurePosixPath(path).parts[-3:-1] == ('.github', 'workflows')
        if (role == 'production_source'
                or (role == 'operational_configuration' and (kind == 'configuration' or (workflow and kind == 'behavior')))
                or (scoped and role == 'example' and (kind == 'configuration' or suffix not in CONFIG_EXTENSIONS))):
            eligible.append(path)
    return eligible


def project_map(sources, analysis):
    roots = Counter(p.split('/')[0] for p in sources)
    return {'roles': dict(Counter(source_role(p) for p in sources)),
            'roots': dict(roots.most_common(32)), 'total_roots': len(roots), 'roots_truncated': len(roots) > 32,
            'syntax_coverage': analysis['coverage'],
            'limitations': analysis['limitations'],
            'qualification': 'source_structure_only; not_behavioral_proof'}
