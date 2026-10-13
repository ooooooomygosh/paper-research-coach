---
title: 为什么要除以 √d_k
subtitle: Attention Is All You Need · 3.2.1 节（PDF 第 4 页）
---
先说结论：维度 d_k 越大，**点积的数值越大**，softmax 会变得非常尖，梯度几乎为零。除以 $\sqrt{d_k}$ 把点积的方差拉回 1，训练才稳定。

## 缩放点积注意力怎么算 {span=2 meta="图 2 左"}
```flow LR
(Q) -> MatMul
(K) -> MatMul
MatMul -> *Scale ÷√d_k
*Scale ÷√d_k -> Mask: 可选
Mask -> SoftMax
SoftMax -> MatMul₂: 权重
(V) -> MatMul₂
MatMul₂ -> (输出)
```
$$\mathrm{Attention}(Q,K,V)=\mathrm{softmax}\!\left(\frac{QK^\top}{\sqrt{d_k}}\right)V$$

## 点积为什么会变大 {meta="脚注 4"}
设 q 和 k 的每个分量独立，均值 0，方差 1。

$$q\cdot k=\sum_{i=1}^{d_k} q_i k_i,\quad \mathrm{Var}(q\cdot k)=d_k$$

```callout info 一个数
基础模型里 d_k = 64，点积的标准差是 8。除以 8 之后，标准差回到 1。
```

## 缩放前后
| | 不缩放 | 除以 √d_k |
|---|---|---|
| 点积的标准差 | d_k 的平方根，随维度变大 | 1 |
| softmax 输出 | no 几乎全给一个位置 | ok 分得开 |
| 梯度 | no 很小，学得慢 | ok 正常 |

## 接下来看哪里
```ask
下一步先读哪一节？
* 3.2.2 多头注意力 | 同一套计算并行做 8 次
- 3.5 位置编码 | 没有循环，顺序从哪里来
```
