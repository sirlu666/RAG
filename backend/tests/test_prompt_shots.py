"""B-06 · Prompt few-shot 选题与数学正确性测试。

验证：
  - 五套 few-shot 齐全（方程/函数/证明/极值/数列证明）
  - 关键词优先级：数列证明优先于证明、极值优先于函数
  - few-shot 样例数学正确（含关键公式/结论，不引错误结论）
"""

from __future__ import annotations

from app.rag.prompt import _FEW_SHOTS, select_few_shot
from app.rag.prompt import build_messages, SYSTEM_PROMPT


def test_five_few_shots_present():
    assert set(_FEW_SHOTS.keys()) == {
        "equation", "function", "proof", "extremum", "sequence_proof",
    }


def test_select_extremum_over_function():
    # "极值" 已从 function 移到 extremum，优先级更高
    assert select_few_shot("求函数 f(x)=x^3-3x 的极值") == "extremum"


def test_select_sequence_proof_over_proof():
    # "证明数列" 应先命中 sequence_proof（更具体），而非 proof
    assert select_few_shot("证明数列 a_n 单调有界") == "sequence_proof"


def test_select_function_still_works():
    assert select_few_shot("判断函数单调性") == "function"


def test_select_unknown_returns_none():
    assert select_few_shot("今天天气怎么样") is None


def test_extremum_shot_math_correct():
    shot = _FEW_SHOTS["extremum"][1]["content"]
    # 极值结论正确：f(x)=x^3-3x 在 x=-1 极大值 2，x=1 极小值 -2
    assert "f(-1)=2" in shot
    assert "f(1)=-2" in shot
    assert "f'(x)=3x^{2}-3" in shot


def test_sequence_proof_shot_math_correct():
    shot = _FEW_SHOTS["sequence_proof"][1]["content"]
    # 数列 (1+1/n)^n 单调有界收敛，结论正确且引用 [1]
    assert "单调有界准则" in shot
    assert "[1]" in shot
    assert "收敛" in shot


def test_followup_uses_user_anchor_for_subject_example_and_keeps_original_question():
    question = '第二步为什么这样变形？'
    history = [{'role':'user','content':'判断函数单调性'},
               {'role':'assistant','content':'模型生成的证明数列文字不能决定题型'}]
    messages = build_messages(question, [], history)
    assert messages[1:3] == _FEW_SHOTS['function']
    assert messages[-1]['content'].endswith('【问题】\n'+question)


def test_independent_question_is_not_reclassified_from_history():
    history = [{'role':'user','content':'判断函数单调性'}]
    messages = build_messages('解方程 x^2-1=0', [], history)
    assert messages[1:3] == _FEW_SHOTS['equation']
    assert messages[0]['content'] == SYSTEM_PROMPT


def test_followup_without_user_anchor_does_not_select_example_from_assistant():
    messages = build_messages('第二种解法是什么？', [], [{'role':'assistant','content':'方程与函数'}])
    assert len(messages) == 2
