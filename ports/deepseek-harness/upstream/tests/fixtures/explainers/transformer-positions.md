---
title: 没有循环，顺序从哪里来
subtitle: Attention Is All You Need · 3.5 节（PDF 第 6 页）
---
先说结论：注意力本身不管词的顺序。论文把一个**位置编码**加到每个词向量上，用不同频率的正弦和余弦写出位置。

## 加在哪里 {span=2}
```flow LR
(词) -> 词向量: 512 维
(位置 pos) -> 位置编码: 512 维
词向量 -> *相加
位置编码 -> *相加
*相加 -> (送进编码器)
```

## 公式 {meta="i 是维度的序号"}
$$PE_{(pos,2i)}=\sin\!\left(pos/10000^{2i/d_{\mathrm{model}}}\right)$$

$$PE_{(pos,2i+1)}=\cos\!\left(pos/10000^{2i/d_{\mathrm{model}}}\right)$$

```callout tip 为什么用正弦
作者猜它能让模型按相对位置来注意，也许还能用到比训练时更长的句子。
```
