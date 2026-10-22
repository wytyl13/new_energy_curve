#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2026/10/22 13:00
@Author  : weiyutao
@File    : results.py

结果读取：从输出根目录读取九库摘要、单库8760小时曲线与汇总表。
"""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path

# 库目录名 → 曲线名（与算法包 power_curves.CASES 冻结口径一致，服务不导入算法内部模块）
LIBRARY_NAMES = {
    'wind_sea_high': '海风_大风资源年', 'wind_sea_mid': '海风_平均风资源年',
    'wind_land_high': '陆风_大风资源年', 'wind_land_mid': '陆风_平均风资源年',
    'wind_sea_low': '海风_小风资源年', 'wind_land_low': '陆风_小风资源年',
    'solar_high': '大光资源年', 'solar_mid': '平均光资源年', 'solar_low': '小光资源年',
}

CURVE_DIR = '九条出力曲线_原参数'
LIB_DIR = '风光完整分类聚类插入程序结果'


def outputs_root() -> Path:
    """取输出根目录（环境变量 CURVE_OUTPUTS_ROOT，缺省为包旁 regression_out）。"""
    env = os.environ.get('CURVE_OUTPUTS_ROOT')
    return Path(env).expanduser().resolve() if env else Path(__file__).resolve().parents[2] / 'regression_out'


def _require_root(root: Path) -> None:
    """输出根目录不存在时报错（服务层统一 404）。"""
    if not root.is_dir():
        raise LookupError(f'输出根目录不存在：{root}，请先提交任务生成结果')


def _hours_rows(root: Path) -> list[dict]:
    """读九条曲线最大利用小时表。"""
    path = root / CURVE_DIR / '九条曲线_最大利用小时.csv'
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def list_libraries() -> list[dict]:
    """九库摘要列表。

    Returns:
        list[dict]: [{library, 曲线名, 代表年, 插入次数, 修改小时, 利用小时, 换算参数}, ...]。
    """
    root = outputs_root()
    _require_root(root)
    hours = {r['曲线']: r for r in _hours_rows(root)}
    libraries = []
    for folder, name in LIBRARY_NAMES.items():
        summary = json.loads((root / LIB_DIR / folder / 'summary.json').read_text(encoding='utf-8'))
        row = hours[name]
        libraries.append({'library': folder, '曲线名': name,
                          '资源类型': summary['资源类型'], '代表年': summary['代表年'],
                          '代表年欧氏距离和': summary['代表年欧氏距离和'],
                          '插入次数': summary['插入次数'], '修改小时': summary['修改小时'],
                          '插入前最大利用小时_h': float(row['插入前最大利用小时_h']),
                          '插入后最大利用小时_h': float(row['插入后最大利用小时_h']),
                          '换算参数': row['换算参数']})
    return libraries


def read_curve(library: str) -> dict:
    """单库8760小时曲线（资源与出力标幺）。

    Args:
        library (str): 库目录名。

    Returns:
        dict: {sheet_name, index, data:[{column_name, data}]}。
    """
    root = outputs_root()
    _require_root(root)
    if library not in LIBRARY_NAMES:
        raise ValueError(f'未知的库目录名：{library}，取值见 LIBRARY_NAMES')
    name = LIBRARY_NAMES[library]
    path = root / CURVE_DIR / '九条8760小时_插前插后资源与出力.csv'
    with path.open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    return {'sheet_name': name, 'index': [r['月日时_UTC'] for r in rows],
            'data': [{'column_name': col, 'data': [r[col] for r in rows]}
                     for col in (name + '_插前资源', name + '_插后资源',
                                 name + '_插前出力pu', name + '_插后出力pu')]}


def read_summary() -> dict:
    """汇总：利用小时表、复核结果、九库代表年。

    Returns:
        dict: {'九条最大利用小时': rows, '复核结果': dict, '代表年': {库: 年}}。
    """
    root = outputs_root()
    _require_root(root)
    review = json.loads((root / '复核结果.json').read_text(encoding='utf-8'))
    manifest = json.loads((root / LIB_DIR / 'classifications_and_results.json').read_text(encoding='utf-8'))
    alias = {'大': 'high', '平均': 'mid', '小': 'low'}
    reps = {f'{key.replace(":", "_")}_{alias[level]}': info['代表年']
            for key, block in manifest.items() if key.startswith('wind')
            for level, info in block['运行结果'].items()}
    reps.update({f'solar_{alias[level]}': info['代表年']
                 for level, info in manifest['solar:all']['运行结果'].items()})
    return {'九条最大利用小时': _hours_rows(root), '复核结果': review, '代表年': reps}
