#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2026/10/22 20:00
@Author  : weiyutao
@File    : pipeline.py

组合入口：run(resource, scenario, data_dir, out_dir, wind_zone='all')。
resource = 'wind' | 'solar'；scenario = 'normal' | 'high' | 'low' | 'all'。
风一次算出海风+陆风（全国掩码分格点）；光为光伏（全格平均）。
2026-10-26 起风区口径可经 wind_zone 指定：'sea'/'land' 全区统一按该风区
处理（不查掩码、全格平均、用该风区机组参数）；'all' 缺省按掩码分海陆，
空区跳过（支持纯海/纯陆区域，对应原始包 --only 单库核算）。
传什么场景算什么，all = 大/正常/小全部。每条曲线写两个结果文件：
  <曲线>-<场景>-资源.csv：列 = 时间维度, 插入前资源, 插入后资源
  <曲线>-<场景>-出力.csv：列 = 时间维度, 插入前出力, 插入后出力
（插入前/后放同一文件；8760 行。）
"""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from .axis import STAMP
from .classify import classify_years
from .load_csv import load_region
from .mask_lookup import sea_flags, zone_mean
from .medoid import medoid
from .power import power_series, resolve_power_params
from .solar_insert import insert_solar
from .wind_insert import insert_wind

SCENARIOS = {'high': '大', 'normal': '正常', 'low': '小'}
LEVEL_OF = {'大': '大', '正常': '平均', '小': '小'}  # 场景名 → 分档档名（正常=平均档）
CURVE_NAMES = {'wind': {'sea': '海风', 'land': '陆风'}, 'solar': {'all': '光伏'}}


def _write_curve(path: Path, columns: list[str], arrays: list[np.ndarray]) -> None:
    """写一条曲线文件：8760 行，全精度浮点。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(columns)
        for i in range(8760):
            w.writerow([STAMP[i].strftime('%m-%d %H:%M')] + [a[i] for a in arrays])


def _sheet(sheet_name: str, kind: str, index: list[str],
           a: np.ndarray, b: np.ndarray) -> dict:
    """曲线数据结构：{sheet_name, index, data:[{column_name, data}]}。"""
    return {'sheet_name': sheet_name, 'index': index,
            'data': [{'column_name': f'插入前{kind}', 'data': a.tolist()},
                     {'column_name': f'插入后{kind}', 'data': b.tolist()}]}


def _one_library(kind: str, zone: str, label: str, years_group: list[int],
                 data: dict[int, np.ndarray], out_dir: Path,
                 wind_p: tuple | None = None, pv_eff: float = .6) -> list[dict]:
    """一个库（曲线×场景）：选代表年 → 极端修正 → 出力 → 写两个文件，返回两个 sheet。"""
    X = np.array([data[y] for y in years_group])
    k, _costs = medoid(X, years_group)
    before = X[k].copy()
    if kind == 'wind':
        after, _targets, _logs, _cands = insert_wind(X, years_group, before)
    else:
        after, _targets, _logs, _cands = insert_solar(X, years_group, before)
    p0 = power_series(kind, zone, before, wind_p, pv_eff)
    p1 = power_series(kind, zone, after, wind_p, pv_eff)
    curve = CURVE_NAMES[kind][zone]
    _write_curve(out_dir / f'{curve}-{label}-资源.csv',
                 ['时间维度', '插入前资源', '插入后资源'], [before, after])
    _write_curve(out_dir / f'{curve}-{label}-出力.csv',
                 ['时间维度', '插入前出力', '插入后出力'], [p0, p1])
    stamps = [t.strftime('%m-%d %H:%M') for t in STAMP]
    return [_sheet(f'{curve}-{label}-资源', '资源', stamps, before, after),
            _sheet(f'{curve}-{label}-出力', '出力', stamps, p0, p1)]


def run(resource: str, scenario: str, data_dir, out_dir,
        mask_csv=None, progress=None, wind_params=None, pv_efficiency=None,
        wind_zone='all') -> dict:
    """运行核心算法：读区域CSV → 掩码分格平均 → 分档选年 → 修极端 → 出力。

    Args:
        resource: 'wind' 或 'solar'。
        scenario: 'normal' | 'high' | 'low' | 'all'。
        data_dir: 输入目录（每年一个区域CSV）。
        out_dir: 结果输出目录。
        mask_csv: 全国海陆掩码路径，缺省项目 data/ 下静态文件（仅风用）。
        progress: 可选回调 progress(0~1小数, 步骤说明)，服务层报进度用。
        wind_params: 可选风机参数 {'sea'/'land': {cut_in/rated/cut_out/alpha
            部分或全部}}，缺省字段用冻结默认（海 4/11/25 m/s α=0.70，陆 2.5/9/18 α=0.95）。
        pv_efficiency: 可选光伏综合效率系数，缺省 0.6（冻结值）。
        wind_zone: 风区口径，'sea'/'land' 全区统一按该风区处理（不查掩码）；
            'all'（缺省）按掩码分海陆、空区跳过（纯海/纯陆区域只算存在的库）。
            仅 resource='wind' 生效，solar 忽略。

    Returns:
        dict: {表名: [sheet]}，表名 = 曲线-场景-资源/出力（与结果文件同名），
        sheet = {sheet_name, index, data:[{column_name, data}]}（api-json-format）。
    """
    if resource not in ('wind', 'solar'):
        raise ValueError(f"resource 须为 'wind' 或 'solar'，实际 {resource!r}")
    if scenario not in (*SCENARIOS, 'all'):
        raise ValueError(f"scenario 须为 normal/high/low/all，实际 {scenario!r}")
    if wind_zone not in ('sea', 'land', 'all'):
        raise ValueError(f"wind_zone 须为 sea/land/all，实际 {wind_zone!r}")
    wind_p, pv_eff = resolve_power_params(wind_params, pv_efficiency)
    data_dir, out_dir = Path(data_dir), Path(out_dir)
    wanted = list(SCENARIOS) if scenario == 'all' else [scenario]
    done = 0

    def _tick(text: str):
        nonlocal done
        done += 1
        if progress is not None:
            progress(round(done / total, 4), text)

    years, lats, lons, cube = load_region(data_dir)
    # 风区口径：sea/land 全区统一按该风区处理（不查掩码、全格平均、用该风区
    # 机组参数）；all 按掩码分海陆，空区跳过（纯海/纯陆区域）。光恒为 all。
    flags = sea_flags(lats, lons, mask_csv) if resource == 'wind' and wind_zone == 'all' else None
    if resource == 'wind':
        zones = ([wind_zone] if wind_zone != 'all' else
                 [z for z in ('sea', 'land') if (flags if z == 'sea' else ~flags).any()])
    else:
        zones = ['all']
    total = 1 + len(zones) * len(wanted)  # 读取1步 + 每库1步
    _tick(f'读取完成：{len(years)}年')
    tables: dict[str, list[dict]] = {}
    for zone in zones:
        data = zone_mean(cube, years, flags, zone) if flags is not None \
            else dict(zip(years, cube.mean(axis=2)))
        if resource == 'solar':
            # SSRD数据偶有约10^-3 W/m²的数值负噪声，物理上按0处理。
            lo = min(a.min() for a in data.values())
            if lo < -0.01:
                raise ValueError(f'辐照含显著负值（最小 {lo:.4f} W/m²）')
            data = {y: np.maximum(a, 0.) for y, a in data.items()}
        classes, _index = classify_years(data, resource)
        for s in wanted:
            label = SCENARIOS[s]
            for sheet in _one_library(resource, zone, label,
                                      classes[LEVEL_OF[label]], data, out_dir,
                                      wind_p.get(zone), pv_eff):
                tables[sheet['sheet_name']] = [sheet]
            _tick(f"{CURVE_NAMES[resource][zone]}-{label} 完成")
    return tables
