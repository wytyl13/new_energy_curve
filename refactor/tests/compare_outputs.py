#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2026/10/22 13:00
@Author  : weiyutao
@File    : compare_outputs.py

回归比对：基准输出（baseline_md5.csv）与重构版输出逐文件比对。
判据（事先声明，见 DESIGN.md）：除"运行来源与程序版本.json"外全部逐位一致；
容器/渲染类文件降级为内容一致：NPZ比数组逐位、PNG比像素逐位。
"""
from __future__ import annotations

import csv
import hashlib
import os
import sys
from pathlib import Path

REF = Path(__file__).resolve().parents[1]
EXCLUDE = {'运行来源与程序版本.json'}  # 含UTC时间戳与代码哈希，非算法产物


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def main(baseline_csv: Path, out_root: Path) -> int:
    with baseline_csv.open(encoding='utf-8') as f:
        base = {r['file']: r['md5'] for r in csv.DictReader(f)}
    base = {k: v for k, v in base.items() if k not in EXCLUDE}
    got = {}
    for dp, _, fns in os.walk(out_root):
        for fn in fns:
            p = Path(dp) / fn
            got[str(p.relative_to(out_root)).replace(os.sep, '/')] = md5(p)
    same, diff, pixel_ok, npz_ok, path_ok = [], [], [], [], []
    for name, h in base.items():
        if name not in got:
            diff.append((name, '基准有而重构缺失'))
        elif got[name] == h:
            same.append(name)
        elif name.endswith('.json') and _json_equal(
                REF / 'baseline_run' / 'outputs' / name, out_root / name):
            path_ok.append(name)
        elif name.endswith('.npz') and _npz_equal(
                REF / 'baseline_run' / 'outputs' / name, out_root / name):
            npz_ok.append(name)
        elif name.endswith('.png') and _pixel_equal(
                REF / 'baseline_run' / 'outputs' / name, out_root / name):
            pixel_ok.append(name)
        else:
            diff.append((name, 'md5不一致'))
    extra = [n for n in got if n not in base and n not in EXCLUDE]
    print(f'逐位一致: {len(same)}  路径归一一致: {len(path_ok)}  NPZ一致: {len(npz_ok)}  '
          f'像素一致: {len(pixel_ok)}  不一致: {len(diff)}  多余: {len(extra)}')
    for name, why in diff:
        print('DIFF', name, why)
    for name in extra:
        print('EXTRA', name)
    for name in path_ok:
        print('PATH-OK', name)
    for name in npz_ok:
        print('NPZ-OK', name)
    for name in pixel_ok:
        print('PIXEL-OK', name)
    return 0 if not diff and not extra else 1


def _json_equal(a: Path, b: Path) -> bool:
    """JSON 逐字段一致视为一致：仅把输出根绝对路径替换为占位符后比较。
    classifications_and_results.json 的 '目录' 字段记录的是运行时输出位置，属路径印记。"""
    import json

    def norm(p: Path):
        root = str(p.parents[1].resolve())  # 各自的输出根（baseline_run/outputs 与 regression_out）
        def rec(x):
            if isinstance(x, dict):
                return {k: rec(v) for k, v in x.items()}
            if isinstance(x, list):
                return [rec(v) for v in x]
            if isinstance(x, str):
                return x.replace(root, '<OUT>')
            return x
        return rec(json.loads(p.read_text(encoding='utf-8')))

    try:
        return norm(a) == norm(b)
    except (ValueError, OSError):
        return False


def _npz_equal(a: Path, b: Path) -> bool:
    """键集一致且全部数组逐位一致视为NPZ一致（npz容器内嵌zip时间戳，md5非确定）。"""
    import numpy as np
    with np.load(a) as za, np.load(b) as zb:
        if set(za.files) != set(zb.files):
            return False
        return all(np.array_equal(za[k], zb[k]) for k in za.files)


def _pixel_equal(a: Path, b: Path) -> bool:
    """同形状且逐像素差为0视为像素一致。"""
    import matplotlib.image as mpimg
    import numpy as np
    ia, ib = mpimg.imread(a), mpimg.imread(b)
    return ia.shape == ib.shape and int(np.abs(ia.astype(float) - ib.astype(float)).max()) == 0


if __name__ == '__main__':
    baseline = Path(sys.argv[1]) if len(sys.argv) > 1 else REF / 'baseline_md5.csv'
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else REF / 'regression_out'
    sys.exit(main(baseline, out))
