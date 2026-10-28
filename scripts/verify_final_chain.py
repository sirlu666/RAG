"""Bounded local HTTP/SSE validation. Never changes the checked-in review CSV.

Uses a disposable backend on port 8001, isolated data and an ephemeral credential.
Real requests require --allow-paid. The key is read from the environment or a
hidden prompt; it is never included in arguments, reports, Git or logs.
"""
import argparse
import csv
from datetime import datetime, timezone
from decimal import Decimal
import getpass
import hashlib
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
INPUT_RATE = Decimal('0.30') / 1_000_000  # Published peak/cache-miss USD rate.
OUTPUT_RATE = Decimal('1.20') / 1_000_000


class RequestBudget:
    def __init__(self, maximum=26, usd='0.30', previous_calls=0, previous_usd='0', max_output_tokens=4096,
                 approved_calls=70, approved_usd='.60'):
        if (not 0 <= previous_calls < approved_calls or not 1 <= maximum <= approved_calls-previous_calls
                or not 1 <= max_output_tokens <= 4096
                or not Decimal('0') <= Decimal(previous_usd) < Decimal(approved_usd)
                or not Decimal('0') < Decimal(usd) <= Decimal(approved_usd)):
            raise ValueError('Budget exceeds the approved limits')
        self.maximum, self.cap = maximum, Decimal(usd)
        self.calls, self.reserved = 0, Decimal('0')
        self.previous_calls, self.previous_usd = previous_calls, Decimal(previous_usd)
        self.max_output_tokens = max_output_tokens
        self.approved_usd = Decimal(approved_usd)

    def reserve(self, messages):
        # UTF-8 byte count plus message framing is a conservative input token bound.
        token_bound = 512 + sum(len(m['content'].encode('utf-8')) for m in messages)
        if token_bound > 20000:
            raise ValueError('Input exceeds the approved validation bound')
        cost = token_bound * INPUT_RATE + self.max_output_tokens * OUTPUT_RATE
        if (self.calls >= self.maximum or self.reserved + cost > self.cap
                or self.previous_usd + self.reserved + cost > self.approved_usd):
            raise ValueError('Approved validation request/cost limit reached')
        self.calls += 1
        self.reserved += cost
        return {'calls':self.calls, 'reserved_upper_usd':str(self.reserved),
                'total_calls':self.previous_calls+self.calls,
                'total_reserved_upper_usd':str(self.previous_usd+self.reserved)}


def cumulative_budget(args):
    # Every raw run keeps its local count, including failed/in-flight attempts.
    previous_calls, previous_usd = 0, Decimal('0')
    for path in args.output.parent.glob('*/budget.json'):
        if path.parent == args.output:continue
        prior=json.loads(path.read_text(encoding='utf-8'))
        previous_calls += prior['calls']
        previous_usd += Decimal(prior['reserved_upper_usd'])
    return RequestBudget(args.max_requests,args.budget_usd,previous_calls,str(previous_usd),
                         getattr(args,'max_output_tokens',4096))


def configure(args):
    data = args.data_dir.resolve()
    if 'c-demo' in data.parts or not (data/'validation-source.json').exists():
        raise ValueError('Use data prepared by prepare_final_validation.py')
    os.environ.update(DATABASE_URL='sqlite:///'+(data/'app.db').as_posix(),UPLOAD_DIR=str(data/'uploads'),
        CHROMA_DIR=str(data/'chroma'),EMBED_PROVIDER='local',EMBED_LOCAL_MODEL=str(args.embedding_dir.resolve()),
        EMBED_DIM='1024',VECTOR_BACKEND='chroma',RERANK_PROVIDER='local',
        RERANK_LOCAL_MODEL=str(args.reranker_dir.resolve()),RELEVANCE_THRESHOLD='0.62',
        MOCK_LLM='false',DEEPSEEK_BASE_URL='https://api.deepseek.com',DEEPSEEK_MODEL='deepseek-flash',
        LLM_MAX_TOKENS=str(args.max_output_tokens),LLM_MAX_RETRIES='0',LLM_FIRST_TOKEN_TIMEOUT_S='90',LLM_TIMEOUT_S='180',
        OCR_ENGINE='rapid',OCR_FORMULA='none',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',
        ANONYMIZED_TELEMETRY='False',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',
        PYTHONIOENCODING='utf-8')
    sys.path.insert(0,str(ROOT/'backend'))


def serve(args):
    configure(args)
    from app.rag import llm
    from app.core.exceptions import AppError
    import httpx
    import ssl
    from pip._vendor import truststore
    tls = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    budget = cumulative_budget(args)
    class BoundedClient(llm.LlmClient):
        async def stream_chat(self, messages, **kwargs):
            kwargs['max_tokens']=min(kwargs.get('max_tokens') or args.max_output_tokens,args.max_output_tokens)
            try:
                record = budget.reserve(messages)
            except ValueError as exc:
                raise AppError(4001,str(exc)) from exc
            (args.output/'budget.json').write_text(json.dumps(record),encoding='utf-8')
            try:
                async for piece in super().stream_chat(messages,**kwargs):
                    yield piece
            finally:
                usage={'call':record['calls'],'usage':(kwargs.get('stats') or {}).get('usage',{}),
                       'finish_reason':(kwargs.get('stats') or {}).get('finish_reason')}
                with (args.output/'usage.jsonl').open('a',encoding='utf-8') as fh:
                    fh.write(json.dumps(usage)+'\n')

        async def _stream_once(self,payload,stats):
            payload={**payload,'thinking':{'type':args.thinking}}
            if args.thinking == 'enabled':payload['reasoning_effort']=args.reasoning_effort
            async for piece in super()._stream_once(payload,stats):
                yield piece
    llm._client=BoundedClient(transport=httpx.AsyncHTTPTransport(verify=tls))
    # A degraded retrieval run must never consume the paid validation budget.
    from app.rag.pipeline import RagPipeline
    from app.rag import reranker
    def small_batch_scores(question, documents):
        model = reranker._local._load()
        return [float(score) for score in model.predict(
            [(question, doc) for doc in documents], batch_size=2, show_progress_bar=False)]
    reranker._local.scores = small_batch_scores
    search, pick = RagPipeline.search, RagPipeline.pick
    def checked_search(self, question, kb_ids):
        result = search(self, question, kb_ids)
        if result.mode != 'hybrid' or not any(c.vector_score > 0 for c in result.candidates):
            raise AppError(4002, 'Validation requires working hybrid retrieval')
        return result
    def checked_pick(self, question, result):
        chosen = pick(self, question, result)
        if chosen and any(c.rerank_score is None for c in chosen):
            raise AppError(4002, 'Validation requires working local reranking')
        return chosen
    RagPipeline.search, RagPipeline.pick = checked_search, checked_pick
    import uvicorn
    uvicorn.run('app.main:app',host='127.0.0.1',port=8001)


def ask(client, kb, question, conversation=None):
    body={'kb_ids':[kb],'question':question,'stream':True}
    if conversation:
        body['conversation_id']=conversation
    events=[]
    with client.stream('POST','/api/chat/stream',json=body) as response:
        response.raise_for_status()
        name=None
        for line in response.iter_lines():
            if line.startswith('event: '):
                name=line[7:]
            elif line.startswith('data: '):
                event={'event':name,'data':json.loads(line[6:])}
                events.append(event)
                if name=='error':
                    break
    done=next((e['data'] for e in events if e['event']=='done'),None)
    error=next((e['data'] for e in events if e['event']=='error'),None)
    if done is None and error is None:
        raise RuntimeError('Response did not complete')
    meta=next(e['data'] for e in events if e['event']=='meta')
    return {'conversation_id':meta['conversation_id'],'events':events,'done':done or {},
            'completed':done is not None,'error':error,
            'answer':(done or {}).get('answer') or ''.join(e['data']['text'] for e in events if e['event']=='delta'),
            'stream_citations':[e['data'] for e in events if e['event']=='citation']}


def behavior_verdict(case_id, evidence):
    done, citations = evidence['done'], evidence['citations']
    if case_id == 'h015':
        passed = done.get('refused') and done.get('first_token_ms') == 0 and not citations
    elif case_id == 'h016':
        passed = done.get('refused') and not citations
    else:
        passed = (done.get('declined') and citations and evidence['answer'].lstrip().startswith('未找到依据'))
    return 'auto:pass' if passed else 'auto:fail'


def replay_history(initial, kb):
    from datetime import timedelta
    from app.db.chat_models import Conversation, Message
    from app.db.models import new_id
    from app.db.session import SessionLocal
    history=[{'role':'user','content':initial['question']}, {'role':'assistant','content':initial['answer']}]
    conversation, now = new_id('c'), datetime.now(timezone.utc)
    with SessionLocal() as db:
        db.add(Conversation(id=conversation,user_id='u_final_validation',kb_ids=json.dumps([kb]),title='追问复验'))
        db.flush()
        for offset,item in enumerate(history):
            db.add(Message(conversation_id=conversation,role=item['role'],content=item['content'],
                           created_at=now+timedelta(microseconds=offset)))
        db.commit()
    return conversation, history


def run(args):
    configure(args)
    for folder,weight in ((args.embedding_dir,'pytorch_model.bin'),(args.reranker_dir,'model.safetensors')):
        if not (folder/'config.json').exists() or not (folder/weight).exists():
            raise ValueError('Model not ready: '+folder.name)
    manifest=json.loads((args.data_dir/'validation-source.json').read_text(encoding='utf-8'))
    if manifest.get('status')!='ready' or args.kb not in manifest['kb_ids']:
        raise ValueError('Validation corpus/KB is not ready')
    if args.check:
        from app.rag.vectorstore import get_store
        store = get_store()
        sample = store.collection.get(limit=1, include=['embeddings'])
        if not sample['ids'] or not store.query(list(sample['embeddings'][0]), [args.kb], 1):
            raise ValueError('Persisted vector index cannot be queried')
        print(json.dumps({'ready':True,'kb':args.kb,'max_requests':args.max_requests,
                          'budget_usd':args.budget_usd,'paid_requests':0}))
        return
    if not args.allow_paid:
        raise ValueError('--allow-paid requires explicit user approval of the stated budget')
    key=os.environ.get('DEEPSEEK_API_KEY') or getpass.getpass('DeepSeek credential (hidden): ').strip()
    if not key:
        raise ValueError('Credential is missing')
    with socket.socket() as probe:
        if probe.connect_ex(('127.0.0.1',8001))==0:
            raise ValueError('Port 8001 is occupied; existing service was not changed')
    args.output.mkdir(parents=True,exist_ok=False)
    env=os.environ.copy();env['DEEPSEEK_API_KEY']=key
    command=[sys.executable,str(Path(__file__).resolve()),'--serve','--data-dir',str(args.data_dir),
        '--embedding-dir',str(args.embedding_dir),'--reranker-dir',str(args.reranker_dir),
        '--kb',args.kb,'--output',str(args.output),'--max-requests',str(args.max_requests),'--budget-usd',args.budget_usd,
        '--thinking',args.thinking,'--reasoning-effort',args.reasoning_effort,
        '--max-output-tokens',str(args.max_output_tokens)]
    creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    with (args.output/'service.log').open('w',encoding='utf-8') as log:
        process=subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=creationflags)
        env.pop('DEEPSEEK_API_KEY',None)
        try:
            import httpx
            with httpx.Client(base_url='http://127.0.0.1:8001',timeout=240,
                              headers={'Authorization':'Bearer dev:final_validation'}) as client:
                for _ in range(90):
                    if process.poll() is not None:
                        raise RuntimeError('Validation backend exited; inspect the local service log')
                    try:
                        if client.get('/api/health').status_code==200:
                            break
                    except httpx.HTTPError:
                        pass
                    time.sleep(1)
                else:
                    raise RuntimeError('Validation backend did not become ready')
                from validation_corpus import ensure_corpus_corrections
                ensure_corpus_corrections(args,client,ROOT)
                execute_cases(args,client)
        finally:
            process.terminate()
            try:process.wait(timeout=15)
            except subprocess.TimeoutExpired:process.kill();process.wait()


def execute_cases(args,client):
    from app.rag.context import build_retrieval_question
    rows=list(csv.DictReader((ROOT/'eval/human_review_template.csv').open(encoding='utf-8')))
    indexed={r['case_id']:r for r in rows}
    records={}
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    def record(case_id,question,conversation=None,history=None,extra=None,kb=None):
        print('Validating',case_id,flush=True)
        kb = kb or args.kb
        budget_path=args.output/'budget.json'
        before=json.loads(budget_path.read_text(encoding='utf-8'))['calls'] if budget_path.exists() else 0
        result=ask(client,kb,question,conversation)
        after=json.loads(budget_path.read_text(encoding='utf-8'))['calls'] if budget_path.exists() else 0
        usage=None
        if after>before:
            usage=next((json.loads(line) for line in (args.output/'usage.jsonl').read_text(encoding='utf-8').splitlines()
                        if json.loads(line)['call']==after),None)
        sources=[]
        for citation in result['done'].get('citations',result.get('stream_citations',[])):
            reply=client.get('/api/docs/'+citation['doc_id']+'/preview',
                             params={'page':citation.get('seq',0)//100+1,'size':100})
            reply.raise_for_status()
            if not any(chunk['id']==citation['chunk_id'] for chunk in reply.json()['data']['items']):
                raise RuntimeError('Citation cannot be resolved to its original chunk')
            with sqlite3.connect((args.data_dir/'app.db').as_uri()+'?mode=ro',uri=True) as db:
                version=db.execute('SELECT content_hash FROM documents WHERE id=?',(citation['doc_id'],)).fetchone()
            sources.append({**citation,'source_content_hash':version[0] if version else None})
        source=json.loads((args.data_dir/'validation-source.json').read_text(encoding='utf-8'))
        evidence={'case_id':case_id,'commit':commit,'model':result['done'].get('model'),
            'thinking':args.thinking,'reasoning_effort':args.reasoning_effort if args.thinking=='enabled' else None,
            'max_output_tokens':args.max_output_tokens,'provider_usage':usage,
            'kb_ids':[kb],'question':question,'history':history or [],
            'retrieval_question':build_retrieval_question(question,history),
            'snapshot_sha256':source['snapshot_sha256'],'citations':sources,**result,**(extra or {})}
        evidence['corpus_corrections']=source.get('corpus_corrections',{})
        with (args.output/'evidence.jsonl').open('a',encoding='utf-8') as fh:
            fh.write(json.dumps(evidence,ensure_ascii=False)+'\n')
        records[case_id]=evidence
        return evidence
    if args.cases:
        if any(case_id not in indexed for case_id in args.cases):
            raise ValueError('Unknown evaluation case ID')
        for case_id in args.cases:
            if case_id=='h017':
                with sqlite3.connect((args.data_dir/'app.db').as_uri()+'?mode=ro',uri=True) as db:
                    fixture_rows=db.execute("SELECT content FROM chunks WHERE kb_id='kb_final_insufficient'").fetchall()
                if not fixture_rows:raise ValueError('Controlled insufficient-evidence fixture missing')
                record(case_id,indexed[case_id]['question'],kb='kb_final_insufficient',
                       extra={'fixture_text':'\n'.join(row[0] for row in fixture_rows)})
            else:record(case_id,indexed[case_id]['question'])
        return
    if args.recheck_followups:
        # Reuse captured real first answers as history fixtures. Preserve failed
        # conversations; replay into new validation-only conversations so the
        # erroneous follow-up cannot contaminate the replacement generation.
        previous={r['case_id']:r for r in map(json.loads,args.recheck_followups.read_text(encoding='utf-8').splitlines())}
        for first,follow in (('h003','h011'),('h018','h012')):
            initial=previous[first]
            conversation, history = replay_history(initial, args.kb)
            result=record(follow,indexed[follow]['question'],conversation,history,
                {'history_provenance':{'type':'replay_of_captured_real_answer','commit':initial['commit'],
                                       'original_conversation_id':initial['conversation_id']}})
            if not result['completed'] or result['done'].get('refused') or result['done'].get('declined'):
                raise RuntimeError('Follow-up recheck failed: '+follow)
        return
    if args.resume_evidence:
        from app.rag.prompt import build_messages
        from app.rag.retriever import Candidate
        previous={r['case_id']:r for r in map(json.loads,args.resume_evidence.read_text(encoding='utf-8').splitlines())}
        for case_id in indexed:
            if case_id not in previous:continue
            evidence=previous[case_id]
            if evidence.get('error') or not evidence.get('completed',any(e['event']=='done' for e in evidence['events'])):
                continue
            if evidence['kb_ids'] != [args.kb]:continue
            if evidence.get('thinking','disabled') != args.thinking:
                raise ValueError('Cannot reuse answer: thinking mode changed')
            if evidence.get('max_output_tokens',2048) != args.max_output_tokens:
                raise ValueError('Cannot reuse answer: output limit changed')
            if args.thinking=='enabled' and evidence.get('reasoning_effort')!=args.reasoning_effort:
                raise ValueError('Cannot reuse answer: reasoning effort changed')
            if evidence['done'].get('refused') or evidence['done'].get('declined'):
                continue
            namespace={}
            old_code=subprocess.check_output(['git','show',evidence['commit']+':backend/app/rag/prompt.py'],cwd=ROOT).decode('utf-8')
            exec(compile(old_code,'captured-prompt.py','exec'),namespace)
            with sqlite3.connect((args.data_dir/'app.db').as_uri()+'?mode=ro',uri=True) as db:
                candidates=[Candidate(chunk_id=c['chunk_id'],kb_id=args.kb,doc_id=c['doc_id'],doc_name=c['doc_name'],
                    content=db.execute('SELECT content FROM chunks WHERE id=?',(c['chunk_id'],)).fetchone()[0],
                    page=c['page']) for c in evidence['citations']]
            old_messages=namespace['build_messages'](evidence['question'],candidates,evidence['history'])
            if old_messages != build_messages(evidence['question'],candidates,evidence['history']):
                raise ValueError('Cannot reuse first answer: effective prompt changed')
            evidence={**evidence,'reuse_verified_against_commit':commit,
                'effective_prompt_sha256':hashlib.sha256(json.dumps(old_messages,ensure_ascii=False,sort_keys=True).encode()).hexdigest()}
            with (args.output/'evidence.jsonl').open('a',encoding='utf-8') as fh:
                fh.write(json.dumps(evidence,ensure_ascii=False)+'\n')
            records[case_id]=evidence
    # Four smoke requests exercise actual stored conversation history.
    for first,follow in (('h003','h011'),('h018','h012')):
        if follow in records:continue
        initial=records.get(first) or record(first,indexed[first]['question'])
        history=[{'role':'user','content':initial['question']},{'role':'assistant','content':initial['answer']}]
        conversation=initial['conversation_id']
        if args.resume_evidence:
            conversation,history=replay_history(initial,args.kb)
        answer=record(follow,indexed[follow]['question'],conversation,history,
            {'history_provenance':{'type':'replay_of_captured_real_answer','commit':initial['commit']}} if args.resume_evidence else None)
        if not answer['completed'] or answer['done'].get('refused') or answer['done'].get('declined'):
            raise RuntimeError('Follow-up smoke failed: '+follow)
    # Two image smoke requests: preserve raw OCR and explicit correction provenance.
    image_cases=(('image-text',args.text_image,args.text_correction),
                 ('image-formula',args.formula_image,args.formula_correction))
    for case_id,image,correction in (() if args.skip_images else image_cases):
        if image is None or not correction:
            raise ValueError('Both image fixtures and their reviewed correction text are required')
        with image.open('rb') as fh:
            response=client.post('/api/chat/image/recognize',files={'file':(image.name,fh,'image/png')})
        response.raise_for_status();ocr=response.json()['data']
        if not ocr['text'].strip():
            raise RuntimeError('Image recognition produced no text: '+case_id)
        outcome=record(case_id,correction,extra={'ocr':ocr,'image_sha256':hashlib.sha256(image.read_bytes()).hexdigest(),
                                               'correction_source':'explicit fixture transcription'})
        if not outcome['completed'] or outcome['done'].get('refused') or outcome['done'].get('declined'):
            raise RuntimeError('Image answer smoke failed: '+case_id)
    # h017 requires genuinely insufficient sources, not a note in the question.
    # Add a controlled fixture only to the disposable validation database.
    from app.db.models import KnowledgeBase
    from app.db.session import SessionLocal
    insufficient_kb = 'kb_final_insufficient'
    with SessionLocal() as db:
        if db.get(KnowledgeBase, insufficient_kb) is None:
            db.add(KnowledgeBase(id=insufficient_kb,user_id='u_final_validation',name='不足依据测试'))
            db.commit()
    fixture = ('# 不足依据测试\n待研究的函数：f(x)=x^2+2x。\n'
               '本资料仅记录函数表达式，未给出单调性判别方法、求导规则或配方恒等式。\n')
    with sqlite3.connect((args.data_dir/'app.db').as_uri()+'?mode=ro',uri=True) as db:
        existing=db.execute('SELECT id FROM documents WHERE kb_id=? AND user_id=? AND content_hash=? AND status=?',
            (insufficient_kb,'u_final_validation',hashlib.sha256(fixture.encode()).hexdigest(),'ready')).fetchone()
    if existing:fixture_doc=existing[0]
    else:
        uploaded = client.post('/api/docs/upload',data={'kb_id':insufficient_kb},
            files={'file':('insufficient-'+args.output.name+'.md',fixture.encode('utf-8'),'text/markdown')})
        uploaded.raise_for_status()
        fixture_doc = uploaded.json()['data']['doc_id']
    for _ in range(90):
        status = client.get('/api/docs/'+fixture_doc+'/status')
        status.raise_for_status()
        state = status.json()['data']['status']
        if state == 'ready':break
        if state == 'failed':raise RuntimeError('Insufficient-evidence fixture ingestion failed')
        time.sleep(1)
    else:raise RuntimeError('Insufficient-evidence fixture ingestion timed out')
    for row in rows:
        if row['case_id'] not in records:
            record(row['case_id'],row['question'],kb=insufficient_kb if row['case_id']=='h017' else args.kb,
                   extra={'fixture_text':fixture} if row['case_id']=='h017' else None)
        evidence=records[row['case_id']]
        row.update(model_answer=evidence['answer'],model_version=evidence['model'] or 'not-called',
                   human_verdict='',verdict_reason='',status='pending')
        if row['scenario']=='无依据':
            row.update(human_verdict=behavior_verdict(row['case_id'],evidence),
                       verdict_reason='仅为拒答行为检查，非人工数学判定',status='auto_checked')
    with (args.output/'review.csv').open('w',encoding='utf-8',newline='') as fh:
        writer=csv.DictWriter(fh,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    human=[r for r in rows if r['scenario']!='无依据']
    for batch in range(0,len(human),3):
        lines=['# 人工复核批次 '+str(batch//3+1),'本文件未填写任何人工通过结论。请结合 evidence.jsonl 的资料与引用核对。']
        for row in human[batch:batch+3]:
            lines.extend(['\n## '+row['case_id'],row['question'],'\n预期检查要点：'+row['expected_points'],
                          '\n模型回答：\n'+row['model_answer'],'\n人工判定：待确认\n理由：待填写'])
        (args.output/f'review-{batch//3+1:02}.md').write_text('\n\n'.join(lines),encoding='utf-8')
    print('Validation evidence and 17 human-review cases saved:',args.output,flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',type=Path,required=True)
    parser.add_argument('--embedding-dir',type=Path,required=True)
    parser.add_argument('--reranker-dir',type=Path,required=True)
    parser.add_argument('--kb',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--allow-paid',action='store_true')
    parser.add_argument('--serve',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--max-requests',type=int,default=26)
    parser.add_argument('--budget-usd',default='0.30')
    parser.add_argument('--text-image',type=Path)
    parser.add_argument('--formula-image',type=Path)
    parser.add_argument('--text-correction')
    parser.add_argument('--formula-correction')
    parser.add_argument('--recheck-followups',type=Path,help='Replay first answers from an earlier evidence JSONL; only ask two follow-ups')
    parser.add_argument('--resume-evidence',type=Path,help='Reuse first answers only after verifying identical effective prompts')
    parser.add_argument('--cases',nargs='+',help='Run only selected independent review cases')
    parser.add_argument('--skip-images',action='store_true',help='Keep separately recorded image-chain evidence; run the 20 review questions only')
    parser.add_argument('--thinking',choices=['enabled','disabled'],default='disabled')
    parser.add_argument('--reasoning-effort',choices=['low','high','max'],default='low')
    parser.add_argument('--max-output-tokens',type=int,default=4096)
    args=parser.parse_args()
    for name in ('data_dir','embedding_dir','reranker_dir','output'):
        setattr(args,name,getattr(args,name).resolve())
    cumulative_budget(args)
    if args.serve:serve(args)
    else:run(args)


if __name__=='__main__':
    main()
