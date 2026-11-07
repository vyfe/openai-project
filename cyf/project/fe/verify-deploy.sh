#!/usr/bin/env bash
# 校验线上前端部署是否正常。
#
# 背景：EdgeOne 的 SPA fallback（rewrites: /* → /index.html）在静态资源
# 尚未就位的瞬间会返回 200 + text/html；若 /assets/* 规则同时带
# "max-age=31536000, immutable"，浏览器会把这份 HTML 当成 JS 缓存下来，
# 导致 "Expected a JavaScript-or-Wasm module script" 且普通刷新无法恢复。
# 本脚本在每次部署后跑一遍，能提前发现资源缺失或缓存规则过激。
#
# 用法：
#   bash cyf/project/fe/verify-deploy.sh [站点地址]
#   bash cyf/project/fe/verify-deploy.sh https://preview.chat-h.cc
set -uo pipefail

SITE="${1:-https://chat-h.cc}"
SITE="${SITE%/}"
FAILED=0

echo "🔍 校验站点: $SITE"

# ── 1. 首页可达且返回 HTML ──
INDEX_HEADERS=$(curl -sSI --max-time 25 "$SITE/" 2>/dev/null || true)
INDEX_BODY=$(curl -sS --max-time 25 "$SITE/" 2>/dev/null || true)
if [ -z "$INDEX_BODY" ]; then
    echo "❌ 首页无法访问（网络错误或超时）"
    exit 1
fi

INDEX_TYPE=$(printf '%s' "$INDEX_HEADERS" | grep -i '^content-type:' | tail -1 | tr -d '\r')
INDEX_CC=$(printf '%s' "$INDEX_HEADERS" | grep -i '^cache-control:' | tail -1 | tr -d '\r')
echo "ℹ️  首页 ${INDEX_TYPE:-未知类型} | ${INDEX_CC:-无 Cache-Control}"

# ── 2. 逐个校验 HTML 引用的静态资源 ──
ASSETS=$(printf '%s' "$INDEX_BODY" | grep -oE '(src|href)="/assets/[^"]+"' | sed -E 's/.*"(\/assets\/[^"]+)"/\1/' | sort -u)
if [ -z "$ASSETS" ]; then
    echo "❌ 首页没有引用任何 /assets/ 资源，页面结构异常"
    exit 1
fi

TOTAL=0
while IFS= read -r asset; do
    [ -z "$asset" ] && continue
    TOTAL=$((TOTAL + 1))
    HEADERS=$(curl -sSI --max-time 25 "$SITE$asset" 2>/dev/null || true)
    STATUS=$(printf '%s' "$HEADERS" | head -1 | awk '{print $2}')
    TYPE=$(printf '%s' "$HEADERS" | grep -i '^content-type:' | tail -1 | tr -d '\r' | awk '{print $2}')
    if [ "$STATUS" != "200" ]; then
        echo "❌ $asset → HTTP $STATUS"
        FAILED=1
    elif [ "$TYPE" != "application/javascript" ] && [ "$TYPE" != "text/css" ]; then
        echo "❌ $asset → Content-Type: ${TYPE:-未知}（命中 SPA 回退，浏览器会缓存成错误资源）"
        FAILED=1
    fi
done <<< "$ASSETS"
echo "ℹ️  已校验 $TOTAL 个静态资源"

# ── 3. 检测 /assets/* 的缓存规则是否过激 ──
PROBE="/assets/__verify_missing_$(date +%s).js"
PROBE_HEADERS=$(curl -sSI --max-time 25 "$SITE$PROBE" 2>/dev/null || true)
PROBE_CC=$(printf '%s' "$PROBE_HEADERS" | grep -i '^cache-control:' | tail -1 | tr -d '\r')
MAX_AGE=$(printf '%s' "$PROBE_CC" | grep -oE 'max-age=[0-9]+' | cut -d= -f2)
if [ -n "$MAX_AGE" ] && [ "$MAX_AGE" -gt 3600 ]; then
    echo "❌ 缺失资源回退的 Cache-Control 为 $PROBE_CC"
    echo "   部署切换窗口期 miss 的请求会被浏览器长期缓存成 HTML，需缩短 /assets/* 的 max-age。"
    FAILED=1
else
    echo "ℹ️  缺失资源回退 | ${PROBE_CC:-无 Cache-Control}（窗口期影响可控）"
fi

if [ "$FAILED" = "0" ]; then
    echo "✅ 部署校验通过：$SITE"
else
    echo "❌ 部署校验未通过，见上方明细"
fi
exit "$FAILED"
