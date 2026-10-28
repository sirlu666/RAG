# 数学复核材料 1

原始回答见 evidence.jsonl；以下仅整理排版。AI结论单列，人工字段未填写。

## h001

题目：解方程 x^2-5x+6=0

原表检查要点：判别式 Δ=1>0，两根 x=2,x=3

回答：

结论：$x_1=2,\ x_2=3$。

分步推导：

1. 对左边作因式分解：
$$
x^2-5x+6=(x-2)(x-3).
$$

2. 原方程化为
$$
(x-2)(x-3)=0.
$$

3. 由零乘积性质，得
$$
x-2=0\quad \text{或}\quad x-3=0.
$$

4. 解得
$$
x=2\quad \text{或}\quad x=3.
$$

所以方程 $x^2-5x+6=0$ 的解为
$$
x_1=2,\qquad x_2=3.
$$

以上只用到因式分解与零乘积性质，未引用资料编号。

正常结束原因：`stop`

## h002

题目：求方程组的解 {x+y=3, x-y=1}

原表检查要点：x=2,y=1

回答：

结论：$x=2,\ y=1$。

将方程组写成增广矩阵形式 [2]：

$$
\left[\begin{array}{cc:c}
1&1&3\\
1&-1&1
\end{array}\right]
$$

对增广矩阵作初等行变换（同解变换）[4]：

$$
\left[\begin{array}{cc:c}
1&1&3\\
1&-1&1
\end{array}\right]
\xrightarrow{R_2-R_1}
\left[\begin{array}{cc:c}
1&1&3\\
0&-2&-2
\end{array}\right]
\xrightarrow{-\frac12R_2}
\left[\begin{array}{cc:c}
1&1&3\\
0&1&1
\end{array}\right]
\xrightarrow{R_1-R_2}
\left[\begin{array}{cc:c}
1&0&2\\
0&1&1
\end{array}\right].
$$

化简后 $r(A)=r([A,b])=2$，未知数个数也为 $2$，故方程组有唯一解 [2]。读出

$$
x=2,\qquad y=1.
$$

验算：$2+1=3$，$2-1=1$，成立。

正常结束原因：`stop`

### [2] 2-4. 线性方程组__非齐次线性方程组.md / ch_302ec8ec842e

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

### [4] 张宇线代原稿__第4讲-线性方程组.md / ch_7c4d7bf1caea

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

## h003

题目：判断 f(x)=x^2+2x 的单调性

原表检查要点：配方 (x+1)^2-1，(-∞,-1] 递减、[-1,+∞) 递增

回答：

结论：$f(x)=x^{2}+2x$ 在 $(-\infty,-1]$ 上严格单调减少，在 $[-1,+\infty)$ 上严格单调增加；在 $\mathbb R$ 上不单调。

推导：

1. 任取 $x_1\neq x_2$，计算
$$
f(x_1)-f(x_2)
=x_1^2+2x_1-(x_2^2+2x_2)
=(x_1-x_2)(x_1+x_2+2).
$$
这是代数因式分解。

2. 于是
$$
(x_1-x_2)[f(x_1)-f(x_2)]
=(x_1-x_2)^2(x_1+x_2+2).
$$
因为 $(x_1-x_2)^2>0$，所以该式的符号由 $x_1+x_2+2$ 决定。

3. 当 $x_1<x_2\le -1$ 时，
$$
x_1+x_2+2<0,
$$
故
$$
(x_1-x_2)[f(x_1)-f(x_2)]<0.
$$
由严格单调减函数的判别形式
$$
f(x)\text{ 严格单调减}\Leftrightarrow (x_1-x_2)[f(x_1)-f(x_2)]<0
$$
可知，$f(x)$ 在 $(-\infty,-1]$ 上严格单调减少。[3]

4. 当 $-1\le x_1<x_2$ 时，
$$
x_1+x_2+2>0,
$$
故
$$
(x_1-x_2)[f(x_1)-f(x_2)]>0.
$$
由严格单调增函数的判别形式
$$
f(x)\text{ 严格单调增}\Leftrightarrow (x_1-x_2)[f(x_1)-f(x_2)]>0
$$
可知，$f(x)$ 在 $[-1,+\infty)$ 上严格单调增加。[3]

因此，$f(x)=x^{2}+2x$ 的单调性为：在 $(-\infty,-1]$ 上严格递减，在 $[-1,+\infty)$ 上严格递增。

正常结束原因：`stop`

### [3] 张宇30讲原稿__第1讲-函数极限与连续.md / ch_31ea1dccd309

上是定义法，是充要条件。

(2) 后面会看到，在考研试题中常常用求导的方法来讨论函数在某个区间上的单调性，但是定义法不可以忘记。试题中也常用到如下定义法的判别形式，请考生留意。

对任意 $x_{1}, x_{2} \in D, x_{1} \neq x_{2}$，有

f(x) 是单调增函数  $\Leftrightarrow (x_{1}-x_{2})[f(x_{1})-f(x_{2})]>0$；

严格单调减  $\Leftrightarrow$

f(x) 是单调减函数  $\Leftrightarrow (x_{1}-x_{2})[f(x_{1})-f(x_{2})]<0$；

f(x) 是单调不减函数  $\Leftrightarrow (x_{1}-x_{2})[f(x_{1})-f(x_{2})]\geq0$；

f(x) 是单调不增函数  $\Leftrightarrow (x_{1}-x_{2})[f(x_{1})-f(x_{2})]\leq0$。

在考研数学中，函数的单调性虽然是基础知识，但也会有综合应用。
