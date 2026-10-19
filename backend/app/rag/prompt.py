"""B3 · Prompt 体系：System + 三套 Few-shot（方程 / 函数 / 证明）。

设计约束（对齐 01 §6 与 05 的评审结论）：
- 强制引用：资料片段的编号即 [n]，答案里必须能对上；
- 数学表达统一 LaTeX，避免模型输出 Unicode 上下标导致前端 KaTeX 渲染失败；
- 资料不足要拒答，不允许"合理推测"——数学编造代价最高；
- Few-shot 按题型选，不把所有样例都塞进去（省 token、少干扰）。
"""

from __future__ import annotations

from app.rag.retriever import Candidate

SYSTEM_PROMPT = """你是一名严谨的数学答疑老师。你只能依据【资料】回答学生的问题。

硬性规则（违反即视为错误回答）：
1. 只能使用【资料】中的定义、定理、公式与结论作答；资料不足以支撑时，直接回答"未找到依据"，并说明缺少哪部分内容。禁止编造公式、结论或页码。
2. 先给结论，再给分步推导；每一步写清依据（定义 / 定理 / 公式）。
3. 数学表达一律用 LaTeX：行内 $...$，独立公式用 $$...$$。不要用 Unicode 数学符号。
4. 引用资料时在句末标注 [n]（n 为资料编号）。没有真正用到的资料不要标；不得虚构编号。
5. 语气简洁直接，不寒暄、不复述题目、不写"作为AI"。
6. 若【对话历史】里学生追问，结合上文理解指代，但答案仍必须落在【资料】上。"""

_FEW_SHOTS: dict[str, list[dict[str, str]]] = {
    "equation": [
        {
            "role": "user",
            "content": "【资料1】解一元二次方程 ax^2+bx+c=0（a≠0）可用求根公式 x=(-b±√(b^2-4ac))/(2a)，判别式 Δ=b^2-4ac。[1]\n\n问题：解方程 x^2-5x+6=0。",
        },
        {
            "role": "assistant",
            "content": "先算判别式，再代入求根公式。\n\n$$\\Delta=(-5)^2-4\\cdot1\\cdot6=25-24=1>0$$\n\n方程有两个不等实根：\n\n$$x=\\frac{5\\pm\\sqrt{1}}{2}=\\frac{5\\pm1}{2}$$\n\n所以 $x_1=2$，$x_2=3$[1]。",
        },
    ],
    "function": [
        {
            "role": "user",
            "content": "【资料1】对区间 D 上任意 x1<x2，若都有 f(x1)<f(x2)，则 f(x) 在 D 上单调递增；配方法可把二次函数化为 a(x-h)^2+k 的形式。[1]\n\n问题：判断 f(x)=x^2+2x 的单调性。",
        },
        {
            "role": "assistant",
            "content": "配方后看对称轴与开口方向。\n\n$$f(x)=x^{2}+2x=(x+1)^{2}-1$$\n\n这是开口向上的抛物线，对称轴为 $x=-1$，所以：\n\n- 在 $(-\\infty,-1]$ 上单调递减\n- 在 $[-1,+\\infty)$ 上单调递增\n\n与增函数的定义一致[1]。",
        },
    ],
    "proof": [
        {
            "role": "user",
            "content": "【资料1】证明不等式常用作差比较法：要证 A>B，只需证 A-B>0，并把差化为完全平方或显然非负的形式。[1]\n\n问题：证明对任意实数 x，都有 x^2+1>2x。",
        },
        {
            "role": "assistant",
            "content": "用作差法，把差配成完全平方。\n\n$$x^{2}+1-2x=(x-1)^{2}\\ge 0$$\n\n且仅当 $x=1$ 时取等号。因此 $x^{2}+1\\ge 2x$，当 $x\\neq1$ 时严格大于[1]。",
        },
    ],
}

_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("proof", ("证明", "求证", "反证", "数学归纳", "证：")),
    ("equation", ("方程", "解方程", "求根", "不等式", "方程组", "解集")),
    ("function", ("函数", "单调", "定义域", "值域", "奇偶", "周期", "图像", "对称轴", "导数", "极值")),
]


def select_few_shot(question: str) -> str | None:
    """按关键词选题型样例；判不出来就不加 Few-shot（宁缺毋滥）。"""
    for name, words in _KEYWORDS:
        if any(w in question for w in words):
            return name
    return None


def build_context_block(candidates: list[Candidate]) -> str:
    if not candidates:
        return "（无相关资料）"
    blocks: list[str] = []
    for i, cand in enumerate(candidates, start=1):
        page = f" 第{cand.page}页" if cand.page else ""
        blocks.append(f"【资料{i}】({cand.doc_name}{page})\n{cand.content.strip()}")
    return "\n\n".join(blocks)


def build_messages(
    question: str,
    candidates: list[Candidate],
    history: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]

    few_shot_key = select_few_shot(question)
    if few_shot_key:
        messages.extend(_FEW_SHOTS[few_shot_key])

    parts: list[str] = [build_context_block(candidates)]

    if history:
        lines = []
        for msg in history:
            role = "学生" if msg["role"] == "user" else "老师"
            content = msg["content"].strip()
            if content:
                lines.append(f"{role}：{content}")
        if lines:
            parts.append("【对话历史（供理解指代，不能作为依据）】\n" + "\n".join(lines))

    parts.append(f"【问题】\n{question.strip()}")
    messages.append({"role": "user", "content": "\n\n".join(parts)})
    return messages


REFUSAL_TEMPLATE = (
    "未找到依据：知识库中没有能支撑这个问题的内容"
    "（最高相关度 {score:.2f}，低于阈值 {threshold:.2f}）。\n\n"
    "建议先补充对应的教材章节或讲义，再提问。"
)
