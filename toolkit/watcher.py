"""
監視ループ本体。

app.py の monitor_loop（収集 → NGワード/必須ワード/価格でフィルタ → 通知 →
記録、429/403 でバックオフ）を、収集元を差し替えられる形に一般化したもの。

    python -m toolkit.watcher              # 常駐して回し続ける
    python -m toolkit.watcher --once       # 1周だけ（動作確認・cron向け）
    python -m toolkit.watcher --config x.json
"""

import argparse
import os
import random
import re
import sys
import threading
import time

from . import notify, sources
from .store import Store, load_json

# ===== パス設定 =====
# PyInstaller の onefile で固めたとき、設定ファイルは exe と同じ場所に置く。
# sys._MEIPASS（展開先の一時ディレクトリ）ではないことに注意。
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    BASE_DIR = os.path.dirname(BASE_DIR)  # リポジトリルート

DEFAULT_CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

DEFAULT_CONFIG = {
    "label": "自動監視",
    "data_dir": os.path.join(BASE_DIR, "data"),
    "interval_sec": 600,
    "jitter_sec": 60,
    "request_gap_sec": 3,
    "notify_first_run": False,
    "sources": [],
    "notify": [{"type": "console"}],
}

# ===== ログ（ダッシュボードと共有）=====
_log = []
_log_lock = threading.Lock()
MAX_LOG = 300


def add_log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    with _log_lock:
        _log.insert(0, line)
        del _log[MAX_LOG:]
    try:
        print(line, flush=True)
    except Exception:
        pass  # exe の --windowed では stdout が無い


def get_log():
    with _log_lock:
        return list(_log)


# ===== 設定 =====

def load_config(path=None):
    path = path or DEFAULT_CONFIG_PATH
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(path):
        loaded = load_json(path, {})
        if isinstance(loaded, dict):
            cfg.update(loaded)
    else:
        add_log(f"⚠ 設定ファイルが見つかりません: {path}")
    # 相対パスはすべて「設定ファイルの場所」を基準に解決する。
    # カレントディレクトリ基準にすると、exe をどこから起動したかで
    # 保存先が変わってしまい、顧客が出力ファイルを見失う。
    cfg_dir = os.path.dirname(os.path.abspath(path))

    def resolve(p):
        return p if os.path.isabs(p) else os.path.join(cfg_dir, p)

    cfg["data_dir"] = resolve(cfg["data_dir"])
    for n in cfg.get("notify") or []:
        if n.get("type") == "file" and n.get("path"):
            n["path"] = resolve(n["path"])
    for s in cfg.get("sources") or []:
        if s.get("type") == "csv" and s.get("path"):
            s["path"] = resolve(s["path"])
    return cfg


# ===== フィルタ =====

def match_filters(item, f):
    """
    設定例:
        "filters": {
          "ng_words":       ["ジャンク", "中古"],
          "required_words": ["新品"],
          "price_min": 0, "price_max": 5000,
          "title_regex": "^\\\\[急募\\\\]",
          "require_price": false
        }

    ng_words は1つでも含まれたら除外、required_words は1つでも含まれればOK
    （app.py と同じ挙動。すべて必須にすると実務でほぼヒットしなくなる）。
    """
    if not f:
        return True

    text = f"{item.get('title', '')} {item.get('summary', '')}"

    for w in f.get("ng_words", []):
        if w and w in text:
            return False

    required = f.get("required_words", [])
    if required and not any(w in text for w in required if w):
        return False

    rx = f.get("title_regex")
    if rx:
        try:
            if not re.search(rx, item.get("title", "")):
                return False
        except re.error:
            pass  # 設定ミスで監視を止めない

    price = item.get("price")
    if price is None:
        if f.get("require_price"):
            return False
    else:
        if "price_min" in f and price < f["price_min"]:
            return False
        if "price_max" in f and f["price_max"] and price > f["price_max"]:
            return False

    return True


# ===== 本体 =====

class Watcher:
    def __init__(self, config_path=None):
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        self.cfg = load_config(self.config_path)
        self.store = Store(self.cfg["data_dir"])
        self.running = False
        self._thread = None
        self._first_run = len(self.store.records()) == 0

    # ---- 1つの収集元を処理 ----
    def _process_source(self, src):
        name = src.get("name") or src.get("type", "?")
        add_log(f"🔍 収集: {name}")

        items = sources.collect(src)
        add_log(f"  → {len(items)}件 取得")

        filters = src.get("filters") or self.cfg.get("filters")
        fresh = []
        for it in items:
            key = f"{name}:{it['id']}"
            if self.store.is_seen(key):
                continue
            self.store.mark_seen(key)
            if not match_filters(it, filters):
                continue
            it = dict(it)
            it["source"] = name
            fresh.append(self.store.add_record(it))

        if not fresh:
            add_log(f"  → {name}: 条件に合う新着なし")
            return []

        # 初回はサイト全件が「新着」になるため通知を抑制する。
        # これをやらないと納品初日に顧客のDiscordが数百件で埋まる。
        if self._first_run and not self.cfg.get("notify_first_run"):
            add_log(f"  → 初回のため通知抑制（{len(fresh)}件を既読として記録）")
            return []

        add_log(f"  ✅ 新着 {len(fresh)}件")
        return fresh

    # ---- 1周 ----
    def run_once(self):
        self.cfg = load_config(self.config_path)  # 設定の再読み込み（再起動不要にする）
        srcs = self.cfg.get("sources", [])
        if not srcs:
            add_log("⚠ sources が空です。config.json を確認してください。")
            return []

        all_fresh = []
        gap = self.cfg.get("request_gap_sec", 3)

        for i, src in enumerate(srcs):
            if not self.running and self._thread:
                break
            if src.get("enabled") is False:
                continue
            try:
                all_fresh.extend(self._process_source(src))
            except PermissionError as e:
                # robots.txt 拒否。設定が間違っているので待っても直らない。
                add_log(f"🚫 {e}")
            except Exception as e:
                err = str(e)
                add_log(f"❌ エラー ({src.get('name', '?')}): {err[:120]}")
                if any(c in err for c in ("429", "403", "503")):
                    add_log("🔄 アクセス制限の可能性。3分待機します...")
                    self._sleep(180)
            if i < len(srcs) - 1:
                self._sleep(gap)

        if all_fresh:
            notify.dispatch(self.cfg.get("notify"), all_fresh,
                            self.cfg.get("label", ""), logger=add_log)

        self._first_run = False
        return all_fresh

    def _sleep(self, sec):
        """停止指示に素早く反応する待機。"""
        end = time.time() + sec
        while time.time() < end:
            if self._thread and not self.running:
                return
            time.sleep(min(1, max(0, end - time.time())))

    # ---- 常駐 ----
    def run_forever(self):
        self.running = True
        add_log(f"▶ 監視開始: {self.cfg.get('label', '')}")
        try:
            while self.running:
                try:
                    self.run_once()
                except Exception as e:
                    # ここで捕まえないと常駐ツールが黙って死ぬ
                    add_log(f"💥 想定外のエラー: {str(e)[:150]}")
                if not self.running:
                    break
                wait = self.cfg.get("interval_sec", 600) + random.randint(
                    0, max(0, self.cfg.get("jitter_sec", 0))
                )
                add_log(f"⏳ 次回まで {wait}秒 待機")
                self._sleep(wait)
        finally:
            self.running = False
            add_log("■ 監視停止")

    def start_background(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self.run_forever, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False


def main():
    ap = argparse.ArgumentParser(description="定期収集 → 条件フィルタ → 通知")
    ap.add_argument("--config", default=None, help="設定ファイルのパス")
    ap.add_argument("--once", action="store_true", help="1周だけ実行して終了")
    args = ap.parse_args()

    w = Watcher(args.config)
    if args.once:
        fresh = w.run_once()
        add_log(f"完了: 新着 {len(fresh)}件")
    else:
        try:
            w.run_forever()
        except KeyboardInterrupt:
            w.stop()


if __name__ == "__main__":
    main()
