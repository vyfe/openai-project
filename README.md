# 项目目标

open-ai 访问器，用于部署代理，跨越魔法限制

# 如何使用

部署服务端+客户端，通过客户端-服务端-openai的方式访问。
## 部署准备工作
需要自行补足部分配置&文件


## 服务端原理：cyf.project.server
所需配置见conf.ini：


## 客户端原理：cyf.project.client
所需配置见conf.ini：

## 启动步骤：
- 根目录执行：sh full-pack-prod.sh，从dist目录取包;
- 服务器上执行：cd ${PROJECT_ROOT} && tar -xf openai-full-prod.tar.gz && sh start-prod.sh
    - 前提条件：python3环境和uwsgi；
- nginx需要根据${PROJECT_ROOT}独立配好前后端的端口转发（这块后续再完善）