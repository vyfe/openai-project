# 通知公告API接口文档

## 功能概述
新增通知公告管理功能，支持通知的创建、查询、更新、删除等操作，包括通知标题、内容、发布时间、优先级等字段。

## 数据模型

### Notification模型字段
- `id`: 主键ID
- `title`: 通知标题 (必填)
- `content`: 通知内容 (必填)
- `publish_time`: 发布时间 (默认当前时间)
- `status`: 状态 (active-有效, inactive-无效, 默认active)
- `priority`: 优先级 (数字越大优先级越高, 默认0)
- `created_at`: 创建时间
- `updated_at`: 更新时间

## API接口列表

### 1. 获取通知列表
- **URL**: `/notification/list`
- **方法**: GET
- **认证**: 需要管理员认证
- **参数**:
  - `user`: 管理员用户名 (必填)
  - `password`: 管理员密码 (必填)
  - `status`: 状态过滤 (可选, active/inactive)
  - `limit`: 限制数量 (可选)
  - `offset`: 偏移量 (可选)
- **返回**: 通知列表数据

### 2. 获取有效通知列表（无需认证）
- **URL**: `/notification/active_list`
- **方法**: GET
- **认证**: 无需认证
- **参数**:
  - `limit`: 限制数量 (可选, 默认10)
- **返回**: 有效通知列表数据

### 3. 获取单个通知
- **URL**: `/notification/get/<notification_id>`
- **方法**: GET
- **认证**: 需要管理员认证
- **参数**:
  - `user`: 管理员用户名 (必填)
  - `password`: 管理员密码 (必填)
- **返回**: 单个通知详细信息

### 4. 创建通知
- **URL**: `/notification/create`
- **方法**: POST
- **认证**: 需要管理员认证
- **参数**:
  - `user`: 管理员用户名 (必填)
  - `password`: 管理员密码 (必填)
  - `title`: 通知标题 (必填)
  - `content`: 通知内容 (必填)
  - `priority`: 优先级 (可选, 默认0)
  - `status`: 状态 (可选, 默认active)
- **返回**: 创建成功的通知数据

### 5. 更新通知
- **URL**: `/notification/update`
- **方法**: POST
- **认证**: 需要管理员认证
- **参数**:
  - `user`: 管理员用户名 (必填)
  - `password`: 管理员密码 (必填)
  - `id`: 通知ID (必填)
  - `title`: 通知标题 (可选)
  - `content`: 通知内容 (可选)
  - `priority`: 优先级 (可选)
  - `status`: 状态 (可选, active/inactive)
- **返回**: 更新成功的通知数据

### 6. 删除通知
- **URL**: `/notification/delete`
- **方法**: POST
- **认证**: 需要管理员认证
- **参数**:
  - `user`: 管理员用户名 (必填)
  - `password`: 管理员密码 (必填)
  - `id`: 通知ID (必填)
- **返回**: 删除成功消息

## 使用示例

### 创建通知
```bash
curl -X POST "http://localhost:39998/notification/create" \
  -d "user=admin&password=admin123&title=系统维护通知&content=系统将于今晚进行维护&priority=5&status=active"
```

### 获取通知列表
```bash
curl "http://localhost:39998/notification/list?user=admin&password=admin123&status=active"
```

### 获取有效通知（无需认证）
```bash
curl "http://localhost:39998/notification/active_list?limit=5"
```

### 更新通知
```bash
curl -X POST "http://localhost:39998/notification/update" \
  -d "user=admin&password=admin123&id=1&title=更新后的标题&priority=8"
```

### 删除通知
```bash
curl -X POST "http://localhost:39998/notification/delete" \
  -d "user=admin&password=admin123&id=1"
```

## 测试脚本
提供了完整的测试脚本 [`test_notification_api.py`](test_notification_api.py)，可以运行该脚本来验证所有接口功能：

```bash
python test_notification_api.py
```

## 数据库初始化
通知公告功能会自动在数据库中创建 `notification` 表，无需手动创建。如果数据库已存在，运行时会自动添加新表。

## 注意事项
1. 除了 `/notification/active_list` 接口外，其他接口都需要管理员认证
2. 状态字段只能是 `active` 或 `inactive`
3. 优先级字段为整数，数字越大表示优先级越高
4. 发布时间字段在创建时自动设置为当前时间
5. 删除操作是永久删除，请谨慎操作