[common]
upload_dir=/home/www/downloads
# 用户配置支持两种格式：
# 1. 旧格式（一行）：users=admin:admin123:key,user1:password1
# 2. 新格式（多行，YAML风格）：
# users=
#   admin:admin123:key
#   user1:password1
#   user2:password234:optional_api_key
users=
  admin:admin123:your_api_key_here
  user1:password1
  user2:password234:optional_api_key
test_user=test_user
test_ip_default_limit=20
test_exceed_msg=当前ip试用次数已满，请联系vx:pata_data_studio获取正式账号！
# HTTP Host 头，用于反代场景（可选）
host=
[log]
sqlite3_file=./logs.db
[runtime_log]
# 运行日志根目录。LLM / Quant / Ops / Platform 会在此目录下分流。
root_dir=
# 默认日志级别
level=INFO
# 近 7 天保留普通文本日志
plain_retention_days=7
# 超过普通保留期后，压缩保留 30 天
archive_retention_days=30
# 是否自动压缩滚动日志
compress_backups=true
[admin]
# 是否启用SQL执行后门
enable_sql_execute=
[quant]
# 独立量化数据库。不要和 log.sqlite3_file 共用，避免被日志清理策略误伤。
sqlite3_file=./quant.db
# 量化 bundle 运行目录。当前主要用于预留运行时目录，建议给独立路径。
bundle_dir=./quant_bundles
# 股票记忆 Markdown 存储目录。
memory_dir=./quant_memory
# 调度执行日志目录。留空时默认使用 <runtime_log.root_dir>/quant/runs。
schedule_log_dir=
# 调度执行日志保留天数。过期文件会被清理。
schedule_log_retention_days=7
# 飞书自建应用配置。用于双向对话、报告推送和持仓录入，当前唯一支持的 IM 通道。
# 回调地址：/never_guess_my_usage/quant/im/feishu/events
feishu_app_id=
feishu_app_secret=
feishu_verification_token=
# 可选。若飞书事件订阅开启加密，则填写 Encrypt Key。
feishu_encrypt_key=
# 消息调试后缀
feishu_debug_suffix=
# 同花顺金融数据 API Key（https://fuyao.aicubes.cn/ 的 capability 鉴权）。
# 留空时 ths provider 会被跳过，auto 链降级到 baostock。
# 也可使用环境变量 THS_API_KEY 兜底（conf > env）。
# 密钥属生产机密，禁止写入本模板；请在服务器的 conf/conf.ini 或环境变量中维护。
ths_api_key=
[api]
api_key=
api_host=
# USD to CNY conversion rate
usd_to_cny_rate=5
# API parameter mode: 'default' for date strings, 'timestamp' for millisecond timestamps
api_param_mode=default
[model_filter]
# 包含前缀（硬编码默认值：gpt,gemini）
include_prefixes=gpt,gemini,qwen,nano-banana,deepseek
# 排除关键词
exclude_keywords=instruct,realtime,audio
# 缓存时间（秒）
cache_ttl=3600

[tools]
# 模型可调用的本地网络搜索脚本，无需第三方搜索 API Key。
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

[minimax]
# 独立语音凭据。MINIMAX_API_KEY 环境变量优先；不回退到 [api]/[claude]。
api_key=<填入你的 MiniMax API Key>
# cn（中国站）或 intl（国际站），须与密钥所属站点一致。
region=cn
# 仅标记密钥类型，实际语音权限以 MiniMax 返回为准；不自动切换计费方式。
key_kind=token_plan
model=speech-2.8-hd
# 范围 10–240 秒。
timeout_seconds=180
# 相对后端目录；保存 MP3、正文导出和文件锁。台账与音频链接复用现有 SQLite。
storage_dir=voice_data

[minimax_music]
# 音乐生成与音色复刻使用的计费凭据；留空则沿用上面的 [minimax] 语音凭据。
# Token Plan 密钥只能合成语音、不能创建音色，复刻需要这里的计费密钥。
# 环境变量 MINIMAX_MUSIC_API_KEY 优先于本段。
api_key=
# 留空沿用 [minimax].region；cn（中国站）或 intl（国际站）。
region=
# 仅标记密钥类型，不改变请求端点或权益。
key_kind=token_plan
# 文本生音乐模型，可选 music-3.0、music-2.6。
model=music-3.0
# 留空沿用 [minimax].timeout_seconds；范围 10–240 秒。
timeout_seconds=
