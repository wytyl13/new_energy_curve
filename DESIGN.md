# 海南风光出力曲线流水线重构

> 本项目唯一设计与规划文件。当前阶段：先表述现有流水线（重构对象），经确认后再出重构设计。

## 子项目：海南风光九条出力曲线流水线（现有系统表述）

> 76年海南NC气象数据 → 海风/陆风/光伏 × 大/平均/小资源年，共9条8760小时出力标幺曲线。

### 基本情况

从海南76年（1950—2025）逐小时再分析NC生成9条8760小时出力曲线：按年资源多少把76年分成小/平均/大三类，每类选一个真实代表年，把历史极端片段插入代表年，再用功率曲线换算为出力标幺。产出供电力系统优化模型用的新能源出力输入。代码在 `海南风光_仅需hainan目录_一键全流程包/`，约870行，入口 `main.py` 串联 `scripts/00`—`05` 六步。

### 输入数据

| 数据 | 维度/规模 | 路径 |
|---|---|---|
| 风NC，76个年文件 | u100、v100 (8760,8,10)/年，m/s | hainan/wind/1950.nc … 2025.nc |
| 光NC，76个年文件 | ssrd (8760,8,10)/年，逐小时累计 J/m² | hainan/solar/ssrd/1950.nc … 2025.nc |
| 80格海陆分类表 | 80行：格ID、行号列号、中心经纬度、海/陆（31海/49陆） | 包内 data/80网格海陆分类.csv |
| 海南省边界 | 1个多边形 | 包内 data/海南省边界_来源geoBoundaries_simplified.geojson |

网格 8×10=80 格；时间轴UTC，删闰年2月29日，每年8760小时须完整无重复。

### 数据流转步骤

> 自上而下框图（格式仿 algorithm_design_base.pptx）：每框一个操作，框间标注处理后的数据与维度；步骤2 的两个插入循环结构图附后。

```text
【输入层】
风NC 76个年文件：u100、v100 (8760,8,10) m/s        hainan/wind/*.nc
光NC 76个年文件：ssrd (8760,8,10) J/m²·h           hainan/solar/ssrd/*.nc
80格海陆分类表：80行，31海/49陆                     包内 data/80网格海陆分类.csv
        │
        ▼ 00_check_grid_mask（模块级）
边界多边形逐格包含判定 ↔ 分类表 → 网格海陆核对.json（80格判定）
        │
        ▼ 01_nc_to_cache.load_one_resource（check_grid 核NC经纬度；分块≤8784h）
风：hypot(u100,v100) → 逐时风速 (8760,80)
    海31格等权均值 / 陆49格等权均值 → (8760,2)
光：80格等权均值 ÷3600 → (8760,) W/m²
逐年删2月29日、验证完整无重复 → 每年 (8760,) ×76年
        │
        ▼ 01_nc_to_cache.main（存NPZ缓存）
风速NPZ 152键 {年}_sea/{年}_land 各(8760,)：海风(76,8760)、陆风(76,8760)
光伏NPZ 76键 {年} 各(8760,)：(76,8760)
        │
        ▼ 02_classify_cluster_insert.load_cache（光负噪声≥−0.01 W/m² 截为0）
dict{年:(8760,)} → 堆叠 (76,8760)（风按海/陆、光各一条支路）
        │
        ▼ 02_classify_cluster_insert.classify_years
年指标：风 mean(v³)、光 ΣG/1000 → 76个数 → 升序分组：小19 / 平均38 / 大19
        │
        ▼ 02_classify_cluster_insert.export_group（海风、陆风、光伏 × 小/平均/大，9库同构并行）
库内堆叠 X (N,8760)，N=19或38
        │
        ▼ 02_classify_cluster_insert.medoid
库内两两欧氏距离和 (N,) → 最小者为真实代表年 → before (8760,)
        │
        ▼ 02.insert_wind（风库） / 02.insert_solar（光库）
风：q10、q90（标量）→ 候选池（越阈且连续≥3h片段）→ 逐月批次插入 → after (8760,)
光：reshape (N,365,24) → 日均 (N,365) → 低光模板 (24,) → 整日替换 → after (8760,)
（两个插入循环的结构图见下）
        │
        ▼ 02.export_group（写库）
9 × curve_8760.csv (8760,)，各配 summary.json、candidates.csv、insertion_log.csv
        │
        ▼ 03_power_curves.main（9条支路在此合并）
wind_power：海风4/11/25 m/s α=0.70、陆风2.5/9/18 α=0.95；光伏 p=0.6·G/1000
资源 (8760,) → 出力pu (8760,)，插前/插后 ×9
九条出力总表 (8760, 2+9×4)；最大利用小时 H=Σpₜ (9,)
        │
        ▼ 04_verify_outputs（模块级）
复核结果.json：NPZ键/维度、9库四件套、8760行、原极端保护、求和一致
        │
        ▼ 05_plot_results（模块级）
九条插后出力曲线 PNG（3×3子图）
```

风插入 `insert_wind(X, years, before)` 的循环结构：

```text
循环外（一次）：算P10/P90 → 候选池（qualified_wind）→ 全年/月目标
  （目标=库内逐年越阈小时均值，half_up）→ 记录原越阈小时
for 尾部 in (P10, P90)：            # 先P10后P90，共用同一条更新中的曲线
  while 全年剩余≥3 且 有活跃月：
    重算当前越阈小时 → 全年剩余、12个月缺口
    选缺口最大月（同缺口先早月）
    额度 = 缺口>6 ? ceil(缺口/2) : 3，且 ≤ 全年剩余
    try_wind_batch()：完整片段优先；完整均不可行才允许历史片段前缀截断
      （截后≥3h）；每段两侧各隔3个正常小时，同日至多1条新增；
      达不到额度则整批不提交
    批次成立 → 提交（更新曲线/占用日/日志）；不成立 → 冻结该月
  终止后自检：原越阈小时不变、片段不互相覆盖、目标位之外小时不变
```

光插入 `insert_solar(X, years, before)` 的循环结构：

```text
循环外（一次）：低光判定（日均≤P10）→ 月目标天=库内年均值；全年目标天=库内
  年均值且 ≥ 代表年原有低光天数 → 每个可插日的模板（同月同日历史低光日按
  日总量排序，奇数个取中间1天、偶数个取中间2天逐时平均；代表年原有低光日剔除）
while 全年剩余>0 且 有活跃月：
  重算低光日 → 月缺口，选缺口最大月，额度 = ceil(缺口/2)
  该月按历史低光频次选日，整日24h替换为模板
  额度不足或无候选 → 冻结该月
终止后自检：原有低光日、未选日期均未被改动
```

### 输出

| 数据 | 维度 | 路径（包内 outputs/ 下） |
|---|---|---|
| 风速缓存 | 152×(8760,) | 海南海陆全网格等权方案/海陆两类_76年8760小时风速.npz |
| 光伏缓存 | 76×(8760,) | 海南年聚类与月聚类公平对照/光伏76年资源缓存.npz |
| 9库四件套 | 每库 curve_8760.csv 8760行 + summary.json + candidates.csv + insertion_log.csv | 风光完整分类聚类插入程序结果/wind_sea_high … solar_low/ |
| 九条出力总表 | 8760行 ×（2+9×4）列 | 九条出力曲线_原参数/九条8760小时_插前插后资源与出力.csv |
| 最大利用小时 | 9行 | 九条出力曲线_原参数/九条曲线_最大利用小时.csv |
| 复核结果 | JSON | 复核结果.json |
| 曲线图 | PNG | 九条出力曲线_原参数/九条插后8760小时出力曲线.png |

## 子项目：重构版流水线与服务（重构设计）

> 2026-10-22 定稿。重构模式：最优移植（algo-porting 默认），行为一致、结构按目标语言惯用分层重写；原始包零改动留作参照。

### 目录结构

```text
refactor/
  curve_pipeline/          核心算法包（唯一入口 run_pipeline，不 import 服务层）
    axis.py                8760小时时间轴常量与 runs/half_up
    grid_mask.py           步骤0 海陆核验
    nc_cache.py            步骤1 NC→NPZ缓存
    classify_cluster.py    步骤2 分类+medoid+库导出（编排风/光插入）
    wind_insert.py         步骤2 风P10/P90插入
    solar_insert.py        步骤2 光低光日插入
    power_curves.py        步骤3 出力换算
    verify_outputs.py      步骤4 复核
    plot_results.py        步骤5 画图
    pipeline.py            步骤编排 + run_pipeline(request) 唯一入口
  curve_service/           FastAPI 服务层（service-api 目录结构）
    api/server/app_server.py   app 装配四件 + 全局异常
    api/routers/curve_router.py  薄路由
    api/schema/curve_schema.py   请求体模型
    api/dependencies.py     依赖工厂（JobManager 单例）
    api/response.py         make_response
    core/manager/job_manager.py  后台任务登记与状态
  tests/                   接口测试 + 回归比对脚本
baseline_run/              原始包副本，基准输出所在
regression_out/            重构版回归输出
```

### 重构步骤细节（动哪些文件、怎么动、回归判据）

- 只新增 `refactor/` 下文件，原始包与 hainan 数据零改动。
- 各函数逻辑逐个从原脚本平移（含原注释），仅做：文件头/docstring/类型注解补齐（code-header、code-function）；02 的 482 行拆为 axis/classify_cluster/wind_insert/solar_insert 四个模块；模块级脚本（00/04/05）包成函数。
- 冻结口径：输出文件列集、行序、精度、键名、遍历顺序全部不变；输出目录树与原版一致（algo-porting §5）。
- 回归判据（事先声明）：**逐位一致**——基准与回归输出的全部文件 md5 相同；排除两类非算法产物：`运行来源与程序版本.json`（含 UTC 时间戳与代码哈希）、`九条…png`（若同环境渲染字节不一致，改按像素一致并留痕）。
- 基准来源：`refactor/baseline_run`（原始代码全量重跑），先建 md5 快照再动代码。

### 服务设计（端点集，返回经 make_response 包装）

| 端点 | 方法 | 传参 | 返回 |
|---|---|---|---|
| /api/health | GET | 无 | {status, message, timestamp} |
| /api/curve/jobs | POST | {hainan_dir} | {job_id}，后台跑全流程 |
| /api/curve/jobs/status | POST | {job_id} | {status, progress, detailed_status, error_message} |
| /api/curve/libraries | GET | 无 | 9库：代表年、插前/插后利用小时等 |
| /api/curve/results/curve | POST | {library} | 曲线 {sheet_name, index, data:[{column_name,data}]} |
| /api/curve/results/summary | GET | 无 | 最大利用小时表 + 复核结果 |

结果读取目录：环境变量 `CURVE_OUTPUTS_ROOT`，缺省 `refactor/regression_out`。

## 子项目：new_energy 解耦核心算法（区域CSV输入 + 服务端全国掩码）

> 2026-10-22 用户定方案并实现。前端传预处理后的区域 CSV（风速已合成/辐照已÷3600），
> 年份数不固定；全国海陆掩码为服务端静态文件；资源类型（风/光）与场景（正常/大/小/全部）
> 解耦传参，传什么算什么；结果按 曲线-场景-资源/出力 分文件存储。原始包保留不动；
> refactor/ 已于 2026-10-22 删除（被 new_energy 取代，其回归留痕见本文件历史记录）。

### 结构与输入契约

- `new_energy/` 核心算法包，模块直接放平：`axis`（8760时间轴）、`load_csv`（区域CSV读取）、
  `mask_lookup`（全国掩码查表+海/陆/全格等权平均）、`classify`（分档）、`medoid`（选代表年）、
  `wind_insert` / `solar_insert`（极端修正，自 refactor 逐字平移含自检断言）、`power`（出力映射）、
  `pipeline`（`run()` 唯一入口，含可选 `progress(0~1小数, 说明)` 回调）。
  服务层在项目根：`api/`（server 装配 / routers / schema / response）、
  `core/compute`（同步计算编排）、`start_server.py` 启动脚本。
- 输入：`data_dir` 每年一个 CSV，列名 `<变量名>_lat_<纬度>_lon_<经度>` 一格点一列，
  格点可为散布子集（不验行政区、不强求矩形）；闰年删 2/29 规整 8760；各年格点列须一致。
- 分档泛化：小/大各 `N//4`、平均居中（N=76 时恰为冻结版 19/38/19）；N<4 报错。
- 掩码：缺省 `data/全国网格海陆分类.csv`（ARCO-ERA5 lsm 口径），行列整数算术换算查表；
  风一次算出海风+陆风两族，光全格平均（负噪声≥−0.01 W/m² 截 0，同冻结版）。
- 输出：`<曲线>-<场景>-资源.csv` / `<曲线>-<场景>-出力.csv`（曲线∈海风/陆风/光伏，
  场景∈大/正常/小），三列 `时间维度, 插入前*, 插入后*`，8760 行；`run()` 返回
  `{表名: [sheet]}`：表名 = 曲线-场景-资源/出力（与结果文件同名），每键一个 sheet 的
  list（留多 sheet 扩展），sheet = {sheet_name, index, data:[插入前/插入后两列]}
  （api-json-format；2026-10-22 用户定稿口径）。
- 场景映射：normal=正常（=平均档）/ high=大 / low=小 / all=全部。

### 服务端点（统一响应 {success, message, data, timestamp}；400 参数错；纯同步无任务态）

| 端点 | 方法 | 传参 | 返回 |
|---|---|---|---|
| /api/health | GET | 无 | {status, message, timestamp} |
| /api/curve/compute | POST | {resource, scenario, data_dir, output_dir?} | 阻塞至算完：data = {表名: [sheet]}（表名=曲线-场景-资源/出力，sheet 含 index 8760 + 插入前/后两列）；文件写 output_dir（自动创建）或缺省 outputs/<时间戳_短随机>/ |

结果根目录：环境变量 `CURVE_OUTPUTS_ROOT`，缺省项目根 `outputs/`；每次计算独立子目录
（`时间戳_短随机`）。

### 冒烟结果（data/wind，2000—2025 共 26 年、51 格点，2026-10-22）

| 曲线-场景 | 代表年 | 修改小时 | 利用小时 插前→插后 |
|---|---|---|---|
| 海风-大 | 2020 | 3 | 1206.3 → 1206.1 |
| 海风-正常 | 2008 | 253 | 1014.8 → 1043.0 |
| 海风-小 | 2004 | 140 | 823.8 → 865.2 |
| 陆风-大 | 2020 | 0 | 1585.4 → 1585.4 |
| 陆风-正常 | 2008 | 204 | 1318.1 → 1331.5 |
| 陆风-小 | 2004 | 148 | 1022.8 → 1072.7 |

大档插入量趋零是算法语义而非缺陷：插入只补代表年相对库均值的越阈缺口，
medoid 年本就贴库均值，小库（26//4=6 年）缺口更小。

### 进度

| 步骤 | 状态 | 验证结果 |
|---|---|---|
| 核心算法 new_energy 9 模块 | 完成 | 冒烟：风全场景 6 曲线 12 文件（8761 行、列头正确）、单场景只出对应文件、非法场景报错 |
| api/ + core/ 服务层（纯同步） | 完成 | tests/test_service.py **12/12 通过**（health、参数/目录 400、wind normal 端到端：data 为 4 张表 {表名:[sheet]}、index 8760、两列、文件落盘 output_dir） |
| 光伏路径 | 已实现未测 | data/solar 数据未到位，用户决定暂不测（缺失数据不造） |
| NEW_ENERFGY_ALGO_DESIGN.md 输入契约段 | 未同步 | 待收口时更新 |

## 需求

> 已确认的需求。
- 2026-10-22 用户确认：按 skills 重构本项目；核心算法与原项目测试对比；按 skills 构建服务并测试每个接口；同步 README 并加流程图；执行过程不需逐项确认。

## 接口设计

> 现有对外接口只有CLI。
- `python main.py --hainan <目录>`：目录下需有 wind/、solar/ 文件夹（或 wind.nc、solar.nc）；依次执行步骤0—5，任何一步失败即停。

## 实施规划与进度

| 步骤 | 状态 | 验证结果 |
|---|---|---|
| 现有系统表述（§子项目） | 完成 | 2026-10-22 用户确认按此执行 |
| 重构设计（重构步骤细节） | 完成 | 见上 |
| 基准全量重跑 + md5 快照 | 完成 | 46 文件，四项核对通过（9组×8760h、复核通过、利用小时与原 README 一致） |
| 算法包重构（curve_pipeline 11 文件） | 完成 | `refactor/curve_pipeline/`，唯一入口 `run_pipeline(request, progress)` |
| 回归比对（tests/compare_outputs.py） | 完成 | **逐位一致 44 / 路径归一一致 1 / 不一致 0 / 多余 0**（详下） |
| 服务层（curve_service） | 完成 | api/server+routers+schema+dependencies、core/manager/job_manager（线程后台任务+进度回调）、core/results；6 端点全部实现 |
| 接口测试 | 完成 | tests/test_api.py：**15 项全部通过**（TestClient，含真实 hainan 端到端任务 succeeded/progress 1.0/复核通过；非法库 400、任务不存在 404、无效目录 400） |
| 真实服务冒烟 | 完成 | uvicorn 起服务：/api/health 200、/api/curve/libraries 返回真实 9 库、不存在任务 404 |
| 服务路径产出再比对 | 完成 | 端到端任务重写 regression_out 后 compare_outputs.py 复跑：逐位一致 44 / 路径归一 1 / 不一致 0 / 多余 0 |
| README 同步 | 完成 | 项目根 README.md 按 readme-structure 8 章定稿，算法全流程表+嵌入 算法流程图.png |

#### 回归比对结论（2026-10-22）

- 首次比对曾出现 15 文件末位（1~2 ULP）差异：根因是基准用 newenergy_dgzy 环境（numpy 2.2.6）、回归用 power_curve 环境（numpy 2.5.4），`np.sum/np.mean` 的 SIMD 归约末位不同；NPZ 数组本身逐位一致。**修正：基准在 power_curve 环境全量重跑**（同环境原则），44/45 文件 md5 直接逐位一致。
- 两处降级判据（均非算法产物，比对留痕）：
  - `classifications_and_results.json`：仅 9 个 `'目录'` 字段含各自输出根绝对路径（baseline_run/outputs vs regression_out），按路径归一后逐字段一致；
  - NPZ：`np.savez` 容器内嵌 zip 时间戳，md5 非确定；同环境下本次 md5 已直接一致，降级判据（键集+数组逐位）保留在比对脚本中备用。
- 排除项维持事先声明：`运行来源与程序版本.json`（UTC 时间戳与代码哈希）。

## 决策记录

- 2026-10-22 **基准与回归统一环境**：首次比对 15 文件末位差异（1~2 ULP），根因是 numpy 版本不同（2.2.6 vs 2.5.4）导致 SIMD 归约末位不同；改为基准在 power_curve 环境重跑，44/45 文件 md5 直接逐位一致。后续比对一律同环境。
- 2026-10-22 **两处降级判据留痕**：NPZ（np.savez 内嵌 zip 时间戳，md5 非确定）按键集+数组逐位；classifications_and_results.json 仅 9 个 '目录' 字段含输出根绝对路径，按路径归一后逐字段一致。均在 tests/compare_outputs.py 实现，比对输出打印 NPZ-OK/PATH-OK。
- 2026-10-22 **任务编排放服务层线程**：run_pipeline 为同步长任务，JobManager 用 daemon 线程执行 + 进度回调（步骤 0—6 映射 0~1），路由层 asyncio.to_thread 包结果读取；算法包保持纯 dict 进出、无 fastapi 依赖。
- 2026-10-22 **无效 hainan_dir 提交即 400**：JobManager.submit 先做目录与 wind/solar 存在性校验（run_pipeline 内仍会复核），避免无效任务占用后台线程后才失败。
- 2026-10-22 **new_energy 服务纯同步、单接口**（用户裁决，取代上上条的线程方案）：删除 jobs 提交/状态/结果查询三端点与 JobManager 线程/事件/进度机制，只留 `POST /api/curve/compute`（普通 def 路由，FastAPI 线程池执行）阻塞直返；曲线数据随响应内联（api-json-format），文件仍写 outputs/ 留档；core/ 缩为 compute.py 同步编排。
