# 量化 Agent 登录凭据模板（生产机密，请勿直接使用本文件）
#
# 用途：start-prod-quant 启动数据采集 Agent 时，用它登录后端 API 认领采集任务。
# 调度 Worker（--scheduler）不需要本文件。
#
# 生产部署步骤（在项目根目录 $HOME/openai-project 执行）：
#   cp .quant-credentials.tpl .quant-credentials
#   $EDITOR .quant-credentials      # 填入实际用户名与密码
#   chmod 600 .quant-credentials
#
# 也可用环境变量 QUANT_LOGIN_USER / QUANT_LOGIN_PASSWORD 覆盖本文件；
# 两者都缺失时 start-prod-quant --agent 会明确报错退出。
#
# 账号来源：平台登录账号（与 conf.ini 的 [common] users 或 DB 用户表一致），
# 不是 API key、也不是飞书 token。
QUANT_LOGIN_USER=
QUANT_LOGIN_PASSWORD=
