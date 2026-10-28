# 数学复核材料 4

用户已要求 agent 自行核对；AI 复核结论另见 AI-REVIEW.md。本材料不包含虚构的人工通过结论。

## h011

题目：（接上题）第二步为什么这样变形？

检查要点（原表）：能结合上文指代、答案仍落在资料

模型完整回答：

所解释的等式是第 3 步中的

$$f(x_2)-f(x_1)=(x_2+1)^{2}-(x_1+1)^{2}=(x_2-x_1)(x_1+x_2+2).$$

先明确变量大小关系：取定 $x_1<x_2$，故 $x_2-x_1>0$。

逐项验算等式两边：

1. 左边第一个等号：由配方 $f(x)=(x+1)^2-1$，得
$$f(x_2)-f(x_1)=\big[(x_2+1)^2-1\big]-\big[(x_1+1)^2-1\big]=(x_2+1)^2-(x_1+1)^2.$$
常数 $-1$ 相消。

2. 第二个等号用平方差公式 $A^2-B^2=(A-B)(A+B)$，取 $A=x_2+1$，$B=x_1+1$：
$$(x_2+1)^2-(x_1+1)^2=\big[(x_2+1)-(x_1+1)\big]\big[(x_2+1)+(x_1+1)\big]=(x_2-x_1)(x_1+x_2+2).$$

这样变形的目的：把 $f(x_2)-f(x_1)$ 写成“正因子 $x_2-x_1$”乘“一个因子”的形式，于是差的符号只由 $x_1+x_2+2$ 的符号决定，再按定义判别单调性[4]。

检索问题：

原问题：判断 f(x)=x^2+2x 的单调性
追问：（接上题）第二步为什么这样变形？

### 资料 [4] 张宇30讲原稿__第1讲-函数极限与连续.md / seq=20

切片 ID：`ch_31ea1dccd309`；文档 SHA256：`66593a017613895d78c2378d94fce645c5798a4d44cd7698281d731580b2af5c`

上是定义法，是充要条件。

(2) 后面会看到，在考研试题中常常用求导的方法来讨论函数在某个区间上的单调性，但是定义法不可以忘记。试题中也常用到如下定义法的判别形式，请考生留意。

对任意 $x_{1}, x_{2} \in D, x_{1} \neq x_{2}$，有

f(x) 是单调增函数  $\Leftrightarrow (x_{1}-x_{2})[f(x_{1})-f(x_{2})]>0$；

严格单调减  $\Leftrightarrow$

f(x) 是单调减函数  $\Leftrightarrow (x_{1}-x_{2})[f(x_{1})-f(x_{2})]<0$；

f(x) 是单调不减函数  $\Leftrightarrow (x_{1}-x_{2})[f(x_{1})-f(x_{2})]\geq0$；

f(x) 是单调不增函数  $\Leftrightarrow (x_{1}-x_{2})[f(x_{1})-f(x_{2})]\leq0$。

在考研数学中，函数的单调性虽然是基础知识，但也会有综合应用。

人工判定：未进行。AI 复核见单独报告。

## h012

题目：第二种解法是什么？

检查要点（原表）：给出资料中可支撑的替代解法或说明无

模型完整回答：

**结论：** 第二种解法可用等价无穷小代换：当 $x\to0$ 时，$e^x-1\sim x\sim\sin x$ [5]，故
$$\lim_{x\to0}\frac{\sin x}{x}=\lim_{x\to0}\frac{e^x-1}{x}.$$

**分步推导：**

1. 由资料公式，当 $x\to0$ 时 $e^x-1\sim x\sim\sin x$ [5]，即 $\sin x\sim x$，$e^x-1\sim x$。
2. 由等价无穷小代换，$\dfrac{\sin x}{x}$ 与 $\dfrac{e^x-1}{x}$ 在 $x\to0$ 时极限相同，故
$$\lim_{x\to0}\frac{\sin x}{x}=\lim_{x\to0}\frac{e^x-1}{x}.$$
3. 资料2中已出现 $\dfrac{e^x-1}{x}$ 在 $x\to0$ 时按 $e^x-1\sim x$ 化为 $1$ 的处理（见资料2第一行推导中 $\frac{e^x-1}{x}\to1$ 的用法）[2]，因此
$$\lim_{x\to0}\frac{e^x-1}{x}=1.$$
4. 所以 $\lim_{x\to0}\dfrac{\sin x}{x}=1$。

**说明：** 资料5只给出 $e^x-1\sim x\sim\sin x$ 这一等价关系 [5]，未单独给出 $\lim_{x\to0}\frac{e^x-1}{x}=1$ 的独立证明；上述第3步依据资料2中对 $\frac{e^x-1}{x}$ 的代换处理 [2]。

检索问题：

原问题：求极限 lim(x→0) sinx/x
追问：第二种解法是什么？

### 资料 [2] 张宇30讲原稿__第1讲-函数极限与连续.md / seq=152

切片 ID：`ch_e7ec1896e46f`；文档 SHA256：`66593a017613895d78c2378d94fce645c5798a4d44cd7698281d731580b2af5c`

$$ \begin{aligned}\lim_{x\to0}\left(\frac{\mathbf{e}^{x}+x\mathbf{e}^{x}}{\mathbf{e}^{x}-1}-\frac{1}{x}\right)&=\lim_{x\to0}\left(\frac{\mathbf{e}^{x}+x\mathbf{e}^{x}}{x}-\frac{1}{x}\right)\\&=\lim_{x\to0}\frac{\mathbf{e}^{x}+x\mathbf{e}^{x}-1}{x}=\lim_{x\to0}(2\mathbf{e}^{x}+x\mathbf{e}^{x})=2\end{aligned} $$

1.13 解 因为  $\lim_{x\to0}a_{i}^{x}=1$ ，所以原极限为 “ $1^{\infty}$” 型未定式.

方法一 使用洛必达法则求极限.

$$ \begin{aligned}\lim_{x\to0}\left(\frac{a_{1}^{x}+a_{2}^{x}+\cdots+a_{n}^{x}}{n}\right)^{\frac{n}{x}}&=\exp\left\{\lim_{x\to0}\frac{n}{x}\left(\frac{a_{1}^{x}+a_{2}^{x}+\cdots+a_{n}^{x}}{n}-1\right)\right\}\\&=\exp\left\{\lim_{x\to0}\frac{a_{1}^{x}-1}{x}+\lim_{x\to0}\frac{a_{2}^{x}-1}{x}+\cdots+\lim_{x\to0}\frac{a_{n}^{x}-1}{x}\right\}\\&=\exp\{\lim_{x\to0}(a_{1}^{x}\ln a_{1}+a_{2}^{x}\ln a_{2}+\cdots+a_{n}^{x}\ln a_{n})\}=a_{1}a_{2}\cdots a_{n}.\end{aligned} $$

方法二 凑成第二个重要极限（“1 $^{\circ}$”型未定式都可以凑成第二个重要极限），在计算过程中使用洛必达法则.

### 资料 [5] 张宇30讲原稿__第1讲-函数极限与连续.md / seq=103

切片 ID：`ch_2c287236e2e5`；文档 SHA256：`66593a017613895d78c2378d94fce645c5798a4d44cd7698281d731580b2af5c`

例1.21 设  $\lim_{x\to0}\frac{\sin x}{e^x-a}(\cos x-b)=5$，则  $b=$（ ）.

(A) -4 (B) -3 (C) -2 (D) -1

(♂分析) 先利用例 1.20 的结果求出 a 的值，再用等价无穷小的代换求 b 的值.

## 解 应选(A)

$\lim_{x\to0}\frac{\sin x}{e^x-a}(\cos x-b)=5\neq0$，由例1.20的(2)知， $\lim_{x\to0}(e^x-a)=0$，故a=1，此时原极限变为 $\lim_{x\to0}\frac{\sin x}{e^x-1}(\cos x-b)=\lim_{x\to0}(\cos x-b)=1-b$，故b=-4。

方法总结 若  $\lim_{x\to0}\frac{f(x)}{g(x)}=A\neq0$，且  $\lim_{x\to0}f(x)=0$，则  $\lim_{x\to0}g(x)=0$。

∅公式 当 $x \to 0$时， $e^x - 1 \sim x \sim \sin x$。

人工判定：未进行。AI 复核见单独报告。
