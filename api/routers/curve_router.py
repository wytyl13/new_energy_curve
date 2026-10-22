#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2026/10/22 21:30
@Author  : weiyutao
@File    : curve_router.py

曲线计算 HTTP 路由：单一同步计算接口（阻塞至完成，直接返回摘要+曲线数据）。
"""
from __future__ import annotations

from fastapi import APIRouter

from api.response import make_response
from api.schema.curve_schema import ComputeReq
from core.compute import compute

router = APIRouter(prefix='/api/curve', tags=['curve'])


@router.post('/compute')
def compute_curve(req: ComputeReq):
    """同步计算：阻塞等待完成，响应内直接带曲线数据（文件仍写 outputs/ 留档）。"""
    data = compute(req.resource, req.scenario, req.data_dir, req.output_dir)
    return make_response(True, '计算完成', data)
