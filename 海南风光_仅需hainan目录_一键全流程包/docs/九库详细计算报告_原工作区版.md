# 风光资源年分类、K-medoids代表曲线与极端插入：完整可运行程序

> 本文件对应一次新的完整计算：从1950—2025年76条逐年8760小时资源曲线重新分类、选代表年、计算本库阈值与年/月目标，再执行风电和光伏各自的插入程序。下表及CSV是程序在当前输入缓存上的实际运行结果，不沿用旧版插后曲线。

## 1. 输入、空间平均与统一时间轴

- 风电输入为100 m风速缓存。原始80格先逐格由 `v=√(u100²+v100²)` 得到风速，再将31个海域格、49个陆地格分别**等权平均**，每区每年形成一条8760小时风速曲线。海陆独立分库、独立选年、独立求阈值与目标。
- 光伏输入为80格等权平均的逐小时地表辐照度 `G`（W/m²）。原始SSRD若为一小时累计J/m²，先除以3600。
- 所有闰年删除2月29日，小时按UTC顺序排列。输入缓存已完成网格平均和8760小时对齐；本程序从这些真实年度序列开始，不读取旧版分类名单或旧版插入结果。光伏缓存中极少数约10⁻³ W/m²的负数值噪声在加载时置零。
- 程序输入：`outputs/海南海陆全网格等权方案/海陆两类_76年8760小时风速.npz`，键为 `1950_sea`、`1950_land` 等；`outputs/海南年聚类与月聚类公平对照/光伏76年资源缓存.npz`，键为 `1950` 等。各有76年。

## 2. 先分三类，再为每类确定一条代表曲线

风、光分别排序，海风与陆风也分别排序。风年资源指标为区域平均风速的 `mean(v³)`（与 `Σv³` 排序完全相同）；光年资源指标为 `ΣG/1000`，单位kWh/m²。指标升序，第1—19名为小资源年、第20—57名为平均资源年、第58—76名为大资源年；指标并列时按年份升序。分类不设额外摆动阈值。

每库将每个真实年表示为8760维向量。对候选年份 `i` 计算 `C_i=Σ_j ||x_i−x_j||₂`，取 `C_i` 最小且年份最早者为 `k=1` 的K-medoids中心。**“聚合成一条”是从本库真实完整年份中选出中心年，不是把库内年份逐小时取平均。**中心年原有极端状态先保留，插入后成为可追溯的重组情景曲线。

本次程序重新得到的各库年份如下（每个分区独立）：

- **海风大资源年（19年）**：2016、1953、1990、1978、1954、1974、1955、1983、1988、2020、1996、2011、1989、1970、2005、2025、1964、1971、1973。
- **海风平均资源年（38年）**：1994、1976、1986、1977、1961、2001、2000、2003、2006、1972、1956、1969、2022、1960、2021、1950、1991、1987、1998、2008、2010、1993、1952、2007、2017、1967、1985、1980、1951、1981、1962、2024、1992、1958、1995、2013、1975、1999。
- **海风小资源年（19年）**：2004、1997、1968、1982、1965、2019、1957、2018、2012、2014、1966、1979、1984、2002、1963、1959、2015、2023、2009。
- **陆风大资源年（19年）**：1988、1974、2016、2013、1978、1992、2020、1983、1990、1955、1970、1954、2025、2005、1996、1971、1989、1964、1973。
- **陆风平均资源年（38年）**：1976、2015、1977、2009、2008、2006、1961、1994、2017、2000、1972、1993、1967、2003、1963、1950、2021、2007、1999、1956、1975、1987、1960、1998、1981、1969、1962、2010、1985、1991、1980、1952、2024、1953、1995、1951、1958、2011。
- **陆风小资源年（19年）**：2004、1997、2018、2014、1968、2012、1984、2019、1959、1965、1982、1966、2023、2001、2022、1986、1979、1957、2002。
- **光伏大资源年（19年）**：1986、2021、2015、1979、2004、1959、1993、2003、1958、2019、1977、1991、1987、1950、1963、1952、1956、1955、1954。
- **光伏平均资源年（38年）**：1970、2002、1981、1994、2013、1997、1967、2000、2023、2009、1999、2010、1982、1983、2024、1995、1990、1964、1960、1992、2005、1996、2007、2020、1968、1989、1998、2006、1961、2014、1953、1980、1966、1969、1951、1957、1965、1962。
- **光伏小资源年（19年）**：1972、2011、1978、1985、2017、1975、2012、2016、1973、2022、2008、2018、1974、1971、2025、1988、1976、1984、2001。

## 3. 风电程序：P10与P90分别按完整片段插入

1. **本库阈值与目标。**由库内所有年份的全部小时风速求P10、P90。每月分别识别“每小时≤P10”或“每小时≥P90”且连续至少3小时的极大完整片段。年目标和12个月目标分别取库内逐年合格小时数的算术平均，再按 `.5` 进位取整。跨月过程在月界切开，只有月内连续仍≥3小时的部分才计入该月目标与候选。
2. **候选来源。**只取本库同月的完整历史片段，记录来源年、起点、长度和片段平均风速。按均速升序，同值按来源年和起点排序。P10从较小侧中位片段起向更小均速方向，P90从较大侧中位片段起向更大均速方向；同一候选每个尾部只用一次。
3. **月缺口和批次。**每批后重算当前曲线的年/月合格小时。按月正缺口 `m=月目标−当前合格小时` 从大到小处理，同缺口先处理月份早者。`m<3` 冻结；`m>6` 的本批额度为 `ceil(m/2)`；`3≤m≤6` 的额度为3小时。额度不能超过全年剩余目标。每批须达到额度才提交；完整片段使本批累计超额度0—2小时可接受，但不得超过全年目标。
4. **合法空间。**候选必须完整落在目标月的连续小时窗口内。目标位置从月初依次找；不覆盖当前曲线任何P10/P90越阈小时，候选前后各3小时必须满足 `P10 < v < P90`。这一限制同时保护原有片段和前批新增片段，也避开原先仅1—2小时的短暂越阈点。同一日历日最多接纳一条新增片段；跨日片段占用其触及的全部日期。
5. **完整优先与最后截断。**先尝试各候选完整曲线并寻找合法窗口；只有所有完整方案都不能完成本批时，才允许将一条历史完整片段**从起点截取**作为最后一段。截后必须仍≥3小时，前后隔离和全年目标也必须成立。批次无法完成则回滚，尝试其他月；无可行月、候选耗尽或全年剩余<3小时即停止，并保留真实欠缺。
6. **复核。**每次提交后重新识别两侧极端、重算缺口。程序最后核验原有极端小时逐值未动；每条新段与历史来源一致；新段不重叠、不同日；每段前后各3小时为正常风速；其余小时未改。P10和P90使用同一条逐步更新的代表曲线，先处理P10再处理P90。

## 4. 光伏程序：P10低光日按日历频次插入完整24小时

1. 在本库所有年份的日均辐照度上求P10。一天的24小时均值≤P10即为低光日；用全天总量判断完全等价，其阈值为 `24×P10/1000` kWh/m²。全年和逐月目标取库内逐年低光日数的平均值后 `.5` 进位取整。
2. 从可插日期池**先删除代表年原本已经是低光日的日期**；这些日期的24小时逐时值绝对不变。对其余每个日历日期，统计在本库年份中成为低光日的次数。
3. 每批按当前月缺口天数降序选月，同缺口先较早月份；额度为 `ceil(月缺口/2)`，不得超过全年剩余天数。同月按历史低光频次降序选日期，同频选较早日历日期。
4. 对选中日期，仅收集历史库中**同月同日且属于低光日**的24小时候选曲线，按全天24小时总辐照量升序排列。奇数个取正中一天的真实24小时曲线；偶数个取中间两天逐小时平均曲线。这里没有对所有候选逐小时求中位数。
5. 将模板替换到代表年的同月同日，一次替换完整24小时；本批后重算月缺口和全年低光天数。全年目标已达、无可行月或候选耗尽时结束。程序验证原有低光日和所有未选日期逐小时不变。

## 5. 本次运行结果

| 类别 | 代表年 | P10插前→插后/目标 | P90插前→插后/目标 | 插入记录数 |
| --- | ---: | ---: | ---: | ---: |
| [海风大资源年](wind_sea_high/summary.json) | 1988 | 723→842/842 h | 807→855/855 h | 20 |
| [海风平均资源年](wind_sea_mid/summary.json) | 1998 | 636→837/837 h | 705→854/854 h | 53 |
| [海风小资源年](wind_sea_low/summary.json) | 1984 | 647→833/835 h | 798→852/852 h | 32 |
| [陆风大资源年](wind_land_high/summary.json) | 1988 | 650→813/813 h | 756→843/843 h | 30 |
| [陆风平均资源年](wind_land_mid/summary.json) | 1993 | 702→810/811 h | 803→841/841 h | 24 |
| [陆风小资源年](wind_land_low/summary.json) | 1959 | 596→813/813 h | 884→884/842 h | 33 |
| [大光资源年](solar_high/summary.json) | 2019 | 24→37/37 天 | — | 13 |
| [平均光资源年](solar_mid/summary.json) | 2006 | 27→37/37 天 | — | 10 |
| [小光资源年](solar_low/summary.json) | 1985 | 25→37/37 天 | — | 12 |

陆风小资源年的P90插前已为884小时，高于本库目标842小时；程序没有删除或改动原有大风小时。海风小资源年P10最终差2小时、陆风平均资源年P10差1小时；剩余不足3小时，按合格片段最短时长停止。**月目标用于排序与分批，全年目标控制最终停止**；独立取整和保护原有极端会使个别月不能逐月恰好达标。

本结果按本文件程序的新增“三小时正常间隔、每天至多一段、3—6小时额度取3”规则重新计算，不能与之前没有这些限制的插入日志混用。

## 6. 运行与输出

在本工作区执行：

```powershell
python work/complete_wind_solar_pipeline.py --out outputs/风光完整分类聚类插入程序结果
```

只核算一个库时，例如：`python work/complete_wind_solar_pipeline.py --only wind:sea:high` 或 `--only solar:high`。`--wind`、`--solar` 可指定其他格式相同的NPZ。需Python与NumPy。

`classifications_and_results.json` 记录全部三类年份和代表年；每个库的子目录含 `summary.json`（阈值与目标）、`candidates.csv`（历史候选）、`insertion_log.csv`（每步来源、目标、额度）、`curve_8760.csv`（插前/插后逐小时资源与修改标记）。风电资源单位m/s，光伏资源单位W/m²。

## 7. 完整源程序

以下代码与同时交付的 `.py` 文件完全相同，可直接复制为 `complete_wind_solar_pipeline.py` 运行。

```python
"""海南风光资源年分类、k=1 K-medoids 与极端片段/低光日插入。

输入为已按网格等权平均、剔除2月29日的1950—2025年8760小时NPZ缓存。
风：{年份}_sea、{年份}_land；光：{年份}。仅依赖NumPy。
"""
from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

ROOT = next((p for p in Path(__file__).resolve().parents
             if (p/'outputs/海南海陆全网格等权方案/海陆两类_76年8760小时风速.npz').exists()),
            None)
if ROOT is None:
    raise FileNotFoundError('未找到包含76年资源缓存的工作区根目录')
YEARS = list(range(1950, 2026))
STAMP = [datetime(2001, 1, 1) + timedelta(hours=i) for i in range(8760)]
MONTH = np.array([t.month for t in STAMP], dtype=np.int16)
DAY = np.arange(8760) // 24
DAY_MONTH = MONTH[::24]
MONTH_BOUNDS = {m: (int(np.flatnonzero(MONTH == m)[0]),
                    int(np.flatnonzero(MONTH == m)[-1]) + 1)
                for m in range(1, 13)}
DAY_LABELS = [t.strftime('%m-%d') for t in STAMP[::24]]
STAMP_INDEX = {t.strftime('%m-%d %H:%M'): i for i, t in enumerate(STAMP)}


def half_up(x: float) -> int:
    return int(np.floor(float(x) + 0.5))


def runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """返回布尔序列的极大连续真值区间，右端点不包含。"""
    edges = np.diff(np.r_[False, np.asarray(mask, bool), False].astype(np.int8))
    return list(zip(np.flatnonzero(edges == 1).tolist(),
                    np.flatnonzero(edges == -1).tolist()))


def save_csv(path: Path, columns: list[str], records: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(records)


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def load_cache(path: Path, suffix: str = '') -> dict[int, np.ndarray]:
    with np.load(path) as source:
        expected = {f'{y}{suffix}' for y in YEARS}
        missing = expected - set(source.files)
        if missing:
            raise ValueError(f'{path} 缺少年份键：{sorted(missing)[:5]}')
        data = {y: np.asarray(source[f'{y}{suffix}'], dtype=float).copy()
                for y in YEARS}
    for y, a in data.items():
        if a.shape != (8760,) or not np.isfinite(a).all():
            raise ValueError(f'{path} 的{y}年须为有限的8760小时数组')
        if suffix == '' and a.min() >= -0.01:
            # SSRD缓存偶有约10^-3 W/m²的数值负噪声，物理上按0处理。
            data[y] = np.maximum(a, 0.0)
        elif (a < 0).any():
            raise ValueError(f'{path} 的{y}年含显著负值')
    return data


def classify_years(data: dict[int, np.ndarray], kind: str):
    """76年资源指标排序：低19年、中38年、高19年。并列按年份升序。"""
    if sorted(data) != YEARS:
        raise ValueError('分类要求1950—2025共76个完整年份')
    index = {y: float(np.mean(a**3)) if kind == 'wind'
             else float(np.sum(a) / 1000.0)
             for y, a in data.items()}
    order = sorted(YEARS, key=lambda y: (index[y], y))
    return {'小': order[:19], '平均': order[19:57], '大': order[57:]}, index


def medoid(X: np.ndarray, years: list[int]):
    """k=1 K-medoids：选本库真实年8760维欧氏距离和最小者。"""
    costs = []
    for a in X:
        costs.append(float(np.linalg.norm(X - a, axis=1).sum()))
    best = min(range(len(years)), key=lambda i: (costs[i], years[i]))
    return best, costs


def qualified_wind(a: np.ndarray, q: float, high: bool):
    """逐月识别每小时越阈且连续≥3小时的完整过程。"""
    out = np.zeros(8760, dtype=bool)
    events = []
    threshold = a >= q if high else a <= q
    for m, (lo, hi) in MONTH_BOUNDS.items():
        for s0, e0 in runs(threshold[lo:hi]):
            if e0 - s0 >= 3:
                s, e = lo + s0, lo + e0
                out[s:e] = True
                events.append((m, s, e))
    return out, events


@dataclass(frozen=True)
class WindCandidate:
    cid: int
    year: int
    month: int
    source_start: int
    values: np.ndarray
    mean: float

    @property
    def length(self):
        return len(self.values)


def wind_candidates(X: np.ndarray, years: list[int], q: float, high: bool):
    pool = []
    for i, year in enumerate(years):
        _, events = qualified_wind(X[i], q, high)
        for month, s, e in events:
            pool.append(WindCandidate(len(pool), year, month, s,
                                      X[i, s:e].copy(), float(X[i, s:e].mean())))
    return pool


def ordered_candidates(pool: list[WindCandidate], month: int, high: bool):
    ids = [i for i, c in enumerate(pool) if c.month == month]
    ids.sort(key=lambda i: (pool[i].mean, pool[i].year, pool[i].source_start))
    if high:
        return ids[len(ids)//2:]  # 偶数从较大一侧中位向更大侧
    return list(reversed(ids[:(len(ids)+1)//2]))  # 较小侧中位向更小侧


def first_window(cur: np.ndarray, values: np.ndarray, month: int,
                 q10: float, q90: float, occupied_days: set[int]):
    """首个完整窗口；已有/新增越阈小时两侧各隔≥3个正常小时。"""
    length = len(values)
    lo, hi = MONTH_BOUNDS[month]
    if length < 3 or length > hi - lo:
        return None
    bad = (cur <= q10) | (cur >= q90)
    # 距任何越阈小时≤3的时点均不可作为新片段窗口。
    guarded = np.convolve(bad.astype(np.int8), np.ones(7, dtype=np.int8),
                          mode='same') > 0
    guarded[:3] = True
    guarded[-3:] = True
    free = ~guarded[lo:hi]
    if occupied_days:
        free &= ~np.isin(DAY[lo:hi], list(occupied_days))
    for s0, e0 in runs(free):
        if e0 - s0 >= length:
            return lo + s0
    return None


def try_wind_batch(after: np.ndarray, pool: list[WindCandidate], choices: list[int],
                   month: int, quota: int, annual_remaining: int,
                   q10: float, q90: float, occupied: set[int], allow_prefix: bool):
    """试探批次；不足额度不提交。完整片段优先，最后才试前缀截断。"""
    max_hours = min(quota + 2, annual_remaining)
    for anchor in range(len(choices)):
        trial = after.copy()
        days = set(occupied)
        plan = []
        acc = 0
        for cid in choices[anchor:]:
            c = pool[cid]
            remaining = quota - acc
            if remaining <= 0:
                break
            value = c.values
            shortened = False
            if acc + len(value) > max_hours:
                if not allow_prefix or remaining < 3 or len(value) < remaining:
                    continue
                value = value[:remaining].copy()
                shortened = True
            dst = first_window(trial, value, month, q10, q90, days)
            if dst is None:
                continue
            end = dst + len(value)
            trial[dst:end] = value
            days.update(range(dst//24, (end-1)//24 + 1))
            plan.append({'candidate': cid, 'dst': dst, 'length': len(value),
                         'shortened': shortened})
            acc += len(value)
            if acc >= quota:
                return trial, days, plan, acc
    return None


def insert_wind(X: np.ndarray, years: list[int], before: np.ndarray):
    q10, q90 = np.quantile(X, [0.1, 0.9]).tolist()
    after = before.copy()
    original_extreme = (before <= q10) | (before >= q90)
    occupied_days: set[int] = set()
    logs: list[dict] = []
    targets = {}
    candidate_rows = []
    for tail, q, high in [('P10', q10, False), ('P90', q90, True)]:
        used: set[int] = set()
        historical = np.array([qualified_wind(x, q, high)[0] for x in X])
        annual_target = half_up(historical.sum(axis=1).mean())
        month_target = {m: half_up(historical[:, MONTH == m].sum(axis=1).mean())
                        for m in range(1, 13)}
        pool = wind_candidates(X, years, q, high)
        for c in pool:
            candidate_rows.append({'尾部': tail, '候选ID': c.cid, '来源年': c.year,
                '来源开始': STAMP[c.source_start].strftime('%m-%d %H:%M'),
                '月份': c.month, '完整长度h': c.length, '片段均风速m/s': c.mean})
        blocked: set[int] = set()
        iterations = 0
        while iterations < 500:
            iterations += 1
            current, _ = qualified_wind(after, q, high)
            annual_remaining = annual_target - int(current.sum())
            if annual_remaining < 3:
                break
            gaps = {m: month_target[m] - int(current[MONTH == m].sum())
                    for m in range(1, 13)}
            active = sorted((m for m in range(1, 13)
                             if gaps[m] >= 3 and m not in blocked),
                            key=lambda m: (-gaps[m], m))
            if not active:
                break
            accepted = False
            for month in active:
                gap = gaps[month]
                quota = min((gap+1)//2 if gap > 6 else 3, annual_remaining)
                if quota < 3:
                    blocked.add(month)
                    continue
                choices = [i for i in ordered_candidates(pool, month, high)
                           if i not in used]
                batch = try_wind_batch(after, pool, choices, month, quota,
                                       annual_remaining, q10, q90, occupied_days,
                                       allow_prefix=False)
                if batch is None:
                    batch = try_wind_batch(after, pool, choices, month, quota,
                                           annual_remaining, q10, q90,
                                           occupied_days, allow_prefix=True)
                if batch is None:
                    blocked.add(month)
                    continue
                trial, trial_days, plan, acc = batch
                old_count = int(current.sum())
                new_count = int(qualified_wind(trial, q, high)[0].sum())
                if new_count - old_count != acc or new_count > annual_target:
                    blocked.add(month)
                    continue
                after, occupied_days = trial, trial_days
                for p in plan:
                    c = pool[p['candidate']]
                    used.add(p['candidate'])
                    logs.append({'尾部': tail, '轮次': iterations, '月份': month,
                        '批前月缺口h': gap, '批前全年缺口h': annual_remaining,
                        '本批额度h': quota, '本批累计h': acc,
                        '来源年': c.year,
                        '来源开始': STAMP[c.source_start].strftime('%m-%d %H:%M'),
                        '来源完整长度h': c.length,
                        '实际插入长度h': p['length'],
                        '末段截断': int(p['shortened']),
                        '片段均风速m/s': c.mean,
                        '目标开始': STAMP[p['dst']].strftime('%m-%d %H:%M'),
                        '目标结束': STAMP[p['dst']+p['length']-1].strftime('%m-%d %H:%M')})
                accepted = True
                break  # 每批后重算所有月缺口并重新排序
            if not accepted:
                break
        final, _ = qualified_wind(after, q, high)
        targets[tail] = {'阈值m/s': q, '全年目标h': annual_target,
                         '插前h': int(qualified_wind(before, q, high)[0].sum()),
                         '插后h': int(final.sum()),
                         '月目标h': month_target,
                         '月插前h': {m: int(qualified_wind(before, q, high)[0][MONTH == m].sum())
                                     for m in range(1, 13)},
                         '月插后h': {m: int(final[MONTH == m].sum())
                                     for m in range(1, 13)},
                         '冻结月份': sorted(blocked)}
    if not np.array_equal(before[original_extreme], after[original_extreme]):
        raise AssertionError('原有P10/P90阈值小时被改动')
    placement_mask = np.zeros(8760, dtype=bool)
    checked_days = set()
    for row in logs:
        s = STAMP_INDEX[row['目标开始']]
        length = row['实际插入长度h']
        e = s + length
        source_start = STAMP_INDEX[row['来源开始']]
        source_year = row['来源年']
        expected = X[years.index(source_year),source_start:source_start+length]
        if length < 3 or not np.array_equal(after[s:e],expected):
            raise AssertionError('插入值不是来源片段的完整曲线或合法前缀')
        if placement_mask[s:e].any():
            raise AssertionError('新增片段相互覆盖')
        placement_mask[s:e] = True
        touched = set(range(s//24,(e-1)//24+1))
        if touched & checked_days:
            raise AssertionError('同一日历日出现两条新增片段')
        checked_days.update(touched)
        buffer = np.r_[after[s-3:s],after[e:e+3]]
        if len(buffer) != 6 or not np.all((buffer > q10) & (buffer < q90)):
            raise AssertionError('新增片段两侧未保持各3个正常小时')
    if not np.array_equal(before[~placement_mask],after[~placement_mask]):
        raise AssertionError('片段目标位置以外的小时被改动')
    changed = np.flatnonzero(before != after)
    if any(i//24 not in occupied_days for i in changed):
        raise AssertionError('修改小时与插入日志不一致')
    return after, targets, logs, candidate_rows


def insert_solar(X: np.ndarray, years: list[int], before: np.ndarray):
    H = X.reshape(len(years), 365, 24)
    a = before.reshape(365, 24).copy()
    daily_mean = H.mean(axis=2)
    q10 = float(np.quantile(daily_mean, 0.1))
    historical_low = daily_mean <= q10
    original_low = a.mean(axis=1) <= q10
    annual_target = max(half_up(historical_low.sum(axis=1).mean()),
                        int(original_low.sum()))
    month_target = {m: half_up(historical_low[:, DAY_MONTH == m].sum(axis=1).mean())
                    for m in range(1, 13)}
    frequency = historical_low.sum(axis=0)
    templates = {}
    candidates = []
    for day in range(365):
        if original_low[day]:
            continue  # 先从可插日期池删去代表年原有低光日
        ids = [i for i in range(len(years)) if historical_low[i, day]]
        ids.sort(key=lambda i: (float(H[i, day].sum()), years[i]))
        if not ids:
            continue
        i0, i1 = ids[(len(ids)-1)//2], ids[len(ids)//2]
        template = (H[i0, day] + H[i1, day]) / 2.0
        if template.mean() > q10 + 1e-9:
            raise AssertionError('低光模板未满足P10阈值')
        templates[day] = template
        candidates.append({'月日': DAY_LABELS[day], '月份': int(DAY_MONTH[day]),
            '低光频次': int(frequency[day]), '库年数': len(years),
            '来源年A': years[i0], '来源年B': years[i1],
            '模板日总辐照kWh/m²': float(template.sum()/1000)})
    changed: set[int] = set()
    blocked: set[int] = set()
    logs = []
    rounds = 0
    while rounds < 365:
        rounds += 1
        current = a.mean(axis=1) <= q10
        annual_remaining = annual_target - int(current.sum())
        if annual_remaining <= 0:
            break
        gaps = {m: month_target[m] - int(current[DAY_MONTH == m].sum())
                for m in range(1, 13)}
        active = sorted((m for m in range(1, 13)
                         if gaps[m] > 0 and m not in blocked),
                        key=lambda m: (-gaps[m], m))
        if not active:
            break
        accepted = False
        for month in active:
            gap = gaps[month]
            quota = min((gap+1)//2, annual_remaining)
            eligible = [i for i in templates
                        if DAY_MONTH[i] == month and i not in changed
                        and not original_low[i]]
            eligible.sort(key=lambda i: (-int(frequency[i]), i))
            if len(eligible) < quota:
                blocked.add(month)
                continue
            for i in eligible[:quota]:
                old_total = float(a[i].sum()/1000)
                a[i] = templates[i]
                changed.add(i)
                meta = next(x for x in candidates if x['月日'] == DAY_LABELS[i])
                logs.append({'轮次': rounds, '月份': month, '批前月缺口天': gap,
                    '本批额度天': quota, '月日': DAY_LABELS[i],
                    '低光频次': int(frequency[i]),
                    '原日总辐照kWh/m²': old_total,
                    '插后日总辐照kWh/m²': float(a[i].sum()/1000),
                    '来源年A': meta['来源年A'], '来源年B': meta['来源年B']})
            accepted = True
            break  # 每批后重算缺口并重新排序
        if not accepted:
            break
    if not np.array_equal(a[original_low], before.reshape(365, 24)[original_low]):
        raise AssertionError('原有低辐照日被改动')
    if not np.array_equal(a[[i for i in range(365) if i not in changed]],
                          before.reshape(365, 24)[[i for i in range(365) if i not in changed]]):
        raise AssertionError('未选日期被改动')
    final = a.mean(axis=1) <= q10
    targets = {'P10日均阈值W/m²': q10,
        'P10日总量等价阈值kWh/m²': q10*24/1000,
        '全年目标天': annual_target,
        '插前天': int(original_low.sum()), '插后天': int(final.sum()),
        '月目标天': month_target,
        '月插前天': {m: int(original_low[DAY_MONTH == m].sum()) for m in range(1,13)},
        '月插后天': {m: int(final[DAY_MONTH == m].sum()) for m in range(1,13)},
        '冻结月份': sorted(blocked)}
    return a.ravel(), targets, logs, candidates


def export_group(folder: Path, kind: str, years: list[int], data: dict[int, np.ndarray],
                 resource_index: dict[int, float]):
    X = np.array([data[y] for y in years])
    k, costs = medoid(X, years)
    representative_year = years[k]
    before = X[k].copy()
    if kind == 'wind':
        after, targets, logs, candidates = insert_wind(X, years, before)
        log_columns = ['尾部','轮次','月份','批前月缺口h','批前全年缺口h','本批额度h',
            '本批累计h','来源年','来源开始','来源完整长度h','实际插入长度h',
            '末段截断','片段均风速m/s','目标开始','目标结束']
        cand_columns = ['尾部','候选ID','来源年','来源开始','月份','完整长度h','片段均风速m/s']
    else:
        after, targets, logs, candidates = insert_solar(X, years, before)
        log_columns = ['轮次','月份','批前月缺口天','本批额度天','月日','低光频次',
            '原日总辐照kWh/m²','插后日总辐照kWh/m²','来源年A','来源年B']
        cand_columns = ['月日','月份','低光频次','库年数','来源年A','来源年B','模板日总辐照kWh/m²']
    folder.mkdir(parents=True, exist_ok=True)
    save_json(folder/'summary.json', {'资源类型':kind, '库年份':years,
        '代表年':representative_year,
        '代表年欧氏距离和':costs[k],
        '候选真实年欧氏距离和':dict(zip(map(str, years),costs)),
        '年资源指标':{str(y):resource_index[y] for y in years},
        '目标与结果':targets,
        '插入次数':len(logs), '修改小时':int(np.count_nonzero(after != before))})
    save_csv(folder/'candidates.csv', cand_columns, candidates)
    save_csv(folder/'insertion_log.csv', log_columns, logs)
    save_csv(folder/'curve_8760.csv',
        ['小时序号','月日时_UTC','插前资源','插后资源','是否修改'],
        [{'小时序号':i+1,'月日时_UTC':STAMP[i].strftime('%m-%d %H:%M'),
          '插前资源':float(before[i]),'插后资源':float(after[i]),
          '是否修改':int(before[i] != after[i])} for i in range(8760)])
    return representative_year, targets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wind', type=Path,
        default=ROOT/'outputs/海南海陆全网格等权方案/海陆两类_76年8760小时风速.npz')
    parser.add_argument('--solar', type=Path,
        default=ROOT/'outputs/海南年聚类与月聚类公平对照/光伏76年资源缓存.npz')
    parser.add_argument('--out', type=Path, default=ROOT/'outputs/风光完整分类聚类插入程序结果')
    parser.add_argument('--only', nargs='*',
        help='仅运行指定库，例如 wind:sea:high solar:high；缺省运行9库')
    args = parser.parse_args()
    selected = set(args.only or [])
    manifest = {}
    inputs = [('wind','sea','_sea'),('wind','land','_land'),('solar','all','')]
    for kind, zone, suffix in inputs:
        if selected and not any(s.startswith(f'{kind}:{zone}:') or
                                (kind == 'solar' and s.startswith('solar:'))
                                for s in selected):
            continue
        data = load_cache(args.wind if kind == 'wind' else args.solar, suffix)
        classes, index = classify_years(data, kind)
        manifest[f'{kind}:{zone}'] = {'三类年份':classes,
            '资源指标':{str(y):index[y] for y in YEARS}, '运行结果':{}}
        for level in ('大','平均','小'):
            alias = {'大':'high','平均':'mid','小':'low'}[level]
            key = f'{kind}:{zone}:{alias}' if kind == 'wind' else f'solar:{alias}'
            if selected and key not in selected:
                continue
            folder = args.out / key.replace(':','_')
            rep, targets = export_group(folder,kind,classes[level],data,index)
            manifest[f'{kind}:{zone}']['运行结果'][level] = {
                '代表年':rep,'目标与结果':targets,'目录':str(folder)}
            print(f'{key}: 代表年{rep}, 输出 {folder}', flush=True)
    save_json(args.out/'classifications_and_results.json', manifest)
    print('完成：', args.out, flush=True)


if __name__ == '__main__':
    main()
```
