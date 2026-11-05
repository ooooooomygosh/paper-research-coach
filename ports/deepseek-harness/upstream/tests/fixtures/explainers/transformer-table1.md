---
title: 表 1：三种层的代价
subtitle: Attention Is All You Need · 第 4 节（PDF 第 6 页）
---
先说结论：自注意力层只要**常数次顺序操作**就能连接任意两个位置；当序列长度 n 小于表示维度 d 时，它每层的计算也比循环层少。

## 表 1 的三行 {meta="n 为序列长度，d 为维度，k 为卷积核宽度"}
| 层的类型 | 每层计算量 | 顺序操作 | 最长路径 |
|---|---|---|---|
| 自注意力 | $O(n^2 \cdot d)$ | ok $O(1)$ | ok $O(1)$ |
| 循环 | $O(n \cdot d^2)$ | no $O(n)$ | no $O(n)$ |
| 卷积 | $O(k \cdot n \cdot d^2)$ | ok $O(1)$ | warn $O(\log_k n)$ |
