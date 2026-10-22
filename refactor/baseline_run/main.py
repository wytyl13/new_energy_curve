"""One-command Hainan NC -> 76-year libraries -> nine 8760-hour output curves.

Usage: python main.py --hainan "C:/path/to/hainan"
The hainan folder needs wind and solar entries (folders or .nc files).
The package provides the fixed 80-cell mask and all processing modules.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parent
STEPS=('00_check_grid_mask.py','01_nc_to_cache.py',
       '02_classify_cluster_insert.py','03_power_curves.py',
       '04_verify_outputs.py','05_plot_results.py')


def locate(hainan:Path,stem:str)->Path:
    matches=[hainan/stem,hainan/(stem+'.nc')]
    found=[p for p in matches if p.is_dir() or (p.is_file() and p.suffix.lower()=='.nc')]
    if not found:
        raise FileNotFoundError(f'{hainan} 下需要 {stem} 文件夹或 {stem}.nc')
    src=found[0]
    files=([src] if src.is_file() else list(src.rglob('*.nc')))
    if not files:
        raise FileNotFoundError(f'{src} 下未找到.nc文件')
    return src


def sha256(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for part in iter(lambda:f.read(2**20),b''):
            h.update(part)
    return h.hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--hainan', '--hainan-dir', type=Path, required=True,
                   help='包含wind、solar文件夹或wind.nc、solar.nc的hainan目录')
    a=p.parse_args()
    hainan=a.hainan.expanduser().resolve()
    if not hainan.is_dir():
        p.error(f'hainan目录不存在：{hainan}')
    wind=locate(hainan,'wind')
    solar=locate(hainan,'solar')
    (ROOT/'outputs').mkdir(exist_ok=True)
    record={'运行时间UTC':datetime.now(timezone.utc).isoformat(),
            'hainan目录':str(hainan),'风NC来源':str(wind),'光NC来源':str(solar),
            'Python版本':sys.version.split()[0],
            '程序SHA256':{s:sha256(ROOT/'scripts'/s) for s in STEPS},
            '状态':'运行中'}
    target=ROOT/'outputs/运行来源与程序版本.json'
    target.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    for idx,step in enumerate(STEPS):
        cmd=[sys.executable,str(ROOT/'scripts'/step)]
        if idx==1:
            cmd+=['--wind-dir',str(wind),'--solar-dir',str(solar)]
        print(f'[{idx}/5] {step}',flush=True)
        try:
            subprocess.run(cmd,cwd=ROOT,check=True)
        except subprocess.CalledProcessError as exc:
            record.update({'状态':'失败','失败步骤':step,'退出码':exc.returncode})
            target.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
            raise SystemExit(exc.returncode)
    record['状态']='完成'
    target.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    print('完成：outputs/九条出力曲线_原参数/九条8760小时_插前插后资源与出力.csv',flush=True)


if __name__=='__main__':
    main()
