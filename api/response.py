#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2026/10/22 21:00
@Author  : weiyutao
@File    : response.py

统一响应包装：所有接口经 make_response 返回
{success, message, data, timestamp}。（自 refactor/curve_service 平移）
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi.encoders import jsonable_encoder


def make_response(success: bool, message: str, data: Any = None, code: int | None = None) -> dict:
    """构造统一响应体。

    Args:
        success (bool): 是否成功。
        message (str): 面向用户的说明。
        data (Any): 结果数据。
        code (int | None): 业务子码，可选。

    Returns:
        dict: {success, message, data, timestamp[, code]}。
    """
    body = {'success': success, 'message': message,
            'data': jsonable_encoder(data),
            'timestamp': datetime.now(timezone.utc).isoformat()}
    if code is not None:
        body['code'] = code
    return body
