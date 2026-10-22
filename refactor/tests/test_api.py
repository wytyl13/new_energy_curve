#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2026/10/22 13:00
@Author  : weiyutao
@File    : test_api.py

接口测试：TestClient 覆盖全部端点（含一次真实 hainan 目录的端到端任务）。
运行：cd refactor && python tests/test_api.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from curve_service.api.server.app_server import app

HAINAN = Path(__file__).resolve().parents[2] / 'hainan'
PASSED = []


def check(name: str, cond: bool, detail: str = ''):
    """断言并记录。"""
    assert cond, f'{name} 失败: {detail}'
    PASSED.append(name)
    print(f'PASS {name}' + (f' ({detail})' if detail else ''))


def main() -> None:
    """顺序执行全部端点测试。"""
    client = TestClient(app)

    r = client.get('/api/health')
    check('health 200', r.status_code == 200)
    check('health 结构', set(r.json()) == {'status', 'message', 'timestamp'} and r.json()['status'] == 'ok')

    r = client.get('/api/curve/libraries')
    body = r.json()
    check('libraries 200', r.status_code == 200)
    check('libraries 包装', body['success'] is True and len(body['data']) == 9)
    first = body['data'][0]
    check('libraries 字段', {'library', '曲线名', '代表年', '插入次数', '修改小时',
                             '插入前最大利用小时_h', '插入后最大利用小时_h'} <= set(first),
          f"first={first['library']} 代表年{first['代表年']}")

    r = client.post('/api/curve/results/curve', json={'library': 'wind_sea_high'})
    body = r.json()
    curve = body['data']
    check('curve 200', r.status_code == 200)
    check('curve 契约', curve['sheet_name'] == '海风_大风资源年' and len(curve['index']) == 8760
          and [d['column_name'] for d in curve['data']] == ['海风_大风资源年_插前资源',
          '海风_大风资源年_插后资源', '海风_大风资源年_插前出力pu', '海风_大风资源年_插后出力pu']
          and all(len(d['data']) == 8760 for d in curve['data']), '8760×4列')

    r = client.post('/api/curve/results/curve', json={'library': 'no_such_lib'})
    check('curve 非法库 400', r.status_code == 400 and r.json()['success'] is False)

    r = client.get('/api/curve/results/summary')
    body = r.json()
    check('summary 200', r.status_code == 200 and body['success'] is True)
    check('summary 内容', len(body['data']['九条最大利用小时']) == 9
          and body['data']['复核结果']['通过'] is True and len(body['data']['代表年']) == 9)

    r = client.post('/api/curve/jobs/status', json={'job_id': 'not-exist'})
    check('status 不存在 404', r.status_code == 404 and r.json()['success'] is False)

    r = client.post('/api/curve/jobs', json={'hainan_dir': str(Path('D:/no/such/dir'))})
    check('jobs 无效目录 400', r.status_code == 400 and r.json()['success'] is False)

    r = client.post('/api/curve/jobs', json={'hainan_dir': str(HAINAN)})
    check('jobs 提交 200', r.status_code == 200 and r.json()['success'] is True)
    job_id = r.json()['data']['job_id']
    print(f'  端到端任务 {job_id} 运行中（真实全流程，约2-4分钟）...')
    deadline = time.time() + 900
    last = {}
    while time.time() < deadline:
        s = client.post('/api/curve/jobs/status', json={'job_id': job_id}).json()['data']
        if s != last:
            print(f"  {s['status']:>9} {s['progress']:.0%} {s['detailed_status']}")
            last = s
        if s['status'] in ('succeeded', 'failed'):
            break
        time.sleep(5)
    check('jobs 端到端成功', s['status'] == 'succeeded' and s['progress'] == 1.0, s['detailed_status'])

    r = client.get('/api/curve/libraries')
    check('任务后 libraries 仍可用', r.status_code == 200 and len(r.json()['data']) == 9)

    print(f'\n全部通过：{len(PASSED)} 项')


if __name__ == '__main__':
    main()
