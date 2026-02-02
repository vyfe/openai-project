# 数据归档系统使用说明

## 功能概述

本系统提供自动化的日志和对话数据归档功能，每7天运行一次，将8天前创建的dialog记录和所有log记录复制到备份数据库，然后从主库删除对应数据。

## 文件说明

### 主要脚本
- [`archive_logs.py`](archive_logs.py) - 数据归档主脚本
- [`crontab_config.txt`](crontab_config.txt) - 定时任务配置说明
- [`simple_test.py`](simple_test.py) - 简单的功能测试脚本

### 备份文件
- 备份数据库保存在 `backup/` 目录下
- 文件名格式：`logs-YYYYMMDD.db`（例如：`logs-20260201.db`）

## 使用方法

### 1. 手动运行归档
```bash
cd /Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/server
python archive_logs.py
```

### 2. 设置定时任务
编辑crontab文件，添加每周日凌晨2点执行的定时任务：
```bash
crontab -e
```

添加以下内容：
```
0 2 * * 0 cd /Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/server && /Users/chenyifei.anon/IdeaProjects/openai-project/.venv/bin/python archive_logs.py >> /Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/server/backup/archive_log.txt 2>&1
```

### 3. 验证归档结果
运行测试脚本验证功能是否正常：
```bash
python simple_test.py
```

## 归档逻辑

### 数据筛选规则
- **Dialog记录**：归档8天前创建的记录（基于`start_date`字段）
- **Log记录**：归档所有记录（因为日志通常不需要长期保留在主库）

### 数据处理流程
1. **统计检查**：获取归档前的数据库统计信息
2. **备份创建**：创建新的备份数据库文件
3. **数据复制**：将符合条件的记录复制到备份库
4. **数据清理**：从主库删除已归档的记录
5. **结果验证**：输出归档统计信息

## 备份文件管理

### 文件命名
备份文件采用日期命名格式：`logs-YYYYMMDD.db`
- 例如：2024年3月15日的备份文件为 `logs-20240315.db`

### 存储位置
所有备份文件保存在 `backup/` 目录下：
```
cyf/project/server/backup/
├── logs-20240201.db
├── logs-20240208.db
├── logs-20240215.db
└── archive_log.txt  # 归档日志文件
```

### 文件大小
备份文件大小取决于数据量，通常几百KB到几MB不等。

## 监控和日志

### 运行日志
- 归档脚本的运行日志保存在 `backup/archive_log.txt`
- 日志包含详细的执行过程和数据统计信息

### 查看日志
```bash
tail -f backup/archive_log.txt
```

## 数据恢复

如果需要从备份文件恢复数据，可以使用SQLite工具：

```bash
# 查看备份文件中的数据
sqlite3 backup/logs-20240201.db "SELECT * FROM log LIMIT 10;"
sqlite3 backup/logs-20240201.db "SELECT * FROM dialog LIMIT 10;"

# 导出数据到SQL文件
sqlite3 backup/logs-20240201.db .dump > backup_data.sql
```

## 注意事项

1. **磁盘空间**：定期检查备份目录的磁盘空间使用情况
2. **备份清理**：根据需要定期清理旧的备份文件
3. **权限设置**：确保脚本有读写备份目录的权限
4. **定时任务**：验证crontab配置是否正确生效

## 故障排查

### 常见问题
1. **数据库连接错误**：检查主数据库文件是否存在
2. **权限错误**：确保有创建备份目录和文件的权限
3. **定时任务不执行**：检查crontab配置和系统日志

### 手动验证
```bash
# 检查主数据库
sqlite3 logs.db "SELECT COUNT(*) FROM log;"
sqlite3 logs.db "SELECT COUNT(*) FROM dialog;"

# 检查备份数据库
sqlite3 backup/logs-20240201.db "SELECT COUNT(*) FROM log;"
sqlite3 backup/logs-20240201.db "SELECT COUNT(*) FROM dialog;"
```

## 联系方式

如有问题，请查看运行日志或联系系统管理员。