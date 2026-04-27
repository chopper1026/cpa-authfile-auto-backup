#!/bin/bash
cd "$(dirname "$0")"

DIR="$(pwd)"
PID_FILE="$DIR/cpa-backup.pid"
LOG_DIR="$DIR/logs"
PYTHON="$DIR/venv/bin/python"

ensure_venv() {
    if [ ! -f "$PYTHON" ]; then
        echo "错误: 虚拟环境不存在，请先运行: python3.12 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
        exit 1
    fi
}

is_running() {
    if [ -f "$PID_FILE" ]; then
        pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            return 0
        fi
        rm -f "$PID_FILE"
    fi
    return 1
}

do_start() {
    if is_running; then
        echo "CPA Backup 已在运行中 (PID: $(cat "$PID_FILE"))"
        exit 0
    fi
    ensure_venv
    mkdir -p "$LOG_DIR"
    nohup "$PYTHON" backup.py >> "$LOG_DIR/daemon.log" 2>&1 &
    echo $! > "$PID_FILE"
    sleep 1
    if is_running; then
        echo "CPA Backup 已启动 (PID: $(cat "$PID_FILE"))"
        echo "日志文件: $LOG_DIR/daemon.log"
    else
        echo "启动失败，请检查日志: $LOG_DIR/daemon.log"
        exit 1
    fi
}

do_stop() {
    if ! is_running; then
        echo "CPA Backup 未在运行"
        exit 0
    fi
    pid=$(cat "$PID_FILE")
    kill "$pid"
    # 等待进程退出，最多 10 秒
    for i in $(seq 1 10); do
        if ! kill -0 "$pid" 2>/dev/null; then
            rm -f "$PID_FILE"
            echo "CPA Backup 已停止"
            exit 0
        fi
        sleep 1
    done
    # 超时强制杀
    kill -9 "$pid" 2>/dev/null
    rm -f "$PID_FILE"
    echo "CPA Backup 已强制停止"
}

do_restart() {
    do_stop
    sleep 1
    do_start
}

do_status() {
    if is_running; then
        pid=$(cat "$PID_FILE")
        echo "CPA Backup 运行中 (PID: $pid)"
        if [ -f "$LOG_DIR/daemon.log" ]; then
            echo ""
            echo "最近日志:"
            tail -5 "$LOG_DIR/daemon.log"
        fi
    else
        echo "CPA Backup 未在运行"
    fi
}

case "${1:-}" in
    start)   do_start ;;
    stop)    do_stop ;;
    restart) do_restart ;;
    status)  do_status ;;
    --once)
        ensure_venv
        exec "$PYTHON" backup.py --once "${@:2}"
        ;;
    *)
        echo "用法: $0 {start|stop|restart|status|--once}"
        echo ""
        echo "  start    后台启动 daemon 模式"
        echo "  stop     停止 daemon"
        echo "  restart  重启 daemon"
        echo "  status   查看运行状态和最近日志"
        echo "  --once   前台单次执行"
        exit 1
        ;;
esac
