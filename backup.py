#!/usr/bin/env python3
"""CPA 认证文件自动备份到阿里云 OSS"""

import argparse
import io
import logging
import os
import signal
import sys
import tarfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import oss2
import schedule
import yaml

SCRIPT_DIR = Path(__file__).parent.resolve()
DEFAULT_CONFIG = SCRIPT_DIR / "config.yaml"

logger = logging.getLogger("cpa-backup")


def load_config(config_path: str) -> dict:
    path = Path(config_path)
    if not path.exists():
        print(f"错误: 配置文件不存在: {path}", file=sys.stderr)
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def setup_logging(cfg: dict):
    log_cfg = cfg.get("logging", {})
    level = getattr(logging, log_cfg.get("level", "INFO").upper(), logging.INFO)
    handlers: list[logging.Handler] = [logging.StreamHandler()]

    log_file = log_cfg.get("file", "")
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )


def create_tarball(auth_dir: str, config_file: str | None = None) -> bytes:
    """将认证文件目录（及可选的配置文件）打包为 tar.gz 字节流"""
    buf = io.BytesIO()
    auth_path = Path(auth_dir)
    if not auth_path.exists():
        raise FileNotFoundError(f"认证文件目录不存在: {auth_dir}")

    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for item in auth_path.iterdir():
            if item.is_file():
                tar.add(str(item), arcname=f"auths/{item.name}")
        if config_file:
            cfg_path = Path(config_file)
            if cfg_path.exists():
                tar.add(str(cfg_path), arcname=f"config/{cfg_path.name}")
            else:
                logger.warning(f"配置文件不存在，跳过: {config_file}")

    return buf.getvalue()


def upload_to_oss(cfg: dict, project_name: str, tar_data: bytes, timestamp: datetime) -> str:
    """上传备份到 OSS，返回 OSS 对象路径"""
    oss_cfg = cfg["oss"]
    auth = oss2.Auth(oss_cfg["access_key_id"], oss_cfg["access_key_secret"])
    bucket = oss2.Bucket(auth, oss_cfg["endpoint"], oss_cfg["bucket_name"])

    date_str = timestamp.strftime("%Y-%m-%d")
    time_str = timestamp.strftime("%H%M%S")
    prefix = oss_cfg.get("backup_prefix", "cpa-backup")
    oss_key = f"{prefix}/{project_name}/{date_str}/auths_backup_{date_str}_{time_str}.tar.gz"

    bucket.put_object(oss_key, tar_data)
    return oss_key


def cleanup_old_backups(cfg: dict, project_name: str):
    """清理过期的 OSS 备份"""
    ret_cfg = cfg.get("retention", {})
    if not ret_cfg.get("enabled", False):
        return

    keep_days = ret_cfg.get("keep_days", 30)
    cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
    cutoff_str = cutoff.strftime("%Y-%m-%d")

    oss_cfg = cfg["oss"]
    auth = oss2.Auth(oss_cfg["access_key_id"], oss_cfg["access_key_secret"])
    bucket = oss2.Bucket(auth, oss_cfg["endpoint"], oss_cfg["bucket_name"])
    prefix = f"{oss_cfg.get('backup_prefix', 'cpa-backup')}/{project_name}/"

    deleted = 0
    for obj in oss2.ObjectIterator(bucket, prefix=prefix):
        # 对象 key 格式: {prefix}/{project}/{date}/xxx.tar.gz
        parts = obj.key.split("/")
        if len(parts) >= 3:
            date_part = parts[2]
            if date_part < cutoff_str:
                bucket.delete_object(obj.key)
                deleted += 1
                logger.info(f"删除过期备份: {obj.key}")

    if deleted:
        logger.info(f"项目 [{project_name}] 清理了 {deleted} 个过期备份 (保留 {keep_days} 天)")


def backup_project(cfg: dict, project: dict, timestamp: datetime) -> bool:
    """备份单个 CPA 项目，返回是否成功"""
    name = project["name"]
    auth_dir = project["auth_dir"]
    config_file = project.get("config_file")

    logger.info(f"开始备份项目 [{name}]，认证目录: {auth_dir}")

    try:
        tar_data = create_tarball(auth_dir, config_file)
        size_mb = len(tar_data) / (1024 * 1024)
        logger.info(f"项目 [{name}] 打包完成，大小: {size_mb:.2f} MB")

        oss_key = upload_to_oss(cfg, name, tar_data, timestamp)
        logger.info(f"项目 [{name}] 上传成功: oss://{cfg['oss']['bucket_name']}/{oss_key}")

        cleanup_old_backups(cfg, name)
        return True

    except FileNotFoundError as e:
        logger.error(f"项目 [{name}] 备份失败: {e}")
    except oss2.exceptions.OssError as e:
        logger.error(f"项目 [{name}] OSS 上传失败: {e}")
    except Exception as e:
        logger.error(f"项目 [{name}] 备份异常: {e}", exc_info=True)

    return False


def run_backup(cfg: dict):
    """执行一次全量备份"""
    timestamp = datetime.now()
    logger.info(f"========== 开始备份任务 ({timestamp.strftime('%Y-%m-%d %H:%M:%S')}) ==========")

    results = {}
    for project in cfg.get("projects", []):
        ok = backup_project(cfg, project, timestamp)
        results[project["name"]] = "成功" if ok else "失败"

    logger.info(f"========== 备份任务完成 ==========")
    for name, status in results.items():
        logger.info(f"  {name}: {status}")


def setup_scheduler(cfg: dict) -> schedule.Job:
    """根据配置设置定时任务"""
    sched_cfg = cfg.get("schedule", {})
    sched_type = sched_cfg.get("type", "interval")

    if sched_type == "interval":
        hours = sched_cfg.get("interval_hours", 24)
        return schedule.every(hours).hours.do(run_backup, cfg)
    elif sched_type == "cron":
        cron_expr = sched_cfg.get("cron", "0 3 * * *")
        parts = cron_expr.split()
        if len(parts) != 5:
            logger.error(f"无效的 cron 表达式: {cron_expr}")
            sys.exit(1)
        minute, hour, day, month, dow = parts
        job = schedule.every().day
        if minute != "*":
            job = job.at(f"{int(hour):02d}:{int(minute):02d}")
        else:
            job = job.at(f"{int(hour):02d}:00")
        return job.do(run_backup, cfg)
    else:
        logger.error(f"不支持的定时类型: {sched_type}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="CPA 认证文件自动备份到阿里云 OSS")
    parser.add_argument("--config", "-c", default=str(DEFAULT_CONFIG), help="配置文件路径")
    parser.add_argument("--once", action="store_true", help="仅执行一次备份，不进入定时模式")
    args = parser.parse_args()

    cfg = load_config(args.config)
    setup_logging(cfg)

    logger.info(f"配置已加载: {args.config}")
    logger.info(f"备份项目数: {len(cfg.get('projects', []))}")

    for p in cfg.get("projects", []):
        logger.info(f"  - {p['name']}: {p['auth_dir']}")

    if args.once:
        run_backup(cfg)
        return

    # daemon 模式
    job = setup_scheduler(cfg)
    logger.info(f"定时任务已设置: {job}")
    logger.info("按 Ctrl+C 退出")

    stop = False

    def handle_signal(sig, frame):
        nonlocal stop
        logger.info("收到退出信号，正在停止...")
        stop = True

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # 启动时立即执行一次
    run_backup(cfg)

    while not stop:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
