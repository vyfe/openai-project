# 多模型并行会话改造分工总览（3角色协作）

## 1. 目标
- 将“单会话单模型”升级为“主会话 + 子会话 + 回合栅格”。
- 支持多模型并行、严格对齐展示、单元级重试。
- 以模块化重构为前提推进：
  - Python 数据模型按单文件拆分。
  - 后端接口逻辑按功能域拆分到独立文件。
  - 前端状态从单数组迁移到回合矩阵结构。

## 2. 角色分工
- 角色A：数据架构升级（DB schema + Model/Repository 模块化）。
- 角色B：后端逻辑开发（V2 API + 服务层 + 流式并发与重试）。
- 角色C：前端重构（会话主子模型、回合栅格 UI、并行交互）。

## 3. 并行策略与依赖
- A 与 B 可以并行启动：
  - A 先给出最终字段与迁移脚本草案。
  - B 可先用接口 DTO 与 in-memory mock 开发，待 A schema 定稿后接入 Repository。
- C 与 B 并行：
  - C 先按接口契约开发页面与 store，使用 mock adapter。
  - B 输出 OpenAPI/JSON 样例后，C 切真实 API。

## 4. 接口契约基线（供 B/C 对齐）
- `POST /conversation/master/create`
- `POST /conversation/master/list`
- `POST /conversation/master/detail`
- `POST /conversation/master/add_model`
- `POST /conversation/master/remove_model`
- `POST /conversation/round/send`
- `POST /conversation/cell/retry`

### 4.1 通用响应结构
```json
{
  "success": true,
  "msg": "",
  "data": {}
}
```

### 4.2 关键枚举
- `session_type`: `single | multi_compare`
- `child_status`: `active | removed | failed`
- `cell_status`: `idle | streaming | success | failed | skipped`

## 5. 里程碑
- M1（A/B/C）：契约冻结（schema + API + store shape）。
- M2（A/B）：后端 V2 可用（含迁移与兼容）。
- M3（C）：前端完整接入 V2，完成栅格化与重试。
- M4（A/B/C）：联调、压测、回归与灰度。

## 6. 完成定义（DoD）
- 历史列表仅展示主会话。
- 进入主会话可一次性恢复全部子会话并严格对齐。
- 动态加模型后历史回合显示 `skipped` 占位。
- 子会话失败可单元级重试，且不影响其他模型/回合。
- 旧 `Dialog` 路径仍可读取，迁移后数据可追溯。
