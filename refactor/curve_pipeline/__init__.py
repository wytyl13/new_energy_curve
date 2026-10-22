#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2026/10/22 13:00
@Author  : weiyutao
@File    : __init__.py

海南风光九条出力曲线算法包：76年NC → 九条8760小时出力标幺曲线。
对外唯一入口 run_pipeline（请求 dict 进 → 结果 dict 出）。
"""
from .pipeline import run_pipeline

__all__ = ['run_pipeline']
