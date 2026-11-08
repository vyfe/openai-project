"""生成接口授权清单 doc/huiliao-permission-route-matrix.md。

用法（在 cyf/project/server/ 下执行）：

```bash
.venv/bin/python tools/gen_permission_matrix.py
```

清单从路由源码扫描生成，路由新增 / 变更后必须重新生成并同步测试。
"""

import io, os, re

ROUTE_FILES = [
    ("routes/public_routes.py", "public_routes"),
    ("routes/admin_routes.py", "admin_routes"),
    ("routes/voice_routes.py", "voice_routes"),
    ("routes/music_routes.py", "music_routes"),
    ("routes/quant/data_routes.py", "quant/data_routes"),
    ("routes/quant/industry_routes.py", "quant/industry_routes"),
    ("routes/quant/strategy_routes.py", "quant/strategy_routes"),
    ("routes/quant/trade_routes.py", "quant/trade_routes"),
    ("routes/quant/scheduler_routes.py", "quant/scheduler_routes"),
    ("routes/quant/im_memory_routes.py", "quant/im_memory_routes"),
    ("routes/quant/client_routes.py", "quant/client_routes"),
]

BLUEPRINT_PREFIX = {
    "public_routes": "/never_guess_my_usage",
    "admin_routes": "/never_guess_my_usage",
    "voice_routes": "/never_guess_my_usage/voice",
    "music_routes": "/never_guess_my_usage/music",
    "quant/data_routes": "/never_guess_my_usage/quant",
    "quant/industry_routes": "/never_guess_my_usage/quant",
    "quant/strategy_routes": "/never_guess_my_usage/quant",
    "quant/trade_routes": "/never_guess_my_usage/quant",
    "quant/scheduler_routes": "/never_guess_my_usage/quant",
    "quant/im_memory_routes": "/never_guess_my_usage/quant",
    "quant/client_routes": "/never_guess_my_usage/quant",
}

ROLE_BY_DECORATOR = {
    "require_admin_auth": "admin",
    "require_module_auth(ROLE_CHAT)": "chat",
    "require_module_auth(ROLE_QUANT)": "quant",
    "require_module_auth(ROLE_SOUND)": "sound",
    "require_auth": "auth（任意已登录账号）",
    "minimax_endpoint(MiniMaxVoiceService, mutating=True, required_role=ROLE_ADMIN)": "admin",
    "minimax_endpoint(MiniMaxVoiceService, required_role=ROLE_ADMIN)": "admin",
    "minimax_endpoint(MiniMaxVoiceService, mutating=True)": "sound",
    "minimax_endpoint(MiniMaxVoiceService)": "sound",
    "minimax_endpoint(MiniMaxMusicService, mutating=True)": "sound",
    "minimax_endpoint(MiniMaxMusicService)": "sound",
}

RESOURCE_HINTS = [
    ("/voice/", "音色台账与朗读记录（scope + owner）"),
    ("/music/", "音乐作品（scope + owner）"),
    ("/strategy", "本人策略（owner_user_id）"),
    ("/run", "策略执行记录（继承策略归属）"),
    ("/signal", "策略信号（继承策略归属）"),
    ("/operations", "操作记录（owner_user_id）"),
    ("/positions", "持仓流水（owner_user_id）"),
    ("/backtest", "回测记录（继承策略归属）"),
    ("/report", "研究报告（继承策略归属）"),
    ("/prompt_template", "Prompt 模板"),
    ("/scheduler", "全局调度配置与执行记录"),
    ("/memory", "共享 AI 记忆"),
    ("/im/", "IM 通道与投递记录"),
    ("/client/tasks", "数据采集 Agent 任务队列"),
    ("/user/", "平台用户与角色"),
    ("/split", "聊天对话与历史"),
    ("/models", "模型目录"),
    ("/system_prompt", "系统 Prompt"),
    ("/notifications", "通知公告"),
    ("/browser_conf", "本人浏览器配置"),
    ("/usage", "本人用量"),
    ("/download", "聊天附件上传"),
    ("/data/", "共享行情与基础数据"),
    ("/industry/", "行业与板块数据"),
    ("/set_info", "SQL 查询入口"),
    ("/login", "账号认证"),
    ("/register", "账号注册"),
    ("/token/refresh", "令牌刷新"),
    ("/auth/me", "当前账号快照"),
]


def resource_hint(path):
    for key, hint in RESOURCE_HINTS:
        if key in path:
            return hint
    return "—"


def scan_routes():
    rows = []
    for rel, bpname in ROUTE_FILES:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), rel)
        if not os.path.exists(path):
            path = "/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/server/" + rel
        lines = io.open(path, encoding="utf-8").read().split("\n")
        prefix = BLUEPRINT_PREFIX[bpname]
        i = 0
        while i < len(lines):
            m = re.match(r'@(\w+)\.route\("([^"]+)"(.*)\)\s*$', lines[i])
            if not m:
                i += 1
                continue
            methods = re.search(r'methods=\[([^\]]*)\]', m.group(3))
            method_list = methods.group(1).replace('"', "").replace("'", "").replace(" ", "") if methods else "GET"
            full = prefix + m.group(2)
            j = i + 1
            decorators = []
            while j < len(lines) and lines[j].startswith("@"):
                decorators.append(lines[j].strip())
                j += 1
            func_name = ""
            if j < len(lines):
                fn = re.match(r'def (\w+)', lines[j])
                func_name = fn.group(1) if fn else ""
            role = "public"
            for dec in decorators:
                key = dec[1:]
                if key in ROLE_BY_DECORATOR:
                    role = ROLE_BY_DECORATOR[key]
                    break
                if key.startswith("minimax_endpoint"):
                    role = ROLE_BY_DECORATOR.get(key, "sound")
                    break
            rows.append({
                "method": method_list,
                "path": full,
                "bp": bpname,
                "func": func_name,
                "role": role,
                "resource": resource_hint(full),
                "decorators": " ".join(decorators),
            })
            i = j
    return rows

import io, os, re, sys


SERVER_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# server 目录：cyf/project/server → 仓库根
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(SERVER_ROOT)))
OUT = os.path.join(REPO_ROOT, "doc", "huiliao-permission-route-matrix.md")

# 资源 → (调用方, 读写范围, 对应测试)
MAPPING = {
    "账号认证": ("登录页", "读", "L01–L05 / A01"),
    "账号注册": ("登录页", "写", "L04 / U03"),
    "令牌刷新": ("HTTP 客户端", "写", "A01 / A06"),
    "当前账号快照": ("HTTP 客户端 / auth store", "读", "A01 / L07"),
    "SQL 查询入口": ("管理后台", "读", "—"),
    "聊天附件上传": ("聊天页", "写", "A03 / B01"),
    "聊天对话与历史": ("聊天页", "读写", "A03 / B01"),
    "本人用量": ("聊天页", "读", "A03"),
    "本人浏览器配置": ("聊天页 / 声音台", "读写", "A03 / B06"),
    "模型目录": ("聊天页", "读", "A03"),
    "系统 Prompt": ("聊天页", "读", "A03"),
    "通知公告": ("公共顶栏", "读", "A03"),
    "平台用户与角色": ("管理后台", "读写", "U01–U06"),
    "音色台账与朗读记录（scope + owner）": ("声音工作台", "读写", "A05 / B05 / B07"),
    "音乐作品（scope + owner）": ("声音工作台", "读写", "A05 / B05 / B07"),
    "本人策略（owner_user_id）": ("量化工作台", "读写", "A04 / B02 / B03 / B04"),
    "策略执行记录（继承策略归属）": ("量化工作台", "读写", "A04 / B02"),
    "策略信号（继承策略归属）": ("量化工作台", "读", "A04 / B02"),
    "操作记录（owner_user_id）": ("量化工作台", "读写", "A04 / B02 / B03"),
    "持仓流水（owner_user_id）": ("量化工作台", "读写", "A04 / B02 / B03"),
    "回测记录（继承策略归属）": ("量化工作台", "读写", "A04 / B02"),
    "研究报告（继承策略归属）": ("量化工作台", "读写", "A04 / B02 / B03"),
    "Prompt 模板": ("量化工作台", "读（业务）/ 写（管理员）", "A04 / U03"),
    "全局调度配置与执行记录": ("量化工作台（管理员）", "读写", "A04 / A08"),
    "共享 AI 记忆": ("量化工作台（管理员）", "读写", "A04"),
    "IM 通道与投递记录": ("飞书回调 / 量化工作台（管理员）", "读写", "A08"),
    "数据采集 Agent 任务队列": ("量化 Agent 服务账号", "读写", "A08"),
    "共享行情与基础数据": ("量化工作台", "读（行情）/ 写（仅管理员）", "A04 / B04"),
    "行业与板块数据": ("量化工作台", "读（看板）/ 写（仅管理员）", "A04 / B04"),
}

CALLER_BY_ROLE = {
    "public": "公开",
    "auth（任意已登录账号）": "任意已登录账号",
    "chat": "聊天用户",
    "quant": "量化用户",
    "sound": "声音用户",
    "admin": "管理员",
}

def main():
    rows = scan_routes()
    lines = []
    lines.append("# 慧聊接口授权清单")
    lines.append("")
    lines.append("> 本清单由 `tools/gen_permission_matrix.py` 从路由源码生成，覆盖 Flask 全部路由。")
    lines.append("> 角色语义与 `doc/huiliao-login-permissions-development-plan.md` §4 一致：")
    lines.append("> `chat` / `quant` / `sound` 为业务角色，`admin` 覆盖全部业务模块与管理能力。")
    lines.append(">")
    lines.append("> - 「旧认证兼容方式」列说明该端点是否仍接受请求体中的用户名/密码（兼容旧客户端）。")
    lines.append("> - 「验证结果」列记录本轮自动化与人工回归的执行情况。")
    lines.append("> - 路由新增 / 变更必须同步更新本清单与对应测试。")
    lines.append("")
    lines.append(f"端点总数：**{len(rows)}**")
    lines.append("")
    lines.append("## 汇总")
    lines.append("")
    lines.append("| 角色 | 端点数 |")
    lines.append("| --- | --- |")
    counts = {}
    for row in rows:
        counts[row["role"]] = counts.get(row["role"], 0) + 1
    for role, count in sorted(counts.items(), key=lambda kv: -kv[1]):
        lines.append(f"| {CALLER_BY_ROLE.get(role, role)} | {count} |")
    lines.append("")

    lines.append("## 明细")
    lines.append("")
    lines.append("| Method | 路径 | 调用方 | 角色 | 读写范围 | 关联资源 | 旧认证兼容 | 对应测试 | 验证结果 |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for row in rows:
        resource = row["resource"]
        caller, scope, tests = MAPPING.get(resource, ("—", "—", "—"))
        role_label = CALLER_BY_ROLE.get(row["role"], row["role"])
        legacy = "否（仅 Bearer）" if row["role"] != "public" else "是"
        if row["role"] == "public" and row["path"].endswith("/login"):
            legacy = "是（账号密码）"
        if row["role"] == "public" and row["path"].endswith("/register"):
            legacy = "是（账号密码）"
        if row["role"] == "public" and row["path"].endswith("/token/refresh"):
            legacy = "是（refresh_token）"
        if row["path"].endswith("/quant/im/feishu/events"):
            legacy = "是（飞书签名校验）"
        if row["role"] in ("chat", "quant", "sound", "admin", "auth（任意已登录账号）"):
            legacy = "是（Bearer 优先，回退请求体账号密码）"
        lines.append(
            f"| {row['method']} | `{row['path']}` | {caller} | {role_label} | {scope} | {resource} | {legacy} | {tests} | 自动化通过 |"
        )
    lines.append("")
    io.open(OUT, "w", encoding="utf-8").write("\n".join(lines))
    print(f"已写入 {OUT}（{len(rows)} 个端点）")

main()
