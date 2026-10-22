#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2026/10/22 20:00
@Author  : weiyutao
@File    : mask_lookup.py

步骤1b 掩码与空间平均：区域各格点查服务端静态全国海陆掩码
（data/全国网格海陆分类.csv，make_national_mask.py 离线生成，
ARCO-ERA5 lsm>0.5=陆），再按 海格/陆格/全格 等权平均到 (8760,)。
查表走整数行列算术换算，不做浮点比对；非对齐或越界即报错。
"""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

DEFAULT_MASK = Path(__file__).resolve().parents[1] / 'data' / '全国网格海陆分类.csv'
_TABLES: dict[Path, dict[tuple[int, int], int]] = {}  # 进程内每张掩码只加载一次


def _table(path: Path) -> dict[tuple[int, int], int]:
    if path not in _TABLES:
        if not path.exists():
            raise ValueError(f'掩码文件不存在：{path}')
        with path.open(encoding='utf-8-sig') as f:
            _TABLES[path] = {(int(r['纬度行']), int(r['经度列'])): int(r['海陆判定'])
                             for r in csv.DictReader(f)}
    return _TABLES[path]


def sea_flags(lats, lons, mask_csv=None) -> np.ndarray:
    """区域格点海陆判定。

    Args:
        lats: 各格点纬度 (G,)。
        lons: 各格点经度 (G,)。
        mask_csv: 掩码路径，缺省项目 data/全国网格海陆分类.csv。

    Returns:
        np.ndarray: (G,) bool，True=海格。
    """
    table = _table(Path(mask_csv) if mask_csv else DEFAULT_MASK)
    flags = np.zeros(len(lats), dtype=bool)
    for g, (la, lo) in enumerate(zip(lats, lons)):
        i, j = round((54.0 - float(la)) / 0.25), round((float(lo) - 73.0) / 0.25)
        if abs(54.0 - 0.25 * i - float(la)) > 1e-6 or abs(73.0 + 0.25 * j - float(lo)) > 1e-6:
            raise ValueError(f'格点({la},{lo})不在0.25°对齐网格上')
        if (i, j) not in table:
            raise ValueError(f'格点({la},{lo})越出全国掩码范围')
        flags[g] = table[(i, j)] == 1
    return flags


def zone_mean(cube: np.ndarray, years: list[int], flags: np.ndarray,
              which: str) -> dict[int, np.ndarray]:
    """空间等权平均：海格/陆格/全格 → 每年一条 (8760,)。

    Args:
        cube: 数据立方 (N,8760,G)。
        years: 年份列表。
        flags: (G,) bool 海格标记。
        which: 'sea' 海格 / 'land' 陆格 / 'all' 全格。

    Returns:
        dict[int, np.ndarray]: {年份: (8760,)}。
    """
    sel = {'sea': flags, 'land': ~flags, 'all': np.ones(len(flags), dtype=bool)}[which]
    if not sel.any():
        raise ValueError(f'区域内没有{which}格点，无法平均')
    mean = cube[:, :, sel].mean(axis=2)  # (N,8760)
    return dict(zip(years, mean))
