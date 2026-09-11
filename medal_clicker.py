"""
メダルゲーム連打ボット（GAPOLI バベルのメダルタワーW 想定）
A（左）と D（右）のキーを連打し、画面を見て次の二つを自動でさばく。
・メダル交換ダイアログ → 100 のプルダウン → 3000 を選ぶ → プレイ開始
　→ 説明の画面を閉じる一押し → ここから連打を再開
・コンティニューチャンス → やめる
・プレイ上限に到達 → プレイ上限数追加 → 自動追加のキャンセル → 連打を停止
・自動追加のキャンセルの後は、決めた時間だけ待ってから右上の精算
・精算確認 → 精算（ここで A と D は止める）
・リザルト → 次へ → 次へ2 → 続けて遊ぶ → 一覧の三番目 → プレイ → レート決定
そのあと説明の画面を黙って待ち、メダル交換をさばくと連打に戻る。
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

CONFIG_PATH = Path(__file__).with_name('medal_clicker.json')
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
}

MAX_PRESS   = 0.025   # キーを押している時間の上限。速度を上げると自動で短くなる
JITTER      = 0.15    # 間隔を ±15% 揺らす
ANCHOR_W    = 140     # 交換ダイアログ判定に使う切り抜きの大きさ
ANCHOR_H    = 44
MATCH_THRESHOLD = 14  # 画素差の平均がこれ未満なら「同じ画面」とみなす
WATCH_INTERVAL  = 0.7
WAIT_MIN        = 30  # プレイ上限をさばいてから精算するまでの待ち時間（分）


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


def grab_anchor(pos):
    """指定座標を中心にした切り抜きを返す。"""
    x = int(pos[0]) - ANCHOR_W // 2
    y = int(pos[1]) - ANCHOR_H // 2
    return grab(x, y, ANCHOR_W, ANCHOR_H)


class MedalClicker:
    def __init__(self):
        self.pos_menu = None    # 交換ダイアログの「100」プルダウン
        self.pos_3000 = None    # スクロール後の「3000」
        self.pos_play = None    # 「プレイ開始」
        self.pos_after  = None  # プレイ開始の後に一度押す場所
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
        self.scrolls  = 2
        self.max_swap = 5
        self.cps      = 100.0
        self.keys     = 'AD'    # 'A' / 'AD'
        self.auto_swap = True
        self.auto_quit = True
        self.auto_limit = True
        self.auto_cash  = True
        self.auto_again = True

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
        self.limit_at   = 0     # プレイ上限をさばいた時刻
        self.cash_at    = 0     # この時刻になったら精算する。0 なら待っていない
        self.anchors    = {}
        self.note       = ''

        self.load_config()

        self.root = tk.Tk()
        self.root.title('メダル連打')
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
            self.wait_min   = int(data.get('wait_min', self.wait_min))
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
            'cps':       self.cps,
            'keys':      self.keys,
            'scrolls':   self.scrolls,
            'max_swap':  self.max_swap,
            'auto_swap': self.auto_swap,
            'auto_quit': self.auto_quit,
            'auto_limit': self.auto_limit,
            'auto_cash': self.auto_cash,
            'auto_again': self.auto_again,
        }
        try:
            CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        except OSError:
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

        row = tk.Frame(self.root)
        row.pack(pady=(6, 4))
        tk.Button(row, text='登録を全部消す', width=13,
                  command=self.reset_points).pack(side='left', padx=6)
        tk.Label(row, text='F8 開始/停止\nF10 終了', font=('', 8), fg='gray',
                 justify='left').pack(side='left')

        self.refresh()

    def on_cps(self, _=None):
        self.cps = round(self.var_cps.get())
        self.save_config()

    def on_keys(self):
        self.keys = self.var_keys.get()
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

    def refresh(self):
        if self.exchanging:
            self.lbl_state.config(text=self.busy_text, fg='darkorange')
        elif self.running:
            self.lbl_state.config(text=f'連打中  {self.taps}', fg='red')
        else:
            self.lbl_state.config(text='停止中', fg='gray')

        self.lbl_cps.config(text=f'{self.cps:.0f} 回/秒')
        self.lbl_note.config(text=self.note)

        marks = ''.join('✓' if p else '×' for p in
                        (self.pos_menu, self.pos_3000, self.pos_play, self.pos_after))
        limit = '無制限' if self.max_swap == 0 else f'{self.max_swap} 回まで'
        self.lbl_swap.config(text=f'登録 {marks}   交換 {self.swaps} 回 / {limit}')

        mark_q = '✓' if self.pos_quit else '×'
        self.lbl_quit.config(text=f'登録 {mark_q}   やめる {self.quits} 回')

        mark_l = ''.join('✓' if p else '×' for p in (self.pos_limit, self.pos_cancel))
        self.lbl_limit.config(text=f'登録 {mark_l}   上限追加 {self.limits} 回')

        mark_c = ''.join('✓' if p else '×' for p in (self.pos_cash, self.pos_cash2))
        if self.cash_at:
            left = max(0, int(self.cash_at - time.monotonic()))
            waiting = f'精算まで あと {left // 60} 分 {left % 60:02d} 秒'
        else:
            waiting = '待機なし'
        self.lbl_cash.config(text=f'登録 {mark_c}   {waiting}   精算 {self.cashes} 回')

        mark_a = ''.join('✓' if p else '×' for p in
                         (self.pos_next, self.pos_next2, self.pos_again,
                          self.pos_game, self.pos_play2, self.pos_rate))
        self.lbl_again.config(text=f'登録 {mark_a}   遊び直し {self.replays} 回')

        self.root.after(200, self.refresh)

    # ---------- 記録 ----------
    def record(self, which):
        """3 秒数えてからカーソル位置を覚える。押したあと目的の場所へ移す。"""
        labels = {'menu': '交換画面の 100', '3000': 'スクロール後の 3000',
                  'play': 'プレイ開始', 'after': '開始後に押す場所',
                  'quit': 'コンティニューの やめる',
                  'limit': 'プレイ上限数追加', 'cancel': '自動追加のキャンセル',
                  'cash': '右上の精算',
                  'cash2': '精算確認の精算', 'next': 'リザルトの次へ',
                  'next2': '二枚目の次へ', 'again': '続けて遊ぶ',
                  'game': '一覧の三番目',
                  'play2': 'ゲーム説明のプレイ', 'rate': 'レート決定'}

        def grab_point():
            pos = cursor_pos()
            setattr(self, POINTS[which], pos)
            if which in ANCHOR_PATHS:
                self.save_anchor(which, pos)
            self.save_config()
            self.note = f'{labels[which]} {pos} を記録'
            self.root.after(2500, lambda: setattr(self, 'note', ''))

        def tick(left):
            if left:
                self.note = f'{labels[which]} の上へ   あと {left}'
                self.root.after(1000, tick, left - 1)
            else:
                grab_point()

        tick(3)

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
            img = grab_anchor(pos)
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
        else:
            self.cash_at = 0
            self.taps   = 0
            self.swaps  = 0
            self.quits  = 0
            self.limits = 0
            self.cashes = 0

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
    def watch_loop(self):
        """0.7 秒ごとに画面を見て、見つけた画面に応じた手を打つ。

        上から順に見て、最初に見つかったものだけを処理する。保留の判定は
        他の画面が被っているときに誤爆しやすいので一番下に置いてある。
        """
        keys  = ('cash2', 'next', 'next2', 'again', 'game', 'play2', 'rate',
                 'quit', 'limit', 'menu')
        clear = {k: 0 for k in keys}
        hits  = dict(clear)
        while True:
            time.sleep(WATCH_INTERVAL)
            if not (self.running and IS_WIN and HAS_VISION) or self.exchanging:
                hits = dict(clear)
                continue

            # 待ち時間が過ぎていたら、画面を見るより先に精算へ入る
            if self.cash_at and time.monotonic() >= self.cash_at and self.pos_cash:
                self.cash_at = 0
                hits = dict(clear)
                self.do_tap('cash', '精算を押した', 1.5)
                continue

            play = self.tapping   # ゲーム中にだけ出る画面かどうかの目安
            for key, ready, check, act, need in (
                ('cash2', self.auto_cash and self.pos_cash2,
                 lambda: self.matches('cash2', self.pos_cash2),
                 lambda: self.do_tap('cash2', '精算した', 2.0, stop_keys=True, count='cashes'), 2),
                ('next',  self.auto_again and self.pos_next,
                 lambda: self.matches('next', self.pos_next),
                 lambda: self.do_tap('next', 'リザルトを送った', 1.5), 2),
                ('next2', self.auto_again and self.pos_next2,
                 lambda: self.matches('next2', self.pos_next2),
                 lambda: self.do_tap('next2', 'リザルトを送った', 1.5), 2),
                ('again', self.auto_again and self.pos_again,
                 lambda: self.matches('again', self.pos_again),
                 lambda: self.do_tap('again', '続けて遊ぶを押した', 2.0), 2),
                ('game',  self.auto_again and self.pos_game,
                 lambda: self.matches('game', self.pos_game),
                 lambda: self.do_tap('game', '台を選んだ', 2.0, count='replays'), 2),
                ('play2', self.auto_again and self.pos_play2,
                 lambda: self.matches('play2', self.pos_play2),
                 lambda: self.do_tap('play2', 'プレイを押した', 1.5), 2),
                ('rate',  self.auto_again and self.pos_rate,
                 lambda: self.matches('rate', self.pos_rate),
                 lambda: self.do_tap('rate', 'レートを決めた', 3.0), 2),
                ('quit',  self.auto_quit and play and self.pos_quit,
                 lambda: self.matches('quit', self.pos_quit),
                 lambda: self.do_tap('quit', 'やめるを押した', 1.5, count='quits'), 2),
                ('limit', self.auto_limit and play and self.pos_limit and self.pos_cancel,
                 lambda: self.matches('limit', self.pos_limit), self.do_limit, 2),
                ('menu',  self.auto_swap and self.pos_menu and self.pos_3000 and self.pos_play
                 and not (self.max_swap and self.swaps >= self.max_swap),
                 lambda: self.matches('menu', self.pos_menu), self.do_exchange, 2),
            ):
                if not ready:
                    hits[key] = 0
                    continue
                # 一瞬の一致では動かさない。続けて出たら本物とみなす
                hits[key] = hits[key] + 1 if check() else 0
                if hits[key] >= need:
                    hits = dict(clear)
                    act()
                    break

    def do_tap(self, key, label, wait, stop_keys=False, count=None):
        """記録した場所を一回押して、画面が変わるまで待つ。"""
        pos = getattr(self, POINTS[key])
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
            click_at(self.pos_limit[0], self.pos_limit[1], 0.03)
            time.sleep(1.2)   # 次のダイアログが開くまで待つ
            click_at(self.pos_cancel[0], self.pos_cancel[1], 0.03)
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
            click_at(self.pos_menu[0], self.pos_menu[1], 0.03)
            time.sleep(0.5)

            # 3000 は畳んだ状態では見えないので、その位置でホイールを回して送る
            if self.scrolls:
                scroll_at(self.pos_3000[0], self.pos_3000[1], self.scrolls)
                time.sleep(0.4)

            click_at(self.pos_3000[0], self.pos_3000[1], 0.03)
            time.sleep(0.6)
            click_at(self.pos_play[0], self.pos_play[1], 0.03)
            self.swaps += 1
            time.sleep(2.5)   # ゲーム画面が戻るまで待つ

            # 台に入った直後は説明の画面が被る。どこか一度押して閉じる
            if self.pos_after:
                click_at(self.pos_after[0], self.pos_after[1], 0.03)
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
