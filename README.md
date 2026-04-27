# CPA 认证文件自动备份

CLIProxyAPI (CPA) 认证文件定时备份到阿里云 OSS。

## 功能

- 支持多个 CPA 项目备份
- 定时自动备份（默认每天一次）
- 备份文件打包为 tar.gz 上传到 OSS
- 自动清理过期备份
- 支持 daemon 模式和单次执行模式

## 安装

```bash
pip install -r requirements.txt
```

## 配置

```bash
cp config.example.yaml config.yaml
```

编辑 `config.yaml`，填入：
- OSS 的 Endpoint、AccessKey、Bucket
- 各 CPA 项目的 `auth_dir`（认证文件目录绝对路径）
- 可选：`config_file`（CPA 配置文件路径，会一并备份）
- 定时规则和保留天数

## 使用

```bash
# 单次备份（适合 crontab 调用）
python backup.py --once

# daemon 模式（持续运行，按配置定时执行）
python backup.py

# 指定配置文件
python backup.py -c /path/to/config.yaml --once
```

## 使用 crontab 定时执行

如果不想用 daemon 模式，可以用 crontab 调用单次模式：

```bash
# 每天凌晨 3 点执行备份
0 3 * * * cd /path/to/cpa-authfile-auto-backup && python backup.py --once >> /var/log/cpa-backup/cron.log 2>&1
```

## OSS 存储结构

```
{bucket}/
  └── {backup_prefix}/
        ├── cpa-main/
        │     └── 2026-04-27/
        │           └── auths_backup_2026-04-27_030000.tar.gz
        └── cpa-secondary/
              └── 2026-04-27/
                    └── auths_backup_2026-04-27_030000.tar.gz
```
