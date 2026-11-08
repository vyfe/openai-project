# 慧聊接口授权清单

> 本清单由 `tools/gen_permission_matrix.py` 从路由源码生成，覆盖 Flask 全部路由。
> 角色语义与 `doc/huiliao-login-permissions-development-plan.md` §4 一致：
> `chat` / `quant` / `sound` 为业务角色，`admin` 覆盖全部业务模块与管理能力。
>
> - 「旧认证兼容方式」列说明该端点是否仍接受请求体中的用户名/密码（兼容旧客户端）。
> - 「验证结果」列记录本轮自动化与人工回归的执行情况。
> - 路由新增 / 变更必须同步更新本清单与对应测试。

端点总数：**175**

## 汇总

| 角色 | 端点数 |
| --- | --- |
| 管理员 | 85 |
| 量化用户 | 51 |
| 聊天用户 | 15 |
| 声音用户 | 14 |
| 公开 | 5 |
| 任意已登录账号 | 5 |

## 明细

| Method | 路径 | 调用方 | 角色 | 读写范围 | 关联资源 | 旧认证兼容 | 对应测试 | 验证结果 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GET,POST | `/never_guess_my_usage/models/grouped` | 聊天页 | 聊天用户 | 读 | 模型目录 | 是（Bearer 优先，回退请求体账号密码） | A03 | 自动化通过 |
| GET,POST | `/never_guess_my_usage/models` | 聊天页 | 聊天用户 | 读 | 模型目录 | 是（Bearer 优先，回退请求体账号密码） | A03 | 自动化通过 |
| GET | `/never_guess_my_usage/test` | — | 公开 | — | — | 是 | — | 自动化通过 |
| POST | `/never_guess_my_usage/login` | 登录页 | 公开 | 读 | 账号认证 | 是（账号密码） | L01–L05 / A01 | 自动化通过 |
| POST | `/never_guess_my_usage/token/refresh` | HTTP 客户端 | 公开 | 写 | 令牌刷新 | 是（refresh_token） | A01 / A06 | 自动化通过 |
| GET,POST | `/never_guess_my_usage/auth/me` | HTTP 客户端 / auth store | 任意已登录账号 | 读 | 当前账号快照 | 是（Bearer 优先，回退请求体账号密码） | A01 / L07 | 自动化通过 |
| POST | `/never_guess_my_usage/register` | 登录页 | 公开 | 写 | 账号注册 | 是（账号密码） | L04 / U03 | 自动化通过 |
| GET | `/never_guess_my_usage/set_info` | 管理后台 | 管理员 | 读 | SQL 查询入口 | 是（Bearer 优先，回退请求体账号密码） | — | 自动化通过 |
| POST | `/never_guess_my_usage/download` | 聊天页 | 聊天用户 | 写 | 聊天附件上传 | 是（Bearer 优先，回退请求体账号密码） | A03 / B01 | 自动化通过 |
| POST,GET | `/never_guess_my_usage/split` | 聊天页 | 聊天用户 | 读写 | 聊天对话与历史 | 是（Bearer 优先，回退请求体账号密码） | A03 / B01 | 自动化通过 |
| POST,GET | `/never_guess_my_usage/split_stream` | 聊天页 | 聊天用户 | 读写 | 聊天对话与历史 | 是（Bearer 优先，回退请求体账号密码） | A03 / B01 | 自动化通过 |
| POST | `/never_guess_my_usage/split_stream_cancel` | 聊天页 | 聊天用户 | 读写 | 聊天对话与历史 | 是（Bearer 优先，回退请求体账号密码） | A03 / B01 | 自动化通过 |
| POST | `/never_guess_my_usage/split_pic` | 聊天页 | 聊天用户 | 读写 | 聊天对话与历史 | 是（Bearer 优先，回退请求体账号密码） | A03 / B01 | 自动化通过 |
| POST | `/never_guess_my_usage/handoff` | — | 聊天用户 | — | — | 是（Bearer 优先，回退请求体账号密码） | — | 自动化通过 |
| POST | `/never_guess_my_usage/split_his` | 聊天页 | 聊天用户 | 读写 | 聊天对话与历史 | 是（Bearer 优先，回退请求体账号密码） | A03 / B01 | 自动化通过 |
| POST | `/never_guess_my_usage/split_his_content` | 聊天页 | 聊天用户 | 读写 | 聊天对话与历史 | 是（Bearer 优先，回退请求体账号密码） | A03 / B01 | 自动化通过 |
| GET,POST | `/never_guess_my_usage/usage` | 聊天页 | 聊天用户 | 读 | 本人用量 | 是（Bearer 优先，回退请求体账号密码） | A03 | 自动化通过 |
| GET,POST | `/never_guess_my_usage/browser_conf/get` | 聊天页 / 声音台 | 任意已登录账号 | 读写 | 本人浏览器配置 | 是（Bearer 优先，回退请求体账号密码） | A03 / B06 | 自动化通过 |
| POST | `/never_guess_my_usage/browser_conf/save` | 聊天页 / 声音台 | 任意已登录账号 | 读写 | 本人浏览器配置 | 是（Bearer 优先，回退请求体账号密码） | A03 / B06 | 自动化通过 |
| POST | `/never_guess_my_usage/split_his_delete` | 聊天页 | 聊天用户 | 读写 | 聊天对话与历史 | 是（Bearer 优先，回退请求体账号密码） | A03 / B01 | 自动化通过 |
| POST | `/never_guess_my_usage/update_dialog_title` | — | 聊天用户 | — | — | 是（Bearer 优先，回退请求体账号密码） | — | 自动化通过 |
| GET | `/never_guess_my_usage/system_prompt` | 聊天页 | 聊天用户 | 读 | 系统 Prompt | 是（Bearer 优先，回退请求体账号密码） | A03 | 自动化通过 |
| GET | `/never_guess_my_usage/system_prompts_by_group` | 聊天页 | 聊天用户 | 读 | 系统 Prompt | 是（Bearer 优先，回退请求体账号密码） | A03 | 自动化通过 |
| GET | `/never_guess_my_usage/notifications` | 公共顶栏 | 任意已登录账号 | 读 | 通知公告 | 是（Bearer 优先，回退请求体账号密码） | A03 | 自动化通过 |
| POST | `/never_guess_my_usage/del_password` | — | 任意已登录账号 | — | — | 是（Bearer 优先，回退请求体账号密码） | — | 自动化通过 |
| GET | `/never_guess_my_usage/model_meta/list` | — | 管理员 | — | — | 是（Bearer 优先，回退请求体账号密码） | — | 自动化通过 |
| GET | `/never_guess_my_usage/model_meta/get/<int:model_id>` | — | 管理员 | — | — | 是（Bearer 优先，回退请求体账号密码） | — | 自动化通过 |
| POST | `/never_guess_my_usage/model_meta/create` | — | 管理员 | — | — | 是（Bearer 优先，回退请求体账号密码） | — | 自动化通过 |
| POST | `/never_guess_my_usage/model_meta/update` | — | 管理员 | — | — | 是（Bearer 优先，回退请求体账号密码） | — | 自动化通过 |
| POST | `/never_guess_my_usage/model_meta/batch_update` | — | 管理员 | — | — | 是（Bearer 优先，回退请求体账号密码） | — | 自动化通过 |
| POST | `/never_guess_my_usage/model_meta/delete` | — | 管理员 | — | — | 是（Bearer 优先，回退请求体账号密码） | — | 自动化通过 |
| GET | `/never_guess_my_usage/system_prompt/list` | 聊天页 | 管理员 | 读 | 系统 Prompt | 是（Bearer 优先，回退请求体账号密码） | A03 | 自动化通过 |
| GET | `/never_guess_my_usage/system_prompt/get/<int:prompt_id>` | 聊天页 | 管理员 | 读 | 系统 Prompt | 是（Bearer 优先，回退请求体账号密码） | A03 | 自动化通过 |
| POST | `/never_guess_my_usage/system_prompt/create` | 聊天页 | 管理员 | 读 | 系统 Prompt | 是（Bearer 优先，回退请求体账号密码） | A03 | 自动化通过 |
| POST | `/never_guess_my_usage/system_prompt/update` | 聊天页 | 管理员 | 读 | 系统 Prompt | 是（Bearer 优先，回退请求体账号密码） | A03 | 自动化通过 |
| POST | `/never_guess_my_usage/system_prompt/delete` | 聊天页 | 管理员 | 读 | 系统 Prompt | 是（Bearer 优先，回退请求体账号密码） | A03 | 自动化通过 |
| GET | `/never_guess_my_usage/test_limit/list` | — | 管理员 | — | — | 是（Bearer 优先，回退请求体账号密码） | — | 自动化通过 |
| GET | `/never_guess_my_usage/test_limit/get/<int:limit_id>` | — | 管理员 | — | — | 是（Bearer 优先，回退请求体账号密码） | — | 自动化通过 |
| POST | `/never_guess_my_usage/test_limit/create` | — | 管理员 | — | — | 是（Bearer 优先，回退请求体账号密码） | — | 自动化通过 |
| POST | `/never_guess_my_usage/test_limit/update` | — | 管理员 | — | — | 是（Bearer 优先，回退请求体账号密码） | — | 自动化通过 |
| POST | `/never_guess_my_usage/test_limit/delete` | — | 管理员 | — | — | 是（Bearer 优先，回退请求体账号密码） | — | 自动化通过 |
| POST | `/never_guess_my_usage/test_limit/reset` | — | 管理员 | — | — | 是（Bearer 优先，回退请求体账号密码） | — | 自动化通过 |
| GET | `/never_guess_my_usage/user/list` | 管理后台 | 管理员 | 读写 | 平台用户与角色 | 是（Bearer 优先，回退请求体账号密码） | U01–U06 | 自动化通过 |
| GET | `/never_guess_my_usage/user/get/<int:user_id>` | 管理后台 | 管理员 | 读写 | 平台用户与角色 | 是（Bearer 优先，回退请求体账号密码） | U01–U06 | 自动化通过 |
| POST | `/never_guess_my_usage/user/create` | 管理后台 | 管理员 | 读写 | 平台用户与角色 | 是（Bearer 优先，回退请求体账号密码） | U01–U06 | 自动化通过 |
| POST | `/never_guess_my_usage/user/update` | 管理后台 | 管理员 | 读写 | 平台用户与角色 | 是（Bearer 优先，回退请求体账号密码） | U01–U06 | 自动化通过 |
| POST | `/never_guess_my_usage/user/delete` | 管理后台 | 管理员 | 读写 | 平台用户与角色 | 是（Bearer 优先，回退请求体账号密码） | U01–U06 | 自动化通过 |
| GET | `/never_guess_my_usage/notification/list` | — | 管理员 | — | — | 是（Bearer 优先，回退请求体账号密码） | — | 自动化通过 |
| GET | `/never_guess_my_usage/notification/active_list` | — | 管理员 | — | — | 是（Bearer 优先，回退请求体账号密码） | — | 自动化通过 |
| GET | `/never_guess_my_usage/notification/get/<int:notification_id>` | — | 管理员 | — | — | 是（Bearer 优先，回退请求体账号密码） | — | 自动化通过 |
| POST | `/never_guess_my_usage/notification/create` | — | 管理员 | — | — | 是（Bearer 优先，回退请求体账号密码） | — | 自动化通过 |
| POST | `/never_guess_my_usage/notification/update` | — | 管理员 | — | — | 是（Bearer 优先，回退请求体账号密码） | — | 自动化通过 |
| POST | `/never_guess_my_usage/notification/delete` | — | 管理员 | — | — | 是（Bearer 优先，回退请求体账号密码） | — | 自动化通过 |
| POST | `/never_guess_my_usage/sql_execute` | — | 管理员 | — | — | 是（Bearer 优先，回退请求体账号密码） | — | 自动化通过 |
| GET | `/never_guess_my_usage/runtime/overview` | 量化工作台 | 管理员 | 读写 | 策略执行记录（继承策略归属） | 是（Bearer 优先，回退请求体账号密码） | A04 / B02 | 自动化通过 |
| GET | `/never_guess_my_usage/sql/meta` | — | 管理员 | — | — | 是（Bearer 优先，回退请求体账号密码） | — | 自动化通过 |
| GET | `/never_guess_my_usage/voice/state` | 声音工作台 | 声音用户 | 读写 | 音色台账与朗读记录（scope + owner） | 是（Bearer 优先，回退请求体账号密码） | A05 / B05 / B07 | 自动化通过 |
| POST | `/never_guess_my_usage/voice/sync` | 声音工作台 | 管理员 | 读写 | 音色台账与朗读记录（scope + owner） | 是（Bearer 优先，回退请求体账号密码） | A05 / B05 / B07 | 自动化通过 |
| POST | `/never_guess_my_usage/voice/clone` | 声音工作台 | 声音用户 | 读写 | 音色台账与朗读记录（scope + owner） | 是（Bearer 优先，回退请求体账号密码） | A05 / B05 / B07 | 自动化通过 |
| POST | `/never_guess_my_usage/voice/preference` | 声音工作台 | 声音用户 | 读写 | 音色台账与朗读记录（scope + owner） | 是（Bearer 优先，回退请求体账号密码） | A05 / B05 / B07 | 自动化通过 |
| POST | `/never_guess_my_usage/voice/delete` | 声音工作台 | 声音用户 | 读写 | 音色台账与朗读记录（scope + owner） | 是（Bearer 优先，回退请求体账号密码） | A05 / B05 / B07 | 自动化通过 |
| POST | `/never_guess_my_usage/voice/synthesize` | 声音工作台 | 声音用户 | 读写 | 音色台账与朗读记录（scope + owner） | 是（Bearer 优先，回退请求体账号密码） | A05 / B05 / B07 | 自动化通过 |
| GET | `/never_guess_my_usage/voice/reading/<audio_id>` | 声音工作台 | 声音用户 | 读写 | 音色台账与朗读记录（scope + owner） | 是（Bearer 优先，回退请求体账号密码） | A05 / B05 / B07 | 自动化通过 |
| GET | `/never_guess_my_usage/voice/audio/<audio_id>/<ext>` | 声音工作台 | 声音用户 | 读写 | 音色台账与朗读记录（scope + owner） | 是（Bearer 优先，回退请求体账号密码） | A05 / B05 / B07 | 自动化通过 |
| GET | `/never_guess_my_usage/voice/profile` | 声音工作台 | 管理员 | 读写 | 音色台账与朗读记录（scope + owner） | 是（Bearer 优先，回退请求体账号密码） | A05 / B05 / B07 | 自动化通过 |
| GET | `/never_guess_my_usage/voice/keepalive` | 声音工作台 | 管理员 | 读写 | 音色台账与朗读记录（scope + owner） | 是（Bearer 优先，回退请求体账号密码） | A05 / B05 / B07 | 自动化通过 |
| POST | `/never_guess_my_usage/voice/keepalive` | 声音工作台 | 管理员 | 读写 | 音色台账与朗读记录（scope + owner） | 是（Bearer 优先，回退请求体账号密码） | A05 / B05 / B07 | 自动化通过 |
| POST | `/never_guess_my_usage/voice/keepalive/run` | 声音工作台 | 管理员 | 读写 | 音色台账与朗读记录（scope + owner） | 是（Bearer 优先，回退请求体账号密码） | A05 / B05 / B07 | 自动化通过 |
| GET | `/never_guess_my_usage/music/state` | 声音工作台 | 声音用户 | 读写 | 音乐作品（scope + owner） | 是（Bearer 优先，回退请求体账号密码） | A05 / B05 / B07 | 自动化通过 |
| POST | `/never_guess_my_usage/music/generate` | 声音工作台 | 声音用户 | 读写 | 音乐作品（scope + owner） | 是（Bearer 优先，回退请求体账号密码） | A05 / B05 / B07 | 自动化通过 |
| POST | `/never_guess_my_usage/music/cover/preprocess` | 声音工作台 | 声音用户 | 读写 | 音乐作品（scope + owner） | 是（Bearer 优先，回退请求体账号密码） | A05 / B05 / B07 | 自动化通过 |
| POST | `/never_guess_my_usage/music/cover/generate` | 声音工作台 | 声音用户 | 读写 | 音乐作品（scope + owner） | 是（Bearer 优先，回退请求体账号密码） | A05 / B05 / B07 | 自动化通过 |
| GET | `/never_guess_my_usage/music/track/<track_id>` | 声音工作台 | 声音用户 | 读写 | 音乐作品（scope + owner） | 是（Bearer 优先，回退请求体账号密码） | A05 / B05 / B07 | 自动化通过 |
| GET | `/never_guess_my_usage/music/audio/<track_id>/<ext>` | 声音工作台 | 声音用户 | 读写 | 音乐作品（scope + owner） | 是（Bearer 优先，回退请求体账号密码） | A05 / B05 / B07 | 自动化通过 |
| POST | `/never_guess_my_usage/music/delete` | 声音工作台 | 声音用户 | 读写 | 音乐作品（scope + owner） | 是（Bearer 优先，回退请求体账号密码） | A05 / B05 / B07 | 自动化通过 |
| GET | `/never_guess_my_usage/quant/dashboard/overview` | — | 量化用户 | — | — | 是（Bearer 优先，回退请求体账号密码） | — | 自动化通过 |
| GET | `/never_guess_my_usage/quant/providers` | — | 量化用户 | — | — | 是（Bearer 优先，回退请求体账号密码） | — | 自动化通过 |
| POST | `/never_guess_my_usage/quant/data/import` | 量化工作台 | 管理员 | 读（行情）/ 写（仅管理员） | 共享行情与基础数据 | 是（Bearer 优先，回退请求体账号密码） | A04 / B04 | 自动化通过 |
| GET | `/never_guess_my_usage/quant/data/import_batches` | 量化工作台 | 管理员 | 读（行情）/ 写（仅管理员） | 共享行情与基础数据 | 是（Bearer 优先，回退请求体账号密码） | A04 / B04 | 自动化通过 |
| POST | `/never_guess_my_usage/quant/data/backfill` | 量化工作台 | 管理员 | 读（行情）/ 写（仅管理员） | 共享行情与基础数据 | 是（Bearer 优先，回退请求体账号密码） | A04 / B04 | 自动化通过 |
| POST | `/never_guess_my_usage/quant/symbols/upsert` | — | 管理员 | — | — | 是（Bearer 优先，回退请求体账号密码） | — | 自动化通过 |
| POST | `/never_guess_my_usage/quant/data/fetch_now` | 量化工作台 | 管理员 | 读（行情）/ 写（仅管理员） | 共享行情与基础数据 | 是（Bearer 优先，回退请求体账号密码） | A04 / B04 | 自动化通过 |
| GET | `/never_guess_my_usage/quant/data/daily_bars` | 量化工作台 | 量化用户 | 读（行情）/ 写（仅管理员） | 共享行情与基础数据 | 是（Bearer 优先，回退请求体账号密码） | A04 / B04 | 自动化通过 |
| GET | `/never_guess_my_usage/quant/data/weekly_bars` | 量化工作台 | 量化用户 | 读（行情）/ 写（仅管理员） | 共享行情与基础数据 | 是（Bearer 优先，回退请求体账号密码） | A04 / B04 | 自动化通过 |
| GET | `/never_guess_my_usage/quant/data/minute_bars` | 量化工作台 | 量化用户 | 读（行情）/ 写（仅管理员） | 共享行情与基础数据 | 是（Bearer 优先，回退请求体账号密码） | A04 / B04 | 自动化通过 |
| POST | `/never_guess_my_usage/quant/symbols/refresh_names` | — | 管理员 | — | — | 是（Bearer 优先，回退请求体账号密码） | — | 自动化通过 |
| GET | `/never_guess_my_usage/quant/instruments` | — | 量化用户 | — | — | 是（Bearer 优先，回退请求体账号密码） | — | 自动化通过 |
| POST | `/never_guess_my_usage/quant/instruments/custom_name` | — | 管理员 | — | — | 是（Bearer 优先，回退请求体账号密码） | — | 自动化通过 |
| POST | `/never_guess_my_usage/quant/instruments/custom_name/clear` | — | 管理员 | — | — | 是（Bearer 优先，回退请求体账号密码） | — | 自动化通过 |
| POST | `/never_guess_my_usage/quant/data/indicators/compute` | 量化工作台 | 量化用户 | 读（行情）/ 写（仅管理员） | 共享行情与基础数据 | 是（Bearer 优先，回退请求体账号密码） | A04 / B04 | 自动化通过 |
| GET | `/never_guess_my_usage/quant/data/indicators` | 量化工作台 | 量化用户 | 读（行情）/ 写（仅管理员） | 共享行情与基础数据 | 是（Bearer 优先，回退请求体账号密码） | A04 / B04 | 自动化通过 |
| GET | `/never_guess_my_usage/quant/industry/boards` | 量化工作台 | 量化用户 | 读（看板）/ 写（仅管理员） | 行业与板块数据 | 是（Bearer 优先，回退请求体账号密码） | A04 / B04 | 自动化通过 |
| POST | `/never_guess_my_usage/quant/industry/defaults` | 量化工作台 | 量化用户 | 读（看板）/ 写（仅管理员） | 行业与板块数据 | 是（Bearer 优先，回退请求体账号密码） | A04 / B04 | 自动化通过 |
| POST | `/never_guess_my_usage/quant/industry/board/save` | 量化工作台 | 管理员 | 读（看板）/ 写（仅管理员） | 行业与板块数据 | 是（Bearer 优先，回退请求体账号密码） | A04 / B04 | 自动化通过 |
| POST | `/never_guess_my_usage/quant/industry/collect` | 量化工作台 | 管理员 | 读（看板）/ 写（仅管理员） | 行业与板块数据 | 是（Bearer 优先，回退请求体账号密码） | A04 / B04 | 自动化通过 |
| GET | `/never_guess_my_usage/quant/industry/dashboard` | 量化工作台 | 量化用户 | 读（看板）/ 写（仅管理员） | 行业与板块数据 | 是（Bearer 优先，回退请求体账号密码） | A04 / B04 | 自动化通过 |
| GET | `/never_guess_my_usage/quant/industry/news` | 量化工作台 | 量化用户 | 读（看板）/ 写（仅管理员） | 行业与板块数据 | 是（Bearer 优先，回退请求体账号密码） | A04 / B04 | 自动化通过 |
| GET | `/never_guess_my_usage/quant/industry/research_reports` | 量化工作台 | 量化用户 | 读（看板）/ 写（仅管理员） | 行业与板块数据 | 是（Bearer 优先，回退请求体账号密码） | A04 / B04 | 自动化通过 |
| GET | `/never_guess_my_usage/quant/industry/report/preview` | 量化工作台 | 量化用户 | 读写 | 研究报告（继承策略归属） | 是（Bearer 优先，回退请求体账号密码） | A04 / B02 / B03 | 自动化通过 |
| GET | `/never_guess_my_usage/quant/strategy/list` | 量化工作台 | 量化用户 | 读写 | 本人策略（owner_user_id） | 是（Bearer 优先，回退请求体账号密码） | A04 / B02 / B03 / B04 | 自动化通过 |
| GET | `/never_guess_my_usage/quant/strategy/get/<int:strategy_id>` | 量化工作台 | 量化用户 | 读写 | 本人策略（owner_user_id） | 是（Bearer 优先，回退请求体账号密码） | A04 / B02 / B03 / B04 | 自动化通过 |
| POST | `/never_guess_my_usage/quant/strategy/create` | 量化工作台 | 量化用户 | 读写 | 本人策略（owner_user_id） | 是（Bearer 优先，回退请求体账号密码） | A04 / B02 / B03 / B04 | 自动化通过 |
| POST | `/never_guess_my_usage/quant/strategy/update` | 量化工作台 | 量化用户 | 读写 | 本人策略（owner_user_id） | 是（Bearer 优先，回退请求体账号密码） | A04 / B02 / B03 / B04 | 自动化通过 |
| POST | `/never_guess_my_usage/quant/strategy/delete` | 量化工作台 | 量化用户 | 读写 | 本人策略（owner_user_id） | 是（Bearer 优先，回退请求体账号密码） | A04 / B02 / B03 / B04 | 自动化通过 |
| POST | `/never_guess_my_usage/quant/strategy/run` | 量化工作台 | 量化用户 | 读写 | 本人策略（owner_user_id） | 是（Bearer 优先，回退请求体账号密码） | A04 / B02 / B03 / B04 | 自动化通过 |
| GET | `/never_guess_my_usage/quant/strategy/runs` | 量化工作台 | 量化用户 | 读写 | 本人策略（owner_user_id） | 是（Bearer 优先，回退请求体账号密码） | A04 / B02 / B03 / B04 | 自动化通过 |
| GET | `/never_guess_my_usage/quant/strategy/signals` | 量化工作台 | 量化用户 | 读写 | 本人策略（owner_user_id） | 是（Bearer 优先，回退请求体账号密码） | A04 / B02 / B03 / B04 | 自动化通过 |
| GET | `/never_guess_my_usage/quant/symbols` | — | 量化用户 | — | — | 是（Bearer 优先，回退请求体账号密码） | — | 自动化通过 |
| DELETE | `/never_guess_my_usage/quant/symbols` | — | 管理员 | — | — | 是（Bearer 优先，回退请求体账号密码） | — | 自动化通过 |
| POST | `/never_guess_my_usage/quant/symbols/batch_delete` | — | 管理员 | — | — | 是（Bearer 优先，回退请求体账号密码） | — | 自动化通过 |
| GET | `/never_guess_my_usage/quant/symbols/search` | — | 量化用户 | — | — | 是（Bearer 优先，回退请求体账号密码） | — | 自动化通过 |
| GET | `/never_guess_my_usage/quant/prompt_templates` | 量化工作台 | 量化用户 | 读（业务）/ 写（管理员） | Prompt 模板 | 是（Bearer 优先，回退请求体账号密码） | A04 / U03 | 自动化通过 |
| GET | `/never_guess_my_usage/quant/prompt_template/<int:template_id>` | 量化工作台 | 量化用户 | 读（业务）/ 写（管理员） | Prompt 模板 | 是（Bearer 优先，回退请求体账号密码） | A04 / U03 | 自动化通过 |
| POST | `/never_guess_my_usage/quant/prompt_template/create` | 量化工作台 | 管理员 | 读（业务）/ 写（管理员） | Prompt 模板 | 是（Bearer 优先，回退请求体账号密码） | A04 / U03 | 自动化通过 |
| POST | `/never_guess_my_usage/quant/prompt_template/update` | 量化工作台 | 管理员 | 读（业务）/ 写（管理员） | Prompt 模板 | 是（Bearer 优先，回退请求体账号密码） | A04 / U03 | 自动化通过 |
| POST | `/never_guess_my_usage/quant/prompt_template/delete` | 量化工作台 | 管理员 | 读（业务）/ 写（管理员） | Prompt 模板 | 是（Bearer 优先，回退请求体账号密码） | A04 / U03 | 自动化通过 |
| GET | `/never_guess_my_usage/quant/reports` | 量化工作台 | 量化用户 | 读写 | 研究报告（继承策略归属） | 是（Bearer 优先，回退请求体账号密码） | A04 / B02 / B03 | 自动化通过 |
| GET | `/never_guess_my_usage/quant/report/<int:report_id>` | 量化工作台 | 量化用户 | 读写 | 研究报告（继承策略归属） | 是（Bearer 优先，回退请求体账号密码） | A04 / B02 / B03 | 自动化通过 |
| POST | `/never_guess_my_usage/quant/report/generate` | 量化工作台 | 量化用户 | 读写 | 研究报告（继承策略归属） | 是（Bearer 优先，回退请求体账号密码） | A04 / B02 / B03 | 自动化通过 |
| POST | `/never_guess_my_usage/quant/report/preview` | 量化工作台 | 量化用户 | 读写 | 研究报告（继承策略归属） | 是（Bearer 优先，回退请求体账号密码） | A04 / B02 / B03 | 自动化通过 |
| GET | `/never_guess_my_usage/quant/meta/indicators` | — | 量化用户 | — | — | 是（Bearer 优先，回退请求体账号密码） | — | 自动化通过 |
| GET | `/never_guess_my_usage/quant/meta/expression_functions` | — | 量化用户 | — | — | 是（Bearer 优先，回退请求体账号密码） | — | 自动化通过 |
| GET | `/never_guess_my_usage/quant/meta/strategy_templates` | 量化工作台 | 量化用户 | 读写 | 本人策略（owner_user_id） | 是（Bearer 优先，回退请求体账号密码） | A04 / B02 / B03 / B04 | 自动化通过 |
| POST | `/never_guess_my_usage/quant/strategy/validate` | 量化工作台 | 量化用户 | 读写 | 本人策略（owner_user_id） | 是（Bearer 优先，回退请求体账号密码） | A04 / B02 / B03 / B04 | 自动化通过 |
| POST | `/never_guess_my_usage/quant/strategy/llm_generate_expr` | 量化工作台 | 量化用户 | 读写 | 本人策略（owner_user_id） | 是（Bearer 优先，回退请求体账号密码） | A04 / B02 / B03 / B04 | 自动化通过 |
| POST | `/never_guess_my_usage/quant/strategy/dry_run` | 量化工作台 | 量化用户 | 读写 | 本人策略（owner_user_id） | 是（Bearer 优先，回退请求体账号密码） | A04 / B02 / B03 / B04 | 自动化通过 |
| GET | `/never_guess_my_usage/quant/positions/summary` | 量化工作台 | 量化用户 | 读写 | 持仓流水（owner_user_id） | 是（Bearer 优先，回退请求体账号密码） | A04 / B02 / B03 | 自动化通过 |
| GET | `/never_guess_my_usage/quant/positions/journal` | 量化工作台 | 量化用户 | 读写 | 持仓流水（owner_user_id） | 是（Bearer 优先，回退请求体账号密码） | A04 / B02 / B03 | 自动化通过 |
| GET | `/never_guess_my_usage/quant/positions/journal/<int:entry_id>` | 量化工作台 | 量化用户 | 读写 | 持仓流水（owner_user_id） | 是（Bearer 优先，回退请求体账号密码） | A04 / B02 / B03 | 自动化通过 |
| POST | `/never_guess_my_usage/quant/positions/create` | 量化工作台 | 量化用户 | 读写 | 持仓流水（owner_user_id） | 是（Bearer 优先，回退请求体账号密码） | A04 / B02 / B03 | 自动化通过 |
| POST | `/never_guess_my_usage/quant/positions/update` | 量化工作台 | 量化用户 | 读写 | 持仓流水（owner_user_id） | 是（Bearer 优先，回退请求体账号密码） | A04 / B02 / B03 | 自动化通过 |
| POST | `/never_guess_my_usage/quant/positions/delete` | 量化工作台 | 量化用户 | 读写 | 持仓流水（owner_user_id） | 是（Bearer 优先，回退请求体账号密码） | A04 / B02 / B03 | 自动化通过 |
| GET | `/never_guess_my_usage/quant/operations/list` | 量化工作台 | 量化用户 | 读写 | 操作记录（owner_user_id） | 是（Bearer 优先，回退请求体账号密码） | A04 / B02 / B03 | 自动化通过 |
| GET | `/never_guess_my_usage/quant/operations/get/<int:record_id>` | 量化工作台 | 量化用户 | 读写 | 操作记录（owner_user_id） | 是（Bearer 优先，回退请求体账号密码） | A04 / B02 / B03 | 自动化通过 |
| POST | `/never_guess_my_usage/quant/operations/create` | 量化工作台 | 量化用户 | 读写 | 操作记录（owner_user_id） | 是（Bearer 优先，回退请求体账号密码） | A04 / B02 / B03 | 自动化通过 |
| POST | `/never_guess_my_usage/quant/operations/update` | 量化工作台 | 量化用户 | 读写 | 操作记录（owner_user_id） | 是（Bearer 优先，回退请求体账号密码） | A04 / B02 / B03 | 自动化通过 |
| POST | `/never_guess_my_usage/quant/operations/delete` | 量化工作台 | 量化用户 | 读写 | 操作记录（owner_user_id） | 是（Bearer 优先，回退请求体账号密码） | A04 / B02 / B03 | 自动化通过 |
| GET | `/never_guess_my_usage/quant/backtest/list` | 量化工作台 | 量化用户 | 读写 | 回测记录（继承策略归属） | 是（Bearer 优先，回退请求体账号密码） | A04 / B02 | 自动化通过 |
| GET | `/never_guess_my_usage/quant/backtest/get/<int:backtest_id>` | 量化工作台 | 量化用户 | 读写 | 回测记录（继承策略归属） | 是（Bearer 优先，回退请求体账号密码） | A04 / B02 | 自动化通过 |
| POST | `/never_guess_my_usage/quant/backtest/run` | 量化工作台 | 量化用户 | 读写 | 策略执行记录（继承策略归属） | 是（Bearer 优先，回退请求体账号密码） | A04 / B02 | 自动化通过 |
| POST | `/never_guess_my_usage/quant/backtest/delete` | 量化工作台 | 量化用户 | 读写 | 回测记录（继承策略归属） | 是（Bearer 优先，回退请求体账号密码） | A04 / B02 | 自动化通过 |
| GET | `/never_guess_my_usage/quant/scheduler/meta` | 量化工作台（管理员） | 管理员 | 读写 | 全局调度配置与执行记录 | 是（Bearer 优先，回退请求体账号密码） | A04 / A08 | 自动化通过 |
| GET | `/never_guess_my_usage/quant/scheduler/overview` | 量化工作台（管理员） | 管理员 | 读写 | 全局调度配置与执行记录 | 是（Bearer 优先，回退请求体账号密码） | A04 / A08 | 自动化通过 |
| GET | `/never_guess_my_usage/quant/scheduler/configs` | 量化工作台（管理员） | 管理员 | 读写 | 全局调度配置与执行记录 | 是（Bearer 优先，回退请求体账号密码） | A04 / A08 | 自动化通过 |
| GET | `/never_guess_my_usage/quant/scheduler/config/<int:schedule_id>` | 量化工作台（管理员） | 管理员 | 读写 | 全局调度配置与执行记录 | 是（Bearer 优先，回退请求体账号密码） | A04 / A08 | 自动化通过 |
| POST | `/never_guess_my_usage/quant/scheduler/config/create` | 量化工作台（管理员） | 管理员 | 读写 | 全局调度配置与执行记录 | 是（Bearer 优先，回退请求体账号密码） | A04 / A08 | 自动化通过 |
| POST | `/never_guess_my_usage/quant/scheduler/config/update` | 量化工作台（管理员） | 管理员 | 读写 | 全局调度配置与执行记录 | 是（Bearer 优先，回退请求体账号密码） | A04 / A08 | 自动化通过 |
| POST | `/never_guess_my_usage/quant/scheduler/config/delete` | 量化工作台（管理员） | 管理员 | 读写 | 全局调度配置与执行记录 | 是（Bearer 优先，回退请求体账号密码） | A04 / A08 | 自动化通过 |
| GET | `/never_guess_my_usage/quant/scheduler/runs` | 量化工作台 | 管理员 | 读写 | 策略执行记录（继承策略归属） | 是（Bearer 优先，回退请求体账号密码） | A04 / B02 | 自动化通过 |
| GET | `/never_guess_my_usage/quant/scheduler/run/<int:run_id>` | 量化工作台 | 管理员 | 读写 | 策略执行记录（继承策略归属） | 是（Bearer 优先，回退请求体账号密码） | A04 / B02 | 自动化通过 |
| GET | `/never_guess_my_usage/quant/scheduler/run/<int:run_id>/log` | 量化工作台 | 管理员 | 读写 | 策略执行记录（继承策略归属） | 是（Bearer 优先，回退请求体账号密码） | A04 / B02 | 自动化通过 |
| POST | `/never_guess_my_usage/quant/scheduler/manual_run` | 量化工作台（管理员） | 管理员 | 读写 | 全局调度配置与执行记录 | 是（Bearer 优先，回退请求体账号密码） | A04 / A08 | 自动化通过 |
| POST | `/never_guess_my_usage/quant/scheduler/rebuild_due_runs` | 量化工作台（管理员） | 管理员 | 读写 | 全局调度配置与执行记录 | 是（Bearer 优先，回退请求体账号密码） | A04 / A08 | 自动化通过 |
| POST | `/never_guess_my_usage/quant/scheduler/execute_run` | 量化工作台（管理员） | 管理员 | 读写 | 全局调度配置与执行记录 | 是（Bearer 优先，回退请求体账号密码） | A04 / A08 | 自动化通过 |
| POST | `/never_guess_my_usage/quant/scheduler/reset_run` | 量化工作台（管理员） | 管理员 | 读写 | 全局调度配置与执行记录 | 是（Bearer 优先，回退请求体账号密码） | A04 / A08 | 自动化通过 |
| POST | `/never_guess_my_usage/quant/scheduler/run/<int:run_id>/cancel` | 量化工作台 | 管理员 | 读写 | 策略执行记录（继承策略归属） | 是（Bearer 优先，回退请求体账号密码） | A04 / B02 | 自动化通过 |
| GET | `/never_guess_my_usage/quant/im/channels` | 飞书回调 / 量化工作台（管理员） | 管理员 | 读写 | IM 通道与投递记录 | 是（Bearer 优先，回退请求体账号密码） | A08 | 自动化通过 |
| GET | `/never_guess_my_usage/quant/im/channel/<int:channel_id>` | 飞书回调 / 量化工作台（管理员） | 管理员 | 读写 | IM 通道与投递记录 | 是（Bearer 优先，回退请求体账号密码） | A08 | 自动化通过 |
| POST | `/never_guess_my_usage/quant/im/channel/create` | 飞书回调 / 量化工作台（管理员） | 管理员 | 读写 | IM 通道与投递记录 | 是（Bearer 优先，回退请求体账号密码） | A08 | 自动化通过 |
| POST | `/never_guess_my_usage/quant/im/channel/update` | 飞书回调 / 量化工作台（管理员） | 管理员 | 读写 | IM 通道与投递记录 | 是（Bearer 优先，回退请求体账号密码） | A08 | 自动化通过 |
| POST | `/never_guess_my_usage/quant/im/channel/delete` | 飞书回调 / 量化工作台（管理员） | 管理员 | 读写 | IM 通道与投递记录 | 是（Bearer 优先，回退请求体账号密码） | A08 | 自动化通过 |
| GET | `/never_guess_my_usage/quant/im/deliveries` | 飞书回调 / 量化工作台（管理员） | 管理员 | 读写 | IM 通道与投递记录 | 是（Bearer 优先，回退请求体账号密码） | A08 | 自动化通过 |
| GET | `/never_guess_my_usage/quant/im/inbound_events` | 飞书回调 / 量化工作台（管理员） | 管理员 | 读写 | IM 通道与投递记录 | 是（Bearer 优先，回退请求体账号密码） | A08 | 自动化通过 |
| POST | `/never_guess_my_usage/quant/im/feishu/events` | 飞书回调 / 量化工作台（管理员） | 公开 | 读写 | IM 通道与投递记录 | 是（飞书签名校验） | A08 | 自动化通过 |
| POST | `/never_guess_my_usage/quant/im/send_report` | 飞书回调 / 量化工作台（管理员） | 管理员 | 读写 | IM 通道与投递记录 | 是（Bearer 优先，回退请求体账号密码） | A08 | 自动化通过 |
| POST | `/never_guess_my_usage/quant/im/send_positions` | 飞书回调 / 量化工作台（管理员） | 管理员 | 读写 | IM 通道与投递记录 | 是（Bearer 优先，回退请求体账号密码） | A08 | 自动化通过 |
| POST | `/never_guess_my_usage/quant/im/test` | 飞书回调 / 量化工作台（管理员） | 管理员 | 读写 | IM 通道与投递记录 | 是（Bearer 优先，回退请求体账号密码） | A08 | 自动化通过 |
| GET | `/never_guess_my_usage/quant/memory/files` | 量化工作台（管理员） | 管理员 | 读写 | 共享 AI 记忆 | 是（Bearer 优先，回退请求体账号密码） | A04 | 自动化通过 |
| GET | `/never_guess_my_usage/quant/memory/<symbol>` | 量化工作台（管理员） | 管理员 | 读写 | 共享 AI 记忆 | 是（Bearer 优先，回退请求体账号密码） | A04 | 自动化通过 |
| POST | `/never_guess_my_usage/quant/memory/curate` | 量化工作台（管理员） | 管理员 | 读写 | 共享 AI 记忆 | 是（Bearer 优先，回退请求体账号密码） | A04 | 自动化通过 |
| POST | `/never_guess_my_usage/quant/client/tasks/create` | 量化 Agent 服务账号 | 管理员 | 读写 | 数据采集 Agent 任务队列 | 是（Bearer 优先，回退请求体账号密码） | A08 | 自动化通过 |
| GET | `/never_guess_my_usage/quant/client/tasks/list` | 量化 Agent 服务账号 | 管理员 | 读写 | 数据采集 Agent 任务队列 | 是（Bearer 优先，回退请求体账号密码） | A08 | 自动化通过 |
| POST | `/never_guess_my_usage/quant/client/tasks/reset` | 量化 Agent 服务账号 | 管理员 | 读写 | 数据采集 Agent 任务队列 | 是（Bearer 优先，回退请求体账号密码） | A08 | 自动化通过 |
| POST | `/never_guess_my_usage/quant/client/tasks/claim` | 量化 Agent 服务账号 | 管理员 | 读写 | 数据采集 Agent 任务队列 | 是（Bearer 优先，回退请求体账号密码） | A08 | 自动化通过 |
| POST | `/never_guess_my_usage/quant/client/tasks/report` | 量化工作台 | 管理员 | 读写 | 研究报告（继承策略归属） | 是（Bearer 优先，回退请求体账号密码） | A04 / B02 / B03 | 自动化通过 |
