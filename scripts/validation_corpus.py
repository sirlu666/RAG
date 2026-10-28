"""Apply a tracked corpus correction through A's API, only in the disposable DB."""
import hashlib
import json
from pathlib import Path
import sqlite3
import time
import re

CORRECTIONS={
    'obsidian_math/1-1. 函数的极限与连续__洛必达法则.md':"\\frac{f'(x)}{F'(x)}",
    'obsidian_math/1-1. 函数的极限与连续__两个重要极限.md':r'\lim_{x \to \infty} (1+x)^\frac{1}{x} = 1',
}


def ensure_corpus_corrections(args, client, root):
    for relative,expected in CORRECTIONS.items():
        _ensure_one(args,client,root,relative,expected)


def _ensure_one(args,client,root,relative,expected):
    marker=args.data_dir/'validation-source.json'
    source=json.loads(marker.read_text(encoding='utf-8'))
    path=root/'knowledge/raw'/relative
    raw=path.read_bytes()
    digest=hashlib.sha256(raw).hexdigest()
    corrected=source.get('corpus_corrections',{})
    if corrected.get(relative,{}).get('sha256')==digest:return
    with sqlite3.connect((args.data_dir/'app.db').as_uri()+'?mode=ro',uri=True) as db:
        row=db.execute('SELECT id,content_hash FROM documents WHERE kb_id=? AND user_id=? AND filename=? AND status=?',
            (args.kb,'u_final_validation',path.name,'ready')).fetchone()
    if row is None:raise ValueError('Validation corpus correction source missing')
    print('Reindexing tracked source correction (no model API calls): '+path.name,flush=True)
    if row[1]!=digest:
        response=client.post('/api/docs/upload',data={'kb_id':args.kb,'overwrite':'true'},
            files={'file':(path.name,raw,'text/markdown')})
        response.raise_for_status()
        doc_id=response.json()['data']['doc_id']
    else:
        doc_id=row[0]
        response=client.post('/api/docs/'+doc_id+'/reindex')
        response.raise_for_status()
    for _ in range(120):
        response=client.get('/api/docs/'+doc_id+'/status');response.raise_for_status()
        state=response.json()['data']['status']
        if state=='ready':break
        if state in ('failed','rejected'):raise RuntimeError('Corpus correction reindex failed')
        time.sleep(1)
    else:raise RuntimeError('Corpus correction reindex timed out')
    preview=client.get('/api/docs/'+doc_id+'/preview',params={'size':100});preview.raise_for_status()
    text='\n'.join(item['content'] for item in preview.json()['data']['items'])
    if re.sub(r'\s+','',expected) not in re.sub(r'\s+','',text):
        raise RuntimeError('Corrected formula absent from rebuilt chunks')
    corrected[relative]={'doc_id':doc_id,'sha256':digest,
                         'reason':'Tracked mathematical erratum; original snapshot retained as base'}
    source['corpus_corrections']=corrected
    marker.write_text(json.dumps(source,ensure_ascii=False,indent=2),encoding='utf-8')
    (args.output/'corpus-corrections.json').write_text(json.dumps(corrected,ensure_ascii=False,indent=2),encoding='utf-8')
