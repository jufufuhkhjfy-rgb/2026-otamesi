"""
納品ツールのエントリポイント。

PyInstaller はパッケージ相対の `-m toolkit.dashboard` を直接固められないため、
exe 化用にこのファイルを起点にする。

    python run_tool.py                    # ダッシュボード + 監視を起動
    python run_tool.py --config x.json    # 設定ファイルを指定
"""

from toolkit.dashboard import main

if __name__ == "__main__":
    main()
