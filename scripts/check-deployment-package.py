"""Extract and smoke-test the ZIP with a fresh DB, existing Python deps, and no model calls."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import zipfile

import httpx


def main():
    root = Path(__file__).resolve().parents[1]
    folder = Path(tempfile.mkdtemp(prefix='mathrag-package-check-'))
    with zipfile.ZipFile(root / 'dist/MathRAG-local-deploy.zip') as archive:
        names = archive.namelist()
        assert all(name.startswith('MathRAG/') and '..' not in Path(name).parts for name in names)
        assert not any(name.endswith(('.db', '.sqlite3', '.log')) or name.endswith('/deploy.env') for name in names)
        archive.extractall(folder)
    project = folder / 'MathRAG'
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0)); port = probe.getsockname()[1]
    base = f'http://127.0.0.1:{port}'
    env = dict(os.environ)
    for key in ['DEEPSEEK_API_KEY', 'DATABASE_URL', 'UPLOAD_DIR', 'CHROMA_DIR', 'EMBED_LOCAL_MODEL', 'RERANK_LOCAL_MODEL']:
        env.pop(key, None)
    with (folder / 'startup.log').open('wb') as log:
        process = subprocess.Popen([sys.executable, '-X', 'utf8', str(project / 'deploy/run.py'), '--demo', '--port', str(port)],
                                   cwd=project, env=env, stdout=log, stderr=subprocess.STDOUT)
    try:
        with httpx.Client(base_url=base, timeout=10, headers={'Origin': base}) as client:
            for _ in range(60):
                if process.poll() is not None:
                    raise ValueError('Package exited: ' + str(folder / 'startup.log'))
                try:
                    if client.get('/api/health').status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                time.sleep(.5)
            else:
                raise TimeoutError('Package startup timeout')
            assert client.get('/').status_code == 200
            assert client.get('/nested/page').status_code == 200
            assert client.get('/api/missing').status_code == 404
            index = client.get('/').text
            import re
            for asset in re.findall(r'(?:src|href)="(/assets/[^\"]+)"', index):
                assert client.get(asset).status_code == 200
            public = client.get('/api/public/kbs').json()['data']
            assert len(public) == 1
            session = client.post('/api/auth/register', json={'username': 'package_test', 'password': 'Package-test-2026'}).json()['data']
            csrf = {'X-CSRF-Token': session['csrf_token']}
            response = client.post('/api/chat/stream', headers=csrf,
                                   json={'kb_ids': [public[0]['id']], 'question': '解方程 x²−5x+6=0', 'stream': True})
            assert response.status_code == 200 and 'event: done' in response.text
            kb = client.post('/api/kbs', headers=csrf, json={'name': '我的资料'}).json()['data']['id']
            upload = client.post('/api/docs/upload', headers=csrf, data={'kb_id': kb},
                                 files={'file': ('sample.txt', ('导数用于判断函数的单调性。' * 10).encode(), 'text/plain')})
            assert upload.status_code == 200
            for _ in range(50):
                user_docs = client.get('/api/docs', params={'kb_id': kb}).json()['data']
                if user_docs and user_docs[0]['status'] not in ('pending', 'parsing', 'embedding'):
                    break
                time.sleep(.1)
            assert len(user_docs) == 1 and user_docs[0]['status'] == 'ready'
        result = {'zip_files': len(names), 'isolated_data': str(project / 'runtime/data'),
                  'static_assets_spa_api_register_upload_sse': True, 'private_data_or_key_included': False,
                  'paid_model_calls': 0, 'docker_runtime_tested': False, 'existing_python_dependencies_reused': True}
        (root / 'dist/package-check.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(json.dumps(result))
    finally:
        process.terminate(); process.wait(timeout=15)


if __name__ == '__main__':
    main()
