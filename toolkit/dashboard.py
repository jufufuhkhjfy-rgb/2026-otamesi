"""
ダッシュボード。Flask + タブUI + Chart.js。

app.py のダッシュボード構成（タブ切り替え・summary-grid・ダークテーマ・
Chart.js集計）を案件横断で使える形にしたもの。

    python -m toolkit.dashboard

exe 化したときはこのファイルがエントリポイントになる。
監視スレッドも一緒に起動するので、顧客は exe をダブルクリックするだけでよい。
"""

import json
import os
import sys
import threading
import time
import webbrowser

from flask import Flask, Response, jsonify, request

from .store import load_json, save_json
from .watcher import Watcher, add_log, get_log, load_config

app = Flask(__name__)
# Flask は既定でJSONのキーをアルファベット順に並べ替える。
# 設定タブは config.json をそのまま編集させる画面なので、
# 並べ替えられると「label や sources の並び」が崩れて読みにくくなる。
app.json.sort_keys = False
PORT = int(os.environ.get("TOOLKIT_PORT", "5057"))
_watcher = None


HTML = r"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__LABEL__</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<style>
* { box-sizing:border-box; margin:0; padding:0; }
body { font-family:'Segoe UI',system-ui,'Yu Gothic UI','Meiryo',sans-serif;
       background:#0d1117; color:#e6edf3; font-size:15px; line-height:1.8; }
.stat-val,.summary-value,td.num { font-variant-numeric:tabular-nums; }
.header { background:#161b22; padding:14px 24px; border-bottom:1px solid #30363d;
          display:flex; align-items:center; gap:14px; position:sticky; top:0; z-index:50; }
.header h1 { font-size:1.15em; font-weight:700; }
.badge { padding:4px 13px; border-radius:20px; font-size:.85em; font-weight:700; }
.badge.on  { background:#132d1c; color:#3fb950; border:1px solid #238636; }
.badge.off { background:#2d1618; color:#f85149; border:1px solid #6e3030; }
.spacer { flex:1; }
.btn { padding:8px 18px; border:none; border-radius:6px; font-weight:700;
       cursor:pointer; font-family:inherit; font-size:.9em; }
.btn-go   { background:#238636; color:#fff; }
.btn-stop { background:#6e3030; color:#ffb3ae; }
.btn-sub  { background:#21262d; color:#c3ccd6; border:1px solid #30363d; }
.tabs { display:flex; gap:4px; padding:0 24px; background:#161b22;
        border-bottom:1px solid #30363d; overflow-x:auto; }
.tab-btn { padding:11px 20px; border:none; background:transparent; color:#b6c2ce;
           font-size:.95em; font-weight:600; cursor:pointer; font-family:inherit;
           border-bottom:3px solid transparent; white-space:nowrap; }
.tab-btn.active { color:#e6edf3; border-bottom-color:#1f6feb; }
.tab-content { display:none; }
.tab-content.active { display:block; }
.container { max-width:1180px; margin:0 auto; padding:22px 24px 60px; }
.card { background:#161b22; border:1px solid #30363d; border-radius:10px;
        padding:18px; margin-bottom:16px; }
.card-title { font-weight:700; margin-bottom:12px; font-size:1em; }
.summary-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr));
                gap:12px; margin-bottom:16px; }
.summary-card { background:#161b22; border:1px solid #30363d; border-radius:10px; padding:15px 17px; }
.summary-label { font-size:.85em; color:#b6c2ce; font-weight:600; margin-bottom:6px; }
.summary-value { font-size:1.6em; font-weight:700; }
.green { color:#3fb950; }
table { width:100%; border-collapse:collapse; font-size:.92em; }
th { text-align:left; padding:10px 12px; color:#b6c2ce; font-size:.88em;
     border-bottom:1px solid #30363d; white-space:nowrap; }
td { padding:11px 12px; border-bottom:1px solid #21262d; vertical-align:top; }
tbody tr:hover { background:#1c2230; }
a { color:#58a6ff; text-decoration:none; }
a:hover { text-decoration:underline; }
.log-box { background:#0d1117; border:1px solid #21262d; border-radius:6px; padding:12px;
           height:440px; overflow-y:auto; font-family:Consolas,'Courier New',monospace;
           font-size:.88em; line-height:1.8; white-space:pre-wrap; }
textarea { width:100%; min-height:420px; background:#0d1117; color:#e6edf3;
           border:1px solid #30363d; border-radius:6px; padding:12px;
           font-family:Consolas,monospace; font-size:.88em; line-height:1.7; }
input.search { width:100%; background:#0d1117; color:#e6edf3; border:1px solid #30363d;
               border-radius:6px; padding:9px 12px; font-family:inherit; font-size:.95em; }
.charts { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
@media (max-width:760px){ .charts{ grid-template-columns:1fr; } }
.empty { text-align:center; color:#7d8590; padding:40px 0; }
.toast { position:fixed; bottom:24px; left:50%; transform:translateX(-50%) translateY(90px);
         background:#238636; color:#fff; padding:11px 26px; border-radius:8px;
         font-weight:700; transition:transform .25s; z-index:99; }
.toast.show { transform:translateX(-50%) translateY(0); }
.src-tag { display:inline-block; background:#21262d; border:1px solid #30363d;
           border-radius:5px; padding:1px 8px; font-size:.82em; color:#b6c2ce; }
</style>
</head>
<body>

<div class="header">
  <h1>__LABEL__</h1>
  <span class="badge off" id="stateBadge">停止中</span>
  <span class="spacer"></span>
  <button class="btn btn-go"   id="btnStart" onclick="ctl('start')">▶ 監視開始</button>
  <button class="btn btn-stop" id="btnStop"  onclick="ctl('stop')" style="display:none">■ 停止</button>
  <button class="btn btn-sub" onclick="ctl('once')">今すぐ1回</button>
</div>

<div class="tabs">
  <button class="tab-btn active" onclick="tab('list',this)">📋 一覧</button>
  <button class="tab-btn" onclick="tab('analytics',this)">📊 分析</button>
  <button class="tab-btn" onclick="tab('log',this)">🖥 ログ</button>
  <button class="tab-btn" onclick="tab('settings',this)">⚙️ 設定</button>
</div>

<div id="tab-list" class="tab-content active"><div class="container">
  <div class="summary-grid">
    <div class="summary-card"><div class="summary-label">総取得件数</div><div class="summary-value" id="s-total">0</div></div>
    <div class="summary-card"><div class="summary-label">今日</div><div class="summary-value green" id="s-today">0</div></div>
    <div class="summary-card"><div class="summary-label">収集元</div><div class="summary-value" id="s-src">0</div></div>
    <div class="summary-card"><div class="summary-label">最終取得</div><div class="summary-value" id="s-last" style="font-size:1.05em">-</div></div>
  </div>
  <div class="card">
    <input class="search" id="q" placeholder="キーワードで絞り込み" oninput="renderList()">
  </div>
  <div class="card">
    <div class="card-title">取得データ</div>
    <div style="overflow-x:auto">
      <table><thead><tr>
        <th>取得日時</th><th>収集元</th><th>タイトル</th><th>価格</th><th>日付</th>
      </tr></thead><tbody id="listBody"></tbody></table>
      <div class="empty" id="listEmpty">まだデータがありません</div>
    </div>
  </div>
</div></div>

<div id="tab-analytics" class="tab-content"><div class="container">
  <div class="charts">
    <div class="card"><div class="card-title">日別 取得件数</div><canvas id="chartDaily"></canvas></div>
    <div class="card"><div class="card-title">収集元の内訳</div><canvas id="chartSrc"></canvas></div>
  </div>
  <div class="card" id="chartFallback" style="display:none;color:#d29922">
    グラフの読み込みに失敗しました（オフライン環境の可能性があります）。一覧タブのデータは正常です。
  </div>
</div></div>

<div id="tab-log" class="tab-content"><div class="container">
  <div class="card"><div class="card-title">実行ログ</div><div class="log-box" id="logBox"></div></div>
</div></div>

<div id="tab-settings" class="tab-content"><div class="container">
  <div class="card">
    <div class="card-title">config.json</div>
    <textarea id="cfgText" spellcheck="false"></textarea>
    <div style="margin-top:12px;display:flex;gap:10px;align-items:center">
      <button class="btn btn-go" onclick="saveCfg()">💾 保存</button>
      <button class="btn btn-sub" onclick="loadCfg()">↩ 読み直す</button>
      <span style="color:#7d8590;font-size:.88em">保存すると次の巡回から反映されます（再起動不要）</span>
    </div>
    <div id="cfgErr" style="color:#f85149;margin-top:10px"></div>
  </div>
</div></div>

<div class="toast" id="toast">保存しました</div>

<script>
let RECORDS = [], CHARTS = {};
const esc = s => String(s??'').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

function tab(name, el){
  document.querySelectorAll('.tab-content').forEach(e=>e.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(e=>e.classList.remove('active'));
  document.getElementById('tab-'+name).classList.add('active');
  el.classList.add('active');
  if(name==='analytics') buildCharts();
  if(name==='settings')  loadCfg();
}
function toast(msg){ const t=document.getElementById('toast'); t.textContent=msg;
  t.classList.add('show'); setTimeout(()=>t.classList.remove('show'),1900); }

async function ctl(action){
  const r = await (await fetch('/api/'+action, {method:'POST'})).json();
  toast(r.message || 'OK'); refresh();
}

function renderList(){
  const q = (document.getElementById('q').value||'').toLowerCase();
  const rows = RECORDS.filter(r => !q ||
    (r.title||'').toLowerCase().includes(q) || (r.summary||'').toLowerCase().includes(q));
  document.getElementById('listEmpty').style.display = rows.length ? 'none' : 'block';
  document.getElementById('listBody').innerHTML = rows.slice(0,400).map(r => `
    <tr>
      <td class="num" style="color:#8b949e;white-space:nowrap">${esc(r.found_at||'')}</td>
      <td><span class="src-tag">${esc(r.source||'-')}</span></td>
      <td>${r.url ? `<a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.title)}</a>`
                  : esc(r.title)}
          ${r.summary ? `<div style="color:#8b949e;font-size:.88em">${esc(r.summary).slice(0,120)}</div>` : ''}</td>
      <td class="num">${r.price!=null ? '¥'+Number(r.price).toLocaleString() : '-'}</td>
      <td style="color:#8b949e">${esc(r.date||'-')}</td>
    </tr>`).join('');
}

function buildCharts(){
  if (typeof Chart === 'undefined'){ document.getElementById('chartFallback').style.display='block'; return; }
  const daily = {}, bysrc = {};
  for (const r of RECORDS){
    const d = (r.found_at||'').slice(0,10); if(d) daily[d]=(daily[d]||0)+1;
    const s = r.source||'その他';           bysrc[s]=(bysrc[s]||0)+1;
  }
  const days = Object.keys(daily).sort().slice(-30);
  const srcs = Object.keys(bysrc).sort((a,b)=>bysrc[b]-bysrc[a]);
  const AXIS = { x:{ticks:{color:'#a3b0bd'},grid:{display:false}},
                 y:{ticks:{color:'#a3b0bd',precision:0},grid:{color:'#21262d'},beginAtZero:true} };
  for (const k in CHARTS){ CHARTS[k].destroy(); delete CHARTS[k]; }
  CHARTS.daily = new Chart(document.getElementById('chartDaily'), {
    type:'bar',
    data:{ labels:days, datasets:[{ data:days.map(d=>daily[d]), backgroundColor:'#1f6feb', borderRadius:4 }] },
    options:{ responsive:true, plugins:{legend:{display:false}}, scales:AXIS } });
  CHARTS.src = new Chart(document.getElementById('chartSrc'), {
    type:'doughnut',
    data:{ labels:srcs, datasets:[{ data:srcs.map(s=>bysrc[s]), borderWidth:0,
      backgroundColor:['#1f6feb','#238636','#da3633','#f0c040','#9b59b6','#1abc9c','#e67e22'] }] },
    options:{ responsive:true, plugins:{legend:{position:'right',labels:{color:'#e6edf3'}}} } });
}

async function loadCfg(){
  const r = await (await fetch('/api/config')).json();
  document.getElementById('cfgText').value = JSON.stringify(r, null, 2);
  document.getElementById('cfgErr').textContent = '';
}
async function saveCfg(){
  const errEl = document.getElementById('cfgErr');
  let parsed;
  try { parsed = JSON.parse(document.getElementById('cfgText').value); }
  catch(e){ errEl.textContent = 'JSONの書式エラー: ' + e.message; return; }
  const r = await (await fetch('/api/config', {method:'POST',
    headers:{'Content-Type':'application/json'}, body:JSON.stringify(parsed)})).json();
  if (r.ok){ errEl.textContent=''; toast('保存しました'); } else { errEl.textContent = r.error||'保存に失敗しました'; }
}

async function refresh(){
  try {
    const s = await (await fetch('/api/status')).json();
    const b = document.getElementById('stateBadge');
    b.textContent = s.running ? '監視中' : '停止中';
    b.className = 'badge ' + (s.running ? 'on' : 'off');
    document.getElementById('btnStart').style.display = s.running ? 'none' : '';
    document.getElementById('btnStop').style.display  = s.running ? '' : 'none';

    RECORDS = await (await fetch('/api/records')).json();
    const today = new Date().toISOString().slice(0,10);
    document.getElementById('s-total').textContent = RECORDS.length.toLocaleString();
    document.getElementById('s-today').textContent =
      RECORDS.filter(r => (r.found_at||'').slice(0,10) === today).length.toLocaleString();
    document.getElementById('s-src').textContent = new Set(RECORDS.map(r=>r.source||'-')).size;
    document.getElementById('s-last').textContent = RECORDS[0]?.found_at || '-';
    renderList();

    document.getElementById('logBox').textContent = (await (await fetch('/api/log')).json()).join('\n');
    if (document.getElementById('tab-analytics').classList.contains('active')) buildCharts();
  } catch(e){ /* サーバー再起動中などは次の周期で復帰する */ }
}
refresh();
setInterval(refresh, 5000);
</script>
</body>
</html>"""


# ===== ルート =====

@app.route("/")
def index():
    label = _watcher.cfg.get("label", "自動監視ツール") if _watcher else "自動監視ツール"
    return Response(HTML.replace("__LABEL__", label), content_type="text/html; charset=utf-8")


@app.route("/api/status")
def api_status():
    return jsonify({
        "running": bool(_watcher and _watcher.running),
        "label": _watcher.cfg.get("label", "") if _watcher else "",
    })


@app.route("/api/records")
def api_records():
    return jsonify(_watcher.store.records() if _watcher else [])


@app.route("/api/log")
def api_log():
    return jsonify(get_log())


@app.route("/api/start", methods=["POST"])
def api_start():
    _watcher.start_background()
    return jsonify({"ok": True, "message": "監視を開始しました"})


@app.route("/api/stop", methods=["POST"])
def api_stop():
    _watcher.stop()
    return jsonify({"ok": True, "message": "停止しました"})


@app.route("/api/once", methods=["POST"])
def api_once():
    threading.Thread(target=_watcher.run_once, daemon=True).start()
    return jsonify({"ok": True, "message": "1回実行しました"})


@app.route("/api/config", methods=["GET", "POST"])
def api_config():
    if request.method == "GET":
        return jsonify(load_json(_watcher.config_path, {}))
    try:
        save_json(_watcher.config_path, request.json or {})
        _watcher.cfg = load_config(_watcher.config_path)
        add_log("⚙ 設定を保存しました")
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:200]})


def main():
    global _watcher
    config_path = None
    for i, a in enumerate(sys.argv):
        if a == "--config" and i + 1 < len(sys.argv):
            config_path = sys.argv[i + 1]

    _watcher = Watcher(config_path)
    if _watcher.cfg.get("autostart", True):
        _watcher.start_background()

    threading.Thread(
        target=lambda: app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False),
        daemon=True,
    ).start()
    time.sleep(1.2)

    url = f"http://127.0.0.1:{PORT}"
    add_log(f"ダッシュボード: {url}")

    # 納品先ではデスクトップアプリとして見せたいので pywebview を優先し、
    # 無ければ既定のブラウザで開く（app.py と同じ二段構え）。
    try:
        import webview

        def on_closed():
            _watcher.stop()
            os._exit(0)

        win = webview.create_window(
            _watcher.cfg.get("label", "自動監視ツール"), url,
            width=1240, height=820, min_size=(820, 520),
        )
        win.events.closed += on_closed
        webview.start()
    except ImportError:
        webbrowser.open(url)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            _watcher.stop()


if __name__ == "__main__":
    main()
