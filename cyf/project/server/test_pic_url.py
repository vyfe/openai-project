#!/usr/bin/env python3
"""
测试dialog_pic接口的FILE_URL_PATTERN匹配功能
"""

import requests
import json
import sys

# 测试配置
BASE_URL = "http://localhost:39997"
TEST_USER = "test_user"
TEST_PASSWORD = "test_password"
TEST_MODEL = "dall-e-3"

def test_single_mode_with_url():
    """测试single模式带URL的情况"""
    print("测试single模式带URL...")
    
    # 测试数据 - 包含文件URL
    test_dialog = "请基于这张图片[FILE_URL:https://example.com/test-image.jpg]生成一张类似的图片"
    
    payload = {
        "user": TEST_USER,
        "password": TEST_PASSWORD,
        "model": TEST_MODEL,
        "dialog": test_dialog,
        "dialog_mode": "single",
        "dialog_title": "测试单张图片生成"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/never_guess_my_usage/split_pic", 
                               json=payload, timeout=30)
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"处理结果: {result}")
        else:
            print("请求失败")
            
    except Exception as e:
        print(f"测试失败: {str(e)}")

def test_single_mode_without_url():
    """测试single模式不带URL的情况"""
    print("\n测试single模式不带URL...")
    
    # 测试数据 - 不包含文件URL
    test_dialog = "生成一张美丽的风景图片"
    
    payload = {
        "user": TEST_USER,
        "password": TEST_PASSWORD,
        "model": TEST_MODEL,
        "dialog": test_dialog,
        "dialog_mode": "single",
        "dialog_title": "测试单张图片生成"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/never_guess_my_usage/split_pic", 
                               json=payload, timeout=30)
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"处理结果: {result}")
        else:
            print("请求失败")
            
    except Exception as e:
        print(f"测试失败: {str(e)}")

def test_multi_mode_with_url():
    """测试multi模式带URL的情况"""
    print("\n测试multi模式带URL...")
    
    # 测试数据 - 包含文件URL的对话历史
    test_dialogs = [
        {"role": "user", "desc": "上传图片", "url": "https://example.com/original.jpg"},
        {"role": "assistant", "desc": "图片已接收"},
        {"role": "user", "desc": "基于这张图片[FILE_URL:https://example.com/style.jpg]生成新图片"}
    ]
    
    payload = {
        "user": TEST_USER,
        "password": TEST_PASSWORD,
        "model": TEST_MODEL,
        "dialog": json.dumps(test_dialogs),
        "dialog_mode": "multi",
        "dialog_title": "测试多张图片编辑"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/never_guess_my_usage/split_pic", 
                               json=payload, timeout=30)
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"处理结果: {result}")
        else:
            print("请求失败")
            
    except Exception as e:
        print(f"测试失败: {str(e)}")

def test_file_url_pattern():
    """测试FILE_URL_PATTERN正则表达式"""
    print("\n测试FILE_URL_PATTERN正则表达式...")
    
    test_cases = [
        "请基于[FILE_URL:https://example.com/image.jpg]生成图片",
        "多张图片[FILE_URL:http://test.com/1.png]和[FILE_URL:http://test.com/2.png]",
        "没有URL的普通文本",
        "[FILE_URL:https://example.com/photo.jpeg]结尾"
    ]
    
    import re
    FILE_URL_PATTERN = re.compile(r'\[FILE_URL:(https?://[^\]]+)\]')
    
    for test_case in test_cases:
        matches = FILE_URL_PATTERN.findall(test_case)
        print(f"文本: {test_case}")
        print(f"匹配到的URL: {matches}")
        print("---")

if __name__ == "__main__":
    print("开始测试dialog_pic接口的FILE_URL_PATTERN功能...")
    
    # 测试正则表达式
    test_file_url_pattern()
    
    # 注意：实际的API测试需要服务器运行和有效的用户凭据
    print("\n注意：实际的API测试需要服务器运行和有效的用户凭据")
    print("以下测试将使用示例配置，可能需要根据实际情况调整")
    
    # 取消注释以下行来进行实际测试
    # test_single_mode_with_url()
    # test_single_mode_without_url()
    # test_multi_mode_with_url()
    
    print("\n测试脚本执行完成！")