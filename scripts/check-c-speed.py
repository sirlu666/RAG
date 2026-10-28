"""One explicitly budgeted real question, after local retrieval gate checks pass."""
import json
import os
from pathlib import Path
import sqlite3
import time

import httpx


def main():
    data = Path(os.environ['LOCALAPPDATA']) / 'Temp/mathrag-c-integration-20261028'
    output = data / 'speed-optimization-20261028'
    target = output / 'real-question-result.json'
    if target.exists():
        raise ValueError('Real speed check already recorded; refusing another paid run')
    local = json.loads((output / 'local-probe.json').read_text(encoding='utf-8'))
    if local['thinking'] != 'disabled' or not all(row['gate_matches'] for row in local['local_cases']):
        raise ValueError('Local quality gates did not all pass; no model request sent')
    db = sqlite3.connect((data / 'app.db').as_uri() + '?mode=ro', uri=True)
    source = db.execute("SELECT content,conversation_id,created_at FROM messages WHERE role='user' AND content LIKE ? ORDER BY created_at DESC LIMIT 1",
                        ('%\\frac{f(x)}{x^{2}}%',)).fetchone()
    baseline = db.execute("SELECT latency_ms,first_token_ms FROM messages WHERE role='assistant' AND conversation_id=? AND created_at>? ORDER BY created_at LIMIT 1",
                          (source[1], source[2])).fetchone()
    db.close()
    account = json.loads((data / 'browser-account.json').read_text(encoding='utf-8'))
    before = json.loads((data / 'budget.json').read_text(encoding='utf-8'))
    if before['total_calls'] >= before['approved_calls']:
        raise ValueError('No approved call remaining')
    # Durable attempt marker prevents accidental paid retries after partial failure.
    with (output / 'real-question-attempt.json').open('x', encoding='utf-8') as marker:
        json.dump({'budget_before': before, 'maximum_attempts': 1}, marker)
    base = 'http://localhost:8086'
    answer = ''
    meta = done = None
    first_answer_ms = None
    with httpx.Client(base_url=base, timeout=180, headers={'Origin': base}) as client:
        response = client.post('/api/auth/login', json=account)
        response.raise_for_status()
        csrf = response.json()['data']['csrf_token']
        kb = next(row for row in client.get('/api/kbs').json()['data'] if row['name'] == '数学真实联调资料')
        start = time.perf_counter()
        with client.stream('POST', '/api/chat/stream', headers={'X-CSRF-Token': csrf},
                           json={'kb_ids': [kb['id']], 'question': source[0], 'stream': True}) as stream:
            stream.raise_for_status()
            event = ''
            for line in stream.iter_lines():
                if line.startswith('event: '):
                    event = line[7:]
                if not line.startswith('data: '):
                    continue
                value = json.loads(line[6:])
                if event == 'error':
                    raise ValueError('Speed question failed: ' + value.get('message', 'unknown'))
                if event == 'meta':
                    meta = value
                if event == 'delta':
                    if first_answer_ms is None:
                        first_answer_ms = round((time.perf_counter() - start) * 1000)
                    answer += value['text']
                if event == 'done':
                    done = value
        elapsed = round((time.perf_counter() - start) * 1000)
    if not done or done.get('refused') or done.get('declined'):
        raise ValueError('Question did not complete with evidence; inspect the saved session')
    after = json.loads((data / 'budget.json').read_text(encoding='utf-8'))
    result = {'baseline_same_question_total_ms': baseline[0], 'baseline_model_first_content_ms': baseline[1],
              'wall_ms': elapsed, 'first_answer_wall_ms': first_answer_ms, 'meta': meta, 'done': done,
              'answer': done.get('answer', answer), 'budget_before': before, 'budget_after': after,
              'calls_added': after['total_calls'] - before['total_calls']}
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({key: result[key] for key in ['baseline_same_question_total_ms', 'wall_ms', 'first_answer_wall_ms', 'calls_added']}, ensure_ascii=False))
    print(json.dumps({key: done.get(key) for key in ['retrieval_ms', 'rerank_ms', 'llm_ms', 'first_token_ms', 'tokens_out']}, ensure_ascii=False))
    print(result['answer'])


if __name__ == '__main__':
    main()
