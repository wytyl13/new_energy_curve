#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2026/10/22 13:00
@Author  : weiyutao
@File    : pipeline.py

流水线编排与算法包唯一入口：hainan 目录进 → 九条出力曲线与复核结果出。
参数校验与默认值填充在此一次完成，服务层透传请求体即可。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from .classify_cluster import run_classify
from .grid_mask import run_grid_mask
from .nc_cache import run_nc_cache
from .plot_results import run_plot
from .power_curves import run_power_curves
from .verify_outputs import run_verify

DEFAULT_OUT = Path(__file__).resolve().parents[1] / 'regression_out'


def locate(hainan: Path, stem: str) -> Path:
    """在 hainan 目录下定位 wind/solar 资源入口。

    Args:
        hainan (Path): hainan 根目录。
        stem (str): 'wind' 或 'solar'。

    Returns:
        Path: 资源入口（文件夹或单个NC文件）。
    """
    matches = [hainan / stem, hainan / (stem + '.nc')]
    found = [p for p in matches if p.is_dir() or (p.is_file() and p.suffix.lower() == '.nc')]
    if not found:
        raise ValueError(f'{hainan} 下需要 {stem} 文件夹或 {stem}.nc')
    src = found[0]
    files = ([src] if src.is_file() else list(src.rglob('*.nc')))
    if not files:
        raise ValueError(f'{src} 下未找到.nc文件')
    return src


def run_pipeline(request: dict, progress: Callable[[int, str], None] | None = None) -> dict:
    """算法包唯一入口：从原始NC跑到九条出力曲线与复核。

    Args:
        request (dict): {'hainan_dir': str 必填；'out_dir': str 可选，
            缺省取环境变量 CURVE_OUTPUTS_ROOT 或包旁 regression_out}。
        progress (Callable | None): 可选进度回调 (步骤序号0-5, 描述)。

    Returns:
        dict: {'状态', '输出根目录', '九条最大利用小时', '复核结果'}。
    """
    hainan_raw = request.get('hainan_dir')
    if not hainan_raw:
        raise ValueError('请求缺少 hainan_dir 字段')
    hainan = Path(hainan_raw).expanduser().resolve()
    if not hainan.is_dir():
        raise ValueError(f'hainan目录不存在：{hainan}')
    wind = locate(hainan, 'wind')
    solar = locate(hainan, 'solar')
    out_dir = request.get('out_dir') or os.environ.get('CURVE_OUTPUTS_ROOT') or str(DEFAULT_OUT)
    out_root = Path(out_dir).expanduser().resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    steps = ['海陆核验', 'NC转缓存', '分类聚类插入', '出力换算', '复核', '画图']
    runs = [
        lambda: run_grid_mask(),
        lambda: run_nc_cache(wind, solar, out_root),
        lambda: run_classify(out_root),
        lambda: run_power_curves(out_root),
        lambda: run_verify(out_root),
        lambda: run_plot(out_root),
    ]
    outputs = []
    for i, (name, run) in enumerate(zip(steps, runs)):
        if progress is not None:
            progress(i, f'步骤{i}/5 {name}')
        outputs.append(run())
        if progress is not None:
            progress(i + 1, f'步骤{i}/5 {name} 完成')
    return {'状态': '完成', '输出根目录': str(out_root),
            '九条最大利用小时': outputs[3], '复核结果': outputs[4]}
