#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2026/10/22 15:30
@Author  : weiyutao
@File    : make_dim_flow_figure.py

按确认的维度流转文本重绘算法流程图（覆盖 算法流程图.png）。
节点=操作，边=张量形状；纵排主线 + stage1 三泳道。
"""
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrow, FancyBboxPatch

plt.rcParams['font.family'] = ['Microsoft YaHei', 'SimHei']
plt.rcParams['axes.unicode_minus'] = False

C_INPUT = ('#D6E4F7', '#2E5E9E')   # 蓝
C_S1 = ('#D9F0E9', '#1F7A5C')      # 青
C_S2 = ('#FCEFD3', '#B07A1F')      # 琥珀
C_S34 = ('#EBE2F6', '#6C48A8')     # 紫
C_S5 = ('#FAE3E5', '#A63A45')      # 玫红
C_OUT = ('#DFF3D8', '#2F7A33')     # 绿
INK = '#333333'

fig, ax = plt.subplots(figsize=(9.6, 15.2), dpi=200)
ax.set_xlim(0, 100)
ax.set_ylim(158, 0)          # 反转 y：自上而下
ax.axis('off')


def box(x0, y0, w, h, lines, palette, title_bold=True, fs=8.3):
    fill, edge = palette
    ax.add_patch(FancyBboxPatch((x0, y0), w, h, boxstyle='round,pad=0.6',
                                fc=fill, ec=edge, lw=1.4))
    cx = x0 + w / 2
    n = len(lines)
    for i, ln in enumerate(lines):
        first = i == 0 and title_bold
        ax.text(cx, y0 + h * (i + 0.55) / n, ln, ha='center', va='center',
                fontsize=fs + (1.1 if first else 0), color=edge if first else INK,
                fontweight='bold' if first else 'normal',
                fontfamily='Microsoft YaHei' if first or any('一' <= ch <= '鿿' for ch in ln)
                else 'monospace')


def arrow(x, y0, y1, label='', dx_label=1.2):
    ax.add_patch(FancyArrow(x, y0, 0, y1 - y0, width=0.06, head_width=1.6,
                            head_length=1.6, length_includes_head=True,
                            fc=INK, ec=INK))
    if label:
        cjk = any('一' <= ch <= '鿿' for ch in label)
        ax.text(x + dx_label, (y0 + y1) / 2, label, ha='left', va='center',
                fontsize=8, color=INK,
                fontfamily='Microsoft YaHei' if cjk else 'monospace')


# ── 标题 ──
ax.text(50, 4, '海南风光九条出力曲线 · 数据维度流转', ha='center', va='center',
        fontsize=15, fontweight='bold', color=INK)

# ── 输入 ──
box(10, 8, 80, 15, [
    '输入',
    'u100 / v100 (76, 8760, 8, 10)  m/s      76=年份数(1950–2025)',
    'ssrd         (76, 8760, 8, 10)  J/m²    8=纬度格 × 10=经度格 = 80 格点',
    'mask_sea (80,) bool 31海格  |  mask_land (80,) bool 49陆格'], C_INPUT)

# ── stage 1 三泳道 ──
lane_y, lane_h = 30, 22
lanes = [
    (6, '① 海风分支', ['hypot(u100,v100)', '(76,8760,8,10)', '展平→(76,8760,80)',
                        '海格均值 dim=80', '(76, 8760)']),
    (38, '① 陆风分支', ['hypot(u100,v100)', '(76,8760,8,10)', '展平→(76,8760,80)',
                         '陆格均值 dim=80', '(76, 8760)']),
    (70, '① 光伏分支', ['ssrd', '(76,8760,8,10)', '展平→(76,8760,80)',
                         '全格均值÷3600', '(76, 8760)'])]
for lx, title, lines in lanes:
    box(lx, lane_y, 24, lane_h, [title] + lines, C_S1, fs=7.6)
    arrow(lx + 12, 23, lane_y - 0.8)
ax.text(50, 54.6, '空间维在此消失 → 之后全部操作都在 8760 时间轴上（3 份 (76,8760)）',
        ha='center', va='center', fontsize=8.6, color=C_S1[1], fontweight='bold')

# ── stage 2 ──
arrow(50, 56, 61, '(76,8760) ×3', 1.4)
box(10, 62, 80, 17, [
    '② 分档（3 条各自做）',
    '年指标 reduce(dim=8760) → (76,)   76=每年一个标量',
    '风: (1/8760)·Σ v³（功率∝v³，按能量权重）   光: Σ G / 1000（量纲缩放）',
    '76 年排序切三档 → 索引 [19] [38] [19]（大/平均/小 各档年份数）'], C_S2)

# ── stage 3 ──
arrow(50, 79, 84, '(76,) 索引', 1.4)
box(10, 85, 80, 17, [
    '③ 选代表年（9 库各自做，库 = 3资源类型 × 3资源档）',
    'gather 按档取行 (n, 8760)，n ∈ {19, 38, 19}',
    '库内两两 8760 维欧氏距离求和 (n,) → argmin 选最典型 1 行',
    '骨架 rep (8760,) = 真实年整行原样取出   ★ 不做逐年平均'], C_S34)

# ── stage 4 ──
arrow(50, 102, 107, '(8760,)', 1.4)
box(10, 108, 80, 17, [
    '④ 修极端（形状不变，替换部分值）',
    '风: ≥3h 连续段替换（配额贴 76 年 P10/P90，段间隔 3h，每日 ≤1 段）',
    '光: 低光日整日替换，一次 24 小时',
    '插后 (8760,) + 修改标记 (8760,) bool   ★ 真实片段换真实片段'], C_S34)

# ── stage 5 ──
arrow(50, 125, 130, '(8760,)', 1.4)
box(10, 131, 80, 14, [
    '⑤ 出力（逐元素确定性映射，插前/插后各一遍）',
    '风: 功率曲线  0 → 立方爬坡 → 顶格α → 0（海 4/11/25 α0.70｜陆 2.5/9/18 α0.95）',
    '光: 0.6 · G / 1000                                          → (8760,)'], C_S5, fs=7.9)

# ── 输出 ──
arrow(50, 145, 150, '(8760,) ×9', 1.4)
box(8, 151, 84, 13.5, [
    '总输出（9 = 3资源类型(海风/陆风/光伏) × 3资源档(大/平均/小)）',
    '资源与出力曲线 (9, 8760, 4)   4 = 插前资源/插后资源/插前出力/插后出力',
    '修改标记 (9, 8760) bool    利用小时 (9,) = 出力沿 8760 求和（等效满发小时）'], C_OUT, fs=7.9)

# ── 右侧不变式括注 ──
ax.plot([95.2, 95.2], [86, 144], color=C_S34[1], lw=1.2, ls=(0, (4, 3)))
ax.plot([94.2, 95.2], [86, 86], color=C_S34[1], lw=1.2)
ax.plot([94.2, 95.2], [144, 144], color=C_S34[1], lw=1.2)
ax.text(97.2, 115, '③④⑤ 9 库各自执行\n形状锁定 (8760,)\n取行/换值，无合成数据', rotation=90,
        ha='center', va='center', fontsize=8.6, color=C_S34[1], fontweight='bold')

out = Path(__file__).resolve().parent / '算法流程图.png'
fig.savefig(out, bbox_inches='tight', facecolor='white')
print('saved:', out)
