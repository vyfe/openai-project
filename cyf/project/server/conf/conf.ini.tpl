[common]
upload_dir=
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
test_exceed_msg=异常123
[log]
sqlite3_file=
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
sqlite3_file=
# 量化 bundle 运行目录。当前主要用于预留运行时目录，建议给独立路径。
bundle_dir=
# 股票记忆 Markdown 存储目录。
memory_dir=
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
