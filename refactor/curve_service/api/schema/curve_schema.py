#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2026/10/22 13:00
@Author  : weiyutao
@File    : curve_schema.py

HTTP 请求体模型（Pydantic）。
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class CurveJobReq(BaseModel):
    """提交流水线任务的请求体。"""
    hainan_dir: str = Field(..., description='包含 wind/、solar/ 的 hainan 数据目录绝对路径')


class JobStatusReq(BaseModel):
    """查询任务状态的请求体。"""
    job_id: str = Field(..., description='任务ID，由 POST /api/curve/jobs 返回')


class CurveReq(BaseModel):
    """查询单库8760小时曲线的请求体。"""
    library: str = Field(..., description='库目录名，如 wind_sea_high、solar_low，取值见 GET /api/curve/libraries')
