"""RRF preservation, context-aware follow-ups and unchanged permissions/protocol."""
import json

import pytest

from app.core.config import settings
from app.db.chat_models import Message
from app.db.session import SessionLocal
from app.rag import pipeline, reranker
from app.rag.context import build_retrieval_question
from app.rag.retriever import Candidate, RetrievalResult


def cand(key, *, vector=.9, rrf=.02, tags=''):
    return Candidate(chunk_id=key, kb_id='kb', doc_id=key, doc_name=key+'.md',
                     content=key, vector_score=vector, rrf_score=rrf, tags_json=tags)


@pytest.mark.parametrize('failure', [False, True])
@pytest.mark.parametrize('mode', ['hybrid', 'vector'])
def test_unlabelled_primary_order_survives_rerank_fallback(monkeypatch, mode, failure):
    first = cand('rrf-first', vector=.7, rrf=.03)
    second = cand('vector-first', vector=.9, rrf=.02)
    ordered = [first, second] if mode == 'hybrid' else [second, first]
    monkeypatch.setattr(settings, 'rerank_provider', 'local' if failure else 'none')
    def boom(*args):
        raise RuntimeError('isolated rerank failure')
    monkeypatch.setattr(reranker, '_rerank_local', boom)
    output = pipeline.RagPipeline(None).pick('no tag', RetrievalResult(candidates=ordered, mode=mode))
    assert [c.chunk_id for c in output] == [c.chunk_id for c in ordered]


@pytest.mark.parametrize('mode', ['hybrid', 'vector'])
def test_tags_break_only_primary_score_ties(monkeypatch, mode):
    monkeypatch.setattr(settings, 'rerank_provider', 'none')
    tags = json.dumps({'knowledge_points': ['泰勒公式']})
    top = cand('primary-top', vector=.9, rrf=.04)
    plain = cand('plain', vector=.7, rrf=.03)
    matched = cand('matched', vector=.7, rrf=.03, tags=tags)
    result = RetrievalResult(candidates=[top, plain, matched], mode=mode)
    output = pipeline.RagPipeline(None).pick('泰勒公式', result)
    assert [c.chunk_id for c in output] == ['primary-top', 'matched', 'plain']
    assert [c.relevance for c in output] == [.9, .7, .7]
    assert matched.tag_rank == 0  # No mutation of the retriever's candidates.


def test_successful_rerank_uses_rerank_then_tag(monkeypatch):
    monkeypatch.setattr(settings, 'rerank_provider', 'local')
    monkeypatch.setattr(reranker, '_rerank_local', lambda q, cs: [.8 for c in cs])
    first = cand('first', rrf=.03)
    tagged = cand('tagged', rrf=.01, tags='{"knowledge_points":["泰勒公式"]}')
    output = pipeline.RagPipeline(None).pick('泰勒公式', RetrievalResult(candidates=[first, tagged]))
    assert [c.chunk_id for c in output] == ['tagged', 'first']
    assert all(c.relevance == .8 for c in output)


HISTORY = [
    {'role': 'user', 'content': '判断 f(x)=x^2+2x 的单调性'},
    {'role': 'assistant', 'content': '本段含模型生成内容，不能作为检索依据'},
]


@pytest.mark.parametrize('question', ['第二步为什么这样变形？', '第二种解法是什么？', '（接上题）继续解释这一步'])
def test_followup_anchors_only_to_user_question(question):
    query = build_retrieval_question(question, HISTORY)
    assert HISTORY[0]['content'] in query and question in query
    assert HISTORY[1]['content'] not in query


def test_repeated_followup_finds_independent_anchor():
    history = HISTORY + [{'role': 'user', 'content': '第二步为什么这样变形？'},
                         {'role': 'assistant', 'content': '解释'}]
    assert HISTORY[0]['content'] in build_retrieval_question('第二种解法是什么？', history)


@pytest.mark.parametrize('question', ['求方程 x^2-3x+2=0 的根', '新问题：第二步为什么这样变形？', '换个题：求极值',
                                    '请换个题：第二步怎么算？', '我们现在换题，第二步怎么算？',
                                    '解方程 x^2-1=0，并解释第二步', '已知函数 f(x)=x^2，解释解题第二步'])
def test_independent_or_new_topic_is_not_rewritten(question):
    assert build_retrieval_question(question, HISTORY) == question


@pytest.mark.parametrize('history', [None, [], [{'role': 'assistant', 'content': '猜测的锚点'}]])
def test_missing_user_anchor_preserves_question(history):
    assert build_retrieval_question('第二种解法是什么？', history) == '第二种解法是什么？'


def test_query_budget_keeps_current_question(monkeypatch):
    monkeypatch.setattr(settings, 'history_char_budget', 70)
    history = [{'role': 'user', 'content': '原始数学问题'*100}]
    question = '第二步为什么这样变形？'
    query = build_retrieval_question(question, history)
    assert len(query) <= 70 and query.endswith(question)


def test_followup_retrieval_and_persistence_keep_scope_and_original_question(client, seeded, alice_headers, bob_headers, monkeypatch):
    captured = []
    retrieve = pipeline.retrieve
    def observe(db, question, kb_ids):
        captured.append((question, kb_ids))
        return retrieve(db, question, kb_ids)
    monkeypatch.setattr(pipeline, 'retrieve', observe)
    first = client.post('/api/chat/stream', headers=alice_headers,
                        json={'kb_ids': [seeded['kb_id']], 'question': '增函数的定义是什么', 'stream': False})
    assert first.status_code == 200
    conversation = first.json()['data']['conversation_id']
    question = '第二步为什么这样变形？'
    follow = client.post('/api/chat/stream', headers=alice_headers,
                         json={'kb_ids': [seeded['kb_id']], 'conversation_id': conversation,
                               'question': question, 'stream': False})
    assert follow.status_code == 200
    assert '增函数的定义是什么' in captured[-1][0] and question in captured[-1][0]
    assert captured[-1][1] == [seeded['kb_id']]
    with SessionLocal() as db:
        assert db.query(Message).filter(Message.conversation_id == conversation, Message.role == 'user',
                                        Message.content == question).count() == 1
    count = len(captured)
    denied = client.post('/api/chat/stream', headers=bob_headers,
                         json={'kb_ids': [seeded['kb_id']], 'conversation_id': conversation, 'question': question})
    assert denied.status_code == 403 and len(captured) == count
