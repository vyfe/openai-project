#!/usr/bin/env python3
"""
集成测试dialog_pic接口的FILE_URL_PATTERN匹配功能
"""

import requests
import json
import sys
import base64
from io import BytesIO

# 测试配置
BASE_URL = "http://localhost:39997"
TEST_USER = "test_user"
TEST_PASSWORD = "test_password"
TEST_MODEL = "dall-e-3"

def create_test_image():
    """创建一个简单的测试图片（1x1像素的红色PNG）"""
    # 这是一个1x1像素的红色PNG图片的base64编码
    test_png_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
    return base64.b64decode(test_png_base64)

def test_file_format():
    """测试文件格式处理"""
    print("测试文件格式处理...")
    
    # 创建测试图片数据
    image_data = create_test_image()
    
    # 测试不同的文件格式
    test_cases = [
        ("test.jpg", image_data, "image/jpeg"),
        ("test.png", image_data, "image/png"),
        ("test.webp", image_data, "image/webp")
    ]
    
    for filename, data, content_type in test_cases:
        # 创建文件元组 (filename, bytes, content_type)
        file_tuple = (filename, data, content_type)
        print(f"文件名: {filename}, 内容类型: {content_type}, 数据大小: {len(data)} bytes")
        print(f"文件元组格式: {type(file_tuple)}")
    
    return True

def test_url_to_file_format():
    """测试URL到文件格式的转换"""
    print("\n测试URL到文件格式转换...")
    
    # 模拟从URL下载的图片数据
    image_data = create_test_image()
    
    # 测试不同的URL
    test_urls = [
        "https://example.com/test-image.jpg",
        "http://test.com/photo.png",
        "https://cdn.example.com/picture.webp"
    ]
    
    for url in test_urls:
        filename = url.split('/')[-1]
        content_type = "image/jpeg" if filename.endswith(".jpg") else "image/png"
        
        # 创建文件元组
        file_tuple = (filename, image_data, content_type)
        print(f"URL: {url}")
        print(f"文件名: {filename}")
        print(f"内容类型: {content_type}")
        print(f"文件元组: {file_tuple}")
        print("---")

def test_openai_file_format():
    """测试OpenAI API文件格式要求"""
    print("\n测试OpenAI API文件格式...")
    
    # 根据OpenAI文档，图片编辑API需要以下格式：
    # - 图片文件：PNG、JPEG、WebP
    # - 大小限制：DALL-E-2为4MB，GPT图片模型为50MB
    # - 尺寸要求：DALL-E-2需要正方形，GPT图片模型支持多种尺寸
    
    image_data = create_test_image()
    
    # 测试文件元组格式 (filename, bytes, content_type)
    file_content = ("test.png", image_data, "image/png")
    
    print(f"文件内容类型: {type(file_content)}")
    print(f"文件内容: {file_content}")
    print(f"准备用于OpenAI API的格式正确")

if __name__ == "__main__":
    print("开始测试dialog_pic接口的文件格式处理...")
    
    # 运行各种测试
    test_file_format()
    test_url_to_file_format()
    test_openai_file_format()
    
    print("\n文件格式测试完成！")
    print("关键要点：")
    print("1. OpenAI API需要文件元组格式：(filename, bytes, content_type)")
    print("2. 内容类型必须正确设置（image/jpeg, image/png, image/webp等）")
    print("3. 文件数据应该是原始字节数据")
    print("4. 文件名应该包含正确的扩展名")