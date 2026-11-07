# 前端 EdgeOne 部署计划

> 更新：2026-11-07。前端适配与 GitHub 关联已完成，API 站点与 EdgeOne 发布正在执行。

## 现状与目标

| 项目 | 当前 | 目标 |
| --- | --- | --- |
| 前端 | `chat-h.cc` → 新加坡服务器 Nginx 静态文件 | `chat-h.cc` → EdgeOne Makers 静态托管/CDN |
| API | 同域 `/never_guess_my_usage/` → `127.0.0.1:39997` | `https://api.chat-h.cc/never_guess_my_usage/` → 原 Flask |
| 附件 | `https://chat-h.cc:4567/download/`，目录 `/home/www/downloads/` | `https://api.chat-h.cc/download/`，同一目录 |
| 数据与任务 | 原服务器 SQLite、量化进程、音频文件 | 继续由原服务器运行 |
| 发布 | 本机打包、传输到服务器 | GitHub 指定生产分支推送后自动构建 |

服务器公网地址为 `43.134.239.126`，地域新加坡；DNS 在 Spaceship，当前使用 `launch1.spaceship.net`、`launch2.spaceship.net`。域名未备案，EdgeOne 必须选择“全球可用区（不含中国大陆）”。大陆用户访问境外节点，实际提速需上线后实测。免费套餐和当前资源以控制台为准。

## 已实现的开发适配

- `services/backendUrl.ts`：统一读取公开构建变量 `VITE_API_BASE_URL`、`VITE_FILE_BASE_URL`；未设置时保留本机开发和同源生产行为。
- Axios、令牌刷新、SSE 使用同一 API 地址；上传、图片、历史附件共用文件地址解析。
- 旧 `:4567/download/` 和 `chat-h.cc:4567/download/` 在显示和发送模型上下文时改用新文件入口，保留原始历史记录。
- `cyf/project/fe/edgeone.json`：Node 22.21.1、`npm ci`、`npm run build`、`dist`、SPA 回退；入口重新验证缓存，带哈希的 `/assets/` 缓存一年。
- `cyf/project/fe/nginx-api.conf.tpl`：独立 API 站点、CORS 白名单、无缓存/无缓冲 SSE、50MB 请求体、HTTPS 文件路径、真实 `/health`。

API 密钥、数据库、生产配置及文件目录均不进入前端构建变量。`VITE_*` 会打入公开浏览器代码。

## 关联和构建配置

GitHub 仓库：`vyfe/openai-project`。EO Makers App 仅授权该仓库；本轮开发分支为 `codex/edgeone-frontend-deploy`，不要将旧 `master` 直接用作生产发布来源。

| EdgeOne 配置 | 值 |
| --- | --- |
| 根目录 | `cyf/project/fe` |
| 框架 | Vite / Vue |
| 安装命令 | `npm ci` |
| 构建命令 | `npm run build` |
| 输出目录 | `dist` |
| Node.js | `22.21.1` |
| 加速区域 | 全球可用区（不含中国大陆） |
| `VITE_API_BASE_URL` | `https://api.chat-h.cc` |
| `VITE_FILE_BASE_URL` | `https://api.chat-h.cc` |

变量分别配置到生产和预览环境；修改后需要重新构建。默认项目域名在中国大陆需要有效期 3 小时的预览链接，稳定验收使用自定义 `preview.chat-h.cc`。

## 上线顺序

1. 在 Spaceship 添加 `api` A → `43.134.239.126`，先保持主域名解析不变。
2. 原服务器添加 API 的 HTTP ACME 验证站点；为 `api.chat-h.cc` 签发独立证书，配置自动续期和续期后 Nginx reload。
3. 备份现有 Nginx 配置，安装 API 模板；确认上传目录与生产配置一致。执行 Nginx 配置检查成功后 reload，保留原主站配置。
4. 验证 API 的 HTTPS、真实 JSON 健康检查、精确 CORS 响应、允许/拒绝来源、上传下载、SSE 即时分块。新 API 无需公网开放 39997。
5. EdgeOne 导入仓库并部署上述分支，绑定 `preview.chat-h.cc`，按平台提供的目标添加 CNAME 并启用免费 HTTPS。
6. 测试登录/刷新令牌、聊天/取消、历史附件、管理员、量化、语音/音乐记录与下载。付费合成调用仅按用户明确授权执行；迁移验证优先复用已有记录。
7. 全部验证通过后绑定 `chat-h.cc`，按控制台提示替换根域解析。切换期间已打开旧代码的浏览器需刷新。保持 API 子域直连服务器。
8. 保留旧前端与 Nginx 主站至少 7 天；复查 DNS、证书和新部署自动发布。

## 验收与回滚

- HTTP 返回 200 仅代表网络可达；`/health` 必须返回 `service=openai-project` 的 JSON。
- 前端嵌套路由刷新正常；HTML 更新可见、哈希资产长期缓存；API 和私人音频无 CDN 缓存。
- 允许来源只有一份 `Access-Control-Allow-Origin`，值为精确来源；未授权来源无该头。JWT 通过 Authorization，不依赖跨域 Cookie。
- SSE 无缓冲且可取消；附件通过标准 HTTPS，旧会话附件继续可读。
- 发生故障时恢复 Spaceship 原根域 A 记录 `43.134.239.126`，EdgeOne 可回滚到上一个成功部署。DNS 生效取决于 TTL 和递归缓存，无法承诺秒级回滚。
- 切换根域后，旧主域证书的 HTTP 验证续期路径会变化；API 使用独立证书/续期任务，避免依赖根域回源。

## 当前执行状态

- 已确认腾讯云和 GitHub 账号；EO Makers 基础 GitHub 授权已通过。
- EO Makers GitHub App 已安装，仅授权 `vyfe/openai-project`；Spaceship 已登录。
- `api.chat-h.cc` A 记录已解析到 `43.134.239.126`，主域仍指向原服务器。
- 前端测试、构建和本地启动验证完成；最终验证结果以本轮提交前记录为准。
- 已通过 14 个文件共 129 项前端测试、生产构建与本地启动检查；API Nginx 模板语法检查通过。
- EdgeOne 项目与生产 API 站点待发布，主域流量尚未切换。

## 官方资料

- [构建配置](https://pages.edgeone.ai/document/build-guide)
- [edgeone.json 与 SPA 回退](https://pages.edgeone.ai/document/edgeone-json)
- [域名、区域与大陆预览限制](https://pages.edgeone.ai/document/domain-overview)
- [套餐](https://pages.edgeone.ai/zh/pricing)
