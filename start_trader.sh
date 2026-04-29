#!/bin/bash
# AI株式デイトレードシミュレーター - バックグラウンド起動スクリプト
# PC を閉じてもトレードが継続されます

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 既存プロセスがあれば確認
if [ -f trader.pid ]; then
    OLD_PID=$(cat trader.pid)
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "⚠️  すでに起動中です (PID: $OLD_PID)"
        echo "停止するには: bash stop_trader.sh"
        exit 1
    else
        rm trader.pid
    fi
fi

# ANTHROPIC_API_KEY のチェック
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "⚠️  警告: ANTHROPIC_API_KEY が未設定です"
    echo "   Claude AI の代わりにルールベース取引が使われます"
    echo "   設定方法: export ANTHROPIC_API_KEY=your_api_key"
    echo ""
fi

echo "🚀 AI株式デイトレードシミュレーター起動中..."
nohup python3 trader_app.py > trader.log 2>&1 &
echo $! > trader.pid
sleep 2

if kill -0 "$(cat trader.pid)" 2>/dev/null; then
    echo "✅ 起動成功！ PID: $(cat trader.pid)"
    echo "📊 ダッシュボード: http://localhost:5001"
    echo "📝 ログ確認: tail -f trader.log"
    echo "🛑 停止: bash stop_trader.sh"
else
    echo "❌ 起動に失敗しました。trader.log を確認してください。"
    exit 1
fi
