"""Build an allowlisted source + prebuilt frontend ZIP, never copy local runtime data."""
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode('utf-8').split('\0')
    output = ROOT / 'dist'
    output.mkdir(exist_ok=True)
    archive = output / 'MathRAG-local-deploy.zip'
    files = []
    for name in tracked:
        path = Path(name)
        if not name or not (ROOT / path).is_file():
            continue
        if not (path.parts[0] in ('backend', 'frontend', 'deploy') or name in ('compose.yaml', 'README.md', '.dockerignore', '.gitignore', 'scripts/formula-worker.py')):
            continue
        if '.env' in path.name or path.suffix in ('.db', '.sqlite3', '.log') or any(part.startswith('.') for part in path.parts):
            if name not in ('deploy/deploy.env.example', '.dockerignore', '.gitignore'):
                continue
        if path.parts[0] == 'backend' and path.parts[1] not in ('app', 'requirements.txt', 'requirements-formula.txt'):
            continue
        if path.parts[0] == 'frontend' and path.parts[1] not in ('src', 'public', 'index.html', 'package.json', 'package-lock.json', 'vite.config.js'):
            continue
        files.append(path)
    built = ROOT / 'frontend/dist'
    if not (built / 'index.html').is_file():
        raise ValueError('Build frontend first')
    files.extend(path.relative_to(ROOT) for path in built.rglob('*') if path.is_file())
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(set(files)):
            bundle.write(ROOT / path, 'MathRAG/' + path.as_posix())
    manifest = {'file': archive.name, 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'files': len(set(files)),
                'includes_private_database': False, 'includes_keys': False, 'includes_model_weights': False}
    (output / 'MathRAG-local-deploy.manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps(manifest))


if __name__ == '__main__':
    main()
