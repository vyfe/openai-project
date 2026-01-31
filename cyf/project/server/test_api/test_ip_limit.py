#!/usr/bin/env python3
"""
测试IP限制功能的脚本
"""
import requests
import time

def test_ip_limit():
    """测试IP限制功能"""
    base_url = "http://localhost:39997"

    # 测试配置的test_user
    test_user = "test_user"
    test_password = "test123"

    # 多次发送请求来测试IP限制
    print(f"开始测试 {test_user} 的IP限制功能...")

    for i in range(25):  # 尝试25次请求，超过默认限制20
        print(f"请求 #{i+1}")

        try:
            response = requests.post(
                f"{base_url}/never_guess_my_usage/split",
                data={
                    "user": test_user,
                    "password": test_password,
                    "model": "gpt-3.5-turbo",  # 使用一个有效的模型
                    "dialog": f"Test message {i}",
                    "dialog_mode": "single"
                },
                timeout=30
            )

            print(f"  状态码: {response.status_code}")
            print(f"  响应: {response.json()}")

            if "异常123" in str(response.json()):
                print(f"  >> 已达到IP限制，第{i+1}次请求被拒绝")
                break

        except requests.exceptions.RequestException as e:
            print(f"  请求失败: {e}")

        time.sleep(0.5)  # 短暂延迟

    print("\n测试完成")

if __name__ == "__main__":
    test_ip_limit()