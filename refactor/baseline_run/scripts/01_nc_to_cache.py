"""Build the 76-year wind/solar caches from the supplied hourly NetCDF files.

Expected NC variables: valid_time, latitude, longitude, u100, v100 (wind)
and valid_time, latitude, longitude, ssrd (solar). SSRD must be hourly
accumulated J/m2. Files may each contain one year or multiple years.
"""
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import netCDF4 as nc
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
GRID = ROOT / 'data' / '80网格海陆分类.csv'
YEARS = range(1950, 2026)


def grid_spec():
    with GRID.open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 80:
        raise ValueError(f'海陆格点表应有80行，实际{len(rows)}行')
    sea = [int(r['网格ID_从0']) for r in rows if r['海陆判定'] == '海域']
    land = [int(r['网格ID_从0']) for r in rows if r['海陆判定'] == '陆地']
    if len(sea) != 31 or len(land) != 49:
        raise ValueError('格点数须为31个海域格和49个陆地格')
    return rows, sea, land


def nc_times(ds, start, stop):
    t = ds['valid_time']
    return nc.num2date(t[start:stop], t.units, calendar=getattr(t, 'calendar', 'standard'))


def check_grid(ds, rows):
    lat = np.asarray(ds['latitude'][:], dtype=float)
    lon = np.asarray(ds['longitude'][:], dtype=float)
    if lat.size * lon.size != 80:
        raise ValueError(f'NC须有80个网格，实际{lat.size}×{lon.size}')
    for row in rows:
        i, j = int(row['纬度行']), int(row['经度列'])
        if not np.isclose(lat[i], float(row['中心纬度_N']), atol=1e-6) or not np.isclose(lon[j], float(row['中心经度_E']), atol=1e-6):
            raise ValueError('NC经纬度或排列次序与格点表不一致')


def load_one_resource(folder: Path, kind: str, rows, sea, land):
    files = [folder] if folder.is_file() and folder.suffix.lower()=='.nc' else sorted(folder.rglob('*.nc'))
    if not files:
        raise FileNotFoundError(f'{folder} 中未找到NC文件')
    chunks = defaultdict(list)
    for path in files:
        with nc.Dataset(path) as ds:
            check_grid(ds, rows)
            if kind != 'wind':
                unit = str(getattr(ds['ssrd'], 'units', '')).lower().replace(' ', '')
                if 'j' not in unit or 'm' not in unit:
                    raise ValueError(f'{path}: ssrd单位须为J/m²的一小时累计值，实际{unit!r}')
            # One NC may contain all 76 years. Read at most 8784 hours at a time
            # so the 80-cell wind arrays do not consume gigabytes of RAM.
            for start in range(0, len(ds['valid_time']), 8784):
                stop = min(start+8784, len(ds['valid_time']))
                times = nc_times(ds, start, stop)
                if kind == 'wind':
                    u = np.ma.filled(ds['u100'][start:stop], np.nan).astype(float)
                    v = np.ma.filled(ds['v100'][start:stop], np.nan).astype(float)
                    speed = np.hypot(u, v).reshape(len(times), 80)
                    values = np.column_stack((speed[:, sea].mean(axis=1), speed[:, land].mean(axis=1)))
                else:
                    ssrd = np.ma.filled(ds['ssrd'][start:stop], np.nan).astype(float)
                    values = ssrd.reshape(len(times), 80).mean(axis=1) / 3600.0
                if not np.isfinite(values).all():
                    raise ValueError(f'{path} 包含缺失/无穷值')
                for year in sorted({int(t.year) for t in times if int(t.year) in YEARS}):
                    take = np.array([int(t.year) == year and not (int(t.month) == 2 and int(t.day) == 29) for t in times])
                    stamps = [(int(t.month), int(t.day), int(t.hour)) for t, use in zip(times, take) if use]
                    chunks[year].append((stamps, values[take]))
        print(kind, path.name, flush=True)
    result = {}
    expected = [(t.month, t.day, t.hour) for t in (datetime(2001, 1, 1) + timedelta(hours=i) for i in range(8760))]
    for year in YEARS:
        if year not in chunks:
            raise ValueError(f'{kind}缺少{year}年NC数据；一年的NC不能推算76年历史库')
        stamps = sum((part[0] for part in chunks[year]), [])
        arrays = [part[1] for part in chunks[year]]
        value = np.concatenate(arrays, axis=0)
        order = sorted(range(len(stamps)), key=lambda i: stamps[i])
        if [stamps[i] for i in order] != expected:
            raise ValueError(f'{kind}{year}年删除2月29日后不是完整且无重复的8760小时')
        result[year] = value[order]
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--wind-dir', type=Path, required=True, help='包含u100/v100逐小时NC文件的文件夹')
    p.add_argument('--solar-dir', type=Path, required=True, help='包含ssrd逐小时NC文件的文件夹')
    a = p.parse_args()
    rows, sea, land = grid_spec()
    wind = load_one_resource(a.wind_dir, 'wind', rows, sea, land)
    solar = load_one_resource(a.solar_dir, 'solar', rows, sea, land)
    out_w = ROOT / 'outputs' / '海南海陆全网格等权方案'
    out_s = ROOT / 'outputs' / '海南年聚类与月聚类公平对照'
    out_w.mkdir(parents=True, exist_ok=True)
    out_s.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out_w/'海陆两类_76年8760小时风速.npz',
                        **{f'{y}_{zone}': wind[y][:, i] for y in YEARS for i, zone in enumerate(('sea', 'land'))})
    np.savez_compressed(out_s/'光伏76年资源缓存.npz',
                        **{str(y): solar[y] for y in YEARS})
    with (out_w/'80网格海陆分类.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader(); writer.writerows(rows)
    print('缓存已生成：', out_w, out_s)


if __name__ == '__main__':
    main()
