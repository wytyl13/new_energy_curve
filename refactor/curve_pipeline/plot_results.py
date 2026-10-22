#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2026/10/22 13:00
@Author  : weiyutao
@File    : plot_results.py

步骤5：绘制九条插后8760小时出力曲线（3×3子图 PNG）。
"""
from __future__ import annotations

import csv
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def run_plot(out_root: Path) -> Path:
    """画九条插后出力曲线并保存PNG。

    Args:
        out_root (Path): 输出根目录。

    Returns:
        Path: PNG 路径。
    """
    out = out_root / '九条出力曲线_原参数'
    with (out / '九条8760小时_插前插后资源与出力.csv').open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    names = [h[:-len('_插后出力pu')] for h in rows[0] if h.endswith('_插后出力pu')]
    plt.rcParams.update({'font.sans-serif': ['Microsoft YaHei', 'SimHei', 'DejaVu Sans'],
                         'axes.unicode_minus': False})
    fig, axes = plt.subplots(3, 3, figsize=(18, 10), sharex=True, sharey=True, layout='constrained')
    for ax, name in zip(axes.flat, names):
        y = [float(r[name + '_插后出力pu']) for r in rows]
        ax.plot(range(1, 8761), y, lw=.5, color='#145a86')
        ax.set_title(f'{name}  {sum(y):.1f} h')
        ax.set_xlim(1, 8760); ax.set_ylim(0, 1)
        ax.grid(alpha=.2)
    for ax in axes[:, 0]:
        ax.set_ylabel('出力标幺')
    for ax in axes[-1, :]:
        ax.set_xlabel('年内小时')
    fig.suptitle('九条插后8760小时出力曲线（原机组参数）', fontsize=17)
    png = out / '九条插后8760小时出力曲线.png'
    fig.savefig(png, dpi=160)
    return png
