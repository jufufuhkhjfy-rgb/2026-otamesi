"""
収集元アダプタ。

対応: rss / html / json_api / csv
どれも共通の「正規化アイテム」を返すので、後段（フィルタ・通知・保存）は
収集元の違いを知らなくてよい。

    {"id": str, "title": str, "url": str, "price": int|None,
     "date": str, "summary": str, "raw": dict}


==============================================================================
受注時の必須確認事項 — ここを飛ばすと後で必ず揉める
==============================================================================
1. robots.txt を確認する。check_robots() が False を返す対象は受けない。
2. サイトの利用規約に自動アクセス禁止の記載がないか確認する。
3. ログインが必要なページはスクレイピングしない（規約違反になる場合が多い）。
4. 公式API・RSS・CSVが提供されているなら必ずそちらを使う。
   HTMLスクレイピングは最後の手段。サイト改修のたびに壊れ、保守が赤字になる。
5. アクセス間隔は最低でも数秒空ける。相手のサーバーに負荷をかけない。

顧客が「規約は気にしないでいい」と言っても、壊れたときに責任を負うのは
こちら側。断れる案件は断ったほうが長期的に儲かる。
==============================================================================
"""

import csv as _csv
import hashlib
import io
import json
import re
import time
import urllib.robotparser
from urllib.parse import urljoin, urlparse

import requests

USER_AGENT = "Mozilla/5.0 (compatible; AutomationToolkit/1.0)"
DEFAULT_TIMEOUT = 20

_robots_cache = {}


# ===== 共通ユーティリティ =====

def check_robots(url, user_agent=USER_AGENT):
    """
    robots.txt で許可されているかを返す。

    取得できなかった場合は True（許可）を返す。robots.txt が無いサイトは
    多く、それだけで拒否すると実務が回らないため。
    ただし「明示的に Disallow されている」場合は必ず False を返す。
    """
    parsed = urlparse(url)
    root = f"{parsed.scheme}://{parsed.netloc}"
    if root not in _robots_cache:
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(urljoin(root, "/robots.txt"))
        try:
            rp.read()
        except Exception:
            rp = None
        _robots_cache[root] = rp
    rp = _robots_cache[root]
    if rp is None:
        return True
    try:
        return rp.can_fetch(user_agent, url)
    except Exception:
        return True


def make_id(*parts):
    """URL や タイトルから安定した重複判定キーを作る。"""
    joined = "|".join(str(p) for p in parts if p)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:16]


def parse_price(text):
    """「¥1,980」「1980円」「1,980 円」などから整数を取り出す。"""
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return int(text)
    m = re.search(r"[\d,]+", str(text).replace("，", ","))
    if not m:
        return None
    try:
        return int(m.group().replace(",", ""))
    except ValueError:
        return None


def fetch(url, respect_robots=True, headers=None, timeout=DEFAULT_TIMEOUT):
    if respect_robots and not check_robots(url):
        raise PermissionError(
            f"robots.txt により拒否されています: {url}\n"
            f"この収集元は使えません。公式API/RSS/CSVの提供がないか確認してください。"
        )
    h = {"User-Agent": USER_AGENT, "Accept-Language": "ja,en;q=0.8"}
    if headers:
        h.update(headers)
    resp = requests.get(url, headers=h, timeout=timeout)
    resp.raise_for_status()
    return resp


def _decode(resp, encoding=None):
    """
    HTML を正しい文字コードで読む。

    requests は Content-Type に charset が無いと HTTP仕様に従って
    ISO-8859-1 とみなすため、日本語サイトがそのまま文字化けする。
    charset の指定が無いときは中身から推定する。国内サイトは Shift_JIS や
    EUC-JP を charset 無しで返すことがあり、ここを外すと全項目が壊れる。

    設定で "encoding": "cp932" のように明示された場合はそれを最優先する。
    """
    if encoding:
        return resp.content.decode(encoding, "replace")
    ctype = resp.headers.get("content-type", "").lower()
    if "charset=" not in ctype:
        resp.encoding = resp.apparent_encoding or "utf-8"
    return resp.text


def _text(node):
    return node.get_text(" ", strip=True) if node is not None else ""


def _dig(obj, path):
    """"data.items[0].name" のようなパスで dict/list を辿る。"""
    cur = obj
    for token in re.split(r"\.", path):
        if not token:
            continue
        m = re.match(r"^([^\[\]]*)((?:\[\d+\])*)$", token)
        if not m:
            return None
        key, idx = m.group(1), m.group(2)
        if key:
            if not isinstance(cur, dict):
                return None
            cur = cur.get(key)
        for i in re.findall(r"\[(\d+)\]", idx or ""):
            if not isinstance(cur, list) or int(i) >= len(cur):
                return None
            cur = cur[int(i)]
        if cur is None:
            return None
    return cur


# ===== RSS / Atom =====

def from_rss(cfg):
    """
    設定例:
        {"type": "rss", "url": "https://example.com/feed.xml"}

    RSS 2.0 / RSS 1.0(RDF) / Atom を扱う。標準ライブラリのみで解析するので
    exe 化時の依存が増えない。

    価格はタイトルから自動では拾わない。「第５回」のような回数表記を
    価格と誤認して ¥5 のような嘘の値が入り、価格フィルタが壊れるため。
    価格を含むフィードでは "parse_price_from_title": true を指定する。
    """
    import xml.etree.ElementTree as ET

    resp = fetch(cfg["url"], cfg.get("respect_robots", True))
    root = ET.fromstring(resp.content)
    # 名前空間を落として、どの形式でも同じ書き方で読めるようにする。
    # RSS 1.0(RDF) は要素が名前空間つきで、これをやらないと1件も取れない。
    # 官公庁サイトの .rdf でよく使われている形式なので落とせない。
    for el in root.iter():
        if isinstance(el.tag, str) and "}" in el.tag:
            el.tag = el.tag.rsplit("}", 1)[1]
        for k in list(el.attrib):
            if "}" in k:
                el.attrib[k.rsplit("}", 1)[1]] = el.attrib.pop(k)

    entries = root.findall(".//item") or root.findall(".//entry")
    items = []

    def pick(e, *names):
        """最初に中身のあったタグのテキストを返す"""
        for n in names:
            v = e.findtext(n)
            if v and v.strip():
                return v.strip()
        return ""

    for e in entries:
        title = pick(e, "title")

        # RSS は <link>URL</link>、Atom は <link href="URL"/>
        link = pick(e, "link")
        if not link:
            for el in e.findall("link"):
                if el.get("href"):
                    link = el.get("href")
                    break

        # pubDate=RSS2.0 / date=RSS1.0のdc:date / updated,published=Atom
        date = pick(e, "pubDate", "date", "updated", "published")
        summary = pick(e, "description", "summary", "content")
        uid = pick(e, "guid", "id") or e.get("about") or link

        summary = re.sub(r"<[^>]+>", " ", summary)
        summary = re.sub(r"\s+", " ", summary).strip()

        items.append({
            "id": make_id(uid or title),
            "title": title,
            "url": link,
            "price": parse_price(title) if cfg.get("parse_price_from_title") else None,
            "date": date,
            "summary": summary[:500],
            "raw": {},
        })
    return items


# ===== HTML スクレイピング =====

def from_html(cfg):
    """
    設定例:
        {
          "type": "html",
          "url": "https://example.com/list",
          "item_selector": ".product-card",
          "fields": {
            "title": ".product-name",
            "url":   {"selector": "a", "attr": "href"},
            "price": ".price",
            "date":  ".posted-at"
          }
        }

    fields の値は CSS セレクタ文字列か、{"selector":..., "attr":...} の辞書。
    attr を省略するとテキストを取る。url は相対パスを自動で絶対化する。

    ※ HTMLスクレイピングはサイト改修で壊れる。保守契約とセットで受けること。
    """
    from bs4 import BeautifulSoup

    resp = fetch(cfg["url"], cfg.get("respect_robots", True))
    soup = BeautifulSoup(_decode(resp, cfg.get("encoding")), "html.parser")
    nodes = soup.select(cfg["item_selector"])
    fields = cfg.get("fields", {})
    items = []

    for node in nodes:
        rec = {}
        for name, spec in fields.items():
            if isinstance(spec, dict):
                sel, attr = spec.get("selector"), spec.get("attr")
            else:
                sel, attr = spec, None
            target = node.select_one(sel) if sel else node
            if target is None:
                rec[name] = ""
                continue
            rec[name] = (target.get(attr, "") or "") if attr else _text(target)

        url = rec.get("url", "")
        if url:
            url = urljoin(cfg["url"], url)

        title = rec.get("title", "")
        if not title and not url:
            continue

        items.append({
            "id": make_id(url or title),
            "title": title,
            "url": url,
            "price": parse_price(rec.get("price")),
            "date": rec.get("date", ""),
            "summary": rec.get("summary", "")[:500],
            "raw": rec,
        })
    return items


# ===== JSON API =====

def from_json_api(cfg):
    """
    設定例:
        {
          "type": "json_api",
          "url": "https://example.com/api/items",
          "items_path": "data.items",
          "fields": {"title": "name", "url": "link", "price": "price"}
        }

    公式APIが提供されているならこれが第一選択。壊れにくく保守が軽い。
    """
    resp = fetch(cfg["url"], cfg.get("respect_robots", False),
                 headers=cfg.get("headers"))
    data = resp.json()
    rows = _dig(data, cfg["items_path"]) if cfg.get("items_path") else data
    if not isinstance(rows, list):
        raise ValueError(
            f"items_path '{cfg.get('items_path')}' がリストを指していません: {type(rows).__name__}"
        )

    fields = cfg.get("fields", {})
    items = []
    for row in rows:
        rec = {name: _dig(row, path) for name, path in fields.items()}
        url = str(rec.get("url") or "")
        if url:
            url = urljoin(cfg["url"], url)
        title = str(rec.get("title") or "")
        items.append({
            "id": make_id(rec.get("id") or url or title),
            "title": title,
            "url": url,
            "price": parse_price(rec.get("price")),
            "date": str(rec.get("date") or ""),
            "summary": str(rec.get("summary") or "")[:500],
            "raw": rec,
        })
    return items


# ===== CSV（ローカルファイル / URL）=====

def from_csv(cfg):
    """
    設定例:
        {
          "type": "csv",
          "path": "C:/data/list.csv",
          "encoding": "cp932",
          "fields": {"title": "商品名", "url": "URL", "price": "価格"}
        }

    顧客が Excel で管理しているデータを扱う案件で使う。
    「毎朝このCSVを開いて条件に合う行を探している」は非常によくある業務。
    """
    src = cfg.get("path") or cfg.get("url")
    enc = cfg.get("encoding", "utf-8-sig")

    if str(src).startswith("http"):
        text = fetch(src, cfg.get("respect_robots", True)).content.decode(enc, "replace")
    else:
        with open(src, "r", encoding=enc, errors="replace") as f:
            text = f.read()

    fields = cfg.get("fields", {})
    items = []
    for row in _csv.DictReader(io.StringIO(text)):
        rec = {name: row.get(col, "") for name, col in fields.items()} if fields else dict(row)
        title = rec.get("title") or next(iter(row.values()), "")
        items.append({
            "id": make_id(rec.get("id") or rec.get("url") or json.dumps(row, ensure_ascii=False)),
            "title": str(title),
            "url": str(rec.get("url") or ""),
            "price": parse_price(rec.get("price")),
            "date": str(rec.get("date") or ""),
            "summary": str(rec.get("summary") or "")[:500],
            "raw": dict(row),
        })
    return items


ADAPTERS = {
    "rss": from_rss,
    "html": from_html,
    "json_api": from_json_api,
    "csv": from_csv,
}


def collect(cfg):
    """設定の type に応じたアダプタを呼ぶ。"""
    kind = cfg.get("type")
    if kind not in ADAPTERS:
        raise ValueError(
            f"未対応の収集元 type: {kind!r}（対応: {', '.join(ADAPTERS)}）"
        )
    return ADAPTERS[kind](cfg)
