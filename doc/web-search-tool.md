# 网络搜索工具

## 工作方式

前端勾选“网络搜索”后，在聊天请求中携带 `enabled_tools: ["web_search"]`。服务端把
工具定义随同一次 Chat Completions / Claude Messages 请求发送给模型：

1. 模型判断是否需要联网；
2. 模型返回 `web_search` tool call；
3. 服务端本地 Python 脚本读取 DuckDuckGo HTML 搜索页，失败时回退 Bing HTML，并抓取公开网页正文；
4. 服务端把正文摘要和来源作为 `tool_result` 回传同一轮模型上下文；
5. 模型生成最终答案。

因此未勾选时仍是原有单次模型请求，勾选后也不会在模型请求前预先搜索。流式请求会额外发送
`tool_status` 和 `part(type=tool_result)` SSE 事件，搜索来源会随对话一起保存。

## 服务端配置

在 `cyf/project/server/conf/conf.ini` 增加（模板见 `conf/conf.ini.tpl`）：

```ini
[tools]
web_search_enabled=true
web_search_engines=duckduckgo,bing
# DuckDuckGo 区域：wt-wt（全球）、sg-en（新加坡）、cn-zh（中国）
web_search_duckduckgo_region=wt-wt
web_search_timeout_seconds=15
web_search_max_rounds=3
web_search_max_sources=5
web_search_max_page_chars=4000
web_search_max_context_chars=16000
web_search_max_download_bytes=1048576
```

该实现不调用 Google/Gemini 或其他搜索 API，不需要 API Key。只有用户勾选“网络搜索”且模型实际
发起 `web_search` tool call 时，服务端才访问公开搜索页和结果网页。它是服务端受控的本地工具，
不依赖模型的原生联网能力，因此 GPT、Claude 等模型都可使用；全局开关关闭时请求返回
`TOOL_NOT_AVAILABLE`。

可在 `cyf/project/server/` 下独立验证本地脚本：

```bash
../../../.venv/bin/python tools/local_web_search.py "OpenAI 最新消息"
```

脚本会拒绝 localhost、内网、链路本地及保留地址；逐次校验重定向，并限制单页下载量、
单页正文长度与总上下文长度。公开搜索页可能触发搜索引擎的限流或验证码，执行器会按配置顺序回退。
DuckDuckGo HTML 返回挑战页时，会使用带浏览器请求头和区域参数的 Lite 页面再尝试一次；仍失败才继续
回退到下一个搜索引擎。该逻辑不绕过验证码，也不做代理轮换。

## 运行日志定位

工具日志写入 `logs/llm/app.log`，并通过请求上下文自动带上同一个 `request_id`。搜索和网页抓取
只记录摘要，不记录完整 HTML 或查询参数：

- `本地搜索开始`：本次查询、搜索引擎、超时和来源上限。
- `本地搜索结果解析`：HTTP 状态、响应地址、Content-Type、正文长度、页面标记和 `parsed_count`。
- `搜索结果网页响应`：结果页状态、重定向次数和正文长度。
- `搜索结果正文解析`：正文提取长度及是否被采纳为来源。
- `本地搜索失败汇总`：所有引擎都失败时的最终错误。
- `本地搜索结果汇总`：搜索结果数、候选数和最终来源数。

线上可使用以下命令定位：

```bash
grep -n -E '本地搜索结果解析|本地搜索失败汇总' logs/llm/app.log
grep -n -E '搜索结果网页响应|搜索结果正文解析|搜索结果正文抓取失败' logs/llm/app.log
grep -n 'split_stream' logs/llm/access.log | grep -E 'enabled_tools|英维克|\\u82f1\\u7ef4\\u514b'
```

`parsed_count=0` 且 `status=2xx` 表示搜索请求已返回，但当前 HTML 未匹配到 DuckDuckGo/Bing
结果节点；`markers` 可辅助判断是否返回了验证码、挑战或同意页面。若日志已轮转，使用
`zgrep` 查询对应的 `.gz` 文件。

## 协议示例

非流式请求：

```json
{
  "model": "gpt-4o",
  "dialog": "今天的 AI 行业要闻有哪些？",
  "enabled_tools": ["web_search"]
}
```

工具结果统一保存为：

```json
{
  "type": "tool_result",
  "name": "web_search",
  "text": "搜索摘要",
  "data": {"sources": [{"title": "来源标题", "url": "https://example.com"}]}
}
```

后续扩展工具只需在 `service/tools/` 增加适配器，在注册表中加入定义与执行入口，再补充
OpenAI/Claude 的 provider schema；不会改动聊天路由的主流程。
