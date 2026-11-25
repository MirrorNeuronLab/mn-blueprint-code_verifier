"""Prepare a Software verifier suite input folder from two local Git commits."""
import argparse
from io import BytesIO
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / 'payloads'))

from domain.ci_evidence import junit_receipt, validate_commit
from domain.git_comparison import BUNDLE_NAME, BUNDLE_SCHEMA, source_digest
from domain.source_files import (MAX_BYTES, MAX_FILES, MAX_FILE_BYTES, excluded_directory,
                                 file_exclusion, relative_path, source_text)


def git(repo, *arguments, data=None):
    env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    env.update(GIT_NO_LAZY_FETCH='1', GIT_ALLOW_PROTOCOL='', GIT_OPTIONAL_LOCKS='0')
    try:
        result = subprocess.run(['git', '--no-pager', '--no-replace-objects', '--literal-pathspecs',
                                 '-C', str(repo), *arguments],
                                input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
                                timeout=60, check=True)
    except (OSError, subprocess.SubprocessError) as error:
        raise ValueError(f'Git could not read {arguments[0]} from the local repository. Check that both commits and their objects are available.') from error
    return result.stdout


def revision_sources(repo, commit, includes, extensions, staging_excluded):
    entries = git(repo, 'ls-tree', '-rlz', '--full-tree', commit, '--', *includes).split(b'\0')[:-1]
    if len(entries) > 30_000:
        raise ValueError('The Git tree exceeds the 30,000 entry scan limit.')
    selected, total = [], 0
    for entry in entries:
        try:
            metadata, name = entry.split(b'\t', 1)
            path = PurePosixPath(relative_path(name.decode('utf-8')))
        except ValueError:
            continue
        relative = path.as_posix()
        if includes and not any(relative == include or relative.startswith(include + '/') for include in includes):
            continue
        mode, kind, oid, size = metadata.split()
        if kind != b'blob' or mode not in {b'100644', b'100755'}:
            continue
        if any(excluded_directory(parent) or parent.name in staging_excluded
               for parent in path.parents if parent.parts) or file_exclusion(path, extensions):
            continue
        size = int(size)
        if size > MAX_FILE_BYTES:
            continue
        if len(selected) >= MAX_FILES or total + size > MAX_BYTES:
            raise ValueError('The snapshot exceeds the review budget. Add --include for the relevant source and spec paths.')
        selected.append((relative, oid, size))
        total += size

    sources = {}
    if selected:
        blobs = BytesIO(git(repo, 'cat-file', '--batch', data=b''.join(oid + b'\n' for _, oid, _ in selected)))
        for path, oid, size in selected:
            if blobs.readline().split() != [oid, b'blob', str(size).encode()]:
                raise ValueError('A selected Git object is missing or has unexpected contents.')
            blob = blobs.read(size)
            if len(blob) != size or blobs.read(1) != b'\n':
                raise ValueError('A selected Git blob is incomplete.')
            try:
                sources[path] = source_text(blob)
            except ValueError:
                continue
    return sources, len(entries) - len(sources)


def prepare(repo, base, head, output, includes=(), *, junit=None, rule_map=None, ci_commit=None):
    includes = list(dict.fromkeys(relative_path(path) for path in includes))
    if len(includes) > 100:
        raise ValueError('Choose at most 100 --include paths.')
    if any(value is not None for value in (junit, rule_map, ci_commit)) and not all((junit, rule_map, ci_commit)):
        raise ValueError('Use --junit, --rule-map and --ci-commit together.')
    repo, output = Path(repo).resolve(strict=True), Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise ValueError('Choose a new output folder for the prepared comparison.')
    config = json.loads((PACKAGE / 'config/default.json').read_text(encoding='utf-8'))['local_inputs']['folders'][0]
    extensions, excluded = set(config['allowed_extensions']), set(config['excluded_directories'])
    base_sha, head_sha = [validate_commit(git(repo, 'rev-parse', '--verify', '--end-of-options',
                                              f'{ref}^{{commit}}').decode('ascii').strip())
                          for ref in (base, head)]
    comparison, snapshots = {'schema_version': BUNDLE_SCHEMA, 'includes': includes}, {}
    if junit:
        if validate_commit(ci_commit) != head_sha:
            raise ValueError('The CI result must be from the exact proposed Git commit.')
        comparison['ci'] = junit_receipt(junit, rule_map, ci_commit)
    for side, commit in (('base', base_sha), ('head', head_sha)):
        sources, omitted = revision_sources(repo, commit, includes, extensions, excluded)
        snapshots[side] = sources
        comparison[side] = {'commit': commit, 'sha256': source_digest(sources), 'omitted': omitted}
    for include in includes:
        if not any(path == include or path.startswith(include + '/')
                   for sources in snapshots.values() for path in sources):
            raise ValueError(f'No reviewable files match the included path {include}.')
    if not snapshots['head']:
        raise ValueError('The proposed commit has no reviewable files within the selected paths.')
    encoded = json.dumps(comparison, indent=2, ensure_ascii=False).encode() + b'\n'
    if len(encoded) > 512_000:
        raise ValueError('The comparison descriptor exceeds its size limit.')

    output.mkdir(mode=0o700)
    descriptor = output / BUNDLE_NAME
    descriptor.write_text('{}\n', encoding='utf-8')
    for side, sources in snapshots.items():
        (output / side).mkdir()
        for path, text in sources.items():
            target = output / side / path
            target.parent.mkdir(parents=True, exist_ok=True)
            # Exclusive creation also rejects path collisions on case-insensitive disks.
            with target.open('xb') as stream:
                stream.write(text.encode())
    pending = output / (BUNDLE_NAME + '.tmp')
    with pending.open('xb') as stream:
        stream.write(encoded)
    pending.replace(descriptor)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path.cwd(), help='local Git checkout')
    parser.add_argument('--base', required=True, help='base commit or local ref')
    parser.add_argument('--head', default='HEAD', help='proposed commit or local ref')
    parser.add_argument('--output', type=Path, required=True, help='new comparison folder')
    parser.add_argument('--include', action='append', default=[], metavar='PATH', help='optional repository-relative path')
    parser.add_argument('--junit', type=Path, help='UTF-8 JUnit XML output from CI')
    parser.add_argument('--rule-map', type=Path, help='JSON mapping rule IDs to JUnit test names')
    parser.add_argument('--ci-commit', help='full commit SHA recorded by the CI run')
    args = parser.parse_args()
    try:
        output = prepare(args.repo, args.base, args.head, args.output, args.include, junit=args.junit,
                         rule_map=args.rule_map, ci_commit=args.ci_commit)
    except (OSError, ValueError) as error:
        parser.exit(1, f'Could not prepare the comparison. {error}\n')
    print(f'Select this folder in Software verifier suite: {output}')


if __name__ == '__main__':
    main()
