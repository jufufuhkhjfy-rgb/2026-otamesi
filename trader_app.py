#!/usr/bin/env python3
"""
AI株式デイトレードシミュレーター
yfinance でリアル株価取得 + Claude AI が日本語で売買判断
"""

import os
import sys
import json
import sqlite3
import logging
import re
import threading
import webbrowser
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Windows で日本語ログが文字化けしないようにする
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from flask import Flask, render_template, jsonify, request
from apscheduler.schedulers.background import BackgroundScheduler
import yfinance as yf

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

app = Flask(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("trader.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# ── 設定 ─────────────────────────────────────────────────────────────────────
INITIAL_CAPITAL = 100_000.0          # 仮想資本 $100,000
DB_PATH = os.path.join(os.path.dirname(__file__), "trader.db")
ET = ZoneInfo("America/New_York")
JST = ZoneInfo("Asia/Tokyo")

# 米国株（50銘柄）
US_STOCKS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "META",
    "NVDA", "TSLA", "JPM",   "JNJ",  "KO",
    "AMD",  "PLTR", "SPY",   "QQQ",  "NFLX",
    "XOM",  "UNH",  "WMT",   "SOFI", "RIVN",
    "ORCL", "CSCO", "INTC",  "CRM",  "ADBE",
    "PYPL", "UBER", "COIN",  "RBLX", "SNAP",
    "BA",   "GE",   "CAT",   "HON",  "PG",
    "PFE",  "MRK",  "ABBV",  "T",    "VZ",
    "DIS",  "GS",   "MS",    "BAC",  "V",
    "MA",   "BRK-B","COST",  "MCD",  "SBUX",
]

# 日経銘柄（50銘柄）
JP_STOCKS = [
    "7203.T",  # トヨタ自動車
    "6758.T",  # ソニーグループ
    "9984.T",  # ソフトバンクグループ
    "8306.T",  # 三菱UFJフィナンシャル
    "7974.T",  # 任天堂
    "6861.T",  # キーエンス
    "4063.T",  # 信越化学工業
    "9432.T",  # NTT
    "4502.T",  # 武田薬品工業
    "7267.T",  # 本田技研工業
    "6954.T",  # ファナック
    "8035.T",  # 東京エレクトロン
    "4519.T",  # 中外製薬
    "9983.T",  # ファーストリテイリング
    "6367.T",  # ダイキン工業
    "8766.T",  # 東京海上HD
    "7751.T",  # キヤノン
    "6326.T",  # クボタ
    "4543.T",  # テルモ
    "6981.T",  # 村田製作所
    "9022.T",  # JR東海
    "8058.T",  # 三菱商事
    "5108.T",  # ブリヂストン
    "4661.T",  # オリエンタルランド
    "6098.T",  # リクルートHD
    "6645.T",  # オムロン
    "4901.T",  # 富士フイルムHD
    "6501.T",  # 日立製作所
    "4568.T",  # 第一三共
    "8001.T",  # 伊藤忠商事
    "3382.T",  # セブン&アイHD
    "6702.T",  # 富士通
    "9020.T",  # JR東日本
    "8802.T",  # 三菱地所
    "7011.T",  # 三菱重工業
    "2914.T",  # JT
    "8031.T",  # 三井物産
    "9613.T",  # NTTデータ
    "4452.T",  # 花王
    "8053.T",  # 住友商事
    "6471.T",  # 日本精工
    "5401.T",  # 日本製鉄
    "7270.T",  # SUBARU
    "6503.T",  # 三菱電機
    "8309.T",  # 三井住友トラスト
    "7201.T",  # 日産自動車
    "4507.T",  # 塩野義製薬
    "8725.T",  # MS&ADインシュアランス
    "6762.T",  # TDK
    "9735.T",  # セコム
]

WATCHLIST = US_STOCKS + JP_STOCKS   # 合計100銘柄

MAX_POSITION_PCT = 0.10   # 1銘柄への最大投資割合（100銘柄なので少し下げる）
TRADE_INTERVAL_MIN = 30   # 取引間隔（分）
scheduler = BackgroundScheduler(daemon=True)


# ── データベース ──────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS account (
                id              INTEGER PRIMARY KEY,
                cash_balance    REAL NOT NULL,
                initial_capital REAL NOT NULL,
                last_updated    TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS portfolio (
                symbol       TEXT PRIMARY KEY,
                shares       REAL NOT NULL,
                avg_cost     REAL NOT NULL,
                last_price   REAL DEFAULT 0,
                last_updated TEXT
            );
            CREATE TABLE IF NOT EXISTS trades (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   TEXT NOT NULL,
                symbol      TEXT NOT NULL,
                action      TEXT NOT NULL,
                shares      REAL NOT NULL,
                price       REAL NOT NULL,
                total_value REAL NOT NULL,
                reason      TEXT
            );
            CREATE TABLE IF NOT EXISTS ai_sessions (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp     TEXT NOT NULL,
                decisions_json TEXT,
                commentary    TEXT,
                reflection    TEXT,
                market_status TEXT
            );
            CREATE TABLE IF NOT EXISTS portfolio_history (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp       TEXT NOT NULL,
                total_value     REAL NOT NULL,
                cash            REAL NOT NULL,
                holdings_value  REAL NOT NULL
            );
        """)
        row = conn.execute("SELECT COUNT(*) as cnt FROM account").fetchone()
        if row["cnt"] == 0:
            conn.execute(
                "INSERT INTO account VALUES (1,?,?,?)",
                (INITIAL_CAPITAL, INITIAL_CAPITAL, datetime.now().isoformat()),
            )
        conn.commit()


def get_account():
    with get_db() as conn:
        return dict(conn.execute("SELECT * FROM account WHERE id=1").fetchone())


def get_portfolio():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM portfolio WHERE shares > 0.001"
        ).fetchall()
        return [dict(r) for r in rows]


def get_recent_trades(limit=100):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_ai_sessions(limit=20):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM ai_sessions ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_portfolio_history():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM portfolio_history ORDER BY timestamp DESC LIMIT 288"
        ).fetchall()
        return [dict(r) for r in reversed(rows)]


def execute_trade(symbol, action, shares, price, reason):
    """シミュレーション売買を実行"""
    total = shares * price
    with get_db() as conn:
        acct = dict(conn.execute("SELECT * FROM account WHERE id=1").fetchone())

        if action == "BUY":
            if total > acct["cash_balance"]:
                logger.warning(f"現金不足: {symbol} 購入に ${total:.2f} 必要, 残高 ${acct['cash_balance']:.2f}")
                return False
            conn.execute(
                "UPDATE account SET cash_balance=cash_balance-?, last_updated=? WHERE id=1",
                (total, datetime.now().isoformat()),
            )
            existing = conn.execute("SELECT * FROM portfolio WHERE symbol=?", (symbol,)).fetchone()
            if existing:
                ns = existing["shares"] + shares
                nc = (existing["shares"] * existing["avg_cost"] + total) / ns
                conn.execute(
                    "UPDATE portfolio SET shares=?,avg_cost=?,last_price=?,last_updated=? WHERE symbol=?",
                    (ns, nc, price, datetime.now().isoformat(), symbol),
                )
            else:
                conn.execute(
                    "INSERT INTO portfolio VALUES (?,?,?,?,?)",
                    (symbol, shares, price, price, datetime.now().isoformat()),
                )

        elif action == "SELL":
            existing = conn.execute("SELECT * FROM portfolio WHERE symbol=?", (symbol,)).fetchone()
            if not existing or existing["shares"] < shares - 0.001:
                logger.warning(f"株数不足: {symbol}")
                return False
            conn.execute(
                "UPDATE account SET cash_balance=cash_balance+?, last_updated=? WHERE id=1",
                (total, datetime.now().isoformat()),
            )
            new_shares = existing["shares"] - shares
            if new_shares < 0.001:
                conn.execute("DELETE FROM portfolio WHERE symbol=?", (symbol,))
            else:
                conn.execute(
                    "UPDATE portfolio SET shares=?,last_price=?,last_updated=? WHERE symbol=?",
                    (new_shares, price, datetime.now().isoformat(), symbol),
                )
        else:
            return False

        conn.execute(
            "INSERT INTO trades(timestamp,symbol,action,shares,price,total_value,reason) VALUES(?,?,?,?,?,?,?)",
            (datetime.now().isoformat(), symbol, action, shares, price, total, reason),
        )
        conn.commit()
    logger.info(f"約定: {action} {shares:.1f}株 {symbol} @ ${price:.2f} = ${total:.2f}")
    return True


def record_snapshot(total_value, cash, holdings_value):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO portfolio_history(timestamp,total_value,cash,holdings_value) VALUES(?,?,?,?)",
            (datetime.now().isoformat(), total_value, cash, holdings_value),
        )
        conn.commit()


# ── 価格キャッシュ（yfinanceの呼びすぎを防ぐ）─────────────────────────────────
_price_cache = {}
_change_cache = {}
_cache_ts = {}
CACHE_TTL = 90  # 90秒キャッシュ


def _cached(cache, key):
    if key in cache and (datetime.now().timestamp() - _cache_ts.get(key, 0)) < CACHE_TTL:
        return cache[key]
    return None


# ── 株価取得 ──────────────────────────────────────────────────────────────────
def fetch_prices(symbols):
    """指定銘柄の最新価格を取得（キャッシュ付き）"""
    prices = {}
    if not symbols:
        return prices
    # キャッシュに残っているものは除外
    uncached = [s for s in symbols if _cached(_price_cache, s) is None]
    for s in symbols:
        cached = _cached(_price_cache, s)
        if cached is not None:
            prices[s] = cached
    if not uncached:
        return prices
    # 一度に取得しすぎないよう30銘柄ずつに分割
    for i in range(0, len(uncached), 30):
        batch = uncached[i:i+30]
        _fetch_prices_batch(batch, prices)
    return prices


def _fetch_prices_batch(symbols, prices):
    try:
        sym_str = " ".join(symbols)
        data = yf.download(
            sym_str, period="2d", interval="5m",
            auto_adjust=True, progress=False, threads=True,
            group_by="ticker",
        )
        now_ts = datetime.now().timestamp()
        if len(symbols) == 1:
            sym = symbols[0]
            try:
                close = data["Close"].dropna()
                if not close.empty:
                    prices[sym] = float(close.iloc[-1])
                    _price_cache[sym] = prices[sym]
                    _cache_ts[sym] = now_ts
            except Exception:
                pass
        else:
            for sym in symbols:
                try:
                    close = data[sym]["Close"].dropna()
                    if not close.empty:
                        prices[sym] = float(close.iloc[-1])
                        _price_cache[sym] = prices[sym]
                        _cache_ts[sym] = now_ts
                except Exception:
                    pass
    except Exception as e:
        logger.error(f"価格取得エラー: {e}")


def fetch_daily_changes(symbols):
    """当日の騰落率を計算（キャッシュ付き）"""
    changes = {}
    if not symbols:
        return changes
    # キャッシュ済みを返す
    uncached = [s for s in symbols if _cached(_change_cache, s) is None]
    for s in symbols:
        v = _cached(_change_cache, s)
        if v is not None:
            changes[s] = v
    if not uncached:
        return changes
    # 30銘柄ずつ取得
    for i in range(0, len(uncached), 30):
        _fetch_changes_batch(uncached[i:i+30], changes)
    return changes


def _fetch_changes_batch(symbols, changes):
    try:
        sym_str = " ".join(symbols)
        data = yf.download(
            sym_str, period="5d", interval="1d",
            auto_adjust=True, progress=False, threads=True,
            group_by="ticker",
        )
        if len(symbols) == 1:
            sym = symbols[0]
            try:
                closes = data["Close"].dropna()
                if len(closes) >= 2:
                    changes[sym] = float((closes.iloc[-1] / closes.iloc[-2] - 1) * 100)
            except Exception:
                pass
        else:
            for sym in symbols:
                try:
                    closes = data[sym]["Close"].dropna()
                    if len(closes) >= 2:
                        v = float((closes.iloc[-1] / closes.iloc[-2] - 1) * 100)
                        changes[sym] = v
                        _change_cache[sym] = v
                        _cache_ts[sym] = datetime.now().timestamp()
                except Exception:
                    pass
    except Exception as e:
        logger.error(f"騰落率取得エラー: {e}")


def is_us_market_open():
    now = datetime.now(ET)
    if now.weekday() >= 5:
        return False
    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
    return market_open <= now <= market_close


def is_jp_market_open():
    now = datetime.now(JST)
    if now.weekday() >= 5:
        return False
    am_open  = now.replace(hour=9,  minute=0,  second=0, microsecond=0)
    am_close = now.replace(hour=11, minute=30, second=0, microsecond=0)
    pm_open  = now.replace(hour=12, minute=30, second=0, microsecond=0)
    pm_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return (am_open <= now <= am_close) or (pm_open <= now <= pm_close)


def is_market_open():
    return is_us_market_open() or is_jp_market_open()


# ── テクニカル指標 ─────────────────────────────────────────────────────────────
def calculate_rsi(closes, period=14):
    if len(closes) < period + 1:
        return 50.0
    deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gains  = [d if d > 0 else 0 for d in deltas[-period:]]
    losses = [-d if d < 0 else 0 for d in deltas[-period:]]
    ag = sum(gains) / period
    al = sum(losses) / period
    if al == 0:
        return 100.0
    return round(100 - (100 / (1 + ag / al)), 1)


def fetch_technicals(symbols):
    """MA5・MA20・RSI・トレンドを計算"""
    result = {}
    if not symbols:
        return result
    try:
        batch = symbols[:40]   # 重いので最大40銘柄
        sym_str = " ".join(batch)
        data = yf.download(sym_str, period="30d", interval="1d",
                           auto_adjust=True, progress=False, group_by="ticker")
        for sym in batch:
            try:
                if len(batch) == 1:
                    closes = data["Close"].dropna().tolist()
                else:
                    col = data[sym]["Close"]
                    if hasattr(col, "columns"):
                        col = col.iloc[:, 0]
                    closes = col.dropna().tolist()
                if len(closes) < 5:
                    continue
                ma5  = round(sum(closes[-5:]) / 5, 2)
                ma20 = round(sum(closes[-min(20, len(closes)):]) / min(20, len(closes)), 2)
                rsi  = calculate_rsi(closes)
                result[sym] = {
                    "ma5": ma5, "ma20": ma20, "rsi": rsi,
                    "trend": "上昇中" if ma5 > ma20 else "下降中",
                    "rsi_signal": "売られすぎ" if rsi < 30 else "買われすぎ" if rsi > 70 else "中立",
                }
            except Exception:
                pass
    except Exception as e:
        logger.error(f"テクニカル取得エラー: {e}")
    return result


def fetch_market_news():
    """主要銘柄のニュースヘッドラインを取得"""
    headlines = []
    for sym in ["SPY", "QQQ", "NVDA", "AAPL", "TSLA"]:
        try:
            news = yf.Ticker(sym).news or []
            for n in news[:2]:
                title = n.get("title", "")
                if title:
                    headlines.append(f"[{sym}] {title}")
        except Exception:
            pass
    return headlines[:8]


def get_recent_trade_performance():
    """直近20取引の損益を分析"""
    trades = get_recent_trades(20)
    summary = []
    for t in trades:
        summary.append({
            "time": t["timestamp"][:16],
            "symbol": t["symbol"],
            "action": t["action"],
            "shares": t["shares"],
            "price": t["price"],
            "total": t["total_value"],
            "reason": t["reason"],
        })
    return summary


# ── AI 取引エンジン ────────────────────────────────────────────────────────────
def ai_trading_session(force=False):
    """Claude AI による取引セッション（シミュレーションは常時実行）"""
    logger.info("AI取引セッション開始...")

    acct = get_account()
    portfolio = get_portfolio()
    all_symbols = list(set(WATCHLIST + [p["symbol"] for p in portfolio]))

    prices = fetch_prices(all_symbols)
    changes = fetch_daily_changes(all_symbols)

    if not prices:
        logger.error("価格取得失敗 - セッションスキップ")
        return {"status": "error", "message": "価格取得失敗"}

    # ポートフォリオ評価
    for p in portfolio:
        if p["symbol"] in prices:
            with get_db() as conn:
                conn.execute(
                    "UPDATE portfolio SET last_price=?,last_updated=? WHERE symbol=?",
                    (prices[p["symbol"]], datetime.now().isoformat(), p["symbol"]),
                )
                conn.commit()

    holdings_value = sum(
        p["shares"] * prices.get(p["symbol"], p["last_price"]) for p in portfolio
    )
    total_value = acct["cash_balance"] + holdings_value
    pnl = total_value - acct["initial_capital"]
    pnl_pct = pnl / acct["initial_capital"] * 100

    # Claude へのコンテキスト構築
    portfolio_detail = []
    for p in portfolio:
        price = prices.get(p["symbol"], p["last_price"])
        pos_pnl = (price - p["avg_cost"]) * p["shares"]
        portfolio_detail.append({
            "symbol": p["symbol"],
            "shares": round(p["shares"], 2),
            "avg_cost": round(p["avg_cost"], 2),
            "current_price": round(price, 2),
            "value": round(p["shares"] * price, 2),
            "pnl": round(pos_pnl, 2),
            "pnl_pct": round((price / p["avg_cost"] - 1) * 100, 2),
            "today_change_pct": round(changes.get(p["symbol"], 0), 2),
        })

    # テクニカル指標・ニュース・取引履歴を取得
    held_syms = [p["symbol"] for p in portfolio]
    top_movers = sorted(changes.items(), key=lambda x: abs(x[1]), reverse=True)[:20]
    top_mover_syms = [s for s, _ in top_movers]
    technicals = fetch_technicals(list(set(held_syms + top_mover_syms))[:40])
    news       = fetch_market_news()
    past_trades = get_recent_trade_performance()

    watchlist_detail = {}
    for sym in WATCHLIST:
        if sym not in held_syms:
            tech = technicals.get(sym, {})
            watchlist_detail[sym] = {
                "price": round(prices.get(sym, 0), 2),
                "today_change_pct": round(changes.get(sym, 0), 2),
                "rsi": tech.get("rsi", ""),
                "trend": tech.get("trend", ""),
                "rsi_signal": tech.get("rsi_signal", ""),
            }

    # 保有銘柄にもテクニカルを付与
    for p in portfolio_detail:
        tech = technicals.get(p["symbol"], {})
        p["rsi"] = tech.get("rsi", "")
        p["trend"] = tech.get("trend", "")
        p["rsi_signal"] = tech.get("rsi_signal", "")

    now_et = datetime.now(ET)
    now_jst = datetime.now(JST)

    prompt = f"""あなたは超攻撃的なプロのデイトレーダーAIです。
勝つことに貪欲になってください。損切りを恐れず、利益を追求してください。
世界情勢・マクロ経済・テクニカルを総合判断して最適な売買をしてください。

## 現在時刻
- 米国東部時間: {now_et.strftime('%Y-%m-%d %H:%M (%a)')}
- 日本時間: {now_jst.strftime('%Y-%m-%d %H:%M')}

## 口座状況
- 現金残高: ${acct['cash_balance']:,.2f}
- 株式評価額: ${holdings_value:,.2f}
- 総資産: ${total_value:,.2f}（初期 ${INITIAL_CAPITAL:,.0f}）
- 累計損益: ${pnl:+,.2f}（{pnl_pct:+.2f}%）

## 保有銘柄（RSI・トレンド付き）
{json.dumps(portfolio_detail, ensure_ascii=False, indent=2)}

## ウォッチリスト上位（騰落率・RSI・トレンド付き）
{json.dumps(dict(list(watchlist_detail.items())[:30]), ensure_ascii=False, indent=2)}

## 最新マーケットニュース
{chr(10).join(news) if news else '取得なし'}

## 直近取引履歴（反省材料）
{json.dumps(past_trades[:10], ensure_ascii=False, indent=2)}

## 取引戦略の指針
1. **損切り**: 含み損が-5%超の銘柄は即座に損切りを検討すること
2. **利確**: 含み益+8%以上なら一部利確を検討
3. **RSI**: 30以下は売られすぎで買いチャンス、70以上は買われすぎで売りシグナル
4. **トレンド**: MA5がMA20を上回っている銘柄（上昇トレンド）を優先買い
5. **ニュース**: 悪材料のある銘柄は保有していれば売り、良材料は買い
6. **集中投資**: 確信度の高い銘柄に集中して投資せよ。分散しすぎるな
7. **反省**: 過去の損失取引を分析し、同じ失敗を繰り返すな

## 制約
- 1銘柄への最大投資: 総資産の{MAX_POSITION_PCT*100:.0f}%（= ${total_value*MAX_POSITION_PCT:,.0f}）
- 現金残高を超える購入不可
- 株数は整数のみ

## 回答形式（このJSONのみ、余計なテキスト不要）
{{
  "decisions": [
    {{
      "action": "BUY" または "SELL",
      "symbol": "銘柄コード",
      "shares": 株数（整数）,
      "reason": "具体的な判断理由（テクニカル・ニュース・世界情勢を踏まえて日本語で）"
    }}
  ],
  "commentary": "今日の市場環境・世界情勢・取引戦略の詳細分析（日本語300文字程度）",
  "reflection": "前回の損失・失敗の分析と今回どう改善したか（日本語、なければ空文字）",
  "market_assessment": "強気" または "弱気" または "中立"
}}"""

    decisions_made = []
    commentary = ""
    reflection = ""
    market_status = "中立"

    if ANTHROPIC_AVAILABLE and os.environ.get("ANTHROPIC_API_KEY"):
        try:
            client = anthropic.Anthropic()
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text
            # JSON を抽出
            match = re.search(r"\{[\s\S]*\}", raw)
            if match:
                result = json.loads(match.group())
            else:
                result = {"decisions": [], "commentary": raw[:500], "reflection": "", "market_assessment": "中立"}

            commentary = result.get("commentary", "")
            reflection = result.get("reflection", "")
            market_status = result.get("market_assessment", "中立")

            for d in result.get("decisions", []):
                action = str(d.get("action", "")).upper()
                symbol = str(d.get("symbol", "")).upper()
                try:
                    shares = int(d.get("shares", 0))
                except (TypeError, ValueError):
                    shares = 0
                reason = d.get("reason", "")

                if action not in ("BUY", "SELL") or not symbol or shares <= 0:
                    continue

                price = prices.get(symbol)
                if not price or price <= 0:
                    logger.warning(f"{symbol} の価格が取得できず - スキップ")
                    continue

                # 最大ポジションチェック
                if action == "BUY":
                    max_invest = total_value * MAX_POSITION_PCT
                    max_shares = int(max_invest / price)
                    shares = min(shares, max_shares)
                    if shares <= 0:
                        continue

                if execute_trade(symbol, action, shares, price, reason):
                    decisions_made.append(d)

        except json.JSONDecodeError as e:
            logger.error(f"JSONパースエラー: {e}")
            commentary = "AI応答のパースに失敗しました。"
        except Exception as e:
            logger.error(f"Claude API エラー: {e}")
            commentary = f"AI取引エラー: {str(e)[:200]}"
    else:
        # 無料テクニカル分析トレード
        logger.info("テクニカル分析トレード実行中（無料モード）")
        buy_signals = []
        sell_signals = []
        cash = get_account()["cash_balance"]

        # ── 保有銘柄の損切り・利確チェック ──
        for p in portfolio:
            price = prices.get(p["symbol"], p["last_price"])
            if not price:
                continue
            pnl_pct = (price - p["avg_cost"]) / p["avg_cost"] * 100
            tech = technicals.get(p["symbol"], {})
            rsi  = tech.get("rsi", 50)
            trend = tech.get("trend", "")

            if pnl_pct <= -5.0:
                # 損切り: -5%以下は全売り
                reason = f"損切り: 含み損{pnl_pct:.1f}%、リスク管理のため全売却"
                sell_signals.append((p["symbol"], int(p["shares"]), price, reason, 100))
            elif pnl_pct >= 8.0 and rsi > 65:
                # 利確: +8%以上かつRSI高い
                shares = max(1, int(p["shares"] / 2))
                reason = f"利確: 含み益{pnl_pct:.1f}%・RSI={rsi}で半分利確"
                sell_signals.append((p["symbol"], shares, price, reason, 80))
            elif trend == "下降中" and rsi > 60 and pnl_pct > 2:
                # トレンド転換で利確
                shares = max(1, int(p["shares"] / 2))
                reason = f"トレンド下降転換・RSI={rsi}で利確"
                sell_signals.append((p["symbol"], shares, price, reason, 60))

        # ── ウォッチリストから買いシグナル ──
        held_syms = {p["symbol"] for p in portfolio}
        for sym, tech in technicals.items():
            if sym in held_syms:
                continue
            price = prices.get(sym, 0)
            if not price:
                continue
            rsi   = tech.get("rsi", 50)
            trend = tech.get("trend", "")
            chg   = changes.get(sym, 0)
            score = 0
            reasons = []

            if rsi < 30:
                score += 40
                reasons.append(f"RSI={rsi}(売られすぎ)")
            elif rsi < 40:
                score += 20
                reasons.append(f"RSI={rsi}(低め)")

            if trend == "上昇中":
                score += 30
                reasons.append("上昇トレンド")

            if -3 < chg < -1:
                score += 20
                reasons.append(f"本日{chg:.1f}%押し目")
            elif chg < -3:
                score += 10
                reasons.append(f"本日{chg:.1f}%急落(慎重)")

            if score >= 50:
                invest = min(cash * 0.06, total_value * MAX_POSITION_PCT)
                shares = int(invest / price)
                if shares > 0:
                    reason = "買いシグナル: " + "・".join(reasons)
                    buy_signals.append((sym, shares, price, reason, score))

        # スコア順に並べて上位5銘柄のみ買う
        buy_signals.sort(key=lambda x: x[4], reverse=True)
        for sym, shares, price, reason, _ in sell_signals:
            if execute_trade(sym, "SELL", shares, price, reason):
                decisions_made.append({"action": "SELL", "symbol": sym, "shares": shares, "reason": reason})

        for sym, shares, price, reason, score in buy_signals[:5]:
            cash = get_account()["cash_balance"]
            if cash < price:
                break
            if execute_trade(sym, "BUY", shares, price, reason):
                decisions_made.append({"action": "BUY", "symbol": sym, "shares": shares, "reason": reason})

        # 分析サマリーをコメントとして生成
        buy_count  = len([d for d in decisions_made if d["action"] == "BUY"])
        sell_count = len([d for d in decisions_made if d["action"] == "SELL"])
        top_rsi_low = [(s, t["rsi"]) for s, t in technicals.items() if t.get("rsi", 50) < 35]
        top_rsi_low.sort(key=lambda x: x[1])
        commentary = (
            f"【テクニカル分析トレード】買い{buy_count}件・売り{sell_count}件を実行。"
            f"RSI売られすぎ銘柄: {', '.join(f'{s}({r})' for s,r in top_rsi_low[:3]) or 'なし'}。"
            f"損切り・利確ルール適用中（損切り-5%、利確+8%）。"
            f"上昇トレンド×RSI低水準の銘柄を優先購入。"
        )
        market_status = "強気" if len(buy_signals) > len(sell_signals) else "弱気" if sell_count > buy_count else "中立"

    # セッション記録
    with get_db() as conn:
        conn.execute(
            "INSERT INTO ai_sessions(timestamp,decisions_json,commentary,reflection,market_status) VALUES(?,?,?,?,?)",
            (
                datetime.now().isoformat(),
                json.dumps(decisions_made, ensure_ascii=False),
                commentary,
                reflection,
                market_status,
            ),
        )
        conn.commit()

    # スナップショット記録
    acct2 = get_account()
    portfolio2 = get_portfolio()
    h2 = sum(p["shares"] * prices.get(p["symbol"], p["last_price"]) for p in portfolio2)
    record_snapshot(acct2["cash_balance"] + h2, acct2["cash_balance"], h2)

    logger.info(f"セッション完了 - {len(decisions_made)}件約定, 評価額 ${acct2['cash_balance']+h2:,.2f}")
    return {"status": "ok", "trades": len(decisions_made), "commentary": commentary}


def update_prices_job():
    """価格のみ更新（スナップショット記録）"""
    portfolio = get_portfolio()
    if not portfolio:
        return
    symbols = [p["symbol"] for p in portfolio]
    prices = fetch_prices(symbols)
    if not prices:
        return

    with get_db() as conn:
        for p in portfolio:
            if p["symbol"] in prices:
                conn.execute(
                    "UPDATE portfolio SET last_price=?,last_updated=? WHERE symbol=?",
                    (prices[p["symbol"]], datetime.now().isoformat(), p["symbol"]),
                )
        conn.commit()

    acct = get_account()
    portfolio = get_portfolio()
    h = sum(p["shares"] * prices.get(p["symbol"], p["last_price"]) for p in portfolio)
    record_snapshot(acct["cash_balance"] + h, acct["cash_balance"], h)


# ── Flask ルート ──────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("dashboard.html")


@app.route("/api/stats")
def api_stats():
    acct = get_account()
    portfolio = get_portfolio()
    prices = fetch_prices([p["symbol"] for p in portfolio]) if portfolio else {}
    holdings_value = sum(
        p["shares"] * prices.get(p["symbol"], p["last_price"]) for p in portfolio
    )
    total_value = acct["cash_balance"] + holdings_value
    pnl = total_value - acct["initial_capital"]
    sessions = get_ai_sessions(1)
    latest_session = sessions[0] if sessions else None
    return jsonify({
        "cash": round(acct["cash_balance"], 2),
        "holdings_value": round(holdings_value, 2),
        "total_value": round(total_value, 2),
        "initial_capital": acct["initial_capital"],
        "pnl": round(pnl, 2),
        "pnl_pct": round(pnl / acct["initial_capital"] * 100, 2),
        "positions": len(portfolio),
        "market_open": is_market_open(),
        "latest_commentary": latest_session["commentary"] if latest_session else "",
        "latest_reflection": latest_session["reflection"] if latest_session else "",
        "market_status": latest_session["market_status"] if latest_session else "中立",
        "next_trade": _get_next_trade_time(),
    })


def _get_next_trade_time():
    try:
        job = scheduler.get_job("ai_trading")
        if job and job.next_run_time:
            local = job.next_run_time.astimezone()
            return local.strftime("%H:%M:%S")
    except Exception:
        pass
    return "--"


@app.route("/api/portfolio")
def api_portfolio():
    portfolio = get_portfolio()
    prices = fetch_prices([p["symbol"] for p in portfolio]) if portfolio else {}
    result = []
    for p in portfolio:
        price = prices.get(p["symbol"], p["last_price"])
        value = p["shares"] * price
        cost = p["shares"] * p["avg_cost"]
        result.append({
            "symbol": p["symbol"],
            "shares": round(p["shares"], 2),
            "avg_cost": round(p["avg_cost"], 2),
            "last_price": round(price, 2),
            "value": round(value, 2),
            "pnl": round(value - cost, 2),
            "pnl_pct": round((price / p["avg_cost"] - 1) * 100, 2),
        })
    result.sort(key=lambda x: x["value"], reverse=True)
    return jsonify(result)


@app.route("/api/trades")
def api_trades():
    return jsonify(get_recent_trades(100))


@app.route("/api/ai_sessions")
def api_ai_sessions():
    sessions = get_ai_sessions(20)
    for s in sessions:
        if s.get("decisions_json"):
            try:
                s["decisions"] = json.loads(s["decisions_json"])
            except Exception:
                s["decisions"] = []
    return jsonify(sessions)


@app.route("/api/history")
def api_history():
    return jsonify(get_portfolio_history())


@app.route("/api/prices")
def api_prices():
    symbols = request.args.get("symbols", "").upper().split(",")
    symbols = [s.strip() for s in symbols if s.strip()]
    if not symbols:
        symbols = WATCHLIST
    prices = fetch_prices(symbols)
    changes = fetch_daily_changes(symbols)
    result = {
        sym: {"price": prices.get(sym, 0), "change_pct": changes.get(sym, 0)}
        for sym in symbols
    }
    return jsonify(result)


@app.route("/api/force_trade", methods=["POST"])
def api_force_trade():
    # バックグラウンドで実行してすぐ返す（タイムアウト防止）
    t = threading.Thread(target=lambda: ai_trading_session(force=True), daemon=True)
    t.start()
    return jsonify({"status": "started", "trades": 0, "commentary": "トレード開始しました。30秒後に自動で更新されます。"})


@app.route("/api/watchlist")
def api_watchlist():
    return jsonify(WATCHLIST)


@app.route("/api/stock_chart/<symbol>")
def api_stock_chart(symbol):
    """銘柄の過去チャートデータを返す"""
    symbol = symbol.upper()
    period = request.args.get("period", "1mo")   # 1d, 5d, 1mo, 3mo, 6mo, 1y
    interval_map = {
        "1d":  "5m",
        "5d":  "30m",
        "1mo": "1d",
        "3mo": "1d",
        "6mo": "1wk",
        "1y":  "1wk",
    }
    interval = interval_map.get(period, "1d")
    try:
        data = yf.download(
            symbol, period=period, interval=interval,
            auto_adjust=True, progress=False,
        )
        if data.empty:
            return jsonify({"error": "データなし"}), 404

        # yfinanceバージョンによりDataFrame/Seriesどちらでも動くよう対応
        closes = data["Close"]
        if hasattr(closes, "columns"):   # DataFrameの場合は最初の列を使う
            closes = closes.iloc[:, 0]
        closes = closes.dropna()
        result = [
            {"t": str(idx)[:16], "v": round(float(v), 2)}
            for idx, v in closes.items()
        ]
        # 現在価格・騰落率
        latest = result[-1]["v"] if result else 0
        prev   = result[-2]["v"] if len(result) >= 2 else latest
        change_pct = (latest / prev - 1) * 100 if prev else 0

        return jsonify({
            "symbol": symbol,
            "period": period,
            "data": result,
            "latest_price": latest,
            "change_pct": round(change_pct, 2),
        })
    except Exception as e:
        logger.error(f"チャートデータ取得エラー {symbol}: {e}")
        return jsonify({"error": str(e)}), 500


# ── スケジューラー起動 ─────────────────────────────────────────────────────────
def start_scheduler():
    # 30分ごとにAI取引セッション
    scheduler.add_job(
        ai_trading_session,
        "interval",
        minutes=TRADE_INTERVAL_MIN,
        id="ai_trading",
        replace_existing=True,
    )
    # 5分ごとに価格更新・スナップショット
    scheduler.add_job(
        update_prices_job,
        "interval",
        minutes=5,
        id="price_update",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(f"スケジューラー起動 - 取引間隔{TRADE_INTERVAL_MIN}分")


def load_api_key():
    """api_key.txt からAPIキーを読み込む"""
    key_file = os.path.join(os.path.dirname(__file__), "api_key.txt")
    if os.path.exists(key_file):
        key = open(key_file, encoding="utf-8").read().strip()
        if key and key.startswith("sk-"):
            os.environ["ANTHROPIC_API_KEY"] = key
            logger.info("api_key.txt からAPIキーを読み込みました")


if __name__ == "__main__":
    load_api_key()
    init_db()
    start_scheduler()
    logger.info("=" * 60)
    logger.info("AI株式デイトレードシミュレーター起動")
    logger.info(f"仮想資本: ${INITIAL_CAPITAL:,.0f}")
    logger.info(f"ウォッチリスト: {len(WATCHLIST)}銘柄")
    logger.info("ダッシュボード: http://localhost:5001")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        logger.warning("ANTHROPIC_API_KEY が未設定 - ルールベース取引を使用")
    logger.info("=" * 60)
    # 1.5秒後にブラウザを自動で開く
    threading.Timer(1.5, lambda: webbrowser.open("http://localhost:5001")).start()
    app.run(host="0.0.0.0", port=5001, debug=False)
