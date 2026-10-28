"""Map the isolated snapshot to a real local browser account; no LLM calls."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',type=Path,required=True)
    parser.add_argument('--embedding-dir',type=Path,required=True)
    args=parser.parse_args();data=args.data_dir.resolve()
    marker=data/'validation-source.json'
    source=json.loads(marker.read_text(encoding='utf-8'))
    if 'c-demo' in data.parts or source['snapshot_sha256']!='8480458b1354b7001e744f9d21fc06a6a3205304a87fe50e4a0649f808aae950':
        raise ValueError('Use the isolated prepared team snapshot')
    os.environ.update(DATABASE_URL='sqlite:///'+(data/'app.db').as_posix(),UPLOAD_DIR=str(data/'uploads'),
        CHROMA_DIR=str(data/'chroma'),VECTOR_BACKEND='chroma',EMBED_PROVIDER='local',
        EMBED_LOCAL_MODEL=str(args.embedding_dir.resolve()),EMBED_DIM='1024',
        MOCK_LLM='true',RERANK_PROVIDER='none',ANONYMIZED_TELEMETRY='False')
    sys.path.insert(0,str(ROOT/'backend'))
    from fastapi.testclient import TestClient
    from app.main import app
    from app.db.session import SessionLocal
    from app.db.models import User,KnowledgeBase,Document,Chunk
    from app.rag.vectorstore import get_store
    account_file=data/'browser-account.json'
    account={'username':'c_integration','password':'MathRAG-local-2026!'}
    with TestClient(app,base_url='http://localhost:5174') as client:
        if source.get('browser_account'):
            account=json.loads(account_file.read_text(encoding='utf-8'))
            response=client.post('/api/auth/login',json={k:account[k] for k in ('username','password')})
        else:
            response=client.post('/api/auth/register',json=account)
            if response.status_code==409:
                response=client.post('/api/auth/login',json=account)
        response.raise_for_status();user_id=response.json()['data']['user']['id']
    previous=source.get('browser_account',{}).get('user_id','u_final_validation')
    if previous not in ('u_final_validation',user_id):raise ValueError('Unexpected data owner')
    store=get_store();items=[]
    with SessionLocal() as db:
        docs=db.query(Document).filter(Document.user_id.in_([previous,user_id])).all()
        for doc in docs:
            for item in store.snapshot_doc(doc.id):
                item['m']['user_id']=user_id;items.append(item)
        ids={c.id for c in db.query(Chunk)}
        if ids!=store.ids():raise ValueError('Snapshot/vector IDs differ before mapping')
        for start in range(0,len(items),128):
            batch=items[start:start+128]
            store.upsert(ids=[i['id'] for i in batch],vectors=[i['v'] for i in batch],
                         documents=[i['d'] for i in batch],metadatas=[i['m'] for i in batch])
        for model in (KnowledgeBase,Document,Chunk):
            db.query(model).filter(model.user_id==previous).update({'user_id':user_id},synchronize_session=False)
        db.query(KnowledgeBase).filter(KnowledgeBase.user_id==user_id).update({'name':'数学真实联调资料'},synchronize_session=False)
        db.commit()
        if any(i['m']['user_id']!=user_id for doc in docs for i in store.snapshot_doc(doc.id)):
            raise ValueError('Vector ownership mapping failed')
        if db.query(Chunk).filter(Chunk.user_id!=user_id).count():raise ValueError('Unexpected chunk owner')
    account['user_id']=user_id
    account_file.write_text(json.dumps(account,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    source['browser_account']={'username':account['username'],'user_id':user_id}
    marker.write_text(json.dumps(source,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'username':account['username'],'user_id':user_id,'documents':len(docs),'vectors':store.count(),'model_calls':0}))


if __name__=='__main__':main()
