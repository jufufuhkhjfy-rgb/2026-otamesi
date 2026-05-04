"""
Fortnite Brainrot 自動購入ボット
NEURAL LINK // INTERFACE_V.2.0
Tesseract OCR でキャラ名を読み取り、ウィッシュリストに一致したら自動購入
"""

import tkinter as tk
from tkinter import ttk
import threading
import time
import queue
import json
import os
from datetime import datetime

from PIL import Image, ImageTk, ImageEnhance, ImageFilter
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
# 色定数 (サイバーパンク)
# ═══════════════════════════════════════════
BG     = '#0a0a0a'
BG2    = '#111111'
BG3    = '#0d1a0d'
CYAN   = '#00ffcc'
CYAN2  = '#00ccaa'
PINK   = '#ff006e'
RED    = '#ff3333'
GREEN  = '#00ff44'
WHITE  = '#e0e0e0'
GRAY2  = '#1a1a1a'
YELLOW = '#ffee00'

FONT_MONO = ('Courier New', 9)
FONT_BOLD = ('Courier New', 9, 'bold')
FONT_TITLE = ('Courier New', 11, 'bold')

# ═══════════════════════════════════════════
# 既知のブレインロット・キャラクター一覧
# ═══════════════════════════════════════════
BRAINROT_CHARS = [
    # アンコモン
    "Fishini Bossini", "Lirili Larilla", "Tim Cheese", "Fluriflura",
    "Penguino Cocosino", "Svinina Bombardino", "Pipi Kiwi", "Pipi Avocado",
    # レア
    "Trippi Troppi", "Tung Sahur", "Grangster Footera", "Boneca Ambalabu",
    "Pipi Corni", "Ta Ta Ta Ta Sahur", "Burballoni Watermeloni", "Pipi Potato",
    # エピック
    "Cappuccino Assassino", "Brr Brr Patapim", "Trulimero Trulicina",
    "Bananita Dolphinita", "Los Lirilitos", "Salamino Pinguino",
    "Tric Trac Baraboom", "Los Tung TungCitos", "Tukanno Bananno",
    "Blueberrinni Octopussini", "Spijiniro Golubiro", "Penguini Zucchini",
    "Blueberrini Tatticini", "Gingobalo Gingobali",
    # レジェンダリー
    "Burbaloni Loliloli", "Chimpanzini Bananini", "Ballerina Cappuccina",
    "Chef Crabracadabra", "Glorbo Fruttodillo", "Cacto Hipopotamo",
    "Ballerino Lololo", "Lerulerulerule", "Bambini Crostini", "Francescoo",
    "Zibra Zubra Zibralini", "Bambu Di Miale", "Mangolini Parrocini",
    "Lampu Lampu Sahur", "Octopuss Coconuss", "Leonelli Cactuselli",
    "Elefantucci Bananucci", "Avocadini Antilopini", "Dragonini Ananasini",
    # ミシック
    "Frigo Camelo", "Orangutini Annassini", "Bombardiro Crocodilo",
    "Bombombini Gusini", "Gorillo Watermellondrillo", "Sigma Boy", "Matteo",
    # Brainrot God
    "Cocofanto Elefanto", "Tob Tobi Tob", "Tralalero Tralala",
    "Odin Din Din Dun", "Akulini Cactusini",
    # シークレット
    "Los Tralaleritos", "Trenostruzzo Turbo", "Los Orcaleritos",
    "Pakrahmatmamat", "Frogino Assassino", "Ketchuru and Musturu",
    # エターナル
    "Gigalitraktos Spidorobos", "Burguro dan Fryuro", "Bearini Plammini Guardini",
    # GOAT
    "SKIBIDI TOILET",
]

RARITY_LIST = [
    ('common',    '#6e6e6e'),
    ('uncommon',  '#1eff00'),
    ('rare',      '#0070dd'),
    ('epic',      '#a335ee'),
    ('legendary', '#ff8000'),
    ('rainbow',   '#ff006e'),
    ('special',   '#e6cc80'),
    ('icon',      '#00d4ff'),
]

SAVE_FILE = 'fortnite_bot_config.json'


# ═══════════════════════════════════════════
# カスタムウィジェット
# ═══════════════════════════════════════════
class CyberpunkButton(tk.Canvas):
    """角飾り付きサイバーパンク風ボタン"""

    def __init__(self, parent, text, command=None, color=CYAN,
                 width=160, height=36, active_bg=None, **kw):
        super().__init__(parent, width=width, height=height,
                         bg=BG, highlightthickness=0, **kw)
        self.command = command
        self.color = color
        self.active_bg = active_bg or color
        self._text = text
        self._hovered = False
        self._active = False
        self._draw()
        self.bind('<Enter>', lambda _: self._hover(True))
        self.bind('<Leave>', lambda _: self._hover(False))
        self.bind('<Button-1>', self._click)

    def _draw(self):
        self.delete('all')
        w, h = int(self['width']), int(self['height'])
        col = self.color
        if self._active:
            fill, text_col = self.active_bg, BG
        elif self._hovered:
            fill, text_col = col, BG
        else:
            fill, text_col = BG2, col

        self.create_rectangle(1, 1, w-2, h-2, outline=col, fill=fill, width=1)
        # 角装飾
        for x1, y1, x2, y2 in [(1,1,9,1),(1,1,1,9),(w-9,h-2,w-2,h-2),(w-2,h-9,w-2,h-2)]:
            self.create_line(x1, y1, x2, y2, fill=col, width=2)
        self.create_text(w//2, h//2, text=self._text, fill=text_col, font=FONT_BOLD)

    def _hover(self, state):
        self._hovered = state; self._draw()

    def _click(self, _):
        if self.command:
            self.command()

    def set_text(self, t):
        self._text = t; self._draw()

    def set_active(self, state):
        self._active = state; self._draw()

    def set_color(self, c):
        self.color = c; self.active_bg = c; self._draw()


class ScanButton(CyberpunkButton):
    """スキャン開始/停止ボタン"""

    def set_scanning(self, scanning):
        if scanning:
            self.set_text('■ スキャン停止')
            self.set_color(PINK)
        else:
            self.set_text('▶ スキャン開始')
            self.set_color(CYAN)


# ═══════════════════════════════════════════
# メインアプリ
# ═══════════════════════════════════════════
class FortniteBot:

    def __init__(self):
        self.running = False
        self.scan_thread = None
        self._click_thread = None
        self.buying = False        # 連打フラグ: True=検知中→連打, False=検知外れ→停止
        self.buying_char: str | None = None
        self.log_q: queue.Queue = queue.Queue()
        self.detected_chars: list[dict] = []
        self.wishlist: list[str] = []
        self.selected_rarities: set[str] = set()
        self.buy_pos = None   # (x, y) 購入ボタン位置 (ユーザーが設定)
        self.calibrating = False
        self._preview_photo = None

        self.root = tk.Tk()
        self.root.title('NEURAL LINK // INTERFACE_V.2.0')
        self.root.configure(bg=BG)
        self.root.resizable(False, False)

        self._load_config()
        self._build_ui()
        self.root.after(150, self._poll_log)
        self._refresh_windows()
        self._log(f'[SYSTEM] NEURAL LINK v2.0 起動完了 // Tesseract: {"OK" if HAS_TESS else "未検出"}')
        self.root.mainloop()

    # ─────────────────────────────────────────
    # UI構築
    # ─────────────────────────────────────────
    def _build_ui(self):
        self._build_titlebar()
        tk.Frame(self.root, bg=CYAN, height=1).pack(fill='x')

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill='both', expand=True)

        self._build_left(body)
        tk.Frame(body, bg='#1a1a1a', width=1).pack(side='left', fill='y')
        self._build_right(body)

        self._build_statusbar()

    def _build_titlebar(self):
        bar = tk.Frame(self.root, bg=BG)
        bar.pack(fill='x')
        tk.Label(bar, text='▶  NEURAL LINK // INTERFACE_V.2.0',
                 font=FONT_TITLE, fg=CYAN, bg=BG).pack(side='left', padx=12, pady=7)
        for txt, col, cmd in [('X', RED, self.root.destroy),
                               ('F', CYAN, None),
                               ('—', WHITE, self.root.iconify)]:
            lbl = tk.Label(bar, text=txt, font=FONT_BOLD, fg=BG, bg=col, width=3,
                           cursor='hand2', padx=2, pady=5)
            lbl.pack(side='right', padx=1, pady=4)
            lbl.bind('<Button-1>', lambda _, c=cmd: c() if c else None)

    def _build_statusbar(self):
        bar = tk.Frame(self.root, bg='#0d0d0d', height=22)
        bar.pack(fill='x', side='bottom')
        self._status_var = tk.StringVar(value='SYSTEM IDLE // WAITING FOR INPUT')
        tk.Label(bar, textvariable=self._status_var, font=('Courier New', 8),
                 fg=CYAN2, bg='#0d0d0d').pack(side='left', padx=8)

    def _build_left(self, parent):
        left = tk.Frame(parent, bg=BG, width=430)
        left.pack(side='left', fill='y')
        left.pack_propagate(False)

        # システムステータス
        sf = tk.Frame(left, bg=BG3, relief='flat')
        sf.pack(fill='x', padx=8, pady=(8, 4))
        tk.Label(sf, text='SYSTEM STATUS: ONLINE // VERSION: v6.2.7',
                 font=FONT_BOLD, fg=GREEN, bg=BG3).pack(anchor='w', padx=8, pady=4)

        # ウィンドウ選択
        wf = self._labeled_frame(left, 'ウィンドウ')
        inner = tk.Frame(wf, bg=BG)
        inner.pack(fill='x', padx=4, pady=4)
        self._window_var = tk.StringVar()
        self._window_cb = ttk.Combobox(inner, textvariable=self._window_var,
                                        width=27, state='readonly',
                                        font=FONT_MONO)
        self._window_cb.pack(side='left', padx=(0, 4))
        tk.Button(inner, text='↺', font=('Courier New', 11), fg=CYAN, bg=BG2,
                  bd=0, cursor='hand2', command=self._refresh_windows).pack(side='left')

        # 取得キー + キャラ検索 (横並び)
        kf = tk.Frame(left, bg=BG)
        kf.pack(fill='x', padx=8, pady=4)

        kl = tk.Frame(kf, bg=BG)
        kl.pack(side='left', padx=(0, 8))
        tk.Label(kl, text='取得キー', font=FONT_MONO, fg=CYAN, bg=BG).pack(anchor='w')
        self._key_var = tk.StringVar(value='D5')
        tk.Entry(kl, textvariable=self._key_var, width=7,
                 font=('Courier New', 10, 'bold'), fg=CYAN, bg=BG2,
                 insertbackground=CYAN, bd=1, relief='solid').pack(ipady=4)

        kr = tk.Frame(kf, bg=BG)
        kr.pack(side='left', fill='x', expand=True)
        tk.Label(kr, text='キャラ検索 (カンマ区切りウィッシュリスト)', font=FONT_MONO, fg=CYAN, bg=BG).pack(anchor='w')
        self._search_var = tk.StringVar()
        self._search_var.trace('w', self._update_wishlist)
        tk.Entry(kr, textvariable=self._search_var, width=22,
                 font=FONT_MONO, fg=CYAN, bg=BG2,
                 insertbackground=CYAN, bd=1, relief='solid').pack(fill='x', ipady=4)

        # レアリティ選択
        rf = self._labeled_frame(left, 'レアリティ選択')
        ri = tk.Frame(rf, bg=BG)
        ri.pack(padx=4, pady=4, anchor='w')
        self._rar_btns: dict[str, tk.Canvas] = {}
        for idx, (name, col) in enumerate(RARITY_LIST):
            c = tk.Canvas(ri, width=34, height=34, bg=col,
                          highlightthickness=2, highlightbackground=BG,
                          cursor='hand2')
            c.grid(row=idx // 5, column=idx % 5, padx=2, pady=2)
            c.bind('<Button-1>', lambda _, n=name, cv=c: self._toggle_rarity(n, cv))
            self._rar_btns[name] = c

        # スキャンボタン
        self._scan_btn = ScanButton(left, '▶ スキャン開始',
                                     command=self._toggle_scan,
                                     color=CYAN, width=408, height=44)
        self._scan_btn.pack(padx=8, pady=8)

        # 購入ボタン位置キャリブレーション
        cal_frame = tk.Frame(left, bg=BG)
        cal_frame.pack(fill='x', padx=8, pady=(0, 4))
        self._cal_btn = CyberpunkButton(cal_frame, '購入ボタン位置を設定',
                                         command=self._start_calibrate,
                                         color=YELLOW, width=280, height=30)
        self._cal_btn.pack(side='left')
        self._cal_label = tk.Label(cal_frame, text='未設定', font=FONT_MONO,
                                    fg=GRAY2, bg=BG)
        self._cal_label.pack(side='left', padx=8)

        # タブボタン
        tab_f = tk.Frame(left, bg=BG)
        tab_f.pack(fill='x', padx=8, pady=(4, 0))
        for txt, key, col in [('AI視点', 'ai', CYAN), ('ログ出力', 'log', PINK),
                               ('ログ消去', 'clear', PINK), ('ログ表示', 'logview', CYAN)]:
            tk.Button(tab_f, text=txt, font=FONT_BOLD, fg=BG, bg=col,
                      bd=0, padx=8, pady=3, cursor='hand2',
                      command=lambda k=key: self._tab_action(k)).pack(side='left', padx=1)

        # キャラ一覧 (スクロール)
        self._char_outer = tk.Frame(left, bg=BG2)
        self._char_outer.pack(fill='both', expand=True, padx=8, pady=4)
        self._char_canvas = tk.Canvas(self._char_outer, bg=BG2, highlightthickness=0)
        sb = ttk.Scrollbar(self._char_outer, orient='vertical',
                           command=self._char_canvas.yview)
        self._char_inner = tk.Frame(self._char_canvas, bg=BG2)
        self._char_inner.bind('<Configure>',
            lambda _: self._char_canvas.configure(
                scrollregion=self._char_canvas.bbox('all')))
        self._char_canvas.create_window((0, 0), window=self._char_inner, anchor='nw')
        self._char_canvas.configure(yscrollcommand=sb.set)
        self._char_canvas.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')

    def _build_right(self, parent):
        right = tk.Frame(parent, bg=BG2)
        right.pack(side='right', fill='both', expand=True)

        # ヘッダー
        hdr = tk.Frame(right, bg=BG2)
        hdr.pack(fill='x', padx=8, pady=(6, 0))
        tk.Label(hdr, text='REC ●', font=FONT_BOLD, fg=RED, bg=BG2).pack(side='left')
        tk.Label(hdr, text='  LIVE FEED // OCR_PROCESSOR',
                 font=('Courier New', 11, 'bold'), fg=RED, bg=BG2).pack(side='left')
        # 右上コーナー
        tk.Label(hdr, text='┐', font=('Courier New', 14), fg=RED, bg=BG2).pack(side='right')

        # ライブプレビュー
        preview_wrap = tk.Frame(right, bg='#050505', bd=1, relief='solid')
        preview_wrap.pack(fill='both', expand=True, padx=8, pady=4)
        self._preview_lbl = tk.Label(preview_wrap, bg='#050505',
                                      text='[ AWAITING SIGNAL ]',
                                      font=('Courier New', 10), fg='#cc0000')
        self._preview_lbl.pack(fill='both', expand=True)

        # OCR ログ
        log_frame = tk.Frame(right, bg=BG2)
        log_frame.pack(fill='x', padx=8, pady=(0, 4))
        tk.Label(log_frame, text='OCR / LOG OUTPUT:', font=FONT_BOLD,
                 fg=CYAN2, bg=BG2).pack(anchor='w')
        self._log_text = tk.Text(log_frame, height=10, font=('Courier New', 8),
                                  fg=GREEN, bg='#050505', insertbackground=GREEN,
                                  bd=0, state='disabled', wrap='word')
        log_sb = ttk.Scrollbar(log_frame, orient='vertical', command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=log_sb.set)
        self._log_text.pack(side='left', fill='x', expand=True)
        log_sb.pack(side='right', fill='y')

        # 下コーナー
        bot = tk.Frame(right, bg=BG2)
        bot.pack(fill='x', padx=8)
        tk.Label(bot, text='└', font=('Courier New', 14), fg=RED, bg=BG2).pack(side='left')
        tk.Label(bot, text='┘', font=('Courier New', 14), fg=RED, bg=BG2).pack(side='right')

    # ─────────────────────────────────────────
    # ウィンドウ管理
    # ─────────────────────────────────────────
    def _refresh_windows(self):
        wins = []
        if HAS_WIN32:
            def _cb(hwnd, _):
                if win32gui.IsWindowVisible(hwnd):
                    t = win32gui.GetWindowText(hwnd)
                    if t:
                        wins.append(t)
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
            self.buying = False
            self.buying_char = None
            self._scan_btn.set_scanning(False)
            self._set_status('SCAN STOPPED')
        else:
            self.running = True
            self._scan_btn.set_scanning(True)
            self._set_status('SCANNING...')
            self._click_thread = threading.Thread(target=self._click_loop, daemon=True)
            self._click_thread.start()
            self.scan_thread = threading.Thread(target=self._scan_loop, daemon=True)
            self.scan_thread.start()

    def _click_loop(self):
        """検知中は即・連打。検知外れたらボタン押さない。"""
        while self.running:
            if self.buying and self.buy_pos:
                pyautogui.click(self.buy_pos[0], self.buy_pos[1])
                time.sleep(0.08)   # ~12Hz 連打
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
            self._log('[WARN] pytesseract 未検出。pip install pytesseract でインストール後、'
                      'Tesseract本体も必要')
            return

        ocr_text = self._run_ocr(img)
        chars = self._parse_characters(ocr_text)
        log_names = ", ".join(chars[:4]) + ("..." if len(chars) > 4 else "") if chars else "なし"
        self._log(f'[SCAN] 検出: {len(chars)}体 | {log_names}')

        self.root.after(0, lambda c=chars: self._update_char_display(c))

        matched = [name for name in chars if self._matches_wishlist(name)]
        if matched:
            if not self.buying:
                self.buying_char = matched[0]
                self.buying = True
                self._log(f'[MATCH ★] {self.buying_char} 検知！連打開始...')
                self._set_status(f'BUYING: {self.buying_char}')
        else:
            if self.buying:
                self._log(f'[STOP] 検知外れました → 連打停止')
                self.buying = False
                self.buying_char = None
                self._set_status('SCANNING...')

    # ─────────────────────────────────────────
    # スクリーンキャプチャ
    # ─────────────────────────────────────────
    def _capture_screen(self) -> Image.Image | None:
        try:
            x, y, w, h = 0, 0, 1920, 1080
            if HAS_WIN32:
                title = self._window_var.get()
                hwnd = win32gui.FindWindow(None, title)
                if hwnd:
                    r = win32gui.GetWindowRect(hwnd)
                    x, y, w, h = r[0], r[1], r[2] - r[0], r[3] - r[1]
            with mss.mss() as sct:
                shot = sct.grab({'left': x, 'top': y, 'width': w, 'height': h})
            return Image.frombytes('RGB', shot.size, shot.bgra, 'raw', 'BGRX')
        except Exception as e:
            self._log(f'[ERROR] キャプチャ失敗: {e}')
            return None

    # ─────────────────────────────────────────
    # OCR処理
    # ─────────────────────────────────────────
    def _run_ocr(self, img: Image.Image) -> str:
        # 下部60%のみOCR (アイテムショップ領域)
        h = img.height
        crop = img.crop((0, int(h * 0.4), img.width, h))
        gray = crop.convert('L')
        enhanced = ImageEnhance.Contrast(gray).enhance(2.5)
        sharpened = enhanced.filter(ImageFilter.SHARPEN)
        cfg = '--psm 6 --oem 3 -l eng'
        return pytesseract.image_to_string(sharpened, config=cfg)

    def _parse_characters(self, text: str) -> list[str]:
        found = []
        text_lower = text.lower()
        for name in BRAINROT_CHARS:
            words = [w for w in name.lower().split() if len(w) > 3]
            if words and any(w in text_lower for w in words):
                found.append(name)
        return found

    # ─────────────────────────────────────────
    # ウィッシュリスト照合
    # ─────────────────────────────────────────
    def _matches_wishlist(self, char_name: str) -> bool:
        if not self.wishlist:
            return False
        cl = char_name.lower()
        for wish in self.wishlist:
            wl = wish.lower().strip()
            if wl and (wl in cl or cl in wl):
                return True
        return False

    # _auto_buy は _click_loop に統合済み。買い続けるかはbuyingフラグで制御。

    # ─────────────────────────────────────────
    # キャリブレーション (購入ボタン位置設定)
    # ─────────────────────────────────────────
    def _start_calibrate(self):
        self._log('[CAL] 3秒後にマウス座標を取得します。購入ボタンの上にマウスを置いてください...')
        self.calibrating = True
        threading.Thread(target=self._calibrate_worker, daemon=True).start()

    def _calibrate_worker(self):
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
            pw = 800
            ph = int(img.height * pw / img.width)
            ph = min(ph, 380)
            preview = img.resize((pw, ph), Image.LANCZOS)
            photo = ImageTk.PhotoImage(preview)
            self._preview_lbl.configure(image=photo, text='')
            self._preview_lbl.image = photo
            self._preview_photo = photo
        except Exception:
            pass

    def _update_char_display(self, chars: list[str]):
        for w in self._char_inner.winfo_children():
            w.destroy()

        if not chars:
            tk.Label(self._char_inner, text='キャラ未検出',
                     font=FONT_MONO, fg=GRAY2, bg=BG2).pack(pady=8)
            return

        row = col = 0
        # ヘッダー表示
        tk.Label(self._char_inner, text=f'検出: {len(chars)}体',
                 font=FONT_BOLD, fg=CYAN, bg=BG2).grid(
                     row=0, column=0, columnspan=3, sticky='w', padx=4, pady=2)
        row = 1
        for name in chars:
            matched = self._matches_wishlist(name)
            border = GREEN if matched else '#2a2a2a'
            cell = tk.Frame(self._char_inner, bg='#141414', bd=2, relief='solid',
                            highlightthickness=1 if matched else 0,
                            highlightbackground=border)
            cell.grid(row=row, column=col, padx=3, pady=3, sticky='nsew')

            icon = tk.Canvas(cell, width=52, height=52, bg='#1a1a2e', highlightthickness=0)
            icon.pack(pady=(4, 0))
            icon.create_text(26, 26, text='◈', font=('', 22), fill=CYAN if not matched else GREEN)
            if matched:
                icon.create_text(44, 10, text='★', font=('', 10), fill=YELLOW)

            tk.Label(cell, text=name[:18], font=('Courier New', 7),
                     fg=GREEN if matched else WHITE, bg='#141414',
                     wraplength=120).pack(padx=2, pady=2)

            col += 1
            if col >= 3:
                col = 0
                row += 1

    # ─────────────────────────────────────────
    # ログ
    # ─────────────────────────────────────────
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
        ts = datetime.now().strftime('%H:%M:%S')
        self._status_var.set(f'>> {msg} // {ts}')

    # ─────────────────────────────────────────
    # タブ操作
    # ─────────────────────────────────────────
    def _tab_action(self, key: str):
        if key == 'clear':
            self._log_text.configure(state='normal')
            self._log_text.delete('1.0', 'end')
            self._log_text.configure(state='disabled')
        elif key == 'log':
            pass  # ログエリアにフォーカス
        elif key == 'logview':
            pass

    # ─────────────────────────────────────────
    # レアリティフィルター
    # ─────────────────────────────────────────
    def _toggle_rarity(self, name: str, canvas: tk.Canvas):
        if name in self.selected_rarities:
            self.selected_rarities.discard(name)
            canvas.configure(highlightbackground=BG, highlightthickness=2)
        else:
            self.selected_rarities.add(name)
            canvas.configure(highlightbackground=WHITE, highlightthickness=3)

    # ─────────────────────────────────────────
    # ウィッシュリスト更新
    # ─────────────────────────────────────────
    def _update_wishlist(self, *_):
        raw = self._search_var.get()
        self.wishlist = [t.strip() for t in raw.split(',') if t.strip()]

    # ─────────────────────────────────────────
    # ヘルパー
    # ─────────────────────────────────────────
    def _labeled_frame(self, parent, label: str) -> tk.Frame:
        outer = tk.LabelFrame(parent, text=label, font=FONT_MONO,
                               fg=CYAN, bg=BG, bd=1, relief='solid')
        outer.pack(fill='x', padx=8, pady=4)
        return outer

    # ─────────────────────────────────────────
    # 設定保存/読み込み
    # ─────────────────────────────────────────
    def _save_config(self):
        data = {
            'wishlist': self._search_var.get() if hasattr(self, '_search_var') else '',
            'capture_key': self._key_var.get() if hasattr(self, '_key_var') else 'D5',
            'buy_pos': list(self.buy_pos) if self.buy_pos else None,
            'rarities': list(self.selected_rarities),
        }
        with open(SAVE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_config(self):
        if not os.path.exists(SAVE_FILE):
            return
        try:
            with open(SAVE_FILE, encoding='utf-8') as f:
                data = json.load(f)
            if data.get('buy_pos'):
                self.buy_pos = tuple(data['buy_pos'])
            if data.get('rarities'):
                self.selected_rarities = set(data['rarities'])
        except Exception:
            pass


if __name__ == '__main__':
    FortniteBot()
