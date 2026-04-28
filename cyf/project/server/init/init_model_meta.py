#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ModelMeta表数据初始化脚本
从API接口获取模型数据并插入到SQLite数据库中
"""

import sqlite3
import requests
import json
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlitelog import db, ModelMeta


def fetch_models_data_from_api():
    """
    从API获取模型数据
    """
    api_url = "https://api.vveai.com/api/models-data"

    try:
        response = requests.get(api_url, timeout=30)
        response.raise_for_status()
        data = response.json()

        print(f"成功获取API数据: {len(data) if isinstance(data, list) else 'object'} 项")
        return data
    except requests.exceptions.RequestException as e:
        print(f"API请求失败: {e}")
        print("使用默认模型数据...")
        return get_default_models_data()
    except json.JSONDecodeError:
        print("API响应不是有效的JSON格式")
        print("使用默认模型数据...")
        return get_default_models_data()


def get_default_models_data():
    """
    默认模型数据（当API不可用时使用）
    """
    return [
        {
            "model_name": "gpt-4o",
            "model_desc": "OpenAI最新旗舰级模型，适用于复杂任务和高级推理",
            "recommend": True,
            "status_valid": True
        },
        {
            "model_name": "gpt-4o-mini",
            "model_desc": "高效的小型模型，适合快速响应和轻量级任务",
            "recommend": True,
            "status_valid": True
        },
        {
            "model_name": "gpt-3.5-turbo",
            "model_desc": "平衡性能与成本的理想选择，适合日常任务",
            "recommend": False,
            "status_valid": True
        },
        {
            "model_name": "dall-e-3",
            "model_desc": "先进的图像生成模型，支持高分辨率图片创作",
            "recommend": False,
            "status_valid": True
        },
        {
            "model_name": "gpt-4-turbo",
            "model_desc": "强大的多模态模型，具备视觉理解能力",
            "recommend": False,
            "status_valid": False
        },
        {
            "model_name": "claude-3-sonnet",
            "model_desc": "Anthropic公司开发的智能模型，擅长分析和推理",
            "recommend": True,
            "status_valid": True
        },
        {
            "model_name": "claude-3-haiku",
            "model_desc": "快速响应的轻量级模型，适合即时对话",
            "recommend": False,
            "status_valid": True
        },
        {
            "model_name": "gemini-pro",
            "model_desc": "Google开发的多模态AI模型，具备广泛知识",
            "recommend": False,
            "status_valid": True
        }
    ]


def init_model_meta_data():
    """
    初始化ModelMeta表数据
    """
    print("开始初始化ModelMeta表数据...")

    # 获取模型数据
    models_data = fetch_models_data_from_api()

    # 如果API返回的是对象而非数组，则尝试提取models字段
    if isinstance(models_data, dict):
        if 'models' in models_data:
            models_data = models_data['models']
        elif 'data' in models_data:
            models_data = models_data['data']
        else:
            print("API响应格式未知，尝试使用默认数据...")
            models_data = get_default_models_data()

    if not isinstance(models_data, list):
        print("无法解析API数据格式，使用默认数据...")
        models_data = get_default_models_data()

    try:
        # 连接数据库（如果尚未连接）
        if db.is_closed():
            db.connect()

        added_count = 0   # 新增记录数
        updated_count = 0 # 更新记录数

        # 写入模型元数据（新增或更新）
        for model_data in models_data:
            # 兼容两种字段：API(id/desc_zh/exists) 与 默认数据(model_name/model_desc/status_valid)
            model_name = str(model_data.get('id') or model_data.get('model_name') or '').strip()
            if not model_name:
                print(f"跳过空模型名称的数据项: {model_data}")
                continue

            model_desc = str(model_data.get('desc_zh') or model_data.get('model_desc') or 'No description available')
            recommend = bool(model_data.get('recommend', False))
            status_valid = bool(model_data.get('exists', model_data.get('status_valid', True)))

            try:
                existing_model = ModelMeta.get(ModelMeta.model_name == model_name)
                changed = False
                if existing_model.model_desc != model_desc:
                    existing_model.model_desc = model_desc
                    changed = True
                if existing_model.recommend != recommend:
                    existing_model.recommend = recommend
                    changed = True
                if existing_model.status_valid != status_valid:
                    existing_model.status_valid = status_valid
                    changed = True

                if changed:
                    existing_model.save()
                    updated_count += 1
                    print(f"成功更新模型: {model_name}")
            except ModelMeta.DoesNotExist:
                try:
                    ModelMeta.create(
                        model_name=model_name,
                        model_desc=model_desc,
                        recommend=recommend,
                        status_valid=status_valid
                    )
                    print(f"成功添加新模型: {model_name}")
                    added_count += 1
                except Exception as e:
                    print(f"添加模型 {model_name} 时出错: {e}")
                    continue

        print(f"完成模型元数据初始化，新增 {added_count} 个，更新 {updated_count} 个")

    except Exception as e:
        print(f"初始化过程中出现错误: {e}")
        raise
    finally:
        # 只有在连接是由本函数打开的情况下才关闭
        # 但是这里我们不关闭，以免影响其他部分使用数据库连接
        pass


def print_current_models():
    """
    打印当前数据库中的模型数据
    """
    try:
        db.connect()

        models = ModelMeta.select()
        print("\n当前数据库中的模型数据:")
        print("-" * 80)
        print(f"{'模型名称':<20} {'推荐':<6} {'有效':<6} {'描述'}")
        print("-" * 80)

        for model in models:
            recommend_str = "是" if model.recommend else "否"
            status_str = "是" if model.status_valid else "否"
            desc_preview = model.model_desc[:50] + "..." if len(model.model_desc) > 50 else model.model_desc
            print(f"{model.model_name:<20} {recommend_str:<6} {status_str:<6} {desc_preview}")

        print("-" * 80)
        print(f"总计: {models.count()} 个模型")

    except Exception as e:
        print(f"查询模型数据时出现错误: {e}")
    finally:
        if not db.is_closed():
            db.close()


if __name__ == "__main__":
    print("ModelMeta数据初始化脚本")
    print("=" * 50)

    # 初始化数据
    init_model_meta_data()

    # 显示当前数据
    print_current_models()
