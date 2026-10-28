"""Corpus errata must go through A's versioning API before paid validation."""
import importlib.util
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import httpx
import pytest

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('validation_corpus',ROOT/'scripts/validation_corpus.py')
corpus=importlib.util.module_from_spec(spec);spec.loader.exec_module(corpus)


@pytest.mark.parametrize('same_hash',[True,False])
def test_corrections_reindex_or_replace_and_preserve_revision_marker(tmp_path,same_hash):
    import hashlib
    args=SimpleNamespace(data_dir=tmp_path,kb='kb',output=tmp_path/'run')
    args.output.mkdir()
    (tmp_path/'validation-source.json').write_text(json.dumps({'status':'ready'}))
    contents={}
    with sqlite3.connect(tmp_path/'app.db') as db:
        db.execute('CREATE TABLE documents(id,content_hash,kb_id,user_id,filename,status)')
        for i,relative in enumerate(corpus.CORRECTIONS):
            path=ROOT/'knowledge/raw'/relative
            contents['doc'+str(i)]=path.read_text(encoding='utf-8')
            digest=hashlib.sha256(path.read_bytes()).hexdigest() if same_hash else 'old'
            db.execute('INSERT INTO documents VALUES(?,?,?,?,?,?)',('doc'+str(i),digest,'kb','u_final_validation',path.name,'ready'))
    requests=[]
    posts=[]
    def handler(request):
        requests.append(request)
        if request.method=='POST':
            posts.append(request)
            return httpx.Response(200,json={'data':{'doc_id':'doc'+str(len(posts)-1)}})
        if request.url.path.endswith('/status'):return httpx.Response(200,json={'data':{'status':'ready'}})
        doc_id=request.url.path.split('/')[3]
        return httpx.Response(200,json={'data':{'items':[{'content':contents[doc_id]}]}})
    with httpx.Client(base_url='http://validation',transport=httpx.MockTransport(handler)) as client:
        corpus.ensure_corpus_corrections(args,client,ROOT)
        count=len(requests)
        corpus.ensure_corpus_corrections(args,client,ROOT)
    assert len(requests)==count and len(posts)==2
    assert all(r.url.path.endswith('/reindex') for r in posts) if same_hash else all(r.url.path=='/api/docs/upload' for r in posts)
    marker=json.loads((tmp_path/'validation-source.json').read_text(encoding='utf-8'))
    assert set(marker['corpus_corrections'])==set(corpus.CORRECTIONS)
    assert all(len(v['sha256'])==64 for v in marker['corpus_corrections'].values())


def test_correction_will_not_mutate_another_owners_document(tmp_path):
    args=SimpleNamespace(data_dir=tmp_path,kb='kb',output=tmp_path)
    (tmp_path/'validation-source.json').write_text('{}')
    with sqlite3.connect(tmp_path/'app.db') as db:
        db.execute('CREATE TABLE documents(id,content_hash,kb_id,user_id,filename,status)')
        name=Path(next(iter(corpus.CORRECTIONS))).name
        db.execute('INSERT INTO documents VALUES(?,?,?,?,?,?)',('doc','old','kb','other',name,'ready'))
    def unexpected(request):raise AssertionError('No HTTP mutation authorized for other owner')
    with httpx.Client(base_url='http://validation',transport=httpx.MockTransport(unexpected)) as client:
        with pytest.raises(ValueError,match='source missing'):corpus.ensure_corpus_corrections(args,client,ROOT)
