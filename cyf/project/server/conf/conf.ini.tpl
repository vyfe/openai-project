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
[log]
sqlite3_file=
[api]
api_key=
api_host=
[model_filter]
# 包含前缀（硬编码默认值：gpt,gemini）
include_prefixes=gpt,gemini,qwen,nano-banana,deepseek
# 排除关键词
exclude_keywords=instruct,realtime,audio
# 缓存时间（秒）
cache_ttl=3600