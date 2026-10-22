#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2026/10/22 20:00
@Author  : weiyutao
@File    : load_csv.py

步骤1a 输入读取：读前端预处理后的区域 CSV（每年一个文件）。
风 = 100m 风速已合成（均方根）m/s；光 = 辐照已÷3600 的 W/m²。
列名形如 <变量名>_lat_<纬度>_lon_<经度>，一格点一列，格点为任意
散布子集（不强求矩形、不验行政区）。闰年删 2 月 29 日，规整为
每年 8760 小时；各年份文件格点列须一致。
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np

_COL = re.compile(r'lat_([0-9.]+)_lon_([0-9.]+)$')


def load_region(data_dir) -> tuple[list[int], np.ndarray, np.ndarray, np.ndarray]:
    """读取目录下全部年度 CSV。

    Args:
        data_dir: 数据目录路径（内含每年一个 *.csv）。

    Returns:
        tuple: (年份列表升序, 各列纬度 (G,), 各列经度 (G,), 数据立方 (N,8760,G))。
            G = 文件内格点列数，N = 年份数（不固定）。
    """
    files = sorted(Path(data_dir).glob('*.csv'))
    if not files:
        raise ValueError(f'{data_dir} 下没有CSV文件')
    years: list[int] = []
    lats = lons = None
    blocks = []
    for fp in files:
        lines = [ln for ln in fp.read_text(encoding='utf-8-sig').splitlines() if ln]
        grid = [_COL.search(c) for c in lines[0].split(',')[1:]]
        if not grid or not all(grid):
            raise ValueError(f'{fp.name} 存在无法解析的格点列名（须含 lat_x_lon_y）')
        cur_lats = np.array([float(m.group(1)) for m in grid])
        cur_lons = np.array([float(m.group(2)) for m in grid])
        if lats is None:
            lats, lons = cur_lats, cur_lons
        elif not (np.array_equal(lats, cur_lats) and np.array_equal(lons, cur_lons)):
            raise ValueError(f'{fp.name} 格点列与其他年份不一致')
        # 删闰年2月29日（时间列前11字符为 'YYYY-MM-DD '）
        body = [r.split(',') for r in lines[1:] if r[5:10] != '02-29']
        stamps = [r[0] for r in body]
        if not stamps:
            raise ValueError(f'{fp.name} 没有数据行')
        year = int(stamps[0][:4])
        if any(s[:4] != str(year) for s in stamps):
            raise ValueError(f'{fp.name} 混有其他年份的小时')
        if len(stamps) != 8760 or len(set(stamps)) != 8760:
            raise ValueError(f'{fp.name} 删2月29日后须为8760个不重复小时，实际{len(stamps)}')
        years.append(year)
        blocks.append(np.array([[float(v) for v in r[1:]] for r in body], dtype=float))
    cube = np.stack(blocks)  # (N,8760,G)
    if not np.isfinite(cube).all():
        raise ValueError('输入含非有限值')
    return years, lats, lons, cube
