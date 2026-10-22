#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2026/10/22 13:00
@Author  : weiyutao
@File    : curve_router.py

曲线流水线 HTTP 路由：任务提交/状态、结果读取。
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter

from curve_service.api.dependencies import get_job_manager
from curve_service.api.response import make_response
from curve_service.api.schema.curve_schema import CurveJobReq, CurveReq, JobStatusReq
from curve_service.core import results

router = APIRouter(prefix='/api/curve', tags=['curve'])


@router.post('/jobs')
async def create_job(req: CurveJobReq):
    """提交流水线后台任务（hainan 目录 → 九条出力曲线）。"""
    job_id = get_job_manager().submit(req.hainan_dir)
    return make_response(True, '任务已提交', {'job_id': job_id})


@router.post('/jobs/status')
async def job_status(req: JobStatusReq):
    """查询任务状态与进度。"""
    status = get_job_manager().status(req.job_id)
    return make_response(True, '查询成功', status)


@router.get('/libraries')
async def libraries():
    """九库摘要：代表年、插入次数、插前/插后利用小时。"""
    data = await asyncio.to_thread(results.list_libraries)
    return make_response(True, '查询成功', data)


@router.post('/results/curve')
async def curve(req: CurveReq):
    """单库8760小时曲线（资源与出力标幺）。"""
    data = await asyncio.to_thread(results.read_curve, req.library)
    return make_response(True, '查询成功', data)


@router.get('/results/summary')
async def summary():
    """汇总：最大利用小时表、复核结果、九库代表年。"""
    data = await asyncio.to_thread(results.read_summary)
    return make_response(True, '查询成功', data)
