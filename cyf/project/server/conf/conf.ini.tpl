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
[model]
gpt-4o-mini=gpt-4o-mini-2024-07-18
gpt-4o=gpt-4o-2024-11-20
gpt-4o-all=gpt-4o-all
gpt-3.5-turbo=gpt-3.5-turbo
图像生成(dall-e)=dall-e-3
图像生成(gpt-4o)=gpt-4o-all