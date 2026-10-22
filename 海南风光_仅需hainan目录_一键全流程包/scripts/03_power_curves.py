"""Convert the nine inserted resource curves into hourly normalized output."""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'outputs' / '风光完整分类聚类插入程序结果'
OUT = ROOT / 'outputs' / '九条出力曲线_原参数'
CASES = [
    ('wind_sea_high', '海风_大风资源年', (4., 11., 25., .7)),
    ('wind_sea_mid', '海风_平均风资源年', (4., 11., 25., .7)),
    ('wind_sea_low', '海风_小风资源年', (4., 11., 25., .7)),
    ('wind_land_high', '陆风_大风资源年', (2.5, 9., 18., .95)),
    ('wind_land_mid', '陆风_平均风资源年', (2.5, 9., 18., .95)),
    ('wind_land_low', '陆风_小风资源年', (2.5, 9., 18., .95)),
    ('solar_high', '大光资源年', None),
    ('solar_mid', '平均光资源年', None),
    ('solar_low', '小光资源年', None),
]


def wind_power(v, ci, rated, co, alpha):
    if v < ci or v >= co:
        return 0.
    if v >= rated:
        return alpha
    return alpha * (v**3-ci**3)/(rated**3-ci**3)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    series = []
    summary = []
    labels = None
    for folder, name, settings in CASES:
        with (SRC/folder/'curve_8760.csv').open(encoding='utf-8-sig', newline='') as f:
            rows = list(csv.DictReader(f))
        if len(rows) != 8760:
            raise ValueError(f'{name}不是8760小时')
        current_labels = [r['月日时_UTC'] for r in rows]
        if labels is None:
            labels = current_labels
        elif labels != current_labels:
            raise ValueError(f'{name}与其他曲线时间轴不一致')
        before = [float(r['插前资源']) for r in rows]
        after = [float(r['插后资源']) for r in rows]
        fn = (lambda v: .6*max(v, 0.)/1000.) if settings is None else (lambda v: wind_power(v,*settings))
        p0 = [fn(v) for v in before]
        p1 = [fn(v) for v in after]
        series.append((name, before, after, p0, p1))
        summary.append({'曲线':name, '插入前最大利用小时_h':sum(p0),
                        '插入后最大利用小时_h':sum(p1),
                        '增减_h':sum(p1)-sum(p0),
                        '换算参数':('光伏α=0.6，G/1000' if settings is None else f'风机{settings[0]:g}/{settings[1]:g}/{settings[2]:g}m/s，α={settings[3]:g}')})
    with (OUT/'九条8760小时_插前插后资源与出力.csv').open('w',encoding='utf-8-sig',newline='') as f:
        header=['小时序号','月日时_UTC']
        for name,*_ in series:
            header += [name+'_插前资源',name+'_插后资源',name+'_插前出力pu',name+'_插后出力pu']
        writer=csv.writer(f); writer.writerow(header)
        for i in range(8760):
            row=[i+1,labels[i]]
            for _,b,a,p0,p1 in series:
                row += [b[i],a[i],p0[i],p1[i]]
            writer.writerow(row)
    with (OUT/'九条曲线_最大利用小时.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=summary[0].keys())
        writer.writeheader();writer.writerows(summary)
    (OUT/'参数与计算结果.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    for r in summary:
        print(r['曲线'],f"{r['插入前最大利用小时_h']:.1f}",f"{r['插入后最大利用小时_h']:.1f}")


if __name__=='__main__':
    main()
