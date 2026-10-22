#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2026/10/22 13:00
@Author  : weiyutao
@File    : verify_outputs.py

步骤4：独立复核缓存、九库曲线、原极端片段保护与出力求和。
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np


def run_verify(out_root: Path) -> dict:
    """复核输出并保存复核结果；有错误即抛异常。

    Args:
        out_root (Path): 输出根目录。

    Returns:
        dict: 复核结果。
    """
    w = out_root / '海南海陆全网格等权方案' / '海陆两类_76年8760小时风速.npz'
    s = out_root / '海南年聚类与月聚类公平对照' / '光伏76年资源缓存.npz'
    p = out_root / '风光完整分类聚类插入程序结果'
    q = out_root / '九条出力曲线_原参数'
    errors = []
    with np.load(w) as z:
        expected = {f'{y}_{side}' for y in range(1950, 2026) for side in ('sea', 'land')}
        if set(z.files) != expected:
            errors.append('风速缓存年份键不完整')
        for k in expected:
            if z[k].shape != (8760,) or not np.isfinite(z[k]).all():
                errors.append(f'风速缓存{k}无效')
    with np.load(s) as z:
        expected = {str(y) for y in range(1950, 2026)}
        if set(z.files) != expected:
            errors.append('光伏缓存年份键不完整')
        for k in expected:
            if z[k].shape != (8760,) or not np.isfinite(z[k]).all():
                errors.append(f'光伏缓存{k}无效')
    groups = ('wind_sea_high', 'wind_sea_mid', 'wind_sea_low', 'wind_land_high',
              'wind_land_mid', 'wind_land_low', 'solar_high', 'solar_mid', 'solar_low')
    for group in groups:
        folder = p / group
        for file in ('summary.json', 'candidates.csv', 'insertion_log.csv', 'curve_8760.csv'):
            if not (folder / file).is_file():
                errors.append(f'{group}缺少{file}')
        if not (folder / 'curve_8760.csv').is_file():
            continue
        with (folder / 'curve_8760.csv').open(encoding='utf-8-sig', newline='') as f:
            rows = list(csv.DictReader(f))
        if len(rows) != 8760:
            errors.append(f'{group}曲线长度不是8760')
        if group.startswith('solar_'):
            before = np.array([float(r['插前资源']) for r in rows]).reshape(365, 24)
            after = np.array([float(r['插后资源']) for r in rows]).reshape(365, 24)
            threshold = json.loads((folder / 'summary.json').read_text(encoding='utf-8'))['目标与结果']['P10日均阈值W/m²']
            original_low = before.mean(axis=1) <= threshold
            if not np.array_equal(before[original_low], after[original_low]):
                errors.append(f'{group}原有低光日被修改')
        else:
            before = np.array([float(r['插前资源']) for r in rows])
            after = np.array([float(r['插后资源']) for r in rows])
            t = json.loads((folder / 'summary.json').read_text(encoding='utf-8'))['目标与结果']
            protected = (before <= t['P10']['阈值m/s']) | (before >= t['P90']['阈值m/s'])
            if not np.array_equal(before[protected], after[protected]):
                errors.append(f'{group}原有极端小时被修改')
    with (q / '九条8760小时_插前插后资源与出力.csv').open(encoding='utf-8-sig', newline='') as f:
        power = list(csv.DictReader(f))
    if len(power) != 8760:
        errors.append('九条出力表长度不是8760')
    with (q / '九条曲线_最大利用小时.csv').open(encoding='utf-8-sig', newline='') as f:
        summary = list(csv.DictReader(f))
    for row in summary:
        name = row['曲线']
        for label, key in [('插前', '插入前最大利用小时_h'), ('插后', '插入后最大利用小时_h')]:
            total = sum(float(r[name + '_' + label + '出力pu']) for r in power)
            if abs(total - float(row[key])) > 1e-6:
                errors.append(f'{name}{label}利用小时求和不一致')
    status = {'通过': not errors, '错误': errors, '检查组数': len(groups), '每组小时数': 8760}
    (out_root / '复核结果.json').write_text(json.dumps(status, ensure_ascii=False, indent=2),
                                             encoding='utf-8')
    if errors:
        raise RuntimeError(f'复核未通过：{errors}')
    return status
