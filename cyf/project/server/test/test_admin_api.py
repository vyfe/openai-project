#!/usr/bin/env python3
"""
Admin API 测试脚本
测试所有 22 个 admin 接口是否正常工作
"""

import requests
import json
import sys

# 配置
BASE_URL = "http://localhost:39997"
ADMIN_USER = "admin"  # 请替换为实际的管理员用户名
ADMIN_PASSWORD = "admin"  # 请替换为实际的管理员密码

def test_api(method, endpoint, data=None, params=None):
    """通用的API测试函数"""
    url = f"{BASE_URL}{endpoint}"
    auth_params = {
        'user': ADMIN_USER,
        'password': ADMIN_PASSWORD
    }
    
    # 合并认证参数
    if method.upper() == 'GET':
        if params:
            auth_params.update(params)
        response = requests.get(url, params=auth_params)
    else:
        if data:
            data.update(auth_params)
        else:
            data = auth_params
        response = requests.request(method, url, data=data, params=params)
    
    print(f"\n=== {method} {endpoint} ===")
    print(f"Status: {response.status_code}")
    try:
        result = response.json()
        print(f"Response: {json.dumps(result, indent=2, ensure_ascii=False)}")
        return result
    except:
        print(f"Response: {response.text}")
        return None

def run_tests():
    """运行所有测试"""
    print("开始测试 Admin API 接口...")
    
    # 1. ModelMeta 接口测试 (5个)
    print("\n\n========== ModelMeta 接口测试 ==========")
    
    # 1.1 创建模型
    create_result = test_api('POST', '/admin_api/model_meta/create', {
        'model_name': 'test-model-1',
        'model_desc': '测试模型1',
        'recommend': 'true',
        'status_valid': 'true'
    })
    
    if create_result and create_result.get('success'):
        model_id = create_result['data']['id']
        
        # 1.2 获取单个模型
        test_api('GET', f'/admin_api/model_meta/get/{model_id}')
        
        # 1.3 更新模型
        test_api('POST', '/admin_api/model_meta/update', {
            'id': model_id,
            'model_desc': '更新的测试模型描述',
            'recommend': 'false'
        })
        
        # 1.4 获取模型列表
        test_api('GET', '/admin_api/model_meta/list', params={'recommend': 'false'})
        
        # 1.5 删除模型
        test_api('POST', '/admin_api/model_meta/delete', {'id': model_id})
    
    # 2. SystemPrompt 接口测试 (5个)
    print("\n\n========== SystemPrompt 接口测试 ==========")
    
    # 2.1 创建系统提示词
    prompt_result = test_api('POST', '/admin_api/system_prompt/create', {
        'role_name': 'test-assistant',
        'role_group': 'test-group',
        'role_desc': '测试助手角色',
        'role_content': '你是一个测试助手',
        'status_valid': 'true'
    })
    
    if prompt_result and prompt_result.get('success'):
        prompt_id = prompt_result['data']['id']
        
        # 2.2 获取单个提示词
        test_api('GET', f'/admin_api/system_prompt/get/{prompt_id}')
        
        # 2.3 更新提示词
        test_api('POST', '/admin_api/system_prompt/update', {
            'id': prompt_id,
            'role_desc': '更新的测试助手描述'
        })
        
        # 2.4 获取提示词列表
        test_api('GET', '/admin_api/system_prompt/list', params={'role_group': 'test-group'})
        
        # 2.5 删除提示词
        test_api('POST', '/admin_api/system_prompt/delete', {'id': prompt_id})
    
    # 3. TestLimit 接口测试 (6个)
    print("\n\n========== TestLimit 接口测试 ==========")
    
    # 3.1 创建测试限制
    limit_result = test_api('POST', '/admin_api/test_limit/create', {
        'user_ip': '192.168.1.100',
        'user_count': '5',
        'limit': '50'
    })
    
    if limit_result and limit_result.get('success'):
        limit_id = limit_result['data']['id']
        
        # 3.2 获取单个测试限制
        test_api('GET', f'/admin_api/test_limit/get/{limit_id}')
        
        # 3.3 更新测试限制
        test_api('POST', '/admin_api/test_limit/update', {
            'id': limit_id,
            'user_count': '10',
            'limit': '100'
        })
        
        # 3.4 获取测试限制列表
        test_api('GET', '/admin_api/test_limit/list')
        
        # 3.5 重置测试限制
        test_api('POST', '/admin_api/test_limit/reset', {'id': limit_id})
        
        # 3.6 删除测试限制
        test_api('POST', '/admin_api/test_limit/delete', {'id': limit_id})
    
    # 4. User 接口测试 (6个)
    print("\n\n========== User 接口测试 ==========")
    
    # 4.1 创建用户
    user_result = test_api('POST', '/admin_api/user/create', {
        'username': 'testuser123',
        'new_password': 'testpass123',
        'role': 'user',
        'is_active': 'true'
    })
    
    if user_result and user_result.get('success'):
        user_id = user_result['data']['id']
        
        # 4.2 获取单个用户
        test_api('GET', f'/admin_api/user/get/{user_id}')
        
        # 4.3 更新用户
        test_api('POST', '/admin_api/user/update', {
            'id': user_id,
            'role': 'admin',
            'is_active': 'true'
        })
        
        # 4.4 重置密码
        test_api('POST', '/admin_api/user/reset_password', {
            'id': user_id,
            'new_password': 'newpass123'
        })
        
        # 4.5 获取用户列表
        test_api('GET', '/admin_api/user/list')
        
        # 4.6 删除用户（软删除）
        test_api('POST', '/admin_api/user/delete', {'id': user_id})
    
    print("\n\n========== 测试完成 ==========")
    print("所有接口测试已执行完毕！")
    print("请检查上述输出，确认所有接口都返回了预期的成功响应。")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        ADMIN_USER = sys.argv[1]
    if len(sys.argv) > 2:
        ADMIN_PASSWORD = sys.argv[2]
    
    run_tests()