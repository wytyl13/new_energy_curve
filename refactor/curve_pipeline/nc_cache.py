#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2026/10/22 13:00
@Author  : weiyutao
@File    : nc_cache.py

步骤1：读取逐年（或多年）NC，计算格点风速与辐照度，空间等权平均，
删闰年2月29日，统一为 1950—2025 每年 8760 小时，保存两个 NPZ 缓存。
"""
from __future__ import annotations

import csv
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import netCDF4 as nc
import numpy as np

from .grid_mask import GRID

YEARS = range(1950, 2026)


def grid_spec():
    """读取80格海陆分类表，返回行与海域/陆地格索引。

    Returns:
        tuple[list[dict], list[int], list[int]]: (80行表, 31个海域格ID, 49个陆地格ID)。
    """
    with GRID.open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 80:
        raise ValueError(f'海陆格点表应有80行，实际{len(rows)}行')
    sea = [int(r['网格ID_从0']) for r in rows if r['海陆判定'] == '海域']
    land = [int(r['网格ID_从0']) for r in rows if r['海陆判定'] == '陆地']
    if len(sea) != 31 or len(land) != 49:
        raise ValueError('格点数须为31个海域格和49个陆地格')
    return rows, sea, land


def nc_times(ds, start, stop):
    """取NC一段 valid_time 并转为 datetime 列表。

    Args:
        ds: 打开的 netCDF4 Dataset。
        start (int): 起始下标。
        stop (int): 结束下标（不含）。

    Returns:
        list[datetime]: 该段时间戳。
    """
    t = ds['valid_time']
    return nc.num2date(t[start:stop], t.units, calendar=getattr(t, 'calendar', 'standard'))


def check_grid(ds, rows):
    """核对NC经纬度次序与格点表一致。

    Args:
        ds: 打开的 netCDF4 Dataset。
        rows (list[dict]): 80行格点表。

    Returns:
        None
    """
    lat = np.asarray(ds['latitude'][:], dtype=float)
    lon = np.asarray(ds['longitude'][:], dtype=float)
    if lat.size * lon.size != 80:
        raise ValueError(f'NC须有80个网格，实际{lat.size}×{lon.size}')
    for row in rows:
        i, j = int(row['纬度行']), int(row['经度列'])
        if not np.isclose(lat[i], float(row['中心纬度_N']), atol=1e-6) or not np.isclose(lon[j], float(row['中心经度_E']), atol=1e-6):
            raise ValueError('NC经纬度或排列次序与格点表不一致')


def load_one_resource(folder: Path, kind: str, rows, sea, land):
    """读一种资源的全部NC并整理为逐年8760小时数组。

    Args:
        folder (Path): NC文件夹或单个NC文件。
        kind (str): 'wind'（u100/v100）或 'solar'（ssrd）。
        rows (list[dict]): 80行格点表。
        sea (list[int]): 海域格索引。
        land (list[int]): 陆地格索引。

    Returns:
        dict[int, np.ndarray]: {年份: (8760,) 海陆两类风速或辐照度}。
    """
    files = [folder] if folder.is_file() and folder.suffix.lower() == '.nc' else sorted(folder.rglob('*.nc'))
    if not files:
        raise FileNotFoundError(f'{folder} 中未找到NC文件')
    chunks = defaultdict(list)
    for path in files:
        with nc.Dataset(path) as ds:
            check_grid(ds, rows)
            if kind != 'wind':
                unit = str(getattr(ds['ssrd'], 'units', '')).lower().replace(' ', '')
                if 'j' not in unit or 'm' not in unit:
                    raise ValueError(f'{path}: ssrd单位须为J/m²的一小时累计值，实际{unit!r}')
            # One NC may contain all 76 years. Read at most 8784 hours at a time
            # so the 80-cell wind arrays do not consume gigabytes of RAM.
            for start in range(0, len(ds['valid_time']), 8784):
                stop = min(start + 8784, len(ds['valid_time']))
                times = nc_times(ds, start, stop)
                if kind == 'wind':
                    u = np.ma.filled(ds['u100'][start:stop], np.nan).astype(float)
                    v = np.ma.filled(ds['v100'][start:stop], np.nan).astype(float)
                    speed = np.hypot(u, v).reshape(len(times), 80)
                    values = np.column_stack((speed[:, sea].mean(axis=1), speed[:, land].mean(axis=1)))
                else:
                    ssrd = np.ma.filled(ds['ssrd'][start:stop], np.nan).astype(float)
                    values = ssrd.reshape(len(times), 80).mean(axis=1) / 3600.0
                if not np.isfinite(values).all():
                    raise ValueError(f'{path} 包含缺失/无穷值')
                for year in sorted({int(t.year) for t in times if int(t.year) in YEARS}):
                    take = np.array([int(t.year) == year and not (int(t.month) == 2 and int(t.day) == 29) for t in times])
                    stamps = [(int(t.month), int(t.day), int(t.hour)) for t, use in zip(times, take) if use]
                    chunks[year].append((stamps, values[take]))
        print(kind, path.name, flush=True)
    result = {}
    expected = [(t.month, t.day, t.hour) for t in (datetime(2001, 1, 1) + timedelta(hours=i) for i in range(8760))]
    for year in YEARS:
        if year not in chunks:
            raise ValueError(f'{kind}缺少{year}年NC数据；一年的NC不能推算76年历史库')
        stamps = sum((part[0] for part in chunks[year]), [])
        arrays = [part[1] for part in chunks[year]]
        value = np.concatenate(arrays, axis=0)
        order = sorted(range(len(stamps)), key=lambda i: stamps[i])
        if [stamps[i] for i in order] != expected:
            raise ValueError(f'{kind}{year}年删除2月29日后不是完整且无重复的8760小时')
        result[year] = value[order]
    return result


def run_nc_cache(wind_dir: Path, solar_dir: Path, out_root: Path) -> dict:
    """由原始NC生成风速与光伏两个76年NPZ缓存。

    Args:
        wind_dir (Path): 风NC入口（文件夹或单个NC）。
        solar_dir (Path): 光NC入口（文件夹或单个NC）。
        out_root (Path): 输出根目录。

    Returns:
        dict: 两个NPZ与分类表副本的路径。
    """
    rows, sea, land = grid_spec()
    wind = load_one_resource(wind_dir, 'wind', rows, sea, land)
    solar = load_one_resource(solar_dir, 'solar', rows, sea, land)
    out_w = out_root / '海南海陆全网格等权方案'
    out_s = out_root / '海南年聚类与月聚类公平对照'
    out_w.mkdir(parents=True, exist_ok=True)
    out_s.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out_w / '海陆两类_76年8760小时风速.npz',
                        **{f'{y}_{zone}': wind[y][:, i] for y in YEARS for i, zone in enumerate(('sea', 'land'))})
    np.savez_compressed(out_s / '光伏76年资源缓存.npz',
                        **{str(y): solar[y] for y in YEARS})
    with (out_w / '80网格海陆分类.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader(); writer.writerows(rows)
    return {'风速缓存': str(out_w / '海陆两类_76年8760小时风速.npz'),
            '光伏缓存': str(out_s / '光伏76年资源缓存.npz')}
