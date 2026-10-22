#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2026/10/22 13:00
@Author  : weiyutao
@File    : start_server.py

服务启动脚本：python start_server.py [--port 8000]
需在 refactor/ 目录下运行（curve_pipeline 与 curve_service 均以本目录为包根）。
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

import uvicorn


def main() -> None:
    """解析端口参数并启动 uvicorn。"""
    parser = argparse.ArgumentParser(description='海南风光九条出力曲线服务')
    parser.add_argument('--port', type=int, default=8000, help='监听端口，默认8000')
    args = parser.parse_args()
    uvicorn.run('curve_service.api.server.app_server:app', host='0.0.0.0',
                port=args.port, log_level='info')


if __name__ == '__main__':
    main()
