#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2026/10/22 21:40
@Author  : weiyutao
@File    : test_service.py

服务接口测试（TestClient，同步计算接口 + 一次真实端到端）。
运行：python tests/test_service.py（在项目根下）
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
TABLES = ['海风-正常-资源', '海风-正常-出力', '陆风-正常-资源', '陆风-正常-出力']


def main() -> None:
    checks = []
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
            checks.append(('data 为 4 张表（曲线-场景-资源/出力）', sorted(data) == sorted(TABLES)))
            checks.append(('每表 list 长 1 且 sheet_name 同名',
                           all(len(data[k]) == 1 and data[k][0]['sheet_name'] == k for k in data)))
            res = data['海风-正常-资源'][0]
            checks.append(('index 8760', len(res['index']) == 8760))
            checks.append(('资源两列各 8760',
                           [c['column_name'] for c in res['data']] == ['插入前资源', '插入后资源']
                           and all(len(c['data']) == 8760 for c in res['data'])))
            pow_ = data['海风-正常-出力'][0]
            checks.append(('出力两列各 8760',
                           [c['column_name'] for c in pow_['data']] == ['插入前出力', '插入后出力']
                           and all(len(c['data']) == 8760 for c in pow_['data'])))
            checks.append(('出力值域 0~1',
                           all(0.0 <= v <= 1.0 for v in pow_['data'][0]['data'][:100])))
            checks.append(('4 个结果文件写入指定目录',
                           all((Path(td) / f'{k}.csv').exists() for k in TABLES)))

            # 缺省路径回归：不传新参数时出力 = 冻结公式逐点一致（海风插入前全列）
            frozen = [wind_power(v, *WIND_PARAMS['sea'])
                      for v in res['data'][0]['data']]
            checks.append(('缺省路径出力=冻结公式（海风插入前全列）',
                           all(abs(a - b) < 1e-9
                               for a, b in zip(frozen, pow_['data'][0]['data']))))

        # 自定义风机参数生效（sea 改 rated/alpha，land 改 cut_in，其余落默认）
        with tempfile.TemporaryDirectory() as td:
            r = client.post('/api/curve/compute',
                            json={'resource': 'wind', 'scenario': 'normal',
                                  'data_dir': str(DATA_WIND), 'output_dir': td,
                                  'wind_params': {'sea': {'rated': 8., 'alpha': .9},
                                                  'land': {'cut_in': 3.}}})
            assert r.status_code == 200, r.text
            d = r.json()['data']
            sea_exp = [wind_power(v, 4., 8., 25., .9)
                       for v in d['海风-正常-资源'][0]['data'][0]['data']]
            checks.append(('自定义海风参数生效',
                           all(abs(a - b) < 1e-9 for a, b in
                               zip(sea_exp, d['海风-正常-出力'][0]['data'][0]['data']))))
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

    n_ok = sum(ok for _, ok in checks)
    for name, ok in checks:
        print(('PASS' if ok else 'FAIL'), name)
    print(f'{n_ok}/{len(checks)} 通过')
    assert n_ok == len(checks), '存在失败项'


if __name__ == '__main__':
    main()
