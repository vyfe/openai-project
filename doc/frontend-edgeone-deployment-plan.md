# 前端 EdgeOne 部署与运维手册

> 更新：2026-11-07。正式站 `chat-h.cc` 已切换到 EdgeOne Makers 并完成公网验证；API、附件与数据继续保留在新加坡原服务器。本文记录各平台现状与后续发布维护流程；README 为快速入口，AGENTS.md 为开发约定。

## 1. 生产架构与职责

| 入口/组件 | 承载位置 | 运维职责 |
| --- | --- | --- |
| `https://chat-h.cc` | EdgeOne Makers 静态托管/CDN | 正式前端、SPA 路由、静态缓存、边缘 HTTPS |
| `https://preview.chat-h.cc` | 同一 EdgeOne 项目的生产环境 | 本轮迁移验收入口，与正式域同步发布 |
| `https://api.chat-h.cc/never_guess_my_usage/` | `43.134.239.126` → Nginx → `127.0.0.1:39997` | Flask API、JWT、SSE、文件上传 |
| `https://api.chat-h.cc/download/` | 同一 Nginx → `/home/www/downloads/` | 现有附件的标准 HTTPS 下载入口 |
| SQLite、量化、语音与音乐文件 | 原服务器 | 后端数据、调度、采集、飞书和音频落盘 |
| DNS | Spaceship `launch1/launch2.spaceship.net` | 域名解析及验证记录 |
| 服务器证书与计划任务 | 宝塔 | API 证书检查、续签、Nginx reload 和执行日志 |

服务器地域为新加坡。域名无 ICP 备案，EdgeOne 选择“全球可用区（不含中国大陆）”；大陆用户访问境外节点。前端加速覆盖 HTML/JS/CSS/字体等静态资源，聊天和文件流量经 API 子域访问原服务器。

## 2. 本轮各平台变更

### GitHub 与代码

- 仓库：`vyfe/openai-project`，EO Makers GitHub App 仅授权该仓库。
- EdgeOne 当前生产分支：`codex/edgeone-frontend-deploy`。推送到该分支会自动触发构建流水线，在 EdgeOne“构建部署”点击发布后生效；`master` 当前不作为生产来源。
- `services/backendUrl.ts` 统一 API 和文件地址；Axios、令牌刷新、SSE、上传和附件渲染共用配置。
- 显示附件和发送模型上下文时，将旧 `:4567/download/`、`chat-h.cc:4567/download/` 改为新文件入口，历史数据保留原内容。
- `package-lock.json` 下载地址统一为 npm 官方 registry，保留依赖版本和 integrity。首次云构建因内网 registry 不可达失败，修复后构建成功。
- `edgeone.json` 保存安装、构建、Node 版本、SPA 回退和缓存策略；`nginx-api.conf.tpl` 保存独立 API 配置；`renew-server-certs.sh` 保存服务器统一续签逻辑。
- `server_pack.py` 打包时排除服务器私有的 `conf/conf.ini` 和 `.priv` 私钥文件；生产密钥通过服务器受控配置维护。

### EdgeOne Makers

| 配置 | 实际值 |
| --- | --- |
| 项目名 / ID | `openai-project` / `makers-ewkduzmpajma` |
| [项目控制台](https://console.cloud.tencent.com/edgeone/makers/project/makers-ewkduzmpajma/index) | 构建部署、域名管理和项目设置 |
| 根目录 | `cyf/project/fe` |
| 框架 / Node.js | Vite / Vue，`22.21.1` |
| 安装 / 构建 / 输出 | `npm ci` / `npm run build` / `dist` |
| 加速区域 | 全球可用区（不含中国大陆） |
| `VITE_API_BASE_URL` | `https://api.chat-h.cc` |
| `VITE_FILE_BASE_URL` | `https://api.chat-h.cc` |
| 默认项目域名 | `openai-project-zeemrvrl.edgeone.dev` |
| 正式 / 迁移验收域名 | `chat-h.cc` / `preview.chat-h.cc`，均关联生产环境 |
| 正式域 HTTPS | EdgeOne 免费证书已部署；HTTP 到 HTTPS 强制 301 跳转 |
| 首次成功部署 | `dpwnl5vp6syc`，提交 `e0aa76a` |

构建变量已配置到生产及预览环境。`VITE_*` 会进入公开浏览器代码，仅放公开服务地址；生产密钥、配置和数据库保留在服务器。修改环境变量后重新部署才生效。默认项目域名在中国大陆需要有效期 3 小时的预览链接，日常使用自定义域名。

缓存与路由由 `edgeone.json` 管理：HTML `Cache-Control: no-cache`，带哈希的 `/assets/*` 为 `public, max-age=600, must-revalidate`；Vue 嵌套路由回退到 `/index.html`。API 子域独立于 EdgeOne，Nginx 设置 `private, no-store`。

> `/assets/*` 的缓存刻意不用一年期 + `immutable`，原因见 §3.1「SPA 回退与静态资源缓存冲突」。

### Spaceship DNS

| 主机记录 | 类型 | 值 | TTL / 用途 |
| --- | --- | --- | --- |
| `@` | CNAME | `chat-h.cc.pages.dnsoe6.com` | 1 分钟，正式站 |
| `preview` | CNAME | `preview.chat-h.cc.pages.dnsoe5.com` | 1 分钟，迁移验收站 |
| `api` | A | `43.134.239.126` | 1 分钟，API 直连原服务器 |
| `_dnsauth` | CNAME | `chat-h.cc.eoacme0.com` | 30 分钟，EdgeOne 免费证书委派验证 |
| `edgeonereclaim` | TXT | 平台已下发的 `reclaim-…` 值 | 正式域名归属验证，保留 |
| `edgeonereclaim.preview` | TXT | 平台已下发的 `reclaim-…` 值 | 验收域名归属验证，保留 |
| `_acme-challenge` | TXT | 原有验证值 | 原配置，保留 |

Spaceship 支持本次根域 CNAME 配置，并将根域查询展开为 A 记录；EdgeOne 域名详情对展平记录可能显示“请添加 CNAME”，平台说明该状态可忽略。应以 DNS 实际解析和 HTTP 响应验证接入：本轮 Spaceship 权威 DNS 与公共 DNS 均解析至 EdgeOne 节点 `43.174.246.112`、`43.174.247.112`，正式站响应头为 `Server: edgeone makers`。维护时保留平台下发的目标域名，节点 IP 由平台调度。

本次已将根域原 A 记录 `43.134.239.126` 替换为 EdgeOne CNAME `chat-h.cc.pages.dnsoe6.com`，名称服务器继续使用 Spaceship。`api` A 记录仍指向 `43.134.239.126`，不随前端切换改变。变更后通过权威 DNS、公共 DNS 及正式域 HTTPS 实测；Chrome 根域访问跳转至 `/login`。已有递归缓存按原 TTL 失效。

### 原服务器、Nginx 与宝塔

- API vhost：`/www/server/panel/vhost/nginx/api.chat-h.cc.conf`，内容对应仓库 `cyf/project/fe/nginx-api.conf.tpl`。
- API 80 端口保留 HTTP ACME 验证目录 `/www/wwwroot/api.chat-h.cc`，其它请求跳到 HTTPS；443 反代 Flask，SSE 无缓存/无缓冲、超时 900 秒、请求体上限 50MB。
- CORS 固定允许 `https://chat-h.cc`、`https://preview.chat-h.cc`、`http://localhost:3000`；由 Nginx 统一输出精确来源，隐藏上游旧 CORS 头。JWT 使用 Authorization。
- `/download/` 指向原上传目录 `/home/www/downloads/`；`/health` 返回真实后端 JSON。
- API 证书：`/www/server/panel/vhost/letsencrypt/api.chat-h.cc/{fullchain,privkey}.pem`；`/www/server/panel/vhost/cert/api.chat-h.cc` 软链接到该目录，私钥权限 600。首次证书有效期至 `2027-02-05 06:47:19 GMT`。
- 原主站配置 `/www/server/panel/vhost/nginx/other_llm_server.conf`、旧前端和数据保留。备份目录 `/home/lighthouse/edgeone-backup-20261107/`，包含原主站配置及本轮中间配置。

## 3. 证书与定时任务

公网主站和预览站证书由 EdgeOne 免费托管，平台在到期前 15 天自动更新。正式域名通过 DNS 委派完成验证并部署，证书状态“已部署”，有效期至 `2027-02-05 07:59:59`；保留 `_dnsauth` 记录。本轮也在原站 `.well-known/pki-validation/fileauth.txt` 放置了首次文件验证材料；长期续签以 EdgeOne 当前委派配置为准。正式域已开启强制 HTTPS，选择 301 永久跳转；没有启用 HSTS，避免浏览器持久策略影响回滚。

服务器证书统一在宝塔“计划任务 → 续签Let's Encrypt证书”管理：

| 项目 | 配置 |
| --- | --- |
| 执行周期 / 用户 | 每天 21:39 / root，以宝塔面板显示时间为准 |
| 任务命令 | `/usr/local/sbin/openai-server-cert-renew` |
| 对应仓库脚本 | `cyf/project/fe/renew-server-certs.sh` |
| 原批量续签命令 | `/www/server/panel/pyenv/bin/python3 -u /www/server/panel/class/acme_v2.py --renew=1` |
| 任务日志 | `/www/server/cron/3ab48c27ec99cb9787749c362afae517.log`，也可直接在面板点击“日志” |

脚本先执行原批量续签，再单独检查 API 手工 vhost 的证书。剩余有效期不足 30 天时，用宝塔已有 ACME 账户和 HTTP webroot 申请证书，校验证书、限制私钥权限、执行 Nginx 配置检查后 reload。加锁避免同时运行，批量续签失败仍执行 API 检查，并保留失败退出码。

本轮新增的独立 `/etc/cron.d/openai-api-cert` 已移出运行目录，备份为 `edgeone-backup-20261107/openai-api-cert.cron.disabled`；原单域脚本备份为 `openai-api-cert-renew.previous`。后续周期修改和手动执行均从宝塔计划任务操作。

维护脚本时，在服务器以 root 安装：

```bash
install -m 700 /path/to/renew-server-certs.sh /usr/local/sbin/openai-server-cert-renew
bash -n /usr/local/sbin/openai-server-cert-renew
```

随后在宝塔点击原任务“执行”，检查日志。2026-11-07 16:12:43 已执行成功：原批量检查结束，API 证书超过 30 天，本次无需签发。EdgeOne 公网证书和服务器 API 证书分别在各自控制台管理。

### 3.1 SPA 回退与静态资源缓存冲突（务必了解）

EdgeOne Makers 的 SPA fallback 语义是**先匹配静态资源，匹配不到才回退 `/index.html`**（[官方说明](https://pages.edgeone.ai/document/edgeone-json)）。因此正常情况下 `/assets/*.js` 直接命中文件，不会拿到 HTML。

问题出在**部署切换的窗口期**：新旧资源不是原子切换的那几十秒里，某个 `/assets/xxx.js` 可能尚未就位 → 请求 miss → 回退到 `index.html` → 响应是 **200 + `Content-Type: text/html`**。

而 headers 规则是**按请求路径匹配**的，EdgeOne 无法区分「静态文件命中」和「回退响应」。如果 `/assets/*` 规则带了 `max-age=31536000, immutable`，这份 **HTML 会被浏览器当成那个 JS 文件缓存下来**，且 `immutable` 让浏览器不再发起条件请求 —— 之后无论服务器和 CDN 是否正常，普通刷新都无法恢复，只能清站点缓存。

典型症状：

```
Failed to load module script: Expected a JavaScript-or-Wasm module script
but the server responded with a MIME type of "text/html".
```

排查顺序：**先确认服务器侧是否正常**（`curl -I https://chat-h.cc/assets/<文件名>` 看 `Content-Type`）。若服务器返回 `application/javascript`，问题就在浏览器本地缓存，清站点缓存即可恢复。

#### 触发条件：构建产物必须是确定性的

上面那个窗口期之所以会伤到用户，是因为 **EdgeOne 边缘节点会缓存 `index.html`（实测 `Age` 可达 4700 秒，`Cache-Control: no-cache` 不被遵守）**。于是用户可能拿到**旧版 HTML**，而它引用的 chunk 已被新部署删除：

```
旧 HTML  ──引用──►  旧 chunk 哈希（比如 index-FTgCRYNU.js）
                        ↓ 新部署已删除该文件
                    请求 miss → SPA 回退返回 HTML → 浏览器按 /assets/* 规则缓存
                        ↓
                  "MIME type of text/html"，清缓存前无法恢复
```

路由懒加载 chunk 同样受影响，会表现为 `Failed to fetch dynamically imported module`。

**只要构建是确定性的，这条链就断了**：新旧部署的 chunk 文件名完全相同，旧 HTML 引用的文件在新部署里依然存在，永远不会 miss。2026-11-07 已修掉这个非确定性来源 —— `vite.config.ts` 原先用 `define` 把构建时刻注入 `__BUILD_TIME__`，它经 `src/services/version.ts` 渗进几乎所有应用 chunk，导致**每次构建所有应用 chunk 哈希都变**（实测间隔 2 秒的两次构建产物全不同）。现在构建时间改为注入 `index.html` 的 `window.__BUILD_TIME__`，不进 JS chunk，产物可复现。

**这条约束对以后改构建配置同样重要**：任何进入 chunk 内容的构建期变量（时间戳、随机数、commit hash）都会让产物哈希漂移，把部署变成非原子操作。如需在页面展示构建时间，走 `index.html` 注入或运行时计算。

校验构建确定性：

```bash
cd cyf/project/fe
npm run build && cp -r dist /tmp/b1 && npm run build && cp -r dist /tmp/b2
diff <(ls /tmp/b1/assets) <(ls /tmp/b2/assets)   # 应无输出
```

因此 `/assets/*` 的缓存策略刻意不用一年期 + `immutable`，改为 `public, max-age=600, must-revalidate`：靠 ETag 协商仍能拿到 304；而窗口期 miss 的回退最多影响 10 分钟，浏览器会自动重新校验恢复。代价是每 10 分钟一次条件请求，性能损失可忽略。

调整 `edgeone.json` 后需重新部署才生效。每次部署后用自检脚本确认：

```bash
bash cyf/project/fe/verify-deploy.sh https://chat-h.cc
```

脚本会逐个校验首页引用的静态资源的 HTTP 状态与 MIME 类型，并探测缺失资源回退的 `Cache-Control`，任一项不达标即退出码非 0。

## 4. 后续前端开发与发布

1. 本机按常规功能分支开发。未配置 `VITE_*` 时，开发默认使用 `http://localhost:39997`；需要连接生产 API 时在本地忽略文件 `.env.local` 设置公开地址。
2. 在 `cyf/project/fe` 执行 `npm ci`、`npm run test`、`npm run build`。新增附件路径复用 `backendUrl.ts`；后端调用复用现有 API 客户端。
3. 审核通过后，将功能提交集成到 `codex/edgeone-frontend-deploy` 并 push。push 会自动触发 EdgeOne 构建流水线；该分支是当前正式发布入口，合并前核对目标分支和生产变更范围。
4. 在 EdgeOne“构建部署”确认对应 commit 的流水线构建成功，再点击**发布**使其成为生产部署，然后访问 `https://chat-h.cc`；新代码由浏览器重新请求 HTML 后加载。发布完成后跑一次自检脚本，确认所有静态资源 MIME 正确、缓存策略符合预期：

   ```bash
   bash cyf/project/fe/verify-deploy.sh https://chat-h.cc
   ```
5. 验证范围按改动选择：登录/API、SSE、上传下载或对应业务页。API/附件地址配置变化时必须重新构建。

本机模拟 EdgeOne 构建：

```bash
cd cyf/project/fe
npm ci
npm run test
VITE_API_BASE_URL=https://api.chat-h.cc VITE_FILE_BASE_URL=https://api.chat-h.cc npm run build
```

`preview.chat-h.cc` 当前是生产别名，与正式站同步发布。功能分支的隔离验收使用 EdgeOne 单次部署地址或项目预览环境；若新增固定验收域名，需同时配置 DNS、HTTPS 与 API CORS 白名单。以后调整生产分支时，先在项目设置更改并完成一次成功发布，再同步修改本文和 AGENTS.md。

## 5. 后续后端开发与发布

后端继续使用现有服务器分包发布，前端发布与后端重启各自独立：

1. 激活已安装依赖的项目 Python 环境，在 `cyf/project/server` 执行 `python -m pytest -m "not api"`（本机也可用 `../../../.venv/bin/python -m pytest -m "not api"`）。涉及量化表列变更时先完成 AGENTS.md 规定的 DDL 与生产 soft 迁移。
2. 发布前备份生产 `conf/conf.ini`、平台和量化数据库，以及本次涉及的附件/音频目录。备份可使用现有宝塔“db备份”任务；SQLite 在线备份使用其备份机制，或在停写窗口备份。
3. 在后端目录执行 `python3 server_pack.py`，得到 `dist/server.tar.gz`；同时准备匹配版本的根目录 `requirements.txt` 和 `start-prod.sh`。打包脚本会自动排除服务器私有的 `conf/conf.ini` 和所有 `.priv` 私钥文件。发布前检查归档清单，确认 `conf/conf.ini`、私钥均未打入，且 `conf/uwsgi.ini` 等运行配置仍在包内；生产配置保留在服务器受控目录。产物仅在受控服务器发布通道传输。

   ```bash
   # 私有文件必须不在包内；运行配置必须在包内
   if tar -tzf dist/server.tar.gz | grep -qE '(^|/)(conf\.ini|[^/]+\.priv)$'; then
     echo '❌ 私有文件被打包，终止发布'
   else
     echo '✅ 未包含 conf.ini / .priv'
   fi
   tar -tzf dist/server.tar.gz | grep -q '^conf/uwsgi.ini$' \
     && echo '✅ conf/uwsgi.ini 在包内' || echo '❌ 缺少 conf/uwsgi.ini'
   ```
4. 将后端包放在 `/home/lighthouse/openai-project/server.tar.gz`，配套依赖和启动脚本放在同一项目根目录。以 lighthouse 用户、现有 Python 环境执行：

   ```bash
   cd /home/lighthouse/openai-project
   bash start-prod.sh --backend-only --restart
   ```

5. 脚本更新后端并启动 `/home/lighthouse/.local/bin/uwsgi`，监听 `127.0.0.1:39997`。检查本机和公网 `/health` JSON，确认 `service=openai-project`、`status=ok`；按改动检查对应业务。
6. 量化采集与调度是独立进程；仅在相关代码变更时按现有 `start-prod-quant` 流程更新和重启。脚本中的 Agent 登录凭据已外置，与 `conf.ini` 一样走「模板 → 复制 → 填值」；更新脚本前先在服务器项目根目录准备受控文件（权限 600）：

   ```bash
   cd /home/lighthouse/openai-project
   cp .quant-credentials.tpl .quant-credentials   # 模板随代码分发，只有占位符
   $EDITOR .quant-credentials                      # 填 QUANT_LOGIN_USER / QUANT_LOGIN_PASSWORD
   chmod 600 .quant-credentials
   ```

   模板文件为仓库根目录 `.quant-credentials.tpl`，实际凭据文件由 `.gitignore` 拦截不入库。也可用环境变量 `QUANT_LOGIN_USER` / `QUANT_LOGIN_PASSWORD` 覆盖；两者都缺失时 `start-prod-quant --agent` 会明确报错退出，不会静默使用内置账号。调度 Worker 不需要凭据。确认任务与数据库状态后结束发布。

宝塔已有部署类 Shell 任务本轮保持原状态；本轮未切换后端发布方式。`start-prod.sh --frontend-only` 和整包 `--all` 保留给原服务器静态站部署，当前 EdgeOne 前端由 Git 构建发布。

## 6. 日常检查、故障定位与回滚

| 现象 | 优先检查 |
| --- | --- |
| 静态页打不开、刷新嵌套路由失败 | EdgeOne 最新生产部署、域名状态、`edgeone.json` 的 SPA 回退 |
| 报 “Expected a JavaScript-or-Wasm module script … MIME type of text/html” | 先 `curl -I` 目标资源的 `Content-Type`：服务器正常则是浏览器缓存了回退 HTML，清站点缓存；详见 §3.1 |
| 新版本未出现 | 生产 commit、环境变量是否重建、HTML 响应与浏览器刷新 |
| 登录/模型/API 报错 | `api.chat-h.cc/health`、JWT、浏览器 CORS、Nginx 和后端日志 |
| 流式输出延迟或中断 | API Nginx `proxy_buffering off`、上游响应、后端日志 |
| 上传失败或附件不可读 | 请求体大小、`upload_dir`、`/download/` alias、文件 URL 是否为 API 标准 HTTPS |
| 证书异常 | 主站看 EdgeOne 域名 HTTPS 状态，API 看宝塔计划任务日志及证书到期时间 |

常用只读检查：

```bash
curl -I https://chat-h.cc/login
curl -fsS https://api.chat-h.cc/health
curl -i -X OPTIONS https://api.chat-h.cc/never_guess_my_usage/models -H 'Origin: https://chat-h.cc' -H 'Access-Control-Request-Method: GET'
dig @launch1.spaceship.net chat-h.cc A +short
dig @launch1.spaceship.net api.chat-h.cc A +short
```

- **前端版本回滚**：在 EdgeOne“构建部署”将历史成功版本恢复为生产，并核对 commit 与主站。DNS 保持 EdgeOne 配置。
- **整站入口回滚**：在 Spaceship 将 `@` CNAME 恢复为 A `43.134.239.126`，保留 API 子域与验证记录，验证旧站。递归缓存按 TTL 传播。原静态站和 Nginx 至少保留到 2026-11-14，清理前确认可用备份和回滚要求。
- **后端回滚**：恢复上一版包和匹配依赖，再按后端单独发布；数据库依据迁移回滚方案处理。API Nginx 改动前备份，执行 `/www/server/nginx/sbin/nginx -t` 成功后再 reload。

## 7. 本轮验收与资源费用

- 前端 14 个测试文件、129 项测试通过，生产构建及本地启动通过；云端 `npm ci` 和构建成功。
- 收尾后端测试使用项目虚拟环境执行 `python -m pytest -m "not api"`：1132 项通过、21 项按标记排除。打包脚本在隔离目录运行通过，归档保留 `conf/uwsgi.ini` 并排除 `conf/conf.ini` 和 `.priv`；续签脚本 `bash -n` 与 `git diff --check` 通过。
- API HTTPS、真实健康 JSON、允许与拒绝来源的 CORS、未登录鉴权通过；20MB 文件上传下载 SHA256 一致。
- Chrome 预览站管理员登录、模型列表、文本文件上传、模型读取验证码 `EDGEONE-7319` 通过；浏览器上传的文本下载 SHA256 一致。PNG 上传后以 API HTTPS 显示，实际尺寸 160×100，预览加载完成。
- 聊天 SSE 已收到真实响应。按用户要求停止进一步业务回归，保留本轮测试会话与附件；管理员、量化、音频等更完整回归交由后续功能发布按需执行。
- 2026-11-07 正式切换完成：Spaceship 根域 CNAME 指向 `chat-h.cc.pages.dnsoe6.com`；权威和公共 DNS 返回 EdgeOne 节点。`https://chat-h.cc/login` 返回 200、响应头 `Server: edgeone makers`，页面资源从 EdgeOne 加载；Chrome 访问根域可进入登录页。EdgeOne 免费证书已部署至 `2027-02-05`，HTTP 已配置 301 到 HTTPS。
- 同时验证 API `https://api.chat-h.cc/health` 返回 `service=openai-project`、`status=ok`；API 域名仍指向新加坡服务器。

本轮使用 EdgeOne 免费套餐和免费证书，未购买付费升级。原腾讯云服务器与 Spaceship 域名继续按原周期续费；服务器承担 API、附件和数据流量。EdgeOne 用量与套餐额度在控制台查看，流量或功能超额前按平台当前价格评估。服务器续签使用 Let's Encrypt 免费证书。

## 8. 官方资料

- [Makers 构建指南](https://cloud.tencent.com/document/product/1552/127392)
- [edgeone.json 与 SPA 回退](https://pages.edgeone.ai/document/edgeone-json)
- [自定义域名](https://cloud.tencent.com/document/product/1552/127404)
- [免费证书、DNS 委派和自动续期](https://cloud.tencent.com/document/product/1552/127407)
- [套餐](https://pages.edgeone.ai/zh/pricing)
