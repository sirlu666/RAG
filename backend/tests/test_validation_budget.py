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


@pytest.mark.parametrize('maximum,usd',[(27,'.30'),(26,'.31'),(0,'.30'),(26,'0')])
def test_unapproved_limits_are_rejected(maximum,usd):
    with pytest.raises(ValueError):
        verification.RequestBudget(maximum,usd)
