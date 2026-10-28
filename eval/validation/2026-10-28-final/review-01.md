# AI 复核材料 1



原始回答及引用不改写；AI 判断另见 AI-REVIEW.md。人工尚未审核。



## h001



题目：解方程 x^2-5x+6=0



原表检查要点：判别式 Δ=1>0，两根 x=2,x=3



记录：run-09，提交 `b1b221c7f7148bec05b6603e3bca3ffd3180ab2b`



模型原始回答：



未找到依据。本轮资料未给出一元二次方程求根公式，也未给出由因式分解结合零因子法则求根的定理或结论；资料1仅涉及判别式、单调性及根的存在性/个数判断[1]，不能据此确定 $x^2-5x+6=0$ 的具体根。



### [1] 张宇30讲原稿__第6讲-一元函数微分学的应用（二）中值定理、微分等式与微分不等式.md / ch_ec4ed765ce5e



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



## h002



题目：求方程组的解 {x+y=3, x-y=1}



原表检查要点：x=2,y=1



记录：run-09，提交 `b1b221c7f7148bec05b6603e3bca3ffd3180ab2b`



模型原始回答：



结论：该方程组的解为

$$

x=2,\qquad y=1.

$$



推导如下。



写成增广矩阵：

$$

[A\vdots b]=

\begin{bmatrix}

1&1&3\\

1&-1&1

\end{bmatrix}.

$$



依据“求解线性方程组，就是对增广矩阵作初等行变换，化成行阶梯形矩阵，然后求解”[4]，作初等行变换：

$$

\begin{bmatrix}

1&1&3\\

1&-1&1

\end{bmatrix}

\xrightarrow{R_2-R_1}

\begin{bmatrix}

1&1&3\\

0&-2&-2

\end{bmatrix}

\xrightarrow{R_2\div(-2)}

\begin{bmatrix}

1&1&3\\

0&1&1

\end{bmatrix}.

$$

初等行变换不改变未知数的值，属于同解变换[4]。



再由

$$

\begin{cases}

x+y=3,\\

y=1,

\end{cases}

$$

得

$$

y=1,\qquad x=3-y=2.

$$



验算：

$$

2+1=3,\qquad 2-1=1.

$$



因此解为

$$

\boxed{x=2,\ y=1}.

$$



依据有解条件，$r(A)=r([A,b])=2=n$ 时方程组有唯一解[2]，故该解为唯一解。



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



记录：run-08，提交 `194aa2bba15d1db85a406cdc624133c6cc54a3e9`



模型原始回答：



结论：$f(x)=x^2+2x$ 在 $(-\infty,-1]$ 上单调减少，在 $[-1,+\infty)$ 上单调增加。



推导：



设 $x_1<x_2$，则

$$

f(x_1)-f(x_2)

=x_1^2+2x_1-x_2^2-2x_2

=(x_1-x_2)(x_1+x_2+2).

$$

于是

$$

(x_1-x_2)\bigl[f(x_1)-f(x_2)\bigr]

=(x_1-x_2)^2(x_1+x_2+2).

$$



1. 当 $x_1,x_2\in(-\infty,-1]$ 且 $x_1<x_2$ 时，有

$$

x_1+x_2+2<0,

$$

又 $(x_1-x_2)^2>0$，故

$$

(x_1-x_2)\bigl[f(x_1)-f(x_2)\bigr]<0.

$$

由严格单调减函数的判别式

$$

f(x)\text{ 是单调减函数}\iff (x_1-x_2)[f(x_1)-f(x_2)]<0

$$

可知 $f(x)$ 在 $(-\infty,-1]$ 上单调减少[3]。



2. 当 $x_1,x_2\in[-1,+\infty)$ 且 $x_1<x_2$ 时，有

$$

x_1+x_2+2>0,

$$

故

$$

(x_1-x_2)\bigl[f(x_1)-f(x_2)\bigr]>0.

$$

由严格单调增函数的判别式

$$

f(x)\text{ 是单调增函数}\iff (x_1-x_2)[f(x_1)-f(x_2)]>0

$$

可知 $f(x)$ 在 $[-1,+\infty)$ 上单调增加[3]。



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
