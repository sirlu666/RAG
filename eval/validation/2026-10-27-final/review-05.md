# 数学复核材料 5

用户已要求 agent 自行核对；AI 复核结论另见 AI-REVIEW.md。本材料不包含虚构的人工通过结论。

## h018

题目：求极限 lim(x→0) sinx/x

检查要点（原表）：=1（两个重要极限）

模型完整回答：

**结论：**
$$\lim_{x\to 0}\frac{\sin x}{x}=1$$

**推导依据：**
该极限是资料中给出的第一个重要极限，直接由公式得出 [1]：
$$\lim_{x \to 0} \frac{\sin x}{x} = 1$$

资料未给出该公式的证明过程，故不补充推导步骤。

检索问题：

求极限 lim(x→0) sinx/x

### 资料 [1] 1-1. 函数的极限与连续__两个重要极限.md / seq=0

切片 ID：`ch_76e3da32aadc`；文档 SHA256：`231893aacf031c592fcf711c5ce03a2c612fdc040a50a8e99b74f4245fecbb8b`

## 1. $\sin x / x$

$$ \lim_{x \to 0} \frac{\sin x}{x} = 1 $$

### 图像

![important_1](assets/important_1.jpg)

---

## 2. $(1+x)^\frac{1}{x}$

$$\lim_{x \to \infty} (1+\frac{1}{x})^x = e$$

### 图像

![important_2](assets/important_2.jpg)

### $x>0$ 时的性质

- $f(x)$ 单调减少
- $\lim_{x \to 0^+}f(x) = e$
- $(1+x)^\frac{1}{x} \sim -\frac{e}{2}x ~ (x \to 0^+)$

### 变式

$$\lim_{x \to \infty} (1+x)^\frac{1}{x} = e$$

#### 图像

![important_2](assets/important_2-1.jpg)

**提示**
> *变量广义化，超级小狗！*

人工判定：未进行。AI 复核见单独报告。
