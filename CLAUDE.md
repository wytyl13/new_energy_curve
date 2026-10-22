# 区域电力系统优化 · 开发指南

> 修改规则见 skill `doc-roles`：文档分工/环境约定段非用户明示不可改；
> 项目事实与当前进度段随项目状态更新。

## 文档分工

- 通用项目规则在 `.claude/skills/`（19 条），改任何文件前先读相关规则
- `DESIGN.md`：本项目唯一设计与规划文件（设计/规划/进度/决策）
- `NEW_ENERFGY_ALGO_DESIGN.md`：算法数据维度流转的固定说明（背景+流程图+流程描述），算法变更时同步
- `README.md`：稳定的项目说明，收口时按 `readme-structure` 定稿

## 环境约定

- Python 用 conda 环境

## 黄金规则
- 权威顺序：理论文档 > MATLAB 源码 > 一切推断。三者冲突时上报裁决，禁止自行拍板。
- 改源码前必须征得同意：先说清改哪几行、为什么，批准后动手；方案有变同样先确认。
- 原代码注释保留、新代码写在下方，禁止静默覆盖他人源码。
- 缺失数据不造：输入表缺列缺值即报告，不补 0、不脑补。
- 每次求解后核对四项：变量规模、约束规模、求解状态、目标函数值，进日志再谈结论。
- 带着目的回答问题，不要跑题。

## 项目事实与当前进度

- 算法逻辑的权威来源是 `海南风光_仅需hainan目录_一键全流程包/`（原始包，零改动）；`refactor/` 已于 2026-10-22 删除（被 new_energy 取代）。
- 运行环境：conda 环境 `power_curve`（python 3.12 + numpy 2.5.4 + netCDF4 + matplotlib + fastapi + uvicorn + httpx + zarr + fsspec + aiohttp，末三者读 ARCO-ERA5 公开桶生成全国海陆掩码）；回归比对基准与回归必须同环境（numpy 归约末位对版本敏感，见 DESIGN.md 决策记录）。
- 2026-10-22：重构完成并通过回归（44 逐位 + 1 路径归一，0 不一致）；服务 6 端点实现并测试通过（15 项，含端到端任务）；README 已按 readme-structure 定稿（均属已删除的 refactor/ 子项目，留痕见 DESIGN.md）。
- 2026-10-22：`new_energy/` 核心算法包 + 根目录 `api/` `core/` 服务层上线：区域CSV输入、年份数不固定、全国掩码查表、风/光×场景解耦传参、结果分文件存储；纯同步单接口 `POST /api/curve/compute`（+ health），支持 `data_dir`/`output_dir` 传参，响应 data 为表格结构 `{表名: [sheet]}`（表名=曲线-场景-资源/出力，api-json-format），文件写 outputs/ 留档，tests/test_service.py 12/12 含端到端；全国掩码由 `make_national_mask.py` 从 ARCO-ERA5 lsm 生成于 `data/`；README 已按 readme-structure 同步为 new_energy 现状。进度详情见 DESIGN.md「实施规划与进度」。
