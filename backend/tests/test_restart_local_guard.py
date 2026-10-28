import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location('restart_local', Path(__file__).resolve().parents[2] / 'scripts/restart-c-integration-local.py')
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


def connection(pid):
    return SimpleNamespace(pid=pid, status='LISTEN', laddr=SimpleNamespace(port=8002))


@pytest.mark.parametrize('connections', [[], [connection(None)], [connection(11), connection(12)]])
def test_ambiguous_listener_is_never_selected(monkeypatch, connections):
    monkeypatch.setattr(helper.psutil, 'net_connections', lambda **kw: connections)
    with pytest.raises(ValueError, match='exactly one known backend'):
        helper.current_backend()


@pytest.mark.parametrize('command,correct_cwd', [
    (['python', '-m', 'uvicorn', '--port', '8002'], True),
    (['python', 'scripts/start-c-integration.py', '--port', '8003'], True),
    (['python', 'scripts/start-c-integration.py', '--port', '8002'], False),
])
def test_unexpected_command_port_or_workspace_is_not_selected(monkeypatch, command, correct_cwd, tmp_path):
    process = SimpleNamespace(cmdline=lambda: command, cwd=lambda: str(helper.ROOT if correct_cwd else tmp_path))
    monkeypatch.setattr(helper.psutil, 'net_connections', lambda **kw: [connection(11)])
    monkeypatch.setattr(helper.psutil, 'Process', lambda pid: process)
    with pytest.raises(ValueError, match='unexpected process'):
        helper.current_backend()


def test_exact_controlled_service_is_selected_without_stopping_it(monkeypatch):
    process = SimpleNamespace(cmdline=lambda: ['python', 'scripts/start-c-integration.py', '--port', '8002'],
                              cwd=lambda: str(helper.ROOT))
    monkeypatch.setattr(helper.psutil, 'net_connections', lambda **kw: [connection(11)])
    monkeypatch.setattr(helper.psutil, 'Process', lambda pid: process)
    assert helper.current_backend() is process
