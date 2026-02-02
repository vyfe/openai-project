#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志和对话数据归档脚本
每7天运行一次，将8天前创建的dialog记录和所有log记录复制到备份数据库，
然后从主库删除对应数据
"""

import os
import sys
import shutil
import configparser
from datetime import datetime, timedelta
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
BACKUP_DIR = 'backup'

class ArchiveManager:
    def __init__(self):
        self.main_db = None
        self.backup_db = None
        
    def setup_databases(self, backup_db_path):
        """设置主库和备份库连接"""
        # 主数据库
        self.main_db = SqliteDatabase(MAIN_DB_PATH)
        
        # 备份数据库
        self.backup_db = SqliteDatabase(backup_db_path)
        
        return True
        
    def create_backup_database(self, backup_db_path):
        """创建备份数据库并初始化表结构"""
        # 确保备份目录存在
        os.makedirs(BACKUP_DIR, exist_ok=True)
        
        # 如果备份数据库已存在，先删除
        if os.path.exists(backup_db_path):
            os.remove(backup_db_path)
            
        # 创建备份数据库连接
        backup_db = SqliteDatabase(backup_db_path)
        
        # 临时设置模型使用备份数据库来创建表结构
        original_log_db = Log._meta.database
        original_dialog_db = Dialog._meta.database
        
        Log._meta.database = backup_db
        Dialog._meta.database = backup_db
        
        try:
            # 在备份库中创建表结构
            with backup_db:
                backup_db.create_tables([Log, Dialog], safe=True)
        finally:
            # 恢复原始数据库设置
            Log._meta.database = original_log_db
            Dialog._meta.database = original_dialog_db
            
        logger.info(f"备份数据库创建成功: {backup_db_path}")
        return True
        
    def archive_old_data(self, cutoff_date):
        """归档旧数据"""
        archived_logs = 0
        archived_dialogs = 0
        
        try:
            # 1. 归档8天前的dialog记录
            old_dialogs_query = Dialog.select().where(Dialog.start_date < cutoff_date)
            dialog_count = old_dialogs_query.count()
            
            if dialog_count > 0:
                logger.info(f"发现 {dialog_count} 条需要归档的旧dialog记录")
                
                # 将数据复制到备份库
                with self.backup_db.atomic():
                    for dialog in old_dialogs_query:
                        # 使用INSERT语句直接插入到备份库
                        self.backup_db.execute_sql(
                            'INSERT INTO dialog (username, chattype, modelname, dialog_name, start_date, context) VALUES (?, ?, ?, ?, ?, ?)',
                            (dialog.username, dialog.chattype, dialog.modelname, dialog.dialog_name, dialog.start_date, dialog.context)
                        )
                        archived_dialogs += 1
                    
                    # 从主库删除已归档的记录
                    deleted_count = Dialog.delete().where(Dialog.start_date < cutoff_date).execute()
                    logger.info(f"已归档并删除 {deleted_count} 条dialog记录")
            
            # 2. 归档所有log记录
            all_logs_query = Log.select()
            log_count = all_logs_query.count()
            
            if log_count > 0:
                logger.info(f"发现 {log_count} 条需要归档的log记录")
                
                # 将数据复制到备份库
                with self.backup_db.atomic():
                    for log in all_logs_query:
                        # 使用INSERT语句直接插入到备份库
                        self.backup_db.execute_sql(
                            'INSERT INTO log (username, modelname, usage, request_text) VALUES (?, ?, ?, ?)',
                            (log.username, log.modelname, log.usage, log.request_text)
                        )
                        archived_logs += 1
                    
                    # 从主库删除已归档的记录
                    deleted_log_count = Log.delete().execute()
                    logger.info(f"已归档并删除 {deleted_log_count} 条log记录")
                    
        except Exception as e:
            logger.error(f"数据归档过程中发生错误: {e}")
            raise
            
        return archived_logs, archived_dialogs
        
    def get_database_stats(self):
        """获取数据库统计信息"""
        try:
            # 使用原始SQL查询避免模型数据库绑定问题
            cursor = self.main_db.execute_sql('SELECT COUNT(*) FROM log')
            log_count = cursor.fetchone()[0]
            
            cursor = self.main_db.execute_sql('SELECT COUNT(*) FROM dialog')
            dialog_count = cursor.fetchone()[0]
            
            # 获取最早和最晚的dialog日期
            if dialog_count > 0:
                cursor = self.main_db.execute_sql('SELECT MIN(start_date), MAX(start_date) FROM dialog')
                earliest_date, latest_date = cursor.fetchone()
            else:
                earliest_date = None
                latest_date = None
                
            return {
                'log_count': log_count,
                'dialog_count': dialog_count,
                'earliest_dialog_date': earliest_date,
                'latest_dialog_date': latest_date
            }
        except Exception as e:
            logger.error(f"获取数据库统计信息失败: {e}")
            return None
            
    def close_connections(self):
        """关闭数据库连接"""
        if self.main_db:
            self.main_db.close()
        if self.backup_db:
            self.backup_db.close()

def main():
    """主函数"""
    logger.info("开始执行数据归档任务...")
    
    # 计算8天前的日期（用于dialog归档）
    cutoff_date = datetime.now().date() - timedelta(days=8)
    
    # 生成备份数据库文件名
    backup_date = datetime.now().strftime("%Y%m%d")
    backup_db_path = os.path.join(BACKUP_DIR, f"logs-{backup_date}.db")
    
    # 检查主数据库是否存在
    if not os.path.exists(MAIN_DB_PATH):
        logger.error(f"主数据库文件不存在: {MAIN_DB_PATH}")
        return
        
    archive_manager = ArchiveManager()
    
    try:
        # 设置数据库连接
        archive_manager.setup_databases(backup_db_path)
        
        # 设置模型使用主数据库
        Log._meta.database = archive_manager.main_db
        Dialog._meta.database = archive_manager.main_db
        
        # 获取归档前的统计信息
        logger.info("获取归档前数据库统计信息...")
        stats_before = archive_manager.get_database_stats()
        if stats_before:
            logger.info(f"归档前 - Log记录数: {stats_before['log_count']}, "
                       f"Dialog记录数: {stats_before['dialog_count']}")
            if stats_before['earliest_dialog_date']:
                logger.info(f"Dialog日期范围: {stats_before['earliest_dialog_date']} 到 {stats_before['latest_dialog_date']}")
        
        # 创建备份数据库
        logger.info(f"创建备份数据库: {backup_db_path}")
        archive_manager.create_backup_database(backup_db_path)
        
        # 执行数据归档
        logger.info(f"开始归档数据，dialog截止日期: {cutoff_date}")
        archived_logs, archived_dialogs = archive_manager.archive_old_data(cutoff_date)
        
        logger.info(f"数据归档完成！")
        logger.info(f"已归档 {archived_logs} 条log记录")
        logger.info(f"已归档 {archived_dialogs} 条dialog记录")
        
        # 获取归档后的统计信息
        logger.info("获取归档后数据库统计信息...")
        stats_after = archive_manager.get_database_stats()
        if stats_after:
            logger.info(f"归档后 - Log记录数: {stats_after['log_count']}, "
                       f"Dialog记录数: {stats_after['dialog_count']}")
        
        logger.info(f"备份文件已保存至: {backup_db_path}")
        
    except Exception as e:
        logger.error(f"数据归档任务失败: {e}")
        raise
        
    finally:
        archive_manager.close_connections()
        logger.info("数据归档任务结束")

if __name__ == "__main__":
    main()