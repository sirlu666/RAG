# 数学复核材料 1

用户已要求 agent 自行核对；AI 复核结论另见 AI-REVIEW.md。本材料不包含虚构的人工通过结论。

## h001

题目：解方程 x^2-5x+6=0

检查要点（原表）：判别式 Δ=1>0，两根 x=2,x=3

模型完整回答：

结论：$x_1=2$，$x_2=3$。

依据求根公式 $x=\dfrac{-b\pm\sqrt{b^2-4ac}}{2a}$，其中 $a=1,\ b=-5,\ c=6$[1]。

先算判别式：

$$\Delta=b^2-4ac=(-5)^2-4\cdot1\cdot6=25-24=1$$

$\Delta=1>0$，故有两个不等实根[1]：

$$x=\frac{-(-5)\pm\sqrt{1}}{2\cdot1}=\frac{5\pm1}{2}$$

于是

$$x_1=\frac{5-1}{2}=2,\qquad x_2=\frac{5+1}{2}=3$$

验算：$2^2-5\cdot2+6=4-10+6=0$，$3^2-5\cdot3+6=9-15+6=0$，均成立。

检索问题：

解方程 x^2-5x+6=0

### 资料 [1] 张宇30讲原稿__第6讲-一元函数微分学的应用（二）中值定理、微分等式与微分不等式.md / seq=35

切片 ID：`ch_ec4ed765ce5e`；文档 SHA256：`28f1c986c910d1fc50de9c3ab868b9c4ebbeceb192fb88a90d864344299ba9eb`

在 $[0,1]$内有无实根即可.因为 $f(0)=-1<0$, $f(1)=2-\cos1>0$，且当 $\underline{\text{x∈(0,1)时，$ f'(x)=\frac{1}{4}x^{-\frac{3}{4}}+\frac{1}{2}x^{-\frac{1}{2}}+\sin x>0}} $所以$ f(x)=0 $在$ (0,+\infty) $内有且仅有一个实根.故在$ \underline{\text{(-\infty,++\infty)内 $f(x)=0$有且仅有两个实根.故答案选(C).}} $$

注 此题若换元，令  $|x|^{\frac{1}{4}} = t$，方程变为  $t + t^{2} - \cos t^{4} = 0$，计算时看起来更“舒服”。

例6.15 若  $3a^{2}-5b<0$，则方程  $\frac{x^{5}+2ax^{3}+3bx+4c=0}{}$（）.

(A) 无实根

(B) 有唯一实根

(C) 有三个不同实根

(D) 有五个不同实根

## 解 应选(B)

由于  $f(x)=x^{5}+2ax^{3}+3bx+4c$ 是奇次多项式，故方程  $f(x)=0$ 至少有一个实根，令  $f'(x)=0$，可知双二次方程  $5x^{4}+6ax^{2}+3b=0$ 对应于  $x^{2}$ 的判别式  $\Delta=12(3a^{2}-5b)<0$，则方程  $f'(x)=0$ 无实根， $f(x)$ 单调，所以方程  $f(x)=0$ 有唯一实根。故答案选 (B).

$$  令 t=x^{2}．则 5t^{2}+6at+3b=0,\Delta=36a^{2}-60b=12(3a^{2}-5b)<0 $$

例6.16 证明  $2^{x}-x^{2}-1=0$ 有且仅有三个根.

证 ①存在性.

观察法

令  $f(x)=2^{x}-x^{2}-1=0$ ，显然  $x_{1}=0, x_{2}=1$ 为根，又  $f(2)=-1<0, f(5)=2^{5}-25-1=6>0$ ，则  $f(x)=0$ 在  $(2,5)$ 内至少有一个根，即  $f(x)=0$ 至少有三个根.

②唯一性.

人工判定：未进行。AI 复核见单独报告。

## h002

题目：求方程组的解 {x+y=3, x-y=1}

检查要点（原表）：x=2,y=1

模型完整回答：

结论：$x=2,\ y=1$。

**分步推导：**

这是非齐次线性方程组，其向量形式为 $x_1\alpha_1+\cdots+x_n\alpha_n=b$[2]。记系数矩阵与增广矩阵：

$$A=\begin{bmatrix}1&1\\1&-1\end{bmatrix},\qquad [A\vdots b]=\begin{bmatrix}1&1&3\\1&-1&1\end{bmatrix}$$

对增广矩阵作初等行变换化为行阶梯形矩阵[4]：第二行减去第一行，得

$$\begin{bmatrix}1&1&3\\0&-2&-2\end{bmatrix}$$

第二行乘以 $-\frac{1}{2}$，得

$$\begin{bmatrix}1&1&3\\0&1&1\end{bmatrix}$$

由第二行得 $y=1$；回代第一行得 $x+1=3$，故 $x=2$。

**有解性校验：** 此时 $r(A)=r([A\vdots b])=2=n$，按有解条件，方程组有唯一解[2]，与上述结果一致。

检索问题：

求方程组的解 {x+y=3, x-y=1}

### 资料 [2] 2-4. 线性方程组__非齐次线性方程组.md / seq=0

切片 ID：`ch_302ec8ec842e`；文档 SHA256：`73821d82bef7a8635bdc8893871bb3a1a28d5e56134220a8cdd21a6943dc0ce7`

方程组：
$$
\left\{\begin{matrix}
a_{11}x_1 + a_{12} + \cdots + a_{1n}x_n = b_{1} \\
a_{21}x_1 + a_{22} + \cdots + a_{2n}x_n = b_{2} \\
\cdots \\
a_{m1}x_1 + a_{m2} + \cdots + a_{mn}x_n = b_{m}
\end{matrix}\right.
$$

其向量形式为： $x_{1} \alpha_{1} + x_{2} \alpha_{2} + \cdots + x_{n}\alpha_{n} = \boldsymbol{b}$

**注**
> 等号右边换成 $b$ 向量

把解向量放进去可获得增广矩阵

$$
\left[ {\begin{array}{c:c}
\begin{matrix}
a_{11} & \cdots & a_{1n} \\
\vdots & \ddots & \vdots \\
a_{m1} & \cdots & a_{mn}
\end{matrix}&
\begin{matrix}
b_1 \\
\vdots \\
b_m \\
\end{matrix}
\end{array}} \right]
$$

简记为 $[A \vdots b]$ 。

## 有解的条件

- 若 $r(A) \ne r([A,b])$ ，则方程组无解；
- 若 $r(A) = r([A,b]) = n$ 则方程组有唯一解；
- 若 $r(A) = r([A,b]) < n$ 则方程组有无穷多解。

**提示**
> - 第一条可理解为： $\boldsymbol{b}$ 不能由 $\alpha_{1}, \alpha_{2}, \cdots , \alpha_{n}$ 线性表示；
> - 第二条为： $\alpha_{1}, \alpha_{2}, \cdots , \alpha_{n}$ 线性无关， $\alpha_{1}, \alpha_{2}, \cdots , \alpha_{n}, \boldsymbol{b}$ 线性相关。

## 解的性质

若 $\eta_{1}, \eta_{2}, \eta$ 是非齐次方程组 $Ax=b$ 的解， $\xi$ 是对应齐次方程组 $Ax=0$ 的解，则：

- $\eta_{1}-\eta_{2}$ 是 $Ax=0$ 的解；
- $k\xi + \eta$ 是 $Ax=b$ 的解。

### 资料 [4] 张宇线代原稿__第4讲-线性方程组.md / seq=1

切片 ID：`ch_7c4d7bf1caea`；文档 SHA256：`cdf04954723d23b68a486ca5f8501048d4ac884637cafce59d55c1a81c9e0efb`

求解线性方程组，就是对增广矩阵作 $\uwave{\text{初等行变换}}$，化成 $\uwave{\text{行阶梯形矩阵}}$，然后求解.这个基本方法贯穿这门课程始终.方法目的

初等行变换，不改变未知数的值，属于同解变换

$$ \begin{array}{l}( 仅数学一 )\quad\uparrow\quad\uparrow\quad 用解空间表示 \\\uparrow\quad\downarrow\quad\downarrow\quad 用线性无关的向量 \quad( 在方程组中 ,\quad 称为“基础解系“)\quad 表示 \\\downarrow\quad\downarrow\quad\downarrow\quad( 仅数学一 )\quad 即向量空间中的基 \\\downarrow\quad\downarrow\quad\downarrow\quad 也为解向量的极大线性无关组 \end{array} $$

接下来，该方程组 $\underline{\text{有无穷多解时，如何表示出所有的解？}}$这又是某个(无穷)向量组用什么“代表”来表示的问题，这个“代表”就是基础解系.于是，解线性方程组便成了这一部分的关键.希望考生能发现：解方程组所得到的解 $x_{1}$， $x_{2}$，…， $x_{n}$就是描述向量与向量之间关系的 $\underline{\text{表示系数}}$.

①自由项 $\beta$被 $a_{1},a_{2},\cdots,a_{n}$线性表示的组合系数；

总结  $[x_{1}, x_{2}, \cdots, x_{n}]^{T}$ 表示

不同场合下，

有不同的名字

②（仅数学一） $a_{1}, a_{2}, \cdots, a_{n}$ 在基下的坐标；

③方程组的解.

## 齐次线性方程组

方程组

$$ \left\{\begin{aligned}a_{11}x_{1}&+a_{12}x_{2}+\cdots+a_{1n}x_{n}=0,\\ a_{21}x_{1}&+a_{22}x_{2}+\cdots+a_{2n}x_{n}=0,\\ &\cdots\cdots\\ a_{m1}x_{1}&+a_{m2}x_{2}+\cdots+a_{mn}x_{n}=0\end{aligned}\right. $$

称为m个方程，n个未知量的齐次线性方程组.

其向量形式为

$$ x_{1}\boldsymbol{\alpha}_{1}+x_{2}\boldsymbol{\alpha}_{2}+\cdots+x_{n}\boldsymbol{\alpha}_{n}=\boldsymbol{0}. $$

向量组的线性组合为零向量.

其中

若只有  $x_{1}, x_{2}, \cdots, x_{n}$ 全为 0 时才为零向量，则称向量组  $\alpha_{1}, \alpha_{2}, \cdots, \alpha_{n}$ 线性无关. 反之，如果  $x_{1}, x_{2}, \cdots, x_{n}$ 存在一组不全为0的数，使等式成立，则称  $\alpha_{1}, \alpha_{2}, \cdots, \alpha_{n}$ 线性相关

$$ \boldsymbol{\alpha}_{j}=\begin{bmatrix}a_{1j}\\ a_{2j}\\ \vdots\\ a_{mj}\end{bmatrix},j=1,2,\cdots,n. $$

其矩阵形式为

$$ \boldsymbol{A}_{m\times n}\boldsymbol{x}=\mathbf{0}, $$

其中

$$ \boldsymbol{A}_{m\times n}=\begin{bmatrix}a_{11}&a_{12}&\cdots&a_{1n}\\ a_{21}&a_{22}&\cdots&a_{2n}\\ \vdots&\vdots&&\vdots\\ a_{m1}&a_{m2}&\cdots&a_{mn}\end{bmatrix},\boldsymbol{x}=\begin{bmatrix}x_{1}\\ x_{2}\\ \vdots\\ x_{n}\end{bmatrix}. $$

## 有解的条件

①当 $r(A)=n$（ $a_1,a_2,\cdots,a_n$线性无关）时，方程组（I）有唯一零解；

理解： $A_{m \times n}$ (m行n列)，当 $r(A)=n$时，A的列向量组满秩，所以Ax=0只有唯一解，又因为齐次方程组必有零解，故方程组Ax=0只有零解。此外，从向量组的线性表示的角度看， $\alpha_1, \alpha_2, \cdots, \alpha_n$是线性无关的，故只有组合系数 $x_1, x_2, \cdots, x_n$全为0时，才能表示零向量。

★★★★★②当 $r(A)=r<n$（ $a_1, a_2, \cdots, a_n$线性相关）时，方程组(I)  $\underline{\text{有非零解(无穷多解)}}$，且有n-r个线性无关解.主要考查有非零解的情形

人工判定：未进行。AI 复核见单独报告。

## h003

题目：判断 f(x)=x^2+2x 的单调性

检查要点（原表）：配方 (x+1)^2-1，(-∞,-1] 递减、[-1,+∞) 递增

模型完整回答：

结论：$f(x)=x^{2}+2x$ 在 $(-\infty,-1]$ 上单调减少，在 $[-1,+\infty)$ 上单调增加。

推导：

1. 配方：$f(x)=x^{2}+2x=(x+1)^{2}-1$，这是开口向上的抛物线，对称轴为 $x=-1$。

2. 判断依据用单调性定义：对区间 $I$ 上任意 $x_1<x_2$，若恒有 $f(x_1)<f(x_2)$，则 $f$ 在 $I$ 上单调增加；若恒有 $f(x_1)>f(x_2)$，则单调减少[2][3]。等价判别式：$f$ 单调增 $\Leftrightarrow (x_1-x_2)[f(x_1)-f(x_2)]>0$，单调减 $\Leftrightarrow (x_1-x_2)[f(x_1)-f(x_2)]<0$[3]。

3. 取 $x_1<x_2$，则
$$f(x_2)-f(x_1)=(x_2+1)^{2}-(x_1+1)^{2}=(x_2-x_1)(x_1+x_2+2).$$
因 $x_2-x_1>0$，故 $f(x_2)-f(x_1)$ 的符号由 $x_1+x_2+2$ 决定。

4. 当 $x_1<x_2\le -1$ 时，$x_1+x_2+2<0$，得 $f(x_2)<f(x_1)$，即 $f$ 在 $(-\infty,-1]$ 上单调减少[3]。

5. 当 $-1\le x_1<x_2$ 时，$x_1+x_2+2>0$，得 $f(x_2)>f(x_1)$，即 $f$ 在 $[-1,+\infty)$ 上单调增加[3]。

补充说明：资料中另有借助导数符号判断单调性的依据（$f'(x)\ge 0$ 则单调增，$f'(x)<0$ 则单调减）[1]，但本资料未给出求导法则，故此处只用定义法完成判断。

检索问题：

判断 f(x)=x^2+2x 的单调性

### 资料 [1] 张宇30讲原稿__第6讲-一元函数微分学的应用（二）中值定理、微分等式与微分不等式.md / seq=39

切片 ID：`ch_8d7f9599ec3e`；文档 SHA256：`28f1c986c910d1fc50de9c3ab868b9c4ebbeceb192fb88a90d864344299ba9eb`

ightarrow x_{1}, $$

$$ f_{2}(x)=x^{2}+2x-1=0\Rightarrow x_{2}, $$

$$ f_{n}(x)=x^{n}+nx-1=0\Rightarrow x_{n}. $$

## 微分不等式

## 用函数性态（包括单调性、凹凸性和最值等）证明不等式

一般地，使用如下依据。

(1)若有 $f'(x)\geq0$, $a<x<b$，则有 $f(a)\leq f(x)\leq f(b)$.

★(2)若有 $f''(x)\geq0$, $a<x<b$，则有 $f'(a)\leq f'(x)\leq f'(b)$.

①当 $f'(a)>0$时， $f'(x)>0$，则 $f(x)$单调增加；

②当 $f'(b)<0$时， $f'(x)<0$，则 $f(x)$单调减少.

★(3)设 $f(x)$在I内连续，且有唯一的极值点 $x_{0}$，则

$$
\left\{\begin{aligned}& 当x_{0}为极大值点时，即为I内的最大值点，有 \\& f(x_{0})\geq f(x),\\& 当x_{0}为极小值点时，即为I内的最小值点，有 \\& f(x_{0})\leq f(x),\end{aligned}\right.
$$

其中 $x\in I$

★(4)若有 $f''(x)>0$, $a<x<b$, $f(a)=f(b)=0$,则有 $f(x)<0$.

例6.19 证明当  $0 < x < \frac{\pi}{2}$ 时，有  $\sin x > \frac{2x}{\pi} \cdot \frac{2x}{\pi} < \sin x < x$

证 方法一 若证  $\sin x > \frac{2x}{\pi}$，即需证  $\frac{\sin x}{x} > \frac{2}{\pi}$，令  $f(x) = \frac{\sin x}{x}$， $x \in \left(0, \frac{\pi}{2}\right)$，则主流方法：单调性

!550

$f'(x)=\frac{x\cos x-\sin x}{x^{2}}$ 一定不出正负，继续求导

分母大于0，只需研究分子

### 资料 [2] 张宇30讲原稿__第1讲-函数极限与连续.md / seq=19

切片 ID：`ch_3c211820fd24`；文档 SHA256：`66593a017613895d78c2378d94fce645c5798a4d44cd7698281d731580b2af5c`

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

### 资料 [3] 张宇30讲原稿__第1讲-函数极限与连续.md / seq=20

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
