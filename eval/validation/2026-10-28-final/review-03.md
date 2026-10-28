# AI 复核材料 3



原始回答及引用不改写；AI 判断另见 AI-REVIEW.md。人工尚未审核。



## h007



题目：证明数列 (1+1/n)^n 单调递增且有上界



原表检查要点：二项式展开比较 + 有上界，单调有界收敛



记录：run-09，提交 `b1b221c7f7148bec05b6603e3bca3ffd3180ab2b`



模型原始回答：



结论：在【资料】范围内，可确认资料直接给出数列 \(\left\{\left(1+\frac1n\right)^n\right\}\) 单调递增且有上界，并由单调有界准则推出其收敛；但资料未给出“单调递增且有上界”的完整证明过程，故无法依据资料逐步完成该证明。



依据如下：



1. 资料1第(7)条直接列出重要数列 \(\left\{\left(1+\frac1n\right)^n\right\}\) 的结论：①单调递增有上界；② \(\lim_{n\to\infty}\left(1+\frac1n\right)^n=e\) [1]。资料4也列出该数列“单调递增” [4]。

2. 单调有界准则：若数列单调增加且有上界，则极限存在；同理单调减少且有下界也可 [2][5]。

3. 因此，由资料1的结论①及资料2、资料5的单调有界准则，可得 \(\left\{\left(1+\frac1n\right)^n\right\}\) 收敛 [1][2][5]。



缺少内容：资料没有给出证明该数列单调递增时所需的作差/作商过程，也没有给出构造上界的具体估计。上一轮使用的二项式展开及上界 \(<3\) 不属于本轮【资料】支持内容，不能作为依据。若需完整证明，需要补充包含相应推导的资料。



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



### [5] 张宇基础30讲__第2讲-数列极限.md / ch_3e3021e031d1



- 定义语言：任意 $\varepsilon>0$，存在正整数 $N$，当 $n>N$ 时 $|x_n-a|<\varepsilon$。

- 收敛性质：唯一性、有界性、保号性。

- 运算规则：和差积商，商法则要求分母极限不为 $0$。

- 易错点：数列收敛只描述趋向目标，不描述趋向速度。



### 极限存在准则



- 夹逼准则：构造上下界，两个界同趋一个数。

- 单调有界准则：单调递增有上界，或单调递减有下界。

- 递推数列：常见流程是先证有界，再证单调，再设极限解方程。

- 压缩映射：若 $|x_{n+1}-a|\le k|x_n-a|$ 且 $0<k<1$，可用夹逼证明 $x_n\to a$。



### 与函数极限的连接



- 海涅定理把函数极限转化为任意趋近点的数列极限。

- 计算复杂数列极限时，可以先构造函数极限，再用泰勒、等价无穷小或洛必达。

- 反向使用时，若能找出两列趋向同一点但函数值极限不同，则函数极限不存在。



## 概念区



### 数列概念



对每个 $n\in\mathbb N_+$，若按照某一法则对应一个确定的实数 $x_n$，则



$$

x_1,x_2,\cdots,x_n,\cdots

$$



称为数列，记作 $\{x_n\}$。



- 数列一定有无穷多项。

- 数列是整标函数，只讨论 $n\to\infty$ 的离散过程。

- 前有限项不影响极限，但可能影响最大值、最小值等全局问题。



### 子列



从数列 $\{a_n\}$ 中选取无穷多项，并保持原来的先后顺序，得到



$$

\{a_{n_k}\}:a_{n_1},a_{n_2},\cdots,a_{n_k},\cdots

$$



称为原数列的子列。



关键结论：



- 若 $\{a_n\}$ 收敛，则任意子列 $\{a_{n_k}\}$ 收敛到同一个极限。

- 若某个子列发散，则原数列发散。

- 若两个收敛子列极限不同，则原数列发散。

- 某个子列收敛不能推出原数列收敛。



### 数列极限定义



若存在常数 $a$，对任意 $\varepsilon>0$，存在正整数 $N$，当 $n>N$ 时恒有



$$

|x_n-a|<\varepsilon,

$$



则称数列 $\{x_n\}$ 收敛于 $a$，记作



$$

\lim_{n\to\infty}x_n=a.

$$



理解边界：



- 定义只要求“最终足够接近”，不要求前有限项如何。



## h008



题目：判断级数 Σ1/n^2 的收敛性



原表检查要点：p 级数 p=2>1 收敛



记录：run-09，提交 `b1b221c7f7148bec05b6603e3bca3ffd3180ab2b`



模型原始回答：



结论：级数 $\displaystyle\sum_{n=1}^{\infty}\frac{1}{n^2}$ 收敛。



分步推导：



1. 令 $u_n=\frac{1}{n^2}$，则 $u_n\ge 0$，故 $\displaystyle\sum_{n=1}^{\infty}\frac{1}{n^2}$ 是正项级数。



2. 由积分判别法，$\displaystyle\int_{1}^{+\infty}\frac{1}{x^p}\,dx$ 与 $\displaystyle\sum_{n=1}^{\infty}\frac{1}{n^p}$ 的敛散性相同[3]。



3. 资料给出

$$

\int_{1}^{+\infty}\frac{1}{x^p}\,dx

\Rightarrow

\begin{cases}

p>1,\ \text{收敛},\\

p\le 1,\ \text{发散},

\end{cases}

\iff

\sum_{n=1}^{\infty}\frac{1}{n^p}

\Rightarrow

\begin{cases}

p>1,\ \text{收敛},\\

p\le 1,\ \text{发散}.

\end{cases}

$$

[1]



4. 本题 $p=2>1$，因此由上述 $p$ 级数结论，

$$

\sum_{n=1}^{\infty}\frac{1}{n^2}

$$

收敛。[1][3]



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



记录：run-09，提交 `b1b221c7f7148bec05b6603e3bca3ffd3180ab2b`



模型原始回答：



结论：对任意实数 \(x\)，有

$$x^2+1\ge 2x.$$



证明：



1. 当 \(x<0\) 时，\(2x<0\)，且 \(x^2+1\ge 1>0\)，故

$$x^2+1>0>2x,$$

所以不等式成立。



2. 当 \(x=0\) 时，

$$x^2+1=1\ge 0=2x,$$

不等式成立。



3. 当 \(x>0\) 时，由资料中的基本不等式

$$\frac{a+b}{2}\ge \sqrt{ab}\quad(a,b>0)$$

取 \(a=x^2>0,\ b=1>0\)，得

$$\frac{x^2+1}{2}\ge \sqrt{x^2\cdot 1}.$$

又由资料中 \(\sqrt{x^2}=|x|\)，且 \(x>0\)，所以 \(|x|=x\)，于是

$$\frac{x^2+1}{2}\ge x,$$

两边乘以 \(2\)，得

$$x^2+1\ge 2x.$$



综上，对任意实数 \(x\)，都有

$$x^2+1\ge 2x.$$

依据：基本不等式及 \(\sqrt{x^2}=|x|\) 见资料1[1]。



### [1] 张宇30讲原稿__第1讲-函数极限与连续.md / ch_3c211820fd24



例 1.6 证明函数  $f(x)=\frac{x}{1+x^{2}}$ 在  $(-∞,+∞)$ 内有界.



补充： $x^{2}=\left|x^{2}\right|=\left|x\right|^{2}$



$$ \begin{aligned}&x^{3}\neq\left|x^{3}\right|=\left|x\right|^{3},\\&\left|x\right|=\sqrt{x^{2}}.\\ \end{aligned} $$



分析 当  $x \neq 0$ 时， $\left|f(x)\right| = \frac{|x|}{1 + x^2} \xlongequal{\text{分子分母同除}} \frac{1}{\frac{1}{|x|} + |x|}$ 或者用  $\left|x\right| = \sqrt{x^2}$



若求  $\left[\left|f(x)\right|\right]'$ 呢；



证 方法一 当 $x\neq0$时，



$$ \left|f(x)\right|=\frac{\left|x\right|}{1+x^{2}}=\frac{1}{\frac{1}{\left|x\right|}+\left|x\right|}, $$



$$ \begin{aligned}\left[\mid f(x)\mid\right]^{\prime}=&\left[\sqrt{f^{2}(x)}\right]^{\prime}\\ =&\frac{2f(x)f^{\prime}(x)}{2\sqrt{f^{2}(x)}}=\frac{f(x)f^{\prime}(x)}{\mid f(x)\mid}.\end{aligned} $$



$$ \begin{aligned} 再如：f(x)&=2x+\sqrt{x^{2}+2x+1}\\&=2x+\sqrt{(x+1)^{2}}\\&=2x+\left|x+1\right|.\end{aligned} $$



由不等式 $\frac{a+b}{2}\geq\sqrt{ab}(a,b>0)$，有 $\frac{1}{|x|}+|x|\geq2\sqrt{\frac{1}{|x|}|x}|=2$，即 $|f(x)|\leq\frac{1}{2}$。



当x=0时， $f(0)=0$．综上，函数 $f(x)$在 $(-∞,+∞)$内有界．



方法二 当  $x \neq 0$ 时， $\frac{1 + x^{2}}{2} \geqslant \sqrt{1 \cdot x^{2}} \Rightarrow |x|$，则  $1 + x^{2} \geqslant 2|x|$，故  $\frac{1}{1 + x^{2}} \leqslant \frac{1}{2|x|}$，则



$$ \left|f(x)\right|=\frac{\left|x\right|}{1+x^{2}}\leqslant\frac{\left|x\right|}{2\left|x\right|}=\frac{1}{2}\ . $$



当x=0时， $f(0)=0$．综上，函数 $f(x)$在 $(-∞,+∞)$内有界．



☎ 方法总结 用基本不等式，找 M，使  $|f(x)| \leqslant M$。



$$ \frac{a+b}{2}\geqslant\sqrt{ab}(a,b>0);\quad\frac{2}{\frac{1}{a}+\frac{1}{b}}\leqslant\sqrt{ab}\leqslant\frac{a+b}{2}\leqslant\sqrt{\frac{a^{2}+b^{2}}{2}}(a,b>0). $$



(2) 单调性.  $\rightarrow$ 整个考研数学，离不开单调性这个话题



设 $f(x)$的定义域为D，区间 $I\subset D$。如果对于区间I上任意两点 $x_{1},x_{2}$，当 $x_{1}<x_{2}$时，恒有 $f(x_{1})<f(x_{2})$，则称 $f(x)$在区间I上单调增加。如果对于区间I上任意两点 $x_{1},x_{2}$，当 $x_{1}<x_{2}$时，恒有 $f(x_{1})>f(x_{2})$，则称 $f(x)$在区间I上单调减少。



注 $^{1}$ (1) 以上是定义法，是充要条件。



(2) 后面会看到，在考研试题中常常用求导的方法来讨论函数在某个区间上的单调性，但是定义法不可以忘记。试题中也常用到如下定义法的判别形式，请考生留意。



对任意 $x_{1}, x_{2} \in D, x_{1} \neq x_{2}$，有



f(x) 是单调增函数  $\Leftrightarrow (x_{1}-x_{2})[f(x_{1})-f(x_{2})]>0$；



严格单调减  $\Leftrightarrow$
