#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2026/10/22 20:00
@Author  : weiyutao
@File    : classify.py

步骤2 分档：年资源指标排序切 小/平均/大 三档。
年份数 N 不固定：小/大各 N//4、平均居中（N=76 时恰为冻结版的
19/38/19）。指标与冻结版一致——风 mean(v³)（功率∝v³，按能量权重）、
光 ΣG/1000（/1000 仅量纲缩放）。并列按年份升序。
"""
from __future__ import annotations

import numpy as np


def classify_years(data: dict[int, np.ndarray], kind: str):
    """N 年资源指标排序切三档。

    Args:
        data (dict[int, np.ndarray]): {年份: (8760,)} 序列。
        kind (str): 'wind' 或 'solar'。

    Returns:
        tuple[dict, dict]: ({'小'/'平均'/'大': 年份列表}, {年份: 指标})。
    """
    years = sorted(data)
    n = len(years)
    if n < 4:
        raise ValueError(f'分档至少需要4个年份，实际{n}个')
    index = {y: float(np.mean(a ** 3)) if kind == 'wind'
             else float(np.sum(a) / 1000.0)
             for y, a in data.items()}
    order = sorted(years, key=lambda y: (index[y], y))
    k = n // 4
    return {'小': order[:k], '平均': order[k:n - k], '大': order[n - k:]}, index
