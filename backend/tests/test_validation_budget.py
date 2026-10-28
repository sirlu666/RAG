"""No real calls: enforce the explicit validation spending and request limits."""
import importlib.util
from pathlib import Path

import pytest

spec=importlib.util.spec_from_file_location('final_verification',Path(__file__).resolve().parents[2]/'scripts/verify_final_chain.py')
verification=importlib.util.module_from_spec(spec)
spec.loader.exec_module(verification)


def test_request_limit_cannot_be_exceeded():
    budget=verification.RequestBudget()
    for _ in range(26):
        budget.reserve([{'role':'user','content':'验证问题'}])
    assert budget.reserved < budget.cap
    with pytest.raises(ValueError,match='limit'):
        budget.reserve([{'role':'user','content':'another'}])
    assert budget.calls == 26


def test_cost_limit_blocks_before_request():
    budget=verification.RequestBudget(usd='.001')
    with pytest.raises(ValueError,match='limit'):
        budget.reserve([{'role':'user','content':'问题'}])
    assert budget.calls == 0


def test_oversized_input_is_not_sent():
    budget=verification.RequestBudget()
    with pytest.raises(ValueError,match='input|Input'):
        budget.reserve([{'role':'user','content':'数'*10000}])
    assert budget.calls == 0


@pytest.mark.parametrize('maximum,usd',[(71,'.60'),(26,'.61'),(0,'.30'),(26,'0')])
def test_unapproved_limits_are_rejected(maximum,usd):
    with pytest.raises(ValueError):
        verification.RequestBudget(maximum,usd)


def test_previous_calls_leave_only_authorized_balance():
    budget=verification.RequestBudget(maximum=1,previous_calls=69)
    assert budget.reserve([{'role':'user','content':'验证'}])['total_calls'] == 70
    with pytest.raises(ValueError):budget.reserve([{'role':'user','content':'再次验证'}])
    with pytest.raises(ValueError):verification.RequestBudget(maximum=2,previous_calls=69)


def test_previous_spending_cannot_be_reset_by_a_new_run():
    budget=verification.RequestBudget(maximum=1,previous_usd='.599')
    with pytest.raises(ValueError,match='limit'):budget.reserve([{'role':'user','content':'验证'}])
    assert budget.calls == 0


def test_raw_run_ledger_does_not_double_count_total_fields(tmp_path):
    import json
    from types import SimpleNamespace
    prior=tmp_path/'old'; prior.mkdir()
    (prior/'budget.json').write_text(json.dumps({'calls':19,'reserved_upper_usd':'.0967605','total_calls':38}))
    budget=verification.cumulative_budget(SimpleNamespace(output=tmp_path/'new',max_requests=21,budget_usd='.30'))
    assert budget.previous_calls == 19 and str(budget.previous_usd) == '0.0967605'


def test_output_limit_changes_reservation_and_enforces_approved_maximum():
    messages=[{'role':'user','content':'验证'}]
    short=verification.RequestBudget(max_output_tokens=2048)
    long=verification.RequestBudget(max_output_tokens=4096)
    short.reserve(messages);long.reserve(messages)
    assert long.reserved-short.reserved == 2048*verification.OUTPUT_RATE
    with pytest.raises(ValueError):verification.RequestBudget(max_output_tokens=4097)


@pytest.mark.parametrize('case_id,done,citations,answer,expected', [
    ('h015', {'refused':True,'first_token_ms':0}, [], '未找到依据', 'auto:pass'),
    ('h015', {'declined':True,'first_token_ms':20}, [{}], '未找到依据', 'auto:fail'),
    ('h016', {'refused':True}, [], '未找到依据', 'auto:pass'),
    ('h016', {'refused':True}, [{}], '未找到依据', 'auto:fail'),
    ('h017', {'declined':True}, [{}], '未找到依据：资料不足', 'auto:pass'),
    ('h017', {'refused':True}, [], '未找到依据', 'auto:fail'),
])
def test_behavior_checks_do_not_confuse_pipeline_refusal_with_model_decline(case_id,done,citations,answer,expected):
    assert verification.behavior_verdict(case_id,{'done':done,'citations':citations,'answer':answer}) == expected


def test_validation_preserves_partial_error_without_inventing_done():
    import httpx,json
    events=[('meta',{'conversation_id':'c'}),('citation',{'index':1}),('delta',{'text':'部分回答'}),
            ('error',{'code':4001,'message':'长度上限'})]
    body=''.join('event: '+name+'\ndata: '+json.dumps(data)+'\n\n' for name,data in events)
    with httpx.Client(base_url='http://validation',transport=httpx.MockTransport(
            lambda request:httpx.Response(200,content=body))) as client:
        answer=verification.ask(client,'kb','问题')
    assert not answer['completed'] and not answer['done']
    assert answer['error']['code']==4001 and answer['answer']=='部分回答'
    assert answer['stream_citations']==[{'index':1}]
