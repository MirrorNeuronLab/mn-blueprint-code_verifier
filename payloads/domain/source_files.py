"""Bounded file selection shared by local capture and Git preparation."""
from pathlib import PurePosixPath
import re

MAX_FILES = 2_000
MAX_BYTES = 10_000_000
MAX_FILE_BYTES = 500_000
EXCLUDED_DIRECTORIES = {'.git', '.svn', 'node_modules', 'vendor', 'dist', 'build', '.venv',
                        'venv', '__pycache__', '.next', 'coverage', '.idea', '.vscode'}
SECRET_PREFIXES = ('credentials', 'secrets', 'id_rsa', 'id_ed25519')
DOCUMENT_EXTENSIONS = {'.md', '.rst', '.txt'}


def relative_path(value):
    if not isinstance(value, str) or not value or len(value) > 1024 or re.search(r'[\\:\x00-\x1f\x7f]', value):
        raise ValueError('Use a relative path with forward slashes inside the source folder.')
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or '..' in path.parts or path.as_posix() != value:
        raise ValueError('Use a relative path with forward slashes inside the source folder.')
    return value


def excluded_directory(path):
    return path.name.casefold() in EXCLUDED_DIRECTORIES or (path.name.startswith('.') and path.as_posix() != '.github')


def file_exclusion(path, extensions):
    if path.parts[0] == '.github' and (path.parent.as_posix() != '.github/workflows'
                                       or path.suffix.casefold() not in {'.yml', '.yaml'}):
        return 'outside_ci_capture_allowlist'
    if (path.name.startswith('.') or path.suffix.casefold() not in extensions
            or path.name.casefold().startswith(SECRET_PREFIXES)):
        return 'excluded_format_secret_name_or_symlink'
    return None


def source_text(data):
    text = data.decode('utf-8')
    if '\0' in text:
        raise ValueError('Binary source.')
    return text
