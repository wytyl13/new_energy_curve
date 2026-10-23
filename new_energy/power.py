#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2026/10/22 20:00
@Author  : weiyutao
@File    : power.py

步骤5 出力映射：资源曲线逐元素换算出力标幺。
风按海/陆机组参数（与冻结版一致：海 4/11/25 m/s α=0.70，
陆 2.5/9/18 α=0.95）；光 0.6·G/1000。
2026-10-23 起机组/光伏参数可经 run(wind_params=, pv_efficiency=) 覆盖，
缺省仍为上述冻结值（回归基准只锁缺省路径）。
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


def resolve_power_params(wind_params=None, pv_efficiency=None):
    """合并前端传入的风/光参数与冻结默认并校验（算法入口一次完成）。

    Args:
        wind_params (dict | None): {'sea'/'land': {'cut_in'/'rated'/'cut_out'/'alpha':
            部分或全部}}，缺省字段用 WIND_PARAMS 冻结值。
        pv_efficiency (float | None): 光伏综合效率系数，缺省 0.6（冻结值）。

    Returns:
        tuple: (各风区参数 {zone: (ci, rated, co, alpha)}, 光伏效率)。
    """
    merged = {z: dict(zip(('cut_in', 'rated', 'cut_out', 'alpha'), p))
              for z, p in WIND_PARAMS.items()}
    for zone, over in (wind_params or {}).items():
        if zone not in merged:
            raise ValueError(f"未知风区 {zone!r}（须为 sea/land）")
        for k, v in (over or {}).items():
            if k not in ('cut_in', 'rated', 'cut_out', 'alpha'):
                raise ValueError(f"未知风机参数字段 {k!r}（须为 cut_in/rated/cut_out/alpha）")
            if v is not None:
                merged[zone][k] = float(v)
    for zone, p in merged.items():
        if not 0 < p['cut_in'] < p['rated'] < p['cut_out']:
            raise ValueError(f"{zone} 风机参数须满足 0<切入<额定<切出 m/s，"
                             f"实际 {p['cut_in']}/{p['rated']}/{p['cut_out']}")
        if not 0 < p['alpha'] <= 1:
            raise ValueError(f"{zone} 顶格系数须在 (0,1]，实际 {p['alpha']}")
    eff = .6 if pv_efficiency is None else float(pv_efficiency)
    if not 0 < eff <= 1:
        raise ValueError(f'光伏综合效率系数须在 (0,1]，实际 {eff}')
    return {z: (p['cut_in'], p['rated'], p['cut_out'], p['alpha'])
            for z, p in merged.items()}, eff


def power_series(kind: str, zone: str, values: np.ndarray,
                 wind_p: tuple | None = None, pv_eff: float = .6) -> np.ndarray:
    """资源 (8760,) → 出力标幺 (8760,)。

    Args:
        kind: 'wind' 或 'solar'。
        zone: kind='wind' 时 'sea'/'land'（选机组参数）；solar 忽略。
        values: 资源曲线。
        wind_p: 本风区机组参数 (ci, rated, co, alpha)；缺省用 WIND_PARAMS 冻结值。
        pv_eff: 光伏综合效率系数；缺省 0.6（冻结值）。

    Returns:
        np.ndarray: 出力标幺曲线 (8760,)。
    """
    if kind == 'wind':
        w = wind_p or WIND_PARAMS[zone]
        return np.array([wind_power(v, *w) for v in values])
    return pv_eff * np.maximum(values, 0.) / 1000.
