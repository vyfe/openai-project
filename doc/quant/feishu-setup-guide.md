# 量化助手 - 飞书机器人注册与配置指南

本文档指引你从零开始在飞书开放平台注册企业自建应用、获取配置密钥、订阅消息事件，并最终在群聊或私聊中使用量化助手机器人。

---

## 1. 注册飞书企业

如果你还没有飞书企业帐号，需要先创建一个：

1. 打开 [飞书官网](https://www.feishu.cn)，点击「注册」。
2. 使用手机号或邮箱注册一个飞书企业。
   - 如果是个人开发者，注册「**个人开发者企业**」即可（免费，功能与标准企业一致）。
3. 注册完成后，登录飞书客户端（桌面端或移动端），确认可以正常进入你的企业。

> 如果已有飞书企业帐号，跳过此步骤。

---

## 2. 创建企业自建应用

1. 打开 [飞书开放平台](https://open.feishu.cn)。
2. 登录后，点击顶部导航栏的「**开发者后台**」或直接访问 [https://open.feishu.cn/app](https://open.feishu.cn/app)。
3. 点击「**创建企业自建应用**」按钮。
4. 填写应用名称（例如「量化助手」）、应用描述，上传图标。
5. 创建完成后，进入应用详情页。

---

## 3. 获取应用凭证

在应用详情页左侧菜单「**凭证与基础信息**」中，找到以下关键信息：

| 字段 | 说明 | 对应 `conf.ini` 配置项 |
|---|---|---|
| **App ID** | 应用唯一标识，格式如 `cli_xxxxxxxxxxxx` | `feishu_app_id` |
| **App Secret** | 应用密钥，用于获取 tenant access token | `feishu_app_secret` |
| **Verification Token** | 事件订阅验证 Token | `feishu_verification_token` |

> 如果你启用了事件加密，还需要 **Encrypt Key** → 对应 `feishu_encrypt_key`。

### 填入配置文件

将这些值填入 `cyf/project/server/conf/conf.ini` 的 `[quant]` 段。**你的 `conf.ini` 目前缺少 `[quant]` 段**，需要新增以下内容：

```ini
[quant]
sqlite3_file=./quant.db
bundle_dir=./quant_bundles
memory_dir=./quant_memory
feishu_app_id=cli_xxxxxxxxxxxx
feishu_app_secret=xxxxxxxxxxxxxxxxxxxxxxxxxx
feishu_verification_token=xxxxxxxxxxxxxxxx
feishu_encrypt_key=
```

> 如果暂时没有飞书密钥，可以先填占位符，等后续再填入真实值。其他量化功能不受影响。

---

## 4. 开启机器人能力

1. 在应用详情页左侧菜单点击「**添加应用能力**」→ 找到「**机器人**」→ 点击「**添加**」。
2. 添加后，左侧菜单会出现「**机器人**」配置项，可以设置：
   - 机器人名称（群聊里显示的名字，如「量化小助手」）
   - 机器人图标
   - 机器人描述
3. 保存配置。

---

## 5. 配置事件订阅

### 5.1 订阅消息事件

1. 在应用详情页左侧菜单点击「**事件订阅**」。
2. （可选）加密策略建议先选「**明文模式**」，后续可再启用加密。
3. 设置「**请求地址**」为：

   ```
   https://你的域名/never_guess_my_usage/quant/im/feishu/events
   ```

   > 本地开发时，需要用 **ngrok**、**frp** 等内网穿透工具将本地 `39997` 端口暴露为公网 HTTPS 地址。

4. 在「**添加事件**」中搜索并勾选：

   | 事件名 | 用途 |
   |---|---|
   | `im.message.receive_v1` | 接收用户发送给机器人的消息 |

5. 点击「**保存**」。飞书会向你的回调地址发送 URL 验证请求，**需要后端服务已在运行**才能通过验证。

### 5.2 权限配置

在左侧菜单「**权限管理**」中，确保已添加以下权限（通常在添加机器人能力后自动获取）：

- `im:message` - 获取与发送消息
- `im:message:send_as_bot` - 以机器人身份发送消息

---

## 6. 发布应用与添加到聊天

### 6.1 发布应用

1. 在应用详情页左侧菜单点击「**版本管理与发布**」。
2. 点击右上角「**创建版本**」，填写版本号（如 `1.0.0`）和更新说明。
3. 提交后由企业管理员审核（个人开发者企业可自行通过）。
4. 审核通过后点击「**发布**」。

### 6.2 添加到群聊

1. 进入你想添加机器人的飞书群聊。
2. 群聊右上角「**设置**」→「**群机器人**」→「**添加机器人**」。
3. 搜索你的应用名称 → 点击「**添加**」。

### 6.3 私聊使用

直接在飞书客户端搜索框搜索你的机器人应用名称，打开对话窗口即可私聊。

---

## 7. 获取群聊 / 对话 ID

机器人与群聊交互需要群聊的 `chat_id`。获取方式：

### 方法一：从数据库查看

在群聊中 @机器人 发一条消息，然后查询数据库：

```sql
SELECT DISTINCT chat_id FROM quant_im_inbound_event ORDER BY received_at DESC LIMIT 10;
```

### 方法二：通过飞书 API

调用飞书开放平台 [获取机器人所在群列表](https://open.feishu.cn/document/server-docs/im-v1/chat/list) API。

### ID 格式说明

| 类型 | 前缀 | 示例 |
|---|---|---|
| 群聊 ID | `oc_` | `oc_1234567890abcdef` |
| 用户 ID（私聊） | `ou_` | `ou_1234567890abcdef` |

---

## 8. 创建 IM 通道（将机器人与群聊绑定）

在量化工作台的「**IM 与持仓**」页面中创建通道，或直接调用 API：

```bash
curl -X POST http://localhost:39997/never_guess_my_usage/quant/im/channels \
  -H "Authorization: Bearer YOUR_LOGIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "量化群-主力",
    "channel_type": "feishu_app",
    "config": {
      "receive_id": "oc_xxxxxxxxxxxxxxxxx",
      "receive_id_type": "chat_id",
      "reply_in_thread": false
    }
  }'
```

### 通道配置字段说明

| 参数 | 必填 | 说明 |
|---|---|---|
| `name` | 是 | 通道名称，自定义 |
| `channel_type` | 是 | 固定 `feishu_app`（目前仅支持飞书） |
| `config.receive_id` | 是 | 群聊 ID（`oc_xxx`）或用户 ID（`ou_xxx`） |
| `config.receive_id_type` | 是 | `chat_id` / `open_id` / `user_id` / `union_id` / `email` |
| `config.inbound_chat_id` | 否 | 入站消息匹配的 chat_id，默认同 `receive_id` |
| `config.reply_in_thread` | 否 | 回复是否以话题形式（`true`/`false`），默认 `false` |
| `mention_list` | 否 | 推送报告时 @ 的用户列表 |

---

## 9. 使用机器人——支持的命令

### 触发规则

| 场景 | 何时响应 |
|---|---|
| **私聊**（P2P/Private） | 任何消息都响应 |
| **群聊** | 仅当 **@机器人** 时响应 |

### 命令一览

| 命令 | 功能 |
|---|---|
| `帮助` / `help` / `菜单` / `说明` | 查看所有可用命令 |
| `持仓` / `position` / `仓位` / `持仓摘要` | 返回当前持仓快照摘要 |
| `报告` / `report` / `日报` / `最新报告` | 返回最近一份量化分析报告 |
| `买入 600519 100 1688 备注` | 登记一条买入持仓流水 |
| `卖出 000001 200 12.50 备注` | 登记一条卖出持仓流水 |

### 买入/卖出命令格式

```
[买入/卖出/buy/sell] [股票代码] [数量] [价格(可选)] [备注(可选)]
```

示例：

- `买入 600519 100 1688 长期持有`
- `卖出 000001 200`
- `buy 600519 100 1688`

---

## 10. 调度推送（自动推送报告到飞书）

配置好 IM 通道后，定时调度任务 `analysis_report` 会在执行后将报告自动推送到所有活跃的飞书通道。

确保 `conf.ini` 的 `[quant]` 段和 IM 通道配置正确后，无需额外操作即可自动推送。

---

## 11. 验证链路是否通畅

按以下顺序逐项验证：

1. **启动后端服务**
   ```bash
   cd cyf/project/server && ./local-run.sh
   ```

2. **验证事件回调 URL**
   - 在飞书开放平台「事件订阅」页面点击「保存」
   - 确认提示「请求地址配置成功」

3. **发送测试消息**
   - 在「IM 与持仓」页面点击通道的「发送测试消息」
   - 确认飞书中收到测试消息

4. **群聊 @ 测试**
   - 在目标群聊中 @机器人 发送「帮助」
   - 确认收到命令列表回复

5. **私聊测试**
   - 在飞书搜索机器人名称，直接发「持仓」
   - 确认收到持仓摘要

---

## 12. 常见问题

**Q: 事件订阅 URL 验证失败？**

A: 后端服务必须已启动且公网可访问。本地开发需使用 ngrok 等内网穿透工具，命令示例：
```bash
ngrok http 39997
```
然后将 ngrok 提供的 HTTPS 地址 + `/never_guess_my_usage/quant/im/feishu/events` 填入飞书后台。

**Q: 群聊中 @机器人 没反应？**

A: 检查三项：
1. 事件订阅是否已保存成功（URL 验证通过）
2. IM 通道的 `receive_id` 是否与该群聊 ID 匹配
3. 通道状态是否为 `active`

**Q: `conf.ini` 没有 `[quant]` 段怎么办？**

A: 手动添加（参考本文档第 3 节）。即使暂时没有飞书密钥，也可以先填入占位符，其他量化功能不受影响。

**Q: 报告推送收不到？**

A: 检查调度任务 `analysis_report` 是否正确执行，以及 IM 通道配置的 `receive_id` 是否正确。

