"""
受注案件用 自動化ツールキット

案件ごとに config.json を書くだけで
「定期収集 → 条件フィルタ → 通知 → 記録 → ダッシュボード」が動く雛形。

使い方:
    python -m toolkit.watcher            # 監視ループを回す
    python -m toolkit.dashboard          # ダッシュボードを開く
    python -m toolkit.watcher --once     # 1回だけ実行（動作確認用）
"""

__version__ = "1.0.0"
