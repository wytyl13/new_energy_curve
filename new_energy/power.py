#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2026/10/22 20:00
@Author  : weiyutao
@File    : power.py

步骤5 出力映射：资源曲线逐元素换算出力标幺。
风按海/陆机组参数（与冻结版一致：海 4/11/25 m/s α=0.70，
陆 2.5/9/18 α=0.95）；光 0.6·G/1000。
"""
from __future__ import annotations

import numpy as np

# 各风区机组参数 (切入, 额定, 切出, α)
WIND_PARAMS = {'sea': (4., 11., 25., .7), 'land': (2.5, 9., 18., .95)}


def wind_power(v, ci, rated, co, alpha):
    """风机功率曲线：风速转出力标幺。

    Args:
        v (float): 风速，m/s。
        ci (float): 切入风速，m/s。
        rated (float): 额定风速，m/s。
        co (float): 切出风速，m/s。
        alpha (float): 顶格系数。

    Returns:
        float: 出力标幺（0~α）。
    """
    if v < ci or v >= co:
        return 0.
    if v >= rated:
        return alpha
    return alpha * (v ** 3 - ci ** 3) / (rated ** 3 - ci ** 3)


def power_series(kind: str, zone: str, values: np.ndarray) -> np.ndarray:
    """资源 (8760,) → 出力标幺 (8760,)。

    Args:
        kind: 'wind' 或 'solar'。
        zone: kind='wind' 时 'sea'/'land'（选机组参数）；solar 忽略。
        values: 资源曲线。

    Returns:
        np.ndarray: 出力标幺曲线 (8760,)。
    """
    if kind == 'wind':
        return np.array([wind_power(v, *WIND_PARAMS[zone]) for v in values])
    return .6 * np.maximum(values, 0.) / 1000.
