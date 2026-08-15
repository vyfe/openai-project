# CLAUDE.md — Claude Code 工作指引

> 本仓库的项目知识库、开发约定、测试规范、文件膨胀控制等内容
> **全部统一维护在 [`AGENTS.md`](./AGENTS.md)**。
>
> 本文件仅保留给 Claude Code 的 **本仓库专属增量约定**，避免和 AGENTS.md 双份维护。

## 仓库专属增量

- 默认使用中文回复用户。
- 修改任何代码前先读 `AGENTS.md` 第 0～2 节，确认项目结构与本文件无冲突后再动手。
- 修改前端样式 / 渲染前先读 `AGENTS.md` 第 4.4～4.5 节。
- 修改后端配置 / 启动脚本前先读 `AGENTS.md` 第 5～6 节。
- 量化子系统改动必须同时核对 `doc/quant/` 下专题文档。

## 本地配置

Claude Code 的本地权限/工具配置放在 [`./.claude/`](./.claude/)（已被 `.gitignore` 排除，仅本地保留）：
- `settings.local.json` — 权限、白名单、工具启用

> 历史备忘（`API_EXCEPTION_HANDLING.md` / `ERROR_FEEDBACK_FIX.md` / `FRONTEND_ERROR_HANDLING_VERIFY.md` / `SSE_ERROR_HANDLING_NOTE.md`）的内容已合并到 `AGENTS.md` §3.6，本地不再保留。

## 文档职责分工

| 文件 | 受众 | 内容 |
| --- | --- | --- |
| `AGENTS.md` | AI 编程助手（Codex / Claude Code / JoyCode 等） | 项目结构 + 开发约定 + 测试规范 + 文件膨胀控制（**最权威**） |
| `README.md` | 用户 / 部署者 | 项目目标 + 快速开始 + 部署 + Nginx 示例 |
| `CLAUDE.md`（本文件） | Claude Code | 仓库专属增量约定，其余内容转发到 AGENTS.md |
| `doc/` | 全员 | 专题设计文档（重构计划、量化 runbook 等） |
| `.claude/` | Claude Code | 本地权限与历史备忘 |

> 当仓库结构、API、配置变化时，先更新 `AGENTS.md`，再视情况同步本文件。
