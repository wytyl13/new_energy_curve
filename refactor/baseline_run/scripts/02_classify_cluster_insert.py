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
