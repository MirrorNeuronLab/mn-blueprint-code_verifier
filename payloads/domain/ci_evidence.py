"""Bounded JUnit observations attached to approved rule IDs and a Git commit."""
from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path
import re
from xml.etree import ElementTree

COMMIT = re.compile(r'(?:[a-f0-9]{40}|[a-f0-9]{64})\Z')
DIGEST = re.compile(r'[a-f0-9]{64}\Z')
RULE_ID = re.compile(r'[A-Za-z][A-Za-z0-9_-]{0,63}\Z')
RESULTS = {'passed', 'failed', 'skipped', 'missing', 'mixed'}
MAX_CHECKS = 500


def read_bounded(path, limit):
    path = Path(path)
    if not path.is_file():
        raise ValueError(f'{path.name} must be a regular file.')
    with path.open('rb') as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f'{path.name} exceeds its size limit.')
    return data


def validate_commit(value):
    if not isinstance(value, str) or not COMMIT.fullmatch(value):
        raise ValueError('Provide a full Git commit SHA.')
    return value


def valid_label(value, maximum):
    return isinstance(value, str) and 0 < len(value) <= maximum and value.isprintable() and bool(value.strip())


def validate_ci(receipt, head):
    if not isinstance(receipt, dict) or set(receipt) != {'commit', 'file', 'sha256', 'checks'}:
        raise ValueError('Invalid CI evidence receipt.')
    if validate_commit(receipt['commit']) != head:
        raise ValueError('The CI result must be from the exact proposed Git commit.')
    if (not valid_label(receipt['file'], 240) or not isinstance(receipt['sha256'], str)
            or not DIGEST.fullmatch(receipt['sha256'])):
        raise ValueError('Invalid CI evidence identity.')
    checks = receipt['checks']
    if not isinstance(checks, list) or not 1 <= len(checks) <= MAX_CHECKS:
        raise ValueError(f'Map between 1 and {MAX_CHECKS} CI checks to approved rules.')
    seen = set()
    for check in checks:
        if (not isinstance(check, dict) or set(check) != {'rule_id', 'test', 'status'}
                or not isinstance(check['rule_id'], str) or not RULE_ID.fullmatch(check['rule_id'])
                or not valid_label(check['test'], 360) or not isinstance(check['status'], str)
                or check['status'] not in RESULTS):
            raise ValueError('Each CI check needs a valid rule ID, test name and status.')
        key = (check['rule_id'], check['test'])
        if key in seen:
            raise ValueError('A CI test can only appear once per rule.')
        seen.add(key)
    return receipt


def junit_receipt(junit_path, rule_map_path, commit):
    validate_commit(commit)
    mapping = json.loads(read_bounded(rule_map_path, 256_000))
    if not isinstance(mapping, dict) or any(not isinstance(names, list) for names in mapping.values()):
        raise ValueError('The CI rule map must map rule IDs to lists of JUnit test names.')
    checks = [{'rule_id': rule_id, 'test': name, 'status': 'missing'}
              for rule_id, names in mapping.items() for name in names]
    data = read_bounded(junit_path, 8_000_000)
    receipt = validate_ci({'commit': commit, 'file': Path(junit_path).name,
                           'sha256': sha256(data).hexdigest(), 'checks': checks}, commit)
    # Decode explicitly before checking the XML declaration. JUnit logs and test
    # messages are private and are never copied into the comparison.
    xml = data.decode('utf-8-sig')
    if re.search(r'<!\s*(?:DOCTYPE|ENTITY)\b', xml, re.IGNORECASE):
        raise ValueError('Use a UTF-8 JUnit report without DTDs or entity declarations.')
    try:
        report = ElementTree.fromstring(xml)
    except ElementTree.ParseError as error:
        raise ValueError('The CI result is not valid JUnit XML.') from error
    if report.tag not in {'testsuite', 'testsuites'}:
        raise ValueError('The CI result must be a JUnit testsuite or testsuites document.')
    wanted = {check['test'] for check in checks}
    outcomes = defaultdict(set)
    for case in report.iter('testcase'):
        name, classname = case.get('name', ''), case.get('classname', '')
        identifier = f'{classname}::{name}' if classname else name
        if identifier not in wanted:
            continue
        tags = {child.tag for child in case}
        if tags & {'failure', 'error'}:
            outcomes[identifier].add('failed')
        elif 'skipped' in tags:
            outcomes[identifier].add('skipped')
        else:
            outcomes[identifier].add('passed')
        if tags & {'flakyFailure', 'flakyError', 'rerunFailure', 'rerunError'}:
            outcomes[identifier].add('failed')
            outcomes[identifier].add('passed')
    for check in checks:
        values = outcomes[check['test']]
        if values:
            check['status'] = next(iter(values)) if len(values) == 1 else 'mixed'
    return receipt
