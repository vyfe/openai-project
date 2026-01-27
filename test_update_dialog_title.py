#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试更新对话标题功能
"""

import requests
import json

# 服务端地址
BASE_URL = "http://localhost:39997"

def test_update_dialog_title():
    """测试更新对话标题功能"""
    print("开始测试更新对话标题功能...")

    # 准备测试数据
    user = "test_user"  # 替换为实际存在的用户名
    password = "test_password"  # 替换为实际密码
    dialog_id = 1  # 替换为实际存在的对话ID
    new_title = "测试更新后的标题"

    # 发送更新标题请求
    url = f"{BASE_URL}/never_guess_my_usage/update_dialog_title"
    data = {
        'user': user,
        'password': password,
        'dialog_id': dialog_id,
        'new_title': new_title
    }

    try:
        response = requests.post(url, data=data)
        print(f"响应状态码: {response.status_code}")
        print(f"响应内容: {response.text}")

        result = response.json()
        if result.get('success'):
            print("✅ 更新对话标题成功!")
        else:
            print(f"❌ 更新对话标题失败: {result.get('msg')}")

    except Exception as e:
        print(f"❌ 请求失败: {e}")

def test_invalid_params():
    """测试无效参数的情况"""
    print("\n测试无效参数情况...")

    user = "test_user"  # 替换为实际存在的用户名
    password = "test_password"  # 替换为实际密码

    # 测试缺少参数
    url = f"{BASE_URL}/never_guess_my_usage/update_dialog_title"
    data = {
        'user': user,
        'password': password,
        # 缺少 dialog_id 和 new_title
    }

    try:
        response = requests.post(url, data=data)
        result = response.json()
        print(f"缺少参数时的响应: {result}")

    except Exception as e:
        print(f"❌ 请求失败: {e}")

if __name__ == "__main__":
    print("对话标题更新功能测试")
    print("="*50)

    test_update_dialog_title()
    test_invalid_params()