"""User-operated masked local key dialog for restarting the bounded integration service.

Never extracts a key from the old process, persists a key, or changes the spending ledger.
Cancel/close before submission leaves the running backend untouched.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request

import psutil

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ['LOCALAPPDATA']) / 'Temp/mathrag-c-integration-20261028'
OUTPUT = DATA / 'nginx-restart-20261028'
PYTHON = ROOT.parents[1] / '.venv/Scripts/python.exe'
LAUNCHER = ROOT / 'scripts/start-c-integration.py'


def current_backend():
    owners = {conn.pid for conn in psutil.net_connections(kind='tcp')
              if conn.status == 'LISTEN' and conn.laddr.port == 8002}
    if len(owners) != 1 or None in owners:
        raise ValueError('Expected exactly one known backend on port 8002')
    process = psutil.Process(owners.pop())
    command = process.cmdline()
    if (not any(Path(arg).name == 'start-c-integration.py' for arg in command)
            or '--port' not in command or command[command.index('--port') + 1] != '8002'
            or Path(process.cwd()).resolve() != ROOT):
        raise ValueError('Port 8002 belongs to an unexpected process; nothing stopped')
    return process


def status(stage, **details):
    OUTPUT.mkdir(exist_ok=True)
    target = OUTPUT / 'restart-status.json'
    temp = target.with_suffix('.tmp')
    temp.write_text(json.dumps({'stage': stage, **details}, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(target)


def restart(key):
    # Check the controlled launcher before stopping the existing service.
    spec = importlib.util.spec_from_file_location('controlled_launcher', LAUNCHER)
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
    os.environ['DEEPSEEK_API_KEY'] = key
    args = argparse.Namespace(data_dir=DATA, embedding_dir=ROOT.parent / 'b-final-models/bge-m3',
                              reranker_dir=ROOT.parent / 'b-final-models/bge-reranker-v2-m3')
    _, missing = launcher.prepare(args)
    if missing:
        raise ValueError('Controlled launcher preflight failed: ' + ', '.join(missing))
    if not (DATA / 'validation-source.json').is_file():
        raise ValueError('Integration data identity marker is missing')
    old = current_backend()
    budget_before = json.loads((DATA / 'budget.json').read_text(encoding='utf-8'))
    status('restarting', old_pid=old.pid, budget_before=budget_before)
    old.terminate()
    old.wait(timeout=20)
    with socket.socket() as probe:
        if probe.connect_ex(('127.0.0.1', 8002)) == 0:
            raise ValueError('Port remained occupied; no replacement started')
    env = dict(os.environ)
    env['DEEPSEEK_API_KEY'] = key
    command = [str(PYTHON), '-X', 'utf8', str(LAUNCHER), '--port', '8002', '--data-dir', str(DATA),
               '--embedding-dir', str(args.embedding_dir), '--reranker-dir', str(args.reranker_dir)]
    with (OUTPUT / 'backend-startup.log').open('a', encoding='utf-8') as log:
        process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
    env.pop('DEEPSEEK_API_KEY', None)
    os.environ.pop('DEEPSEEK_API_KEY', None)
    status('loading_models', old_pid=old.pid, launcher_pid=process.pid, budget_before=budget_before)
    for _ in range(240):
        if process.poll() is not None:
            raise ValueError('New launcher exited; inspect the local startup log')
        try:
            with urllib.request.urlopen('http://127.0.0.1:8002/api/health', timeout=2) as response:
                health = json.load(response)
            budget_after = json.loads((DATA / 'budget.json').read_text(encoding='utf-8'))
            status('ready', old_pid=old.pid, launcher_pid=process.pid, backend_pid=current_backend().pid,
                   health=health, budget_before=budget_before, budget_after=budget_after)
            return
        except (OSError, ValueError):
            time.sleep(1)
    raise ValueError('Backend startup timed out; inspect the local startup log')


def main():
    import tkinter as tk
    from tkinter import messagebox
    current_backend()
    status('waiting_for_local_key')
    window = tk.Tk()
    window.title('MathRAG 受控重启 · 本机密钥输入')
    window.geometry('560x240')
    window.attributes('-topmost', True)
    tk.Label(window, text='请输入 DeepSeek 密钥（仅进入新后端内存，不写入文件或聊天）。\n提交前旧服务继续运行；关闭窗口会取消重启。',
             justify='left', wraplength=520, padx=18, pady=18).pack()
    field = tk.Entry(window, show='●', width=62)
    field.pack(padx=18, pady=6)
    field.focus_force()
    info = tk.StringVar(value='累计预算保持不变：100次 / 1美元。')
    tk.Label(window, textvariable=info, wraplength=520).pack(pady=10)

    def cancel():
        field.delete(0, tk.END)
        status('cancelled_existing_backend_preserved')
        window.destroy()

    def submit():
        key = field.get().strip()
        if not key or not key.isascii():
            info.set('请输入有效的 ASCII 密钥。')
            return
        field.delete(0, tk.END)
        field.configure(state='disabled')
        button.configure(state='disabled')
        window.protocol('WM_DELETE_WINDOW', lambda: None)
        info.set('正在受控重启与加载本地模型，完成后窗口自动关闭。')
        window.update()
        try:
            restart(key)
            key = ''
            window.destroy()
        except Exception as error:
            key = ''
            os.environ.pop('DEEPSEEK_API_KEY', None)
            status('failed', error_type=type(error).__name__, message=str(error))
            messagebox.showerror('MathRAG 重启未完成', '请查看本机 restart-status.json 和 backend-startup.log。\n不要在聊天中发送密钥。')
            window.destroy()

    button = tk.Button(window, text='输入完成，受控重启', command=submit)
    button.pack()
    window.protocol('WM_DELETE_WINDOW', cancel)
    window.bind('<Return>', lambda _: submit())
    window.mainloop()


if __name__ == '__main__':
    main()
