#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2026/10/22 20:00
@Author  : weiyutao
@File    : __init__.py

new_energy 核心算法包：分步骤模块 + pipeline 组合，唯一入口 run()。
"""
from .pipeline import run

__all__ = ['run']
