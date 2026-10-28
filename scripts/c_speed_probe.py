"""Optional bootstrap probe using already-loaded models; never calls an LLM."""
import json
import time


def probe(data):
    from app.core.config import settings
    from app.db.models import KnowledgeBase
    from app.db.session import SessionLocal
    from app.rag.context import build_retrieval_question
    from app.rag.pipeline import RagPipeline
    with SessionLocal() as db:
        kb = db.query(KnowledgeBase).filter_by(name='数学真实联调资料').one()
        pipeline = RagPipeline(db)
        anchor = [{'role': 'user', 'content': '判断函数 f(x)=x^2+2x 的单调性'}]
        questions = [
            ('monotonicity', anchor[0]['content'], None, True),
            ('boundary_followup', '为什么分界点是 x=-1？', anchor, True),
            ('limit', r'设 f(x)=ln(1+x)-x/(1+x)，求 x→0 时 f(x)/x^2 的极限。', None, True),
            ('out_of_domain', '如何给汽车更换机油？', None, False),
        ]
        rows = []
        for name, question, history, expected in questions:
            query = build_retrieval_question(question, history)
            start = time.perf_counter()
            result = pipeline.search(query, [kb.id])
            middle = time.perf_counter()
            selected = pipeline.pick(query, result)
            end = time.perf_counter()
            confidence = pipeline.confidence(selected)
            accepted = not pipeline.should_refuse(selected, confidence)
            rows.append({'case': name, 'retrieval_ms': round((middle-start)*1000),
                         'rerank_ms': round((end-middle)*1000), 'total_ms': round((end-start)*1000),
                         'confidence': confidence, 'accepted': accepted, 'expected_accepted': expected,
                         'gate_matches': accepted == expected, 'citations': len(selected)})
        start = time.perf_counter()
        repeated = pipeline.search(anchor[0]['content'], [kb.id])
        middle = time.perf_counter()
        pipeline.pick(anchor[0]['content'], repeated)
        repeat_rerank_ms = round((time.perf_counter()-middle)*1000, 2)
    report = {'thinking': settings.llm_thinking, 'rerank_pool': settings.rerank_candidate_limit,
              'rerank_max_length': settings.rerank_max_length, 'threshold': settings.relevance_threshold,
              'local_cases': rows, 'repeat_rerank_ms': repeat_rerank_ms, 'paid_calls': 0}
    output = data / 'speed-optimization-20261028'
    output.mkdir(exist_ok=True)
    (output / 'local-probe.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False), flush=True)
