"""
Fortnite Brainrot 自動購入ボット
NEURAL LINK // INTERFACE_V.2.0
キャラ画像をクリックして選択 → スキャン開始で自動購入
"""

import tkinter as tk
from tkinter import ttk
import threading
import time
import queue
import json
import os
import urllib.request
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageTk, ImageEnhance, ImageFilter, ImageDraw, ImageFont
import mss
import pyautogui

try:
    import pytesseract
    HAS_TESS = True
except ImportError:
    HAS_TESS = False

try:
    import win32gui
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

pyautogui.FAILSAFE = True

# ═══════════════════════════════════════════
# 色定数
# ═══════════════════════════════════════════
BG      = '#0a0a0a'
BG2     = '#111111'
BG3     = '#0d1a0d'
CYAN    = '#00ffcc'
CYAN2   = '#00ccaa'
PINK    = '#ff006e'
RED     = '#ff3333'
GREEN   = '#00ff44'
WHITE   = '#e0e0e0'
GRAY    = '#333333'
YELLOW  = '#ffee00'

FONT_MONO  = ('Courier New', 9)
FONT_BOLD  = ('Courier New', 9, 'bold')
FONT_TITLE = ('Courier New', 11, 'bold')
FONT_SMALL = ('Courier New', 7)

RARITY_COLOR = {
    'アンコモン':    '#1eff00',
    'レア':          '#0070dd',
    'エピック':      '#a335ee',
    'レジェンダリー':'#ff8000',
    'ミシック':      '#ff3333',
    'Brainrot God':  '#ffee00',
    'シークレット':  '#cccccc',
    'エターナル':    '#00ffff',
    'GOAT':          '#ff006e',
}

IMG_BASE = 'https://brainrot.fnjpnews.com/wp-content/uploads/2025/10/'
IMG_DIR  = Path('images')
SAVE_FILE = 'fortnite_bot_config.json'

# ═══════════════════════════════════════════
# キャラクターデータベース
# ═══════════════════════════════════════════
CHARACTERS = [
    # アンコモン
    {"name": "Fishini Bossini",          "rarity": "アンコモン"},
    {"name": "Lirili Larilla",           "rarity": "アンコモン"},
    {"name": "Tim Cheese",               "rarity": "アンコモン"},
    {"name": "Fluriflura",               "rarity": "アンコモン"},
    {"name": "Penguino Cocosino",        "rarity": "アンコモン"},
    {"name": "Svinina Bombardino",       "rarity": "アンコモン"},
    {"name": "Pipi Kiwi",                "rarity": "アンコモン"},
    {"name": "Pipi Avocado",             "rarity": "アンコモン"},
    # レア
    {"name": "Trippi Troppi",            "rarity": "レア"},
    {"name": "Tung Sahur",               "rarity": "レア"},
    {"name": "Grangster Footera",        "rarity": "レア"},
    {"name": "Boneca Ambalabu",          "rarity": "レア"},
    {"name": "Pipi Corni",               "rarity": "レア"},
    {"name": "Ta Ta Ta Ta Sahur",        "rarity": "レア"},
    {"name": "Burballoni Watermeloni",   "rarity": "レア"},
    {"name": "Pipi Potato",              "rarity": "レア"},
    # エピック
    {"name": "Cappuccino Assassino",     "rarity": "エピック"},
    {"name": "Brr Brr Patapim",          "rarity": "エピック"},
    {"name": "Trulimero Trulicina",      "rarity": "エピック"},
    {"name": "Bananita Dolphinita",      "rarity": "エピック"},
    {"name": "Los Lirilitos",            "rarity": "エピック"},
    {"name": "Salamino Pinguino",        "rarity": "エピック"},
    {"name": "Tric Trac Baraboom",       "rarity": "エピック"},
    {"name": "Los Tung TungCitos",       "rarity": "エピック"},
    {"name": "Tukanno Bananno",          "rarity": "エピック"},
    {"name": "Blueberrinni Octopussini", "rarity": "エピック"},
    {"name": "Spijiniro Golubiro",       "rarity": "エピック"},
    {"name": "Penguini Zucchini",        "rarity": "エピック"},
    {"name": "Blueberrini Tatticini",    "rarity": "エピック"},
    {"name": "Gingobalo Gingobali",      "rarity": "エピック"},
    # レジェンダリー
    {"name": "Burbaloni Loliloli",       "rarity": "レジェンダリー"},
    {"name": "Chimpanzini Bananini",     "rarity": "レジェンダリー"},
    {"name": "Ballerina Cappuccina",     "rarity": "レジェンダリー"},
    {"name": "Chef Crabracadabra",       "rarity": "レジェンダリー"},
    {"name": "Glorbo Fruttodillo",       "rarity": "レジェンダリー"},
    {"name": "Cacto Hipopotamo",         "rarity": "レジェンダリー"},
    {"name": "Ballerino Lololo",         "rarity": "レジェンダリー"},
    {"name": "Lerulerulerule",           "rarity": "レジェンダリー"},
    {"name": "Bambini Crostini",         "rarity": "レジェンダリー"},
    {"name": "Francescoo",               "rarity": "レジェンダリー"},
    {"name": "Zibra Zubra Zibralini",    "rarity": "レジェンダリー"},
    {"name": "Bambu Di Miale",           "rarity": "レジェンダリー"},
    {"name": "Mangolini Parrocini",      "rarity": "レジェンダリー"},
    {"name": "Lampu Lampu Sahur",        "rarity": "レジェンダリー"},
    {"name": "Octopuss Coconuss",        "rarity": "レジェンダリー"},
    {"name": "Leonelli Cactuselli",      "rarity": "レジェンダリー"},
    {"name": "Elefantucci Bananucci",    "rarity": "レジェンダリー"},
    {"name": "Avocadini Antilopini",     "rarity": "レジェンダリー"},
    {"name": "Dragonini Ananasini",      "rarity": "レジェンダリー"},
    # ミシック
    {"name": "Frigo Camelo",             "rarity": "ミシック"},
    {"name": "Orangutini Annassini",     "rarity": "ミシック"},
    {"name": "Bombardiro Crocodilo",     "rarity": "ミシック"},
    {"name": "Bombombini Gusini",        "rarity": "ミシック"},
    {"name": "Gorillo Watermellondrillo","rarity": "ミシック"},
    {"name": "Sigma Boy",                "rarity": "ミシック"},
    {"name": "Matteo",                   "rarity": "ミシック"},
    # Brainrot God
    {"name": "Cocofanto Elefanto",       "rarity": "Brainrot God"},
    {"name": "Tob Tobi Tob",             "rarity": "Brainrot God"},
    {"name": "Tralalero Tralala",        "rarity": "Brainrot God"},
    {"name": "Odin Din Din Dun",         "rarity": "Brainrot God"},
    {"name": "Akulini Cactusini",        "rarity": "Brainrot God"},
    # シークレット
    {"name": "Los Tralaleritos",         "rarity": "シークレット"},
    {"name": "Trenostruzzo Turbo",       "rarity": "シークレット"},
    {"name": "Los Orcaleritos",          "rarity": "シークレット"},
    {"name": "Pakrahmatmamat",           "rarity": "シークレット"},
    {"name": "Frogino Assassino",        "rarity": "シークレット"},
    {"name": "Ketchuru and Musturu",     "rarity": "シークレット"},
    # エターナル
    {"name": "Gigalitraktos Spidorobos", "rarity": "エターナル"},
    {"name": "Burguro dan Fryuro",       "rarity": "エターナル"},
    {"name": "Bearini Plammini Guardini","rarity": "エターナル"},
    # GOAT
    {"name": "SKIBIDI TOILET",           "rarity": "GOAT"},
]


def img_url(name: str) -> str:
    return IMG_BASE + name.replace(' ', '-') + '.png'


def img_path(name: str) -> Path:
    return IMG_DIR / (name.replace(' ', '-') + '.png')


def make_placeholder(size=80) -> Image.Image:
    img = Image.new('RGB', (size, size), '#1a1a2e')
    d = ImageDraw.Draw(img)
    d.text((size//2, size//2), '?', fill='#444444', anchor='mm')
    return img


# ═══════════════════════════════════════════
# カスタムボタン
# ═══════════════════════════════════════════
class CyberpunkButton(tk.Canvas):
    def __init__(self, parent, text, command=None, color=CYAN,
                 width=160, height=36, **kw):
        super().__init__(parent, width=width, height=height,
                         bg=BG, highlightthickness=0, **kw)
        self.command = command
        self.color = color
        self._text = text
        self._hovered = False
        self._draw()
        self.bind('<Enter>', lambda _: self._hover(True))
        self.bind('<Leave>', lambda _: self._hover(False))
        self.bind('<Button-1>', lambda _: self.command() if self.command else None)

    def _draw(self):
        self.delete('all')
        w, h = int(self['width']), int(self['height'])
        fill = self.color if self._hovered else BG2
        fg   = BG if self._hovered else self.color
        self.create_rectangle(1, 1, w-2, h-2, outline=self.color, fill=fill)
        for x1,y1,x2,y2 in [(1,1,9,1),(1,1,1,9),(w-9,h-2,w-2,h-2),(w-2,h-9,w-2,h-2)]:
            self.create_line(x1,y1,x2,y2, fill=self.color, width=2)
        self.create_text(w//2, h//2, text=self._text, fill=fg, font=FONT_BOLD)

    def _hover(self, s): self._hovered = s; self._draw()
    def set_text(self, t): self._text = t; self._draw()
    def set_color(self, c): self.color = c; self._draw()


# ═══════════════════════════════════════════
# メインアプリ
# ═══════════════════════════════════════════
class FortniteBot:

    def __init__(self):
        self.running     = False
        self.buying      = False
        self.buying_char: str | None = None
        self.buy_pos     = None
        self.selected: set[str] = set()   # クリックで選択したキャラ名
        self.log_q: queue.Queue = queue.Queue()
        self._photos: dict[str, ImageTk.PhotoImage] = {}
        self._cells:  dict[str, tk.Frame] = {}
        self._preview_photo = None

        IMG_DIR.mkdir(exist_ok=True)

        self.root = tk.Tk()
        self.root.title('NEURAL LINK // INTERFACE_V.2.0')
        self.root.configure(bg=BG)
        self.root.resizable(True, True)

        self._load_config()
        self._build_ui()
        self.root.after(150, self._poll_log)
        self._refresh_windows()
        self._log('[SYSTEM] NEURAL LINK v2.0 起動完了')
        self._log(f'[SYSTEM] Tesseract: {"OK" if HAS_TESS else "未検出 — pip install pytesseract 後 Tesseract本体も必要"}')

        # 画像を非同期でダウンロード
        threading.Thread(target=self._download_all_images, daemon=True).start()

        self.root.mainloop()

    # ─────────────────────────────────────────
    # UI 構築
    # ─────────────────────────────────────────
    def _build_ui(self):
        # タイトルバー
        bar = tk.Frame(self.root, bg=BG)
        bar.pack(fill='x')
        tk.Label(bar, text='▶  NEURAL LINK // INTERFACE_V.2.0',
                 font=FONT_TITLE, fg=CYAN, bg=BG).pack(side='left', padx=12, pady=7)
        for txt, col, cmd in [('X', RED, self.root.destroy),
                               ('—', WHITE, self.root.iconify)]:
            lbl = tk.Label(bar, text=txt, font=FONT_BOLD, fg=BG, bg=col,
                           width=3, cursor='hand2', padx=2, pady=5)
            lbl.pack(side='right', padx=1, pady=4)
            lbl.bind('<Button-1>', lambda _, c=cmd: c())
        tk.Frame(self.root, bg=CYAN, height=1).pack(fill='x')

        # ボディ (左右分割)
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill='both', expand=True)

        self._build_left(body)
        tk.Frame(body, bg=GRAY, width=1).pack(side='left', fill='y')
        self._build_right(body)

        # ステータスバー
        sb = tk.Frame(self.root, bg='#0d0d0d', height=22)
        sb.pack(fill='x', side='bottom')
        self._status_var = tk.StringVar(value='SYSTEM IDLE')
        tk.Label(sb, textvariable=self._status_var, font=('Courier New', 8),
                 fg=CYAN2, bg='#0d0d0d').pack(side='left', padx=8)

    def _build_left(self, parent):
        left = tk.Frame(parent, bg=BG, width=560)
        left.pack(side='left', fill='both', expand=True)
        left.pack_propagate(False)

        # ── 上部コントロール ──
        ctrl = tk.Frame(left, bg=BG2)
        ctrl.pack(fill='x', padx=8, pady=6)

        # ウィンドウ選択
        tk.Label(ctrl, text='ウィンドウ', font=FONT_MONO, fg=CYAN, bg=BG2).grid(
            row=0, column=0, sticky='w', padx=4)
        self._window_var = tk.StringVar()
        self._window_cb = ttk.Combobox(ctrl, textvariable=self._window_var,
                                        width=22, state='readonly', font=FONT_MONO)
        self._window_cb.grid(row=0, column=1, padx=4, pady=2)
        tk.Button(ctrl, text='↺', font=('Courier New', 11), fg=CYAN, bg=BG2,
                  bd=0, cursor='hand2', command=self._refresh_windows).grid(
                  row=0, column=2, padx=2)

        # 購入ボタン位置
        tk.Label(ctrl, text='購入ボタン位置', font=FONT_MONO, fg=CYAN, bg=BG2).grid(
            row=1, column=0, sticky='w', padx=4, pady=2)
        self._cal_label = tk.Label(ctrl, text='未設定', font=FONT_MONO,
                                    fg=RED, bg=BG2)
        self._cal_label.grid(row=1, column=1, sticky='w', padx=4)
        tk.Button(ctrl, text='設定 (3秒)', font=FONT_SMALL, fg=BG, bg=YELLOW,
                  bd=0, cursor='hand2', command=self._start_calibrate).grid(
                  row=1, column=2, padx=2)

        # 選択中キャラ表示
        sel_f = tk.Frame(left, bg='#0d0d0d')
        sel_f.pack(fill='x', padx=8, pady=2)
        tk.Label(sel_f, text='選択中: ', font=FONT_BOLD, fg=CYAN, bg='#0d0d0d').pack(side='left')
        self._sel_label = tk.Label(sel_f, text='なし', font=FONT_MONO,
                                    fg=YELLOW, bg='#0d0d0d', wraplength=400, justify='left')
        self._sel_label.pack(side='left')

        # ── スキャンボタン ──
        self._scan_btn = CyberpunkButton(left, '▶ スキャン開始',
                                          command=self._toggle_scan,
                                          color=CYAN, width=540, height=42)
        self._scan_btn.pack(padx=8, pady=6)

        # ── キャラグリッド (スクロール) ──
        grid_label = tk.Label(left, text='キャラクター一覧  (クリックで選択)',
                               font=FONT_BOLD, fg=CYAN, bg=BG)
        grid_label.pack(anchor='w', padx=10)

        wrapper = tk.Frame(left, bg=BG)
        wrapper.pack(fill='both', expand=True, padx=8, pady=4)

        self._grid_canvas = tk.Canvas(wrapper, bg=BG, highlightthickness=0)
        vsb = ttk.Scrollbar(wrapper, orient='vertical', command=self._grid_canvas.yview)
        self._grid_inner = tk.Frame(self._grid_canvas, bg=BG)
        self._grid_inner.bind('<Configure>',
            lambda _: self._grid_canvas.configure(
                scrollregion=self._grid_canvas.bbox('all')))
        self._grid_canvas.create_window((0, 0), window=self._grid_inner, anchor='nw')
        self._grid_canvas.configure(yscrollcommand=vsb.set)
        self._grid_canvas.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        self._grid_canvas.bind('<MouseWheel>',
            lambda e: self._grid_canvas.yview_scroll(-1*(e.delta//120), 'units'))

        self._build_char_grid()

    def _build_right(self, parent):
        right = tk.Frame(parent, bg=BG2, width=420)
        right.pack(side='right', fill='both')
        right.pack_propagate(False)

        hdr = tk.Frame(right, bg=BG2)
        hdr.pack(fill='x', padx=8, pady=(6, 0))
        tk.Label(hdr, text='REC ●', font=FONT_BOLD, fg=RED, bg=BG2).pack(side='left')
        tk.Label(hdr, text='  LIVE FEED // OCR_PROCESSOR',
                 font=('Courier New', 10, 'bold'), fg=RED, bg=BG2).pack(side='left')

        pw = tk.Frame(right, bg='#050505', bd=1, relief='solid')
        pw.pack(fill='both', expand=True, padx=8, pady=4)
        self._preview_lbl = tk.Label(pw, bg='#050505',
                                      text='[ AWAITING SIGNAL ]',
                                      font=('Courier New', 10), fg='#cc0000')
        self._preview_lbl.pack(fill='both', expand=True)

        lf = tk.Frame(right, bg=BG2)
        lf.pack(fill='x', padx=8, pady=(0, 4))
        tk.Label(lf, text='LOG OUTPUT:', font=FONT_BOLD, fg=CYAN2, bg=BG2).pack(anchor='w')
        self._log_text = tk.Text(lf, height=12, font=('Courier New', 8),
                                  fg=GREEN, bg='#050505', bd=0,
                                  state='disabled', wrap='word')
        lsb = ttk.Scrollbar(lf, orient='vertical', command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=lsb.set)
        self._log_text.pack(side='left', fill='x', expand=True)
        lsb.pack(side='right', fill='y')

        btn_f = tk.Frame(right, bg=BG2)
        btn_f.pack(fill='x', padx=8, pady=4)
        tk.Button(btn_f, text='ログ消去', font=FONT_SMALL, fg=BG, bg=PINK,
                  bd=0, padx=6, pady=2, cursor='hand2',
                  command=self._clear_log).pack(side='left')

    # ─────────────────────────────────────────
    # キャラグリッド
    # ─────────────────────────────────────────
    def _build_char_grid(self):
        COLS = 4
        cur_rarity = None
        col = 0
        grid_row = 0

        for char in CHARACTERS:
            name   = char['name']
            rarity = char['rarity']
            color  = RARITY_COLOR.get(rarity, WHITE)

            # レアリティヘッダー
            if rarity != cur_rarity:
                cur_rarity = rarity
                col = 0
                grid_row_start = grid_row
                hdr = tk.Label(self._grid_inner, text=f'── {rarity} ──',
                               font=FONT_BOLD, fg=color, bg=BG)
                hdr.grid(row=grid_row, column=0, columnspan=COLS,
                         sticky='w', padx=6, pady=(8, 2))
                grid_row += 1

            # キャラセル
            cell = tk.Frame(self._grid_inner, bg='#141414',
                            highlightthickness=2, highlightbackground=GRAY,
                            cursor='hand2', width=120, height=120)
            cell.grid(row=grid_row, column=col, padx=3, pady=3, sticky='nsew')
            cell.grid_propagate(False)

            # 画像ラベル
            img_lbl = tk.Label(cell, bg='#141414', cursor='hand2')
            img_lbl.place(x=4, y=4, width=112, height=80)

            # プレースホルダー
            ph = ImageTk.PhotoImage(make_placeholder(80))
            img_lbl.configure(image=ph)
            img_lbl.image = ph

            # キャラ名
            tk.Label(cell, text=name[:16], font=('Courier New', 7),
                     fg=WHITE, bg='#141414', wraplength=112).place(
                     x=0, y=84, width=120, height=18)

            # レアリティバッジ
            tk.Label(cell, text=rarity, font=('Courier New', 6, 'bold'),
                     fg=color, bg='#0a0a0a').place(x=0, y=102, width=120, height=14)

            # クリックイベント
            for w in [cell, img_lbl]:
                w.bind('<Button-1>', lambda _, n=name, c=cell: self._toggle_select(n, c))

            self._cells[name] = cell

            col += 1
            if col >= COLS:
                col = 0
                grid_row += 1

        # 選択済みキャラを反映
        for name in self.selected:
            if name in self._cells:
                self._cells[name].configure(highlightbackground=CYAN,
                                             highlightthickness=3)

    def _toggle_select(self, name: str, cell: tk.Frame):
        if name in self.selected:
            self.selected.discard(name)
            cell.configure(highlightbackground=GRAY, highlightthickness=2)
        else:
            self.selected.add(name)
            cell.configure(highlightbackground=CYAN, highlightthickness=3)
        self._update_sel_label()
        self._save_config()

    def _update_sel_label(self):
        if self.selected:
            self._sel_label.configure(text=', '.join(sorted(self.selected)))
        else:
            self._sel_label.configure(text='なし')

    # ─────────────────────────────────────────
    # 画像ダウンロード
    # ─────────────────────────────────────────
    def _download_all_images(self):
        self._log('[IMG] 画像ダウンロード開始...')
        ok = 0
        for char in CHARACTERS:
            name = char['name']
            path = img_path(name)
            if path.exists():
                self._load_image_to_cell(name, path)
                ok += 1
                continue
            try:
                url = img_url(name)
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=8) as r:
                    data = r.read()
                path.write_bytes(data)
                self._load_image_to_cell(name, path)
                ok += 1
                time.sleep(0.05)
            except Exception:
                pass  # プレースホルダーのまま
        self._log(f'[IMG] 完了: {ok}/{len(CHARACTERS)} 枚')

    def _load_image_to_cell(self, name: str, path: Path):
        try:
            img = Image.open(path).convert('RGBA')
            img.thumbnail((108, 76), Image.LANCZOS)
            bg = Image.new('RGBA', (108, 76), '#141414')
            ox = (108 - img.width)  // 2
            oy = (76  - img.height) // 2
            bg.paste(img, (ox, oy), img)
            photo = ImageTk.PhotoImage(bg)
            self._photos[name] = photo

            def _update(n=name, p=photo):
                cell = self._cells.get(n)
                if cell:
                    for w in cell.winfo_children():
                        if isinstance(w, tk.Label) and w.winfo_y() < 84:
                            w.configure(image=p)
                            w.image = p
                            break

            self.root.after(0, _update)
        except Exception:
            pass

    # ─────────────────────────────────────────
    # ウィンドウ管理
    # ─────────────────────────────────────────
    def _refresh_windows(self):
        wins = []
        if HAS_WIN32:
            def _cb(hwnd, _):
                if win32gui.IsWindowVisible(hwnd):
                    t = win32gui.GetWindowText(hwnd)
                    if t: wins.append(t)
            win32gui.EnumWindows(_cb, None)
        else:
            wins = ['Fortnite', 'FortniteClient-Win64-Shipping']
        self._window_cb['values'] = wins
        if wins:
            fn = [w for w in wins if 'fortnite' in w.lower()]
            self._window_var.set(fn[0] if fn else wins[0])

    # ─────────────────────────────────────────
    # スキャン制御
    # ─────────────────────────────────────────
    def _toggle_scan(self):
        if self.running:
            self.running = False
            self.buying  = False
            self.buying_char = None
            self._scan_btn.set_text('▶ スキャン開始')
            self._scan_btn.set_color(CYAN)
            self._set_status('SCAN STOPPED')
        else:
            if not self.selected:
                self._log('[WARN] キャラを選択してからスキャンしてください')
                return
            self.running = True
            self._scan_btn.set_text('■ スキャン停止')
            self._scan_btn.set_color(PINK)
            self._set_status('SCANNING...')
            threading.Thread(target=self._click_loop, daemon=True).start()
            threading.Thread(target=self._scan_loop,  daemon=True).start()

    def _click_loop(self):
        while self.running:
            if self.buying and self.buy_pos:
                pyautogui.click(self.buy_pos[0], self.buy_pos[1])
                time.sleep(0.08)
            else:
                time.sleep(0.05)

    def _scan_loop(self):
        while self.running:
            try:
                self._do_scan()
            except Exception as e:
                self._log(f'[ERROR] {e}')
            time.sleep(1.5)

    def _do_scan(self):
        img = self._capture_screen()
        if img is None:
            return
        self.root.after(0, lambda i=img: self._update_preview(i))

        if not HAS_TESS:
            self._log('[WARN] Tesseract 未検出')
            return

        text  = self._run_ocr(img)
        found = self._parse_chars(text)
        self._log(f'[SCAN] 検出: {", ".join(found[:3]) if found else "なし"}')

        matched = [n for n in found if n in self.selected]
        if matched:
            if not self.buying:
                self.buying_char = matched[0]
                self.buying = True
                self._log(f'[MATCH ★] {self.buying_char} 検知！連打開始')
                self._set_status(f'BUYING: {self.buying_char}')
        else:
            if self.buying:
                self._log('[STOP] 検知外れ → 連打停止')
                self.buying = False
                self.buying_char = None
                self._set_status('SCANNING...')

    # ─────────────────────────────────────────
    # スクリーンキャプチャ / OCR
    # ─────────────────────────────────────────
    def _capture_screen(self):
        try:
            x, y, w, h = 0, 0, 1920, 1080
            if HAS_WIN32:
                hwnd = win32gui.FindWindow(None, self._window_var.get())
                if hwnd:
                    r = win32gui.GetWindowRect(hwnd)
                    x, y, w, h = r[0], r[1], r[2]-r[0], r[3]-r[1]
            with mss.mss() as sct:
                shot = sct.grab({'left': x, 'top': y, 'width': w, 'height': h})
            return Image.frombytes('RGB', shot.size, shot.bgra, 'raw', 'BGRX')
        except Exception as e:
            self._log(f'[ERROR] キャプチャ失敗: {e}')
            return None

    def _run_ocr(self, img: Image.Image) -> str:
        h = img.height
        crop = img.crop((0, int(h * 0.4), img.width, h))
        enhanced = ImageEnhance.Contrast(crop.convert('L')).enhance(2.5)
        return pytesseract.image_to_string(
            enhanced.filter(ImageFilter.SHARPEN),
            config='--psm 6 --oem 3 -l eng')

    def _parse_chars(self, text: str) -> list[str]:
        tl = text.lower()
        return [c['name'] for c in CHARACTERS
                if any(w in tl for w in c['name'].lower().split() if len(w) > 3)]

    # ─────────────────────────────────────────
    # キャリブレーション
    # ─────────────────────────────────────────
    def _start_calibrate(self):
        self._log('[CAL] 3秒後にマウス位置を取得します...')
        threading.Thread(target=self._cal_worker, daemon=True).start()

    def _cal_worker(self):
        for i in range(3, 0, -1):
            self._log(f'[CAL] {i}...')
            time.sleep(1)
        pos = pyautogui.position()
        self.buy_pos = (pos.x, pos.y)
        self._log(f'[CAL ✓] 購入ボタン位置: ({pos.x}, {pos.y})')
        self.root.after(0, lambda: self._cal_label.configure(
            text=f'({pos.x}, {pos.y})', fg=GREEN))
        self._save_config()

    # ─────────────────────────────────────────
    # UI更新
    # ─────────────────────────────────────────
    def _update_preview(self, img: Image.Image):
        try:
            pw = 400
            ph = min(int(img.height * pw / img.width), 300)
            preview = img.resize((pw, ph), Image.LANCZOS)
            photo = ImageTk.PhotoImage(preview)
            self._preview_lbl.configure(image=photo, text='')
            self._preview_lbl.image = photo
            self._preview_photo = photo
        except Exception:
            pass

    def _log(self, msg: str):
        ts = datetime.now().strftime('%H:%M:%S')
        self.log_q.put(f'[{ts}] {msg}')

    def _poll_log(self):
        while not self.log_q.empty():
            msg = self.log_q.get_nowait()
            self._log_text.configure(state='normal')
            self._log_text.insert('end', msg + '\n')
            self._log_text.see('end')
            self._log_text.configure(state='disabled')
        self.root.after(150, self._poll_log)

    def _set_status(self, msg: str):
        self._status_var.set(f'>> {msg} // {datetime.now().strftime("%H:%M:%S")}')

    def _clear_log(self):
        self._log_text.configure(state='normal')
        self._log_text.delete('1.0', 'end')
        self._log_text.configure(state='disabled')

    # ─────────────────────────────────────────
    # 設定保存/読み込み
    # ─────────────────────────────────────────
    def _save_config(self):
        data = {
            'selected': list(self.selected),
            'buy_pos':  list(self.buy_pos) if self.buy_pos else None,
        }
        with open(SAVE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_config(self):
        if not os.path.exists(SAVE_FILE):
            return
        try:
            with open(SAVE_FILE, encoding='utf-8') as f:
                data = json.load(f)
            self.selected = set(data.get('selected', []))
            if data.get('buy_pos'):
                self.buy_pos = tuple(data['buy_pos'])
        except Exception:
            pass


if __name__ == '__main__':
    FortniteBot()
