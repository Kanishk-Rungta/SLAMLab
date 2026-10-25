"""Lightweight tracked-source, Markdown-link, configuration and provenance checks."""
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET

import yaml

ROOT = Path(__file__).resolve().parents[2]
REQUIRED = ('README.md', 'LICENSE', 'THIRD_PARTY_NOTICES.md', 'CITATION.cff',
            'CONTRIBUTING.md', 'CODE_OF_CONDUCT.md', 'SECURITY.md', 'CHANGELOG.md',
            'docs/implementation-inventory.md', 'docs/source-provenance.md',
            'docs/import-manifest.json', 'simulations/webots/README.md')
SECRET_PATTERNS = [r'gh[pousr]_[A-Za-z0-9]{30,}', r'github_pat_[A-Za-z0-9_]{40,}',
                   r'AKIA[0-9A-Z]{16}', r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----']


def repository_files():
    result = subprocess.check_output(['git', '-c', 'safe.directory=' + ROOT.as_posix(),
        '-c', 'core.excludesfile=NUL' if sys.platform == 'win32' else 'core.excludesfile=/dev/null',
        '-C', str(ROOT), 'ls-files', '--cached', '--others', '--exclude-standard', '-z'])
    return sorted(set(Path(name.decode('utf-8')) for name in result.split(b'\0') if name))


def normalized_hash(path):
    blob = path.read_bytes()
    if path.suffix.lower() not in ('.png', '.npz'):
        blob = blob.replace(b'\r\n', b'\n')
    return hashlib.sha256(blob).hexdigest()


def headings(path):
    text = re.sub(r'```.*?```', '', path.read_text(encoding='utf-8-sig'), flags=re.S)
    result, counts = set(), {}
    for heading in re.findall(r'^#{1,6}\s+(.+?)\s*#*$', text, re.M):
        slug = re.sub(r'[^\w\- ]', '', heading.lower()).replace(' ', '-')
        count = counts.get(slug, 0)
        counts[slug] = count + 1
        result.add(slug + ('-' + str(count) if count else ''))
    return result


def main():
    errors, links = [], 0
    files = repository_files()
    for name in REQUIRED:
        if not (ROOT / name).is_file():
            errors.append('Missing required file: ' + name)
    for relative in files:
        path = ROOT / relative
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(ROOT):
            errors.append('Missing or unsafe path: ' + relative.as_posix())
            continue
        if '.git' in relative.parts or any(part in ('Bstem', 'node_modules', '__pycache__', 'runs', 'backup_runs') for part in relative.parts):
            errors.append('Unexpected generated/hardware/nested-repository file: ' + relative.as_posix())
        if path.stat().st_size > 5 * 1024 * 1024:
            errors.append('Tracked file exceeds 5 MiB: ' + relative.as_posix())
        if path.suffix.lower() in ('.png', '.npz'):
            continue
        try:
            text = path.read_text(encoding='utf-8-sig')
        except UnicodeDecodeError:
            errors.append('Unexpected nontext file: ' + relative.as_posix())
            continue
        if any(re.search(pattern, text) for pattern in SECRET_PATTERNS):
            errors.append('Possible credential/private key: ' + relative.as_posix())
        try:
            if path.suffix == '.py':
                ast.parse(text, filename=relative.as_posix())
            elif path.suffix == '.json':
                json.loads(text)
            elif path.suffix in ('.xml',) or path.name == 'package.xml':
                ET.fromstring(text)
            elif path.suffix in ('.yaml', '.yml') or path.name == 'CITATION.cff':
                # OpenCV uses a nonstandard directive and matrix tag in calibration files.
                loader = type('CalibrationSafeLoader', (yaml.SafeLoader,), {})
                loader.add_constructor('tag:yaml.org,2002:opencv-matrix',
                    lambda reader, node: reader.construct_mapping(node, deep=True))
                yaml.load(text.replace('%YAML:1.0', ''), Loader=loader)
        except (SyntaxError, ValueError, ET.ParseError, yaml.YAMLError) as error:
            errors.append('Invalid syntax/configuration %s: %s' % (relative.as_posix(), error))
        if path.suffix != '.md':
            continue
        if not re.search(r'^#{1,6}\s+\S', text, re.M):
            errors.append('Markdown file has no title: ' + relative.as_posix())
        stripped = re.sub(r'```.*?```', '', text, flags=re.S)
        for raw in re.findall(r'\[[^\]]*\]\(([^)]+)\)', stripped):
            raw = raw.strip().strip('<>')
            parsed = urlsplit(raw)
            if parsed.scheme or parsed.netloc:
                if parsed.scheme not in ('https', 'http', 'mailto'):
                    errors.append('Unsupported link scheme: ' + raw)
                continue
            target = (path.parent / unquote(parsed.path)).resolve() if parsed.path else path
            links += 1
            if not target.is_relative_to(ROOT) or not target.exists():
                errors.append('Broken internal link in %s: %s' % (relative.as_posix(), raw))
            elif parsed.fragment and target.suffix == '.md' and unquote(parsed.fragment) not in headings(target):
                errors.append('Broken heading anchor in %s: %s' % (relative.as_posix(), raw))
    manifest = json.loads((ROOT / 'docs/import-manifest.json').read_text(encoding='utf-8'))
    seen = set()
    for record in manifest['files']:
        name = record['destination']
        path = ROOT / name
        if name in seen or not path.resolve().is_relative_to(ROOT):
            errors.append('Duplicate/unsafe provenance destination: ' + name)
        seen.add(name)
        if not path.is_file():
            errors.append('Imported file missing: ' + name)
        elif record.get('repository_sha256') and normalized_hash(path) != record['repository_sha256']:
            errors.append('Imported file changed without provenance update: ' + name)
    if errors:
        print('\n'.join(errors))
        raise SystemExit(1)
    print('Repository checks passed: %d files, %d internal links, %d provenance records.' % (len(files), links, len(seen)))
    print('Credential scan uses high-confidence patterns; external URLs and native runtime are not validated by this check.')


if __name__ == '__main__':
    main()
