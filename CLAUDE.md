# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

CLIProxyAPI (CPA) 认证文件自动备份工具。将 CPA 的 OAuth 认证文件（`auths/` 目录下的 JSON 文件）定时打包上传到阿里云 OSS。支持多个 CPA 项目、可配置定时规则、自动清理过期备份。

## 运行命令

```bash
pip install -r requirements.txt          # 安装依赖
python backup.py --once                  # 单次备份
python backup.py                         # daemon 模式（启动时立即执行一次，之后按 schedule 定时）
python backup.py -c /path/to/config.yaml # 指定配置文件
python3 -c "import py_compile; py_compile.compile('backup.py', doraise=True)"  # 语法检查
```

## 架构

单文件 Python 应用 (`backup.py`)，核心流程：

`load_config` -> `run_backup` -> 遍历 `projects` -> `backup_project` -> `create_tarball` + `upload_to_oss` + `cleanup_old_backups`

- **配置驱动**：`config.yaml` 定义项目列表、OSS 凭证、定时规则、保留策略。`config.example.yaml` 是模板，实际配置被 `.gitignore` 排除。
- **daemon 模式**：使用 `schedule` 库做定时调度，启动时立即执行一次，之后每 60 秒检查是否到时。
- **单次模式** (`--once`)：执行一次后退出，适合 crontab 调用。
- **OSS 路径结构**：`{backup_prefix}/{project_name}/{date}/auths_backup_{date}_{time}.tar.gz`

## 依赖

- `oss2` — 阿里云 OSS SDK
- `pyyaml` — YAML 配置解析
- `schedule` — 定时任务调度
