#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2026/10/22 21:40
@Author  : weiyutao
@File    : test_service.py

服务接口测试（TestClient，同步计算接口 + 一次真实端到端）。
运行：python tests/test_service.py（在项目根下）
样本 data/wind 由使用者随时替换（海陆构成不定），期望表集合运行时探测，
测试不写死构成。
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from api.server.app_server import app  # noqa: E402
from new_energy.power import WIND_PARAMS, wind_power  # noqa: E402

DATA_WIND = Path(__file__).resolve().parents[1] / 'data' / 'wind'
CURVE = {'sea': '海风', 'land': '陆风'}


def _zones_present() -> list[str]:
    """探测样本数据按全国掩码的非空风区（sea/land）。"""
    import csv
    import re

    from new_energy.mask_lookup import sea_flags

    fp = sorted(DATA_WIND.glob('*.csv'))[0]
    cols = next(csv.reader(fp.open(encoding='utf-8-sig')))[1:]
    lats = [float(re.search(r'lat_([0-9.]+)_lon_', c).group(1)) for c in cols]
    lons = [float(re.search(r'lon_([0-9.]+)$', c).group(1)) for c in cols]
    flags = sea_flags(lats, lons)
    return [z for z in ('sea', 'land') if (flags if z == 'sea' else ~flags).any()]


def _land_only_dir(dst: Path) -> Path:
    """由 DATA_WIND 生成仅保留陆格列的纯陆区域数据目录（供空区跳过测试）。"""
    import csv
    import re

    from new_energy.mask_lookup import sea_flags

    dst.mkdir(parents=True, exist_ok=True)
    for fp in sorted(DATA_WIND.glob('*.csv')):
        rows = list(csv.reader(fp.open(encoding='utf-8-sig')))
        cols = rows[0][1:]
        lats = [float(re.search(r'lat_([0-9.]+)_lon_', c).group(1)) for c in cols]
        lons = [float(re.search(r'lon_([0-9.]+)$', c).group(1)) for c in cols]
        keep = [0] + [k for k, sea in enumerate(sea_flags(lats, lons), 1) if not sea]
        with (dst / fp.name).open('w', encoding='utf-8-sig', newline='') as f:
            w = csv.writer(f)
            for r in rows:
                w.writerow([r[k] for k in keep])
    return dst


def main() -> None:
    checks = []
    zones = _zones_present()
    tables = sorted(f'{CURVE[z]}-正常-{k}' for z in zones for k in ('资源', '出力'))
    with TestClient(app) as client:
        r = client.get('/api/health')
        checks.append(('健康检查 200', r.status_code == 200 and r.json()['status'] == 'ok'))

        r = client.post('/api/curve/compute', json={'resource': 'xxx', 'scenario': 'all',
                                                    'data_dir': str(DATA_WIND)})
        checks.append(('非法 resource → 400', r.status_code == 400))

        r = client.post('/api/curve/compute', json={'resource': 'wind', 'scenario': 'xx',
                                                    'data_dir': str(DATA_WIND)})
        checks.append(('非法 scenario → 400', r.status_code == 400))

        r = client.post('/api/curve/compute', json={'resource': 'wind', 'scenario': 'all',
                                                    'data_dir': r'C:\不存在'})
        checks.append(('目录不存在 → 400', r.status_code == 400))

        # 端到端：wind + normal（阻塞直返，指定 output_dir 便于核对落盘文件）
        with tempfile.TemporaryDirectory() as td:
            r = client.post('/api/curve/compute',
                            json={'resource': 'wind', 'scenario': 'normal',
                                  'data_dir': str(DATA_WIND), 'output_dir': td})
            assert r.status_code == 200, r.text
            body = r.json()
            checks.append(('success=True', body['success'] is True))
            data = body['data']
            z0 = zones[0]
            checks.append((f'data 为 {len(tables)} 张表（曲线-场景-资源/出力，非空风区）',
                           sorted(data) == tables))
            checks.append(('每表 list 长 1 且 sheet_name 同名',
                           all(len(data[k]) == 1 and data[k][0]['sheet_name'] == k for k in data)))
            res = data[f'{CURVE[z0]}-正常-资源'][0]
            checks.append(('index 8760', len(res['index']) == 8760))
            checks.append(('资源两列各 8760',
                           [c['column_name'] for c in res['data']] == ['插入前资源', '插入后资源']
                           and all(len(c['data']) == 8760 for c in res['data'])))
            pow_ = data[f'{CURVE[z0]}-正常-出力'][0]
            checks.append(('出力两列各 8760',
                           [c['column_name'] for c in pow_['data']] == ['插入前出力', '插入后出力']
                           and all(len(c['data']) == 8760 for c in pow_['data'])))
            checks.append(('出力值域 0~1',
                           all(0.0 <= v <= 1.0 for v in pow_['data'][0]['data'][:100])))
            checks.append((f'{len(tables)} 个结果文件写入指定目录',
                           all((Path(td) / f'{k}.csv').exists() for k in tables)))

            # 缺省路径回归：不传新参数时出力 = 冻结公式逐点一致（插入前全列）
            frozen = [wind_power(v, *WIND_PARAMS[z0])
                      for v in res['data'][0]['data']]
            checks.append(('缺省路径出力=冻结公式（插入前全列）',
                           all(abs(a - b) < 1e-9
                               for a, b in zip(frozen, pow_['data'][0]['data']))))

        # 自定义风机参数生效（sea 改 rated/alpha，land 改 cut_in，其余落默认；按非空风区核对）
        with tempfile.TemporaryDirectory() as td:
            r = client.post('/api/curve/compute',
                            json={'resource': 'wind', 'scenario': 'normal',
                                  'data_dir': str(DATA_WIND), 'output_dir': td,
                                  'wind_params': {'sea': {'rated': 8., 'alpha': .9},
                                                  'land': {'cut_in': 3.}}})
            assert r.status_code == 200, r.text
            d = r.json()['data']
            if 'sea' in zones:
                sea_exp = [wind_power(v, 4., 8., 25., .9)
                           for v in d['海风-正常-资源'][0]['data'][0]['data']]
                checks.append(('自定义海风参数生效',
                               all(abs(a - b) < 1e-9 for a, b in
                                   zip(sea_exp, d['海风-正常-出力'][0]['data'][0]['data']))))
            if 'land' in zones:
                land_exp = [wind_power(v, 3., 9., 18., .95)
                            for v in d['陆风-正常-资源'][0]['data'][0]['data']]
                checks.append(('自定义陆风参数生效',
                               all(abs(a - b) < 1e-9 for a, b in
                                   zip(land_exp, d['陆风-正常-出力'][0]['data'][0]['data']))))

        # 非法参数 → 400
        for name, extra in [
                ('额定≤切入 → 400', {'wind_params': {'sea': {'rated': 3.}}}),
                ('α>1 → 400', {'wind_params': {'sea': {'alpha': 1.5}}}),
                ('效率≤0 → 400', {'pv_params': {'efficiency': 0.}})]:
            r = client.post('/api/curve/compute',
                            json={'resource': 'wind', 'scenario': 'all',
                                  'data_dir': str(DATA_WIND), **extra})
            checks.append((name, r.status_code == 400))

        # wind_zone：sea/land 全区统一按该风区处理（不查掩码）；非法值 → 400
        with tempfile.TemporaryDirectory() as td:
            r = client.post('/api/curve/compute',
                            json={'resource': 'wind', 'scenario': 'normal',
                                  'data_dir': str(DATA_WIND), 'output_dir': td,
                                  'wind_zone': 'land'})
            assert r.status_code == 200, r.text
            d = r.json()['data']
            checks.append(('wind_zone=land 只算陆风 2 表',
                           sorted(d) == ['陆风-正常-出力', '陆风-正常-资源']))
            land_exp = [wind_power(v, *WIND_PARAMS['land'])
                        for v in d['陆风-正常-资源'][0]['data'][0]['data']]
            checks.append(('land 全区统一 → 陆风机参数出力',
                           all(abs(a - b) < 1e-9 for a, b in
                               zip(land_exp, d['陆风-正常-出力'][0]['data'][0]['data']))))

        with tempfile.TemporaryDirectory() as td:
            r = client.post('/api/curve/compute',
                            json={'resource': 'wind', 'scenario': 'normal',
                                  'data_dir': str(DATA_WIND), 'output_dir': td,
                                  'wind_zone': 'sea'})
            assert r.status_code == 200, r.text
            checks.append(('wind_zone=sea 只算海风 2 表（纯陆数据强制海风同样成立）',
                           sorted(r.json()['data']) == ['海风-正常-出力', '海风-正常-资源']))

        r = client.post('/api/curve/compute',
                        json={'resource': 'wind', 'scenario': 'normal',
                              'data_dir': str(DATA_WIND), 'wind_zone': 'xx'})
        checks.append(('非法 wind_zone → 400', r.status_code == 400))

        # 纯陆区域 + 缺省 wind_zone=all：空区跳过，只算陆风
        if 'land' in zones:
            with tempfile.TemporaryDirectory() as td:
                with tempfile.TemporaryDirectory() as od:
                    r = client.post('/api/curve/compute',
                                    json={'resource': 'wind', 'scenario': 'normal',
                                          'data_dir': str(_land_only_dir(Path(td) / 'land_only')),
                                          'output_dir': od})
                    assert r.status_code == 200, r.text
                    checks.append(('纯陆区域 all 空区跳过只算陆风',
                                   sorted(r.json()['data']) == ['陆风-正常-出力', '陆风-正常-资源']))

    n_ok = sum(ok for _, ok in checks)
    for name, ok in checks:
        print(('PASS' if ok else 'FAIL'), name)
    print(f'{n_ok}/{len(checks)} 通过')
    assert n_ok == len(checks), '存在失败项'


if __name__ == '__main__':
    main()
