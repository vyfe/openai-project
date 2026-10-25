# MiniMax 音乐创作

入口：管理员登录后访问 `http://localhost:3000/studio/music`，或从聊天页右上角用户菜单进入“声音工作台 → 音乐创作”。声音工作台是独立功能页（`/studio`，外壳 `views/studio/StudioLayout.vue`），与量化工作台同级，不嵌在管理后台页签里。沿用现有 Vue、Flask 和管理员鉴权，不另起服务。

生成配置的形态和音乐保存的原理参考已有的语音合成功能（见 [minimax-voice-management.md](./minimax-voice-management.md)）：先把创作参数写入 SQLite，再请求云端生成，成功后保存临时链接并下载本地 MP3。

## 配置

音乐生成使用**独立的配置段和凭据**，与音色管理的语音凭据互不影响，方便后续单独接入计费账号。

向后端**实际加载的配置文件**追加以下段落，填入自己的密钥后重启后端。开发启动脚本使用 `cyf/project/server/conf/conf.dev.ini`；默认/生产使用 `conf/conf.ini`。页面”连接配置”会显示实际配置文件路径和当前密钥来源。独立占位配置为 [`minimax.ini.example`](../cyf/project/server/conf/minimax.ini.example)，完整模板在 `cyf/project/server/conf/conf.ini.tpl`。

```ini
[minimax_music]
api_key=<填入音乐专用的 MiniMax API Key>
region=cn
key_kind=token_plan
model=music-3.0
timeout_seconds=180
```

> 这一段同时也是**音色复刻**用的计费凭据：Token Plan 密钥只能合成语音、不能创建音色。分工细节见 [minimax-voice-management.md](./minimax-voice-management.md) 的”两套凭据的分工”。

| 字段 | 说明 |
| --- | --- |
| `api_key` | 音乐接口的 API Key。**留空则沿用 `[minimax]` 的语音密钥**，单密钥部署无需改配置。 |
| `region` | `cn` 或 `intl`，须与密钥所属站点一致；留空沿用 `[minimax].region`。 |
| `key_kind` | `token_plan` / `m_plan` / `pay_as_you_go`，仅标记来源，不改变请求端点或权益。 |
| `model` | 文本生音乐模型，`music-3.0`（推荐）或 `music-2.6`。 |
| `timeout_seconds` | 范围 10–240 秒；留空沿用 `[minimax].timeout_seconds`。 |

也支持环境变量 `MINIMAX_MUSIC_API_KEY`，优先级高于配置文件。`MINIMAX_API_KEY` 只影响语音能力；两者互不覆盖。

**数据隔离**：凭据指纹由 `region + api_key` 计算，存储目录为 `voice_data/<凭据指纹>/music/`。使用独立密钥后，音乐记录与本地音频归到该密钥名下；换回原密钥才能看到用旧密钥生成的作品。

> 官方说明：自 2026 年 8 月 20 日起，付费接口（音乐生成、歌词生成）不再面向新用户提供服务，历史付费用户可继续使用现有 API；免费音乐生成接口（`music-3.0-free`、`music-2.6-free`、`music-cover-free`）停止服务。本功能因此只开放 `music-3.0` 和 `music-2.6` 两个付费文本生音乐模型。
>
> 若密钥属于新用户账号，官方会返回业务码 `2153`：`This Music API is no longer available to new users.`。此时换密钥或开通音乐能力之前，页面所有生成动作都会失败并显示该提示；这是账号权限问题，不是参数或网络问题。官方替代方案为 [MiniMax Audio](https://www.minimax.io/audio) 和开源的 [MiniMax Music 3](https://huggingface.co/MiniMaxAI/MiniMax-Music3)。

## 使用

页面提供两种模式：**文本生音乐** 和 **参考音频翻唱**。

1. **文本生音乐**
   - 填写作品名称、风格描述和歌词，选择模型后点击“提交生成并保存”。
   - 风格描述对应接口的 `prompt`，上限 2000 字符；歌词对应 `lyrics`，上限 3500 字符，段落用 `[Verse]`、`[Chorus]`、`[Bridge]` 等标记分行。
   - 勾选“纯音乐（无人声）”时只填风格描述即可，对应 `is_instrumental`。
   - 勾选“由风格描述自动写词”时，歌词可留空，对应 `lyrics_optimizer`；若填了歌词则优先使用填写的歌词。
   - 带人声且既没有歌词也没有开启自动写词时，前端拦截且后端同样拒绝，不会发起付费请求。
2. **参考音频翻唱**（官方 `music-cover` 模型，两步流程）
   - 上传参考音频（MP3 / WAV / FLAC / M4A / AAC / OGG，6 秒–6 分钟、最大 20 MB），点击“上传参考音频并提取歌词”。后端以 base64 提交到 `/v1/music_cover_preprocess`，取回 `cover_feature_id`（24 小时有效）和 ASR 提取的 `formatted_lyrics`。
   - 提取出的歌词会回填到歌词框，可直接修改；再填写“目标曲风”（10–300 字符，对应 `prompt`），点击“提交生成翻唱”。后端用 `cover_feature_id` 调用 `/v1/music_generation`。
   - 翻唱特征 24 小时后失效，需要重新上传参考音频。
3. **创作记录**：播放、下载 MP3 与创作参数（风格描述与歌词导出为 TXT）、复制音频链接、载入编辑后重新生成，或删除记录。翻唱记录点“载入编辑”会回到翻唱模式，可基于同一份参考音频改词重生成。MiniMax 返回的音频链接有效期为 **24 小时**，本地 MP3 保留后可继续播放；备份下载失败时，链接与创作参数仍在 SQLite 中，可在链接有效期内重试下载，不会重新生成。

## 本地数据与请求行为

复用平台现有 SQLite（配置项 `[log].sqlite3_file`），启动时自动创建新表 `music_track`，不修改原有表：

- `music_track`：作品名称、风格描述、歌词、模型、纯音乐与自动写词开关、生成状态、音频 URL、24 小时过期时间、实际时长、本地文件大小和错误信息；翻唱另有 `cover_feature_id` 与参考音频时长。列表显示最近 200 条，数据库保留完整记录。

`music_track` 在迭代中新增过列，存量库由 `model/db.py` 的 `ensure_schema` 在启动时自动补齐（`cover_feature_id`、`reference_duration`）。

MP3 备份放在 `voice_data/<凭据指纹>/music/`，与音色共用同一个 `voice_data` 根目录和文件锁机制，但凭据指纹不同即目录不同；更换密钥或区域会隔离数据，切回原凭据可看到原记录。音频目录已加入 `.gitignore`，备份时同时备份平台 SQLite 与该目录。

请求前保存 `generating` 记录；明确失败标记 `failed`，超时或网络中断标记 `unknown` 并保留创作参数。云端链接返回后立即入库为 `remote_ready`，本地 MP3 下载成功后为 `ready`。若接口返回 hex 内联音频（`output_format` 未被服务端按 url 处理），直接解码落盘并标记 `ready`，不产生临时链接。

云端请求不自动重试；浏览器音乐客户端也禁用失败后的认证重放，保留请求前的登录刷新。若超时、网络中断或服务端本地保存失败，先检查云端或本地结果，避免立即再次生成。音乐接口的请求体和响应体不写入访问日志，只记录访问元数据。

## 接口

均在 `/never_guess_my_usage/music` 下并要求管理员权限：

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/state` | 脱敏配置、模型列表与历史记录 |
| POST | `/generate` | 文本生音乐，参数与链接入 SQLite，备份 MP3 |
| POST | `/cover/preprocess` | multipart 上传参考音频，换取翻唱特征与 ASR 歌词 |
| POST | `/cover/generate` | 用翻唱特征生成翻唱，参数与链接入 SQLite |
| GET | `/track/<id>` | 查询单条记录与创作参数，供重新载入 |
| GET | `/audio/<id>/<mp3或txt>` | 鉴权下载本地文件 |
| POST | `/delete` | 删除记录和本地 MP3 |

## 官方依据

- [音乐生成接口（请求参数、响应字段、错误码）](https://platform.minimax.cn/docs/api-reference/music-generation)
- [翻唱前处理（参考音频、特征 ID、ASR 歌词）](https://platform.minimax.cn/docs/api-reference/music-cover-preprocess)
- [模型与额度说明](https://platform.minimax.cn/docs/guides/models-intro)
- [错误码参考](https://platform.minimax.cn/docs/api-reference/errorcode)

开发验证：后端全量测试 1132 项通过（其中音乐相关 34 项），前端全量测试 113 项通过，Vite 生产构建通过。已运行 `start-dev.sh`，通过 Playwright 检查模式切换、参考音频上传与时长校验、表单拦截、错误提示、记录列表、载入编辑和删除。

真实接口验证：使用开发环境密钥上传 10 秒 WAV 参考音频，官方返回业务码 `2153`（`This Music API is no longer available to new users.`），说明当前密钥为新用户账号、无音乐接口权限；请求链路（multipart 上传 → base64 → 官方接口 → 错误透出）已验证通畅，但未消耗真实音乐额度，真实生成效果与费用须使用有音乐权限的历史付费账号密钥验收。
