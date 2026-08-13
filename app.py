import sys
import os
import json
import time
import uuid
import random
import threading
import webbrowser
import requests
from flask import Flask, Response, request, jsonify

# ===== パス設定 =====
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")

DEFAULT_SETTINGS = {
    "webhook_url": "",
    "claude_api_key": "",
    "searches": {
        "妖怪ウォッチ 真打": 2000,
        "妖怪ウォッチ スキヤキ": 3000,
        "妖怪ウォッチ スシ": 1000,
        "妖怪ウォッチ テンプラ": 1000,
        "妖怪ウォッチ 白犬隊": 1200,
        "妖怪ウォッチ 赤猫団": 2200,
        "ポケモン エメラルド": 3000
    },
    "ng_words": ["ジャンク", "壊れ", "オークション"],
    "wait_min": 5,
    "wait_max": 15
}

# ===== 状態管理 =====
flask_app = Flask(__name__)
running = False
monitor_thread = None
checked_items = set()
recent_hits = []
log_messages = []
_lock = threading.Lock()


def add_log(msg):
    with _lock:
        t = time.strftime("%H:%M:%S")
        log_messages.insert(0, f"[{t}] {msg}")
        if len(log_messages) > 200:
            log_messages.pop()


def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return DEFAULT_SETTINGS.copy()


SETTINGS_BACKUP_FILE = os.path.join(BASE_DIR, "settings_backup.json")

def save_settings(settings):
    # 現在の設定をバックアップ
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                backup = f.read()
            with open(SETTINGS_BACKUP_FILE, 'w', encoding='utf-8') as f:
                f.write(backup)
        except Exception:
            pass
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


# ===== 購入履歴管理 =====
PURCHASES_FILE = os.path.join(BASE_DIR, "purchases.json")

def load_purchases():
    if os.path.exists(PURCHASES_FILE):
        try:
            with open(PURCHASES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_purchases(purchases):
    with open(PURCHASES_FILE, 'w', encoding='utf-8') as f:
        json.dump(purchases, f, ensure_ascii=False, indent=2)


# ===== DPoP 認証 =====
import base64 as _b64
import hashlib as _hashlib

def _b64url(data):
    if isinstance(data, dict):
        import json as _j
        data = _j.dumps(data, separators=(',', ':')).encode()
    return _b64.urlsafe_b64encode(data).rstrip(b'=').decode()

def _make_dpop_key():
    from cryptography.hazmat.primitives.asymmetric import ec
    return ec.generate_private_key(ec.SECP256R1())

def _make_dpop_proof(private_key, method, url, nonce=None):
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

    pub = private_key.public_key().public_numbers()
    def ei(n):
        return _b64.urlsafe_b64encode(n.to_bytes(32, 'big')).rstrip(b'=').decode()

    jwk = {"kty": "EC", "crv": "P-256", "x": ei(pub.x), "y": ei(pub.y)}
    header = {"typ": "dpop+jwt", "alg": "ES256", "jwk": jwk}
    payload = {"jti": str(uuid.uuid4()), "htm": method.upper(), "htu": url, "iat": int(time.time())}
    if nonce:
        payload["nonce"] = nonce

    signing_input = f"{_b64url(header)}.{_b64url(payload)}".encode()
    sig_der = private_key.sign(signing_input, ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(sig_der)
    raw_sig = r.to_bytes(32, 'big') + s.to_bytes(32, 'big')
    return f"{signing_input.decode()}.{_b64url(raw_sig)}"

# キーペアとnonceは起動時に一度だけ生成
_dpop_key = None
_dpop_nonce = None

def _get_dpop_key():
    global _dpop_key
    if _dpop_key is None:
        _dpop_key = _make_dpop_key()
    return _dpop_key

# ===== メルカリ 検索 =====
def search_mercari(keyword):
    global _dpop_nonce

    try:
        from curl_cffi import requests as curl_req
    except ImportError:
        raise RuntimeError("curl_cffi がインストールされていません。run.bat を再実行してください。")

    API_URL = "https://api.mercari.jp/v2/entities:search"
    body = {
        "pageSize": 30,
        "pageToken": "",
        "searchSessionId": str(uuid.uuid4()),
        "indexRouting": "INDEX_ROUTING_UNSPECIFIED",
        "thumbnailTypes": [],
        "searchCondition": {
            "keyword": keyword,
            "excludeKeyword": "",
            "sort": "SORT_CREATED_TIME",
            "order": "ORDER_DESC",
            "status": ["STATUS_ON_SALE"],
            "categoryId": [], "brandId": [], "sellerId": [],
            "priceMin": 0, "priceMax": 0,
            "itemConditionId": [], "shippingPayerId": [],
            "shippingFromArea": [], "shippingMethod": [],
            "colorId": [], "hasCoupon": False,
            "attributes": [], "itemTypes": []
        },
        "userId": "",
        "withItemBrand": True,
        "withItemSize": False,
        "withItemPromotions": False,
        "withItemSizes": False,
        "includeFacets": False
    }

    key = _get_dpop_key()
    session = curl_req.Session(impersonate="chrome120")

    def make_headers():
        proof = _make_dpop_proof(key, "POST", API_URL, _dpop_nonce)
        return {
            "X-Platform": "web",
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": "https://jp.mercari.com",
            "Referer": "https://jp.mercari.com/",
            "DPoP": proof,
        }

    resp = session.post(API_URL, json=body, headers=make_headers(), timeout=15)

    # nonceが必要な場合は再試行
    if resp.status_code == 401:
        nonce = resp.headers.get("DPoP-Nonce")
        if nonce:
            _dpop_nonce = nonce
            resp = session.post(API_URL, json=body, headers=make_headers(), timeout=15)

    resp.raise_for_status()
    return resp.json()


# ===== Discord 通知 =====
def send_discord(webhook_url, keyword, name, price, url, thumbnail=None):
    embed = {
        "title": f"🔥 {keyword}",
        "description": name,
        "url": url,
        "color": 0xFF6B00,
        "fields": [
            {"name": "💰 価格", "value": f"¥{price:,}", "inline": True},
        ],
        "footer": {"text": "MeriWatch"}
    }
    if thumbnail:
        embed["thumbnail"] = {"url": thumbnail}

    try:
        requests.post(webhook_url, json={"embeds": [embed]}, timeout=5)
    except Exception as e:
        add_log(f"Discord送信エラー: {e}")


# ===== 監視ループ =====
def monitor_loop():
    global running, recent_hits
    add_log("▶ 監視開始")
    try:
        while running:
            settings = load_settings()
            searches = settings.get("searches", {})
            ng_words = settings.get("ng_words", [])
            webhook_url = settings.get("webhook_url", "")

            for keyword, search_cfg in searches.items():
                if not running:
                    break

                # 設定の解析（int or dict両対応）
                if isinstance(search_cfg, dict):
                    max_price  = search_cfg.get("max_price", 999999)
                    required   = search_cfg.get("required", [])
                    ng_extra   = search_cfg.get("ng_extra", [])
                else:
                    max_price  = int(search_cfg)
                    required   = []
                    ng_extra   = []

                try:
                    add_log(f"検索中: {keyword}")
                    result = search_mercari(keyword)
                    items = result.get("items", [])
                    hit_count = 0

                    # 相場計算（フィルタ前の全件）
                    all_prices = []
                    for it in items:
                        p = it.get("price", 0)
                        if isinstance(p, str):
                            p = int(p.replace(",","").replace("¥","").strip() or 0)
                        if int(p) > 0:
                            all_prices.append(int(p))
                    if all_prices:
                        avg_p = sum(all_prices) // len(all_prices)
                        min_p = min(all_prices)
                        add_log(f"  相場: 平均¥{avg_p:,} / 最安¥{min_p:,} ({len(all_prices)}件)")

                    for item in items:
                        item_id = item.get("id", "")
                        if not item_id or item_id in checked_items:
                            continue

                        checked_items.add(item_id)

                        name = item.get("name", "")
                        price = item.get("price", 0)
                        if isinstance(price, str):
                            price = int(price.replace(",", "").replace("¥", "").strip() or 0)
                        price = int(price)
                        thumbnails = item.get("thumbnails", [])
                        thumbnail = thumbnails[0] if thumbnails else ""

                        # グローバルNGワード
                        if any(word in name for word in ng_words):
                            continue
                        # キーワード個別NGワード
                        if any(word in name for word in ng_extra):
                            continue
                        # 必須ワード（1つでも含まれていればOK）
                        if required and not any(word in name for word in required):
                            continue

                        if 0 < price <= max_price:
                            url = f"https://jp.mercari.com/item/{item_id}"
                            hit = {
                                "keyword": keyword,
                                "name": name,
                                "price": price,
                                "url": url,
                                "thumbnail": thumbnail,
                                "time": time.strftime("%H:%M:%S")
                            }
                            with _lock:
                                recent_hits.insert(0, hit)
                                recent_hits[:] = recent_hits[:100]

                            hit_count += 1

                            if webhook_url:
                                send_discord(webhook_url, keyword, name, price, url, thumbnail)

                            add_log(f"ヒット ¥{price:,} {name[:25]}")

                    if hit_count == 0:
                        add_log(f"  → {keyword}: 新着なし ({len(items)}件確認)")

                except Exception as e:
                    err = str(e)
                    add_log(f"エラー ({keyword}): {err[:80]}")
                    # ブロック検知時はDPoP鍵リセット＋長めに待機
                    if "401" in err or "403" in err or "429" in err or "503" in err:
                        global _dpop_key, _dpop_nonce
                        _dpop_key = None
                        _dpop_nonce = None
                        add_log("DPoP鍵リセット。3分待機してから再開します...")
                        for _ in range(180):
                            if not running:
                                break
                            time.sleep(1)
                        continue

            if not running:
                break

            wait = random.randint(
                settings.get("wait_min", 5),
                settings.get("wait_max", 15)
            )
            add_log(f"{wait}秒待機...")
            for _ in range(wait):
                if not running:
                    break
                time.sleep(1)

    except Exception as e:
        add_log(f"監視スレッド異常終了: {str(e)[:80]}")
    finally:
        running = False
        add_log("■ 監視停止")


# ===== 管理画面 HTML =====
HTML = r"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MeriWatch</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;600;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  /* 英数字は Segoe UI、日本語は Noto Sans JP。オフライン(.exe実行時)は Yu Gothic UI / Meiryo に確実に落ちる */
  font-family: 'Segoe UI', system-ui, 'Noto Sans JP', 'Yu Gothic UI', 'Meiryo', sans-serif;
  background: #0d1117; color: #e6edf3; min-height: 100vh;
  font-size: 16px; line-height: 1.8; letter-spacing: 0.02em;
  -webkit-font-smoothing: antialiased;
}
/* 金額・数値は等幅数字にして桁を揃える */
.stat-val, .hit-price, .summary-value, .kw-price-input, .rank-num,
.purchase-table td, .profit-preview .big { font-variant-numeric: tabular-nums; }

/* ===== アイコン ===== */
.ico {
  width: 18px; height: 18px; flex-shrink: 0;
  fill: none; stroke: currentColor; stroke-width: 1.8;
  stroke-linecap: round; stroke-linejoin: round;
}
.ico-sm { width: 15px; height: 15px; stroke-width: 2; }
.brand-mark {
  display: inline-flex; align-items: center; justify-content: center;
  width: 30px; height: 30px; border-radius: 8px;
  background: #1f6feb; color: #fff;
}

/* ===== 押下フィードバック =====
   全ボタン共通。沈み込み(1px)＋影の消失で物理的な手応えを出す。
   transform は 70ms と短くし、跳ねる動きは付けない。 */
button {
  transition: background .15s ease, border-color .15s ease, color .15s ease,
              box-shadow .15s ease, opacity .15s ease, transform .07s ease;
}
button:active { transform: translateY(1px); }
button:focus-visible { outline: 2px solid #58a6ff; outline-offset: 2px; }
button:disabled { opacity: .45; cursor: not-allowed; transform: none; }

.header { background: #161b22; padding: 16px 24px; border-bottom: 1px solid #30363d; display: flex; align-items: center; gap: 12px; position: sticky; top: 0; z-index: 200; }
.header h1 { font-size: 1.3em; font-weight: 700; letter-spacing: 0.05em; }
.header-right { margin-left: auto; display: flex; align-items: center; gap: 10px; }

.tab-nav { display: flex; gap: 4px; background: #161b22; padding: 8px 24px 0; border-bottom: 1px solid #30363d; overflow-x: auto; }
.tab-btn { display: inline-flex; align-items: center; gap: 8px; padding: 11px 18px; border: none; border-radius: 8px 8px 0 0; background: transparent; color: #b6c2ce; font-size: 1em; font-weight: 600; cursor: pointer; border-bottom: 3px solid transparent; white-space: nowrap; font-family: inherit; }
.tab-btn.active { color: #e6edf3; border-bottom-color: #1f6feb; }
.tab-btn:hover { color: #e6edf3; background: #1c222b; }
.tab-btn:active { transform: none; }
.tab-btn .ico { opacity: .75; }
.tab-btn.active .ico { opacity: 1; color: #58a6ff; }

.tab-content { display: none; }
.tab-content.active { display: block; }

.badge { display: inline-flex; align-items: center; gap: 6px; padding: 5px 14px; border-radius: 999px; font-size: 0.9em; font-weight: 700; }
.badge.stopped { background: #21262d; color: #b6c2ce; }
.badge.running { background: #1a4a2e; color: #3fb950; }
.badge .dot { width: 8px; height: 8px; border-radius: 50%; background: currentColor; }
.badge.running .dot { box-shadow: 0 0 6px currentColor; animation: pulse 2s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }

.container { max-width: 1280px; margin: 0 auto; padding: 24px; }
.layout { display: grid; grid-template-columns: 300px 1fr; gap: 16px; }

.card { background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 20px; margin-bottom: 16px; }
.card-title { font-size: 1em; font-weight: 700; color: #c3ccd6; letter-spacing: 0.02em; margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid #21262d; }

.btn { display: flex; align-items: center; justify-content: center; gap: 8px; width: 100%; padding: 13px; border: none; border-radius: 8px; font-size: 1em; font-weight: 700; cursor: pointer; margin-bottom: 8px; font-family: inherit; letter-spacing: 0.03em; box-shadow: 0 1px 0 rgba(0,0,0,.3); }
.btn:hover { filter: brightness(1.12); }
.btn:active { transform: translateY(1px); box-shadow: none; filter: brightness(.95); }
.btn .ico { fill: currentColor; stroke: none; }
.btn-start { background: #238636; color: #fff; }
.btn-stop  { background: #da3633; color: #fff; }

.stat-row { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid #21262d; font-size: 0.95em; }
.stat-row:last-child { border-bottom: none; }
.stat-val { font-weight: 700; color: #3fb950; font-size: 1.2em; }

label { display: block; font-size: 0.95em; font-weight: 700; color: #c3ccd6; margin-bottom: 6px; margin-top: 14px; letter-spacing: 0.02em; }
label:first-child { margin-top: 0; }
input, textarea { width: 100%; background: #0d1117; border: 1px solid #30363d; border-radius: 6px; padding: 10px 12px; color: #e6edf3; font-size: 1em; resize: vertical; font-family: inherit; line-height: 1.5; }
input:focus, textarea:focus { outline: none; border-color: #58a6ff; box-shadow: 0 0 0 3px rgba(88,166,255,0.15); }

.save-btn { margin-top: 12px; width: 100%; padding: 11px; background: #1f6feb; border: none; border-radius: 6px; color: #fff; font-weight: 700; cursor: pointer; font-size: 0.95em; font-family: inherit; }
.save-btn:hover { background: #388bfd; }
.save-btn:active { background: #1a5fcc; }
.action-btn:active, .add-kw-btn:active, .chip:active,
.big-btn:active, .modal-btns button:active { filter: brightness(.9); }

/* 日本語を含むログなので、等幅の後ろに日本語フォントを必ず置く */
.log-box { background: #0d1117; border-radius: 6px; padding: 12px; height: 240px; overflow-y: auto; font-family: 'Consolas', 'Courier New', 'Noto Sans JP', 'Yu Gothic UI', 'Meiryo', monospace; font-size: 0.95em; border: 1px solid #21262d; line-height: 1.85; }
.log-line { color: #b6c2ce; padding: 2px 0; }
.log-line.hit { color: #3fb950; font-weight: 600; }
.log-line.error { color: #f85149; font-weight: 600; }

.hits-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid #21262d; }
.count-badge { background: #da3633; color: #fff; font-size: 0.9em; font-weight: 700; padding: 3px 10px; border-radius: 999px; }

.hit-item { background: #0d1117; border: 1px solid #21262d; border-radius: 8px; padding: 13px 15px; margin-bottom: 10px; transition: border-color 0.2s; }
.hit-item:hover { border-color: #388bfd; }
.hit-top { display: flex; gap: 12px; align-items: flex-start; }
.hit-thumb { width: 64px; height: 64px; border-radius: 6px; object-fit: cover; background: #21262d; flex-shrink: 0; }
.hit-info { flex: 1; min-width: 0; }
.hit-name { font-size: 1em; line-height: 1.5; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.hit-name a { color: #6cb2ff; text-decoration: none; }
.hit-name a:hover { text-decoration: underline; }
.hit-price { color: #3fb950; font-weight: 700; font-size: 1.3em; margin-top: 5px; letter-spacing: 0.02em; }
.hit-meta { font-size: 0.95em; color: #b6c2ce; margin-top: 4px; }
.hit-actions { display: flex; gap: 8px; margin-top: 10px; flex-wrap: wrap; }
.hit-actions button { display: inline-flex; align-items: center; gap: 6px; }
.buy-btn  { padding: 7px 14px; background: #1f6feb; border: 1px solid #1f6feb; border-radius: 6px; color: #fff; font-size: 0.95em; font-weight: 600; cursor: pointer; box-shadow: 0 1px 0 rgba(0,0,0,.25); }
.buy-btn:hover  { background: #388bfd; border-color: #388bfd; }
.buy-btn:active { box-shadow: none; background: #1a5fcc; }
.miss-btn { padding: 7px 12px; background: #21262d; border: 1px solid #4a2c2c; border-radius: 6px; color: #ff7b72; font-size: 0.95em; font-weight: 600; cursor: pointer; }
.miss-btn:hover { background: #3a1a1a; border-color: #6e3030; }
.miss-btn:active { background: #2b1212; }
.ng-btn   { padding: 7px 12px; background: #21262d; border: 1px solid #30363d; border-radius: 6px; color: #b6c2ce; font-size: 0.95em; font-weight: 600; cursor: pointer; }
.ng-btn:hover   { background: #30363d; color: #e6edf3; }
.ng-btn:active  { background: #1a1f26; }

.empty { text-align: center; color: #8b97a5; padding: 44px; font-size: 1em; }

/* 収益管理タブ */
.summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 16px; margin-bottom: 24px; }
.chart-box { background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 20px; }
.chart-box h3 { font-size: 1em; color: #c3ccd6; margin-bottom: 14px; letter-spacing: 0.02em; }

/* ===== 分析タブ ===== */
/* 冒頭に要約文を置き、指標を選ぶと下のグラフが切り替わる構成 */
.an-hero { padding: 2px 0 22px; }
.an-hero h2 { font-size: 1.5em; font-weight: 700; line-height: 1.55; letter-spacing: 0.01em; }
.an-hero p { margin-top: 7px; color: #a3b0bd; font-size: 0.95em; }

.an-panel { background: #161b22; border: 1px solid #30363d; border-radius: 10px; overflow: hidden; margin-bottom: 16px; }
.metric-row { display: grid; grid-template-columns: repeat(4, 1fr); border-bottom: 1px solid #21262d; }
.metric { background: none; border: none; border-right: 1px solid #21262d; border-bottom: 3px solid transparent; padding: 15px 18px; text-align: left; cursor: pointer; font-family: inherit; color: #a3b0bd; }
.metric:last-child { border-right: none; }
.metric:hover { background: #1a2029; }
.metric:active { transform: none; }
.metric.active { background: #1a2029; border-bottom-color: #1f6feb; color: #e6edf3; }
.metric-label { display: block; font-size: 0.92em; font-weight: 600; }
.metric-value { display: block; margin-top: 5px; font-size: 1.45em; font-weight: 700; color: #e6edf3; font-variant-numeric: tabular-nums; }
.an-chart { height: 330px; padding: 20px; }
.an-grid { display: grid; grid-template-columns: 1.4fr 1fr; gap: 16px; align-items: start; }
@media (max-width: 1080px) {
  .an-grid { grid-template-columns: 1fr; }
  .metric-row { grid-template-columns: repeat(2, 1fr); }
}

.rank-table { width: 100%; border-collapse: collapse; font-size: 0.95em; }
.rank-table th { text-align: left; padding: 11px 12px; color: #b6c2ce; font-size: 0.92em; font-weight: 700; letter-spacing: 0.02em; border-bottom: 1px solid #30363d; }
.rank-table td { padding: 12px; border-bottom: 1px solid #21262d; font-size: 0.98em; }
.rank-table tr:last-child td { border-bottom: none; }
.rank-table tr:hover td { background: #1c2129; }
/* 順位はメダル絵文字ではなく落ち着いたバッジで示す */
.rank-num { display: inline-flex; align-items: center; justify-content: center; width: 25px; height: 25px; border-radius: 8px; background: #21262d; color: #a3b0bd; font-size: 0.88em; font-weight: 700; }
.rank-num.top1 { background: #3a3116; color: #e3b341; }
.rank-num.top2 { background: #2d323a; color: #c9d1d9; }
.rank-num.top3 { background: #33251a; color: #d18d5b; }

/* 分析タブを開いたときの入場。上から順に立ち上がり、数値とグラフの
   カウントアップに視線が向くようにする */
@keyframes an-rise { from { opacity: 0; transform: translateY(7px); } to { opacity: 1; transform: none; } }
.an-animate .an-hero,
.an-animate .an-panel,
.an-animate .an-grid > * { animation: an-rise .45s ease-out both; }
.an-animate .an-panel        { animation-delay: .07s; }
.an-animate .an-grid > *:nth-child(1) { animation-delay: .14s; }
.an-animate .an-grid > *:nth-child(2) { animation-delay: .21s; }
/* 動きを減らす設定の環境では止める */
@media (prefers-reduced-motion: reduce) {
  .an-animate .an-hero,
  .an-animate .an-panel,
  .an-animate .an-grid > * { animation: none; }
}
.summary-card { background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 20px; text-align: center; }
.summary-label { font-size: 0.95em; font-weight: 600; color: #b6c2ce; margin-bottom: 9px; letter-spacing: 0.02em; }
.summary-value { font-size: 1.6em; font-weight: 700; color: #e6edf3; letter-spacing: 0.02em; }
.summary-value.green { color: #3fb950; }
.summary-value.red { color: #f85149; }

/* 表の見出し行。件数を右に添える */
.table-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid #21262d; }
.count-pill { background: #21262d; color: #b6c2ce; border: 1px solid #30363d; font-size: 0.88em; font-weight: 700; padding: 2px 11px; border-radius: 20px; font-variant-numeric: tabular-nums; }
.purchase-table { width: 100%; border-collapse: collapse; font-size: 0.95em; }
/* 11列あるため、見出しやバッジが単語の途中で折り返さないよう nowrap で固定する */
.purchase-table th { text-align: left; padding: 11px 9px; color: #b6c2ce; font-weight: 700; border-bottom: 1px solid #30363d; font-size: 0.92em; letter-spacing: 0.02em; white-space: nowrap; }
.purchase-table td { padding: 13px 9px; border-bottom: 1px solid #21262d; vertical-align: middle; font-size: 0.98em; }
.purchase-table tr:hover td { background: #1c2129; }
/* 金額・状態・操作は折り返させない。商品名とメモだけが可変幅を受け持つ */
.purchase-table td.nowrap, .purchase-table th.nowrap { white-space: nowrap; }
.p-thumb { width: 46px; height: 46px; border-radius: 6px; object-fit: cover; background: #21262d; }
.p-name { max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.p-name a { color: #6cb2ff; text-decoration: none; }
/* 色は意味のある箇所だけに使う。利益(金額)のみ着色し、利益率はニュートラルにする */
.profit-pos { color: #3fb950; font-weight: 700; }
.profit-neg { color: #f85149; font-weight: 700; }
.rate-cell { color: #c3ccd6; font-weight: 600; }
.rate-cell.neg { color: #f85149; }
.action-btn { display: inline-flex; align-items: center; padding: 6px 12px; border: none; border-radius: 6px; cursor: pointer; font-size: 0.95em; font-weight: 600; margin-right: 5px; white-space: nowrap; }
/* 一覧に何度も並ぶ操作はべた塗りにせず、面と枠線で示す */
.sell-btn { background: #21262d; color: #56d364; border: 1px solid #2f4a38; }
.sell-btn:hover { background: #1b2a22; border-color: #3fb950; }
.listing-btn { background: #21262d; color: #c3ccd6; border: 1px solid #30363d; }
.listing-btn:hover { background: #30363d; color: #e6edf3; }
.del-btn { background: #21262d; color: #b6c2ce; border: 1px solid #30363d; }
.del-btn:hover { background: #3a1a1a; color: #ff7b72; border-color: #6e3030; }
.memo-input { background: #0d1117; border: 1px solid #30363d; border-radius: 6px; padding: 5px 8px; color: #e6edf3; font-size: 0.95em; width: 130px; }

/* モーダル */
.modal-overlay { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.75); z-index: 500; justify-content: center; align-items: center; }
.modal-overlay.open { display: flex; }
.modal { background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 24px; width: 460px; max-width: 95vw; }
.modal h3 { font-size: 1.25em; margin-bottom: 18px; }
.modal-name { font-size: 0.98em; color: #c3ccd6; margin-bottom: 14px; padding: 10px; background: #0d1117; border-radius: 6px; word-break: break-all; }
.modal label { margin-top: 12px; }
.profit-preview { margin-top: 16px; padding: 14px; background: #0d1117; border-radius: 8px; font-size: 0.95em; }
.profit-preview .big { font-size: 1.45em; font-weight: 700; }
.modal-btns { display: flex; gap: 10px; margin-top: 18px; }
.modal-btns button { flex: 1; padding: 12px; border: none; border-radius: 8px; font-weight: 600; font-size: 0.98em; cursor: pointer; }
.modal-ok { background: #238636; color: #fff; }
.modal-cancel { background: #21262d; color: #b6c2ce; }

.toast { position: fixed; bottom: 26px; right: 26px; background: #238636; color: #fff; padding: 12px 20px; border-radius: 8px; font-size: 0.98em; font-weight: 600; display: none; z-index: 999; }

/* ===== 設定タブ ===== */
.settings-save-bar { display: flex; gap: 8px; margin-bottom: 24px; }
.settings-save-bar .big-btn { padding: 13px 30px; border: none; border-radius: 8px; font-size: 1em; font-weight: 700; cursor: pointer; }
.btn-save-big  { background: #238636; color: #fff; }
.btn-undo-big  { background: #21262d; border: 1px solid #30363d; color: #b6c2ce; }
.btn-save-big:hover { background: #2ea043; }
.btn-undo-big:hover { background: #30363d; color: #e6edf3; }

.kw-card { background: #0d1117; border: 1px solid #30363d; border-radius: 10px; padding: 16px; margin-bottom: 12px; }
.kw-header { display: flex; gap: 10px; align-items: center; margin-bottom: 12px; }
.kw-dot { width: 13px; height: 13px; border-radius: 50%; flex-shrink: 0; }
.kw-name-input { flex: 1; background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 8px 11px; color: #e6edf3; font-size: 1em; font-family: inherit; font-weight: 500; }
.kw-name-input:focus { outline: none; border-color: #58a6ff; box-shadow: 0 0 0 3px rgba(88,166,255,0.15); }
.kw-price-wrap { display: flex; align-items: center; gap: 6px; background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 5px 11px; }
.kw-price-wrap span { color: #3fb950; font-size: 0.92em; }
.kw-price-input { width: 90px; background: transparent; border: none; color: #3fb950; font-size: 1.02em; font-weight: 700; text-align: right; }
.kw-price-input:focus { outline: none; }
.kw-del-btn { background: none; border: 1px solid #30363d; border-radius: 6px; color: #b6c2ce; cursor: pointer; padding: 6px 10px; font-size: 0.98em; }
.kw-del-btn:hover { background: #3a1a1a; border-color: #da3633; color: #f85149; }

.tag-row { display: flex; align-items: center; gap: 7px; margin-top: 9px; flex-wrap: wrap; }
.tag-row-label { font-size: 0.9em; font-weight: 700; letter-spacing: 0.02em; padding: 4px 9px; border-radius: 6px; white-space: nowrap; }
.label-req { background: #1f3a5f; color: #6cb2ff; }
.label-ng  { background: #3a1a1a; color: #ff7b72; }
.tag { display: inline-flex; align-items: center; gap: 4px; padding: 4px 9px; border-radius: 999px; font-size: 0.95em; font-weight: 500; }
.req-tag { background: #1a2f4e; border: 1px solid #1f6feb; color: #79c0ff; }
.ng-tag2 { background: #2d1212; border: 1px solid #6e3030; color: #ff7b72; }
.tag button { background: none; border: none; cursor: pointer; color: inherit; padding: 0 0 0 2px; font-size: 0.9em; opacity: 0.7; line-height: 1; }
.tag button:hover { opacity: 1; }
.tag-add-input { background: #161b22; border: 1px solid #21262d; border-radius: 999px; padding: 4px 11px; color: #e6edf3; font-size: 0.95em; width: 100px; }
.tag-add-input:focus { outline: none; border-color: #58a6ff; width: 140px; transition: width 0.2s; }

.add-kw-btn { width: 100%; margin-top: 12px; padding: 12px; background: transparent; border: 1px dashed #30363d; border-radius: 8px; color: #b6c2ce; cursor: pointer; font-size: 0.98em; }
.add-kw-btn:hover { border-color: #58a6ff; color: #58a6ff; }

.global-ng-box { background: #0d1117; border-radius: 8px; padding: 14px; display: flex; flex-wrap: wrap; gap: 7px; align-items: center; }
.suggest-section { margin-top: 14px; }
.suggest-title { font-size: 0.95em; color: #b6c2ce; margin-bottom: 9px; }
.chips { display: flex; flex-wrap: wrap; gap: 7px; }
.chip { padding: 5px 13px; background: #21262d; border: 1px solid #30363d; border-radius: 999px; font-size: 0.95em; color: #b6c2ce; cursor: pointer; }
.chip:hover { background: #da3633; color: #fff; border-color: #da3633; }
/* キーワード色を文字色に使うとコントラストが 3.7:1 程度まで落ちる色が多いため、
   文字は通常色にし、色の識別は先頭のドットだけに担わせる */
.kw-badge { display: inline-flex; align-items: center; gap: 8px; padding: 6px 12px; border-radius: 8px; font-size: 0.95em; font-weight: 600; background: #1c222b; border: 1px solid #30363d; color: #e6edf3; }
.kw-badge .kw-dot { width: 8px; height: 8px; }
.kw-badge .kw-price { color: #a3b0bd; font-weight: 500; font-variant-numeric: tabular-nums; }
</style>
</head>
<body>

<div class="header">
  <span class="brand-mark">
    <svg class="ico" viewBox="0 0 24 24" style="width:17px;height:17px"><circle cx="9" cy="20" r="1.4"/><circle cx="19" cy="20" r="1.4"/><path d="M2 3h3l2.4 11.2a1.8 1.8 0 0 0 1.8 1.4h8.6a1.8 1.8 0 0 0 1.8-1.4L21.4 7H6"/></svg>
  </span>
  <h1>MeriWatch</h1>
  <div class="header-right">
    <div class="badge stopped" id="statusBadge">
      <span class="dot"></span>
      <span id="statusLabel">停止中</span>
    </div>
  </div>
</div>

<div class="tab-nav">
  <button class="tab-btn active" onclick="switchTab('monitor')"><svg class="ico" viewBox="0 0 24 24"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>監視</button>
  <button class="tab-btn" onclick="switchTab('profit')"><svg class="ico" viewBox="0 0 24 24"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>収益管理</button>
  <button class="tab-btn" onclick="switchTab('miss')"><svg class="ico" viewBox="0 0 24 24"><polyline points="23 18 13.5 8.5 8.5 13.5 1 6"/><polyline points="17 18 23 18 23 12"/></svg>買い負け</button>
  <button class="tab-btn" onclick="switchTab('analytics')"><svg class="ico" viewBox="0 0 24 24"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>分析</button>
  <button class="tab-btn" onclick="switchTab('settings')"><svg class="ico" viewBox="0 0 24 24"><line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/><line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/></svg>設定</button>
</div>

<!-- ===== 監視タブ ===== -->
<div id="tab-monitor" class="tab-content active">
<div class="container">
  <div class="layout">
    <div>
      <div class="card">
        <div class="card-title">コントロール</div>
        <button class="btn btn-start" onclick="doStart()"><svg class="ico" viewBox="0 0 24 24"><polygon points="7 4 20 12 7 20"/></svg>開始</button>
        <button class="btn btn-stop" onclick="doStop()"><svg class="ico" viewBox="0 0 24 24"><rect x="6" y="6" width="12" height="12" rx="1.5"/></svg>停止</button>
        <div style="margin-top:10px">
          <div class="stat-row"><span>検知数</span><span class="stat-val" id="hitCount">0</span></div>
          <div class="stat-row"><span>既チェック数</span><span class="stat-val" id="checkedCount">0</span></div>
        </div>
      </div>
      <div class="card" id="kwOverviewCard">
        <div class="card-title">監視中キーワード</div>
        <div id="kwOverview" style="display:flex;flex-wrap:wrap;gap:6px"></div>
      </div>
      <div class="card">
        <div class="card-title">ログ</div>
        <div class="log-box" id="logBox"></div>
      </div>
    </div>
    <div class="card" style="margin-bottom:0">
      <div class="hits-header">
        <span class="card-title" style="margin:0;padding:0;border:none">検知リスト</span>
        <span class="count-badge" id="hitBadge">0</span>
      </div>
      <div id="hitList"><div class="empty">まだ検知がありません</div></div>
    </div>
  </div>
</div>
</div>

<!-- ===== 収益管理タブ ===== -->
<div id="tab-profit" class="tab-content">
<div class="container">
  <div class="card" style="margin-bottom:16px">
    <div class="card-title">URLから商品を追加</div>
    <div style="display:flex;gap:8px;align-items:center">
      <input type="text" id="urlInput" placeholder="https://jp.mercari.com/item/m..." style="flex:1">
      <button onclick="lookupUrl()" style="padding:8px 18px;background:#1f6feb;border:none;border-radius:6px;color:#fff;font-weight:600;cursor:pointer;white-space:nowrap">商品を取得</button>
    </div>
    <div id="urlStatus" style="font-size:0.92em;color:#a3b0bd;margin-top:6px"></div>
  </div>
  <div class="summary-grid">
    <div class="summary-card">
      <div class="summary-label">仕入れ総額</div>
      <div class="summary-value" id="s-cost">¥0</div>
    </div>
    <div class="summary-card">
      <div class="summary-label">実現利益（売却済）</div>
      <div class="summary-value green" id="s-profit">¥0</div>
    </div>
    <div class="summary-card">
      <div class="summary-label">総利益（予定含む）</div>
      <div class="summary-value green" id="s-total">¥0</div>
    </div>
    <div class="summary-card">
      <div class="summary-label">平均利益率</div>
      <div class="summary-value" id="s-rate">0%</div>
    </div>
    <div class="summary-card">
      <div class="summary-label">購入数 / 売却数</div>
      <div class="summary-value" id="s-counts">0 / 0</div>
    </div>
  </div>
  <!-- 未売却＝これから動かす在庫。売却済とは別の表にして、状態列を省く -->
  <div class="card">
    <div class="table-head">
      <span class="card-title" style="margin:0;padding:0;border:none">在庫（未売却）</span>
      <span class="count-pill" id="stockCount">0</span>
    </div>
    <div style="overflow-x:auto">
      <table class="purchase-table">
        <thead>
          <tr>
            <th></th>
            <th>商品名</th>
            <th>仕入れ値</th>
            <th>想定売値</th>
            <th>送料</th>
            <th>想定利益</th>
            <th>利益率</th>
            <th>メモ</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody id="purchaseList"></tbody>
      </table>
      <div class="empty" id="purchaseEmpty" style="display:none">未売却の在庫はありません</div>
    </div>
  </div>

  <div class="card">
    <div class="table-head">
      <span class="card-title" style="margin:0;padding:0;border:none">売却済み</span>
      <span class="count-pill" id="soldCount">0</span>
    </div>
    <div style="overflow-x:auto">
      <table class="purchase-table">
        <thead>
          <tr>
            <th></th>
            <th>商品名</th>
            <th>仕入れ値</th>
            <th>売値</th>
            <th>送料</th>
            <th>利益</th>
            <th>利益率</th>
            <th>期間</th>
            <th>メモ</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody id="soldList"></tbody>
      </table>
      <div class="empty" id="soldEmpty" style="display:none">まだ売却済みの記録がありません</div>
    </div>
  </div>
</div>
</div>

<!-- ===== 設定タブ ===== -->
<div id="tab-settings" class="tab-content">
<div class="container" style="max-width:860px">
  <div class="settings-save-bar">
    <button class="big-btn btn-save-big" onclick="saveSettings()">保存</button>
    <button class="big-btn btn-undo-big" onclick="restoreSettings()">↩ 元に戻す</button>
  </div>

  <div class="card">
    <div class="card-title">Discord Webhook URL</div>
    <input type="text" id="webhookUrl" placeholder="https://discord.com/api/webhooks/...">
  </div>

  <div class="card">
    <div class="card-title">Claude API キー <span style="font-size:0.92em;font-weight:400;color:#a3b0bd">— 出品文の自動生成に使用</span></div>
    <input type="password" id="claudeApiKey" placeholder="sk-ant-...">
    <div style="font-size:0.78em;color:#a3b0bd;margin-top:6px">取得先: <a href="https://console.anthropic.com/" target="_blank" style="color:#58a6ff">console.anthropic.com</a>（無料枠あり）</div>
  </div>

  <div class="card">
    <div class="card-title">監視キーワード</div>
    <div id="kwList"></div>
    <button class="add-kw-btn" onclick="addKeyword()">＋ キーワードを追加</button>
  </div>

  <div class="card">
    <div class="card-title">グローバルNGワード <span style="font-size:0.92em;font-weight:400;color:#a3b0bd">— 全キーワードに適用（クリックで削除）</span></div>
    <div class="global-ng-box" id="globalNgTags"></div>
    <input class="tag-add-input" style="margin-top:10px;width:150px" id="globalNgInput" placeholder="追加してEnter" onkeydown="addGlobalNG(event)">
    <div class="suggest-section">
      <div class="suggest-title">おすすめNGワード（クリックで追加）</div>
      <div class="chips" id="ngSuggestChips"></div>
    </div>
  </div>
</div>
</div>

<!-- ===== 買い負けタブ ===== -->
<div id="tab-miss" class="tab-content">
<div class="container">
  <div class="card">
    <div class="card-title">買い負け履歴 <span style="font-size:0.92em;color:#a3b0bd;font-weight:400">— 他の人に買われた商品</span></div>
    <div style="overflow-x:auto">
      <table class="purchase-table">
        <thead>
          <tr><th></th><th>商品名</th><th>価格</th><th>キーワード</th><th>メモ</th><th>記録日時</th></tr>
        </thead>
        <tbody id="missList"></tbody>
      </table>
      <div class="empty" id="missEmpty">まだ買い負け記録がありません</div>
    </div>
  </div>
  <div class="card">
    <div class="card-title">キーワード別 買い負け数</div>
    <canvas id="chartMiss" style="max-height:260px"></canvas>
  </div>
</div>
</div>

<!-- ===== 分析タブ ===== -->
<div id="tab-analytics" class="tab-content">
<div class="container">
  <div class="an-hero">
    <h2 id="anHeadline">読み込み中…</h2>
    <p id="anSubline"></p>
  </div>

  <div class="an-panel">
    <div class="metric-row" id="metricRow">
      <button class="metric active" data-metric="profit" onclick="selectMetric('profit')">
        <span class="metric-label">総利益</span><span class="metric-value" id="mv-profit">—</span>
      </button>
      <button class="metric" data-metric="count" onclick="selectMetric('count')">
        <span class="metric-label">購入数</span><span class="metric-value" id="mv-count">—</span>
      </button>
      <button class="metric" data-metric="rate" onclick="selectMetric('rate')">
        <span class="metric-label">平均利益率</span><span class="metric-value" id="mv-rate">—</span>
      </button>
      <button class="metric" data-metric="days" onclick="selectMetric('days')">
        <span class="metric-label">平均売却期間</span><span class="metric-value" id="mv-days">—</span>
      </button>
    </div>
    <div class="an-chart"><canvas id="chartMain"></canvas></div>
  </div>

  <div class="an-grid">
    <div class="chart-box">
      <h3>キーワード別 ランキング</h3>
      <table class="rank-table">
        <thead>
          <tr>
            <th>順位</th>
            <th>キーワード</th>
            <th>購入</th>
            <th>売却</th>
            <th>総利益</th>
            <th>利益率</th>
            <th>期間</th>
          </tr>
        </thead>
        <tbody id="rankTable"></tbody>
      </table>
      <div class="empty" id="rankEmpty" style="display:none;padding:28px">まだデータがありません</div>
    </div>
    <div class="chart-box">
      <h3>購入数の内訳</h3>
      <div style="height:260px"><canvas id="chartCount"></canvas></div>
    </div>
  </div>
</div>
</div>

<!-- ===== 出品文生成モーダル ===== -->
<div class="modal-overlay" id="listingModal">
  <div class="modal" style="width:520px">
    <h3>出品文を生成</h3>
    <div class="modal-name" id="listing-name"></div>
    <label>状態</label>
    <select id="listing-condition" style="width:100%;background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:8px 10px;color:#e6edf3;font-size:0.9em;font-family:inherit">
      <option>新品未使用</option>
      <option>未使用に近い</option>
      <option selected>良い</option>
      <option>普通</option>
      <option>やや傷あり</option>
    </select>
    <label>付属品</label>
    <select id="listing-accessories" style="width:100%;background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:8px 10px;color:#e6edf3;font-size:0.9em;font-family:inherit">
      <option>ソフトのみ</option>
      <option>箱・説明書あり</option>
      <option>箱のみ</option>
      <option>説明書のみ</option>
      <option>付属品なし</option>
    </select>
    <label>動作確認</label>
    <select id="listing-working" style="width:100%;background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:8px 10px;color:#e6edf3;font-size:0.9em;font-family:inherit">
      <option>動作確認済み</option>
      <option>動作未確認</option>
    </select>
    <label>追加メモ（任意）</label>
    <input type="text" id="listing-memo" placeholder="例: 背面に小さな傷あり">
    <div class="modal-btns" style="margin-top:14px">
      <button class="modal-ok" id="listing-gen-btn" onclick="generateListing()">生成する</button>
      <button class="modal-cancel" onclick="closeListingModal()">閉じる</button>
    </div>
    <div id="listing-result" style="display:none;margin-top:16px">
      <div style="margin-bottom:10px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
          <span style="font-size:0.78em;font-weight:700;color:#a3b0bd;text-transform:uppercase;letter-spacing:0.06em">タイトル</span>
          <button onclick="copyText('listing-title-text')" style="padding:3px 10px;background:#21262d;border:1px solid #30363d;border-radius:6px;color:#a3b0bd;font-size:0.78em;cursor:pointer">コピー</button>
        </div>
        <div id="listing-title-text" style="background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:10px;font-size:0.9em;line-height:1.6;white-space:pre-wrap;word-break:break-all"></div>
      </div>
      <div>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
          <span style="font-size:0.78em;font-weight:700;color:#a3b0bd;text-transform:uppercase;letter-spacing:0.06em">説明文</span>
          <button onclick="copyText('listing-desc-text')" style="padding:3px 10px;background:#21262d;border:1px solid #30363d;border-radius:6px;color:#a3b0bd;font-size:0.78em;cursor:pointer">コピー</button>
        </div>
        <div id="listing-desc-text" style="background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:10px;font-size:0.92em;line-height:1.8;white-space:pre-wrap;max-height:260px;overflow-y:auto"></div>
      </div>
    </div>
  </div>
</div>

<!-- ===== 買い負けモーダル ===== -->
<div class="modal-overlay" id="missModal">
  <div class="modal">
    <h3>買い負け記録</h3>
    <div class="modal-name" id="miss-name"></div>
    <label>カテゴリ（キーワード）</label>
    <select id="miss-keyword" style="width:100%;background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:8px 10px;color:#e6edf3;font-size:0.9em;font-family:inherit">
    </select>
    <label>価格（円）</label>
    <input type="number" id="miss-price" placeholder="0">
    <label>メモ</label>
    <input type="text" id="miss-memo" placeholder="なぜ買い負けたか、状態など">
    <div class="modal-btns" style="margin-top:16px">
      <button class="modal-ok" onclick="saveMiss()">記録する</button>
      <button class="modal-cancel" onclick="closeMissModal()">キャンセル</button>
    </div>
  </div>
</div>

<!-- ===== 購入モーダル ===== -->
<div class="modal-overlay" id="purchaseModal">
  <div class="modal">
    <h3>購入記録</h3>
    <div class="modal-name" id="modal-name"></div>
    <input type="hidden" id="modal-data">
    <label>カテゴリ（キーワード）</label>
    <select id="modal-keyword" style="width:100%;background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:8px 10px;color:#e6edf3;font-size:0.9em;font-family:inherit;margin-bottom:2px"></select>
    <label>仕入れ値（円）</label>
    <input type="number" id="modal-buy" placeholder="0" oninput="updatePreview()">
    <label>売値予定（円）</label>
    <input type="number" id="modal-sell" placeholder="0" oninput="updatePreview()">
    <label>送料（円）</label>
    <input type="number" id="modal-ship" value="0" oninput="updatePreview()">
    <label>メモ</label>
    <input type="text" id="modal-memo" placeholder="状態・購入場所など">
    <div class="profit-preview">
      <div style="color:#a3b0bd;margin-bottom:6px;font-size:0.92em">予想利益（メルカリ手数料10%含む）</div>
      <span class="big" id="preview-profit">¥0</span>
      &nbsp;
      <span id="preview-rate" style="color:#a3b0bd">（0%）</span>
    </div>
    <div class="modal-btns">
      <button class="modal-ok" onclick="savePurchase()">保存</button>
      <button class="modal-cancel" onclick="closeModal()">キャンセル</button>
    </div>
  </div>
</div>

<div class="toast" id="toast">保存しました</div>

<script>
// ===== タブ切り替え =====
function switchTab(name) {
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  // ボタン内のSVGアイコンをクリックすると event.target が svg 要素になるため、
  // closest() で必ずボタン自体を掴む
  const clicked = event.target.closest('.tab-btn');
  if (clicked) clicked.classList.add('active');
  if (name === 'analytics') {
    _anAnimate = true;
    // クラスを付け直すだけでは再生されないため、間に reflow を挟んで作り直す
    const pane = document.getElementById('tab-analytics');
    pane.classList.remove('an-animate');
    void pane.offsetWidth;
    pane.classList.add('an-animate');
  }
  if (name === 'profit' || name === 'analytics') loadPurchases();
  if (name === 'miss') loadMisses();
  if (name === 'settings') loadSettings();
}

// ===== 設定（新UI） =====
const KW_COLORS = ['#1f6feb','#238636','#9b59b6','#e67e22','#da3633','#1abc9c','#f0c040','#e91e63','#00bcd4','#ff9800'];
const NG_SUGGESTS = ['ポーチ','バッグ','キーホルダー','ストラップ','缶バッジ','ピンバッジ','アクスタ','アクリル','トレカ','スリーブ','ローダー','グッズ','フィギュア','ぬいぐるみ','ガチャ','シール','ソックス','靴下','Tシャツ','パーカー','アパレル','服','攻略','ガイド','歯ブラシ','PSA','まとめ','セット','ジャンク','壊れ','液晶割れ','ラバー','クリアファイル','タオル','マグカップ','スタンプ','ぬり絵'];

let _kwData = [];
let _globalNg = [];

async function loadSettings() {
  const r = await fetch('/api/settings');
  const s = await r.json();
  document.getElementById('webhookUrl').value   = s.webhook_url    || '';
  document.getElementById('claudeApiKey').value = s.claude_api_key || '';
  _kwData = Object.entries(s.searches || {}).map(([k, v]) => {
    if (typeof v === 'object') return { kw: k, price: v.max_price, required: [...(v.required||[])], ng_extra: [...(v.ng_extra||[])] };
    return { kw: k, price: parseInt(v)||0, required: [], ng_extra: [] };
  });
  _globalNg = [...(s.ng_words || [])];
  renderKwList();
  renderGlobalNg();
  renderNgSuggests();
}

function renderKwList() {
  const el = document.getElementById('kwList');
  if (!_kwData.length) { el.innerHTML = '<div class="empty" style="padding:20px">キーワードがありません</div>'; return; }
  el.innerHTML = _kwData.map((d, i) => {
    const color = KW_COLORS[i % KW_COLORS.length];
    const reqTags = d.required.map((w,j) => `<span class="tag req-tag">${w}<button onclick="_kwData[${i}].required.splice(${j},1);renderKwList()">×</button></span>`).join('');
    const ngTags  = d.ng_extra.map((w,j) => `<span class="tag ng-tag2">${w}<button onclick="_kwData[${i}].ng_extra.splice(${j},1);renderKwList()">×</button></span>`).join('');
    return `
    <div class="kw-card">
      <div class="kw-header">
        <div class="kw-dot" style="background:${color}"></div>
        <input class="kw-name-input" value="${d.kw}" placeholder="キーワード" onchange="_kwData[${i}].kw=this.value">
        <div class="kw-price-wrap">
          <span>上限¥</span>
          <input class="kw-price-input" type="number" value="${d.price}" onchange="_kwData[${i}].price=parseInt(this.value)||0">
        </div>
        <button class="kw-del-btn" onclick="_kwData.splice(${i},1);renderKwList()" title="削除"><svg class="ico ico-sm" viewBox="0 0 24 24"><polyline points="3 6 21 6"/><path d="M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/></svg></button>
      </div>
      <div class="tag-row">
        <span class="tag-row-label label-req">必須</span>
        ${reqTags}
        <input class="tag-add-input" placeholder="追加→Enter" onkeydown="addTag(event,_kwData[${i}].required,()=>renderKwList())">
      </div>
      <div class="tag-row">
        <span class="tag-row-label label-ng">NG</span>
        ${ngTags}
        <input class="tag-add-input" placeholder="追加→Enter" onkeydown="addTag(event,_kwData[${i}].ng_extra,()=>renderKwList())">
        <button onclick="addGlobalToKw(${i})" style="padding:3px 8px;background:#21262d;border:1px solid #30363d;border-radius:12px;color:#a3b0bd;font-size:0.75em;cursor:pointer" title="グローバルNGを全部追加">＋グローバルから</button>
      </div>
    </div>`;
  }).join('');
}

function addTag(e, arr, cb) {
  if (e.key !== 'Enter') return;
  const w = e.target.value.trim();
  if (w && !arr.includes(w)) { arr.push(w); e.target.value = ''; cb(); }
}

function addKeyword() {
  _kwData.push({ kw: '', price: 1000, required: [], ng_extra: [] });
  renderKwList();
}

function addGlobalToKw(i) {
  for (const w of _globalNg) {
    if (!_kwData[i].ng_extra.includes(w)) _kwData[i].ng_extra.push(w);
  }
  renderKwList();
}

function renderGlobalNg() {
  const el = document.getElementById('globalNgTags');
  if (!_globalNg.length) { el.innerHTML = '<span style="color:#8b97a5;font-size:0.95em">まだNGワードがありません</span>'; return; }
  el.innerHTML = _globalNg.map((w,i) =>
    `<span class="tag ng-tag2" style="cursor:pointer" onclick="_globalNg.splice(${i},1);renderGlobalNg();renderNgSuggests()">${w} <span style="opacity:0.6">×</span></span>`
  ).join('');
}

function addGlobalNG(e) {
  if (e.key !== 'Enter') return;
  const w = e.target.value.trim();
  if (w && !_globalNg.includes(w)) { _globalNg.push(w); e.target.value = ''; renderGlobalNg(); renderNgSuggests(); }
}

function renderNgSuggests() {
  const el = document.getElementById('ngSuggestChips');
  el.innerHTML = NG_SUGGESTS.filter(w => !_globalNg.includes(w))
    .map(w => `<span class="chip" onclick="addSuggestNG('${w}')">${w}</span>`).join('');
}

function addSuggestNG(w) {
  if (!_globalNg.includes(w)) { _globalNg.push(w); renderGlobalNg(); renderNgSuggests(); }
}

async function saveSettings() {
  const webhook      = document.getElementById('webhookUrl').value.trim();
  const claudeApiKey = document.getElementById('claudeApiKey').value.trim();
  const searches = {};
  for (const d of _kwData) {
    if (d.kw.trim()) searches[d.kw.trim()] = { max_price: d.price, required: d.required, ng_extra: d.ng_extra };
  }
  await fetch('/api/settings', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ webhook_url: webhook, claude_api_key: claudeApiKey, searches, ng_words: _globalNg })
  });
  showToast('保存しました');
}

async function doStart() { await fetch('/api/start'); }
async function doStop()  { await fetch('/api/stop');  }

async function loadKwOverview() {
  const r = await fetch('/api/settings');
  const s = await r.json();
  const el = document.getElementById('kwOverview');
  const searches = s.searches || {};
  const keys = Object.keys(searches);
  if (!keys.length) { el.innerHTML = '<span style="color:#8b97a5;font-size:0.95em">キーワードなし</span>'; return; }
  el.innerHTML = keys.map((k, i) => {
    const v = searches[k];
    const price = typeof v === 'object' ? v.max_price : v;
    const color = KW_COLORS[i % KW_COLORS.length];
    return `<span class="kw-badge">
      <span class="kw-dot" style="background:${color}"></span>
      ${k} <span class="kw-price">¥${parseInt(price).toLocaleString()}</span>
    </span>`;
  }).join('');
}

async function lookupUrl() {
  const url = document.getElementById('urlInput').value.trim();
  const status = document.getElementById('urlStatus');
  if (!url) return;
  status.textContent = '取得中...';
  status.style.color = '#a3b0bd';
  try {
    const r = await fetch('/api/item_lookup', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ url })
    });
    const data = await r.json();
    if (!data.ok) { status.textContent = data.error; status.style.color = '#f85149'; return; }
    status.textContent = data.name ? '取得成功: ' + data.name : '商品名を手動で入力してください';
    status.style.color = '#3fb950';
    document.getElementById('urlInput').value = '';
    // ヒットとして扱いモーダルを開く
    _hits.push({ name: data.name || 'URL追加商品', price: data.price, url: data.url,
                 thumbnail: data.thumbnail, keyword: 'URL追加', time: '-' });
    openModal(_hits.length - 1);
  } catch(e) {
    status.textContent = 'エラー: ' + e.message;
    status.style.color = '#f85149';
  }
}

async function restoreSettings() {
  if (!confirm('保存前の設定に戻しますか？')) return;
  const r = await fetch('/api/settings/restore', { method: 'POST' });
  const res = await r.json();
  if (res.ok) {
    await loadSettings();
    showToast('↩ 元の設定に戻しました');
  } else {
    showToast(res.error || 'バックアップなし');
  }
}

// ===== 監視タブ =====
let _hits = [];
function renderHits(hits) {
  _hits = hits;
  const el = document.getElementById('hitList');
  if (!hits.length) { el.innerHTML = '<div class="empty">まだ検知がありません</div>'; return; }
  el.innerHTML = hits.map((h, i) => `
    <div class="hit-item">
      <div class="hit-top">
        ${h.thumbnail ? `<img class="hit-thumb" src="${h.thumbnail}" onerror="this.style.display='none'">` : '<div class="hit-thumb"></div>'}
        <div class="hit-info">
          <div class="hit-name"><a href="${h.url}" target="_blank">${h.name.replace(/</g,'&lt;')}</a></div>
          <div class="hit-price">¥${h.price.toLocaleString()}</div>
          <div class="hit-meta">${h.keyword} · ${h.time}</div>
        </div>
      </div>
      <div class="hit-actions">
        <button class="buy-btn"  onclick="openModal(${i})"><svg class="ico ico-sm" viewBox="0 0 24 24"><path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"/><line x1="3" y1="6" x2="21" y2="6"/><path d="M16 10a4 4 0 0 1-8 0"/></svg>購入</button>
        <button class="miss-btn" onclick="recordMiss(${i})"><svg class="ico ico-sm" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>買い負け</button>
        <button class="ng-btn"   onclick="quickNG(${i})"><svg class="ico ico-sm" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><line x1="5.6" y1="5.6" x2="18.4" y2="18.4"/></svg>NG追加</button>
      </div>
    </div>
  `).join('');
}

let _missHit = null;

async function recordMiss(i) {
  _missHit = _hits[i];
  document.getElementById('miss-name').textContent = _missHit.name;
  document.getElementById('miss-price').value = _missHit.price || '';
  document.getElementById('miss-memo').value = '';

  // キーワード一覧をドロップダウンに設定
  const r = await fetch('/api/settings');
  const s = await r.json();
  const sel = document.getElementById('miss-keyword');
  const keys = Object.keys(s.searches || {});
  sel.innerHTML = keys.map(k =>
    `<option value="${k}" ${k === _missHit.keyword ? 'selected' : ''}>${k}</option>`
  ).join('') + '<option value="その他">その他</option>';
  // 検知から開いた場合は自動選択
  if (_missHit.keyword && keys.includes(_missHit.keyword)) sel.value = _missHit.keyword;

  document.getElementById('missModal').classList.add('open');
}

function closeMissModal() {
  document.getElementById('missModal').classList.remove('open');
}

async function saveMiss() {
  if (!_missHit) return;
  const keyword = document.getElementById('miss-keyword').value;
  const price   = parseInt(document.getElementById('miss-price').value) || _missHit.price || 0;
  const memo    = document.getElementById('miss-memo').value.trim();
  await fetch('/api/misses', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ ..._missHit, keyword, price, memo })
  });
  closeMissModal();
  showToast('買い負け記録しました');
}

async function quickNG(i) {
  const name = _hits[i].name;
  const word = prompt('NGワードを入力（商品名から追加）:\n\n' + name);
  if (!word || !word.trim()) return;
  const r = await fetch('/api/settings/ng_add', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ word: word.trim() })
  });
  const res = await r.json();
  if (res.ok) showToast('NGワード追加: ' + word.trim());
}

function colorLog(line) {
  if (line.includes('✅') || line.includes('ヒット')) return 'hit';
  if (line.includes('❌') || line.includes('エラー')) return 'error';
  return '';
}

async function update() {
  try {
    const [sr, hr, lr] = await Promise.all([fetch('/api/status'), fetch('/api/hits'), fetch('/api/log')]);
    const status = await sr.json();
    const hits   = await hr.json();
    const logs   = await lr.json();
    const badge  = document.getElementById('statusBadge');
    const label  = document.getElementById('statusLabel');
    if (status.running) { badge.className = 'badge running'; label.textContent = '監視中'; }
    else                { badge.className = 'badge stopped'; label.textContent = '停止中'; }
    document.getElementById('hitCount').textContent    = hits.length;
    document.getElementById('checkedCount').textContent = status.checked_count;
    document.getElementById('hitBadge').textContent    = hits.length;
    renderHits(hits);
    const logBox = document.getElementById('logBox');
    logBox.innerHTML = logs.map(l => `<div class="log-line ${colorLog(l)}">${l}</div>`).join('');
  } catch(e) {}
}

// ===== 購入モーダル =====
let _modalHit = null;
async function openModal(i) {
  const hit = _hits[i];
  _modalHit = hit;
  document.getElementById('modal-name').textContent = hit.name;
  document.getElementById('modal-buy').value  = hit.price;
  document.getElementById('modal-sell').value = '';
  document.getElementById('modal-ship').value = '0';
  document.getElementById('modal-memo').value = '';

  // キーワード選択肢を設定
  const r = await fetch('/api/settings');
  const s = await r.json();
  const keys = Object.keys(s.searches || {});
  const sel = document.getElementById('modal-keyword');
  sel.innerHTML = keys.map(k =>
    `<option value="${k}" ${k === hit.keyword ? 'selected' : ''}>${k}</option>`
  ).join('') + '<option value="その他">その他</option>';
  if (!keys.includes(hit.keyword)) sel.value = 'その他';

  updatePreview();
  document.getElementById('purchaseModal').classList.add('open');
}
function closeModal() {
  document.getElementById('purchaseModal').classList.remove('open');
}
function calcProfit() {
  const buy  = parseInt(document.getElementById('modal-buy').value)  || 0;
  const sell = parseInt(document.getElementById('modal-sell').value) || 0;
  const ship = parseInt(document.getElementById('modal-ship').value) || 0;
  const profit = Math.round(sell * 0.9) - buy - ship;
  const rate   = buy > 0 ? Math.round(profit / buy * 1000) / 10 : 0;
  return { profit, rate };
}
function updatePreview() {
  const { profit, rate } = calcProfit();
  const el = document.getElementById('preview-profit');
  el.textContent = `¥${profit.toLocaleString()}`;
  el.style.color = profit >= 0 ? '#3fb950' : '#f85149';
  document.getElementById('preview-rate').textContent = `（${rate}%）`;
}
async function savePurchase() {
  if (!_modalHit) return;
  const buy     = parseInt(document.getElementById('modal-buy').value)     || 0;
  const sell    = parseInt(document.getElementById('modal-sell').value)    || 0;
  const ship    = parseInt(document.getElementById('modal-ship').value)    || 0;
  const memo    = document.getElementById('modal-memo').value.trim();
  const keyword = document.getElementById('modal-keyword').value;
  await fetch('/api/purchases', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      item_id: _modalHit.item_id || '',
      name: _modalHit.name,
      keyword,
      url: _modalHit.url,
      thumbnail: _modalHit.thumbnail,
      buy_price: buy, sell_price: sell, shipping: ship, memo
    })
  });
  closeModal();
  showToast('購入記録しました');
}

// ===== 収益管理タブ =====
async function loadPurchases() {
  const r = await fetch('/api/purchases');
  const purchases = await r.json();
  renderPurchases(purchases);
  renderSummary(purchases);
  buildAnalytics(purchases);
}

function calcPurchaseProfit(p) {
  return Math.round(p.sell_price * 0.9) - p.buy_price - p.shipping;
}
function daysBetween(a, b) {
  if (!a || !b) return null;
  const diff = new Date(b) - new Date(a);
  return Math.round(diff / 86400000);
}

function renderSummary(purchases) {
  const totalCost = purchases.reduce((s, p) => s + p.buy_price, 0);
  const sold = purchases.filter(p => p.status === 'sold');
  const realizedProfit = sold.reduce((s, p) => s + calcPurchaseProfit(p), 0);
  const totalProfit    = purchases.reduce((s, p) => s + calcPurchaseProfit(p), 0);
  const avgRate = sold.length > 0
    ? Math.round(sold.reduce((s, p) => {
        const pr = calcPurchaseProfit(p);
        return s + (p.buy_price > 0 ? pr / p.buy_price * 100 : 0);
      }, 0) / sold.length * 10) / 10
    : 0;
  document.getElementById('s-cost').textContent = `¥${totalCost.toLocaleString()}`;
  const rEl = document.getElementById('s-profit');
  rEl.textContent = `¥${realizedProfit.toLocaleString()}`;
  rEl.className   = 'summary-value ' + (realizedProfit >= 0 ? 'green' : 'red');
  const tEl = document.getElementById('s-total');
  tEl.textContent = `¥${totalProfit.toLocaleString()}`;
  tEl.className   = 'summary-value ' + (totalProfit >= 0 ? 'green' : 'red');
  document.getElementById('s-rate').textContent   = `${avgRate}%`;
  document.getElementById('s-counts').textContent = `${purchases.length} / ${sold.length}`;
}

// 1行分のセル。売却済かどうかで期間列と売却済ボタンの有無だけが変わる
function purchaseRow(p, isSold) {
  const profit = Math.round(p.sell_price * 0.9) - p.buy_price - p.shipping;
  const rate   = p.buy_price > 0 ? Math.round(profit / p.buy_price * 1000) / 10 : 0;
  const pClass = profit >= 0 ? 'profit-pos' : 'profit-neg';
  return `
      <tr>
        <td>${p.thumbnail ? `<img class="p-thumb" src="${p.thumbnail}" onerror="this.style.display='none'">` : '<div class="p-thumb"></div>'}</td>
        <td class="p-name"><a href="${p.url}" target="_blank">${p.name}</a><br><span style="font-size:0.75em;color:#a3b0bd">${p.bought_at}</span></td>
        <td class="nowrap">¥${p.buy_price.toLocaleString()}</td>
        <td class="nowrap"><input class="memo-input" type="number" value="${p.sell_price}" onchange="updateSellPrice('${p.id}', this.value)" style="width:90px;color:#e6edf3;text-align:right"></td>
        <td class="nowrap">¥${p.shipping.toLocaleString()}</td>
        <td class="nowrap ${pClass}">¥${profit.toLocaleString()}</td>
        <td class="nowrap rate-cell ${profit < 0 ? 'neg' : ''}">${rate}%</td>
        ${isSold ? `<td class="nowrap" style="color:#a3b0bd;font-size:0.92em">${p.sold_at ? daysBetween(p.bought_at, p.sold_at) + '日' : '-'}</td>` : ''}
        <td><input class="memo-input" value="${p.memo}" onchange="updateMemo('${p.id}', this.value)" placeholder="メモ"></td>
        <td class="nowrap">
          <button class="action-btn listing-btn" onclick='openListingModal(${JSON.stringify({name:p.name,keyword:p.keyword})})'><svg class="ico ico-sm" viewBox="0 0 24 24" style="vertical-align:-2px;margin-right:4px"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/></svg>出品文</button>
          ${!isSold ? `<button class="action-btn sell-btn" onclick="markSold('${p.id}')">売却済</button>` : ''}
          <button class="action-btn del-btn" onclick="deletePurchase('${p.id}')">削除</button>
        </td>
      </tr>`;
}

function renderPurchases(purchases) {
  const stock = purchases.filter(p => p.status !== 'sold');
  const sold  = purchases.filter(p => p.status === 'sold');
  const fill = (listId, emptyId, countId, rows, isSold) => {
    document.getElementById(listId).innerHTML = rows.map(p => purchaseRow(p, isSold)).join('');
    document.getElementById(emptyId).style.display = rows.length ? 'none' : 'block';
    document.getElementById(countId).textContent = rows.length;
  };
  fill('purchaseList', 'purchaseEmpty', 'stockCount', stock, false);
  fill('soldList',     'soldEmpty',     'soldCount',  sold,  true);
}

async function markSold(id) {
  await fetch(`/api/purchases/${id}`, {
    method: 'PUT',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ status: 'sold' })
  });
  loadPurchases();
}

async function updateMemo(id, memo) {
  await fetch(`/api/purchases/${id}`, {
    method: 'PUT',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ memo })
  });
}

async function updateSellPrice(id, val) {
  const sell_price = parseInt(val) || 0;
  await fetch(`/api/purchases/${id}`, {
    method: 'PUT',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ sell_price })
  });
  loadPurchases();
  showToast('売値を更新しました');
}

async function deletePurchase(id) {
  if (!confirm('削除しますか？')) return;
  await fetch(`/api/purchases/${id}`, { method: 'DELETE' });
  loadPurchases();
}

// ===== 出品文生成 =====
let _listingItem = null;
function openListingModal(item) {
  _listingItem = item;
  document.getElementById('listing-name').textContent = item.name;
  document.getElementById('listing-result').style.display = 'none';
  document.getElementById('listing-gen-btn').textContent = '生成する';
  document.getElementById('listing-gen-btn').disabled = false;
  document.getElementById('listingModal').classList.add('open');
}
function closeListingModal() {
  document.getElementById('listingModal').classList.remove('open');
}
async function generateListing() {
  if (!_listingItem) return;
  const btn = document.getElementById('listing-gen-btn');
  btn.textContent = '生成中...';
  btn.disabled = true;
  const r = await fetch('/api/generate_listing', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      name:        _listingItem.name,
      keyword:     _listingItem.keyword || '',
      condition:   document.getElementById('listing-condition').value,
      accessories: document.getElementById('listing-accessories').value,
      working:     document.getElementById('listing-working').value,
      memo:        document.getElementById('listing-memo').value.trim()
    })
  });
  const res = await r.json();
  btn.textContent = '再生成';
  btn.disabled = false;
  if (!res.ok) { showToast(res.error); return; }
  document.getElementById('listing-title-text').textContent = res.title;
  document.getElementById('listing-desc-text').textContent  = res.description;
  document.getElementById('listing-result').style.display = 'block';
}
function copyText(id) {
  const text = document.getElementById(id).textContent;
  navigator.clipboard.writeText(text).then(() => showToast('コピーしました'));
}

// ===== 買い負けタブ =====
async function loadMisses() {
  const r = await fetch('/api/misses');
  const misses = await r.json();
  const tbody = document.getElementById('missList');
  const empty = document.getElementById('missEmpty');
  if (!misses.length) {
    tbody.innerHTML = '';
    empty.style.display = 'block';
  } else {
    empty.style.display = 'none';
    tbody.innerHTML = misses.map(m => `
      <tr>
        <td>${m.thumbnail ? `<img class="p-thumb" src="${m.thumbnail}" onerror="this.style.display='none'">` : '<div class="p-thumb"></div>'}</td>
        <td class="p-name"><a href="${m.url}" target="_blank">${m.name}</a></td>
        <td class="nowrap" style="font-weight:700">¥${m.price.toLocaleString()}</td>
        <td class="nowrap" style="color:#a3b0bd;font-size:0.92em">${m.keyword}</td>
        <td style="color:#a3b0bd;font-size:0.92em">${m.memo || '-'}</td>
        <td class="nowrap" style="color:#a3b0bd;font-size:0.92em">${m.time}</td>
      </tr>`).join('');
  }
  // 買い負けグラフ
  const kw = {};
  for (const m of misses) {
    const k = m.keyword || 'その他';
    kw[k] = (kw[k] || 0) + 1;
  }
  const labels = Object.keys(kw).sort((a,b) => kw[b]-kw[a]);
  destroyChart('miss');
  if (labels.length) {
    _charts['miss'] = new Chart(document.getElementById('chartMiss'), {
      type: 'bar',
      data: { labels, datasets: [{ label: '買い負け数', data: labels.map(k=>kw[k]), backgroundColor: '#da3633', borderRadius: 4 }] },
      options: { responsive: true, plugins: { legend: { display: false } }, scales: { x:{ticks:{color:'#a3b0bd'}}, y:{ticks:{color:'#a3b0bd'},grid:{color:'#21262d'}} } }
    });
  }
}

// ===== 分析タブ =====
const _charts = {};
function destroyChart(id) { if (_charts[id]) { _charts[id].destroy(); delete _charts[id]; } }

// 分析タブは集計結果を保持しておき、指標を切り替えても再集計しない
let _anData    = null;
let _anMetric  = 'profit';
// loadPurchases は収益管理タブとも共用のため、分析タブを開いた直後だけ立てる
let _anAnimate = false;

const yen = v => (v < 0 ? '−¥' : '¥') + Math.abs(Math.round(v)).toLocaleString();

const reduceMotion = () =>
  window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// 0 から実値まで数値を動かす。分析タブのメーター表現に使う
function animateValue(el, to, fmt, decimals) {
  if (el._anRaf) { cancelAnimationFrame(el._anRaf); el._anRaf = null; }
  if (reduceMotion() || !isFinite(to)) { el.textContent = fmt(to); return; }
  const DURATION = 900, t0 = performance.now();
  el.textContent = fmt(0);   // 最初の1フレームに前回値が残らないようにする
  const step = now => {
    const p = Math.min(1, (now - t0) / DURATION);
    const eased = 1 - Math.pow(1 - p, 3);   // easeOutCubic: 勢いよく出て静かに止まる
    const v = to * eased;
    el.textContent = fmt(decimals ? Math.round(v * 10) / 10 : Math.round(v));
    el._anRaf = p < 1 ? requestAnimationFrame(step) : null;
  };
  el._anRaf = requestAnimationFrame(step);
}

// 指標の定義。profit / rate / days は売却済みの実績のみを対象にする
const AN_METRICS = {
  profit: { label: '実現利益',     fmt: v => yen(v) },
  count:  { label: '購入数',       fmt: v => v + ' 件' },
  rate:   { label: '平均利益率',   fmt: v => v + ' %' },
  days:   { label: '平均売却期間', fmt: v => v + ' 日' },
};

function selectMetric(m) {
  _anMetric = m;
  document.querySelectorAll('#metricRow .metric')
    .forEach(b => b.classList.toggle('active', b.dataset.metric === m));
  drawMainChart();
}

function drawMainChart() {
  if (!_anData) return;
  const { labels, value } = _anData;
  const meta = AN_METRICS[_anMetric];
  const vals = labels.map(k => value(k, _anMetric));
  // 損益に関わる指標だけ正負で色分けし、それ以外は単色に抑える
  const signed = _anMetric === 'profit' || _anMetric === 'rate';
  const colors = vals.map(v => signed ? (v >= 0 ? '#2ea043' : '#da3633') : '#1f6feb');

  destroyChart('main');
  _charts['main'] = new Chart(document.getElementById('chartMain'), {
    type: 'bar',
    data: { labels, datasets: [{ data: vals, backgroundColor: colors, borderRadius: 4, maxBarThickness: 26 }] },
    options: {
      // キーワード名が日本語で長いため横棒にして読めるようにする
      indexAxis: 'y',
      responsive: true, maintainAspectRatio: false,
      // 棒は基準線から伸びる。数値のカウントアップと歩調を合わせたいので
      // 時間と減速の仕方を animateValue と揃え、ずらさず一斉に立ち上げる
      animation: reduceMotion() ? false : { duration: 900, easing: 'easeOutCubic' },
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: c => meta.label + ': ' + meta.fmt(c.parsed.x) } }
      },
      scales: {
        x: { ticks: { color: '#8b97a5', font: { size: 11 } }, grid: { color: '#21262d' }, border: { display: false } },
        y: { ticks: { color: '#c3ccd6', font: { size: 12 } }, grid: { display: false }, border: { display: false } }
      }
    }
  });
}

function buildAnalytics(purchases) {
  // キーワード別集計
  const kw = {};
  for (const p of purchases) {
    const k = p.keyword || 'その他';
    if (!kw[k]) kw[k] = { realized: 0, count: 0, soldCount: 0, rates: [], days: [] };
    kw[k].count++;
    if (p.status === 'sold') {
      const profit = calcPurchaseProfit(p);
      kw[k].realized += profit;
      kw[k].soldCount++;
      if (p.buy_price > 0) kw[k].rates.push(profit / p.buy_price * 100);
      const d = daysBetween(p.bought_at, p.sold_at);
      if (d !== null) kw[k].days.push(d);
    }
  }
  const avg = arr => arr.length ? Math.round(arr.reduce((s,v)=>s+v,0)/arr.length*10)/10 : 0;
  const labels = Object.keys(kw).sort((a, b) => kw[b].realized - kw[a].realized);
  const value = (k, m) => m === 'profit' ? kw[k].realized
                        : m === 'count'  ? kw[k].count
                        : m === 'rate'   ? avg(kw[k].rates)
                        :                  avg(kw[k].days);
  _anData = { kw, labels, avg, value };

  // ── 冒頭の要約文 ──
  const bought   = labels.reduce((s,k) => s + kw[k].count, 0);
  const sold     = labels.reduce((s,k) => s + kw[k].soldCount, 0);
  const realized = labels.reduce((s,k) => s + kw[k].realized, 0);
  const allRates = labels.flatMap(k => kw[k].rates);
  const allDays  = labels.flatMap(k => kw[k].days);

  const head = document.getElementById('anHeadline');
  const sub  = document.getElementById('anSubline');
  if (!bought) {
    head.textContent = 'まだ購入記録がありません';
    sub.textContent  = '「収益管理」タブで商品を登録すると、ここに分析が表示されます。';
  } else if (!sold) {
    head.textContent = `${bought} 件を仕入れ、まだ 1 件も売却していません`;
    sub.textContent  = `監視キーワード ${labels.length} 件。売却を記録すると利益の分析が表示されます。`;
  } else {
    head.textContent = `売却した ${sold} 件で ${yen(realized)} の利益が出ています`;
    sub.textContent  = `購入 ${bought} 件 ・ 未売却 ${bought - sold} 件 ・ キーワード ${labels.length} 件`;
  }

  // ── 指標カードの数値 ──
  // 分析タブを開いた直後だけ 0 から数え上げる。収益管理タブ経由の
  // 再描画では即座に確定値を入れる
  const animating = _anAnimate;
  _anAnimate = false;
  const setMetric = (id, to, fmt, decimals) => {
    const el = document.getElementById(id);
    if (animating) animateValue(el, to, fmt, decimals);
    else el.textContent = fmt(to);
  };
  setMetric('mv-profit', realized,       yen,            0);
  setMetric('mv-count',  bought,         v => v + ' 件', 0);
  setMetric('mv-rate',   avg(allRates),  v => v + ' %',  1);
  if (allDays.length) setMetric('mv-days', avg(allDays), v => v + ' 日', 1);
  else document.getElementById('mv-days').textContent = '—';

  // ── メイングラフ ──
  drawMainChart();

  // ── 購入数の内訳（青系の濃淡で色数を抑える）──
  const COLORS = ['#1f6feb','#3b82f6','#58a6ff','#79c0ff','#a5d6ff','#c9e2ff','#7d8590','#545d68'];
  destroyChart('count');
  _charts['count'] = new Chart(document.getElementById('chartCount'), {
    type: 'doughnut',
    data: { labels, datasets: [{ data: labels.map(k=>kw[k].count), backgroundColor: COLORS, borderWidth: 0 }] },
    options: { responsive: true, maintainAspectRatio: false, cutout: '58%',
      animation: reduceMotion() ? false
        : { duration: 900, easing: 'easeOutCubic', animateRotate: true, animateScale: true },
      plugins: { legend: { position:'right', labels:{ color:'#c3ccd6', font:{size:11}, boxWidth:10, boxHeight:10, padding:10, usePointStyle:true } } } }
  });

  // ── ランキングテーブル ──
  const tbody = document.getElementById('rankTable');
  document.getElementById('rankEmpty').style.display = labels.length ? 'none' : '';
  tbody.innerHTML = labels.map((k, i) => `
    <tr>
      <td><span class="rank-num ${i < 3 ? 'top' + (i+1) : ''}">${i+1}</span></td>
      <td>${k}</td>
      <td>${kw[k].count}</td>
      <td>${kw[k].soldCount}</td>
      <td class="${kw[k].realized>=0?'profit-pos':'profit-neg'}">${yen(kw[k].realized)}</td>
      <td class="${avg(kw[k].rates)>=0?'profit-pos':'profit-neg'}">${avg(kw[k].rates)}%</td>
      <td style="color:#a3b0bd">${kw[k].days.length ? avg(kw[k].days)+'日' : '-'}</td>
    </tr>`).join('');
}

function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.style.display = 'block';
  setTimeout(() => t.style.display = 'none', 2500);
}

// モーダル外クリックで閉じる
document.getElementById('purchaseModal').addEventListener('click', function(e) {
  if (e.target === this) closeModal();
});
document.getElementById('missModal').addEventListener('click', function(e) {
  if (e.target === this) closeMissModal();
});
document.getElementById('listingModal').addEventListener('click', function(e) {
  if (e.target === this) closeListingModal();
});

update();
loadKwOverview();
setInterval(update, 3000);
setInterval(loadKwOverview, 30000);
</script>
</body>
</html>"""


# ===== Flask ルート =====
# 購入履歴API
@flask_app.route("/api/purchases", methods=["GET"])
def api_purchases_get():
    return jsonify(load_purchases())

@flask_app.route("/api/purchases", methods=["POST"])
def api_purchases_post():
    data = request.json or {}
    purchases = load_purchases()
    p = {
        "id": str(uuid.uuid4()),
        "item_id":   data.get("item_id", ""),
        "name":      data.get("name", ""),
        "keyword":   data.get("keyword", ""),
        "url":       data.get("url", ""),
        "thumbnail": data.get("thumbnail", ""),
        "buy_price":  int(data.get("buy_price", 0)),
        "sell_price": int(data.get("sell_price", 0)),
        "shipping":   int(data.get("shipping", 0)),
        "memo":      data.get("memo", ""),
        "status":    "purchased",
        "bought_at": time.strftime("%Y-%m-%d %H:%M"),
        "sold_at":   None,
    }
    purchases.insert(0, p)
    save_purchases(purchases)
    return jsonify({"ok": True})

@flask_app.route("/api/purchases/<pid>", methods=["PUT"])
def api_purchase_update(pid):
    data = request.json or {}
    purchases = load_purchases()
    for p in purchases:
        if p["id"] == pid:
            for key in ("buy_price", "sell_price", "shipping", "memo", "status"):
                if key in data:
                    p[key] = data[key]
            if data.get("status") == "sold" and not p.get("sold_at"):
                p["sold_at"] = time.strftime("%Y-%m-%d %H:%M")
            break
    save_purchases(purchases)
    return jsonify({"ok": True})

@flask_app.route("/api/purchases/<pid>", methods=["DELETE"])
def api_purchase_delete(pid):
    purchases = [p for p in load_purchases() if p["id"] != pid]
    save_purchases(purchases)
    return jsonify({"ok": True})

# 通常ルート
@flask_app.route("/")
def home():
    return Response(HTML, content_type="text/html; charset=utf-8")


@flask_app.route("/api/start")
def api_start():
    global running, monitor_thread
    if not running:
        running = True
        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()
    return jsonify({"ok": True})


@flask_app.route("/api/stop")
def api_stop():
    global running
    running = False
    return jsonify({"ok": True})


@flask_app.route("/api/status")
def api_status():
    return jsonify({
        "running": running,
        "checked_count": len(checked_items)
    })


@flask_app.route("/api/hits")
def api_hits():
    return jsonify(recent_hits)


@flask_app.route("/api/log")
def api_log():
    return jsonify(log_messages)


@flask_app.route("/api/settings", methods=["GET"])
def api_settings_get():
    return jsonify(load_settings())


@flask_app.route("/api/settings", methods=["POST"])
def api_settings_post():
    data = request.json or {}
    settings = load_settings()
    for key in ("webhook_url", "claude_api_key", "searches", "ng_words", "wait_min", "wait_max"):
        if key in data:
            settings[key] = data[key]
    save_settings(settings)
    return jsonify({"ok": True})


@flask_app.route("/api/generate_listing", methods=["POST"])
def api_generate_listing():
    data = request.json or {}
    settings = load_settings()
    api_key = settings.get("claude_api_key", "").strip()
    if not api_key:
        return jsonify({"ok": False, "error": "設定タブでClaude APIキーを入力してください"})
    try:
        import anthropic
        name        = data.get("name", "")
        condition   = data.get("condition", "普通")
        accessories = data.get("accessories", "ソフトのみ")
        working     = data.get("working", "動作確認済み")
        memo        = data.get("memo", "")
        prompt = f"""あなたはメルカリ出品のプロです。以下の情報を元にメルカリ出品用のタイトルと説明文を作成してください。

商品名: {name}
状態: {condition}
付属品: {accessories}
動作確認: {working}
追加メモ: {memo if memo else "なし"}

以下のJSON形式のみで返答してください（他のテキスト不要）:
{{"title": "タイトル（絵文字あり・30文字以内）", "description": "説明文"}}

説明文のフォーマット:
【商品内容】
・{name}
→{accessories}
→{working}⭕️

⸻

【状態】
・状態に応じた説明（傷・汚れ・動作など）
・簡単ではありますが、ウェットティッシュで清掃済みです
・万が一動作に不具合があった場合は返金対応いたします

⸻

【その他】
・即購入OK⭕️
・まとめ買い1点につき50円引きで対応します！
・プチプチ梱包＋匿名配送でお届けします"""

        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        import re as _re
        text = msg.content[0].text.strip()
        m = _re.search(r'\{.*\}', text, _re.DOTALL)
        if m:
            result = json.loads(m.group())
            return jsonify({"ok": True, "title": result.get("title",""), "description": result.get("description","")})
        return jsonify({"ok": False, "error": "生成に失敗しました。再試行してください"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:100]})


@flask_app.route("/api/settings/ng_add", methods=["POST"])
def api_ng_add():
    word = (request.json or {}).get("word", "").strip()
    if not word:
        return jsonify({"ok": False})
    settings = load_settings()
    ng = settings.get("ng_words", [])
    if word not in ng:
        ng.append(word)
        settings["ng_words"] = ng
        save_settings(settings)
    return jsonify({"ok": True})


MISSES_FILE = os.path.join(BASE_DIR, "misses.json")

def load_misses():
    if os.path.exists(MISSES_FILE):
        try:
            with open(MISSES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_misses(misses):
    with open(MISSES_FILE, 'w', encoding='utf-8') as f:
        json.dump(misses, f, ensure_ascii=False, indent=2)

@flask_app.route("/api/misses", methods=["GET"])
def api_misses_get():
    return jsonify(load_misses())

@flask_app.route("/api/misses", methods=["POST"])
def api_misses_post():
    data = request.json or {}
    misses = load_misses()
    misses.insert(0, {
        "id": str(uuid.uuid4()),
        "name": data.get("name", ""),
        "keyword": data.get("keyword", ""),
        "url": data.get("url", ""),
        "thumbnail": data.get("thumbnail", ""),
        "price": int(data.get("price", 0)),
        "time": time.strftime("%Y-%m-%d %H:%M")
    })
    misses[:] = misses[:200]
    save_misses(misses)
    return jsonify({"ok": True})


@flask_app.route("/api/item_lookup", methods=["POST"])
def api_item_lookup():
    import re
    url = (request.json or {}).get("url", "").strip()
    m = re.search(r'/item/(m\w+)', url)
    if not m:
        return jsonify({"ok": False, "error": "URLが正しくありません"})
    item_id = m.group(1)
    item_url = f"https://jp.mercari.com/item/{item_id}"
    try:
        from curl_cffi import requests as curl_req
        global _dpop_nonce
        key = _get_dpop_key()
        session = curl_req.Session(impersonate="chrome120")
        api_url = f"https://api.mercari.jp/v2/items/{item_id}"
        def do_get(nonce):
            proof = _make_dpop_proof(key, "GET", api_url, nonce)
            return session.get(api_url, headers={
                "X-Platform": "web", "Accept": "application/json",
                "Origin": "https://jp.mercari.com", "Referer": "https://jp.mercari.com/",
                "DPoP": proof,
            }, timeout=10)
        resp = do_get(_dpop_nonce)
        if resp.status_code == 401:
            nonce = resp.headers.get("DPoP-Nonce")
            if nonce:
                _dpop_nonce = nonce
                resp = do_get(nonce)
        data = resp.json()
        item = data.get("data", data)
        name = item.get("name", "")
        price = item.get("price", 0)
        thumbs = item.get("thumbnails", [])
        thumbnail = thumbs[0] if thumbs else item.get("thumbnailUrl", "")
        return jsonify({"ok": True, "item_id": item_id, "name": name,
                        "price": int(price or 0), "thumbnail": thumbnail, "url": item_url})
    except Exception as e:
        return jsonify({"ok": True, "item_id": item_id, "name": "",
                        "price": 0, "thumbnail": "", "url": item_url})


@flask_app.route("/api/settings/restore", methods=["POST"])
def api_settings_restore():
    if not os.path.exists(SETTINGS_BACKUP_FILE):
        return jsonify({"ok": False, "error": "バックアップがありません"})
    try:
        with open(SETTINGS_BACKUP_FILE, 'r', encoding='utf-8') as f:
            backup = json.load(f)
        # 現在をバックアップに上書き（バックアップは消さない）
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(backup, f, ensure_ascii=False, indent=2)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


# ===== 起動処理 =====
def start_server():
    flask_app.run(host="127.0.0.1", port=5001, debug=False, use_reloader=False)


def make_icon():
    from PIL import Image, ImageDraw
    S = 256
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 背景：ダーク角丸
    draw.rounded_rectangle([0, 0, S, S], radius=52, fill=(13, 17, 23))

    # ショッピングカート（オレンジ）
    C = (255, 107, 53)
    draw.arc([48, 38, 162, 108], 210, 358, fill=C, width=18)
    draw.polygon([(40, 94), (210, 94), (190, 174), (60, 174)], fill=C)
    draw.ellipse([72, 174, 112, 214], fill=C)
    draw.ellipse([144, 174, 184, 214], fill=C)
    draw.ellipse([82, 184, 102, 204], fill=(13, 17, 23))
    draw.ellipse([154, 184, 174, 204], fill=(13, 17, 23))

    # レーダー（緑）右上
    G = (63, 185, 80)
    draw.arc([158, 22, 234, 98], 0, 360, fill=G, width=7)
    draw.arc([172, 36, 220, 84], 0, 360, fill=G, width=5)
    draw.ellipse([188, 52, 206, 70], fill=G)

    return img


def main():
    if not os.path.exists(SETTINGS_FILE):
        save_settings(DEFAULT_SETTINGS)

    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    time.sleep(1.5)

    try:
        import webview

        def on_closed():
            global running
            running = False
            os._exit(0)

        window = webview.create_window(
            "MeriWatch",
            "http://127.0.0.1:5001",
            width=1280,
            height=800,
            resizable=True,
            on_top=False,
            min_size=(800, 500),
        )
        window.events.closed += on_closed
        webview.start()

    except ImportError:
        # pywebview未インストールの場合はブラウザで開く
        webbrowser.open("http://127.0.0.1:5001")
        try:
            import pystray

            def on_open(icon, item):
                webbrowser.open("http://127.0.0.1:5001")

            def on_quit(icon, item):
                global running
                running = False
                icon.stop()
                os._exit(0)

            menu = pystray.Menu(
                pystray.MenuItem("管理画面を開く", on_open, default=True),
                pystray.MenuItem("終了", on_quit),
            )
            icon = pystray.Icon("MeriWatch", make_icon(), "MeriWatch", menu)
            icon.run()

        except ImportError:
            print("起動完了: http://127.0.0.1:5001")
            print("終了するには Ctrl+C")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass


if __name__ == "__main__":
    main()
