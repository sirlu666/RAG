"""标定脚本的纯函数测试（不碰数据库）。

只测统计与判读逻辑：这部分出错会让"建议阈值"静默失真，
比脚本跑不起来更危险，所以单独护住。
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import calibrate_threshold as ct  # noqa: E402


def test_percentile_handles_bounds_and_median():
    data = [0.0, 1.0, 2.0, 3.0, 4.0]
    assert ct.percentile(data, 0.0) == 0.0
    assert ct.percentile(data, 1.0) == 4.0
    assert ct.percentile(data, 0.5) == 2.0


def test_percentile_interpolates_between_points():
    # 4 个点时 p50 落在第 1、2 个之间（线性插值）
    assert ct.percentile([0.0, 2.0, 4.0, 6.0], 0.5) == 3.0


def test_percentile_handles_empty_and_single():
    assert ct.percentile([], 0.5) == 0.0
    assert ct.percentile([0.7], 0.9) == 0.7


def test_error_rates_counts_false_refusal_and_false_accept():
    pos = [0.5, 0.6, 0.4]  # 阈值 0.45 时 1 条会被误拒
    neg = [0.1, 0.5]  # 阈值 0.45 时 1 条会被误放行
    result = ct._error_rates(pos, neg, 0.45)
    assert result["false_refusal_rate"] == round(1 / 3, 4)
    assert result["false_accept_rate"] == round(1 / 2, 4)


def test_error_rates_returns_none_without_samples():
    assert ct._error_rates([], [0.1], 0.3) is None
    assert ct._error_rates([0.5], [], 0.3) is None
    assert ct._error_rates([0.5], [0.1], None) is None


def test_off_domain_questions_have_no_math_terms():
    """负样本要真的域外，否则标定结果偏乐观。抽查最常见的数学词不出现。"""
    banned = ["函数", "方程", "矩阵", "概率", "向量", "导数", "积分", "定理"]
    for q in ct.OFF_DOMAIN:
        assert not any(term in q for term in banned), f"负样本含数学词：{q}"
