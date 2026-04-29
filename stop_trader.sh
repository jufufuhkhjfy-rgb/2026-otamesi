#!/bin/bash
# AI株式デイトレードシミュレーター - 停止スクリプト

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -f trader.pid ]; then
    echo "📭 trader.pid が見つかりません（起動していない可能性）"
    exit 0
fi

PID=$(cat trader.pid)
if kill -0 "$PID" 2>/dev/null; then
    kill "$PID"
    rm trader.pid
    echo "🛑 AI株式デイトレーダーを停止しました (PID: $PID)"
else
    rm trader.pid
    echo "📭 プロセスはすでに終了しています"
fi
