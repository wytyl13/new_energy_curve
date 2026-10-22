#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2026/10/22 13:00
@Author  : weiyutao
@File    : classify_cluster.py

步骤2（库导出）：加载缓存、三类资源年划分、k=1 K-medoids 选代表真实年，
调用风/光插入，导出 9 库四件套与总索引。
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

from .axis import YEARS, STAMP
from .solar_insert import insert_solar
from .wind_insert import insert_wind


def save_csv(path: Path, columns: list[str], records: list[dict]):
    """保存 CSV（UTF-8-BOM，列集冻结）。

    Args:
        path (Path): 目标文件。
        columns (list[str]): 列名。
        records (list[dict]): 行记录。

    Returns:
        None
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(records)


def save_json(path: Path, data):
    """保存 JSON（UTF-8，缩进2）。

    Args:
        path (Path): 目标文件。
        data: 可 JSON 序列化的对象。

    Returns:
        None
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def load_cache(path: Path, suffix: str = '') -> dict[int, np.ndarray]:
    """加载76年NPZ缓存并校验维度与数值。

    Args:
        path (Path): NPZ 路径。
        suffix (str): 年份键后缀（风缓存为 '_sea'/'_land'，光为空）。

    Returns:
        dict[int, np.ndarray]: {年份: (8760,) 数组}。
    """
    with np.load(path) as source:
        expected = {f'{y}{suffix}' for y in YEARS}
        missing = expected - set(source.files)
        if missing:
            raise ValueError(f'{path} 缺少年份键：{sorted(missing)[:5]}')
        data = {y: np.asarray(source[f'{y}{suffix}'], dtype=float).copy()
                for y in YEARS}
    for y, a in data.items():
        if a.shape != (8760,) or not np.isfinite(a).all():
            raise ValueError(f'{path} 的{y}年须为有限的8760小时数组')
        if suffix == '' and a.min() >= -0.01:
            # SSRD缓存偶有约10^-3 W/m²的数值负噪声，物理上按0处理。
            data[y] = np.maximum(a, 0.0)
        elif (a < 0).any():
            raise ValueError(f'{path} 的{y}年含显著负值')
    return data


def classify_years(data: dict[int, np.ndarray], kind: str):
    """76年资源指标排序：低19年、中38年、高19年。并列按年份升序。

    Args:
        data (dict[int, np.ndarray]): 76年缓存。
        kind (str): 'wind' 或 'solar'。

    Returns:
        tuple[dict, dict]: ({'小'/'平均'/'大': 年份列表}, {年份: 指标})。
    """
    if sorted(data) != YEARS:
        raise ValueError('分类要求1950—2025共76个完整年份')
    index = {y: float(np.mean(a ** 3)) if kind == 'wind'
             else float(np.sum(a) / 1000.0)
             for y, a in data.items()}
    order = sorted(YEARS, key=lambda y: (index[y], y))
    return {'小': order[:19], '平均': order[19:57], '大': order[57:]}, index


def medoid(X: np.ndarray, years: list[int]):
    """k=1 K-medoids：选本库真实年8760维欧氏距离和最小者。

    Args:
        X (np.ndarray): 库内各年曲线 (N,8760)。
        years (list[int]): 库内年份。

    Returns:
        tuple[int, list[float]]: (中选下标, 各年距离和)。
    """
    costs = []
    for a in X:
        costs.append(float(np.linalg.norm(X - a, axis=1).sum()))
    best = min(range(len(years)), key=lambda i: (costs[i], years[i]))
    return best, costs


def export_group(folder: Path, kind: str, years: list[int], data: dict[int, np.ndarray],
                 resource_index: dict[int, float]):
    """导出一个库：medoid 代表年 + 插入 + 四件套文件。

    Args:
        folder (Path): 库输出目录。
        kind (str): 'wind' 或 'solar'。
        years (list[int]): 本库年份。
        data (dict[int, np.ndarray]): 76年缓存。
        resource_index (dict[int, float]): 年资源指标。

    Returns:
        tuple[int, dict]: (代表年, 目标与结果)。
    """
    X = np.array([data[y] for y in years])
    k, costs = medoid(X, years)
    representative_year = years[k]
    before = X[k].copy()
    if kind == 'wind':
        after, targets, logs, candidates = insert_wind(X, years, before)
        log_columns = ['尾部', '轮次', '月份', '批前月缺口h', '批前全年缺口h', '本批额度h',
            '本批累计h', '来源年', '来源开始', '来源完整长度h', '实际插入长度h',
            '末段截断', '片段均风速m/s', '目标开始', '目标结束']
        cand_columns = ['尾部', '候选ID', '来源年', '来源开始', '月份', '完整长度h', '片段均风速m/s']
    else:
        after, targets, logs, candidates = insert_solar(X, years, before)
        log_columns = ['轮次', '月份', '批前月缺口天', '本批额度天', '月日', '低光频次',
            '原日总辐照kWh/m²', '插后日总辐照kWh/m²', '来源年A', '来源年B']
        cand_columns = ['月日', '月份', '低光频次', '库年数', '来源年A', '来源年B', '模板日总辐照kWh/m²']
    folder.mkdir(parents=True, exist_ok=True)
    save_json(folder / 'summary.json', {'资源类型': kind, '库年份': years,
        '代表年': representative_year,
        '代表年欧氏距离和': costs[k],
        '候选真实年欧氏距离和': dict(zip(map(str, years), costs)),
        '年资源指标': {str(y): resource_index[y] for y in years},
        '目标与结果': targets,
        '插入次数': len(logs), '修改小时': int(np.count_nonzero(after != before))})
    save_csv(folder / 'candidates.csv', cand_columns, candidates)
    save_csv(folder / 'insertion_log.csv', log_columns, logs)
    save_csv(folder / 'curve_8760.csv',
        ['小时序号', '月日时_UTC', '插前资源', '插后资源', '是否修改'],
        [{'小时序号': i + 1, '月日时_UTC': STAMP[i].strftime('%m-%d %H:%M'),
          '插前资源': float(before[i]), '插后资源': float(after[i]),
          '是否修改': int(before[i] != after[i])} for i in range(8760)])
    return representative_year, targets


def run_classify(out_root: Path) -> dict:
    """跑全部9库（海风/陆风/光伏 × 大/平均/小）并保存总索引。

    Args:
        out_root (Path): 输出根目录（含两个NPZ缓存）。

    Returns:
        dict: classifications_and_results.json 的内容。
    """
    out_dir = out_root / '风光完整分类聚类插入程序结果'
    wind_npz = out_root / '海南海陆全网格等权方案' / '海陆两类_76年8760小时风速.npz'
    solar_npz = out_root / '海南年聚类与月聚类公平对照' / '光伏76年资源缓存.npz'
    manifest = {}
    inputs = [('wind', 'sea', '_sea'), ('wind', 'land', '_land'), ('solar', 'all', '')]
    for kind, zone, suffix in inputs:
        data = load_cache(wind_npz if kind == 'wind' else solar_npz, suffix)
        classes, index = classify_years(data, kind)
        manifest[f'{kind}:{zone}'] = {'三类年份': classes,
            '资源指标': {str(y): index[y] for y in YEARS}, '运行结果': {}}
        for level in ('大', '平均', '小'):
            alias = {'大': 'high', '平均': 'mid', '小': 'low'}[level]
            key = f'{kind}:{zone}:{alias}' if kind == 'wind' else f'solar:{alias}'
            folder = out_dir / key.replace(':', '_')
            rep, targets = export_group(folder, kind, classes[level], data, index)
            manifest[f'{kind}:{zone}']['运行结果'][level] = {
                '代表年': rep, '目标与结果': targets, '目录': str(folder)}
            print(f'{key}: 代表年{rep}, 输出 {folder}', flush=True)
    save_json(out_dir / 'classifications_and_results.json', manifest)
    return manifest
