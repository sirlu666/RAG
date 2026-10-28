"""B3 · Prompt：五套题型示例及极限追问示例。

设计约束（对齐 01 §6 与 05 的评审结论）：
- 强制引用：资料片段的编号即 [n]，答案里必须能对上；
- 数学表达统一 LaTeX，避免模型输出 Unicode 上下标导致前端 KaTeX 渲染失败；
- 资料不足要拒答，不允许"合理推测"——数学编造代价最高；
- Few-shot 按题型选，不把所有样例都塞进去（省 token、少干扰）。
"""

from __future__ import annotations

import re

from app.rag.retriever import Candidate
from app.rag.context import build_retrieval_question, is_dependent_question

SYSTEM_PROMPT = """你是一名严谨的数学答疑老师。你只能依据【资料】回答学生的问题。

硬性规则（违反即视为错误回答）：
1. 只能使用本轮【资料】中的定义、定理、公式与结论作答；允许对题目及资料的表达式进行可验算的算术计算和代数恒等变形，不要求资料逐字给出原题答案。新定理或公式仍需资料支持；依据不足时直接回答"未找到依据"，说明缺少内容。禁止编造公式、结论或页码。
2. 先给结论，再给分步推导；每一步写清依据（定义 / 定理 / 公式）。
3. 数学表达一律用 LaTeX：行内 $...$，独立公式用 $$...$$。不要用 Unicode 数学符号。
4. 引用资料时在句末标注 [n]（n 为资料编号）。没有真正用到的资料不要标；不得虚构编号。
5. 语气简洁直接，不寒暄、不复述题目、不写"作为AI"。
6. 若【对话历史】里学生追问，结合上文理解指代，但答案仍必须落在【资料】上。
7. 输出前验算每次恒等变形、正负号与区间条件；尤其两个因子同时变号时乘积不变，不能误判为反号。按当前题目的函数重新计算导数；资料例题函数不同，不能复制其导数与极值结论。若历史回答存在计算或符号错误，明确纠正，不能沿用错误步骤。
8. 【示例资料】和 [示例n] 仅演示回答格式，不是本轮检索依据。正式回答的 [n] 只能指向最后一条用户消息的【资料n】，且该资料必须实际支持所引用的陈述。"""

SYSTEM_PROMPT += """
9. 区分资料中的数学依据与基础推理：算术、分配律、因式分解、零乘积性质、有限求和/乘积展开、初等计数及数学归纳法的逻辑框架可以自行使用，但必须展开关键步骤。这些基础推理不必在资料中逐字出现，也不能伪称资料给出。新定义、专门定理和判别条件仍须本轮资料支持；缺少这些依据应拒答，不能从示例借用。
10. 证明题必须完成原题要求的证明，不能只引用原题的结论。有限乘积展开应说明系数如何得到；比较随参数变化的和式时要比较每个已有项，并处理新增项；上界估计须写出理由。求和恒等式可通过成对相加或归纳现场证明。资料中的例题不等于原题，但资料中的定义和判别准则可以应用于原题。
11. 回答保留结论、必要推导与真实引用，避免重复相同公式和无关补充。追问只展开所问步骤，不重新抄写整道题。"""

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
    "extremum": [
        {
            "role": "user",
            "content": "【资料1】求可导函数极值：先令 f'(x)=0 求驻点，再用 f''(x) 的符号或一阶导变号判断极值点与极值。[1]\n\n问题：求函数 f(x)=x^3-3x 的极值。",
        },
        {
            "role": "assistant",
            "content": "先求导找驻点，再判号。\n\n$$f'(x)=3x^{2}-3=3(x-1)(x+1)$$\n\n令 $f'(x)=0$ 得驻点 $x=\\pm1$。由 $f'(x)$ 的符号变化：\n\n- $x<-1$ 时 $f'(x)>0$，$-1<x<1$ 时 $f'(x)<0$，故 $x=-1$ 处取极大值 $f(-1)=2$；\n- $-1<x<1$ 时 $f'(x)<0$，$x>1$ 时 $f'(x)>0$，故 $x=1$ 处取极小值 $f(1)=-2$[1]。",
        },
    ],
    "sequence_proof": [
        {
            "role": "user",
            "content": "【资料1】证明数列极限常先求通项或构造单调有界：单调递增且有上界的数列必收敛（单调有界准则）。[1]\n\n问题：证明数列 a_n=(1+1/n)^n 单调递增且有上界，从而收敛。",
        },
        {
            "role": "assistant",
            "content": "用二项式展开比较 $a_n$ 与 $a_{n+1}$。\n\n$$a_n=\\left(1+\\frac1n\\right)^{n}=\\sum_{k=0}^{n}\\binom{n}{k}\\frac{1}{n^{k}}$$\n\n逐项比较可证 $a_{n+1}\\ge a_n$（各项非负且 $a_{n+1}$ 展开多出正项），故 $\\{a_n\\}$ 单调递增；再由 $a_n=\\sum_{k=0}^{n}\\binom{n}{k}n^{-k}\\le\\sum_{k=0}^{n}\\frac{1}{k!}<3$，得 $\\{a_n\\}$ 有上界。\n\n由单调有界准则，$\\{a_n\\}$ 收敛[1]。",
        },
    ],
}

_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("sequence_proof", ("数列", "收敛", "单调有界", "递推", "通项", "极限存在")),
    ("extremum", ("极值", "最值", "极大", "极小", "最大值", "最小值", "驻点", "拐点")),
    ("proof", ("证明", "求证", "反证", "数学归纳", "证：")),
    ("equation", ("方程", "解方程", "求根", "不等式", "方程组", "解集")),
    ("function", ("函数", "单调", "定义域", "值域", "奇偶", "周期", "图像", "对称轴", "导数")),
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

    # A short follow-up has no subject keywords of its own. Use only the user
    # anchor for example selection, while preserving the actual question below.
    few_shot_key = select_few_shot(build_retrieval_question(question, history))
    if history and is_dependent_question(question):
        messages[0]['content'] += (
            '\n追问解释应只展开被问到的等式或依据。先明确变量大小关系，再逐项验算等式两边；'
            '不要扩展到本题不需要的判别式。上下文不能唯一确定所指步骤时，明确说明所解释的等式。'
            '若追问另一种解法，可用资料中的其他定理或公式重新推导，不要求资料逐字写出“第二种解法”。'
            '若仍无依据，整个回答必须直接以“未找到依据”开头，不在前面添加标题或“结论”。'
        )
    if few_shot_key:
        messages.extend({**example, 'content': re.sub(
            r'\[(\d+)\]', r'[示例\1]', example['content'].replace('【资料', '【示例资料')
        )} for example in _FEW_SHOTS[few_shot_key])
    elif history and is_dependent_question(question) and '极限' in build_retrieval_question(question, history):
        messages.extend([
            {'role':'user','content':'【示例资料】t→0 时 e^t=1+t+o(t)。历史问题：(e^t-1)/t 的极限，已直接引用重要极限得 1。追问：还有其他解法吗？'},
            {'role':'assistant','content':'可以从示例资料的展开式推导：$(e^t-1)/t=1+o(t)/t$，由 $o(t)/t\\to0$ 得极限为 $1$。这与直接引用重要极限不同。正式作答应同样逐项检查本轮资料的可用公式，依据公式推导，而非要求资料逐字写出另一解法；此处示例不是正式引用来源。'},
        ])

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
