#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通知公告API测试脚本
"""

import requests
import json
from datetime import datetime

# 管理员认证信息
ADMIN_USER = "cyf"
ADMIN_PASSWORD = "cyf123_"

# API基础URL
BASE_URL = "http://localhost:39997"
ADMIN_API_PREFIX = "/admin_api"

def test_notification_apis():
    """测试通知公告相关API"""
    print("=== 开始测试通知公告API ===")
    
    # 1. 创建通知
    print("\n1. 创建通知...")
    create_data = {
        'user': ADMIN_USER,
        'password': ADMIN_PASSWORD,
        'title': '系统维护通知',
        'content': '系统将于今晚22:00-24:00进行例行维护，期间服务可能暂时不可用，请提前做好准备。',
        'priority': 5,
        'status': 'active'
    }
    
    try:
        response = requests.post(f"{BASE_URL}{ADMIN_API_PREFIX}/notification/create", data=create_data)
        result = response.json()
        print(f"创建通知结果: {result}")
        
        if result.get('success'):
            notification_id = result['data']['id']
            print(f"通知创建成功，ID: {notification_id}")
        else:
            print(f"通知创建失败: {result.get('msg')}")
            return
    except Exception as e:
        print(f"创建通知异常: {e}")
        return
    
    # 2. 获取通知列表
    print("\n2. 获取通知列表...")
    try:
        response = requests.get(f"{BASE_URL}{ADMIN_API_PREFIX}/notification/list", params={
            'user': ADMIN_USER,
            'password': ADMIN_PASSWORD
        })
        result = response.json()
        print(f"通知列表结果: {json.dumps(result, ensure_ascii=False, indent=2)}")
    except Exception as e:
        print(f"获取通知列表异常: {e}")
    
    # 3. 获取单个通知
    print(f"\n3. 获取单个通知 (ID: {notification_id})...")
    try:
        response = requests.get(f"{BASE_URL}{ADMIN_API_PREFIX}/notification/get/{notification_id}", params={
            'user': ADMIN_USER,
            'password': ADMIN_PASSWORD
        })
        result = response.json()
        print(f"单个通知结果: {json.dumps(result, ensure_ascii=False, indent=2)}")
    except Exception as e:
        print(f"获取单个通知异常: {e}")
    
    # 4. 更新通知
    print(f"\n4. 更新通知 (ID: {notification_id})...")
    update_data = {
        'user': ADMIN_USER,
        'password': ADMIN_PASSWORD,
        'id': notification_id,
        'title': '系统维护通知（已更新）',
        'content': '系统维护时间调整为今晚21:00-23:00，请提前做好准备。',
        'priority': 8
    }
    
    try:
        response = requests.post(f"{BASE_URL}{ADMIN_API_PREFIX}/notification/update", data=update_data)
        result = response.json()
        print(f"更新通知结果: {result}")
    except Exception as e:
        print(f"更新通知异常: {e}")
    
    # 5. 获取有效通知列表（无需认证）
    print("\n5. 获取有效通知列表（无需认证）...")
    try:
        response = requests.get(f"{BASE_URL}{ADMIN_API_PREFIX}/notification/active_list", params={'limit': 5})
        result = response.json()
        print(f"有效通知列表: {json.dumps(result, ensure_ascii=False, indent=2)}")
    except Exception as e:
        print(f"获取有效通知列表异常: {e}")
    
    # 6. 创建第二个通知
    print("\n6. 创建第二个通知...")
    create_data2 = {
        'user': ADMIN_USER,
        'password': ADMIN_PASSWORD,
        'title': '新功能上线',
        'content': '我们很高兴地宣布，新的AI助手功能已经正式上线，欢迎大家体验使用！',
        'priority': 3,
        'status': 'active'
    }
    
    try:
        response = requests.post(f"{BASE_URL}{ADMIN_API_PREFIX}/notification/create", data=create_data2)
        result = response.json()
        print(f"创建第二个通知结果: {result}")
        
        if result.get('success'):
            notification_id2 = result['data']['id']
            print(f"第二个通知创建成功，ID: {notification_id2}")
        else:
            print(f"第二个通知创建失败: {result.get('msg')}")
    except Exception as e:
        print(f"创建第二个通知异常: {e}")
    
    # 7. 删除通知
    print(f"\n7. 删除通知 (ID: {notification_id})...")
    delete_data = {
        'user': ADMIN_USER,
        'password': ADMIN_PASSWORD,
        'id': notification_id
    }
    
    try:
        response = requests.post(f"{BASE_URL}{ADMIN_API_PREFIX}/notification/delete", data=delete_data)
        result = response.json()
        print(f"删除通知结果: {result}")
    except Exception as e:
        print(f"删除通知异常: {e}")
    
    print("\n=== 通知公告API测试完成 ===")

if __name__ == "__main__":
    test_notification_apis()