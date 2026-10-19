"""整页多模态转录（VLM）：一页图片 → 结构化 Markdown。

为什么需要它：
rapidocr 只做"逐行文字"，遇到表格会压成一行、行内公式会丢符号、矩阵会转成垃圾 LaTeX。
VLM 直接把整页当输入，能同时给出阅读顺序、表格结构与公式的 LaTeX。

用法：OCR_ENGINE=vlm，并配置 VLM_API_BASE / VLM_API_KEY / VLM_MODEL（OpenAI 兼容接口）。
"""

from __future__ import annotations

import base64
import io
import logging
import re

from app.core.config import settings
from app.core.exceptions import AppError

logger = logging.getLogger("mathrag.vlm")

PROMPT = """你是数学教材的文档转录器。请把这一页扫描图完整转录为 Markdown。

规则：
1. 只转录，不要总结、不要改写、不要补充图中没有的内容；
2. 行内公式用 $...$，独立公式用 $$...$$，公式必须写成合法 LaTeX；
3. 表格用 Markdown 表格，保留表头与行列对应关系；
4. 保留题号、选项 (A)(B)(C)(D) 与"例 1.1 / 习题 1.2"这类编号；
5. 页眉页脚、二维码、公众号引流文字不要转录；
6. 实在无法辨认的内容写 [不清]，不要猜测；
7. 只输出 Markdown 正文，不要任何解释、不要代码块围栏。"""


def _encode(img) -> str:
    from PIL import Image

    buffer = io.BytesIO()
    Image.fromarray(img).save(buffer, format="PNG", optimize=True)
    return base64.b64encode(buffer.getvalue()).decode()


def _post(payload: dict) -> str:
    import httpx

    base = settings.vlm_api_base.rstrip("/")
    if not base or not settings.vlm_api_key:
        raise AppError(2003, "未配置 VLM：请设置 VLM_API_BASE / VLM_API_KEY（或改用 OCR_ENGINE=rapid）")

    last_error: Exception | None = None
    for attempt in range(3):
        try:
            resp = httpx.post(
                f"{base}/chat/completions",
                headers={"Authorization": f"Bearer {settings.vlm_api_key}"},
                json=payload,
                timeout=settings.vlm_timeout,
            )
            if resp.status_code == 429:  # 限流，退避后重试
                raise RuntimeError("rate limited")
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"] or ""
        except Exception as exc:  # 网络抖动/限流
            last_error = exc
            logger.warning("vlm attempt %d failed: %s", attempt + 1, str(exc)[:180])
    raise AppError(4001, f"VLM 转录失败：{last_error}")


def page_to_markdown(img, page_no: int | None = None) -> str:
    """一页图片 → Markdown。失败抛 AppError，由上层决定是否降级到 OCR。"""
    payload = {
        "model": settings.vlm_model,
        "temperature": 0,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{_encode(img)}"},
                    },
                ],
            }
        ],
    }
    md = _post(payload).strip()
    md = re.sub(r"^```(?:markdown|md)?\s*", "", md)
    md = re.sub(r"\s*```$", "", md)
    return _guard(_normalize_math(md), page_no)


def _normalize_math(md: str) -> str:
    """把 LaTeX 定界符统一成 $ / $$：\\(...\\) → $...$，\\[...\\] → $$...$$。

    切片器的公式保护只认 $ 定界，不归一化的话行内公式会当普通文本被切开。
    """
    md = re.sub(r"\\\((.+?)\\\)", lambda m: f"${m.group(1).strip()}$", md, flags=re.S)
    md = re.sub(r"\\\[(.+?)\\\]", lambda m: f"$$\n{m.group(1).strip()}\n$$", md, flags=re.S)
    return md


def _guard(md: str, page_no: int | None) -> str:
    """基本质量门禁：公式定界符必须成对，否则该页标记待人工复核。"""
    dollars = md.count("$") - 2 * md.count("$$")
    if dollars % 2 != 0:
        logger.warning("page %s: 行内公式 $ 不成对，建议人工复核", page_no)
    if md.count("$$") % 2 != 0:
        logger.warning("page %s: 块级公式 $$ 不成对，建议人工复核", page_no)
    if len(md) < 20:
        logger.warning("page %s: 转录内容过少（%d 字）", page_no, len(md))
    return md
