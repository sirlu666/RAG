from app.core.config import settings
from app.rag import reranker
from app.rag.pipeline import RagPipeline
from app.rag.retriever import Candidate, RetrievalResult


def test_exact_score_cache_preserves_order_and_recomputes_changed_text(monkeypatch):
    calls = []
    class Model:
        def predict(self, pairs, **kwargs):
            calls.append(pairs)
            return [len(text) / 100 for question, text in pairs]
    local = reranker._LocalReranker()
    monkeypatch.setattr(local, '_load', lambda: Model())
    assert local.scores('q', ['long text', 'a', 'long text']) == [.09, .01, .09]
    assert len(calls) == 1 and len(calls[0]) == 2
    assert local.scores('q', ['a', 'long text']) == [.01, .09]
    assert len(calls) == 1
    assert local.scores('q', ['new version']) == [.11]
    assert len(calls) == 2


def candidate(n, text=None):
    return Candidate(chunk_id=str(n), kb_id='kb', doc_id=str(n), doc_name='doc', content=text or str(n))


def test_rerank_bounds_pool_without_changing_threshold(monkeypatch):
    monkeypatch.setattr(settings, 'rerank_provider', 'local')
    monkeypatch.setattr(settings, 'rerank_candidate_limit', 6)
    threshold = settings.relevance_threshold
    seen = []
    def score(question, candidates):
        seen.extend(candidates)
        return [.9] * len(candidates)
    monkeypatch.setattr(reranker, '_rerank_local', score)
    result = reranker.rerank('q', [candidate(n) for n in range(20)], top_n=5)
    assert len(seen) == 6 and len(result) == 5
    assert settings.relevance_threshold == threshold


def test_duplicate_context_keeps_first_real_source(monkeypatch):
    monkeypatch.setattr(settings, 'rerank_provider', 'none')
    result = RagPipeline(None).pick('q', RetrievalResult(candidates=[candidate(1, 'f(x)=1'), candidate(2, ' f(x)=1 \n')]))
    assert len(result) == 1 and result[0].doc_id == '1'
