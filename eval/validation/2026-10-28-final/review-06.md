# AI 复核材料 6



原始回答及引用不改写；AI 判断另见 AI-REVIEW.md。人工尚未审核。



## h019



题目：求导 f(x)=x·e^x



原表检查要点：f=(1+x)e^x（乘积法则）



记录：run-09，提交 `b1b221c7f7148bec05b6603e3bca3ffd3180ab2b`



模型原始回答：



结论：

\[

f'(x)=(x+1)e^x

\]



推导：

由资料中的莱布尼茨公式，取 \(n=1\)，得

\[

(uv)'=u'v+uv'

\]

[1]



令 \(u=x,\ v=e^x\)，则

\[

u'=1,\qquad v'=e^x

\]

因此

\[

f'(x)=(x)'e^x+x(e^x)'

=1\cdot e^x+x e^x

=(x+1)e^x

\]

[1]



也可由资料例4.17的结论

\[

(xe^x)^{(n)}=(n+x)e^x

\]

[1]



取 \(n=1\)，同样得到

\[

f'(x)=(1+x)e^x

\]



### [1] 张宇30讲原稿__第4讲-一元函数微分学的计算.md / ch_9c8d53607c9d



例4.17 设 $f(x)=xe^{x}$，则 $f^{(n)}(x)=$___。



♣分析 本题是两类不同函数乘积的 n 阶导数，且其中  $u(x)=x$ 是低次幂函数，可以考虑莱布尼茨公式，最后只有 2 项！



解 应填 $(n+x)e^{x}$



$$ f^{(n)}(x)=(x\mathrm{e}^{x})^{(n)}=(e^{x})^{(n)}x+C_{n}^{1}(\mathrm{e}^{x})^{(n-1)}\bullet1=x\mathrm{e}^{x}+n\mathrm{e}^{x}=(n+x)\mathrm{e}^{x}. $$



方法总结 求两类不同函数乘积的 n 阶导数，用莱布尼茨公式.



$$ (uv)^{(n)}=u^{(n)}v+C_{n}^{1}u^{(n-1)}v^{\prime}+C_{n}^{2}u^{(n-2)}v^{\prime\prime}+\cdots+C_{n}^{k}u^{(n-k)}v^{(k)}+\cdots+C_{n}^{n-1}u^{\prime}v^{(n-1)}+uv^{(n)}=\sum_{k=0}^{n}C_{n}^{k}u^{(n-k)}v^{(k)} $$



(3)泰勒展开式.  $\rightarrow$也称任意阶可导.



①任何一个无穷阶可导的函数都可写成



抽象展开



$$ y=f(x)=\sum_{n=0}^{\infty}\frac{f^{(n)}(x_{0})}{n!}(x-x_{0})^{n}, $$



或者



$$ y=f(x)=\sum_{n=0}^{\infty}\frac{f^{(n)}(0)}{n!}x^{n} $$



具体展开



②题目给出一个具体的无穷阶可导函数 $y=f(x)$，可以通过已知公式展开成幂级数。这些已知公式为



$$ \begin{aligned}&\mathrm{e}^{x}=\sum_{n=0}^{\infty}\frac{x^{n}}{n!}=1+x+\frac{x^{2}}{2!}+\cdots+\frac{x^{n}}{n!}+\cdots,-\infty<x<+\infty.\\ &\frac{1}{1+x}=\sum_{n=0}^{\infty}(-1)^{n}x^{n}=1-x+x^{2}-x^{3}+\cdots+(-1)^{n}x^{n}+\cdots,-1<x<1.\\ &\frac{1}{1-x}=\sum_{n=0}^{\infty}x^{n}=1+x+x^{2}+\cdots+x^{n}+\cdots,-1<x<1.\\ &\ln(1+x)=\sum_{n=1}^{\infty}(-1)^{n-1}\frac{x^{n}}{n}=x-\frac{x^{2}}{2}+\frac{x^{3}}{3}-\frac{x^{4}}{4}+\cdots+(-1)^{n-1}\frac{x^{n}}{n}+\cdots,-1<x\leq1.\\ &\sin x=\sum_{n=0}^{\infty}(-1)^{n}\frac{x^{2n+1}}{(2n+1)!}=x-\frac{x^{3}}{3!}+\frac{x^{5}}{5!}-\frac{x^{7}}{7!}+\cdots+(-1)^{n}\frac{x^{2n+1}}{(2n+1)!}+\cdots,-\infty<x<+\infty.\\ &\cos x=\sum_{n=0}^{\infty}(-1)^{n}\frac{x^{2n}}{(2n)!}=1-\frac{x^{2}}{2!}+\frac{x^{4}}{4!}-\frac{x^{6}}{6!}+\cdots+(-1)^{n}\frac{x^{2n}}{(2n)!}+\cdots,-\infty<x<+\infty.\\ &(1+x)^{\alpha}=1+\alpha x+\frac{\alpha(\alpha-1)}{2!}x^{2}+\cdots+\frac{\alpha(\alpha-1)\cdots(\alpha-n+1)}{n!}x^{n}+\cdots,\begin{cases}x\in(-1,1),&\alpha\leq-1,\\x\in(-1,1],&-1<\alpha<0,\\x\in[-1,1],&\alpha>0,\alpha\notin\mathbf{N}_{+},\\x\in\mathbf{R},&\alpha\in\mathbf{N}_{+}.\end{cases}\\ &\tan x=x+\frac{1}{3}x^{3}+\cdots.\\ &\arcsin x=x+\frac{1}{6}x^{3}+\cdots.\\ &\arctan x=x-\frac{1}{3}x^{3}+\cdots.\\ &\end{aligned} $$



③函数泰勒展开式的唯一性：无论 $f(x)$由何种方法展开，其泰勒展开式具有唯一性.于是我们可以通过比较①，②中公式的系数，获得 $f^{(n)}(x_{0})$或者 $f^{(n)}(0)$.



## h020



题目：计算定积分 ∫0^1 x dx



原表检查要点：=1/2



记录：run-09，提交 `b1b221c7f7148bec05b6603e3bca3ffd3180ab2b`



模型原始回答：



$$ \int_{0}^{1}x\,\mathrm{d}x=\frac12. $$



分步推导：



1. 由定积分的定义式，取 \(a=0,b=1\)，有

\[

\int_{0}^{1}f(x)\,\mathrm{d}x

=\lim_{n\to\infty}\sum_{i=1}^{n}f\left(\frac{i}{n}\right)\frac{1}{n}.

\]

依据：资料 [3] 中的定积分定义公式。



2. 令 \(f(x)=x\)，则

\[

\int_{0}^{1}x\,\mathrm{d}x

=\lim_{n\to\infty}\sum_{i=1}^{n}\frac{i}{n}\cdot\frac{1}{n}

=\lim_{n\to\infty}\frac{1}{n^{2}}\sum_{i=1}^{n}i.

\]

依据：代入 \(f\left(\frac{i}{n}\right)=\frac{i}{n}\)。



3. 利用

\[

\sum_{i=1}^{n}i=\frac{n(n+1)}{2},

\]

得

\[

\int_{0}^{1}x\,\mathrm{d}x

=\lim_{n\to\infty}\frac{1}{n^{2}}\cdot\frac{n(n+1)}{2}

=\lim_{n\to\infty}\frac{n+1}{2n}

=\frac12.

\]

依据：代数恒等变形并取极限。



因此，

\[

\boxed{\int_{0}^{1}x\,\mathrm{d}x=\frac12}.

\]



### [3] 张宇30讲原稿__第8讲-一元函数积分学的概念与性质.md / ch_8e765939404f



$$ \lim_{n\to\infty}\sum_{i=0}^{n-1}f\left(a+\frac{b-a}{n}i\right)\frac{b-a}{n}=\int_{a}^{b}f(x)\mathrm{d}x $$



<div style="text-align: center;">图 8-2</div>



若将式子中的 a, b 特殊化为 0, 1 这两个数，得出的形式更为简单：



$$ \int_{0}^{1}f(x)\mathrm{d}x=\lim_{n\to\infty}\sum_{i=1}^{n}f\left(\frac{i}{n}\right)\frac{1}{n} $$



(4) 定积分的值与字母无关.



当定积分存在时，有



$$ \int_{a}^{b}f(x)\mathrm{d}x=\int_{a}^{b}f(t)\mathrm{d}t=\int_{a}^{b}f(u)\mathrm{d}u, $$



注：积分与字母无关，无论x, t, u，都只是一个符号



这就是说， $\underline{\text{定积分的值只与被积函数及积分区间有关，而与积分变量的记法无关。}}$



是个客观存在的数量值



## 2 存在定理



定积分的存在性，也称一元函数的（常义）可积性。这里的“常义”是指“区间有限，函数有界”，也有人称为“黎曼”可积性，与后面要谈到的“区间无穷，函数无界”的“反常”积分有所区别。在本讲中所谈到的可积性都是指常义可积性。



!550



<div style="text-align: center;">函数与积分区间被限制在框之内.</div>



按照《全国硕士研究生招生考试数学考试大纲》，定积分存在定理包括下面两个方面。



(1) 定积分存在的充分条件.



①若 $f(x)$在 $[a,b]$上连续，则 $\int_{a}^{b}f(x)dx$存在.



闭区间上连续函数一定有界；



连续函数一定存在不定积分；



连续函数一定存在定积分.



②若 $f(x)$在 $[a,b]$上单调，则 $\int_{a}^{b}f(x)dx$存在.
