"""Capture authorized local source and knowledge; never import reviewed programs."""
import os
from pathlib import Path

from mn_code_search_skill import TextSearchIndex
from mn_static_code_analysis_skill import SUPPORTED_EXTENSIONS, analyze_sources
from mn_sdk.blueprint.hooks import report_activity
from mn_sdk.blueprint.inputs import capture_declared_inputs

from .artifacts import read
from .configuration import BLUEPRINT_ID, settings
from .git_comparison import changed_files, load_bundle
from .source_files import (DOCUMENT_EXTENSIONS, MAX_BYTES, MAX_FILES, MAX_FILE_BYTES,
                           CredentialMaterial, excluded_directory, file_exclusion, source_text)
from .source_policy import source_role

TEXT_EXTENSIONS = SUPPORTED_EXTENSIONS | {'.md', '.txt', '.rst', '.json', '.yaml', '.yml',
                                        '.toml', '.ini', '.cfg', '.html', '.css', '.sql', '.sh'}


def capture_folder(root, *, max_files=MAX_FILES, max_bytes=MAX_BYTES):
    root = Path(root).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError('Choose a repository checkout or source folder.')
    sources, omitted, total, scanned = {}, [], 0, 0
    for directory, folders, files in os.walk(root, followlinks=False):
        selected = []
        for name in sorted(folders):
            path = Path(directory) / name
            relative = path.relative_to(root)
            if excluded_directory(relative) or path.is_symlink():
                omitted.append({'path': relative.as_posix(), 'reason': 'excluded_directory_or_symlink'})
            else:
                selected.append(name)
        folders[:] = selected
        scanned += len(files) + len(folders)
        if scanned > 30_000:
            raise ValueError('Source scan exceeds 30,000 entries; select a smaller folder.')
        for name in sorted(files):
            path = Path(directory) / name
            relative = path.relative_to(root)
            reason = file_exclusion(relative, TEXT_EXTENSIONS)
            if reason or path.is_symlink() or not path.is_file():
                omitted.append({'path': relative.as_posix(), 'reason': reason or 'excluded_format_secret_name_or_symlink'})
                continue
            size = path.stat().st_size
            if size > MAX_FILE_BYTES:
                omitted.append({'path': relative.as_posix(), 'reason': 'file_exceeds_500KB'})
                continue
            if len(sources) >= max_files or total + size > max_bytes:
                raise ValueError('Source capture budget exceeded; select a smaller folder.')
            data = path.read_bytes()
            if len(data) > MAX_FILE_BYTES or total + len(data) > max_bytes:
                raise ValueError('Source grew beyond the capture budget.')
            try:
                value = source_text(data)
            except CredentialMaterial as error:
                omitted.append({'path': relative.as_posix(), 'line': error.line, 'reason': 'credential_material_withheld'})
                continue
            except ValueError:
                omitted.append({'path': relative.as_posix(), 'reason': 'not_utf8_text'})
                continue
            sources[relative.as_posix()] = value
            total += len(data)
    return sources, omitted


def role(path):
    return source_role(path)


def commit_snapshot(block, sources, prefix=''):
    analysis = analyze_sources({p: v for p, v in sources.items() if Path(p).suffix in SUPPORTED_EXTENSIONS})
    block.store.path(prefix + 'source').mkdir(parents=True, exist_ok=True)
    for path, content in sources.items():
        block.check()
        block.store.commit_bytes(prefix + 'source/' + path, content.encode('utf-8'), kind='captured_source')
    return block.store.commit(prefix + 'static-analysis.json', analysis, kind='static_analysis')


def capture(block, inputs):
    report_activity("Capturing source and documentation", owner_blueprint=BLUEPRINT_ID,
                    step_id=block.step_id, run_dir=block.store.run_dir)
    settings(block)
    if block.store.path("capture.json").is_file():
        value = read(block, "capture.json")
    else:
        value = capture_sources(block, inputs)
        if 'baseline_sources' in value:
            baseline = block.store.commit('baseline/capture.json', value.pop('baseline_sources'), kind='baseline_capture')
            value['baseline_capture'] = baseline.to_dict()
    sources = value["sources"]
    analysis_ref = commit_snapshot(block, sources)
    if 'baseline_capture' in value:
        commit_snapshot(block, block.store.read(value['baseline_capture']), 'baseline/')
    capture_ref = block.store.commit("capture.json", value, kind="source_capture")
    return {"snapshot_id": value["snapshot_id"], "files": len(sources),
            "capture": capture_ref.to_dict(), "static_analysis": analysis_ref.to_dict()}


def capture_sources(block, inputs):
    inputs = capture_declared_inputs(block, inputs, runtime_file=__file__)
    folder = inputs.get('input_folder')
    if not folder:
        raise ValueError('Choose a repository checkout or source folder.')
    root = Path(folder).resolve(strict=True)
    run_root = block.store.run_dir
    if run_root == root or run_root.is_relative_to(root):
        raise ValueError('Run outputs must be outside the inspected source folder.')
    bundle = load_bundle(root, capture_folder)
    comparison, baseline_sources = None, {}
    if bundle is None:
        sources, omitted = capture_folder(root)
    else:
        comparison, snapshots = bundle
        sources, baseline_sources = snapshots['head'], snapshots['base']
        omitted = []
    repository_prefix = ''
    if any(p.startswith('knowledge/') for p in sources.keys() | baseline_sources.keys()):
        # Keep repository paths separate from supervisor-owned blueprint knowledge.
        repository_prefix = 'repository/'
        sources = {repository_prefix + p: v for p, v in sources.items()}
        baseline_sources = {repository_prefix + p: v for p, v in baseline_sources.items()}
        omitted = [{**item, 'path': repository_prefix + item['path']} for item in omitted]
    if comparison is not None:
        comparison['changes'] = changed_files(baseline_sources, sources)
        comparison['base']['snapshot_id'] = TextSearchIndex(baseline_sources).snapshot_id
    knowledge = block.job_directory / 'knowledge' / 'rules'
    custom = {}
    if knowledge.is_symlink() or knowledge.parent.is_symlink():
        raise ValueError('Job knowledge must not be a symlink.')
    if knowledge.is_dir():
        custom, skipped = capture_folder(knowledge, max_files=100, max_bytes=500_000)
        if skipped:
            raise ValueError('Custom rules must be bounded UTF-8 Markdown files without symlinks.')
        if any(Path(p).suffix.lower() != '.md' for p in custom):
            raise ValueError('Custom rules must be Markdown files.')
    sources.update({'knowledge/rules/' + p: v for p, v in custom.items()})
    index = TextSearchIndex(sources)
    docs = [p for p in sources if Path(p).suffix.casefold() in DOCUMENT_EXTENSIONS and not p.startswith('knowledge/')]
    value = {'schema_version': 'mn.software_rules.capture.v1', 'sources': sources,
             'snapshot_id': index.snapshot_id, 'documents': docs,
             'custom_documents': ['knowledge/rules/' + p for p in custom], 'omitted': omitted,
             'source_execution': False, 'repository_prefix': repository_prefix}
    if comparison is not None:
        value.update(comparison=comparison, baseline_sources=baseline_sources)
    return value
