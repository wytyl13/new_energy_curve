#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2026/10/22 21:30
@Author  : weiyutao
@File    : curve_schema.py

HTTP 请求体模型（Pydantic）。
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ComputeReq(BaseModel):
    """同步计算请求体。"""
    resource: str = Field(..., description="资源类型：'wind'（风，一次算出海风+陆风）或 'solar'（光伏）")
    scenario: str = Field(..., description="资源场景：'normal' 正常 / 'high' 大 / 'low' 小 / 'all' 全部")
    data_dir: str = Field(..., description='输入目录绝对路径，内含每年一个区域CSV（列名 *_lat_x_lon_y）')
    output_dir: str | None = Field(None, description='可选结果输出目录；缺省写 outputs/<时间戳_短随机>/')
