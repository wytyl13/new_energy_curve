#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2026/10/22 13:00
@Author  : weiyutao
@File    : app_server.py

服务入口：FastAPI 应用装配（CORS、请求日志、异常处理、健康检查、路由挂载）。
"""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from curve_service.api.response import make_response
from curve_service.api.routers.curve_router import router as curve_router

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(levelname)s %(message)s')
logger = logging.getLogger('app_server')


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动/关闭钩子。"""
    logger.info('curve_service 启动')
    yield
    logger.info('curve_service 关闭')


def create_app() -> FastAPI:
    """装配 FastAPI 应用。"""
    app = FastAPI(title='海南风光九条出力曲线服务', version='1.0.0', lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'],
                       allow_credentials=True, allow_headers=['*'])

    @app.middleware('http')
    async def log_requests(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        logger.info('%s %s -> %s (%.1fms)', request.method, request.url.path,
                    response.status_code, (time.perf_counter() - start) * 1000)
        return response

    @app.get('/api/health')
    async def health():
        return {'status': 'ok', 'message': '服务运行中',
                'timestamp': datetime.now(timezone.utc).isoformat()}

    @app.exception_handler(LookupError)
    async def not_found_handler(request: Request, exc: LookupError):
        return JSONResponse(status_code=404, content=make_response(False, str(exc)))

    @app.exception_handler(ValueError)
    async def bad_request_handler(request: Request, exc: ValueError):
        return JSONResponse(status_code=400, content=make_response(False, str(exc)))

    @app.exception_handler(Exception)
    async def internal_handler(request: Request, exc: Exception):
        logger.exception('未处理异常 %s %s', request.method, request.url.path)
        return JSONResponse(status_code=500,
                            content=make_response(False, f'Internal Server Error: {exc}'))

    app.include_router(curve_router)
    return app


app = create_app()
