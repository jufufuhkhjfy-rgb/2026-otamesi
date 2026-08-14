"""
通知チャネル。

app.py の send_discord（embed 整形 + タイムアウト付き POST + 例外握りつぶし）を
一般化したもの。通知の失敗で監視ループを止めないのが最重要の設計方針。

対応: discord / email(SMTP) / file / console

案件では「Discordは使っていない」と言われることが多いので、
メール通知は必ず用意しておく。ヒアリング時に必ず確認する項目。
"""

import json
import os
import smtplib
import time
from email.header import Header
from email.mime.text import MIMEText

import requests

COLOR_DEFAULT = 0x1F6FEB
COLOR_ALERT = 0x3FB950


def _fmt_lines(items, limit=10):
    lines = []
    for it in items[:limit]:
        price = f" ¥{it['price']:,}" if it.get("price") else ""
        url = f"\n{it['url']}" if it.get("url") else ""
        lines.append(f"・{it.get('title', '(無題)')}{price}{url}")
    if len(items) > limit:
        lines.append(f"…ほか {len(items) - limit} 件")
    return "\n".join(lines)


# ===== Discord =====

def send_discord(cfg, items, label=""):
    webhook = cfg.get("webhook_url", "").strip()
    if not webhook:
        return False

    # Discord の embed は1リクエスト10個まで。超える分は本文にまとめる。
    embeds = []
    for it in items[:10]:
        fields = []
        if it.get("price") is not None:
            fields.append({"name": "価格", "value": f"¥{it['price']:,}", "inline": True})
        if it.get("date"):
            fields.append({"name": "日付", "value": str(it["date"])[:60], "inline": True})

        embed = {
            "title": (it.get("title") or "(無題)")[:250],
            "color": COLOR_ALERT if it.get("alert") else COLOR_DEFAULT,
            "footer": {"text": label or cfg.get("label", "自動監視")},
        }
        if it.get("url"):
            embed["url"] = it["url"]
        if it.get("summary"):
            embed["description"] = it["summary"][:300]
        if fields:
            embed["fields"] = fields
        embeds.append(embed)

    payload = {"embeds": embeds}
    if len(items) > 10:
        payload["content"] = f"新着 {len(items)} 件（うち10件を表示）"
    if cfg.get("mention"):
        payload["content"] = f"{cfg['mention']} " + payload.get("content", "")

    try:
        r = requests.post(webhook, json=payload, timeout=10)
        # レート制限は待って1回だけ再送する
        if r.status_code == 429:
            wait = float(r.headers.get("Retry-After", 2))
            time.sleep(min(wait, 30))
            r = requests.post(webhook, json=payload, timeout=10)
        return r.status_code < 300
    except Exception:
        return False


# ===== メール（SMTP）=====

def send_email(cfg, items, label=""):
    """
    設定例:
        {"host": "smtp.gmail.com", "port": 587, "user": "...", "password": "...",
         "to": ["client@example.com"], "subject": "新着通知"}

    Gmail を使う場合はアプリパスワードが必要。顧客に取得してもらう手順を
    納品書に含めること（ここでのつまずきが一番多い）。
    """
    host = cfg.get("host")
    to = cfg.get("to") or []
    if not host or not to:
        return False

    body = f"{label or '自動監視'}: 新着 {len(items)} 件\n\n" + _fmt_lines(items, limit=50)
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = Header(cfg.get("subject", "新着通知"), "utf-8")
    msg["From"] = cfg.get("from") or cfg.get("user", "")
    msg["To"] = ", ".join(to)

    try:
        port = int(cfg.get("port", 587))
        if port == 465:
            server = smtplib.SMTP_SSL(host, port, timeout=20)
        else:
            server = smtplib.SMTP(host, port, timeout=20)
            server.starttls()
        with server:
            if cfg.get("user"):
                server.login(cfg["user"], cfg.get("password", ""))
            server.sendmail(msg["From"], to, msg.as_string())
        return True
    except Exception:
        return False


# ===== ファイル出力（CSV追記）=====

def send_file(cfg, items, label=""):
    """
    Excel で開ける形で追記する。
    「通知はいらないから一覧が欲しい」という顧客向け。
    """
    import csv

    path = cfg.get("path", "output.csv")
    d = os.path.dirname(os.path.abspath(path))
    if d:
        os.makedirs(d, exist_ok=True)
    is_new = not os.path.exists(path)

    # cp932 は Excel がそのまま開ける。utf-8-sig でも可。
    enc = cfg.get("encoding", "utf-8-sig")
    try:
        with open(path, "a", encoding=enc, errors="replace", newline="") as f:
            w = csv.writer(f)
            if is_new:
                w.writerow(["取得日時", "タイトル", "価格", "日付", "URL", "概要"])
            for it in items:
                w.writerow([
                    it.get("found_at", time.strftime("%Y-%m-%d %H:%M:%S")),
                    it.get("title", ""),
                    it.get("price", ""),
                    it.get("date", ""),
                    it.get("url", ""),
                    it.get("summary", ""),
                ])
        return True
    except Exception:
        return False


# ===== コンソール（開発・デモ用）=====

def send_console(cfg, items, label=""):
    print(f"\n=== {label or '新着'}: {len(items)}件 ===")
    print(_fmt_lines(items, limit=20))
    return True


CHANNELS = {
    "discord": send_discord,
    "email": send_email,
    "file": send_file,
    "console": send_console,
}


def dispatch(notify_cfgs, items, label="", logger=print):
    """
    設定された全チャネルに送る。

    1つのチャネルが落ちても他は送る。通知失敗は監視を止める理由にならない。
    """
    if not items:
        return {}
    results = {}
    for cfg in notify_cfgs or []:
        kind = cfg.get("type")
        fn = CHANNELS.get(kind)
        if not fn:
            logger(f"⚠ 未対応の通知type: {kind}")
            continue
        try:
            ok = fn(cfg, items, label)
        except Exception as e:
            ok = False
            logger(f"⚠ 通知エラー({kind}): {str(e)[:100]}")
        results[kind] = ok
        logger(f"{'✅' if ok else '❌'} 通知 {kind}: {len(items)}件")
    return results
