#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通知公告API调试脚本 - 详细版本
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

def debug_request(method, url, data=None, params=None):
    """调试请求函数"""
    print(f"\n=== {method.upper()} 请求 ===")
    print(f"URL: {url}")
    
    if data:
        print(f"请求数据: {json.dumps(data, ensure_ascii=False, indent=2)}")
    if params:
        print(f"查询参数: {json.dumps(params, ensure_ascii=False, indent=2)}")
    
    try:
        if method.upper() == 'POST':
            response = requests.post(url, data=data)
        elif method.upper() == 'GET':
            response = requests.get(url, params=params)
        
        print(f"状态码: {response.status_code}")
        print(f"响应头: {dict(response.headers)}")
        
        if response.text:
            print(f"原始响应: {response.text}")
            try:
                json_result = response.json()
                print(f"JSON响应: {json.dumps(json_result, ensure_ascii=False, indent=2)}")
                return json_result
            except json.JSONDecodeError as e:
                print(f"JSON解析错误: {e}")
                return None
        else:
            print("响应体为空")
            return None
            
    except Exception as e:
        print(f"请求异常: {e}")
        return None

def test_debug():
    """详细调试测试"""
    print("=== 开始详细调试通知公告API ===")
    
    # 1. 测试基础连接
    print("\n1. 测试基础连接...")
    debug_request('GET', f"{BASE_URL}/")
    
    # 2. 创建通知
    print("\n2. 创建通知...")
    create_data = {
        'user': ADMIN_USER,
        'password': ADMIN_PASSWORD,
        'title': '测试通知',
        'content': '这是一个测试通知内容。',
        'priority': 5,
        'status': 'active'
    }
    
    result = debug_request('POST', f"{BASE_URL}{ADMIN_API_PREFIX}/notification/create", data=create_data)
    
    if result and result.get('success'):
        notification_id = result['data']['id']
        
        # 3. 获取通知列表
        print("\n3. 获取通知列表...")
        debug_request('GET', f"{BASE_URL}{ADMIN_API_PREFIX}/notification/list", params={
            'user': ADMIN_USER,
            'password': ADMIN_PASSWORD
        })
        
        # 4. 获取单个通知
        print(f"\n4. 获取单个通知 (ID: {notification_id})...")
        debug_request('GET', f"{BASE_URL}{ADMIN_API_PREFIX}/notification/get/{notification_id}", params={
            'user': ADMIN_USER,
            'password': ADMIN_PASSWORD
        })
        
        # 5. 获取有效通知列表（无需认证）
        print("\n5. 获取有效通知列表（无需认证）...")
        debug_request('GET', f"{BASE_URL}{ADMIN_API_PREFIX}/notification/active_list", params={'limit': 5})
        
        # 6. 清理 - 删除测试通知
        print(f"\n6. 删除测试通知 (ID: {notification_id})...")
        delete_data = {
            'user': ADMIN_USER,
            'password': ADMIN_PASSWORD,
            'id': notification_id
        }
        debug_request('POST', f"{BASE_URL}{ADMIN_API_PREFIX}/notification/delete", data=delete_data)
    
    print("\n=== 详细调试完成 ===")

if __name__ == "__main__":
    test_debug()