#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志和对话数据恢复脚本
从归档备份库中恢复数据到主库
入参：select语句，备份库路径，主库路径（可选）
"""

import os
import sys
import configparser
from datetime import datetime
from peewee import *
import logging

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 从sqlitelog导入数据模型
from sqlitelog import Log, Dialog

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 读取配置文件
conf = configparser.ConfigParser()
conf.read('conf/conf.ini')

# 主数据库配置
MAIN_DB_PATH = conf['log']['sqlite3_file']


class RestoreManager:
    def __init__(self):
        self.main_db = None
        self.backup_db = None
        
    def setup_databases(self, backup_db_path, main_db_path=None):
        """设置主库和备份库连接"""
        # 主数据库（如果未提供则使用默认配置）
        main_path = main_db_path if main_db_path else MAIN_DB_PATH
        self.main_db = SqliteDatabase(main_path)
        
        # 备份数据库
        self.backup_db = SqliteDatabase(backup_db_path)
        
        return True
    
    def restore_from_query(self, select_query, table_name):
        """
        从备份库执行查询并将结果恢复到主库
        
        Args:
            select_query: SELECT查询语句
            table_name: 表名（log 或 dialog）
            
        Returns:
            恢复的记录数
        """
        restored_count = 0
        
        # 根据表名选择模型
        if table_name.lower() == 'log':
            model_class = Log
        elif table_name.lower() == 'dialog':
            model_class = Dialog
        else:
            raise ValueError(f"不支持的表名: {table_name}，仅支持 log 或 dialog")
        
        try:
            # 在备份库执行查询
            logger.info(f"在备份库执行查询: {select_query}")
            cursor = self.backup_db.execute_sql(select_query)
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            
            if not rows:
                logger.warning("查询结果为空，没有数据需要恢复")
                return 0
            
            logger.info(f"查询到 {len(rows)} 条记录需要恢复")
            
            # 将数据插入到主库
            with self.main_db.atomic():
                for row in rows:
                    # row 是元组，直接使用索引
                    self.main_db.execute_sql(
                        self._build_insert_sql(table_name, columns),
                        row
                    )
                    restored_count += 1
            
            logger.info(f"成功恢复 {restored_count} 条 {table_name} 记录")
            
        except Exception as e:
            logger.error(f"数据恢复过程中发生错误: {e}")
            raise
            
        return restored_count
    
    def _build_insert_sql(self, table_name, columns):
        """构建INSERT语句"""
        placeholders = ', '.join(['?' for _ in columns])
        columns_str = ', '.join(columns)
        return f'INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})'
    
    def validate_query(self, select_query):
        """验证查询语句是否为SELECT"""
        query_upper = select_query.upper().strip()
        if not query_upper.startswith('SELECT'):
            raise ValueError("只能执行SELECT查询语句，不允许UPDATE/DELETE/INSERT等操作")
        return True
    
    def get_backup_db_tables(self):
        """获取备份库中的表"""
        try:
            cursor = self.backup_db.execute_sql(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = [row[0] for row in cursor.fetchall()]
            return tables
        except Exception as e:
            logger.error(f"获取备份库表列表失败: {e}")
            return []
    
    def get_table_row_count(self, db_path, table_name):
        """获取表中记录数"""
        try:
            if db_path == self.backup_db.database:
                cursor = self.backup_db.execute_sql(f'SELECT COUNT(*) FROM {table_name}')
            else:
                cursor = self.main_db.execute_sql(f'SELECT COUNT(*) FROM {table_name}')
            return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"获取 {table_name} 记录数失败: {e}")
            return 0
    
    def close_connections(self):
        """关闭数据库连接"""
        if self.main_db:
            self.main_db.close()
        if self.backup_db:
            self.backup_db.close()


def main():
    """主函数"""
    # 解析命令行参数
    if len(sys.argv) < 3:
        print("用法: python restore_logs.py <select查询语句> <备份库路径> [主库路径]")
        print("")
        print("参数说明:")
        print("  select查询语句  - 要执行的SELECT查询语句（必须）")
        print("  备份库路径      - 备份数据库文件路径（必须）")
        print("  主库路径        - 主数据库文件路径（可选，默认使用conf.ini中的配置）")
        print("")
        print("示例:")
        print("  python restore_logs.py \"SELECT * FROM dialog\" backup/logs-20240401.db")
        print("  python restore_logs.py \"SELECT * FROM dialog WHERE start_date >= '2024-01-01'\" backup/logs-20240401.db")
        print("  python restore_logs.py \"SELECT * FROM log\" backup/logs-20240401.db /path/to/main.db")
        return
    
    select_query = sys.argv[1]
    backup_db_path = sys.argv[2]
    main_db_path = sys.argv[3] if len(sys.argv) > 3 else None
    
    # 检查备份数据库是否存在
    if not os.path.exists(backup_db_path):
        logger.error(f"备份数据库文件不存在: {backup_db_path}")
        return
    
    logger.info("开始执行数据恢复任务...")
    logger.info(f"备份库路径: {backup_db_path}")
    logger.info(f"主库路径: {main_db_path or MAIN_DB_PATH}")
    logger.info(f"执行查询: {select_query}")
    
    # 从查询语句中推断表名
    query_upper = select_query.upper()
    if 'FROM LOG' in query_upper or 'FROM log' in query_upper:
        table_name = 'log'
    elif 'FROM DIALOG' in query_upper or 'FROM dialog' in query_upper:
        table_name = 'dialog'
    else:
        logger.error("无法从查询语句中推断表名，请确保查询语句包含 FROM log 或 FROM dialog")
        return
    
    restore_manager = RestoreManager()
    
    try:
        # 设置数据库连接
        restore_manager.setup_databases(backup_db_path, main_db_path)
        
        # 设置模型使用主数据库（用于后续操作）
        Log._meta.database = restore_manager.main_db
        Dialog._meta.database = restore_manager.main_db
        
        # 验证查询语句
        restore_manager.validate_query(select_query)
        
        # 显示备份库中的表
        tables = restore_manager.get_backup_db_tables()
        logger.info(f"备份库中的表: {tables}")
        
        # 显示恢复前的记录数
        backup_count = restore_manager.get_table_row_count(backup_db_path, table_name)
        main_count = restore_manager.get_table_row_count(MAIN_DB_PATH, table_name)
        logger.info(f"恢复前 - 备份库 {table_name} 记录数: {backup_count}")
        logger.info(f"恢复前 - 主库 {table_name} 记录数: {main_count}")
        
        # 执行恢复
        restored_count = restore_manager.restore_from_query(select_query, table_name)
        
        # 显示恢复后的记录数
        main_count_after = restore_manager.get_table_row_count(MAIN_DB_PATH, table_name)
        logger.info(f"恢复后 - 主库 {table_name} 记录数: {main_count_after}")
        
        logger.info("数据恢复任务完成")
        
    except Exception as e:
        logger.error(f"数据恢复任务失败: {e}")
    finally:
        restore_manager.close_connections()


if __name__ == '__main__':
    main()