# 数学复核材料 3

原始回答见 evidence.jsonl；以下仅整理排版。AI结论单列，人工字段未填写。

## h007

题目：证明数列 (1+1/n)^n 单调递增且有上界

原表检查要点：二项式展开比较 + 有上界，单调有界收敛

回答：

结论：数列 $\left\{\left(1+\frac1n\right)^n\right\}$ 严格单调递增且有上界 $3$，故由单调有界准则收敛；资料同时给出其极限为 $e$ [1][4]。

**1. 二项式展开**

由有限乘积展开（初等计数：从 $n$ 个因子中各选 $k$ 个取 $\frac1n$，有 $\binom nk$ 种选法），

$$
a_n=\left(1+\frac1n\right)^n
=\sum_{k=0}^{n}\binom nk\frac1{n^k}.
$$

又

$$
\binom nk\frac1{n^k}
=\frac{n(n-1)\cdots(n-k+1)}{k!\,n^k}
=\frac1{k!}\prod_{j=0}^{k-1}\left(1-\frac jn\right),
$$

其中 $k=0$ 时为空积，规定为 $1$。因此

$$
a_n=\sum_{k=0}^{n}\frac1{k!}\prod_{j=0}^{k-1}\left(1-\frac jn\right).
$$

**2. 证明单调递增**

对 $0\le k\le n$，因

$$
1-\frac{j}{n+1}\ge 1-\frac jn\qquad (0\le j\le k-1),
$$

所以

$$
\frac1{k!}\prod_{j=0}^{k-1}\left(1-\frac{j}{n+1}\right)
\ge
\frac1{k!}\prod_{j=0}^{k-1}\left(1-\frac jn\right).
$$

而 $a_{n+1}$ 还多出第 $k=n+1$ 项，且该项为正。因此

$$
a_{n+1}>a_n.
$$

故 $\left\{\left(1+\frac1n\right)^n\right\}$ 严格单调递增。

**3. 证明有上界**

由上式及 $\prod_{j=0}^{k-1}\left(1-\frac jn\right)\le 1$，得

$$
a_n\le \sum_{k=0}^{n}\frac1{k!}.
$$

又对 $k\ge1$，有 $k!\ge 2^{k-1}$，故

$$
a_n\le 1+\sum_{k=1}^{n}\frac1{2^{k-1}}.
$$

由有限等比数列求和公式 [1]，

$$
\sum_{m=0}^{n-1}\left(\frac12\right)^m
=\frac{1-\left(\frac12\right)^n}{1-\frac12}
=2-2^{1-n}.
$$

于是

$$
a_n\le 1+\left(2-2^{1-n}\right)
=3-2^{1-n}<3.
$$

所以 $0<a_n<3$，即数列有上界 $3$；按有界数列定义，存在正实数 $M=3$，使 $|a_n|\le M$ [1]。

**4. 由准则得收敛**

该数列单调递增且有上界，由单调有界准则知 $\lim_{n\to\infty}\left(1+\frac1n\right)^n$ 存在 [2]。资料另给出该极限为 $e$ [1][4]。

正常结束原因：`stop`

### [1] 张宇30讲原稿__第2讲-数列极限.md / ch_38dcafd6cbf0

例如，若  $n_{k}(k=1,2,\cdots)$ 分别取 2k 和 2k-1，则得到数列  $\{a_{n}\}$ 的两个子列

$$ \{a_{2k}\}\colon a_{2},\;a_{4},\cdots,\;a_{2k},\cdots;\;\{a_{2k-1}\}\colon a_{1},\;a_{3},\cdots,\;a_{2k-1},\cdots, $$

这两个子列的项在原数列中交错出现。

(2) 等差数列.

首项为  $a_{1}$，公差为  $d(d \neq 0)$ 的数列  $a_{1}, a_{1} + d, a_{1} + 2d, \cdots, a_{1} + (n - 1)d, \cdots$.

①通项公式 $a_{n}=a_{1}+(n-1)d$

②前 n 项的和  $S_{n}=\frac{n}{2}\left[2a_{1}+(n-1)d\right]=\frac{n}{2}(a_{1}+a_{n})$

(3) 等比数列.

首项为  $a_{1}$，公比为  $r(r \neq 0)$ 的数列  $a_{1}, a_{1}r, a_{1}r^{2}, \cdots, a_{1}r^{n-1}, \cdots$.

①通项公式 $a_{n}=a_{1}r^{n-1}$

②前 n 项的和

$$
S_{n}=\begin{cases}na_{1},&r=1,\\\dfrac{a_{1}(1-r^{n})}{1-r},&r\neq1.\end{cases}
$$

③常用  $1+r+r^{2}+\cdots+r^{n-1}=\frac{1-r^{n}}{1-r}(r\neq1)$ →有限项和不会发散，收敛和发散的概念，只在无穷项时会涉及

这两个求和公式针对的前n项和，即有限项和，当讨论无限项和时，需要使用无穷级数理论

(4) 单调数列.

若对所有正整数  $n$，有  $a_{n+1} \geqslant a_n (a_{n+1} \leqslant a_n)$，则称数列  $\{a_n\}$ 为单调不减（不增）数列。将  $\geqslant (\leqslant)$ 换成  $> (<)$，则称为单调递增（递减）数列。单调递增数列与单调递减数列统称为单调数列。

(5) 有界数列.

若对所有正整数  $n$，存在正实数  $M$，有  $|a_n| \leq M$，则称数列  $\{a_n\}$ 为有界数列。

①找 M，使得  $|a_n| \leqslant M$；

证明数列有界的几种方法：

②放缩法；

③找最值；

④基本不等式法.

(6) 一些常见数列前 n 项的和.

$$ \sum_{k=1}^{n}k=1+2+3+\cdots+n=\frac{n(n+1)}{2} $$

$$ \begin{aligned}& \textcircled{2} \sum_{k=1}^{n}k^{2}=1^{2}+2^{2}+3^{2}+\cdots+n^{2}=\frac{n(n+1)(2n+1)}{6}．\\ &\begin{aligned}\\ &\star\textcircled{3} \sum_{k=1}^{n}\frac{1}{k(k+1)}=\frac{1}{1\times2}+\frac{1}{2\times3}+\frac{1}{3\times4}+\cdots+\frac{1}{n(n+1)}=\frac{n}{n+1}．\\ &\end{aligned}\\ &\\ &\lim_{n\rightarrow\infty}\sum_{k=1}^{n}\frac{1}{k(k+1)}=\lim_{n\rightarrow\infty}\frac{n}{n+1}=1\\ \end{aligned}\begin{aligned}\\ & 怎么算出来吗？\quad 复项相消 \\ &\rightarrow\begin{aligned}\\ &=1-\frac{1}{2}+\frac{1}{2}-\frac{1}{3}+\frac{1}{3}-\frac{1}{4}+\cdots+\frac{1}{n-\frac{1}{n+1}}\\ &\end{aligned}\\ &\begin{aligned}\\ &=1-\frac{1}{n+1}\\ &\end{aligned}\\ \end{aligned} $$

(7) 一个重要数列  $\left\{\left(1+\frac{1}{n}\right)^{n}\right\}$ 的结论：

①单调递增有上界.

②  $\lim_{n \to \infty} \left(1 + \frac{1}{n}\right)^n = e.$

!550

当 n 无限增大时（即  $n \to \infty$ 时），对应的  $x_{n} = f(n)$ 是否能无限接近于某个确定的数值，这就是我们接下来要研究的数列极限。

### [2] 张宇30讲原稿__第2讲-数列极限.md / ch_22523943974f

例 2.11 设  $0 < a_n < \frac{\pi}{2}$， $0 < b_n < \frac{\pi}{2}$， $\cos a_n - a_n = \cos b_n$，且  $\lim_{n \to \infty} b_n = 0$，求  $\lim_{n \to \infty} a_n$， $\lim_{n \to \infty} \frac{a_n}{b_n^2}$

(1) 分清约束式、关系式和定义式；(2) 做一至两步的逆运算；(3) 联想一些经典形式。

解 由  $\cos a_n - \cos b_n = a_n > 0$，知  $0 < a_n < b_n$，则由夹逼准则，得  $\rightarrow$ 根据  $\cos x$ 的单调性， $\cos x$ 在

$$ \lim_{n\to\infty}a_{n}=0, $$

$$ \left(0,\frac{\pi}{2}\right) $$

$$  联想到 1-\cos x\sim\frac{1}{2}x^{2}(x\rightarrow0) $$

$$ \lim_{n\to\infty}\frac{a_{n}}{b_{n}^{2}}=\lim_{n\to\infty}\frac{\sqrt{1-\cos b_{n}}}{b_{n}^{2}}\cdot\frac{a_{n}}{1-\cos b_{n}}=\frac{1}{2}\lim_{n\to\infty}\frac{a_{n}}{1-\cos a_{n}+a_{n}}=\frac{1}{2}\lim_{n\to\infty}\frac{1}{\frac{1-\cos a_{n}}{a_{n}}+1}=\frac{1}{2} $$

单调有界准则  $\rightarrow$ 单调有界准则是讨论数列极限存在的两个最重要的准则之一，另外一个是夹逼准则

单调有界数列必有极限，即若数列  $\{x_{n}\}$ 单调增加（减少）且有上界（下界），则  $\lim_{n\to\infty}x_{n}$ 存在。

不等关系

单调有界准则其实包含两种情况（涉及不等关系，是数学中的难点），第1种情况数列单调增加并且有上界；第2种情况，数列单调减少并且有下界。在这两种情况下数列极限都是存在的，使用的时候需要注意，当证明出来数列单调增加时，只需要再去证明数列有上界即可，无须再去证明有下界，同样如果证明出来数列有上界，则只需要再去证明数列单调增加即可，第二种情况同理。

记： $x_{n} \leqslant x_{n+1} \leqslant a$，则  $\lim_{n \to \infty} x_{n}$ 存在.

!550

学会用结论即可。不必去证明准则本身

!550

$a \leqslant x_{n+1} \leqslant x_n$，则  $\lim_{n \to \infty} x_n$ 存在。

!550

证明数列 $\{x_{n}\}$单调性的常用方法：

★ a.  $\underline{x_{n+1}-x_{n}}>$ 0 或  $\frac{x_{n+1}}{x_{n}}>$ 1（同号）.

作差法用得较多.

★ b. 利用数学归纳法.

一题一练 设  $c = 2 \ln(1 + b)$,  $b > a > 0$，且  $a$ 是方程  $x - 2 \ln(1 + x) = 0$ 的唯一非零解，证明  $c > a$

♡分析 由题知， $c=2\ln(1+b)$， $a=2\ln(1+a)$。

### [4] 1-2. 数列极限__数列的相关概念.md / ch_517218626e99

#### 证明数列有界的常用方法

1. 加绝对值，用定义法
2. 放缩法
3. 求最值
## 常见数列求和

1. 等差数列
$$ 1+2+3+\cdots +n = \frac{n(n+1)}{2} $$

2. 平方求和
$$ 1^2+2^2+3^2+ \cdots +n^2 = \frac{n(n+1)(2n+1)}{6}$$

3. 裂项相消
$$ \frac{1}{1 \times 2} + \frac{1}{2 \times 3} + \cdots + \frac{1}{n \times (n+1)} = \frac{n}{n+1} $$

## 重要数列的结论

$$\{ (1+\frac{1}{n})^n \} $$

对于上述数列，有以下几点性质：

- 单调递增;
- 该数列的极限： $\lim_{n \to \infty}(1+\frac{1}{n})^n = e.$

![graph](assets/1+1n_series.jpg)

## 无界变量

与无界变量相对的是有界变量。容易混淆的无穷大。

### 无界变量和无穷大量有什么关系？

> 无穷大一定无界，无界不一定是无穷大。

无穷大量是一个函数，里面所有的点都是“无穷大”，而无界变量则可以有一部分在有界内。例如：
当 $n$ 为奇数时， $x_n =\frac{1}{x}$ ；当 $n$ 为偶数时， $x_n =x$ 。当 $n \to \infty$ ，$x_n$ 是**无界大量**。

## h008

题目：判断级数 Σ1/n^2 的收敛性

原表检查要点：p 级数 p=2>1 收敛

回答：

结论：级数 $\displaystyle\sum_{n=1}^{\infty}\frac{1}{n^2}$ 收敛。

推导：

1. 这是正项级数。由 $p$ 级数判别结论：$\displaystyle\sum_{n=1}^{\infty}\frac{1}{n^p}$ 当 $p>1$ 时收敛，当 $p\le 1$ 时发散[1][3]。

2. 本题中 $p=2>1$，因此
$$
\sum_{n=1}^{\infty}\frac{1}{n^2}
$$
收敛[1]。

也可用积分判别法验证：取 $f(x)=\dfrac{1}{x^2}$，在 $[1,+\infty)$ 上非负、连续、单调减少，且 $u_n=f(n)$，则级数与 $\displaystyle\int_1^{+\infty}\frac{1}{x^2}\,dx$ 同敛散[3]。而
$$
\int_1^{+\infty}\frac{1}{x^2}\,dx
=\left[-\frac{1}{x}\right]_1^{+\infty}=1<+\infty,
$$
故原级数收敛[3]。

正常结束原因：`stop`

### [1] 张宇30讲原稿__第16讲-无穷级数（仅数学一、数学三）.md / ch_4d73dce2213a

例：对于正项级数  $\sum_{n=1}^{\infty}u_{n}$， $S_{n}$ 是级数前 n 项和，当 n > 1 时，则

$$ \frac{u_{n}}{S_{n}^{2}}=\frac{S_{n}-S_{n-1}}{S_{n}^{2}}\leqslant\frac{S_{n}-S_{n-1}}{S_{n}\cdot S_{n-1}}=\frac{1}{S_{n-1}}-\frac{1}{S_{n}} $$

分析： $u_{n}$ 与  $S_{n}^{2}$ 不同类，所以要化为同类

注3 此性质是级数收敛的必要条件. 其逆否命题: 若  $\lim_{n\to\infty}u_n\neq0$，则  $\sum_{n=1}^{\infty}u_n$ 必发散，且即使  $\lim_{n\to\infty}u_n=0$，也不能保证  $\sum_{n=1}^{\infty}u_n$ 收敛，见例 16.13.

!550

$$ \int_{1}^{+\infty}\frac{1}{x^{p}}\mathrm{d}x\Rightarrow\begin{cases}p>1, 收敛 ,\\ p\leq1, 发散 \end{cases}\Leftrightarrow\sum_{n=1}^{\infty}\frac{1}{n^{p}}\Rightarrow\begin{cases}p>1, 收敛 .\\ p\leq1, 发散 .\end{cases} $$

应用：判别 $\sum_{n=1}^{\infty}\ln\left(1+\frac{1}{n}\right)$的敛散性.

$$ \mathrm{n}\left(1+\frac{1}{n}\right)=\ln\frac{n+1}{n}=\ln(n+1)-\ln n $$

### [3] 张宇30讲原稿__第16讲-无穷级数（仅数学一、数学三）.md / ch_127bfe7af192

例 16.12 级数  $\sum_{n=1}^{\infty}\left[e^{\frac{\sin^{2}\alpha n}{n^{2}}}+\left(\cos\frac{1}{\sqrt{n}}\right)^{n^{2}}-1\right]$ （ ）.

(A) 收敛 (B) 发散 (C) 敛散性与  $\alpha$ 有关 (D) 无法判断

解 应选(A).

对级数  $I_{1}=\sum_{n=1}^{\infty}\left(e^{\frac{\sin^{2}\alpha n}{n^{2}}}-1\right)$，当  $n\to\infty$ 时， $\frac{\sin^{2}\alpha n}{n^{2}}\to0^{+}$，可判断其为正项级数。当  $n\to\infty$ 时， $e^{\frac{\sin^{2}\alpha n}{n^{2}}}-1$ 等价于  $\frac{\sin^{2}\alpha n}{n^{2}}$，而  $\frac{\sin^{2}\alpha n}{n^{2}}$ 满足  $0<\frac{\sin^{2}\alpha n}{n^{2}}\leq\frac{1}{n^{2}}$，且  $\sum_{n=1}^{\infty}\frac{1}{n^{2}}$ 收敛，从而  $I_{1}$ 收敛。

对级数  $I_2 = \sum_{n=1}^{\infty} \left( \cos \frac{1}{\sqrt{n}} \right)^n^2$，其亦为正项级数，用根值判别法  $\lim_{n \to \infty} \sqrt[n]{\left( \cos \frac{1}{\sqrt{n}} \right)^n^2} = e^{-\frac{1}{2}} < 1$，知  $I_2$ 收敛。

综上， $I_1 + I_2$ 收敛，选 (A).

(6) 积分判别法.

设  $\sum_{n=1}^{\infty}u_{n}$ 为正项级数，若存在  $[1, +\infty)$ 上单调减少的非负连续函数  $f(x)$，使得  $u_{n}=f(n)$，则级数  $\sum_{n=1}^{\infty}u_{n}$ 与反常积分  $\int_{1}^{+\infty}f(x)dx$ 的敛散性相同。

常见： $\int_{1}^{+\infty}\frac{1}{x^{p}}dx$ 与  $\sum_{n=1}^{\infty}\frac{1}{n^{p}}$ 敛散性相同； $\int_{1}^{+\infty}\frac{\ln x}{x^{p}}dx$ 与  $\sum_{n=1}^{\infty}\frac{\ln n}{n^{p}}$ 敛散性相同； $\int_{2}^{+\infty}\frac{1}{x^{p}}dx$ 与  $\sum_{n=2}^{\infty}\frac{1}{n^{p}}$ 敛散性相同； $\int_{2}^{+\infty}\frac{1}{x^{p}}dx$ 与  $\sum_{n=2}^{\infty}\frac{1}{n^{p}}$ 敛散性相同； $\int_{2}^{+\infty}\frac{1}{x^{p}}dx$ 与  $\sum_{n=2}^{\infty}\frac{1}{n^{p}}$ 收敛， $p>1$， $p=1$， $q>1$， $q\leq1$； $\int_{2}^{+\infty}\frac{1}{x^{p}\ln^{q}x}dx$ 与  $\sum_{n=2}^{\infty}\frac{1}{n^{p}\ln^{q}n}$ 敛散性相同； $\int_{2}^{+\infty}\frac{1}{x^{p}}dx$ 与  $\sum_{n=2}^{\infty}\frac{1}{n^{p}}$ 收敛， $p=1$， $q>1$， $q\leq1$； $\int_{2}^{+\infty}\frac{1}{x^{p}\ln^{q}x}dx$ 与  $\sum_{n=2}^{\infty}\frac{1}{n^{p}}$ 收敛， $p>1$， $q>1$， $q\leq1$；

## h009

题目：证明 x^2+1≥2x

原表检查要点：作差配平方 (x-1)^2≥0

回答：

结论：对任意实数 \(x\)，有
$$x^2+1\ge 2x,$$
等号当且仅当 \(x=1\) 时成立。

推导：

作差：
$$(x^2+1)-2x=x^2-2x+1=(x-1)^2.$$
依据：合并同类项与完全平方公式（基础代数恒等变形）。

由实数平方非负，得
$$(x-1)^2\ge 0.$$
依据：实数平方非负。

因此
$$(x^2+1)-2x\ge 0,$$
即
$$x^2+1\ge 2x.$$

等号成立当且仅当
$$(x-1)^2=0,$$
即 \(x=1\)。依据：实数平方为零当且仅当底数为零。

正常结束原因：`stop`
