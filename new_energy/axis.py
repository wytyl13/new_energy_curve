#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2026/10/22 20:00
@Author  : weiyutao
@File    : axis.py

8760 小时时间轴公共量与通用小函数：删闰年2月29日的平年时间戳、
月/日索引、月边界，以及 half_up 与 runs。风/光插入与各步骤共用。
（自 refactor/curve_pipeline/axis.py 平移，去掉固定76年清单 YEARS——
年份数不再固定，由输入数据决定。）
"""
from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np

STAMP = [datetime(2001, 1, 1) + timedelta(hours=i) for i in range(8760)]  # 平年8760小时时间戳（非闰年2001）
MONTH = np.array([t.month for t in STAMP], dtype=np.int16)  # 每小时所属月份
DAY = np.arange(8760) // 24  # 每小时所属年内日序（0基）
DAY_MONTH = MONTH[::24]  # 每日的月份
MONTH_BOUNDS = {m: (int(np.flatnonzero(MONTH == m)[0]),
                    int(np.flatnonzero(MONTH == m)[-1]) + 1)
                for m in range(1, 13)}  # 各月在8760轴上的闭开区间
DAY_LABELS = [t.strftime('%m-%d') for t in STAMP[::24]]  # 每日的月日标签
STAMP_INDEX = {t.strftime('%m-%d %H:%M'): i for i, t in enumerate(STAMP)}  # 月日时 -> 小时序号


def half_up(x: float) -> int:
    """四舍五入取整（对 .5 取上半）。

    Args:
        x (float): 待取整数值。

    Returns:
        int: 四舍五入结果。
    """
    return int(np.floor(float(x) + 0.5))


def runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """返回布尔序列的极大连续真值区间，右端点不包含。

    Args:
        mask (np.ndarray): 布尔序列。

    Returns:
        list[tuple[int, int]]: 各连续真值区间的 [起点, 终点)。
    """
    edges = np.diff(np.r_[False, np.asarray(mask, bool), False].astype(np.int8))
    return list(zip(np.flatnonzero(edges == 1).tolist(),
                    np.flatnonzero(edges == -1).tolist()))
