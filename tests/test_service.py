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

    n_ok = sum(ok for _, ok in checks)
    for name, ok in checks:
        print(('PASS' if ok else 'FAIL'), name)
    print(f'{n_ok}/{len(checks)} 通过')
    assert n_ok == len(checks), '存在失败项'


if __name__ == '__main__':
    main()
