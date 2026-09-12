# 网络搜索工具

## 工作方式

前端勾选“网络搜索”后，在聊天请求中携带 `enabled_tools: ["web_search"]`。服务端把
工具定义随同一次 Chat Completions / Claude Messages 请求发送给模型：

1. 模型判断是否需要联网；
2. 模型返回 `web_search` tool call；
3. 服务端调用 Google Gemini Interactions API 的 `google_search`（传入 URL 时同时使用 `url_context`）；
4. 服务端把摘要和来源作为 `tool_result` 回传同一轮模型上下文；
5. 模型生成最终答案。

因此未勾选时仍是原有单次模型请求，勾选后也不会在模型请求前预先搜索。流式请求会额外发送
`tool_status` 和 `part(type=tool_result)` SSE 事件，搜索来源会随对话一起保存。

## 服务端配置

在 `cyf/project/server/conf/conf.ini` 增加（模板见 `conf/conf.ini.tpl`）：

```ini
[tools]
google_web_search_enabled=true
google_web_search_api_key=<Google Gemini API Key>
google_web_search_model=gemini-2.5-flash
google_web_search_base_url=https://generativelanguage.googleapis.com/v1beta
google_web_search_timeout_seconds=30
google_web_search_max_rounds=3
google_web_search_max_sources=8
```

API Key 只在服务端使用，不下发浏览器。服务端默认关闭工具；未配置 Key 或模型元数据显式
`allow_net=false` 时，勾选请求会返回 `TOOL_NOT_AVAILABLE`，不会调用上游模型。

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
