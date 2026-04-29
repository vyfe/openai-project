# Conversation V2 API 合同（后端B阶段）

## 通用
- 前缀：`/never_guess_my_usage/conversation`
- 认证：与现有接口一致（Bearer token 或兼容 user/password）
- 响应格式：
```json
{
  "success": true,
  "msg": "",
  "data": {}
}
```

## 1) 创建主会话
POST `/master/create`

请求：
```json
{
  "title": "多模型比较：提示词A",
  "session_type": "multi_compare",
  "active_models": ["gpt-4o-mini", "gpt-4o"]
}
```

响应（示例）：
```json
{
  "success": true,
  "msg": "",
  "data": {
    "master": {
      "id": 10,
      "owner": "alice",
      "title": "多模型比较：提示词A",
      "session_type": "multi_compare",
      "active_models": ["gpt-4o-mini", "gpt-4o"],
      "created_at": "2026-04-28 14:00:00",
      "updated_at": "2026-04-28 14:00:00"
    },
    "children": [
      {"child_id": 20, "master_id": 10, "model_id": "gpt-4o-mini", "status": "active"},
      {"child_id": 21, "master_id": 10, "model_id": "gpt-4o", "status": "active"}
    ]
  }
}
```

## 2) 主会话列表
POST `/master/list`

请求：
```json
{ "page": 1, "page_size": 20 }
```

响应：
```json
{
  "success": true,
  "msg": "",
  "data": {
    "list": [
      {
        "id": 10,
        "owner": "alice",
        "title": "多模型比较：提示词A",
        "session_type": "multi_compare",
        "active_models": ["gpt-4o-mini", "gpt-4o"],
        "active_model_count": 2,
        "created_at": "2026-04-28 14:00:00",
        "updated_at": "2026-04-28 14:02:00"
      }
    ],
    "pagination": {"page": 1, "page_size": 20, "has_more": false}
  }
}
```

## 3) 主会话详情
POST `/master/detail`

请求：
```json
{ "master_id": 10 }
```

响应：
```json
{
  "success": true,
  "msg": "",
  "data": {
    "master": {"id": 10, "title": "多模型比较：提示词A"},
    "children": [
      {"child_id": 20, "model_id": "gpt-4o-mini", "status": "active"},
      {"child_id": 21, "model_id": "gpt-4o", "status": "removed"}
    ],
    "rounds": [
      {"round_id": 30, "round_index": 1, "user_prompt": "你好", "attachments": []}
    ],
    "cells": [
      {
        "cell_id": 40,
        "round_id": 30,
        "child_id": 20,
        "assistant_output": "你好，我是...",
        "cell_status": "success",
        "error": null
      }
    ]
  }
}
```

## 4) 增加模型
POST `/master/add_model`

请求：
```json
{ "master_id": 10, "model_id": "gpt-3.5-turbo" }
```

响应：
```json
{
  "success": true,
  "msg": "",
  "data": {
    "child": {"child_id": 22, "model_id": "gpt-3.5-turbo", "status": "active"},
    "active_models": ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"]
  }
}
```

## 5) 移除模型（软删除）
POST `/master/remove_model`

请求：
```json
{ "master_id": 10, "model_id": "gpt-4o" }
```

响应：
```json
{
  "success": true,
  "msg": "",
  "data": {
    "child_id": 21,
    "model_id": "gpt-4o",
    "status": "removed",
    "active_models": ["gpt-4o-mini", "gpt-3.5-turbo"]
  }
}
```

## 6) 发送一轮并行请求
POST `/round/send`

请求：
```json
{
  "master_id": 10,
  "user_prompt": "请用三句话解释RAG",
  "attachments": [],
  "system_prompt_id": 12,
  "max_response_tokens": 1200
}
```

响应：
```json
{
  "success": true,
  "msg": "",
  "data": {
    "round": {"round_id": 31, "round_index": 2, "user_prompt": "请用三句话解释RAG"},
    "cells": [
      {"cell_id": 41, "child_id": 20, "cell_status": "success", "assistant_output": "..."},
      {"cell_id": 42, "child_id": 22, "cell_status": "failed", "error": {"msg": "..."}}
    ]
  }
}
```

## 7) 单元级重试
POST `/cell/retry`

请求：
```json
{
  "round_id": 31,
  "child_id": 22,
  "system_prompt_id": 12,
  "max_response_tokens": 1200
}
```

响应：
```json
{
  "success": true,
  "msg": "",
  "data": {
    "cell": {
      "cell_id": 42,
      "round_id": 31,
      "child_id": 22,
      "cell_status": "success",
      "assistant_output": "重试后的输出"
    }
  }
}
```
