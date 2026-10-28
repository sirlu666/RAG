"""A-02 标签消费约定测试：doc_tags_out 输出 + /api/docs 附加字段 + metadata 序列化。"""

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.rag.indexer import _doc_tags
from app.services.doc_service import doc_tags_out


class _Doc:
    def __init__(self, tags_json):
        self.tags_json = tags_json


def test_doc_tags_out_untagged():
    assert doc_tags_out(_Doc(None)) == {
        "knowledge_points": [],
        "question_types": [],
        "difficulty": None,
    }


def test_doc_tags_out_valid():
    tags = json.dumps({
        "knowledge_points": ["泰勒公式", "麦克劳林公式"],
        "question_types": ["计算题"],
        "difficulty": "进阶",
    })
    out = doc_tags_out(_Doc(tags))
    assert out["knowledge_points"] == ["泰勒公式", "麦克劳林公式"]
    assert out["difficulty"] == "进阶"


def test_doc_tags_out_bad_json_and_enum():
    # 坏 JSON → 空
    assert doc_tags_out(_Doc("{not json"))["knowledge_points"] == []
    # 非法难度 → None
    bad = json.dumps({"knowledge_points": ["x"], "difficulty": "超难"})
    assert doc_tags_out(_Doc(bad))["difficulty"] is None


def test_doc_tags_metadata_scalar_only():
    """Chroma metadata 只接受标量：_doc_tags 必须把 list 序列化成字符串。"""
    tags = json.dumps({
        "knowledge_points": ["伴随矩阵", "行列式"],
        "question_types": ["计算题"],
        "difficulty": "基础",
    })
    meta = _doc_tags(_Doc(tags))
    # 所有值必须是标量（str/int/float/bool），不能是 list/dict
    for v in meta.values():
        assert isinstance(v, (str, int, float, bool)), f"{v!r} 不是标量"
    # tags_json 以 JSON 字符串形式冗余，difficulty 单独存标量
    assert meta["tags_json"] == tags
    assert meta["difficulty"] == "基础"
    # 反序列化可还原
    assert json.loads(meta["tags_json"])["knowledge_points"][0] == "伴随矩阵"


def test_doc_tags_metadata_untagged():
    assert _doc_tags(_Doc(None)) == {}


def test_list_docs_exposes_tag_fields():
    """接口契约：/api/docs 列表项必须带 knowledge_points/question_types/difficulty 字段。"""
    with TestClient(app) as client:
        resp = client.get("/api/docs")
    assert resp.status_code == 200
    items = resp.json()["data"]
    for it in items:
        assert "knowledge_points" in it
        assert "question_types" in it
        assert "difficulty" in it
        assert isinstance(it["knowledge_points"], list)
        assert isinstance(it["question_types"], list)
