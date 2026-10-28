"""Four bounded real smoke requests through C's actual Vite proxy and cookie auth."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import httpx

from validation_corpus import ensure_corpus_corrections

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',type=Path,required=True)
    parser.add_argument('--allow-paid',action='store_true')
    args=parser.parse_args();data=args.data_dir.resolve()
    out=data/'browser-results';out.mkdir(exist_ok=True)
    account=json.loads((data/'browser-account.json').read_text(encoding='utf-8'))
    source=json.loads((data/'validation-source.json').read_text(encoding='utf-8'))
    kb=source['kb_ids'][0]
    with httpx.Client(base_url='http://localhost:5174',timeout=240,trust_env=False) as client:
        page=client.get('/');page.raise_for_status()
        assert 'src/main.js' in page.text
        health=client.get('/api/health');health.raise_for_status();state=health.json()['data']
        assert state['embed_provider']=='local' and state['vector_backend']=='chroma'
        assert state['llm']['model']=='deepseek-flash' and state['llm']['configured'] and not state['llm']['mock']
        assert state['retrieval']['rerank_provider']=='local' and state['retrieval']['threshold']==0.62
        response=client.post('/api/auth/login',headers={'Origin':'http://localhost:5174'},
                             json={k:account[k] for k in ('username','password')})
        response.raise_for_status()
        client.headers.update({'X-CSRF-Token':response.json()['data']['csrf_token'],'Origin':'http://localhost:5174'})
        bad=client.post('/api/chat/stream',headers={'X-CSRF-Token':''},json={'kb_ids':[kb],'question':'测试'})
        assert bad.status_code==403
        with httpx.Client(base_url='http://localhost:5174',trust_env=False) as guest:
            assert guest.get('/api/docs').status_code==401
        ensure_corpus_corrections(SimpleNamespace(data_dir=data,kb=kb,user_id=account['user_id'],output=out),client,ROOT)
        docs=client.get('/api/docs',params={'kb_id':kb});docs.raise_for_status()
        assert len(docs.json()['data'])==171
        (out/'preflight.json').write_text(json.dumps({'health':state,'document_count':171,
            'csrf_enforced':True,'guest_document_access_denied':True,'frontend_proxy':True,
            'local_models_loaded':True,'index_reopened':True,'paid_requests':0},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print('Free preflight passed: real models, proxy/cookie/CSRF, 171 documents, two corrected sources.',flush=True)
        if not args.allow_paid:return
        evidence=out/'evidence.jsonl'
        if evidence.exists() and evidence.stat().st_size:
            raise ValueError('Smoke results already exist; do not repeat paid requests automatically')
        cases=[('h003','判断 f(x)=x^2+2x 的单调性',False),
               ('h011','（接上题）第二步为什么这样变形？',True),
               ('h018','求极限 lim(x→0) sinx/x',False),
               ('h012','第二种解法是什么？',True)]
        conversation=None
        for case_id,question,followup in cases:
            body={'kb_ids':[kb],'question':question,'stream':True}
            if followup:body['conversation_id']=conversation
            events=[];kind=None
            print('Real request '+case_id+' (no automatic retry).',flush=True)
            with client.stream('POST','/api/chat/stream',json=body) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line.startswith('event:'):kind=line[6:].strip()
                    elif line.startswith('data:'):events.append({'event':kind,'data':json.loads(line[5:])})
            errors=[e['data'] for e in events if e['event']=='error']
            completed=[e['data'] for e in events if e['event']=='done']
            meta=next(e['data'] for e in events if e['event']=='meta')
            conversation=meta['conversation_id']
            done=completed[-1] if completed else {}
            citations=done.get('citations') or [e['data'] for e in events if e['event']=='citation']
            history=client.get('/api/conversations/'+conversation+'/messages');history.raise_for_status()
            refs=[]
            with sqlite3.connect((data/'app.db').as_uri()+'?mode=ro',uri=True) as db:
                for cite in citations:
                    row=db.execute('SELECT c.content,c.seq,d.content_hash,d.stored_path FROM chunks c JOIN documents d ON c.doc_id=d.id WHERE c.id=? AND d.id=?',
                                   (cite['chunk_id'],cite['doc_id'])).fetchone()
                    assert row is not None and hashlib.sha256(Path(row[3]).read_bytes()).hexdigest()==row[2]
                    preview=client.get('/api/docs/'+cite['doc_id']+'/preview',params={'page':row[1]//5+1,'size':5})
                    preview.raise_for_status();assert any(i['id']==cite['chunk_id'] for i in preview.json()['data']['items'])
                    original=client.get('/api/docs/'+cite['doc_id']+'/file');original.raise_for_status()
                    assert hashlib.sha256(original.content).hexdigest()==row[2]
                    refs.append({'chunk_id':cite['chunk_id'],'doc_id':cite['doc_id'],'source_hash':row[2],'content':row[0]})
            record={'case_id':case_id,'question':question,'conversation_id':conversation,'request':body,
                    'events':events,'done':done,'errors':errors,'sources':refs,'history':history.json()['data'],
                    'budget':json.loads((data/'budget.json').read_text(encoding='utf-8')),
                    'model':state['llm']['model'],'code_commit':__import__('subprocess').check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),
                    'runtime_source':'integration worktree with launcher/budget changes; pending local commit'}
            with evidence.open('a',encoding='utf-8') as output:output.write(json.dumps(record,ensure_ascii=False)+'\n')
            if errors or not completed:raise RuntimeError('Smoke failed; evidence saved, no further model requests')
            if done.get('refused') or done.get('declined'):raise RuntimeError('Expected grounded answer declined; stop and inspect')
            assert refs and history.json()['data']['items'][-1]['status']=='done'
            print(case_id+' completed; cited sources/versions and saved history verified.',flush=True)
    print('Four requests completed; inspect answers before marking mathematical review passed.',flush=True)


if __name__=='__main__':main()
