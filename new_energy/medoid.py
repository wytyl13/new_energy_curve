#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2026/10/22 20:00
@Author  : weiyutao
@File    : medoid.py

步骤3 选代表年：k=1 K-medoids（自 refactor/curve_pipeline/classify_cluster.py
平移）。库内两两 8760 维欧氏距离和最小者为代表真实年，整条取出不做平均。
"""
from __future__ import annotations

import numpy as np


def medoid(X: np.ndarray, years: list[int]):
    """k=1 K-medoids：选本库真实年8760维欧氏距离和最小者。

    Args:
        X (np.ndarray): 库内各年曲线 (N,8760)。
        years (list[int]): 库内年份。

    Returns:
        tuple[int, list[float]]: (中选下标, 各年距离和)。
    """
    costs = []
    for a in X:
        costs.append(float(np.linalg.norm(X - a, axis=1).sum()))
    best = min(range(len(years)), key=lambda i: (costs[i], years[i]))
    return best, costs
