"""A leading formatted refusal is still a refusal; a trailing caveat is not."""
import pytest

from app.rag.pipeline import answer_declined


@pytest.mark.parametrize('answer', [
    '未找到依据：资料不足',
    '**结论：** 未找到依据。',
    '### 结论\n未找到依据',
    '**答案**：**未找到依据**',
    '> 未找到依据：资料不足',
])
def test_leading_formatted_refusal_is_declined(answer):
    assert answer_declined(answer)


@pytest.mark.parametrize('answer', [
    '结论：x=2。补充：未找到依据解释其他情况。',
    '由资料可得答案。\n未找到依据补充另一种解法。',
    '',
])
def test_answer_with_later_caveat_is_not_declined(answer):
    assert not answer_declined(answer)
