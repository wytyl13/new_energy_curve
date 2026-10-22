#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2026/10/22 21:30
@Author  : weiyutao
@File    : compute.py

同步计算入口（无后台任务、无状态）：供 api 调用，依赖 new_energy。
"""
from __future__ import annotations

import os
import time
import uuid
from pathlib import Path

from new_energy import run


def compute(resource: str, scenario: str, data_dir: str,
            output_dir=None, outputs_root=None) -> dict:
    """同步跑一次完整计算：结果文件写指定/自动目录，返回表格数据
    {表名: [sheet]}（表名 = 曲线-场景-资源/出力，api-json-format）。

    Args:
        resource: 'wind' 或 'solar'。
        scenario: 'normal' | 'high' | 'low' | 'all'。
        data_dir: 输入目录（每年一个区域CSV）。
        output_dir: 结果输出目录（自动创建）；缺省 outputs/<时间戳_短随机>/。
        outputs_root: 自动命名时的结果根目录，缺省环境变量 CURVE_OUTPUTS_ROOT 或项目根 outputs/。

    Raises:
        ValueError: 参数非法 / 目录不存在或无 CSV（HTTP 层映射 400）。
    """
    p = Path(data_dir)
    if not p.is_dir():
        raise ValueError(f'输入目录不存在：{data_dir}')
    if not list(p.glob('*.csv')):
        raise ValueError(f'输入目录内无 CSV 文件：{data_dir}')
    if output_dir:
        out_dir = Path(output_dir)
    else:
        root = Path(outputs_root) if outputs_root else Path(
            os.environ.get('CURVE_OUTPUTS_ROOT', '')
            or Path(__file__).resolve().parents[1] / 'outputs')
        out_dir = root / f"{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    return run(resource, scenario, data_dir, out_dir)
