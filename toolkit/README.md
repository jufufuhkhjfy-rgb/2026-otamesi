# toolkit — 受注案件用 自動化テンプレート

「サイトを定期巡回して、条件に合うものだけ通知する」案件を **config.json 1枚で納品する**ためのテンプレート。

MeriWatch（`app.py`）で実証済みの構造を、収集元を差し替えられる形に一般化したもの。
新しく書くコードは基本的にゼロで、設定を書くだけで動く。

---

## 使い方

```bash
pip install -r toolkit/requirements.txt

cp toolkit/config.example.json config.json   # 設定を作る（Windows: copy）

python -m toolkit.watcher --once             # 1回だけ実行して動作確認
python -m toolkit.watcher                    # 常駐して回し続ける
python run_tool.py                           # ダッシュボード + 監視（納品形態）
```

## 構成

| ファイル | 役割 |
|---|---|
| `sources.py` | 収集元アダプタ（rss / html / json_api / csv）。robots.txt チェック込み。rss は RSS 2.0・RSS 1.0(RDF)・Atom に対応 |
| `watcher.py` | 巡回ループ。フィルタ・重複除去・バックオフ |
| `notify.py` | 通知（discord / email / file / console） |
| `store.py` | JSON永続化。アトミック書き込み・既読管理 |
| `dashboard.py` | Flask ダッシュボード（一覧 / 分析 / ログ / 設定） |
| `build_exe.bat` | 納品用 exe ビルド。第2引数に `debug` でコンソール版 |
| `test_clean_env.bat` | Python を外した環境での起動テスト（Home 版でサンドボックスが使えないとき用） |

## 設定の書き方

`config.example.json` に4種類すべての例が入っている。案件では不要なものを
`"enabled": false` にするか削除する。

### 収集元の選択順（重要）

**`json_api` > `rss` > `csv` > `html`** の順で検討する。

`html` はサイト改修のたびに壊れる。壊れれば無償修正を求められるので、
HTMLスクレイピングを含む案件は**必ず保守契約とセットで受ける**。

### フィルタ

```json
"filters": {
  "ng_words":       ["ジャンク", "訳あり"],   // 1つでも含まれたら除外
  "required_words": ["新品", "未使用"],       // 1つでも含まれればOK
  "price_min": 0,
  "price_max": 5000,
  "title_regex": "^\\[急募\\]",
  "require_price": true                       // 価格が取れない項目を捨てる
}
```

`filters` は収集元ごとにも、トップレベルにも書ける（収集元側が優先）。

### RSS の価格

RSS はタイトルから価格を自動では拾わない。「第５回」のような回数表記を価格と
誤認して `¥5` のような値が入り、価格フィルタが壊れるため。
価格を含むフィードでは収集元に `"parse_price_from_title": true` を足す。

### 動作確認済みの公開フィード（デモ用）

| | URL | 形式 |
|---|---|---|
| 厚労省 報道発表 | `https://www.mhlw.go.jp/stf/news.rdf` | RSS 1.0 |
| 気象庁 防災情報 | `https://www.data.jma.go.jp/developer/xml/feed/extra.xml` | Atom |

（`https://www.e-gov.go.jp/rss/public_comment.xml` は現在404。使わないこと）

### 通知

`notify` は配列で、複数指定すると全部に送る。1つが失敗しても他は送られる。

**メール通知は必ず用意しておく。** 「Discordは使っていない」と言われる案件が多い。
Gmail を使う場合はアプリパスワードが必要なので、取得手順を納品書に含めること。

---

## 納品の手順

1. `config.json` を顧客の要件に合わせて書く
2. `python -m toolkit.watcher --once` で意図通りにヒットするか確認
3. `toolkit\build_exe.bat 製品名` で exe を作る
4. **Python に依存していないことを確認する**（ここを飛ばすと必ず問い合わせが来る）
   ```
   toolkit\test_clean_env.bat 製品名
   ```
   PATH から Python を外した状態で、別フォルダにコピーして起動する。
   落ちる場合は `toolkit\build_exe.bat 製品名 debug` でコンソール版を作ると原因が読める
   （`--windowed` だとエラーが表示されないまま終了する）
5. `data\` を空にしてから `dist\` の中身を渡す

顧客に渡すのは **exe と config.json の2ファイルだけ**。
サーバー不要なので月額費用が発生せず、粗利がそのまま残る。

## 実務上の注意

- **初回起動時は通知を抑制している**（`notify_first_run: false`）。これが無いと
  納品初日に顧客のDiscordが数百件で埋まる。全件を既読として記録し、次回以降の
  差分だけ通知する。
- **設定はダッシュボードの設定タブから編集でき、再起動不要**で次の巡回から反映される。
  顧客がJSONを直接触れなくても運用できるので、保守の問い合わせが減る。
- `data/records.json` と `data/seen.json` を消すと、次回は全件が新着扱いになる。
- ダッシュボードは Chart.js を CDN から読む。オフライン環境ではグラフだけ
  表示されず警告が出る（一覧・通知は正常に動く）。完全オフライン納品が要件なら
  Chart.js をローカルに同梱する。

## やらないこと

- **ログインが必要なサイトのスクレイピング**（規約違反になる場合が多い）
- **robots.txt で拒否されているサイト**（`sources.py` が例外を投げて止める）
- **非公開APIの署名を再現する方式**（`app.py` の DPoP のような手法）。
  仕様変更で予告なく壊れ、保守が無限に発生する。案件には持ち込まない。
