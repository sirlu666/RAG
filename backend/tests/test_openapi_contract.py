"""B → C 的契约防漂移：静态 docs/api/openapi.json 必须与代码一致。

C 用这份 json 生成 TS 类型。如果后端改了字段却没重新导出，C 会在联调时才发现，
所以把"导出结果 == 仓库里的文件"做成测试；改动后跑：

    python scripts/dump_openapi.py
"""

from __future__ import annotations

import json
from pathlib import Path

from app.main import app

OPENAPI = Path(__file__).resolve().parents[2] / "docs" / "api" / "openapi.json"


def _load() -> dict:
    assert OPENAPI.exists(), f"缺少 {OPENAPI}，跑 python scripts/dump_openapi.py"
    return json.loads(OPENAPI.read_text(encoding="utf-8"))


def test_b_chat_endpoint_is_in_contract():
    spec = _load()
    op = spec["paths"]["/api/chat/stream"]["post"]
    assert "text/event-stream" in op["responses"]["200"]["content"]
    # 请求体字段是 C 生成类型的依据
    ref = op["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    assert ref.endswith("/ChatRequest")
    props = spec["components"]["schemas"]["ChatRequest"]["properties"]
    assert {"conversation_id", "kb_ids", "question", "stream"} <= set(props)


def test_static_openapi_matches_code():
    spec = _load()
    live = app.openapi()
    # 描述是导出脚本注入的，比较时忽略
    spec.get("info", {}).pop("description", None)
    live.get("info", {}).pop("description", None)

    assert set(spec["paths"]) == set(live["paths"]), "路径增删后忘记重新导出 openapi.json"
    for path, methods in live["paths"].items():
        for method, live_op in methods.items():
            assert spec["paths"][path][method] == live_op, f"{method.upper()} {path} 的契约已过期"
