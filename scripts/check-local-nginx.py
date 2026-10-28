"""Exercise real local Nginx, with a separate no-model SSE upstream fixture.

Production checks use port 8086. The disposable fixture instance uses 8087;
it never connects to the real backend or touches its database/budget.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request


def main():
    local = Path(os.environ['LOCALAPPDATA'])
    runtime = local / 'MathRAG/runtime'
    binary = runtime / 'nginx-1.31.8/nginx.exe'
    output = local / 'Temp/mathrag-c-integration-20261028/nginx-restart-20261028'
    output.mkdir(exist_ok=True)
    production = runtime / 'mathrag-local'
    checks = []
    for route, expected in [('/', 'text/html'), ('/nested/test/page', 'text/html'),
                            ('/api/health', 'application/json'), ('/openapi.json', 'application/json')]:
        with urllib.request.urlopen('http://127.0.0.1:8086' + route, timeout=5) as response:
            assert response.status == 200 and expected in response.headers['Content-Type']
            checks.append({'path': route, 'status': response.status, 'content_type': response.headers['Content-Type']})
    try:
        urllib.request.urlopen('http://127.0.0.1:8086/api/does-not-exist', timeout=5)
        raise AssertionError('Expected API 404')
    except urllib.error.HTTPError as error:
        assert error.code == 404 and 'application/json' in error.headers['Content-Type']

    class Fixture(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def log_message(self, *args):
            pass

        def do_POST(self):
            self.rfile.read(int(self.headers.get('Content-Length', 0)))
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Connection', 'close')
            self.end_headers()
            for event in ['meta', 'delta', 'done']:
                if event != 'meta':
                    time.sleep(0.8)
                self.wfile.write(('event: ' + event + '\ndata: {}\n\n').encode())
                self.wfile.flush()
            self.close_connection = True

    with socket.socket() as probe:
        if probe.connect_ex(('127.0.0.1', 8087)) == 0:
            raise ValueError('Fixture port 8087 occupied; nothing stopped')
    fixture = ThreadingHTTPServer(('127.0.0.1', 0), Fixture)
    threading.Thread(target=fixture.serve_forever, daemon=True).start()
    instance = runtime / 'mathrag-sse-validation'
    for name in ['logs', 'conf', 'temp']:
        (instance / name).mkdir(parents=True, exist_ok=True)
    config = (production / 'conf/mathrag.conf').read_text(encoding='utf-8')
    config = config.replace('listen 127.0.0.1:8086;', 'listen 127.0.0.1:8087;')
    config = config.replace('http://127.0.0.1:8002;', f'http://127.0.0.1:{fixture.server_port};')
    (instance / 'conf/mathrag.conf').write_text(config, encoding='utf-8')
    command = [str(binary), '-p', instance.as_posix() + '/', '-c', 'conf/mathrag.conf']
    subprocess.run(command + ['-t'], check=True, capture_output=True)
    process = subprocess.Popen(command, cwd=instance, creationflags=subprocess.CREATE_NO_WINDOW)
    started = False
    try:
        for _ in range(50):
            with socket.socket() as probe:
                if probe.connect_ex(('127.0.0.1', 8087)) == 0:
                    started = True
                    break
            time.sleep(0.1)
        assert started, 'Fixture Nginx failed to listen'
        request = urllib.request.Request('http://127.0.0.1:8087/api/chat/stream?privacy_canary=DO_NOT_LOG_QUERY',
                                         data=b'{}', headers={'Content-Type': 'application/json', 'Cookie': 'DO_NOT_LOG_COOKIE'})
        times = []
        begin = time.monotonic()
        with urllib.request.urlopen(request, timeout=8) as response:
            assert response.headers.get('Content-Encoding') is None
            assert response.headers.get('X-Accel-Buffering') == 'no'
            for raw in response:
                if raw.startswith(b'event:'):
                    times.append({'event': raw.decode().strip(), 'seconds': round(time.monotonic() - begin, 3)})
        assert len(times) == 3 and times[0]['seconds'] < 0.5
        assert times[1]['seconds'] - times[0]['seconds'] > 0.6
        assert times[2]['seconds'] - times[1]['seconds'] > 0.6
        # Headers alone must trigger the configured cap, without allocating/sending 55MB.
        request = urllib.request.Request('http://127.0.0.1:8087/api/upload-limit-check', data=b'',
                                         headers={'Content-Length': str(55 * 1024 * 1024 + 1)})
        try:
            urllib.request.urlopen(request, timeout=5)
            raise AssertionError('Expected upload limit rejection')
        except urllib.error.HTTPError as error:
            assert error.code == 413
    finally:
        if started:
            subprocess.run(command + ['-s', 'quit'], check=True, capture_output=True)
        else:
            process.terminate()
        process.wait(timeout=10)
        fixture.shutdown()
        fixture.server_close()
    access = (instance / 'logs/mathrag-access.log').read_text(encoding='utf-8')
    assert 'DO_NOT_LOG_QUERY' not in access and 'DO_NOT_LOG_COOKIE' not in access
    result = {'production_routes': checks, 'api_404_is_json': True, 'real_network_sse_fixture': times,
              'upload_limit_413': True, 'access_log_omits_query_and_cookie': True,
              'fixture_instance_stopped': True, 'paid_model_calls': 0}
    (output / 'nginx-network-result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
