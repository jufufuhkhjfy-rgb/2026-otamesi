"""
自動タイミングボット
mss で高速キャプチャ + バー速度予測で早押し対応
色はプレビューをクリックして自動取得
"""
import time
import threading
import ctypes
import tkinter as tk
from tkinter import ttk, messagebox
from collections import deque
import numpy as np
from PIL import ImageTk, Image, ImageGrab, ImageDraw
try:
    import mss
    USE_MSS = True
except ImportError:
    USE_MSS = False
import pyautogui
from pynput import keyboard as pynput_keyboard

pyautogui.FAILSAFE = True

TOLERANCE  = 40   # クリックした色からの許容誤差
COL_THRESH = 0.25 # 縦方向にこの割合以上一致する列だけ有効（ノイズ除去）


def grab_region(x, y, w, h):
    if USE_MSS:
        with mss.mss() as sct:
            shot = sct.grab({'left': x, 'top': y, 'width': w, 'height': h})
        return Image.frombytes('RGB', shot.size, shot.bgra, 'raw', 'BGRX')
    else:
        return ImageGrab.grab(bbox=(x, y, x+w, y+h))


class AutoTimingBot:
    def __init__(self):
        self.region       = None
        self.key          = 'e'
        self.running      = False
        self.cooldown_ms  = 800
        self.last_press   = 0
        self.window_name  = 'Roblox'
        self.early_ms     = 80
        self.prev_in_zone = False
        self.pos_history   = deque(maxlen=8)
        self.suppress_until = 0.0   # この時刻まで自動押し抑制
        self._key_listener  = None

        # 色設定（クリックで更新）
        self.white_rgb = (220, 220, 220)   # 白バーの代表色
        self.cyan_rgb  = (0,   200, 230)   # 水色ゾーンの代表色
        self._pick_mode = None
        self._preview_img = None
        self._preview_disp_size = (380, 60)

        self.root = tk.Tk()
        self.root.title("自動タイミングボット")
        self.root.resizable(False, False)
        self.root.configure(bg='#1a1a2e')
        self._build_ui()

    # ─────────────────────────────────────────
    def _build_ui(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TLabel',  background='#1a1a2e', foreground='white')
        style.configure('TFrame',  background='#1a1a2e')
        style.configure('TButton', padding=6)

        pad = dict(padx=10, pady=4)
        f = ttk.Frame(self.root)
        f.pack(padx=20, pady=16)

        # ── 領域選択 ──
        ttk.Label(f, text="【1】 バー領域を選択", font=('', 11, 'bold')).grid(
            row=0, column=0, columnspan=3, sticky='w', **pad)
        self.region_var = tk.StringVar(value="未選択")
        ttk.Label(f, textvariable=self.region_var).grid(row=1, column=0, columnspan=2, sticky='w', **pad)
        ttk.Button(f, text="領域を選択", command=self.pick_region).grid(row=1, column=2, **pad)

        # プレビュー（クリックで色取得）
        self.preview_label = tk.Label(f, bg='#0a0a1a', width=40, height=5,
                                       text="領域を選択すると画像が表示されます", fg='gray', cursor='crosshair')
        self.preview_label.grid(row=2, column=0, columnspan=3, padx=10, pady=4)
        self.preview_label.bind('<Button-1>', self._on_preview_click)

        # 色取得ボタン
        color_f = ttk.Frame(f)
        color_f.grid(row=3, column=0, columnspan=3, pady=2)
        ttk.Button(color_f, text="白バーの色を取得 →クリック",
                   command=lambda: self._set_pick_mode('white')).pack(side='left', padx=4)
        ttk.Button(color_f, text="水色ゾーンの色を取得 →クリック",
                   command=lambda: self._set_pick_mode('cyan')).pack(side='left', padx=4)

        self.color_status_var = tk.StringVar(value="↑ボタンを押してからプレビューをクリックしてください")
        ttk.Label(f, textvariable=self.color_status_var, foreground='#ffcc00').grid(
            row=4, column=0, columnspan=3, **pad)

        # 色表示
        color_disp = ttk.Frame(f)
        color_disp.grid(row=5, column=0, columnspan=3, pady=2)
        ttk.Label(color_disp, text="白バー:").pack(side='left', padx=4)
        self.white_swatch = tk.Label(color_disp, width=6, bg='#dcdcdc', relief='solid')
        self.white_swatch.pack(side='left', padx=2)
        self.white_val_lbl = tk.Label(color_disp, text="(220,220,220)", bg='#1a1a2e', fg='white')
        self.white_val_lbl.pack(side='left', padx=4)
        ttk.Label(color_disp, text="水色:").pack(side='left', padx=8)
        self.cyan_swatch = tk.Label(color_disp, width=6, bg='#00c8e6', relief='solid')
        self.cyan_swatch.pack(side='left', padx=2)
        self.cyan_val_lbl = tk.Label(color_disp, text="(0,200,230)", bg='#1a1a2e', fg='white')
        self.cyan_val_lbl.pack(side='left', padx=4)

        ttk.Separator(f, orient='horizontal').grid(row=6, column=0, columnspan=3, sticky='ew', pady=6)

        # ── 設定 ──
        ttk.Label(f, text="【2】 設定", font=('', 11, 'bold')).grid(
            row=7, column=0, columnspan=3, sticky='w', **pad)

        ttk.Label(f, text="押すキー:").grid(row=8, column=0, sticky='e', **pad)
        self.key_var = tk.StringVar(value='e')
        ttk.Entry(f, textvariable=self.key_var, width=6).grid(row=8, column=1, sticky='w', **pad)

        ttk.Label(f, text="早押し量 (ms):").grid(row=9, column=0, sticky='e', **pad)
        self.early_var = tk.IntVar(value=80)
        ttk.Spinbox(f, from_=0, to=300, textvariable=self.early_var, width=6).grid(row=9, column=1, sticky='w', **pad)
        ttk.Label(f, text="← 遅い場合は増やす", foreground='#888').grid(row=9, column=2, sticky='w', **pad)

        ttk.Label(f, text="クールダウン (ms):").grid(row=10, column=0, sticky='e', **pad)
        self.cooldown_var = tk.IntVar(value=800)
        ttk.Spinbox(f, from_=100, to=3000, textvariable=self.cooldown_var, width=6).grid(row=10, column=1, sticky='w', **pad)

        ttk.Label(f, text="手動押し後の抑制 (秒):").grid(row=11, column=0, sticky='e', **pad)
        self.suppress_sec_var = tk.IntVar(value=3)
        ttk.Spinbox(f, from_=0, to=10, textvariable=self.suppress_sec_var, width=6).grid(row=11, column=1, sticky='w', **pad)
        ttk.Label(f, text="← 自分で押した後この秒数無視", foreground='#888').grid(row=11, column=2, sticky='w', **pad)

        ttk.Label(f, text="対象ウィンドウ名:").grid(row=12, column=0, sticky='e', **pad)
        self.window_var = tk.StringVar(value='Roblox')
        ttk.Entry(f, textvariable=self.window_var, width=14).grid(row=12, column=1, sticky='w', **pad)
        ttk.Label(f, text="(空欄=常時)", foreground='#888').grid(row=12, column=2, sticky='w', **pad)

        ttk.Separator(f, orient='horizontal').grid(row=13, column=0, columnspan=3, sticky='ew', pady=6)

        # ── 実行 ──
        ttk.Label(f, text="【3】 実行", font=('', 11, 'bold')).grid(
            row=14, column=0, columnspan=3, sticky='w', **pad)

        self.start_btn = ttk.Button(f, text="▶ 開始", command=self.toggle)
        self.start_btn.grid(row=15, column=0, columnspan=3, sticky='ew', padx=10, pady=4)

        self.status_var = tk.StringVar(value="停止中")
        self.status_lbl = ttk.Label(f, textvariable=self.status_var, font=('', 10), foreground='gray')
        self.status_lbl.grid(row=16, column=0, columnspan=3, **pad)

        self.press_count_var = tk.StringVar(value="自動押し回数: 0")
        ttk.Label(f, textvariable=self.press_count_var).grid(row=17, column=0, columnspan=3, **pad)

        ttk.Label(f, text="緊急停止: マウスを画面左上へ", foreground='#ff6666').grid(
            row=18, column=0, columnspan=3, **pad)

        self.press_count  = 0
        self._status_tick = 0

    # ─────────────────────────────────────────
    # 色取得
    # ─────────────────────────────────────────
    def _set_pick_mode(self, mode):
        if not self.region:
            messagebox.showwarning("未設定", "先に領域を選択してください")
            return
        self._pick_mode = mode
        label = "白バー" if mode == 'white' else "水色ゾーン"
        self.color_status_var.set(f"プレビューの「{label}」部分をクリックしてください")
        self._refresh_preview()

    def _on_preview_click(self, event):
        if not self._pick_mode or self._preview_img is None:
            return
        disp_w, disp_h = self._preview_disp_size
        orig_w, orig_h = self._preview_img.size
        px = int(event.x * orig_w / disp_w)
        py = int(event.y * orig_h / disp_h)
        px = max(0, min(px, orig_w - 1))
        py = max(0, min(py, orig_h - 1))
        r, g, b = self._preview_img.getpixel((px, py))

        if self._pick_mode == 'white':
            self.white_rgb = (r, g, b)
            hex_col = f'#{r:02x}{g:02x}{b:02x}'
            self.white_swatch.config(bg=hex_col)
            self.white_val_lbl.config(text=f"({r},{g},{b})")
            self.color_status_var.set(f"白バー色を設定: RGB({r},{g},{b})")
        else:
            self.cyan_rgb = (r, g, b)
            hex_col = f'#{r:02x}{g:02x}{b:02x}'
            self.cyan_swatch.config(bg=hex_col)
            self.cyan_val_lbl.config(text=f"({r},{g},{b})")
            self.color_status_var.set(f"水色ゾーン色を設定: RGB({r},{g},{b})")

        self._pick_mode = None

    # ─────────────────────────────────────────
    # 領域選択
    # ─────────────────────────────────────────
    def pick_region(self):
        self.root.withdraw()
        time.sleep(0.2)

        overlay = tk.Toplevel()
        overlay.attributes('-fullscreen', True)
        overlay.attributes('-alpha', 0.3)
        overlay.attributes('-topmost', True)
        overlay.configure(bg='black')
        canvas = tk.Canvas(overlay, cursor='cross', bg='black', highlightthickness=0)
        canvas.pack(fill='both', expand=True)

        start   = [0, 0]
        rect_id = [None]

        def on_down(e):
            start[0], start[1] = e.x, e.y

        def on_drag(e):
            if rect_id[0]:
                canvas.delete(rect_id[0])
            rect_id[0] = canvas.create_rectangle(start[0], start[1], e.x, e.y,
                                                   outline='#00c8ff', width=2, fill='')

        def on_up(e):
            x1, y1 = min(start[0], e.x), min(start[1], e.y)
            x2, y2 = max(start[0], e.x), max(start[1], e.y)
            overlay.destroy()
            self.root.deiconify()
            if x2 - x1 > 10 and y2 - y1 > 5:
                self.region = (x1, y1, x2 - x1, y2 - y1)
                self.region_var.set(f"x={x1} y={y1}  {x2-x1}×{y2-y1}px")
                self._refresh_preview()
                self.color_status_var.set("↑ 白バーと水色ゾーンの色を取得してください")
            else:
                messagebox.showwarning("領域エラー", "もう少し広く選択してください")

        canvas.bind('<ButtonPress-1>',   on_down)
        canvas.bind('<B1-Motion>',       on_drag)
        canvas.bind('<ButtonRelease-1>', on_up)
        overlay.mainloop()

    def _refresh_preview(self):
        if not self.region:
            return
        x, y, w, h = self.region
        img = grab_region(x, y, w, h)
        self._preview_img = img
        disp_w = 380
        disp_h = max(40, int(disp_w * h / w))
        self._preview_disp_size = (disp_w, disp_h)
        disp  = img.resize((disp_w, disp_h), Image.NEAREST)
        photo = ImageTk.PhotoImage(disp)
        self.preview_label.config(image=photo, text='', width=disp_w, height=disp_h)
        self.preview_label.image = photo

    # ─────────────────────────────────────────
    # 開始 / 停止
    # ─────────────────────────────────────────
    def toggle(self):
        if self.running:
            self.running = False
            if self._key_listener:
                self._key_listener.stop()
                self._key_listener = None
            self.start_btn.config(text='▶ 開始')
            self.status_var.set("停止中")
            self.status_lbl.config(foreground='gray')
        else:
            if not self.region:
                messagebox.showwarning("未設定", "先に領域を選択してください")
                return
            self.key          = self.key_var.get().strip() or 'e'
            self.cooldown_ms  = self.cooldown_var.get()
            self.early_ms     = self.early_var.get()
            self.window_name  = self.window_var.get().strip()
            self.prev_in_zone = False
            self.pos_history.clear()
            self.running      = True
            self.suppress_until = 0.0
            self.start_btn.config(text='■ 停止')
            self.status_lbl.config(foreground='#00ffaa')
            self.status_var.set("監視中...")
            self._start_key_listener()
            threading.Thread(target=self._watch_loop, daemon=True).start()

    def _start_key_listener(self):
        target_key = self.key
        suppress_sec = self.suppress_sec_var.get()

        def on_press(key):
            if not self.running:
                return False  # リスナー停止
            try:
                ch = key.char
            except AttributeError:
                ch = None
            if ch and ch.lower() == target_key.lower():
                self.suppress_until = time.time() + suppress_sec
                self.root.after(0, lambda: self.status_var.set(
                    f"手動押し検知 → {suppress_sec}秒抑制中..."))

        self._key_listener = pynput_keyboard.Listener(on_press=on_press)
        self._key_listener.start()

    # ─────────────────────────────────────────
    # 監視ループ
    # ─────────────────────────────────────────
    def _watch_loop(self):
        x, y, w, h = self.region
        monitor = {'left': x, 'top': y, 'width': w, 'height': h}

        ctx = mss.mss() if USE_MSS else None
        try:
            while self.running:
                try:
                    t_capture = time.perf_counter()

                    if USE_MSS:
                        shot = ctx.grab(monitor)
                        arr  = np.frombuffer(shot.bgra, dtype=np.uint8).reshape(h, w, 4)
                        r, g, b = arr[:,:,2], arr[:,:,1], arr[:,:,0]
                    else:
                        img = ImageGrab.grab(bbox=(x, y, x+w, y+h))
                        arr = np.array(img)
                        r, g, b = arr[:,:,0], arr[:,:,1], arr[:,:,2]

                    wr, wg, wb = self.white_rgb
                    cr, cg, cb = self.cyan_rgb

                    # 白バー検出
                    white_mask = (
                        (r.astype(int) - wr)**2 +
                        (g.astype(int) - wg)**2 +
                        (b.astype(int) - wb)**2 < TOLERANCE**2 * 3
                    )
                    # 水色ゾーン検出
                    cyan_mask = (
                        (r.astype(int) - cr)**2 +
                        (g.astype(int) - cg)**2 +
                        (b.astype(int) - cb)**2 < TOLERANCE**2 * 3
                    )

                    # 縦方向に COL_THRESH 以上の割合で一致する列のみ有効
                    col_thresh = max(1, int(h * COL_THRESH))
                    cyan_cols  = np.where(cyan_mask.sum(axis=0)  >= col_thresh)[0]
                    white_cols = np.where(white_mask.sum(axis=0) >= col_thresh)[0]

                    if cyan_cols.size > 0 and white_cols.size > 0:
                        cyan_left  = int(cyan_cols.min())
                        cyan_right = int(cyan_cols.max())
                        white_cx   = int(white_cols.mean())

                        self.pos_history.append((t_capture, white_cx))
                        in_zone = cyan_left <= white_cx <= cyan_right
                        self._update_status(in_zone, white_cx, cyan_left, cyan_right, w)

                        if not in_zone and self.early_ms > 0 and len(self.pos_history) >= 3:
                            self._try_predict_press(cyan_left, cyan_right, t_capture)

                        if in_zone and not self.prev_in_zone:
                            self._do_press()

                        self.prev_in_zone = in_zone
                    else:
                        self._update_status_text("検知なし（色を再設定してください）")

                except Exception as e:
                    self.root.after(0, lambda err=str(e): self.status_var.set(f"エラー: {err}"))
                    time.sleep(0.5)
        finally:
            if ctx:
                ctx.close()

    def _try_predict_press(self, cyan_left, cyan_right, now):
        history = list(self.pos_history)
        if len(history) < 3:
            return
        t0, x0 = history[-3]
        t1, x1 = history[-1]
        dt = t1 - t0
        if dt < 0.001:
            return
        velocity = (x1 - x0) / dt
        if abs(velocity) < 10:
            return
        dist = (cyan_left - x1) if velocity > 0 else (x1 - cyan_right)
        if dist <= 0:
            return
        time_to_press_s = dist / abs(velocity) - (self.early_ms / 1000)
        if 0 < time_to_press_s < 0.05:
            time.sleep(time_to_press_s)
            self._do_press()

    def _do_press(self):
        now_s = time.time()
        if now_s < self.suppress_until:
            return
        now = now_s * 1000
        if now - self.last_press < self.cooldown_ms:
            return
        if not self._is_target_window_active():
            return
        pyautogui.press(self.key)
        self.last_press = now
        self.press_count += 1
        self.root.after(0, lambda c=self.press_count:
            self.press_count_var.set(f"自動押し回数: {c}"))

    def _is_target_window_active(self):
        if not self.window_name:
            return True
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        buf  = ctypes.create_unicode_buffer(256)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, 256)
        return self.window_name.lower() in buf.value.lower()

    def _update_status(self, in_zone, white_cx, cyan_l, cyan_r, bar_w):
        self._status_tick += 1
        if self._status_tick % 15 != 0:
            return
        pct      = int(white_cx / bar_w * 100) if bar_w else 0
        zone_pct = f"{int(cyan_l/bar_w*100)}〜{int(cyan_r/bar_w*100)}%"
        label    = "IN ZONE!" if in_zone else "監視中..."
        self.root.after(0, lambda: self.status_var.set(
            f"{label}  バー:{pct}%  ゾーン:{zone_pct}"))

    def _update_status_text(self, text):
        self._status_tick += 1
        if self._status_tick % 15 != 0:
            return
        self.root.after(0, lambda: self.status_var.set(text))

    def run(self):
        self.root.mainloop()


if __name__ == '__main__':
    bot = AutoTimingBot()
    bot.run()
