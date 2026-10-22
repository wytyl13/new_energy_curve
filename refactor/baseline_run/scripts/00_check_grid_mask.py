"""Audit the supplied 31-sea/49-land grid mask against the boundary GeoJSON."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
from matplotlib.path import Path as PolygonPath

ROOT=Path(__file__).resolve().parent.parent
GRID=ROOT/'data/80网格海陆分类.csv'
BOUNDARY=ROOT/'data/海南省边界_来源geoBoundaries_simplified.geojson'
with GRID.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
geo=json.loads(BOUNDARY.read_text(encoding='utf-8'))
polygon=PolygonPath(np.array(geo['features'][0]['geometry']['coordinates'][0]))
mismatches=[]
for row in rows:
    land=polygon.contains_point((float(row['中心经度_E']),float(row['中心纬度_N'])))
    expected=(row['海陆判定']=='陆地')
    if land!=expected:mismatches.append(int(row['网格ID_从0']))
result={'网格数':len(rows),'海域格':sum(r['海陆判定']=='海域' for r in rows),
        '陆地格':sum(r['海陆判定']=='陆地' for r in rows),
        '与边界判定不一致的格ID':mismatches,'通过':not mismatches}
(ROOT/'data/网格海陆核对.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
if len(rows)!=80 or result['海域格']!=31 or result['陆地格']!=49 or mismatches:
    raise SystemExit(1)
