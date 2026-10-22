#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2026/10/22
@Author  : weiyutao
@File    : make_national_mask.py

离线一次性生成全国网格海陆分类 CSV（服务端静态掩码，供运行时按行列号查表）。
数据源：ARCO-ERA5 公开桶的 land_sea_mask——原生 ERA5 0.25° 不变量，
与业务 NC 同产品同网格（下载免认证；lsm 与风速场同海岸线，物理自洽）。
判定：lsm > 0.5 → 陆(0)；否则 → 海(1)。
输出 5 列：纬度行,经度列,中心纬度_N,中心经度_E,海陆判定
  纬度行 0..144 = 54.0→18.0°N（步长 0.25，与 2025.nc latitude 一致）
  经度列 0..252 = 73.0→136.0°E（步长 0.25）
运行时匹配：行 = round((54 - lat)/0.25)，列 = round((lon - 73)/0.25)，不做浮点比对。
附带自查：与包内权威 80网格海陆分类.csv 的海南窗口逐格对照（替代已删除的步骤0核验）。
"""
import csv
from pathlib import Path

import numpy as np
import zarr

ARCO = ('https://storage.googleapis.com/gcp-public-data-arco-era5/'
        'ar/full_37-1h-0p25deg-chunk-1.zarr-v3')
LAT0, DLAT = 54.0, -0.25   # 全国网格锚点（实测 2025.nc：54.0°N 起、0.25° 降序）
LON0, DLON = 73.0, 0.25    # 73.0°E 起、0.25° 升序
NROW, NCOL = 145, 253      # 145=54→18°N，253=73→136°E，共 36685 格
ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'data' / '全国网格海陆分类.csv'
REF = ROOT / '海南风光_仅需hainan目录_一键全流程包' / 'data' / '80网格海陆分类.csv'


def fetch_lsm() -> np.ndarray:
    """读 ARCO 2025-01-01 时刻的 land_sea_mask，切全国框 (145, 253)。

    ARCO 全球网格：latitude 90→-90°N 共 721 行、longitude 0→360°E 共 1440 列；
    全国框锚点 = 行144(54°N)、列292(73°E)。切片前先核对锚点坐标，防错位。
    """
    g = zarr.open(store=zarr.storage.FsspecStore.from_url(ARCO), mode='r')
    idx = int((np.datetime64('2025-01-01T00:00:00')
               - np.datetime64('1900-01-01T00:00:00')) / np.timedelta64(1, 'h'))
    r0 = int(round((90.0 - LAT0) / 0.25))    # 144
    c0 = int(round(LON0 / 0.25))             # 292
    if not (float(g['latitude'][r0]) == LAT0 and float(g['longitude'][c0]) == LON0):
        raise ValueError(f'锚点坐标不符: lat[{r0}]={float(g["latitude"][r0])} '
                         f'lon[{c0}]={float(g["longitude"][c0])}')
    lsm = np.asarray(g['land_sea_mask'][idx, r0:r0 + NROW, c0:c0 + NCOL],
                     dtype=np.float32)
    if lsm.shape != (NROW, NCOL) or np.isnan(lsm).any():
        raise ValueError(f'lsm 切片异常: shape={lsm.shape}, '
                         f'NaN={int(np.isnan(lsm).sum())}')
    return lsm


def main() -> None:
    lsm = fetch_lsm()
    lats = LAT0 + DLAT * np.arange(NROW)
    lons = LON0 + DLON * np.arange(NCOL)
    sea = lsm <= 0.5   # 1=海 0=陆
    OUT.parent.mkdir(exist_ok=True)
    with OUT.open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['纬度行', '经度列', '中心纬度_N', '中心经度_E', '海陆判定'])
        for i in range(NROW):
            for j in range(NCOL):
                w.writerow([i, j, f'{lats[i]:.2f}', f'{lons[j]:.2f}', int(sea[i, j])])
    print(f'已生成 {OUT.name}: 海 {int(sea.sum())} / 陆 {int((~sea).sum())} / 共 {sea.size}')
    crosscheck_hainan(sea)


def crosscheck_hainan(sea: np.ndarray) -> None:
    """权威旧表（海南 8×10）逐格对照：换算全国行列后比对海陆。"""
    with REF.open(encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    agree = mismatch = 0
    for r in rows:
        i = int(round((54.0 - float(r['中心纬度_N'])) / 0.25))
        j = int(round((float(r['中心经度_E']) - 73.0) / 0.25))
        if bool(sea[i, j]) == (r['海陆判定'].strip() == '海域'):
            agree += 1
        else:
            mismatch += 1
            print(f'  不一致格: 行{i} 列{j} lat={r["中心纬度_N"]} '
                  f'lon={r["中心经度_E"]} 旧={r["海陆判定"]} 新={"海域" if sea[i, j] else "陆地"}')
    print(f'海南窗口对照: 一致 {agree} / 不一致 {mismatch} / 共 {len(rows)}')


if __name__ == '__main__':
    main()
