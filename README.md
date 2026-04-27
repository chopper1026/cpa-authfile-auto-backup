# CPA 认证文件自动备份

CLIProxyAPI (CPA) 认证文件定时备份到阿里云 OSS。

## 功能

- 支持多个 CPA 项目备份
- 定时自动备份（默认每天一次）
- 备份文件打包为 tar.gz 上传到 OSS
- 自动清理过期备份
- 支持 daemon 模式和单次执行模式

## 安装

### 1. 安装 Python 3.12

Ubuntu/Debian（通过 Deadsnakes PPA）：

```bash
sudo apt update
sudo apt install software-properties-common -y
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install python3.12 python3.12-venv -y
```

> Ubuntu 24.04+ 自带 Python 3.12，直接 `sudo apt install python3.12 python3.12-venv` 即可。

### 2. 创建虚拟环境并安装依赖

**不要**直接用系统 pip 安装（Ubuntu 的 Python 受 PEP 668 保护，会报 `externally-managed-environment` 错误）。

```bash
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

> 之后所有操作都要先 `source venv/bin/activate` 激活虚拟环境，或者直接用 `venv/bin/python` 来运行脚本。

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

项目提供了 `start.sh` 启动脚本，自动使用虚拟环境的 Python，无需手动激活：

```bash
# 单次备份
./start.sh --once

# daemon 模式（持续运行，按配置定时执行）
./start.sh

# 指定配置文件
./start.sh -c /path/to/config.yaml --once
```

## 使用 crontab 定时执行

如果不想用 daemon 模式，可以用 crontab 调用单次模式：

```bash
# 每天凌晨 3 点执行备份
0 3 * * * /root/cpa-authfile-auto-backup/start.sh --once >> /var/log/cpa-backup/cron.log 2>&1
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
