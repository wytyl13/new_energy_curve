#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2026/10/22 21:00
@Author  : weiyutao
@File    : start_server.py

服务启动脚本：python start_server.py --port 8000
结果根目录：环境变量 CURVE_OUTPUTS_ROOT，缺省项目根下 outputs/。
"""
from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='风光出力曲线计算服务')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    uvicorn.run('api.server.app_server:app', host=args.host, port=args.port,
                app_dir=str(Path(__file__).resolve().parent))
