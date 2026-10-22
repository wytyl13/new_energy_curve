#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2026/10/22 13:00
@Author  : weiyutao
@File    : wind_insert.py

步骤2（风库）：P10/P90 极端片段插入。对代表年曲线逐月补历史越阈片段，
使全年/逐月越阈小时数达到库内历史平均目标，原有越阈小时不变。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .axis import DAY, MONTH, MONTH_BOUNDS, STAMP, STAMP_INDEX, half_up, runs


def qualified_wind(a: np.ndarray, q: float, high: bool):
    """逐月识别每小时越阈且连续≥3小时的完整过程。

    Args:
        a (np.ndarray): 单年8760小时风速。
        q (float): 阈值（P10或P90），m/s。
        high (bool): True 为 ≥q（P90），False 为 ≤q（P10）。

    Returns:
        tuple[np.ndarray, list[tuple[int, int, int]]]: (越阈小时掩码, (月, 起, 止)片段列表)。
    """
    out = np.zeros(8760, dtype=bool)
    events = []
    threshold = a >= q if high else a <= q
    for m, (lo, hi) in MONTH_BOUNDS.items():
        for s0, e0 in runs(threshold[lo:hi]):
            if e0 - s0 >= 3:
                s, e = lo + s0, lo + e0
                out[s:e] = True
                events.append((m, s, e))
    return out, events


@dataclass(frozen=True)
class WindCandidate:
    """一个可插入的历史越阈片段。"""
    cid: int                # 候选编号
    year: int               # 来源年
    month: int              # 所属月份
    source_start: int       # 来源年内的起始小时序号
    values: np.ndarray      # 片段逐小时风速，m/s
    mean: float             # 片段平均风速，m/s

    @property
    def length(self):
        return len(self.values)


def wind_candidates(X: np.ndarray, years: list[int], q: float, high: bool):
    """收集库内全部越阈且连续≥3小时的完整候选片段。

    Args:
        X (np.ndarray): 库内各年风速 (N,8760)。
        years (list[int]): 库内年份。
        q (float): 阈值，m/s。
        high (bool): True 为 P90 侧。

    Returns:
        list[WindCandidate]: 候选池。
    """
    pool = []
    for i, year in enumerate(years):
        _, events = qualified_wind(X[i], q, high)
        for month, s, e in events:
            pool.append(WindCandidate(len(pool), year, month, s,
                                      X[i, s:e].copy(), float(X[i, s:e].mean())))
    return pool


def ordered_candidates(pool: list[WindCandidate], month: int, high: bool):
    """按片段均值排序，P90从较大侧中位向更大侧，P10从较小侧中位向更小侧。

    Args:
        pool (list[WindCandidate]): 候选池。
        month (int): 月份。
        high (bool): True 为 P90 侧。

    Returns:
        list[int]: 候选下标（按插入优先顺序）。
    """
    ids = [i for i, c in enumerate(pool) if c.month == month]
    ids.sort(key=lambda i: (pool[i].mean, pool[i].year, pool[i].source_start))
    if high:
        return ids[len(ids) // 2:]  # 偶数从较大一侧中位向更大侧
    return list(reversed(ids[:(len(ids) + 1) // 2]))  # 较小侧中位向更小侧


def first_window(cur: np.ndarray, values: np.ndarray, month: int,
                 q10: float, q90: float, occupied_days: set[int]):
    """找首个可插入窗口；已有/新增越阈小时两侧各隔≥3个正常小时。

    Args:
        cur (np.ndarray): 当前更新中的曲线。
        values (np.ndarray): 待插片段值。
        month (int): 目标月份。
        q10 (float): P10阈值，m/s。
        q90 (float): P90阈值，m/s。
        occupied_days (set[int]): 已有新增片段占用的日序。

    Returns:
        int | None: 插入起始小时；无窗口返回 None。
    """
    length = len(values)
    lo, hi = MONTH_BOUNDS[month]
    if length < 3 or length > hi - lo:
        return None
    bad = (cur <= q10) | (cur >= q90)
    # 距任何越阈小时≤3的时点均不可作为新片段窗口。
    guarded = np.convolve(bad.astype(np.int8), np.ones(7, dtype=np.int8),
                          mode='same') > 0
    guarded[:3] = True
    guarded[-3:] = True
    free = ~guarded[lo:hi]
    if occupied_days:
        free &= ~np.isin(DAY[lo:hi], list(occupied_days))
    for s0, e0 in runs(free):
        if e0 - s0 >= length:
            return lo + s0
    return None


def try_wind_batch(after: np.ndarray, pool: list[WindCandidate], choices: list[int],
                   month: int, quota: int, annual_remaining: int,
                   q10: float, q90: float, occupied: set[int], allow_prefix: bool):
    """试探一批插入；不足额度不提交。完整片段优先，最后才试前缀截断。

    Args:
        after (np.ndarray): 当前曲线。
        pool (list[WindCandidate]): 候选池。
        choices (list[int]): 本月候选下标（按优先顺序）。
        month (int): 目标月份。
        quota (int): 本批额度，小时。
        annual_remaining (int): 全年剩余额度，小时。
        q10 (float): P10阈值，m/s。
        q90 (float): P90阈值，m/s。
        occupied (set[int]): 已占用日序。
        allow_prefix (bool): 是否允许历史片段前缀截断。

    Returns:
        tuple | None: (新曲线, 新占用日集合, 插入计划, 累计小时)；不可行返回 None。
    """
    max_hours = min(quota + 2, annual_remaining)
    for anchor in range(len(choices)):
        trial = after.copy()
        days = set(occupied)
        plan = []
        acc = 0
        for cid in choices[anchor:]:
            c = pool[cid]
            remaining = quota - acc
            if remaining <= 0:
                break
            value = c.values
            shortened = False
            if acc + len(value) > max_hours:
                if not allow_prefix or remaining < 3 or len(value) < remaining:
                    continue
                value = value[:remaining].copy()
                shortened = True
            dst = first_window(trial, value, month, q10, q90, days)
            if dst is None:
                continue
            end = dst + len(value)
            trial[dst:end] = value
            days.update(range(dst // 24, (end - 1) // 24 + 1))
            plan.append({'candidate': cid, 'dst': dst, 'length': len(value),
                         'shortened': shortened})
            acc += len(value)
            if acc >= quota:
                return trial, days, plan, acc
    return None


def insert_wind(X: np.ndarray, years: list[int], before: np.ndarray):
    """对代表年曲线执行 P10/P90 片段插入并自检。

    Args:
        X (np.ndarray): 库内各年风速 (N,8760)。
        years (list[int]): 库内年份。
        before (np.ndarray): 代表年（插入前）风速 (8760,)。

    Returns:
        tuple: (插入后曲线 (8760,), 目标与结果 dict, 插入日志 list, 候选行 list)。
    """
    q10, q90 = np.quantile(X, [0.1, 0.9]).tolist()
    after = before.copy()
    original_extreme = (before <= q10) | (before >= q90)
    occupied_days: set[int] = set()
    logs: list[dict] = []
    targets = {}
    candidate_rows = []
    for tail, q, high in [('P10', q10, False), ('P90', q90, True)]:
        used: set[int] = set()
        historical = np.array([qualified_wind(x, q, high)[0] for x in X])
        annual_target = half_up(historical.sum(axis=1).mean())
        month_target = {m: half_up(historical[:, MONTH == m].sum(axis=1).mean())
                        for m in range(1, 13)}
        pool = wind_candidates(X, years, q, high)
        for c in pool:
            candidate_rows.append({'尾部': tail, '候选ID': c.cid, '来源年': c.year,
                '来源开始': STAMP[c.source_start].strftime('%m-%d %H:%M'),
                '月份': c.month, '完整长度h': c.length, '片段均风速m/s': c.mean})
        blocked: set[int] = set()
        iterations = 0
        while iterations < 500:
            iterations += 1
            current, _ = qualified_wind(after, q, high)
            annual_remaining = annual_target - int(current.sum())
            if annual_remaining < 3:
                break
            gaps = {m: month_target[m] - int(current[MONTH == m].sum())
                    for m in range(1, 13)}
            active = sorted((m for m in range(1, 13)
                             if gaps[m] >= 3 and m not in blocked),
                            key=lambda m: (-gaps[m], m))
            if not active:
                break
            accepted = False
            for month in active:
                gap = gaps[month]
                quota = min((gap + 1) // 2 if gap > 6 else 3, annual_remaining)
                if quota < 3:
                    blocked.add(month)
                    continue
                choices = [i for i in ordered_candidates(pool, month, high)
                           if i not in used]
                batch = try_wind_batch(after, pool, choices, month, quota,
                                       annual_remaining, q10, q90, occupied_days,
                                       allow_prefix=False)
                if batch is None:
                    batch = try_wind_batch(after, pool, choices, month, quota,
                                           annual_remaining, q10, q90,
                                           occupied_days, allow_prefix=True)
                if batch is None:
                    blocked.add(month)
                    continue
                trial, trial_days, plan, acc = batch
                old_count = int(current.sum())
                new_count = int(qualified_wind(trial, q, high)[0].sum())
                if new_count - old_count != acc or new_count > annual_target:
                    blocked.add(month)
                    continue
                after, occupied_days = trial, trial_days
                for p in plan:
                    c = pool[p['candidate']]
                    used.add(p['candidate'])
                    logs.append({'尾部': tail, '轮次': iterations, '月份': month,
                        '批前月缺口h': gap, '批前全年缺口h': annual_remaining,
                        '本批额度h': quota, '本批累计h': acc,
                        '来源年': c.year,
                        '来源开始': STAMP[c.source_start].strftime('%m-%d %H:%M'),
                        '来源完整长度h': c.length,
                        '实际插入长度h': p['length'],
                        '末段截断': int(p['shortened']),
                        '片段均风速m/s': c.mean,
                        '目标开始': STAMP[p['dst']].strftime('%m-%d %H:%M'),
                        '目标结束': STAMP[p['dst'] + p['length'] - 1].strftime('%m-%d %H:%M')})
                accepted = True
                break  # 每批后重算所有月缺口并重新排序
            if not accepted:
                break
        final, _ = qualified_wind(after, q, high)
        targets[tail] = {'阈值m/s': q, '全年目标h': annual_target,
                         '插前h': int(qualified_wind(before, q, high)[0].sum()),
                         '插后h': int(final.sum()),
                         '月目标h': month_target,
                         '月插前h': {m: int(qualified_wind(before, q, high)[0][MONTH == m].sum())
                                     for m in range(1, 13)},
                         '月插后h': {m: int(final[MONTH == m].sum())
                                     for m in range(1, 13)},
                         '冻结月份': sorted(blocked)}
    if not np.array_equal(before[original_extreme], after[original_extreme]):
        raise AssertionError('原有P10/P90阈值小时被改动')
    placement_mask = np.zeros(8760, dtype=bool)
    checked_days = set()
    for row in logs:
        s = STAMP_INDEX[row['目标开始']]
        length = row['实际插入长度h']
        e = s + length
        source_start = STAMP_INDEX[row['来源开始']]
        source_year = row['来源年']
        expected = X[years.index(source_year), source_start:source_start + length]
        if length < 3 or not np.array_equal(after[s:e], expected):
            raise AssertionError('插入值不是来源片段的完整曲线或合法前缀')
        if placement_mask[s:e].any():
            raise AssertionError('新增片段相互覆盖')
        placement_mask[s:e] = True
        touched = set(range(s // 24, (e - 1) // 24 + 1))
        if touched & checked_days:
            raise AssertionError('同一日历日出现两条新增片段')
        checked_days.update(touched)
        buffer = np.r_[after[s - 3:s], after[e:e + 3]]
        if len(buffer) != 6 or not np.all((buffer > q10) & (buffer < q90)):
            raise AssertionError('新增片段两侧未保持各3个正常小时')
    if not np.array_equal(before[~placement_mask], after[~placement_mask]):
        raise AssertionError('片段目标位置以外的小时被改动')
    changed = np.flatnonzero(before != after)
    if any(i // 24 not in occupied_days for i in changed):
        raise AssertionError('修改小时与插入日志不一致')
    return after, targets, logs, candidate_rows
