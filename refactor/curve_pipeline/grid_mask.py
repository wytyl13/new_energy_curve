#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2026/10/22 13:00
@Author  : weiyutao
@File    : grid_mask.py

步骤0：用海南省边界 GeoJSON 核验 80 格海陆划分表
（31 海域格 / 49 陆地格），不一致即报错。
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
from matplotlib.path import Path as PolygonPath

PACKAGE_DIR = Path(__file__).resolve().parent
GRID = PACKAGE_DIR / 'data' / '80网格海陆分类.csv'  # 80格海陆分类表
BOUNDARY = PACKAGE_DIR / 'data' / '海南省边界_来源geoBoundaries_simplified.geojson'  # 省边界多边形


def run_grid_mask() -> dict:
    """逐格核验海陆判定并保存核对结果（写在包内 data 目录，与原版口径一致）。

    Returns:
        dict: 核对结果（网格数、海域格、陆地格、不一致格ID、是否通过）。
    """
    out_dir = PACKAGE_DIR / 'data'
    out_dir.mkdir(parents=True, exist_ok=True)
    with GRID.open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    geo = json.loads(BOUNDARY.read_text(encoding='utf-8'))
    polygon = PolygonPath(np.array(geo['features'][0]['geometry']['coordinates'][0]))
    mismatches = []
    for row in rows:
        land = polygon.contains_point((float(row['中心经度_E']), float(row['中心纬度_N'])))
        expected = (row['海陆判定'] == '陆地')
        if land != expected:
            mismatches.append(int(row['网格ID_从0']))
    result = {'网格数': len(rows), '海域格': sum(r['海陆判定'] == '海域' for r in rows),
              '陆地格': sum(r['海陆判定'] == '陆地' for r in rows),
              '与边界判定不一致的格ID': mismatches, '通过': not mismatches}
    (out_dir / '网格海陆核对.json').write_text(json.dumps(result, ensure_ascii=False, indent=2),
                                                encoding='utf-8')
    if len(rows) != 80 or result['海域格'] != 31 or result['陆地格'] != 49 or mismatches:
        raise ValueError(f'海陆网格核验未通过：{result}')
    return result
