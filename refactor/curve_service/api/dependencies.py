#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2026/10/22 13:00
@Author  : weiyutao
@File    : dependencies.py

依赖装配：JobManager 单例工厂。
"""
from __future__ import annotations

from functools import lru_cache

from curve_service.core.manager.job_manager import JobManager
from curve_service.core.results import outputs_root


@lru_cache(maxsize=1)
def get_job_manager() -> JobManager:
    """进程内唯一的任务管理器实例。"""
    return JobManager(str(outputs_root()))
