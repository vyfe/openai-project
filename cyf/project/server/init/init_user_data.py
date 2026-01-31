#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
用户数据迁移脚本
将用户认证数据从配置文件迁移到 SQLite 数据库
"""

import configparser
import sys
import os
# 添加上级目录到Python路径，以便导入sqlitelog
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sqlitelog
from typing import Dict, List, Tuple

def parse_users_from_config() -> Dict[str, Tuple[str, str]]:
    """
    从配置文件解析用户数据

    Returns:
        Dict[str, Tuple[str, str]]: {username: (password, api_key)}
    """
    print("正在从配置文件解析用户数据...")
    conf = configparser.ConfigParser()
    conf.read('conf/conf.ini', encoding="UTF-8")

    user_data = {}

    # 解析用户凭据，支持格式：用户名:密码:api_key（api_key可选）
    users_config = conf['common']['users']
    # 支持多行格式的用户配置，每行一个用户信息
    user_lines = [line.strip() for line in users_config.split('\n') if line.strip()]

    for line in user_lines:
        # 按逗号分割（兼容旧格式）
        user_entries = line.split(',') if ',' in line else [line]

        for item in user_entries:
            # 使用最大分割次数2，确保即使密码或API密钥中包含冒号也能正确处理
            parts = item.strip().split(':', 2)
            if len(parts) >= 2:
                username = parts[0].strip()
                password = parts[1].strip()

                # 如果有第三个参数，则为该用户的专属API key
                if len(parts) >= 3 and parts[2].strip():
                    api_key = parts[2].strip()
                else:
                    api_key = conf['api']['api_key']  # 使用默认API key

                user_data[username] = (password, api_key)
            elif item.strip():  # 如果不是空行
                username = item.strip()
                user_data[username] = ('', conf['api']['api_key'])  # 使用默认API key

    print(f"成功解析到 {len(user_data)} 个用户")
    return user_data


def migrate_users_to_db():
    """
    将用户数据迁移到数据库
    """
    print("开始迁移用户数据到数据库...")

    # 获取配置文件中的用户数据
    user_data = parse_users_from_config()

    migrated_count = 0
    skipped_count = 0

    for username, (password, api_key) in user_data.items():
        # 检查用户是否已存在于数据库中
        existing_user = sqlitelog.get_user_by_username(username)
        if existing_user:
            print(f"用户 {username} 已存在于数据库中，跳过迁移")
            skipped_count += 1
            continue

        # 创建新用户到数据库
        try:
            sqlitelog.create_user(username, password, api_key)
            print(f"成功迁移用户: {username}")
            migrated_count += 1
        except Exception as e:
            print(f"迁移用户 {username} 失败: {e}")

    print(f"迁移完成！成功迁移 {migrated_count} 个用户，跳过 {skipped_count} 个已存在用户")


def print_current_users():
    """
    打印当前数据库中的所有活跃用户
    """
    print("\n当前数据库中的活跃用户:")
    active_users = sqlitelog.get_all_active_users()

    if not active_users:
        print("数据库中没有活跃用户")
        return

    for username in active_users:
        user = sqlitelog.get_user_by_username(username)
        print(f"- 用户名: {user.username}")
        print(f"  - API Key: {'已配置' if user.api_key else '未配置'}")
        print(f"  - 激活状态: {'是' if user.is_active else '否'}")
        print()


def main():
    """
    主函数
    """
    print("=" * 50)
    print("用户数据迁移脚本")
    print("=" * 50)

    # 检查数据库中是否已有用户
    if sqlitelog.user_exists_in_db():
        print("检测到数据库中已存在用户数据")
        response = input("是否继续迁移？这可能会导致重复用户数据(y/N): ")
        if response.lower() not in ['y', 'yes']:
            print("操作已取消")
            return

    # 执行迁移
    migrate_users_to_db()

    # 显示当前用户
    print_current_users()

    print("迁移脚本执行完成！")


if __name__ == "__main__":
    sqlitelog.init_db();
    main()