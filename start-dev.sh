#!/usr/bin/env bash
# 开发环境启动脚本 - 同时启动前端和后端

# 如果通过 sh 调用，自动切换到 bash，避免 shell 兼容性问题
if [ -z "${BASH_VERSION:-}" ]; then
    exec bash "$0" "$@"
fi

set -euo pipefail
set +m

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_PORT=39997
FRONTEND_PORT=3000
BACKEND_LOG="${TMPDIR:-/tmp}/openai-project-backend.log"
FRONTEND_LOG="${TMPDIR:-/tmp}/openai-project-frontend.log"

BACKEND_PID=""
FRONTEND_PID=""

kill_port() {
    local port="$1"
    local pids
    pids="$(lsof -ti:"$port" 2>/dev/null || true)"
    if [ -n "$pids" ]; then
        echo "⚠️  端口 ${port} 被占用，正在终止进程: ${pids}"
        kill ${pids} 2>/dev/null || true
        sleep 1
        kill -9 ${pids} 2>/dev/null || true
    fi
}

is_port_open() {
    local port="$1"
    python3 - "$port" <<'PY'
import socket
import sys

port = int(sys.argv[1])
targets = [
    ("127.0.0.1", socket.AF_INET),
    ("::1", socket.AF_INET6),
]

for host, family in targets:
    sock = socket.socket(family, socket.SOCK_STREAM)
    sock.settimeout(0.3)
    try:
        sock.connect((host, port))
        sys.exit(0)
    except OSError:
        pass
    finally:
        sock.close()

# 兜底：走 localhost 解析，兼容系统仅监听 localhost 的场景
try:
    infos = socket.getaddrinfo("localhost", port, type=socket.SOCK_STREAM)
except OSError:
    infos = []

for family, socktype, proto, _, sockaddr in infos:
    sock = socket.socket(family, socktype, proto)
    sock.settimeout(0.3)
    try:
        sock.connect(sockaddr)
        sys.exit(0)
    except OSError:
        pass
    finally:
        sock.close()

sys.exit(1)
PY
}

can_bind_port() {
    local port="$1"
    python3 - "$port" <<'PY'
import errno
import socket
import sys

port = int(sys.argv[1])
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    sock.bind(("127.0.0.1", port))
except OSError as e:
    if e.errno in (errno.EPERM, errno.EACCES):
        print(f"permission:{e}")
        sys.exit(2)
    print(f"busy:{e}")
    sys.exit(1)
finally:
    sock.close()
sys.exit(0)
PY
}

print_log_tail() {
    local name="$1"
    local file="$2"
    if [ -f "$file" ]; then
        echo "----- ${name} 日志（最后100行）-----"
        tail -n 100 "$file"
        echo "----- ${name} 日志结束 -----"
    fi
}

wait_for_service() {
    local name="$1"
    local port="$2"
    local pid="$3"
    local timeout_seconds="$4"
    local log_file="$5"
    local elapsed=0

    while [ "$elapsed" -lt "$timeout_seconds" ]; do
        if is_port_open "$port"; then
            echo "✅ ${name} 已启动（端口 ${port}）"
            return 0
        fi

        if ! kill -0 "$pid" 2>/dev/null; then
            echo "❌ ${name} 进程已退出（PID: ${pid}）"
            print_log_tail "$name" "$log_file"
            return 1
        fi

        sleep 1
        elapsed=$((elapsed + 1))
    done

    echo "❌ ${name} 启动超时（${timeout_seconds}s），端口 ${port} 未就绪"
    print_log_tail "$name" "$log_file"
    return 1
}

cleanup() {
    trap - INT TERM EXIT
    trap - ERR
    echo ""
    echo "🛑 正在停止开发环境..."

    if [[ -n "${FRONTEND_PID}" ]] && kill -0 "${FRONTEND_PID}" 2>/dev/null; then
        kill "${FRONTEND_PID}" 2>/dev/null || true
    fi
    if [[ -n "${BACKEND_PID}" ]] && kill -0 "${BACKEND_PID}" 2>/dev/null; then
        kill "${BACKEND_PID}" 2>/dev/null || true
    fi

    # 回收子进程，避免 shell 打印 Terminated 作业信息
    if [[ -n "${FRONTEND_PID}" ]]; then
        wait "${FRONTEND_PID}" 2>/dev/null || true
    fi
    if [[ -n "${BACKEND_PID}" ]]; then
        wait "${BACKEND_PID}" 2>/dev/null || true
    fi

    sleep 1

    if [[ -n "${FRONTEND_PID}" ]] && kill -0 "${FRONTEND_PID}" 2>/dev/null; then
        kill -9 "${FRONTEND_PID}" 2>/dev/null || true
    fi
    if [[ -n "${BACKEND_PID}" ]] && kill -0 "${BACKEND_PID}" 2>/dev/null; then
        kill -9 "${BACKEND_PID}" 2>/dev/null || true
    fi

    if [[ -n "${FRONTEND_PID}" ]]; then
        wait "${FRONTEND_PID}" 2>/dev/null || true
    fi
    if [[ -n "${BACKEND_PID}" ]]; then
        wait "${BACKEND_PID}" 2>/dev/null || true
    fi

    kill_port "$FRONTEND_PORT"
    kill_port "$BACKEND_PORT"
    echo "👋 开发环境已停止"
}

on_signal() {
    cleanup
    exit 0
}

on_error() {
    local line="$1"
    echo "❌ 脚本在第 ${line} 行失败"
    print_log_tail "后端" "$BACKEND_LOG"
    print_log_tail "前端" "$FRONTEND_LOG"
    cleanup
    exit 1
}

trap on_signal INT TERM
trap 'on_error $LINENO' ERR
trap cleanup EXIT

echo "🧹 清理占用的端口..."
kill_port "$FRONTEND_PORT"
kill_port "$BACKEND_PORT"

echo "🔎 预检端口绑定权限..."
bind_check_msg="$(can_bind_port "$BACKEND_PORT" || true)"
if [[ "$bind_check_msg" == permission:* ]]; then
    echo "❌ 当前环境禁止监听本地端口 (${BACKEND_PORT}): ${bind_check_msg#permission:}"
    echo "💡 常见原因：受限沙箱/容器策略。请在允许本地端口监听的终端环境执行。"
    exit 1
fi

echo "🚀 启动开发环境..."
echo "📄 后端日志: $BACKEND_LOG"
echo "📄 前端日志: $FRONTEND_LOG"
: > "$BACKEND_LOG"
: > "$FRONTEND_LOG"

if [ -x "$PROJECT_ROOT/.venv/bin/python" ]; then
    BACKEND_PYTHON="$PROJECT_ROOT/.venv/bin/python"
else
    BACKEND_PYTHON="python3"
fi

echo "🔌 启动后端服务..."
(
    cd "$PROJECT_ROOT/cyf/project/server"
    exec "$BACKEND_PYTHON" server.py
) >"$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

wait_for_service "后端" "$BACKEND_PORT" "$BACKEND_PID" 30 "$BACKEND_LOG"

echo "🌐 启动前端服务..."
(
    cd "$PROJECT_ROOT/cyf/project/fe"
    exec npm run dev
) >"$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!

wait_for_service "前端" "$FRONTEND_PORT" "$FRONTEND_PID" 45 "$FRONTEND_LOG"

echo "✅ 前后端服务已启动 (前端 PID: $FRONTEND_PID, 后端 PID: $BACKEND_PID)"
echo "💡 按 Ctrl+C 退出并停止所有服务"

wait "$FRONTEND_PID" "$BACKEND_PID"
