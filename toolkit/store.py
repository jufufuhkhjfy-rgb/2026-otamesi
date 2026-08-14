"""
JSON 永続化。

app.py の load_purchases / save_purchases / load_misses / save_misses と同じ
「1ファイル1リスト、UTF-8、indent=2」のパターンを一般化したもの。

案件では SQLite を使うほどのデータ量にならないことがほとんどで、
JSON なら顧客が中身を直接見られる（＝説明が要らない）ため納品向き。
"""

import json
import os
import tempfile
import threading
import time

_lock = threading.RLock()


def _atomic_write(path, data):
    """
    書き込み中にプロセスが落ちてもファイルを壊さない。

    常駐ツールは顧客がタスクトレイから強制終了することがあり、
    通常の open(w) だと履歴ファイルが空になって問い合わせになる。
    """
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def load_json(path, default=None):
    if not os.path.exists(path):
        return default if default is not None else []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        # 壊れたファイルで起動不能にしない。退避してデフォルトで続行する。
        try:
            os.replace(path, path + ".broken")
        except Exception:
            pass
        return default if default is not None else []


def save_json(path, data):
    with _lock:
        _atomic_write(path, data)


class Store:
    """
    収集結果の保存先。

    - records: 通知済みアイテムの履歴（新しい順）
    - seen:    通知済みキーの集合。再起動しても重複通知しないための要。
    """

    def __init__(self, data_dir, max_records=5000, max_seen=20000):
        self.data_dir = data_dir
        self.records_path = os.path.join(data_dir, "records.json")
        self.seen_path = os.path.join(data_dir, "seen.json")
        self.max_records = max_records
        self.max_seen = max_seen
        os.makedirs(data_dir, exist_ok=True)
        self._records = load_json(self.records_path, [])
        self._seen = list(load_json(self.seen_path, []))
        self._seen_set = set(self._seen)

    # ----- 重複判定 -----
    def is_seen(self, key):
        return key in self._seen_set

    def mark_seen(self, key):
        if key in self._seen_set:
            return
        self._seen_set.add(key)
        self._seen.append(key)
        if len(self._seen) > self.max_seen:
            # 古い順に捨てる
            drop = self._seen[: len(self._seen) - self.max_seen]
            self._seen = self._seen[len(self._seen) - self.max_seen :]
            self._seen_set.difference_update(drop)
        save_json(self.seen_path, self._seen)

    # ----- 履歴 -----
    def add_record(self, record):
        rec = dict(record)
        rec.setdefault("found_at", time.strftime("%Y-%m-%d %H:%M:%S"))
        with _lock:
            self._records.insert(0, rec)
            del self._records[self.max_records :]
            save_json(self.records_path, self._records)
        return rec

    def records(self):
        return list(self._records)

    def clear(self):
        with _lock:
            self._records = []
            self._seen = []
            self._seen_set = set()
            save_json(self.records_path, [])
            save_json(self.seen_path, [])
