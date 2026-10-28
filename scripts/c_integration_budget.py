"""Persistent spending reservations for the explicitly authorized local C session."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import threading
from decimal import Decimal

from verify_final_chain import RequestBudget

BASE_CALLS=66
BASE_USD='0.4175985'
MAX_CALLS=100
MAX_USD='1.00'


class PersistentBudget:
    def __init__(self, path):
        self.path=Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.lock=threading.Lock()
        with self._locked():
            if not self.path.exists():
                self._write({'baseline_calls':BASE_CALLS,'baseline_reserved_usd':BASE_USD,
                             'calls':0,'reserved_upper_usd':'0',
                             'total_calls':BASE_CALLS,'total_reserved_upper_usd':BASE_USD,
                             'approved_calls':MAX_CALLS,'approved_usd':MAX_USD})
            self._read()

    @contextmanager
    def _locked(self):
        with self.lock, self.path.with_suffix('.lock').open('a+b') as handle:
            handle.seek(0,2)
            if not handle.tell():handle.write(b'0');handle.flush()
            handle.seek(0)
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(handle.fileno(),msvcrt.LK_LOCK,1)
            else:
                import fcntl
                fcntl.flock(handle,fcntl.LOCK_EX)
            try:yield
            finally:
                handle.seek(0)
                if os.name=='nt':msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
                else:fcntl.flock(handle,fcntl.LOCK_UN)

    def _read(self):
        record=json.loads(self.path.read_text(encoding='utf-8'))
        if (record['baseline_calls']!=BASE_CALLS or record['baseline_reserved_usd']!=BASE_USD
                or record['total_calls']!=BASE_CALLS+record['calls']):
            raise ValueError('Budget ledger baseline is inconsistent; do not reset it')
        if (Decimal(record['total_reserved_upper_usd'])!=Decimal(BASE_USD)+Decimal(record['reserved_upper_usd'])
                or record['calls']<0 or Decimal(record['reserved_upper_usd'])<0):
            raise ValueError('Budget ledger amounts are inconsistent; do not reset it')
        return record

    def _write(self,record):
        temporary=self.path.with_suffix('.tmp')
        with temporary.open('w',encoding='utf-8') as output:
            json.dump(record,output,ensure_ascii=False,indent=2)
            output.flush();os.fsync(output.fileno())
        temporary.replace(self.path)

    def reserve(self,messages):
        with self._locked():
            record=self._read()
            previous=record['total_calls']
            if previous>=MAX_CALLS:raise ValueError('已达到累计100次调用上限')
            budget=RequestBudget(maximum=MAX_CALLS-previous,usd=MAX_USD,
                previous_calls=previous,previous_usd=record['total_reserved_upper_usd'],
                max_output_tokens=4096,approved_calls=MAX_CALLS,approved_usd=MAX_USD)
            reserved=budget.reserve(messages)
            record.update(calls=record['calls']+1,
                reserved_upper_usd=str(budget.previous_usd+budget.reserved-Decimal(BASE_USD)),
                total_calls=reserved['total_calls'],total_reserved_upper_usd=reserved['total_reserved_upper_usd'])
            self._write(record)
            return record


def install_runtime(data):
    """Guard streaming and nonstreaming provider entrypoints, before any HTTP call."""
    import httpx
    import ssl
    from pip._vendor import truststore
    from app.core.exceptions import AppError
    from app.rag import llm,reranker
    from app.rag.pipeline import RagPipeline
    budget=PersistentBudget(data/'budget.json')
    usage_lock=threading.Lock()

    def reserve(messages):
        try:return budget.reserve(messages)
        except ValueError as exc:raise AppError(4001,'联调预算保护：'+str(exc)) from exc

    def usage(record,stats):
        with usage_lock, (data/'usage.jsonl').open('a',encoding='utf-8') as output:
            output.write(json.dumps({'total_call':record['total_calls'],'usage':stats.get('usage',{}),
                                     'finish_reason':stats.get('finish_reason')})+'\n')

    class BoundedClient(llm.LlmClient):
        async def stream_chat(self,messages,**kwargs):
            record=reserve(messages)
            kwargs['max_tokens']=min(kwargs.get('max_tokens') or 4096,4096)
            kwargs.setdefault('stats',{})
            try:
                async for piece in super().stream_chat(messages,**kwargs):yield piece
            finally:usage(record,kwargs['stats'])

        async def complete(self,messages,**kwargs):
            record=reserve(messages);stats={}
            kwargs['max_tokens']=min(kwargs.get('max_tokens') or 4096,4096)
            try:
                result=await super().complete(messages,**kwargs)
                stats={'usage':result.get('usage',{}),'finish_reason':'stop'}
                return result
            finally:usage(record,stats)

    tls=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    llm._client=BoundedClient(transport=httpx.AsyncHTTPTransport(verify=tls))
    def small_batch(question,documents):
        return [float(s) for s in reranker._local._load().predict(
            [(question,text) for text in documents],batch_size=2,show_progress_bar=False)]
    reranker._local.scores=small_batch
    search,pick=RagPipeline.search,RagPipeline.pick
    def checked_search(self,question,kb_ids):
        result=search(self,question,kb_ids)
        if result.mode!='hybrid' or not any(c.vector_score>0 for c in result.candidates):
            raise AppError(4002,'联调要求真实混合检索可用，未调用模型')
        return result
    def checked_pick(self,question,result):
        chosen=pick(self,question,result)
        if chosen and any(c.rerank_score is None for c in chosen):
            raise AppError(4002,'联调要求本地重排可用，未调用模型')
        return chosen
    RagPipeline.search,RagPipeline.pick=checked_search,checked_pick
