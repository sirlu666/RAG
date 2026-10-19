"""导出后端 OpenAPI 到 docs/api/openapi.json（B → C 的机器可读契约）。

为什么要有静态文件：C 不必先起后端就能 `openapi-typescript` 生成类型；
后端接口有任何改动，跑一次本脚本并把 json 一起提交，契约就不会漂。

用法（仓库根目录）：
    python scripts/dump_openapi.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.main import app  # noqa: E402

OUT = ROOT / "docs" / "api" / "openapi.json"

DESCRIPTION = (
    "MathRAG 后端契约（A 文档链路 + B 问答链路）。"
    "SSE 事件模型见 docs/B-接口与边界.md 与 docs/api/mock/chat_stream.txt。"
)


def main() -> None:
    spec = app.openapi()
    spec.setdefault("info", {})["description"] = DESCRIPTION
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"写入 {OUT.relative_to(ROOT)}（{len(spec['paths'])} 个路径）")
    for path in sorted(spec["paths"]):
        methods = ",".join(sorted(m.upper() for m in spec["paths"][path]))
        print(f"  {methods:12s} {path}")


if __name__ == "__main__":
    main()
