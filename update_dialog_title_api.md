# 更新对话标题 API 接口文档

## 接口说明
更新指定对话的标题（会话名）。

## 接口地址
```
POST /never_guess_my_usage/update_dialog_title
```

## 请求参数
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| user | String | 是 | 用户名 |
| password | String | 是 | 用户密码 |
| dialog_id | Integer | 是 | 对话ID |
| new_title | String | 是 | 新的对话标题 |

## 响应格式
### 成功响应
```json
{
  "success": true,
  "msg": "对话标题更新成功"
}
```

### 失败响应
```json
{
  "success": false,
  "msg": "错误信息"
}
```

## 示例

### 请求示例
```bash
curl -X POST http://localhost:39997/never_guess_my_usage/update_dialog_title \
  -d "user=test_user" \
  -d "password=test_password" \
  -d "dialog_id=1" \
  -d "new_title=新的对话标题"
```

### 响应示例（成功）
```json
{
  "success": true,
  "msg": "对话标题更新成功"
}
```

## 注意事项
- 用户必须通过身份验证才能执行此操作
- 对话ID必须属于当前用户，否则操作会失败
- new_title 参数不能为空
- 此操作会更新数据库中对应的 dialog_name 字段