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


class TurbineParams(BaseModel):
    """单个风区的风机机组参数；不传的字段落冻结默认值。"""
    cut_in: float | None = Field(None, description='切入风速 m/s；默认 海4/陆2.5')
    rated: float | None = Field(None, description='额定风速 m/s；默认 海11/陆9')
    cut_out: float | None = Field(None, description='切出风速 m/s；默认 海25/陆18')
    alpha: float | None = Field(None, description='顶格系数（满发时的标幺出力）；默认 海0.70/陆0.95')


class WindParams(BaseModel):
    """风机参数：海/陆各一组，均可整体省略。"""
    sea: TurbineParams | None = Field(None, description='海上风机组参数')
    land: TurbineParams | None = Field(None, description='陆上风机组参数')


class PvParams(BaseModel):
    """光伏参数。"""
    efficiency: float | None = Field(None, description='综合效率系数；默认 0.6，出力标幺 = 效率×辐照/1000')


class ComputeReq(BaseModel):
    """同步计算请求体。"""
    resource: str = Field(..., description="资源类型：'wind'（风，一次算出海风+陆风）或 'solar'（光伏）")
    scenario: str = Field(..., description="资源场景：'normal' 正常 / 'high' 大 / 'low' 小 / 'all' 全部")
    data_dir: str = Field(..., description='输入目录绝对路径，内含每年一个区域CSV（列名 *_lat_x_lon_y）')
    output_dir: str | None = Field(None, description='可选结果输出目录；缺省写 outputs/<时间戳_短随机>/')
    wind_params: WindParams | None = Field(None, description='可选风机参数（不传用冻结默认：海 4/11/25 m/s α=0.70，陆 2.5/9/18 m/s α=0.95）')
    pv_params: PvParams | None = Field(None, description='可选光伏参数（不传用冻结默认：综合效率 0.6）')
    wind_zone: str = Field('all', description="可选风区口径（仅 wind 生效）：'sea' 全区统一按海风处理 / 'land' 全区统一按陆风处理 / 'all'（缺省）按掩码自动分海陆、空区跳过（支持纯海/纯陆区域）")
