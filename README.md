# 风光出力曲线计算（区域 CSV 输入）与服务

## 1. 背景

本项目把任意区域的 ERA5 风光资源历史 CSV（风为均方根后的 100m 风速，光为除以 3600 后的小时辐照度）加工为海风/陆风/光伏 × 大/正常/小场景的 8760 小时资源与出力曲线，并封装为纯同步 HTTP 计算服务。输入是每年一个的区域网格 CSV 与服务端预生成的全国海陆掩码；输出是与所传场景对应的曲线 CSV 文件，以及随响应直接返回的表格数据。年份数不固定，上传多少年使用多少年。

## 2. Quick Start

> 本章给出环境安装、算法运行、服务启动与测试的最小命令。

```bash
# 环境：conda 环境 power_curve（python 3.12 + numpy netCDF4 matplotlib fastapi uvicorn httpx zarr fsspec aiohttp）
conda activate power_curve

# 起服务
python -X utf8 start_server.py --port 9996   # 结果根目录：环境变量 CURVE_OUTPUTS_ROOT，缺省项目根 outputs/

# 直接跑算法（CLI，不走 HTTP；返回表名列表）
python -X utf8 -c "from new_energy import run; print(sorted(run('wind', 'normal', r'data/wind', r'outputs/smoke')))"

# 接口测试（含一次真实端到端计算）
python -X utf8 tests/test_service.py

# 重新生成全国海陆掩码（可选，需联网读 ARCO-ERA5 公开桶；结果已生成于 data/全国网格海陆分类.csv）
python -X utf8 make_national_mask.py
```

## 3. 架构

> 本章给出分层结构与各层职责。

```
HTTP 客户端
    │  JSON over HTTP（统一响应 {success, message, data, timestamp}）
┌───▼─────────────────────────────────────────────┐
│ api/  服务层                                     │
│   server/app_server.py   应用装配（CORS/日志/异常）│
│   routers/curve_router.py  同步计算路由           │
│   schema/curve_schema.py  请求体                  │
│   response.py  统一响应                           │
├─────────────────────────────────────────────────┤
│ core/compute.py  同步计算入口（校验/输出目录）     │
├─────────────────────────────────────────────────┤
│ new_energy/  算法层（唯一入口 run）               │
│   load_csv → mask_lookup → classify → medoid    │
│   → wind_insert / solar_insert → power          │
│   （pipeline.py 组合各步骤）                     │
├─────────────────────────────────────────────────┤
│ data/wind 区域CSV + data/全国网格海陆分类.csv     │
│   → outputs/ 曲线CSV                             │
└─────────────────────────────────────────────────┘
```

依赖单向自上而下：服务层经 `core/compute` 调算法层，算法层不感知 HTTP。

| 模块         | 职责                                 | 编写规则                     |
| ------------ | ------------------------------------ | ---------------------------- |
| api/         | 应用装配、路由、请求体、统一响应     | service-api                  |
| core/compute | 同步计算入口、参数校验、输出目录管理 | service-api、code-decoupling |
| new_energy/  | 曲线算法各步骤，纯 dict/list 进出    | algo-porting、code-function  |
| tests/       | 接口测试                             | process-verify               |

## 4. 算法全流程

> 本章是端到端数据流主线：读区域 CSV → 掩码分区平均 → 分档选代表年 → 极端修正 → 出力换算 → 写结果文件。

冻结步骤（极端修正、出力换算）的张量维度流转见 [NEW_ENERFGY_ALGO_DESIGN.md](NEW_ENERFGY_ALGO_DESIGN.md)。

| 步骤           | 输入                                                            | 中间处理                                                                            | 输出                                        | 模块                                    |
| -------------- | --------------------------------------------------------------- | ----------------------------------------------------------------------------------- | ------------------------------------------- | --------------------------------------- |
| 1 读取区域CSV  | data_dir 每年一个 CSV，列名`<变量>_lat_<纬度>_lon_<经度>` [1] | 闰年删 2/29 规整 8760；校验每年单年、时间戳完整、各年格点列一致                     | years 升序、lats/lons (G,)、cube (N,8760,G) | load_csv.py [1]                         |
| 2 海陆分区平均 | cube + data/全国网格海陆分类.csv [2][9]                         | 格点坐标整数行列算术查掩码；风：海/陆格点各自等权平均（wind_zone 可全区统一或空区跳过），光：全格平均 → 每年 (8760,) | 各区逐年序列 {年: (8760,)}      | mask_lookup.py [2]                      |
| 3 分档         | 各区逐年序列                                                    | 逐年指标排序（风 mean(v³)、光 ΣG/1000），小/大各 N//4 年、平均居中                | 三档年份组                                  | classify.py [3]                         |
| 4 选代表年     | 档内年份序列                                                    | k=1 K-medoids：库内欧氏距离和最小的真实年                                           | 代表年 (8760,)                              | medoid.py [4]                           |
| 5 极端修正     | 代表年 + 库内全部年份序列                                       | 风：P10/P90 片段插入（配额、3h 间隔、前缀截断）；光：低光日整日替换                 | 插后资源 (8760,)                            | wind_insert.py [5]、solar_insert.py [6] |
| 6 出力换算     | 插前/插后资源                                                   | 风功率曲线（海 4/11/25 m/s α=0.70，陆 2.5/9/18 α=0.95）；光 0.6·G/1000           | 归一化出力 (8760,)                          | power.py [7]                            |
| 7 输出         | 插前/插后资源与出力                                             | 写曲线 CSV；组装返回数据 {表名: [sheet]}                                            | 曲线文件 + 表格数据                         | pipeline.py [8]                         |

## 5. 分实体明细

> 本章按曲线族展开描述、约束、换算参数与输入输出。

| 曲线族 | 描述                         | 约束                                      | 换算参数                                 |
| ------ | ---------------------------- | ----------------------------------------- | ---------------------------------------- |
| 海风   | 海上格点平均风速的代表年曲线 | 按 mean(v³) 排序分档；代表年为库内真实年 | 切入 4 / 额定 11 / 切出 25 m/s，α=0.70  |
| 陆风   | 陆上格点平均风速的代表年曲线 | 同海风，按陆风指标独立排序                | 切入 2.5 / 额定 9 / 切出 18 m/s，α=0.95 |
| 光伏   | 全格平均辐照度的代表年曲线   | 按 ΣG/1000 排序分档；低光日整日替换      | 0.6·G/1000（G 为 W/m² 小时均值）       |

每族 × 场景（大/正常/小）为一个库；`resource='wind'` 缺省一次算出海风+陆风两族（纯海/纯陆区域自动只算存在的一族），`wind_zone` 可指定全区统一按海风或陆风处理；`resource='solar'` 算光伏一族。上表换算参数为冻结缺省值，可经请求 `wind_params` / `pv_params` 覆盖（逐字段说明见第 7 章）。

| 库           | 输入数据                             | 输出数据                                       |
| ------------ | ------------------------------------ | ---------------------------------------------- |
| 各库（同构） | 档内年份 (8760,) 序列（步骤 2 输出） | 该曲线-场景的资源、出力两个 CSV 与两份表格数据 |

## 6. 汇总输出

> 本章列出输出文件与产出模块。

| 文件                                  | 内容                                      | 产出模块                  |
| ------------------------------------- | ----------------------------------------- | ------------------------- |
| data/全国网格海陆分类.csv             | 36685 格点海陆判定（预生成静态掩码）      | make_national_mask.py [9] |
| outputs/<批次>/<曲线>-<场景>-资源.csv | 时间维度、插入前资源、插入后资源，8760 行 | pipeline.py [8]           |
| outputs/<批次>/<曲线>-<场景>-出力.csv | 时间维度、插入前出力、插入后出力，8760 行 | pipeline.py [8]           |

曲线 ∈ 海风/陆风/光伏；场景 ∈ 大/正常/小。批次目录：请求传 `output_dir` 时为该目录，缺省为 `outputs/<时间戳_短随机>/`。

## 7. 接口

> 本章给出 2 个 HTTP 端点的传参与返回示例。
> http://192.168.2.40:9996/

统一响应包装：`{success, message, data, timestamp}`；业务错误 400，未处理异常 500。计算为同步阻塞：请求发出后等待算完一次返回，无任务状态查询。

### GET /api/health

无传参。

```json
{"status": "ok", "message": "服务运行中", "timestamp": "2026-10-22T10:00:00Z"}
```

> status：服务状态；message：说明；timestamp：UTC 时间。

### POST /api/curve/compute —— 同步计算曲线（http://[192.168.2.40:9996](http://192.168.2.40:9996/)/）

```json
{"resource": "wind", "scenario": "normal",
 "data_dir": "C:/Users/weiyutao/20260823/new_energy_curve/data/wind",
 "output_dir": "D:/results/demo",
 "wind_params": {"sea": {"cut_in": 4, "rated": 11, "cut_out": 25, "alpha": 0.70},
                 "land": {"cut_in": 2.5, "rated": 9, "cut_out": 18, "alpha": 0.95}},
 "pv_params": {"efficiency": 0.6},
 "wind_zone": "all"}
```

> resource：必填，'wind'（一次算出海风+陆风）或 'solar'（光伏），资源类型。
> scenario：必填，'normal' 正常 / 'high' 大 / 'low' 小 / 'all' 全部，资源场景。
> data_dir：必填，输入目录绝对路径，内含每年一个区域 CSV。
> output_dir：可选，缺省 outputs/<时间戳_短随机>/，结果 CSV 写入该目录（不存在则创建）。
> wind_zone：可选，风区口径，仅 resource='wind' 生效：'sea' 全区统一按海风处理 / 'land' 全区统一按陆风处理（均不查掩码、全格平均、用对应机组参数，纯海/纯陆区域均可算）；'all'（缺省）按掩码自动分海陆，空区跳过（纯海/纯陆区域只算存在的一族）。
> wind_params：可选，风机参数，不传用冻结默认；支持只传部分字段，省略的字段落默认。
> sea：可选，海上风机组参数；land：可选，陆上风机组参数。各含 4 个字段（均可省略）：
> cut_in：切入风速，m/s，低于此风速出力为 0；默认 海 4 / 陆 2.5。
> rated：额定风速，m/s，达到此风速满发；默认 海 11 / 陆 9。
> cut_out：切出风速，m/s，达到此风速停机、出力为 0；默认 海 25 / 陆 18。
> alpha：顶格系数，满发时的标幺出力，取值 (0,1]；默认 海 0.70 / 陆 0.95。
> 校验：须满足 0 < cut_in < rated < cut_out，且各风区字段合法，否则 400。
> pv_params：可选，光伏参数，不传用冻结默认。
> efficiency：综合效率系数，出力标幺 = 效率 × 辐照 / 1000，取值 (0,1]；默认 0.6。

data_dir 内文件与表头格式：

- 文件：每年一个 `*.csv`，文件名不限（年份以 time 列为准，如 `hainnewan_wind_2000.csv`）。
- 表头：第一列固定 `time`，格式 `YYYY-MM-DD HH:MM:SS`；一年只含一个年份，删 2 月 29 日后 8760 个不重复小时。
- 其余每格点一列，列名 `<变量>_lat_<纬度>_lon_<经度>`：风 `wind_speed_100m`（均方根后的 100m 风速，m/s），光 `ssrd`（÷3600 后的辐照度，W/m²）。

```csv
time,wind_speed_100m_lat_20.0_lon_110.25,wind_speed_100m_lat_20.0_lon_110.5
2000-01-01 00:00:00,5.0948,5.8584
2000-01-01 01:00:00,5.2578,6.2660
```

各年份文件格点列须一致；格点可为散布子集，坐标须在全国掩码覆盖范围内（0.25° 网格，73—136°E、18—54°N）。

```json
{"success": true, "message": "计算完成", "timestamp": "2026-10-22T10:00:05Z",
 "data": {"海风-正常-资源": [{"sheet_name": "海风-正常-资源",
                          "index": ["01-01 00:00", "01-01 01:00"],
                          "data": [{"column_name": "插入前资源", "data": [8.31, 8.26]},
                                   {"column_name": "插入后资源", "data": [8.31, 8.26]}]}],
          "海风-正常-出力": [{"sheet_name": "海风-正常-出力", "index": ["…"], "data": ["…同构…"]}],
          "陆风-正常-资源": [{"sheet_name": "陆风-正常-资源", "index": ["…"], "data": ["…同构…"]}],
          "陆风-正常-出力": [{"sheet_name": "陆风-正常-出力", "index": ["…"], "data": ["…同构…"]}]}}
```

> data：字典，键为表名（= 曲线-场景-资源/出力，与结果 CSV 同名），传什么场景返回什么表，all 返回全部（风 12 张、光 6 张）。
> 表名值：sheet 列表（当前每表 1 个 sheet，保留多 sheet 扩展）。
> sheet_name：表名；index：8760 个"月-日 时:分"时间戳；column_name：列名（插入前/插入后 + 资源或出力）；data：8760 个数值，与 index 对齐，数值不转字符串。

## 8. Reference

> 本章为正文编号引用与代码位置的映射。

```markdown
<!-- 算法层 new_energy -->
[1]: new_energy/load_csv.py
[2]: new_energy/mask_lookup.py
[3]: new_energy/classify.py
[4]: new_energy/medoid.py
[5]: new_energy/wind_insert.py
[6]: new_energy/solar_insert.py
[7]: new_energy/power.py
[8]: new_energy/pipeline.py
<!-- 数据准备 -->
[9]: make_national_mask.py
<!-- 服务层 -->
[10]: api/server/app_server.py
[11]: api/routers/curve_router.py
[12]: api/schema/curve_schema.py
[13]: core/compute.py
<!-- 测试 -->
[14]: tests/test_service.py
```
