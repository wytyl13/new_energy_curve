#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2026/10/22 13:00
@Author  : weiyutao
@File    : solar_insert.py

步骤2（光库）：P10 低光日插入。对代表年按月补历史低光日模板
（整日24小时替换），原有低光日不变。
"""
from __future__ import annotations

import numpy as np

from .axis import DAY_LABELS, DAY_MONTH, half_up


def insert_solar(X: np.ndarray, years: list[int], before: np.ndarray):
    """对代表年曲线执行低光日整日替换并自检。

    Args:
        X (np.ndarray): 库内各年辐照 (N,8760)，W/m²。
        years (list[int]): 库内年份。
        before (np.ndarray): 代表年（插入前）辐照 (8760,)。

    Returns:
        tuple: (插入后曲线 (8760,), 目标与结果 dict, 插入日志 list, 候选行 list)。
    """
    H = X.reshape(len(years), 365, 24)
    a = before.reshape(365, 24).copy()
    daily_mean = H.mean(axis=2)
    q10 = float(np.quantile(daily_mean, 0.1))
    historical_low = daily_mean <= q10
    original_low = a.mean(axis=1) <= q10
    annual_target = max(half_up(historical_low.sum(axis=1).mean()),
                        int(original_low.sum()))
    month_target = {m: half_up(historical_low[:, DAY_MONTH == m].sum(axis=1).mean())
                    for m in range(1, 13)}
    frequency = historical_low.sum(axis=0)
    templates = {}
    candidates = []
    for day in range(365):
        if original_low[day]:
            continue  # 先从可插日期池删去代表年原有低光日
        ids = [i for i in range(len(years)) if historical_low[i, day]]
        ids.sort(key=lambda i: (float(H[i, day].sum()), years[i]))
        if not ids:
            continue
        i0, i1 = ids[(len(ids) - 1) // 2], ids[len(ids) // 2]
        template = (H[i0, day] + H[i1, day]) / 2.0
        if template.mean() > q10 + 1e-9:
            raise AssertionError('低光模板未满足P10阈值')
        templates[day] = template
        candidates.append({'月日': DAY_LABELS[day], '月份': int(DAY_MONTH[day]),
            '低光频次': int(frequency[day]), '库年数': len(years),
            '来源年A': years[i0], '来源年B': years[i1],
            '模板日总辐照kWh/m²': float(template.sum() / 1000)})
    changed: set[int] = set()
    blocked: set[int] = set()
    logs = []
    rounds = 0
    while rounds < 365:
        rounds += 1
        current = a.mean(axis=1) <= q10
        annual_remaining = annual_target - int(current.sum())
        if annual_remaining <= 0:
            break
        gaps = {m: month_target[m] - int(current[DAY_MONTH == m].sum())
                for m in range(1, 13)}
        active = sorted((m for m in range(1, 13)
                         if gaps[m] > 0 and m not in blocked),
                        key=lambda m: (-gaps[m], m))
        if not active:
            break
        accepted = False
        for month in active:
            gap = gaps[month]
            quota = min((gap + 1) // 2, annual_remaining)
            eligible = [i for i in templates
                        if DAY_MONTH[i] == month and i not in changed
                        and not original_low[i]]
            eligible.sort(key=lambda i: (-int(frequency[i]), i))
            if len(eligible) < quota:
                blocked.add(month)
                continue
            for i in eligible[:quota]:
                old_total = float(a[i].sum() / 1000)
                a[i] = templates[i]
                changed.add(i)
                meta = next(x for x in candidates if x['月日'] == DAY_LABELS[i])
                logs.append({'轮次': rounds, '月份': month, '批前月缺口天': gap,
                    '本批额度天': quota, '月日': DAY_LABELS[i],
                    '低光频次': int(frequency[i]),
                    '原日总辐照kWh/m²': old_total,
                    '插后日总辐照kWh/m²': float(a[i].sum() / 1000),
                    '来源年A': meta['来源年A'], '来源年B': meta['来源年B']})
            accepted = True
            break  # 每批后重算缺口并重新排序
        if not accepted:
            break
    if not np.array_equal(a[original_low], before.reshape(365, 24)[original_low]):
        raise AssertionError('原有低辐照日被改动')
    if not np.array_equal(a[[i for i in range(365) if i not in changed]],
                          before.reshape(365, 24)[[i for i in range(365) if i not in changed]]):
        raise AssertionError('未选日期被改动')
    final = a.mean(axis=1) <= q10
    targets = {'P10日均阈值W/m²': q10,
        'P10日总量等价阈值kWh/m²': q10 * 24 / 1000,
        '全年目标天': annual_target,
        '插前天': int(original_low.sum()), '插后天': int(final.sum()),
        '月目标天': month_target,
        '月插前天': {m: int(original_low[DAY_MONTH == m].sum()) for m in range(1, 13)},
        '月插后天': {m: int(final[DAY_MONTH == m].sum()) for m in range(1, 13)},
        '冻结月份': sorted(blocked)}
    return a.ravel(), targets, logs, candidates
