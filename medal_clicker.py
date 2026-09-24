"""
メダルゲーム連打ボット（GAPOLI バベルのメダルタワーW 想定）
A（左）と D（右）のキーを連打し、画面を見て次の二つを自動でさばく。
・メダル交換ダイアログ → 100 のプルダウン → 3000 を選ぶ → プレイ開始
　→ 説明の画面を閉じる一押し → ここから連打を再開
・盤面に赤いボタンが出ている間は、そこを叩き続ける
・コンティニューチャンス → やめる
・プレイ上限に到達 → プレイ上限数追加 → 自動追加のキャンセル → 連打を停止
・自動追加のキャンセルの後は、決めた時間だけ待ってから右上の精算
・精算確認 → 精算（ここで A と D は止める）
・リザルト → 次へ → 次へ2 → 続けて遊ぶ → 一覧の三番目 → プレイ → レート決定
そのあと説明の画面を黙って待ち、メダル交換をさばくと連打に戻る。

決まった順になぞるのではなく、毎回いまの盤面を見て手を選ぶ。どれにも
当てはまらない画面が続いたらゲーム中とみなして連打に入るので、途中で
止めて別の画面を触ってから戻ってきても、その場から続けられる。

覚えた座標は登録したときのまま一切動かさない。ブラウザの位置やページの
送りでゲームの枠がずれたぶんは、見本を探して割り出し、動かしている間の
ずれとして持って押すときに足す。座標そのものを書き換えると、外した探索
が積み重なって登録が壊れていくため。
F8 開始/停止、F10 終了。ブラウザ側をアクティブにしておくこと。
"""
import sys
import json
import time
import random
import ctypes
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

from pynput import keyboard as pynput_keyboard

try:
    import numpy as np
    from PIL import Image
    HAS_VISION = True
except ImportError:
    HAS_VISION = False

try:
    import mss
    USE_MSS = True
except ImportError:
    USE_MSS = False
    if HAS_VISION:
        from PIL import ImageGrab

IS_WIN = sys.platform == 'win32'
if IS_WIN:
    import ctypes.wintypes
    user32 = ctypes.windll.user32
    try:
        # 高 DPI でも座標がずれないようにする
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass
    try:
        # 既定のタイマー分解能は 15ms 前後。毎秒 100 回には粗すぎるので上げる
        ctypes.windll.winmm.timeBeginPeriod(1)
    except (AttributeError, OSError):
        pass
else:
    user32 = None

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP   = 0x0004
MOUSEEVENTF_WHEEL    = 0x0800
WHEEL_DELTA          = 120
KEYEVENTF_KEYUP      = 0x0002

VK = {'A': 0x41, 'D': 0x44}

VERSION = 'v19'   # 入れ替えたか分かるように、窓の題に出す

CONFIG_PATH = Path(__file__).with_name('medal_clicker.json')
BACKUP_PATH = Path(__file__).with_name('medal_clicker.bak.json')
# 画面が出ているかの判定に使う見本。ここに無いものは座標だけ覚える
ANCHOR_PATHS = {
    'menu':  Path(__file__).with_name('medal_clicker_anchor.png'),
    'quit':  Path(__file__).with_name('medal_clicker_quit.png'),
    'limit': Path(__file__).with_name('medal_clicker_limit.png'),
    'cash2': Path(__file__).with_name('medal_clicker_cash2.png'),
    'next':  Path(__file__).with_name('medal_clicker_next.png'),
    'next2': Path(__file__).with_name('medal_clicker_next2.png'),
    'again': Path(__file__).with_name('medal_clicker_again.png'),
    'game':  Path(__file__).with_name('medal_clicker_game.png'),
    'play2': Path(__file__).with_name('medal_clicker_play2.png'),
    'rate':  Path(__file__).with_name('medal_clicker_rate.png'),
    'red':   Path(__file__).with_name('medal_clicker_red.png'),
    'play':  Path(__file__).with_name('medal_clicker_play.png'),
}

# 裏取りに使う組み合わせ。同じダイアログの離れた二か所がそろって初めて
# その画面とみなす。メダル交換は外すとコインを使ってしまうので特に固く。
CONFIRM = {'menu': 'play'}

# 続けて何回見えたら本物とみなすか。書いていない画面は二回
NEED = {'menu': 3}

# 記録ボタンの呼び名
LABELS = {
    'menu':   '交換画面の 100',
    '3000':   'スクロール後の 3000',
    'play':   'プレイ開始',
    'after':  '開始後に押す場所',
    'quit':   'コンティニューの やめる',
    'limit':  'プレイ上限数追加',
    'cancel': '自動追加のキャンセル',
    'cash':   '右上の精算',
    'cash2':  '精算確認の精算',
    'next':   'リザルトの次へ',
    'next2':  '二枚目の次へ',
    'again':  '続けて遊ぶ',
    'game':   '一覧の三番目',
    'play2':  'ゲーム説明のプレイ',
    'rate':   'レート決定',
    'red':    '盤面の赤いボタン',
    'idle':   '空押しの場所',
}

# 記録ボタンと、それをしまう変数の対応
POINTS = {
    'menu':   'pos_menu',
    '3000':   'pos_3000',
    'play':   'pos_play',
    'quit':   'pos_quit',
    'limit':  'pos_limit',
    'cancel': 'pos_cancel',
    'cash':   'pos_cash',
    'cash2':  'pos_cash2',
    'next':   'pos_next',
    'next2':  'pos_next2',
    'again':  'pos_again',
    'game':   'pos_game',
    'play2':  'pos_play2',
    'rate':   'pos_rate',
    'after':  'pos_after',
    'red':    'pos_red',
    'idle':   'pos_idle',
}

MAX_PRESS   = 0.025   # キーを押している時間の上限。速度を上げると自動で短くなる
JITTER      = 0.15    # 間隔を ±15% 揺らす
# 見本はボタンだけでなく周りごと切り取る。青いボタン同士は形も色も似て
# いて、ボタンだけでは見分けがつかないため。大きさは画面ごとに選べる。
# 背景が動く場所では小さめ、似たダイアログの見分けには大きめが向く。
ANCHOR_SIZE = 320     # 新しく取る見本の一辺（ピクセル）
ANCHOR_W    = ANCHOR_SIZE
ANCHOR_H    = ANCHOR_SIZE
MATCH_THRESHOLD = 20  # 区画ごとの差の真ん中がこれ未満なら「同じ画面」とみなす
GRID            = 8   # 見本を縦横この数に区切り、食い違いの大きい区画を見る
WORST_RATIO     = 3   # 一角の差がゆるさのこの倍を超えたら、別の画面とみなす
WATCH_INTERVAL  = 0.7
WAIT_MIN        = 30  # プレイ上限をさばいてから精算するまでの待ち時間（分）
IDLE_HITS       = 3   # どの画面にも当てはまらない回数。これで盤面とみなす
RED_CPS         = 15  # 赤いボタンを叩く速さ（回/秒）
RED_MAX         = 30  # 叩き続ける上限（秒）。見間違いで延々押さないための保険

# ブラウザの位置やページの送り具合で、ゲームの枠ごと数十ピクセル動く。
# 空振りが続いたら見本を周りから探し直して、覚えた座標をまとめてずらす。
ALIGN_PAD   = 120     # 探す範囲（上下左右にこのピクセルぶん）
ALIGN_STEP  = 8       # 探すときの粗さ。8 なら 8 ピクセル刻みで当たりを付ける
AIM_MAX     = 40      # 見つけた画面を押す前に直してよいずれの上限
POKE_MIN    = 3       # 何分ごとに画面をひと押しするか
ALIGN_TIGHT = 0.7     # 探して見つけたと認めるのは、ふだんのゆるさのこの割合まで
ALIGN_FLAT  = 10      # のっぺりした見本は他の場所とも似るので、探す目印には使わない


def cursor_pos():
    if not IS_WIN:
        return (0, 0)
    pt = ctypes.wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return (pt.x, pt.y)


def precise_sleep(sec):
    """time.sleep は短い待ちで精度が出ないので、最後だけ空回しで詰める。"""
    if sec <= 0:
        return
    end = time.perf_counter() + sec
    if sec > 0.002:
        time.sleep(sec - 0.002)
    while time.perf_counter() < end:
        pass


def tap_key(vk, press_sec):
    scan = user32.MapVirtualKeyW(vk, 0)
    user32.keybd_event(vk, scan, 0, 0)
    precise_sleep(press_sec)
    user32.keybd_event(vk, scan, KEYEVENTF_KEYUP, 0)


def click_at(x, y, press_sec):
    user32.SetCursorPos(int(x), int(y))
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    precise_sleep(press_sec)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def scroll_at(x, y, notches):
    user32.SetCursorPos(int(x), int(y))
    for _ in range(abs(notches)):
        delta = -WHEEL_DELTA if notches > 0 else WHEEL_DELTA
        user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, delta, 0)
        time.sleep(0.08)


def grab(x, y, w, h):
    if USE_MSS:
        with mss.mss() as sct:
            shot = sct.grab({'left': x, 'top': y, 'width': w, 'height': h})
        return Image.frombytes('RGB', shot.size, shot.bgra, 'raw', 'BGRX')
    return ImageGrab.grab(bbox=(x, y, x + w, y + h))


def block_mean(a, n):
    """n かける n の平均に潰す。間引きと違い、少しのずれでも形が残る。"""
    h = a.shape[0] // n * n
    w = a.shape[1] // n * n
    return a[:h, :w].reshape(h // n, n, w // n, n, -1).mean(axis=(1, 3))


def anchor_rect(pos, w=ANCHOR_W, h=ANCHOR_H):
    """見本として切り抜く四角の左上を返す。"""
    return int(pos[0]) - w // 2, int(pos[1]) - h // 2


def screen_size():
    if not IS_WIN:
        return 1920, 1080
    return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


def grab_anchor(pos, w=ANCHOR_W, h=ANCHOR_H):
    """指定座標を中心にした切り抜きを返す。大きさは見本に合わせられる。"""
    x, y = anchor_rect(pos, w, h)
    return grab(x, y, w, h)


class MedalClicker:
    def __init__(self):
        self.pos_menu = None    # 交換ダイアログの「100」プルダウン
        self.pos_3000 = None    # スクロール後の「3000」
        self.pos_play = None    # 「プレイ開始」
        self.pos_after  = None  # プレイ開始の後に一度押す場所
        self.pos_red    = None  # 盤面に出る赤いボタン
        self.pos_idle   = None  # 時々ひと押しする、押しても害のない場所
        self.pos_quit = None    # コンティニューチャンスの「やめる」
        self.pos_limit  = None  # プレイ上限到達の「プレイ上限数追加」
        self.pos_cancel = None  # その次の画面の「自動追加のキャンセル」
        self.pos_cash   = None  # 右上の「精算」
        self.pos_cash2  = None  # 精算確認ダイアログの「精算」
        self.pos_next   = None  # リザルトの「次へ」
        self.pos_next2  = None  # リザルトがもう一枚あるときの「次へ」
        self.pos_again  = None  # リザルトの「続けて遊ぶ」
        self.pos_game   = None  # ゲーム一覧の三番目
        self.pos_play2  = None  # ゲーム説明の「プレイ」
        self.pos_rate   = None  # レート選択の「レート決定」
        self.wait_min   = WAIT_MIN  # 上限をさばいてから精算するまでの待ち時間
        self.tol        = MATCH_THRESHOLD  # 画面の見分けのゆるさ
        self.anchor_size = ANCHOR_SIZE     # これから取る見本の一辺
        self.scrolls  = 2
        self.max_swap = 5
        self.cps      = 100.0
        self.keys     = 'AD'    # 'A' / 'AD'
        self.auto_swap = True
        self.auto_quit = True
        self.auto_limit = True
        self.auto_cash  = True
        self.auto_again = True
        self.auto_red   = True
        self.auto_poke  = True
        self.poke_min   = POKE_MIN

        self.running    = False   # ボット全体が動いているか
        self.tapping    = False   # いま A と D を叩いてよいか
        self.exchanging = False
        self.busy_text  = ''
        self.taps       = 0
        self.swaps      = 0
        self.quits      = 0
        self.limits     = 0
        self.cashes     = 0
        self.replays    = 0
        self.reds       = 0
        self.pokes      = 0
        self.poked_at   = 0     # 最後にひと押しした時刻
        self.offset     = (0, 0)  # ゲームの枠が登録時からどれだけ動いたか
        self.scan_i     = 0     # 順に探す見本の番号
        self.seen       = ''    # いま見えていると判断した画面
        self.limit_at   = 0     # プレイ上限をさばいた時刻
        self.cash_at    = 0     # この時刻になったら精算する。0 なら待っていない
        self.anchors    = {}
        self.note       = ''

        self.load_config()

        self.root = tk.Tk()
        self.root.title(f'メダル連打 {VERSION}')
        self.root.attributes('-topmost', True)
        self.build_ui()
        self.fit_window()

        threading.Thread(target=self.key_loop, daemon=True).start()
        threading.Thread(target=self.watch_loop, daemon=True).start()

        self.listener = pynput_keyboard.Listener(on_press=self.on_key)
        self.listener.start()

    # ---------- 設定 ----------
    def load_config(self):
        if CONFIG_PATH.exists():
            try:
                data = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                data = {}
            for key in POINTS.values():
                val = data.get(key)
                setattr(self, key, tuple(val) if val else None)
            self.cps       = float(data.get('cps', self.cps))
            self.keys      = data.get('keys', self.keys)
            self.scrolls   = int(data.get('scrolls', self.scrolls))
            self.max_swap  = int(data.get('max_swap', self.max_swap))
            self.auto_swap = bool(data.get('auto_swap', self.auto_swap))
            self.auto_quit = bool(data.get('auto_quit', self.auto_quit))
            self.auto_limit = bool(data.get('auto_limit', self.auto_limit))
            self.auto_cash  = bool(data.get('auto_cash', self.auto_cash))
            self.auto_again = bool(data.get('auto_again', self.auto_again))
            self.auto_red   = bool(data.get('auto_red', self.auto_red))
            self.auto_poke  = bool(data.get('auto_poke', self.auto_poke))
            self.poke_min   = int(data.get('poke_min', self.poke_min))
            self.wait_min   = int(data.get('wait_min', self.wait_min))
            self.tol        = int(data.get('tol', self.tol))
            self.anchor_size = int(data.get('anchor_size', self.anchor_size))
        if HAS_VISION:
            for key, path in ANCHOR_PATHS.items():
                if not path.exists():
                    continue
                try:
                    self.anchors[key] = np.asarray(Image.open(path).convert('RGB'), dtype=np.int16)
                except OSError:
                    pass

    def save_config(self):
        data = {
            'pos_menu':  list(self.pos_menu) if self.pos_menu else None,
            'pos_3000':  list(self.pos_3000) if self.pos_3000 else None,
            'pos_play':  list(self.pos_play) if self.pos_play else None,
            'pos_after': list(self.pos_after) if self.pos_after else None,
            'pos_red':   list(self.pos_red)   if self.pos_red   else None,
            'pos_idle':  list(self.pos_idle)  if self.pos_idle  else None,
            'pos_quit':   list(self.pos_quit)   if self.pos_quit   else None,
            'pos_limit':  list(self.pos_limit)  if self.pos_limit  else None,
            'pos_cancel': list(self.pos_cancel) if self.pos_cancel else None,
            'pos_cash':   list(self.pos_cash)   if self.pos_cash   else None,
            'pos_cash2':  list(self.pos_cash2)  if self.pos_cash2  else None,
            'pos_next':   list(self.pos_next)   if self.pos_next   else None,
            'pos_next2':  list(self.pos_next2)  if self.pos_next2  else None,
            'pos_again':  list(self.pos_again)  if self.pos_again  else None,
            'pos_game':   list(self.pos_game)   if self.pos_game   else None,
            'pos_play2':  list(self.pos_play2)  if self.pos_play2  else None,
            'pos_rate':   list(self.pos_rate)   if self.pos_rate   else None,
            'wait_min':   self.wait_min,
            'tol':        self.tol,
            'anchor_size': self.anchor_size,
            'cps':       self.cps,
            'keys':      self.keys,
            'scrolls':   self.scrolls,
            'max_swap':  self.max_swap,
            'auto_swap': self.auto_swap,
            'auto_quit': self.auto_quit,
            'auto_limit': self.auto_limit,
            'auto_cash': self.auto_cash,
            'auto_again': self.auto_again,
            'auto_red': self.auto_red,
            'auto_poke': self.auto_poke,
            'poke_min': self.poke_min,
        }
        try:
            CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        except (OSError, TypeError, ValueError):
            pass

    # ---------- UI ----------
    def section(self, text, value, cmd):
        """区切り線とチェックボックスを出して、その入れ物を返す。"""
        ttk.Separator(self.root, orient='horizontal').pack(fill='x', padx=10, pady=3)
        var = tk.BooleanVar(value=value)
        tk.Checkbutton(self.root, text=text, variable=var, command=cmd).pack()
        return var

    def point_row(self, items):
        """記録ボタンを一列に並べる。"""
        row = tk.Frame(self.root)
        row.pack(pady=1)
        for key, label, width in items:
            tk.Button(row, text=label, width=width,
                      command=lambda k=key: self.record(k)).pack(side='left', padx=2)

    def info_label(self):
        lbl = tk.Label(self.root, text='', font=('', 9))
        lbl.pack()
        return lbl

    def fit_window(self):
        """中身がちょうど入る大きさにする。窓が短いとボタンが隠れるため。"""
        self.root.update_idletasks()
        w = self.root.winfo_reqwidth()
        h = self.root.winfo_reqheight()
        h = min(h, self.root.winfo_screenheight() - 80)
        self.root.geometry(f'{w}x{h}+40+40')
        self.root.minsize(w, 400)

    def build_ui(self):
        self.lbl_state = tk.Label(self.root, text='停止中', font=('', 15, 'bold'), fg='gray')
        self.lbl_state.pack(pady=(8, 0))

        self.lbl_note = tk.Label(self.root, text='', font=('', 9), fg='blue')
        self.lbl_note.pack()

        self.lbl_seen = tk.Label(self.root, text='', font=('', 9), fg='#555')
        self.lbl_seen.pack()

        self.var_keys = tk.StringVar(value=self.keys)
        row = tk.Frame(self.root)
        row.pack(pady=2)
        tk.Radiobutton(row, text='A だけ', variable=self.var_keys, value='A',
                       command=self.on_keys).pack(side='left')
        tk.Radiobutton(row, text='A と D 交互', variable=self.var_keys, value='AD',
                       command=self.on_keys).pack(side='left')

        tk.Label(self.root, text='連打速度（回/秒）').pack()
        self.var_cps = tk.DoubleVar(value=self.cps)
        ttk.Scale(self.root, from_=3, to=100, variable=self.var_cps, orient='horizontal',
                  length=250, command=self.on_cps).pack()
        self.lbl_cps = tk.Label(self.root, text='')
        self.lbl_cps.pack()

        # メダル交換
        self.var_swap = self.section('メダル交換を自動でやる', self.auto_swap, self.on_swap)
        self.point_row([('menu', '1. 100', 7), ('3000', '2. 3000', 7),
                        ('play', '3. プレイ開始', 11)])
        self.point_row([('after', '15. 開始後の一押し', 16)])
        row = tk.Frame(self.root)
        row.pack(pady=1)
        tk.Label(row, text='スクロール').pack(side='left')
        self.var_scrolls = tk.IntVar(value=self.scrolls)
        tk.Spinbox(row, from_=0, to=10, width=3, textvariable=self.var_scrolls,
                   command=self.on_nums).pack(side='left', padx=(2, 10))
        tk.Label(row, text='交換上限').pack(side='left')
        self.var_max = tk.IntVar(value=self.max_swap)
        tk.Spinbox(row, from_=0, to=99, width=3, textvariable=self.var_max,
                   command=self.on_nums).pack(side='left', padx=2)
        self.lbl_swap = self.info_label()

        # 時々のひと押し
        self.var_poke = self.section('時々どこかを押しておく', self.auto_poke, self.on_poke)
        row = tk.Frame(self.root)
        row.pack(pady=1)
        self.var_pmin = tk.IntVar(value=self.poke_min)
        tk.Spinbox(row, from_=1, to=60, width=3, textvariable=self.var_pmin,
                   command=self.on_poke_min).pack(side='left', padx=2)
        tk.Label(row, text='分ごとに').pack(side='left')
        tk.Button(row, text='17. 空押しの場所', width=15,
                  command=lambda: self.record('idle')).pack(side='left', padx=3)
        self.lbl_poke = self.info_label()

        # 盤面の赤いボタン
        self.var_red = self.section('赤ボタンが出ている間は叩く', self.auto_red, self.on_red)
        self.point_row([('red', '16. 赤ボタン', 13)])
        self.lbl_red = self.info_label()

        # コンティニューチャンス
        self.var_quit = self.section('コンティニューは やめる を押す', self.auto_quit, self.on_quit)
        self.point_row([('quit', '4. やめる', 10)])
        self.lbl_quit = self.info_label()

        # プレイ上限
        self.var_limit = self.section('プレイ上限は追加してキャンセル', self.auto_limit, self.on_limit)
        self.point_row([('limit', '5. 上限数追加', 12), ('cancel', '6. 自動追加のキャンセル', 18)])
        self.lbl_limit = self.info_label()

        # 精算
        self.var_cash = self.section('上限のあと待ってから精算する', self.auto_cash, self.on_cash)
        row = tk.Frame(self.root)
        row.pack(pady=1)
        tk.Label(row, text='待ち時間').pack(side='left')
        self.var_wait = tk.IntVar(value=self.wait_min)
        tk.Spinbox(row, from_=0, to=600, width=4, textvariable=self.var_wait,
                   command=self.on_wait).pack(side='left', padx=2)
        tk.Label(row, text='分').pack(side='left')
        tk.Button(row, text='いま精算', width=8, command=self.cash_now).pack(side='left', padx=8)
        self.point_row([('cash', '7. 精算（右上）', 13), ('cash2', '8. 精算（確認）', 13)])
        self.lbl_cash = self.info_label()

        # 精算のあと、もう一度同じ台に入り直す
        self.var_again = self.section('精算したら同じ台で遊び直す', self.auto_again, self.on_again)
        self.point_row([('next', '9. 次へ', 9), ('next2', '10. 次へ 2', 10)])
        self.point_row([('again', '11. 続けて遊ぶ', 12), ('game', '12. 一覧の三番目', 14)])
        self.point_row([('play2', '13. プレイ', 9), ('rate', '14. レート決定', 12)])
        self.lbl_again = self.info_label()

        ttk.Separator(self.root, orient='horizontal').pack(fill='x', padx=10, pady=3)
        row = tk.Frame(self.root)
        row.pack(pady=(4, 2))
        tk.Button(row, text='判定を見る', width=10,
                  command=self.check_screens).pack(side='left', padx=3)
        tk.Label(row, text='ゆるさ').pack(side='left')
        self.var_tol = tk.IntVar(value=self.tol)
        tk.Spinbox(row, from_=2, to=80, width=3, textvariable=self.var_tol,
                   command=self.on_tol).pack(side='left', padx=2)
        tk.Label(row, text='見本').pack(side='left')
        self.var_size = tk.IntVar(value=self.anchor_size)
        tk.Spinbox(row, from_=80, to=400, increment=40, width=4,
                   textvariable=self.var_size, command=self.on_size).pack(side='left', padx=2)

        row = tk.Frame(self.root)
        row.pack(pady=(2, 4))
        tk.Button(row, text='登録を全部消す', width=13,
                  command=self.reset_points).pack(side='left', padx=3)
        tk.Button(row, text='控えに戻す', width=10,
                  command=self.restore_points).pack(side='left', padx=3)
        tk.Label(row, text=f'{VERSION}\nF8 開始/停止   F10 終了', font=('', 8), fg='gray',
                 justify='left').pack(side='left')

        self.refresh()

    def on_cps(self, _=None):
        self.cps = round(self.var_cps.get())
        self.save_config()

    def on_keys(self):
        self.keys = self.var_keys.get()
        self.save_config()

    def on_poke(self):
        self.auto_poke = self.var_poke.get()
        self.save_config()

    def on_poke_min(self):
        try:
            self.poke_min = int(self.var_pmin.get())
        except (tk.TclError, ValueError):
            return
        self.save_config()

    def on_red(self):
        self.auto_red = self.var_red.get()
        self.save_config()

    def on_swap(self):
        self.auto_swap = self.var_swap.get()
        self.save_config()

    def on_quit(self):
        self.auto_quit = self.var_quit.get()
        self.save_config()

    def on_limit(self):
        self.auto_limit = self.var_limit.get()
        self.save_config()

    def on_cash(self):
        self.auto_cash = self.var_cash.get()
        self.save_config()

    def on_tol(self):
        try:
            self.tol = int(self.var_tol.get())
        except (tk.TclError, ValueError):
            return
        self.save_config()

    def on_size(self):
        try:
            self.anchor_size = int(self.var_size.get())
        except (tk.TclError, ValueError):
            return
        self.save_config()

    def on_wait(self):
        try:
            self.wait_min = int(self.var_wait.get())
        except (tk.TclError, ValueError):
            return
        # 待っている最中に変えたら、その場で残り時間を引き直す
        if self.cash_at:
            self.cash_at = self.limit_at + self.wait_min * 60
        self.save_config()

    def cash_now(self):
        """待ち時間を飛ばして、すぐ精算に入る。"""
        if not self.pos_cash:
            self.note = '先に 7 の精算を登録して'
            self.root.after(2500, lambda: setattr(self, 'note', ''))
            return
        self.limit_at = time.monotonic()
        self.cash_at  = time.monotonic()

    def on_again(self):
        self.auto_again = self.var_again.get()
        self.save_config()

    def on_nums(self):
        try:
            self.scrolls  = int(self.var_scrolls.get())
            self.max_swap = int(self.var_max.get())
        except (tk.TclError, ValueError):
            return
        self.save_config()

    def marks(self, *keys):
        """× 未登録、▲ 場所はあるが見本がない、✓ そろっている。"""
        out = ''
        for key in keys:
            if not getattr(self, POINTS[key]):
                out += '×'
            elif key in ANCHOR_PATHS and self.anchors.get(key) is None:
                out += '▲'
            else:
                out += '✓'
        return out

    def refresh(self):
        if self.exchanging:
            self.lbl_state.config(text=self.busy_text, fg='darkorange')
        elif self.running:
            self.lbl_state.config(text=f'連打中  {self.taps}', fg='red')
        else:
            self.lbl_state.config(text='停止中', fg='gray')

        self.lbl_cps.config(text=f'{self.cps:.0f} 回/秒')
        if self.offset != (0, 0):
            self.lbl_state.config(
                text=self.lbl_state.cget('text') + f'   枠 {self.offset[0]:+d},{self.offset[1]:+d}')
        self.lbl_note.config(text=self.note)
        self.lbl_seen.config(text=f'見えている: {self.seen}' if self.seen else '')

        marks = self.marks('menu', '3000', 'play', 'after')
        limit = '無制限' if self.max_swap == 0 else f'{self.max_swap} 回まで'
        self.lbl_swap.config(text=f'登録 {marks}   交換 {self.swaps} 回 / {limit}')

        self.lbl_red.config(text=f'登録 {self.marks("red")}   赤 {self.reds} 回')
        self.lbl_poke.config(text=f'登録 {self.marks("idle")}   空押し {self.pokes} 回')

        mark_q = self.marks('quit')
        self.lbl_quit.config(text=f'登録 {mark_q}   やめる {self.quits} 回')

        mark_l = self.marks('limit', 'cancel')
        self.lbl_limit.config(text=f'登録 {mark_l}   上限追加 {self.limits} 回')

        mark_c = self.marks('cash', 'cash2')
        if self.cash_at:
            left = max(0, int(self.cash_at - time.monotonic()))
            waiting = f'精算まで あと {left // 60} 分 {left % 60:02d} 秒'
        else:
            waiting = '待機なし'
        self.lbl_cash.config(text=f'登録 {mark_c}   {waiting}   精算 {self.cashes} 回')

        mark_a = self.marks('next', 'next2', 'again', 'game', 'play2', 'rate')
        self.lbl_again.config(text=f'登録 {mark_a}   遊び直し {self.replays} 回')

        self.root.after(200, self.refresh)

    # ---------- 記録 ----------
    def record(self, which):
        """3 秒数えてからカーソル位置を覚える。押したあと目的の場所へ移す。"""
        def grab_point():
            pos = cursor_pos()
            # 手で登録した状態を控えておく。あとで戻せるようにするため
            try:
                if CONFIG_PATH.exists():
                    BACKUP_PATH.write_text(CONFIG_PATH.read_text(encoding='utf-8'),
                                           encoding='utf-8')
            except OSError:
                pass
            setattr(self, POINTS[which], pos)
            if which in ANCHOR_PATHS:
                self.save_anchor(which, pos)
            self.save_config()
            self.note = f'{LABELS[which]} {pos} を記録'
            self.root.after(2500, lambda: setattr(self, 'note', ''))

        def tick(left):
            if left:
                self.note = f'{LABELS[which]} の上へ   あと {left}'
                self.root.after(1000, tick, left - 1)
            else:
                grab_point()

        tick(3)

    def restore_points(self):
        """手で登録した最後の状態に戻す。"""
        if not BACKUP_PATH.exists():
            self.note = '控えがない'
            self.root.after(2500, lambda: setattr(self, 'note', ''))
            return
        if not messagebox.askyesno('確認', 'いまの座標を捨てて、手で登録した最後の状態に戻します。'):
            return
        try:
            CONFIG_PATH.write_text(BACKUP_PATH.read_text(encoding='utf-8'), encoding='utf-8')
        except OSError:
            return
        self.running = False
        self.tapping = False
        self.load_config()
        self.note = '手で登録した状態に戻した'
        self.root.after(3000, lambda: setattr(self, 'note', ''))

    def check_screens(self):
        """いま見えている画面と、覚えた見本の違いを並べて出す。"""
        lines = []
        for key in ANCHOR_PATHS:
            pos = self.at(key)
            if not pos:
                lines.append(f'{LABELS[key]}: 未登録')
                continue
            if self.anchors.get(key) is None:
                lines.append(f'{LABELS[key]}: 見本がない。登録し直して')
                continue
            d = self.diff(key, pos)
            if d is None:
                lines.append(f'{LABELS[key]}: 画面を読めない')
                continue

            side = self.anchors[key].shape[0]
            worst = self.compare(key, pos)
            worst = worst[1] if worst else 0.0
            line = f'{LABELS[key]} {pos[0]},{pos[1]} 見本{side}: 差 {d:.1f} 一角 {worst:.1f}'
            if d < self.tol:
                line += ' 一致'
            else:
                # その場では合わなくても、近くにあるかもしれない
                found = self.search(key, pos)
                if found:
                    moved = self.compare(key, (pos[0] + found[0], pos[1] + found[1]))
                    if moved:
                        line += f' / 探すと {found[0]:+d},{found[1]:+d} で {moved[0]:.1f}'
            if float(np.std(self.anchors[key])) < ALIGN_FLAT:
                line += ' のっぺり'
            if key in CONFIRM:
                line += '  裏取り' + ('○' if self.confirmed(key) else '×')
            lines.append(line)
        lines.append('')
        lines.append(f'ゆるさ {self.tol} より小さい差が一致になる')
        lines.append('差は区画ごとの真ん中、一角は食い違いの大きい区画')
        lines.append(f'一角が {self.tol * WORST_RATIO} 以上なら別の画面として弾く')
        lines.append(f'枠のずれ {self.offset[0]:+d},{self.offset[1]:+d} を足した場所で見ている')
        messagebox.showinfo('判定', '\n'.join(lines))

    def reset_points(self):
        """覚えた場所と見本を捨てて、登録前の状態に戻す。"""
        if not messagebox.askyesno('確認', '登録した場所を全部消します。よろしいですか。'):
            return
        self.running = False
        self.tapping = False
        for attr in POINTS.values():
            setattr(self, attr, None)
        self.cash_at   = 0
        self.anchors   = {}
        for path in ANCHOR_PATHS.values():
            try:
                path.unlink()
            except OSError:
                pass
        self.save_config()
        self.note = '登録を全部消した'
        self.root.after(3000, lambda: setattr(self, 'note', ''))

    def save_anchor(self, key, pos):
        """その画面が出ているかの判定用に、ボタン周りの見た目を保存する。"""
        if not (HAS_VISION and IS_WIN):
            return
        try:
            img = grab_anchor(pos, self.anchor_size, self.anchor_size)
            img.save(ANCHOR_PATHS[key])
            self.anchors[key] = np.asarray(img.convert('RGB'), dtype=np.int16)
        except (OSError, ValueError):
            self.anchors.pop(key, None)

    # ---------- 操作 ----------
    def toggle(self):
        self.running = not self.running
        self.tapping = self.running
        if self.running:
            self.note = ''
            self.taps   = 0
            self.swaps  = 0
            self.quits  = 0
            self.limits = 0
            self.cashes = 0
            self.reds   = 0

    def on_key(self, key):
        if key == pynput_keyboard.Key.f8:
            self.root.after(0, self.toggle)
        elif key == pynput_keyboard.Key.f10:
            self.running = False
            self.root.after(0, self.root.destroy)

    # ---------- 連打 ----------
    def key_loop(self):
        turn = 0
        while True:
            if not (self.running and self.tapping) or self.exchanging or not IS_WIN:
                time.sleep(0.05)
                continue

            interval = 1.0 / max(self.cps, 0.1)
            press    = min(MAX_PRESS, interval * 0.5)

            vk = VK['D'] if (self.keys == 'AD' and turn % 2) else VK['A']
            turn += 1

            tap_key(vk, press)
            self.taps += 1

            gap = (interval - press) * (1 + random.uniform(-JITTER, JITTER))
            precise_sleep(gap)

    # ---------- 画面の見張り ----------
    def screen_table(self):
        """見張る画面の一覧。順番は同じくらい似ていたときの優先順位。"""
        return (
            ('cash2', self.auto_cash and self.pos_cash2,
             lambda: self.do_tap('cash2', '精算した', 2.0, stop_keys=True, count='cashes'), 2),
            ('next',  self.auto_again and self.pos_next,
             lambda: self.do_tap('next', 'リザルトを送った', 1.5), 2),
            ('next2', self.auto_again and self.pos_next2,
             lambda: self.do_tap('next2', 'リザルトを送った', 1.5), 2),
            ('again', self.auto_again and self.pos_again,
             lambda: self.do_tap('again', '続けて遊ぶを押した', 2.0), 2),
            ('game',  self.auto_again and self.pos_game,
             lambda: self.do_tap('game', '台を選んだ', 2.0, count='replays'), 2),
            ('play2', self.auto_again and self.pos_play2,
             lambda: self.do_tap('play2', 'プレイを押した', 1.5), 2),
            ('rate',  self.auto_again and self.pos_rate,
             lambda: self.do_tap('rate', 'レートを決めた', 3.0), 2),
            ('quit',  self.auto_quit and self.pos_quit,
             lambda: self.do_tap('quit', 'やめるを押した', 1.5, count='quits'), 2),
            ('limit', self.auto_limit and self.pos_limit and self.pos_cancel,
             self.do_limit, 2),
            ('menu',  self.auto_swap and self.pos_menu and self.pos_3000 and self.pos_play
             and not (self.max_swap and self.swaps >= self.max_swap),
             self.do_exchange, NEED.get('menu', 2)),
        )

    def watch_loop(self):
        """見張りの本体。一巡ごとに包んで、何かあっても糸ごと死なせない。"""
        hits = {e[0]: 0 for e in self.screen_table()}
        idle = 0
        while True:
            time.sleep(WATCH_INTERVAL)
            try:
                idle = self.watch_once(hits, idle)
            except Exception as err:
                self.note = f'見張りでエラー {type(err).__name__}'
                time.sleep(2)

    def watch_once(self, hits, idle):
        """一巡ぶんの見張り。いま出ている画面に合った手を打つ。

        当てはまるものが複数あったら、一番よく似ている画面を選ぶ。白い
        ダイアログ同士は似がちで、順番だけで決めると取り違えるため。
        どれにも当てはまらない状態が続いたらゲーム中とみなして連打に戻る。
        """
        if not (self.running and IS_WIN and HAS_VISION) or self.exchanging:
            hits.update(dict.fromkeys(hits, 0))
            return 0

        # 決めた間隔でひと押し。画面が何であっても止めない
        if self.auto_poke and self.pos_idle:
            if not self.poked_at:
                self.poked_at = time.monotonic()
            elif time.monotonic() - self.poked_at >= self.poke_min * 60:
                self.poke()

        # 精算待ちの間は投入できないので、連打には戻さない
        if self.cash_at:
            self.tapping = False

        # 待ち時間が過ぎていたら、画面を見るより先に精算へ入る
        if self.cash_at and time.monotonic() >= self.cash_at and self.pos_cash:
            self.cash_at = 0
            hits.update(dict.fromkeys(hits, 0))
            self.do_tap('cash', '精算を押した', 1.5)
            return idle

        # 赤いボタンは盤面に重なって出る。見えている間は叩き続ける
        if self.auto_red and self.pos_red:
            both = self.look('red')
            if both and both[0] < self.tol:
                self.hit_red()
                return 0

        table  = self.screen_table()
        scores = {}
        seen   = {}
        for order, (key, ready, act, need) in enumerate(table):
            if not ready:
                continue
            both = self.look(key)
            if not both:
                continue
            # 真ん中の差だけだと、半分そろっていれば通ってしまう。どこか
            # 一角が大きく食い違うものは別の画面として弾く
            if both[0] < self.tol and both[1] < self.tol * WORST_RATIO:
                if self.confirmed(key):
                    scores[key] = (both[1], both[0], order)
            seen[key] = both

        if scores:
            found = min(scores, key=scores.get)
            self.seen = f'{LABELS[found]}  差 {seen[found][0]:.0f} 一角 {seen[found][1]:.0f}'
            for key in hits:
                if key != found:
                    hits[key] = 0
            hits[found] += 1
            # 何かの画面が見えている。盤面ではないので連打は止める
            self.tapping = False
            # 一瞬の一致では動かさない。続けて出たら本物とみなす
            act, need = next((e[2], e[3]) for e in table if e[0] == found)
            if hits[found] >= need:
                hits.update(dict.fromkeys(hits, 0))
                act()
            return 0

        hits.update(dict.fromkeys(hits, 0))

        # 当てはまらなかったときも、一番近かったものを出しておく。誤検知や
        # 取りこぼしを、判定を開かずに見比べられるようにするため
        if seen:
            near = min(seen, key=lambda k: seen[k][0])
            self.seen = f'なし（近い: {LABELS[near]} 差 {seen[near][0]:.0f} 一角 {seen[near][1]:.0f}）'
        else:
            self.seen = 'なし'

        # どの画面でもない。しばらく続いたら盤面とみなして連打に戻る
        idle += 1
        if idle >= IDLE_HITS and not self.cash_at and not self.tapping:
            self.tapping = True
            self.busy_text = ''

        # 枠が動いた疑いがあるので、見本を一枚だけ順に探す。見つかっても
        # 覚えた座標は触らず、動かしている間のずれとして持つだけにする
        if self.scan():
            return 0
        return idle

    def compare(self, key, pos):
        """覚えた見本といまの画面を比べ、(全体の差, 一番違う一角の差) を返す。

        全体の差は、見本を広く取るほど小さな違いが薄まる。似たダイアログ
        同士を分けるために、八つに区切った中で食い違いの大きい区画だけを
        平均した値も一緒に出す。

        切り抜く大きさは見本に合わせる。前の版で取った小さい見本もその
        まま使えるようにするため。
        """
        anchor = self.anchors.get(key)
        if anchor is None or not pos:
            return None
        h, w = anchor.shape[0], anchor.shape[1]
        try:
            cur = np.asarray(grab_anchor(pos, w, h).convert('RGB'), dtype=np.int16)
        except (OSError, ValueError):
            return None
        if cur.shape != anchor.shape:
            return None

        gap = np.abs(cur - anchor).mean(axis=2)
        gh = gap.shape[0] // GRID * GRID
        gw = gap.shape[1] // GRID * GRID
        if gh < GRID or gw < GRID:
            overall = float(gap.mean())
            return overall, overall

        blocks = gap[:gh, :gw].reshape(GRID, gh // GRID, GRID, gw // GRID).mean(axis=(1, 3))
        order = np.sort(blocks, axis=None)
        # 真ん中の区画の差で見る。平均だと絵の動く一角に引きずられ、同じ
        # 画面でも外れてしまう。半分以上の区画が合っていれば同じ画面とみなす
        middle = float(np.median(order))
        worst  = float(order[-GRID:].mean())
        return middle, worst

    def diff(self, key, pos):
        """区画の真ん中の差だけを返す。"""
        both = self.compare(key, pos)
        return None if both is None else both[0]

    def search(self, key, center):
        """見本を周りから探し、中心からのずれを返す。見つからなければ None。

        粗く当たりを付けてから細かく詰める。全画素をずらしながら比べると
        重いので、どちらの段も平均に潰した絵で見る。
        """
        anchor = self.anchors.get(key)
        if anchor is None or not center:
            return None

        ah, aw = anchor.shape[0], anchor.shape[1]
        ax, ay = anchor_rect(center, aw, ah)
        sw, sh = screen_size()
        x0 = max(0, ax - ALIGN_PAD)
        y0 = max(0, ay - ALIGN_PAD)
        x1 = min(sw, ax + aw + ALIGN_PAD)
        y1 = min(sh, ay + ah + ALIGN_PAD)
        if x1 - x0 < aw or y1 - y0 < ah:
            return None
        try:
            big = np.asarray(grab(x0, y0, x1 - x0, y1 - y0).convert('RGB'), dtype=np.int16)
        except (OSError, ValueError):
            return None

        rough = self.best_offset(anchor, big, ALIGN_STEP, None)
        if rough is None:
            return None
        fine = self.best_offset(anchor, big, 2, rough)
        bx, by = fine if fine else rough
        return int(x0 + bx - ax), int(y0 + by - ay)

    @staticmethod
    def best_offset(anchor, big, step, around):
        """潰した絵どうしをずらして比べ、一番合う左上の位置を返す。

        around を渡すと、その周り ALIGN_STEP ぶんだけを見る。粗い当たりを
        細かく詰め直すときに使う。
        """
        a = block_mean(anchor, step)
        b = block_mean(big, step)
        th, tw = a.shape[0], a.shape[1]
        if b.shape[0] < th or b.shape[1] < tw:
            return None

        if around is None:
            lo_y = lo_x = 0
            hi_y, hi_x = b.shape[0] - th, b.shape[1] - tw
        else:
            lo_x = max(0, (around[0] - ALIGN_STEP) // step)
            lo_y = max(0, (around[1] - ALIGN_STEP) // step)
            hi_x = min(b.shape[1] - tw, (around[0] + ALIGN_STEP) // step)
            hi_y = min(b.shape[0] - th, (around[1] + ALIGN_STEP) // step)
            if hi_y < lo_y or hi_x < lo_x:
                return None

        view = b[lo_y:hi_y + th, lo_x:hi_x + tw]
        if view.shape[0] < th or view.shape[1] < tw:
            return None
        win = np.lib.stride_tricks.sliding_window_view(view, (th, tw, 3))
        gap = np.abs(win - a).mean(axis=(3, 4, 5))[:, :, 0]
        iy, ix = np.unravel_index(int(np.argmin(gap)), gap.shape)
        return (lo_x + ix) * step, (lo_y + iy) * step

    def at(self, key):
        """いま押すべき場所。覚えた座標に、枠のずれを足したもの。

        覚えた座標そのものは触らない。触ると、外した探索が積み重なって
        登録が壊れる。ずれは動かしているあいだだけ持つ。
        """
        pos = getattr(self, POINTS[key])
        if not pos:
            return None
        return pos[0] + self.offset[0], pos[1] + self.offset[1]

    def confirmed(self, key):
        """裏取りが要る画面かどうかを見て、要るなら相方もそろっているか返す。"""
        mate = CONFIRM.get(key)
        if not mate or self.anchors.get(mate) is None or not getattr(self, POINTS[mate]):
            return True
        both = self.look(mate)
        return bool(both and both[0] < self.tol and both[1] < self.tol * WORST_RATIO)

    def look(self, key):
        """いまの画面がその画面か見る。(真ん中の差, 一角の差) か None。"""
        return self.compare(key, self.at(key))

    def refine(self, key):
        """押す直前に見本を探し直して、枠のずれを詰める。

        真ん中の差は少しの位置違いでは動かない。白い面の多い画面だと、
        ずれたままでも同じ画面に見えてしまう。押す前にここで詰めておく。
        """
        if key not in ANCHOR_PATHS:
            return
        center = self.at(key)
        found  = self.search(key, center)
        if not found or found == (0, 0):
            return
        dx, dy = found
        now   = self.compare(key, center)
        moved = self.compare(key, (center[0] + dx, center[1] + dy))
        # 食い違う一角の差で見比べる。こちらは位置がずれるとすぐ大きくなる
        if not moved or (now and moved[1] >= now[1]):
            return
        self.offset = (self.offset[0] + dx, self.offset[1] + dy)
        self.note = f'枠が {self.offset[0]:+d},{self.offset[1]:+d} 動いている'

    def scan(self):
        """見本を一枚ずつ順に探し、見つかったら枠のずれを覚え直す。

        どれも当てはまらなかった巡回で一枚だけ探す。全部を毎回探すと重く、
        連打の足を引っぱるため。
        """
        keys = [k for k in ANCHOR_PATHS
                if getattr(self, POINTS[k]) and self.anchors.get(k) is not None]
        if not keys:
            return False
        key = keys[self.scan_i % len(keys)]
        self.scan_i += 1

        center = self.at(key)
        found  = self.search(key, center)
        if not found:
            return False
        dx, dy = found
        if dx == 0 and dy == 0:
            return False

        # 探した先が本当にその画面か、細かいところまで見て確かめる
        both = self.compare(key, (center[0] + dx, center[1] + dy))
        if not both or both[0] >= self.tol:
            return False
        self.offset = (self.offset[0] + dx, self.offset[1] + dy)
        self.note = f'枠が {self.offset[0]:+d},{self.offset[1]:+d} 動いている'
        return True

    def poke(self):
        """どの画面でも、決めた間隔で害のない場所をひと押しする。"""
        pos = self.at('idle')
        if not pos:
            return
        keep = cursor_pos()
        click_at(pos[0], pos[1], 0.03)
        user32.SetCursorPos(int(keep[0]), int(keep[1]))
        self.pokes += 1
        self.poked_at = time.monotonic()

    def hit_red(self):
        """赤いボタンが見えている間、そこを叩き続ける。

        一巡ぶんだけ叩いて戻る。消えていれば次の巡回で止まる。A と D の
        連打は止めない。投入しながら押す場面なので、どちらも要る。
        """
        self.refine('red')
        pos = self.at('red')
        if not pos:
            return
        self.busy_text = '赤ボタンを叩いている'
        end = time.monotonic() + RED_MAX
        gap = 1.0 / RED_CPS
        n   = 0
        while self.running and time.monotonic() < end:
            click_at(pos[0], pos[1], 0.02)
            self.reds += 1
            precise_sleep(gap)
            # 消えていないか折々に見て、無くなったらすぐ止める
            n += 1
            if n % 5 == 0:
                both = self.compare('red', pos)
                if not both or both[0] >= self.tol:
                    break

    def do_tap(self, key, label, wait, stop_keys=False, count=None):
        """記録した場所を一回押して、画面が変わるまで待つ。"""
        self.refine(key)
        pos = self.at(key)
        if not pos:
            return
        self.exchanging = True
        self.busy_text  = label
        keep = cursor_pos()
        try:
            time.sleep(0.2)
            click_at(pos[0], pos[1], 0.03)
            if count:
                setattr(self, count, getattr(self, count) + 1)
            time.sleep(wait)
        finally:
            user32.SetCursorPos(int(keep[0]), int(keep[1]))
            if stop_keys:
                self.tapping = False
                self.note    = '精算したので連打を止めた'
            self.exchanging = False

    def do_limit(self):
        """プレイ上限の知らせを、上限数追加 → 自動追加のキャンセル でさばいて止まる。

        上限に達した後は投入できないので、A と D の連打はここで止める。
        そのあと決めた時間だけ待ってから精算し、遊び直しの流れに乗る。
        """
        self.exchanging = True
        self.busy_text  = 'プレイ上限を処理中'
        keep = cursor_pos()
        try:
            time.sleep(0.2)
            self.refine('limit')
            limit, cancel = self.at('limit'), self.at('cancel')
            click_at(limit[0], limit[1], 0.03)
            time.sleep(1.2)   # 次のダイアログが開くまで待つ
            click_at(cancel[0], cancel[1], 0.03)
            self.limits += 1
            time.sleep(1.0)
        finally:
            user32.SetCursorPos(int(keep[0]), int(keep[1]))
            self.tapping    = False
            self.exchanging = False
            self.limit_at   = time.monotonic()
            self.cash_at    = self.limit_at + self.wait_min * 60
            self.note       = f'{self.wait_min} 分待ってから精算する'

    def do_exchange(self):
        """100 のプルダウンを開き、3000 まで送って選び、プレイ開始を押す。"""
        self.exchanging = True
        self.busy_text  = 'メダル交換中'
        keep = cursor_pos()
        try:
            time.sleep(0.2)
            self.refine('menu')
            menu, three = self.at('menu'), self.at('3000')
            click_at(menu[0], menu[1], 0.03)
            time.sleep(0.5)

            # 3000 は畳んだ状態では見えないので、その位置でホイールを回して送る
            if self.scrolls:
                scroll_at(three[0], three[1], self.scrolls)
                time.sleep(0.4)

            click_at(three[0], three[1], 0.03)
            time.sleep(0.6)
            play = self.at('play')
            click_at(play[0], play[1], 0.03)
            self.swaps += 1
            time.sleep(2.5)   # ゲーム画面が戻るまで待つ

            # 台に入った直後は説明の画面が被る。どこか一度押して閉じる
            after = self.at('after')
            if after:
                click_at(after[0], after[1], 0.03)
                time.sleep(1.5)
        finally:
            user32.SetCursorPos(int(keep[0]), int(keep[1]))
            # プレイ開始まで押せたので、ここから連打に戻る
            self.tapping    = True
            self.note       = ''
            self.exchanging = False

    def run(self):
        self.root.mainloop()


if __name__ == '__main__':
    MedalClicker().run()
