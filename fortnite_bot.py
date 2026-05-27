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
import difflib
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageTk, ImageEnhance, ImageFilter, ImageDraw
import mss
import pyautogui

try:
    import pytesseract
    HAS_TESS = True
except ImportError:
    HAS_TESS = False

try:
    import win32gui
    import win32api
    import win32con
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

pyautogui.FAILSAFE = True

def _vk_code(key: str) -> int:
    special = {'space': 0x20, 'return': 0x0D, 'enter': 0x0D,
               'tab': 0x09, 'shift': 0x10, 'ctrl': 0x11, 'alt': 0x12,
               'f1':0x70,'f2':0x71,'f3':0x72,'f4':0x73,'f5':0x74,
               'f6':0x75,'f7':0x76,'f8':0x77,'f9':0x78,'f10':0x79,
               'f11':0x7A,'f12':0x7B,'up':0x26,'down':0x28,
               'left':0x25,'right':0x27,'escape':0x1B,
               '0':0x30,'1':0x31,'2':0x32,'3':0x33,'4':0x34,
               '5':0x35,'6':0x36,'7':0x37,'8':0x38,'9':0x39}
    k = key.lower()
    if k in special:
        return special[k]
    return ord(k.upper()) if len(k) == 1 else 0

BG      = '#06060f'
BG2     = '#0e0e1a'
BG3     = '#0d1a0d'
CYAN    = '#00ffcc'
CYAN2   = '#00ccaa'
PINK    = '#ff00aa'
PINK2   = '#ff006e'
RED     = '#ff3333'
GREEN   = '#00ff44'
WHITE   = '#e0e0e0'
GRAY    = '#2a2a3a'
YELLOW  = '#ffee00'
ORANGE  = '#ff8800'
PURPLE  = '#cc00ff'

FONT_MONO  = ('Consolas', 10)
FONT_BOLD  = ('Consolas', 10, 'bold')
FONT_TITLE = ('Consolas', 13, 'bold')
FONT_SMALL = ('Consolas', 8)
FONT_UI    = ('Segoe UI', 10)         # 日本語ラベル
FONT_UI_SM = ('Segoe UI', 9)          # 小ラベル
FONT_UI_BD = ('Segoe UI', 10, 'bold') # ボールドラベル

def _load_custom_fonts() -> None:
    """Share Tech Mono / Orbitron を Google Fonts から取得して Windows に登録する"""
    import re, ctypes
    if not hasattr(ctypes, 'windll'):
        return
    global FONT_MONO, FONT_BOLD, FONT_TITLE, FONT_SMALL

    font_dir = Path(os.path.dirname(os.path.abspath(__file__))) / 'fonts'
    font_dir.mkdir(exist_ok=True)

    targets = [
        # (保存ファイル名, Google Fonts CSS クエリ, tkinter family名, 用途)
        ('ShareTechMono.ttf',  'Share+Tech+Mono',  'Share Tech Mono', 'mono'),
        ('Orbitron-Bold.ttf',  'Orbitron:700',     'Orbitron',        'title'),
    ]

    loaded: dict[str, bool] = {}
    for fname, css_q, family, role in targets:
        fpath = font_dir / fname
        if not fpath.exists():
            try:
                req = urllib.request.Request(
                    f'https://fonts.googleapis.com/css?family={css_q}',
                    headers={'User-Agent': 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'}
                )
                css = urllib.request.urlopen(req, timeout=8).read().decode()
                m = re.search(r'url\((https://[^)]+)\)', css)
                if m:
                    urllib.request.urlretrieve(m.group(1), fpath)
            except Exception:
                pass

        ok = False
        if fpath.exists():
            try:
                n = ctypes.windll.gdi32.AddFontResourceW(str(fpath.resolve()))
                if n > 0:
                    ctypes.windll.user32.SendMessageW(0xFFFF, 0x001D, 0, 0)
                    ok = True
            except Exception:
                pass
        loaded[role] = ok

    if loaded.get('mono'):
        FONT_MONO  = ('Share Tech Mono', 11)
        FONT_BOLD  = ('Share Tech Mono', 11, 'bold')
        FONT_SMALL = ('Share Tech Mono', 9)
    if loaded.get('title'):
        FONT_TITLE = ('Orbitron', 13, 'bold')

# OCRで読まれても無視すべきキーワード（レアリティ・属性・UI文字）
OCR_SKIP_WORDS = {
    # レアリティ名
    'uncommon','rare','epic','legendary','mythic','secret','eternal','goat',
    'brainrot','god',
    # 属性名
    'magical','gold','shadow','corrupted','divine','crystal','neon','super',
    'ultra','shiny','dark','light','void','forest','fire','ice','water',
    'thunder','wind','earth','chaos','holy','cursed','ancient','cosmic',
    # UI / ゲーム文字
    'collect','collect!','steals','cash','rebirths','lobby','support',
    'favorite','recommend','admin','machine','event','starts','join',
    'community','buy','sell','trade','shop','store','upgrade','level',
    'rebirth','prestige','boost','pet','egg','hatch','spin','roll',
    'claim','daily','mission','quest','reward','bonus','free','new',
    'limited','special','exclusive','obtained','equipped','stolen',
    # 記号・数字のみの行はparse時に除外
}

RARITY_COLOR = {
    'アンコモン':     '#1eff00',
    'レア':           '#0070dd',
    'エピック':       '#a335ee',
    'レジェンダリー': '#ff8000',
    'ミシック':       '#ff3333',
    'Brainrot God':   '#ffee00',
    'シークレット':   '#cccccc',
    'エターナル':     '#00ffff',
    'GOAT':           '#ff006e',
}

IMG_BASE  = 'https://brainrot.fnjpnews.com/wp-content/uploads/'
IMG_DIR   = Path('images')
SAVE_FILE = 'fortnite_bot_config.json'

# ═══════════════════════════════════════════
# キャラクターデータベース (name, rarity, img)
# ═══════════════════════════════════════════
CHARACTERS = [
    # ── アンコモン ──
    {"name": "Fishini Bossini",           "rarity": "アンコモン",     "img": "2025/10/Fishini-Bossini.png"},
    {"name": "Lirili Larilla",            "rarity": "アンコモン",     "img": "2025/10/Lirili-Larilla.png"},
    {"name": "Tim Cheese",                "rarity": "アンコモン",     "img": "2025/10/Tim-Cheese.png"},
    {"name": "Fluriflura",                "rarity": "アンコモン",     "img": "2025/10/Fluriflura.png"},
    {"name": "Penguino Cocosino",         "rarity": "アンコモン",     "img": "2025/10/Penguino-Cocosino.png"},
    {"name": "Svinina Bombardino",        "rarity": "アンコモン",     "img": "2025/10/Svinina-Bombardino.png"},
    {"name": "Pipi Kiwi",                 "rarity": "アンコモン",     "img": "2025/10/Default_5_6.webp"},
    {"name": "Pipi Avocado",              "rarity": "アンコモン",     "img": "2025/10/Default_9_4.webp"},
    # ── レア ──
    {"name": "Trippi Troppi",             "rarity": "レア",           "img": "2025/10/Default_1_6.webp"},
    {"name": "Tung Tung Tung Sahur",      "rarity": "レア",           "img": "2025/10/Tung-Sahur.webp"},
    {"name": "Grangster Footera",         "rarity": "レア",           "img": "2025/10/Grangster-Footera.webp"},
    {"name": "Boneca Ambalabu",           "rarity": "レア",           "img": "2025/10/Default_1_9.webp"},
    {"name": "Pipi Corni",                "rarity": "レア",           "img": "2025/10/Pipi-Corni.webp"},
    {"name": "Ta Ta Ta Ta Sahur",         "rarity": "レア",           "img": "2025/10/Ta-Ta-Ta-Ta-Sahur.webp"},
    {"name": "Burballoni Watermeloni",    "rarity": "レア",           "img": "2025/10/Burballoni-Watermeloni.webp"},
    {"name": "Pipi Potato",               "rarity": "レア",           "img": "2025/10/Pipi-Potato.webp"},
    # ── エピック ──
    {"name": "Cappuccino Assassino",      "rarity": "エピック",       "img": "2025/10/Cappuccino-Assassino.webp"},
    {"name": "Brr Brr Patapim",           "rarity": "エピック",       "img": "2025/10/Brr-Brr-Patapim.webp"},
    {"name": "Trulimero Trulicina",       "rarity": "エピック",       "img": "2025/10/Trulimero-Trulicina.webp"},
    {"name": "Bananita Dolphinita",       "rarity": "エピック",       "img": "2025/10/Bananita-Dolphinita.webp"},
    {"name": "Los Lirilitos",             "rarity": "エピック",       "img": "2025/10/Los-Lirilitos.webp"},
    {"name": "Salamino Pinguino",         "rarity": "エピック",       "img": "2025/10/Salamino-Pinguino.webp"},
    {"name": "Tric Trac Baraboom",        "rarity": "エピック",       "img": "2025/10/Tric-Trac-Baraboom.webp"},
    {"name": "Los Tung TungCitos",        "rarity": "エピック",       "img": "2025/10/Los-Tung-TungCitos.webp"},
    {"name": "Tukanno Bananno",           "rarity": "エピック",       "img": "2025/10/Tukanno-Bananno.webp"},
    {"name": "Blueberrinni Octopussini",  "rarity": "エピック",       "img": "2025/10/Blueberrinni-Octopussini.webp"},
    {"name": "Spijiniro Golubiro",        "rarity": "エピック",       "img": "2025/10/Spijiniro-Golubiro.webp"},
    {"name": "Penguini Zucchini",         "rarity": "エピック",       "img": "2025/10/Penguini-Zucchini.webp"},
    {"name": "Blueberrini Tatticini",     "rarity": "エピック",       "img": "2025/10/Blueberrini-Tatticini.webp"},
    {"name": "Gingobalo Gingobali",       "rarity": "エピック",       "img": "2025/10/Gingobalo-Gingobali.webp"},
    # ── レジェンダリー ──
    {"name": "Burbaloni Loliloli",        "rarity": "レジェンダリー", "img": "2025/10/Burbaloni-Loliloli.webp"},
    {"name": "Chimpanzini Bananini",      "rarity": "レジェンダリー", "img": "2025/10/Chimpanzini-Bananini.webp"},
    {"name": "Ballerina Cappuccina",      "rarity": "レジェンダリー", "img": "2025/10/Ballerina-Cappuccina.webp"},
    {"name": "Chef Crabracadabra",        "rarity": "レジェンダリー", "img": "2025/10/Chef-Crabracadabra.webp"},
    {"name": "Glorbo Fruttodillo",        "rarity": "レジェンダリー", "img": "2025/10/Glorbo-Fruttodillo.webp"},
    {"name": "Cacto Hipopotamo",          "rarity": "レジェンダリー", "img": "2025/10/Cacto-Hipopotamo.webp"},
    {"name": "Ballerino Lololo",          "rarity": "レジェンダリー", "img": "2025/10/Ballerino-Lololo.webp"},
    {"name": "Lerulerulerule",            "rarity": "レジェンダリー", "img": "2025/10/Lerulerulerule.webp"},
    {"name": "Bambini Crostini",          "rarity": "レジェンダリー", "img": "2025/10/Bambini-Crostini.webp"},
    {"name": "Francescoo",                "rarity": "レジェンダリー", "img": "2025/10/Francescoo.webp"},
    {"name": "Zibra Zubra Zibralini",     "rarity": "レジェンダリー", "img": "2025/10/Zibra-Zubra-Zibralini.webp"},
    {"name": "Bambu Di Miale",            "rarity": "レジェンダリー", "img": "2025/10/Bambu-Di-Miale.webp"},
    {"name": "Mangolini Parrocini",       "rarity": "レジェンダリー", "img": "2025/10/Mangolini-Parrocini.webp"},
    {"name": "Lampu Lampu Sahur",         "rarity": "レジェンダリー", "img": "2025/10/Lampu-Lampu-Sahur.webp"},
    {"name": "Octopuss Coconuss",         "rarity": "レジェンダリー", "img": "2025/10/Octopuss-Coconuss.webp"},
    {"name": "Leonelli Cactuselli",       "rarity": "レジェンダリー", "img": "2025/10/Leonelli-Cactuselli.webp"},
    {"name": "Elefantucci Bananucci",     "rarity": "レジェンダリー", "img": "2025/10/Elefantucci-Bananucci.webp"},
    {"name": "Avocadini Antilopini",      "rarity": "レジェンダリー", "img": "2025/10/Avocadini-Antilopini.webp"},
    {"name": "Dragonini Ananasini",       "rarity": "レジェンダリー", "img": "2026/02/Dragonini-Ananasini.webp"},
    # ── ミシック ──
    {"name": "Frigo Camelo",              "rarity": "ミシック",       "img": "2025/10/Frigo-Camelo.webp"},
    {"name": "Orangutini Annassini",      "rarity": "ミシック",       "img": "2025/10/Orangutini-Annassini.webp"},
    {"name": "Bombardiro Crocodilo",      "rarity": "ミシック",       "img": "2025/10/Bombardiro-Crocodilo.webp"},
    {"name": "Bombombini Gusini",         "rarity": "ミシック",       "img": "2025/10/Bombombini-Gusini.webp"},
    {"name": "Gorillo Watermellondrillo", "rarity": "ミシック",       "img": "2025/10/Gorillo-Watermellondrillo.webp"},
    {"name": "Sigma Boy",                 "rarity": "ミシック",       "img": "2025/10/Sigma-Boy.webp"},
    {"name": "Matteo",                    "rarity": "ミシック",       "img": "2025/10/Matteo.webp"},
    {"name": "Los Spijuniritos",          "rarity": "ミシック",       "img": "2025/10/Los-Spijuniritos.webp"},
    {"name": "Rhino Toasterino",          "rarity": "ミシック",       "img": "2025/10/Rhino-Toasterino.webp"},
    {"name": "Ganganzelli Trulala",       "rarity": "ミシック",       "img": "2025/10/Ganganzelli-Trulala.webp"},
    {"name": "Te Te Te Sahur",            "rarity": "ミシック",       "img": "2025/10/Te-Te-Te-Sahur.webp"},
    {"name": "Fireworkito Explodito",     "rarity": "ミシック",       "img": "2025/10/Fireworkito-Explodito.webp"},
    {"name": "Strawberrelli Flamingelli", "rarity": "ミシック",       "img": "2025/10/Strawberrelli-Flamingelli.webp"},
    {"name": "Elefantino Frigorifero",    "rarity": "ミシック",       "img": "2025/10/Elefantino-Frigorifero.webp"},
    {"name": "To To To Sahur",            "rarity": "ミシック",       "img": "2025/10/To-To-To-Sahur.webp"},
    {"name": "Elefante Cafettino",        "rarity": "ミシック",       "img": "2025/10/Elefante-Cafettino.webp"},
    {"name": "Antoniooo",                 "rarity": "ミシック",       "img": "2025/10/Antoniooo.webp"},
    {"name": "Kudanile Astronaute",       "rarity": "ミシック",       "img": "2025/10/Kudanile-Astronaute.webp"},
    {"name": "Girafa Celeste",            "rarity": "ミシック",       "img": "2025/10/Girafa-Celeste.webp"},
    {"name": "Mr Peppermint",             "rarity": "ミシック",       "img": "2025/10/Mr-Peppermint.webp"},
    {"name": "Perochello Lemonchello",    "rarity": "ミシック",       "img": "2025/10/Perochello-Lemonchello.webp"},
    {"name": "Tang Tang Kelentang",       "rarity": "ミシック",       "img": "2025/10/Tang-Tang-Kelentang.webp"},
    {"name": "Avocadorilla",              "rarity": "ミシック",       "img": "2025/10/Avocadorilla.webp"},
    {"name": "Patapimus Maximus",         "rarity": "ミシック",       "img": "2025/10/Patapimus-Maximus.webp"},
    {"name": "Tirilikalika Tirilikaliko", "rarity": "ミシック",       "img": "2025/10/Tirilikalika-Tirilikaliko.webp"},
    {"name": "Santoniooo",                "rarity": "ミシック",       "img": "2025/10/Santoniooo.webp"},
    {"name": "Los Matteos",               "rarity": "ミシック",       "img": "2025/10/Los-Matteos.webp"},
    {"name": "Los Sigma Boys",            "rarity": "ミシック",       "img": "2025/10/Los_Sigma_Boys.webp"},
    {"name": "Eaglucci Cocosucci",        "rarity": "ミシック",       "img": "2025/10/Eaglucci-Cocosucci.webp"},
    {"name": "Ti Ti Ti Sahur",            "rarity": "ミシック",       "img": "2025/10/Ti-Ti-Ti-Sahur.webp"},
    {"name": "Fishinis Santinis",         "rarity": "ミシック",       "img": "2025/10/Fishinis-Santinis.webp"},
    # ── Brainrot God ──
    {"name": "Cocofanto Elefanto",            "rarity": "Brainrot God", "img": "2025/10/Cocofanto-Elefanto.webp"},
    {"name": "Tob Tobi Tob",                  "rarity": "Brainrot God", "img": "2025/10/Tob-Tobi-Tob.webp"},
    {"name": "Tralalero Tralala",             "rarity": "Brainrot God", "img": "2025/10/Tralalero-Tralala.webp"},
    {"name": "Odin Din Din Dun",              "rarity": "Brainrot God", "img": "2025/10/Odin-Din-Din-Dun.webp"},
    {"name": "Akulini Cactusini",             "rarity": "Brainrot God", "img": "2025/10/Akulini-Cactusini.webp"},
    {"name": "Chachechicha",                  "rarity": "Brainrot God", "img": "2025/10/Chachechicha.webp"},
    {"name": "Espressona Signora",            "rarity": "Brainrot God", "img": "2025/10/Espressona-Signora.webp"},
    {"name": "La Vaca Saturno Saturnita",     "rarity": "Brainrot God", "img": "2025/10/La-Vaca-Saturno-Saturnita.webp"},
    {"name": "Centralucci Nuclearucci",       "rarity": "Brainrot God", "img": "2025/10/Centralucci-Nuclearucci.webp"},
    {"name": "Ecco Cavallo Virtuoso",         "rarity": "Brainrot God", "img": "2025/10/Ecco-Cavallo-Virtuoso.webp"},
    {"name": "Los Vaguitas Saturnitas",       "rarity": "Brainrot God", "img": "2025/10/Los-Vaguitas-Saturnitas.webp"},
    {"name": "Bulbito Bandito Traktorito",    "rarity": "Brainrot God", "img": "2025/10/Bulbito-Traktorito.webp"},
    {"name": "Bananananito Bandito",          "rarity": "Brainrot God", "img": "2025/10/Bananananito-Bandito.webp"},
    {"name": "Chillin Chili",                 "rarity": "Brainrot God", "img": "2025/10/Chillin-Chili.webp"},
    {"name": "Trippi Troppi Troppa Trippa",   "rarity": "Brainrot God", "img": "2025/10/Trippi-Troppi-Troppa-Trippa.webp"},
    {"name": "Brri Bicus Dicus",              "rarity": "Brainrot God", "img": "2025/10/Brri-Bicus-Dicus.webp"},
    {"name": "Cioccolatini Pancioncioni",     "rarity": "Brainrot God", "img": "2025/10/Cioccolatini-Pancioncioni.webp"},
    {"name": "Brr Es Teh Patipum",            "rarity": "Brainrot God", "img": "2025/10/Brr-Es-Teh-Patipum.webp"},
    {"name": "Torrtuginni Dragonfrutinni",    "rarity": "Brainrot God", "img": "2025/10/Torrtuginni-Dragonfrutinni.webp"},
    {"name": "Los Bros",                      "rarity": "Brainrot God", "img": "2025/10/Los-Bros.webp"},
    {"name": "Bim Bim Bim Sadim",             "rarity": "Brainrot God", "img": "2025/10/Bim-Bim-Bim-Sadim.webp"},
    {"name": "Bambini Tankini",               "rarity": "Brainrot God", "img": "2025/10/Bambini-Tankini.webp"},
    {"name": "Hotti Coccolli",                "rarity": "Brainrot God", "img": "2025/10/Hotti-Coccolli.webp"},
    {"name": "Jiqi Jiqi Shizhon",             "rarity": "Brainrot God", "img": "2025/10/Default2_7_9.webp"},
    {"name": "Los Crocodillitos",             "rarity": "Brainrot God", "img": "2025/10/Los-Crocodillitos.webp"},
    {"name": "Agarrini La Palini",            "rarity": "Brainrot God", "img": "2025/10/Default2_6_4.webp"},
    {"name": "Alessiooooooo",                 "rarity": "Brainrot God", "img": "2025/10/Alessiooooooo.webp"},
    {"name": "Dig Torto Dolf",                "rarity": "Brainrot God", "img": "2025/10/Dig_Torto_Dolf.webp"},
    {"name": "Karkerkar Kurkur",              "rarity": "Brainrot God", "img": "2025/10/Karkerkar-Kurkur.webp"},
    {"name": "Il Costruttore Di Pomodori",    "rarity": "Brainrot God", "img": "2025/10/Il-Costruttore-Di-Pomodori.webp"},
    {"name": "Piccionetta Machina",           "rarity": "Brainrot God", "img": "2025/10/Piccionetta-Machina.webp"},
    {"name": "Pipoqueira Motoqueira",         "rarity": "Brainrot God", "img": "2025/10/Pipoqueira-Motoqueira.webp"},
    {"name": "Il Piccione Musculone",         "rarity": "Brainrot God", "img": "2025/10/Il-Piccione-Musculone.webp"},
    {"name": "Job Job Job Sahur",             "rarity": "Brainrot God", "img": "2025/10/Job-Job-Job-Sahur.webp"},
    {"name": "Las Sis",                       "rarity": "Brainrot God", "img": "2025/10/Las-Sis.webp"},
    {"name": "La Matcha Assassino",           "rarity": "Brainrot God", "img": "2025/10/La-Matcha-Assassino.webp"},
    {"name": "Il Mastodontico Telepiedone",   "rarity": "Brainrot God", "img": "2025/10/Il-Mastodontico-Telepiedone.webp"},
    {"name": "Los Christmas Bros",            "rarity": "Brainrot God", "img": "2025/10/Los-Christmas-Bros.webp"},
    {"name": "Il Bisonte Giuppitere",         "rarity": "Brainrot God", "img": "2025/10/Il-Bisonte-Giuppitere.webp"},
    {"name": "Malame Amarale",                "rarity": "Brainrot God", "img": "2025/10/Malame-Amarale.webp"},
    {"name": "Linguicine Serpentine",         "rarity": "Brainrot God", "img": "2025/10/Linguicine_Serpentine.webp"},
    {"name": "Belugelo Beluga",               "rarity": "Brainrot God", "img": "2025/10/Belugelo-Beluga.webp"},
    {"name": "Bella Pancasita",               "rarity": "Brainrot God", "img": "2025/10/Bella-Pancasita.webp"},
    {"name": "Rhino Helicopterino",           "rarity": "Brainrot God", "img": "2026/03/Rhino-Helicopterino.webp"},
    {"name": "Missilpython Turbozzo",         "rarity": "Brainrot God", "img": "2025/10/Missilpython-Turbozzo.webp"},
    {"name": "Auglurini Arbuzini",            "rarity": "Brainrot God", "img": "2025/10/Auglurini-Arbuzini.webp"},
    # ── シークレット ──
    {"name": "Los Tralaleritos",              "rarity": "シークレット", "img": "2025/10/Los-Orcaleritos.webp"},
    {"name": "Los Tralaleritas",              "rarity": "シークレット", "img": "2025/10/Los-Tralaleritas.webp"},
    {"name": "Trenostruzzo Turbo",            "rarity": "シークレット", "img": "2025/10/Trenostruzzo-Turbo.webp"},
    {"name": "Kravilino Cekicino",            "rarity": "シークレット", "img": "2025/10/Kravilino-Cekicino.webp"},
    {"name": "Los Orcaleritos",               "rarity": "シークレット", "img": "2025/10/Los-Orcaleritos-1.webp"},
    {"name": "Las Agarrinis",                 "rarity": "シークレット", "img": "2025/10/Las-Agarrinis.webp"},
    {"name": "Los Couples",                   "rarity": "シークレット", "img": "2025/10/Los-Couples.webp"},
    {"name": "Piccione Macchina",             "rarity": "シークレット", "img": "2025/10/Piccione-Macchina.webp"},
    {"name": "Peeling Peely",                 "rarity": "シークレット", "img": "2025/10/Peeling-Peely.webp"},
    {"name": "Pakrahmatmamat",                "rarity": "シークレット", "img": "2025/10/Pakrah-matmamat.webp"},
    {"name": "Pakrahmatmamatcita",            "rarity": "シークレット", "img": "2025/10/Pakrahmatmamatcita.webp"},
    {"name": "Pickolini Malakini",            "rarity": "シークレット", "img": "2025/10/Pickolini-Malakini.webp"},
    {"name": "Los Job Jobsitos",              "rarity": "シークレット", "img": "2025/10/Los-Job-Jobsitos.webp"},
    {"name": "TrenoStruzzo Turbo 4000",       "rarity": "シークレット", "img": "2025/10/TrenoStruzzo-Turbo-4000.webp"},
    {"name": "Anpali Babel",                  "rarity": "シークレット", "img": "2025/10/Anpali-Babel.webp"},
    {"name": "Los Karkeritos",                "rarity": "シークレット", "img": "2025/10/Los-Karkeritos.webp"},
    {"name": "Orcalero Orcala",               "rarity": "シークレット", "img": "2025/10/Orcalero-Orcala.webp"},
    {"name": "Frogino Assassino",             "rarity": "シークレット", "img": "2025/10/Frogino-Assassino.webp"},
    {"name": "Ketchuru and Musturu",          "rarity": "シークレット", "img": "2025/10/Ketchuru-and-Musturu.webp"},
    {"name": "Pot Hotspot",                   "rarity": "シークレット", "img": "2025/10/Pot-Hotspot.webp"},
    {"name": "Tatoruman",                     "rarity": "シークレット", "img": "2025/10/Tatoruman.webp"},
    {"name": "Fragola La La La",              "rarity": "シークレット", "img": "2025/10/Fragola-La-La-La.webp"},
    {"name": "21",                            "rarity": "シークレット", "img": "2025/10/21.webp"},
    {"name": "Los Mobilis",                   "rarity": "シークレット", "img": "2025/10/Los-Mobilis.webp"},
    {"name": "Frogatto Piratto",              "rarity": "シークレット", "img": "2025/10/Frogatto-Piratto.webp"},
    {"name": "Garamaramadungdung",            "rarity": "シークレット", "img": "2025/10/Garamaramadungdung.webp"},
    {"name": "Papero Aspiratorino",           "rarity": "シークレット", "img": "2026/02/Papero-Aspiratorino.webp"},
    {"name": "Bun Din Din Dun",               "rarity": "シークレット", "img": "2025/10/Bun-Din-Din-Dun.webp"},
    {"name": "Pirulitoita Bicicleteira",      "rarity": "シークレット", "img": "2025/10/Pirulitoita-Bicicleteira.webp"},
    {"name": "Chachechi Sahur",               "rarity": "シークレット", "img": "2025/10/Chachechi-Sahur.webp"},
    {"name": "Il Sacro Cabrospaghetti",       "rarity": "シークレット", "img": "2025/10/Il-Sacro-Cabrospaghetti.webp"},
    {"name": "Owlito Tactito",                "rarity": "シークレット", "img": "2025/10/Owlito-Tactito.webp"},
    {"name": "La Grande Combinacion",         "rarity": "シークレット", "img": "2025/10/La-Grande-Combinacion.webp"},
    {"name": "Rosalero",                      "rarity": "シークレット", "img": "2026/02/Rosalero.webp"},
    {"name": "Clove Clove Clove Sahur",       "rarity": "シークレット", "img": "2025/10/Clove-Clove-Clove-Sahur.webp"},
    {"name": "Los Santacitos",                "rarity": "シークレット", "img": "2025/10/Los-Santacitos.webp"},
    {"name": "Paquito El Taquito",            "rarity": "シークレット", "img": "2025/10/Paquito-El-Taquito.webp"},
    {"name": "Cornball Sahur",                "rarity": "シークレット", "img": "2025/10/Cornball-Sahur.webp"},
    {"name": "Nuclearo Dinossauro",           "rarity": "シークレット", "img": "2025/10/Nuclearo-Dinossauro.webp"},
    {"name": "67",                            "rarity": "シークレット", "img": "2025/10/67.webp"},
    {"name": "Los Esok Sekolitos",            "rarity": "シークレット", "img": "2025/10/Los-Esok-Sekolitos.webp"},
    {"name": "Roobinha Acerolinha",           "rarity": "シークレット", "img": "2025/10/Roobinha-Acerolinha.webp"},
    {"name": "Coccoblade",                    "rarity": "シークレット", "img": "2025/10/Coccoblade.webp"},
    {"name": "Cacasito Satelito",             "rarity": "シークレット", "img": "2025/10/Cacasito-Satelito.webp"},
    {"name": "Dilly Pickle",                  "rarity": "シークレット", "img": "2025/10/Dilly_Pickle.webp"},
    {"name": "Chop Chop Chop Sahur",          "rarity": "シークレット", "img": "2025/10/Chop-Chop-Chop-Sahur.webp"},
    {"name": "Crocodila Bicicleteira",        "rarity": "シークレット", "img": "2025/10/Crocodila-Bicicleteira.webp"},
    {"name": "Pingus Kingus",                 "rarity": "シークレット", "img": "2025/10/Pingus-Kingus.webp"},
    {"name": "Ketupat Kepat Prekupat",        "rarity": "シークレット", "img": "2025/10/Ketupat-Kepat-Prekupat.webp"},
    {"name": "Lovey Lovey Bear",              "rarity": "シークレット", "img": "2026/02/Lovey-Lovey-Bear.webp"},
    {"name": "Coccobladina",                  "rarity": "シークレット", "img": "2025/10/Coccobladina.webp"},
    {"name": "Carrot Carrot Sahur",           "rarity": "シークレット", "img": "2025/10/Carrot-Carrot-Sahur.webp"},
    {"name": "Rang Reng Kelerang",            "rarity": "シークレット", "img": "2025/10/Rang-Reng-Kelerang.webp"},
    {"name": "Cobracadabra",                  "rarity": "シークレット", "img": "2026/04/Cobracadabra.webp"},
    {"name": "Los Garamadungcitos",           "rarity": "シークレット", "img": "2025/10/Los-Garamadungcitos.webp"},
    {"name": "Aquanaut",                      "rarity": "シークレット", "img": "2025/10/Aquanaut.webp"},
    {"name": "Re Delle Carte",                "rarity": "シークレット", "img": "2026/04/Re-Delle-Carte.webp"},
    {"name": "Tung Ballerina Sahur",          "rarity": "シークレット", "img": "2025/10/Tung-Ballerina-Sahur.webp"},
    {"name": "Baskuru And Egguru",            "rarity": "シークレット", "img": "2025/10/Baskuru-And-Egguru.webp"},
    {"name": "Pitiata Baem",                  "rarity": "シークレット", "img": "2025/10/Pitiata-Baem.webp"},
    {"name": "Los 67",                        "rarity": "シークレット", "img": "2025/10/Los-67.webp"},
    {"name": "Tralalero Kingala",             "rarity": "シークレット", "img": "2026/05/Tralalero-Kingala.webp"},
    {"name": "Penguini Armorini Kingini",     "rarity": "シークレット", "img": "2025/10/Penguini-Armorini-Kingini.webp"},
    {"name": "Chimpanzini Kingini",           "rarity": "シークレット", "img": "2025/10/Chimpanzini-Kingini.webp"},
    {"name": "Tictac Tictac Sahur",           "rarity": "シークレット", "img": "2025/10/Tictac-Tictac-Sahur.webp"},
    {"name": "La Royals",                     "rarity": "シークレット", "img": "2026/02/La-Royals.webp"},
    {"name": "Alligarto Alligarto",           "rarity": "シークレット", "img": "2025/10/Alligarto-Alligarto.webp"},
    {"name": "Cannelloni Dragoni",            "rarity": "シークレット", "img": "2025/10/Cannelloni-Dragoni.webp"},
    {"name": "Vulturino Skeletono",           "rarity": "シークレット", "img": "2025/10/Vulturino-Skeletono.webp"},
    {"name": "Chocone Dragone",               "rarity": "シークレット", "img": "2026/02/Chocone-Dragone.webp"},
    {"name": "Koinobori Shogunelli",          "rarity": "シークレット", "img": "2026/05/Koinobori-Shogunelli.webp"},
    {"name": "Scarletbyte",                   "rarity": "シークレット", "img": "2026/05/Scarletbyte.webp"},
    {"name": "Capanna Distruttore",           "rarity": "シークレット", "img": "2026/04/Capanna-Distruttore.webp"},
    {"name": "Trifoglita Bicicleta",          "rarity": "シークレット", "img": "2026/03/Trifoglita-Bicicleta.webp"},
    {"name": "Lovelypat",                     "rarity": "シークレット", "img": "2026/02/Lovelypat.webp"},
    {"name": "Fourteen",                      "rarity": "シークレット", "img": "2026/02/Fourteen.webp"},
    # ── エターナル ──
    {"name": "Gigalitraktos Spidorobos",  "rarity": "エターナル",   "img": "2025/10/Gigalitraktos-Spidorobos.webp"},
    {"name": "Burguro dan Fryuro",        "rarity": "エターナル",   "img": "2025/10/Burguro-dan-Fryuro.webp"},
    {"name": "Bearini Plammini Guardini", "rarity": "エターナル",   "img": "2025/10/Bearini-Plammini-Guardini.webp"},
    {"name": "Tiramisubmarini",           "rarity": "エターナル",   "img": "2025/10/Tiramisubmarini.webp"},
    {"name": "Tralaledon",                "rarity": "エターナル",   "img": "2026/04/Tralaledon.webp"},
    {"name": "Garbagzilla",               "rarity": "エターナル",   "img": "2025/10/Garbagzilla.webp"},
    {"name": "Fishini Mechinini",         "rarity": "エターナル",   "img": "2025/10/Fishini-Mechinini.webp"},
    {"name": "Cannone Maledettone",       "rarity": "エターナル",   "img": "2025/10/Cannone-Maledettone.webp"},
    {"name": "La Superior Combinacion",   "rarity": "エターナル",   "img": "2026/04/La-Superior-Combinacion.webp"},
    {"name": "Il Maledettones",           "rarity": "エターナル",   "img": "2026/05/Il-Maledettones.webp"},
    {"name": "DiggoBlock",                "rarity": "エターナル",   "img": "2026/05/tile_8_9.webp"},
    # ── GOAT ──
    {"name": "SKIBIDI TOILET",            "rarity": "GOAT",         "img": "2025/10/SKIBIDI-TOILET.webp"},
    # ── 新キャラ（シークレット） ──
    {"name": "Dul Dul Dul",               "rarity": "シークレット", "img": "2025/10/Default2_1_5.webp"},
    {"name": "Lucky Rod",                 "rarity": "シークレット", "img": "2025/10/Default_9_5.webp"},
    {"name": "Guardilope Antilope",       "rarity": "シークレット", "img": "2026/05/Default3_9_5.webp"},
    {"name": "Mistifly",                  "rarity": "シークレット", "img": "2026/05/Default3_9_4.webp"},
    {"name": "Mushzilla Fungzilla",       "rarity": "シークレット", "img": "2026/05/Default3_9_3.webp"},
    {"name": "Flowerfang Squirreli",      "rarity": "シークレット", "img": "2026/05/Default3_9_2.webp"},
    {"name": "Croakolini Spellini",       "rarity": "シークレット", "img": "2026/05/Default3_9_1.webp"},
]


def make_placeholder(size=80) -> Image.Image:
    img = Image.new('RGB', (size, size), '#1a1a2e')
    d = ImageDraw.Draw(img)
    d.text((size//2, size//2), '?', fill='#444444', anchor='mm')
    return img


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


class FortniteBot:

    def __init__(self):
        self.running     = False
        self.buying      = False
        self.buying_char: str | None = None
        self.buy_key     = 'e'
        self.selected: set[str] = set()
        self.log_q: queue.Queue = queue.Queue()
        self._photos: dict[str, ImageTk.PhotoImage] = {}
        self._cells:  dict[str, tk.Frame] = {}
        self._rarity_seps: dict[str, tk.Widget] = {}
        self._preview_photo = None
        self._cps_var    = None
        self._search_var: tk.StringVar | None = None
        self._rarity_filter: set[str] = set()   # 空=全表示
        self._ai_vision_on  = False
        self._log_visible   = True
        self._rarity_btn_labels: dict[str, tk.Label] = {}

        IMG_DIR.mkdir(exist_ok=True)
        _load_custom_fonts()  # Share Tech Mono / Orbitron を登録（Windows のみ）

        self.root = tk.Tk()
        self.root.title('NEURAL LINK // INTERFACE_V.2.0')
        self.root.configure(bg=BG)
        self.root.resizable(True, True)

        self._build_ui()
        self._load_config()
        self._key_label.configure(text=f'[ {self.buy_key.upper()} ]')
        self._refresh_selection_ui()  # 保存済み選択をハイライト反映
        self.root.after(150, self._poll_log)
        self._refresh_windows()
        self._log('[SYSTEM] NEURAL LINK v2.0 起動完了')
        self._log(f'[TESS] {"OK" if HAS_TESS else "未検出 — pip install pytesseract 後 Tesseract本体も必要"}')
        threading.Thread(target=self._download_all_images, daemon=True).start()
        self.root.mainloop()

    def _build_ui(self):
        self.root.minsize(1060, 700)
        # ── タイトルバー ──
        bar = tk.Frame(self.root, bg='#06060f')
        bar.pack(fill='x')
        tk.Label(bar, text='NEURAL LINK', font=FONT_TITLE, fg=CYAN, bg='#06060f').pack(side='left', padx=(14, 0), pady=6)
        tk.Label(bar, text=' // BRAINROT BOT', font=('Consolas', 10), fg='#334455', bg='#06060f').pack(side='left', padx=4)
        for txt, col, cmd in [('✕', '#1a0a0a', self.root.destroy),
                               ('─', '#0a0a1a', self.root.iconify)]:
            lbl = tk.Label(bar, text=txt, font=FONT_UI_SM, fg='#556677', bg=col,
                           width=4, cursor='hand2', pady=6)
            lbl.pack(side='right', padx=1)
            lbl.bind('<Button-1>', lambda _, c=cmd: c())
        # シングルライン
        tk.Frame(self.root, bg=CYAN, height=1).pack(fill='x')

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill='both', expand=True)
        self._build_left(body)
        tk.Frame(body, bg='#111122', width=2).pack(side='left', fill='y')
        self._build_right(body)

        sb = tk.Frame(self.root, bg='#03030a', height=22)
        sb.pack(fill='x', side='bottom')
        self._status_var = tk.StringVar(value='SYSTEM IDLE')
        tk.Label(sb, textvariable=self._status_var, font=FONT_SMALL,
                 fg='#336633', bg='#03030a').pack(side='left', padx=10, pady=2)
        tk.Label(sb, text='BRAINROT AUTO-BUY v2.0', font=FONT_SMALL,
                 fg='#111133', bg='#03030a').pack(side='right', padx=10)

    def _build_left(self, parent):
        left = tk.Frame(parent, bg=BG, width=440)
        left.pack(side='left', fill='both')
        left.pack_propagate(False)

        tk.Frame(left, bg='#0d0d1d', height=4).pack(fill='x')

        # ── コントロール枠 ──
        ctrl = tk.Frame(left, bg=BG2)
        ctrl.pack(fill='x', padx=8, pady=(6, 2))

        # ウィンドウ選択
        r0 = tk.Frame(ctrl, bg=BG2); r0.pack(fill='x', pady=2)
        tk.Label(r0, text='ウィンドウ', font=FONT_UI_SM, fg='#8888aa', bg=BG2,
                 width=9, anchor='w').pack(side='left')
        self._window_var = tk.StringVar()
        self._window_cb = ttk.Combobox(r0, textvariable=self._window_var,
                                        state='readonly', font=FONT_SMALL)
        self._window_cb.pack(side='left', fill='x', expand=True, padx=(4, 2))
        tk.Button(r0, text='R', font=FONT_BOLD, fg=CYAN, bg='#111122',
                  bd=0, cursor='hand2', padx=6, pady=1,
                  command=self._refresh_windows).pack(side='left')

        # 購入キー + キャラ検索（横並び）
        r1 = tk.Frame(ctrl, bg=BG2); r1.pack(fill='x', pady=2)
        kf = tk.Frame(r1, bg=BG2); kf.pack(side='left')
        tk.Label(kf, text='取得キー', font=FONT_UI_SM, fg='#8888aa', bg=BG2).pack(side='left')
        self._key_label = tk.Label(kf, text=f'[ {self.buy_key.upper()} ]',
                                    font=FONT_BOLD, fg=YELLOW, bg='#181800',
                                    cursor='hand2', padx=6, pady=2,
                                    relief='solid', bd=1)
        self._key_label.pack(side='left', padx=4)
        self._key_label.bind('<Button-1>', lambda _: self._start_key_capture())
        tk.Button(kf, text='TEST', font=FONT_SMALL, fg='#000', bg=GREEN,
                  bd=0, cursor='hand2', padx=6, pady=2, relief='flat',
                  command=lambda: threading.Thread(
                      target=self._press_game_key, args=(self.buy_key,), daemon=True
                  ).start()).pack(side='left', padx=(2, 10))
        tk.Label(r1, text='検索', font=FONT_UI_SM, fg='#8888aa', bg=BG2).pack(side='left')
        self._search_var = tk.StringVar()
        se = tk.Entry(r1, textvariable=self._search_var, font=FONT_SMALL,
                      fg=CYAN, bg='#0a0a1e', bd=0, insertbackground=CYAN,
                      relief='solid', highlightthickness=1,
                      highlightbackground='#333355', highlightcolor=CYAN)
        se.pack(side='left', fill='x', expand=True, padx=(4, 0))
        self._search_var.trace_add('write', lambda *_: self._apply_char_filter())

        # 連打速度
        r2 = tk.Frame(ctrl, bg=BG2); r2.pack(fill='x', pady=2)
        tk.Label(r2, text='SPEED', font=FONT_UI_SM, fg='#8888aa', bg=BG2,
                 width=9, anchor='w').pack(side='left')
        self._cps_var = tk.IntVar(value=10)
        tk.Scale(r2, from_=1, to=20, orient='horizontal', variable=self._cps_var,
                 bg=BG2, fg=ORANGE, troughcolor='#1a1a2a', highlightthickness=0,
                 font=FONT_SMALL, showvalue=False).pack(side='left', fill='x', expand=True, padx=4)
        self._cps_lbl = tk.Label(r2, font=FONT_BOLD, fg=ORANGE, bg=BG2, width=8, anchor='w')
        self._cps_lbl.pack(side='left')
        self._cps_var.trace_add('write', self._update_cps_label)
        self._update_cps_label()

        # ── レアリティフィルター ──
        rf = tk.Frame(left, bg=BG); rf.pack(fill='x', padx=8, pady=(4, 2))
        tk.Label(rf, text='レアリティ選択:', font=FONT_UI_SM, fg='#8888aa', bg=BG).pack(side='left')
        rbf = tk.Frame(left, bg=BG); rbf.pack(fill='x', padx=8, pady=(0, 4))
        for rar, col, abbr in [
            ('アンコモン',     '#1eff00', '緑'),
            ('レア',           '#4499ff', '青'),
            ('エピック',       '#cc77ff', '紫'),
            ('レジェンダリー', '#ff9933', '橙'),
            ('ミシック',       '#ff5555', '赤'),
            ('Brainrot God',   '#ddcc00', '虹'),
            ('シークレット',   '#aaaaaa', '灰'),
            ('エターナル',     '#00eeff', '水'),
            ('GOAT',           '#ff55aa', 'GT'),
        ]:
            lbl = tk.Label(rbf, text=abbr, font=('Consolas', 8),
                           fg=col, bg='#111122', padx=6, pady=3,
                           cursor='hand2', relief='flat',
                           highlightthickness=1, highlightbackground='#222233')
            lbl.pack(side='left', padx=2)
            lbl.bind('<Button-1>', lambda _, r=rar: self._toggle_rarity_filter(r))
            self._rarity_btn_labels[rar] = lbl

        # ── スキャンボタン ──
        self._scan_btn = tk.Button(left, text='>> START SCAN <<',
                                    font=FONT_TITLE, fg=BG, bg=CYAN,
                                    relief='flat', cursor='hand2', pady=10,
                                    activebackground='#00ccaa', activeforeground=BG,
                                    command=self._toggle_scan)
        self._scan_btn.pack(fill='x', padx=8, pady=4)

        # ── アクションボタン行 ──
        abf = tk.Frame(left, bg=BG); abf.pack(fill='x', padx=8, pady=(0, 4))
        _btn_kw = dict(font=FONT_UI_SM, fg='#aabbcc', bg='#111122',
                       bd=0, padx=10, pady=4, cursor='hand2', relief='flat',
                       activebackground='#1a1a33', activeforeground=CYAN)
        self._ai_btn = tk.Button(abf, text='AI視点', command=self._toggle_ai_vision, **_btn_kw)
        self._ai_btn.pack(side='left', padx=(0, 1))
        tk.Button(abf, text='ログ消去', command=self._clear_log, **_btn_kw).pack(side='left', padx=1)
        self._log_toggle_btn = tk.Button(abf, text='ログ非表示', command=self._toggle_log_panel, **_btn_kw)
        self._log_toggle_btn.pack(side='left', padx=1)

        # ── 選択ステータス + 全選択/解除 ──
        sf = tk.Frame(left, bg=BG); sf.pack(fill='x', padx=8, pady=(0, 4))
        tk.Label(sf, text='選択中:', font=FONT_UI_SM, fg='#556677', bg=BG).pack(side='left', padx=(2, 2), pady=2)
        self._sel_label = tk.Label(sf, text='0体', font=FONT_UI_BD, fg=CYAN, bg=BG)
        self._sel_label.pack(side='left')
        _s_kw = dict(font=FONT_UI_SM, fg='#667788', bg='#0d0d1e',
                     bd=0, padx=8, pady=2, cursor='hand2', relief='flat',
                     activebackground='#1a1a33', activeforeground=CYAN)
        tk.Button(sf, text='全選択', command=self._quick_select_visible, **_s_kw).pack(side='right', padx=2)
        tk.Button(sf, text='全解除', command=lambda: self._quick_select(None), **_s_kw).pack(side='right', padx=2)

        # ── キャラ一覧ヘッダー ──
        hf = tk.Frame(left, bg='#090916'); hf.pack(fill='x', padx=8)
        tk.Label(hf, text='CHARACTER LIST', font=FONT_BOLD,
                 fg=CYAN, bg='#090916').pack(side='left', padx=4, pady=4)
        tk.Button(hf, text='RESET FILTERS', font=FONT_SMALL, fg='#fff', bg='#222233',
                  bd=0, padx=6, pady=2, cursor='hand2', relief='flat',
                  command=self._reset_filters).pack(side='right', padx=4)

        # ── キャラグリッド ──
        wrapper = tk.Frame(left, bg=BG)
        wrapper.pack(fill='both', expand=True, padx=8, pady=(2, 6))
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
        right = tk.Frame(parent, bg=BG2)
        right.pack(side='right', fill='both', expand=True)

        # ── ヘッダー ──
        hdr = tk.Frame(right, bg='#0a0a1a')
        hdr.pack(fill='x')
        tk.Label(hdr, text='REC', font=FONT_SMALL, fg=RED,
                 bg='#0a0a1a').pack(side='left', padx=(8, 2), pady=5)
        tk.Label(hdr, text='●', font=FONT_SMALL, fg=RED,
                 bg='#0a0a1a').pack(side='left')
        tk.Label(hdr, text=' LIVE FEED // OCR_PROCESSOR', font=FONT_SMALL,
                 fg='#ff3366', bg='#0a0a1a').pack(side='left', padx=4)
        tk.Frame(right, bg='#1a1a2a', height=1).pack(fill='x')

        # ── プレビューエリア（コーナーブラケット付き） ──
        pf = tk.Frame(right, bg='#04040e', highlightthickness=1,
                      highlightbackground='#1a1a3a')
        pf.pack(fill='both', expand=True, padx=8, pady=8)
        self._preview_lbl = tk.Label(pf, bg='#04040e',
                                      text='[ AWAITING SIGNAL ]',
                                      font=FONT_MONO, fg='#550011')
        self._preview_lbl.pack(fill='both', expand=True)


        # ── ログエリア（トグル可能） ──
        tk.Frame(right, bg='#1a1a2a', height=1).pack(fill='x', padx=8)
        self._log_frame = tk.Frame(right, bg=BG2)
        self._log_frame.pack(fill='x', padx=8, pady=(4, 6))

        log_hdr = tk.Frame(self._log_frame, bg=BG2)
        log_hdr.pack(fill='x')
        tk.Label(log_hdr, text='LOG OUTPUT', font=FONT_SMALL,
                 fg=CYAN2, bg=BG2).pack(side='left')

        lf = tk.Frame(self._log_frame, bg=BG2)
        lf.pack(fill='x', pady=(2, 0))
        self._log_text = tk.Text(lf, height=10, font=FONT_SMALL,
                                  fg='#00ee77', bg='#04040e', bd=0,
                                  state='disabled', wrap='word',
                                  padx=4, pady=4)
        lsb = ttk.Scrollbar(lf, orient='vertical', command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=lsb.set)
        self._log_text.pack(side='left', fill='x', expand=True)
        lsb.pack(side='right', fill='y')

    def _build_char_grid(self):
        COLS   = 4
        CW, CH = 138, 130   # cell width / height
        IW, IH = 122, 86    # image width / height

        cur_rarity = None
        col = 0
        grid_row = 0

        for char in CHARACTERS:
            name   = char['name']
            rarity = char['rarity']
            color  = RARITY_COLOR.get(rarity, WHITE)

            if rarity != cur_rarity:
                cur_rarity = rarity
                col = 0
                # レアリティ区切りライン
                sep = tk.Frame(self._grid_inner, bg=BG)
                sep.grid(row=grid_row, column=0, columnspan=COLS,
                         sticky='ew', padx=4, pady=(12, 3))
                tk.Frame(sep, bg=color, height=1).pack(side='left', fill='x', expand=True)
                tk.Label(sep, text=f'  {rarity}  ', font=FONT_SMALL,
                         fg=color, bg=BG).pack(side='left')
                tk.Frame(sep, bg=color, height=1).pack(side='left', fill='x', expand=True)
                self._rarity_seps[rarity] = sep
                grid_row += 1

            cell = tk.Frame(self._grid_inner, bg='#0e0e1c',
                            highlightthickness=2, highlightbackground=GRAY,
                            cursor='hand2', width=CW, height=CH)
            cell.grid(row=grid_row, column=col, padx=3, pady=3)
            cell.grid_propagate(False)

            img_lbl = tk.Label(cell, bg='#0e0e1c', cursor='hand2')
            img_lbl.place(x=(CW-IW)//2, y=4, width=IW, height=IH)
            ph = ImageTk.PhotoImage(make_placeholder(IH))
            img_lbl.configure(image=ph)
            img_lbl.image = ph

            name_lbl = tk.Label(cell, text=name, font=FONT_SMALL,
                                 fg=WHITE, bg='#0e0e1c',
                                 wraplength=CW-6, justify='center')
            name_lbl.place(x=0, y=IH+6, width=CW, height=26)

            rar_lbl = tk.Label(cell, text=rarity, font=('Consolas', 7, 'bold'),
                                fg=color, bg='#08080f', justify='center')
            rar_lbl.place(x=0, y=CH-16, width=CW, height=15)

            for w in [cell, img_lbl, name_lbl]:
                w.bind('<Button-1>', lambda _, n=name, c=cell: self._toggle_select(n, c))

            self._cells[name] = cell
            col += 1
            if col >= COLS:
                col = 0
                grid_row += 1

        for name in self.selected:
            if name in self._cells:
                self._cells[name].configure(highlightbackground=CYAN, highlightthickness=3)

    def _quick_select(self, rarity: str | None):
        if rarity is None:
            self.selected.clear()
        else:
            for c in CHARACTERS:
                if c['rarity'] == rarity:
                    self.selected.add(c['name'])
        self._refresh_selection_ui()
        self._save_config()

    def _toggle_rarity_filter(self, rarity: str):
        if rarity in self._rarity_filter:
            self._rarity_filter.discard(rarity)
            lbl = self._rarity_btn_labels.get(rarity)
            if lbl:
                col = RARITY_COLOR.get(rarity, WHITE)
                lbl.configure(fg=col, bg='#111122',
                              highlightbackground='#222233')
        else:
            self._rarity_filter.add(rarity)
            lbl = self._rarity_btn_labels.get(rarity)
            if lbl:
                col = RARITY_COLOR.get(rarity, WHITE)
                lbl.configure(fg='#000000', bg=col,
                              highlightbackground=col)
        self._apply_char_filter()

    def _apply_char_filter(self):
        search = (self._search_var.get().lower()
                  if self._search_var else '').strip()
        for char in CHARACTERS:
            name   = char['name']
            rarity = char['rarity']
            cell   = self._cells.get(name)
            if cell is None:
                continue
            if self._rarity_filter and rarity not in self._rarity_filter:
                cell.grid_remove()
                continue
            if search and search not in name.lower():
                cell.grid_remove()
                continue
            cell.grid()
        for rarity, sep in self._rarity_seps.items():
            if self._rarity_filter and rarity not in self._rarity_filter:
                sep.grid_remove()
            else:
                sep.grid()

    def _toggle_ai_vision(self):
        self._ai_vision_on = not self._ai_vision_on
        if self._ai_vision_on:
            self._ai_btn.configure(text='AI視点 ●', fg=CYAN, bg='#001a1a')
        else:
            self._ai_btn.configure(text='AI視点', fg='#aabbcc', bg='#111122')

    def _toggle_log_panel(self):
        self._log_visible = not self._log_visible
        if self._log_visible:
            self._log_frame.pack(fill='x', padx=8, pady=(4, 6))
            self._log_toggle_btn.configure(text='ログ非表示')
        else:
            self._log_frame.pack_forget()
            self._log_toggle_btn.configure(text='ログ表示')

    def _quick_select_visible(self):
        for char in CHARACTERS:
            name = char['name']
            cell = self._cells.get(name)
            if cell and cell.winfo_ismapped():
                self.selected.add(name)
        self._refresh_selection_ui()
        self._save_config()

    def _reset_filters(self):
        self._rarity_filter.clear()
        if self._search_var:
            self._search_var.set('')
        for rar, lbl in self._rarity_btn_labels.items():
            col = RARITY_COLOR.get(rar, WHITE)
            lbl.configure(fg='#000', bg=col)
        self._apply_char_filter()

    def _refresh_selection_ui(self):
        for name, cell in self._cells.items():
            if name in self.selected:
                cell.configure(highlightbackground=CYAN, highlightthickness=3)
            else:
                cell.configure(highlightbackground=GRAY, highlightthickness=2)
        count = len(self.selected)
        self._sel_label.configure(text=f'{count}体' if count > 0 else '0体')

    def _toggle_select(self, name: str, cell: tk.Frame):
        if name in self.selected:
            self.selected.discard(name)
            cell.configure(highlightbackground=GRAY, highlightthickness=2)
        else:
            self.selected.add(name)
            cell.configure(highlightbackground=CYAN, highlightthickness=3)
        self._refresh_selection_ui()
        self._save_config()

    def _download_all_images(self):
        self._log(f'[IMG] {len(CHARACTERS)}体の画像をダウンロード中...')
        FALLBACK_MONTHS = [
            '2025/10', '2026/02', '2026/03', '2026/04', '2026/05',
            '2025/11', '2025/12', '2026/01',
        ]
        ok = 0
        for char in CHARACTERS:
            name  = char['name']
            img   = char['img']
            fname = img.split('/')[-1]
            path  = IMG_DIR / fname
            if path.exists():
                self._load_image_to_cell(name, path)
                ok += 1
                continue
            downloaded = False
            # 指定パスを最初に試す、失敗したら全月を試す
            candidates = [img] + [f'{m}/{fname}' for m in FALLBACK_MONTHS
                                   if f'{m}/{fname}' != img]
            for candidate in candidates:
                try:
                    url = IMG_BASE + candidate
                    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=8) as r:
                        data = r.read()
                    if len(data) > 1000:
                        path.write_bytes(data)
                        self._load_image_to_cell(name, path)
                        ok += 1
                        downloaded = True
                        break
                except Exception:
                    continue
            if not downloaded:
                time.sleep(0.02)
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
                if not cell:
                    return
                for w in cell.winfo_children():
                    if isinstance(w, tk.Label) and w.winfo_y() < 84:
                        w.configure(image=p)
                        w.image = p
                        break

            self.root.after(0, _update)
        except Exception:
            pass

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

    def _toggle_scan(self):
        if self.running:
            self.running = False
            self.buying  = False
            self.buying_char = None
            self._scan_btn.configure(text='>> START SCAN <<', bg=CYAN,
                                      activebackground='#00ccaa')
            self._set_status('SCAN STOPPED')
        else:
            if not self.selected:
                self._log('[WARN] キャラを選択してからスキャンしてください')
                return
            self.running = True
            self._scan_btn.configure(text='|| STOP SCAN ||', bg=PINK,
                                      activebackground='#cc0088')
            self._set_status('SCANNING...')
            threading.Thread(target=self._click_loop, daemon=True).start()
            threading.Thread(target=self._scan_loop,  daemon=True).start()
            threading.Thread(target=self._afk_loop,   daemon=True).start()

    def _get_fortnite_hwnd(self):
        if not HAS_WIN32:
            return None
        name = self._window_var.get()
        hwnd = win32gui.FindWindow(None, name)
        if not hwnd:
            found = []
            def _cb(h, _):
                t = win32gui.GetWindowText(h)
                if t and name.lower() in t.lower():
                    found.append(h)
            win32gui.EnumWindows(_cb, None)
            hwnd = found[0] if found else None
        return hwnd

    def _focus_fortnite(self, hwnd):
        try:
            import win32process
            fg  = win32gui.GetForegroundWindow()
            fg_tid  = win32process.GetWindowThreadProcessId(fg)[0]
            tgt_tid = win32process.GetWindowThreadProcessId(hwnd)[0]
            win32process.AttachThreadInput(fg_tid, tgt_tid, True)
            win32gui.ShowWindow(hwnd, 9)
            win32gui.SetForegroundWindow(hwnd)
            win32process.AttachThreadInput(fg_tid, tgt_tid, False)
        except Exception:
            try:
                win32gui.ShowWindow(hwnd, 9)
                win32gui.SetForegroundWindow(hwnd)
            except Exception:
                pass
        time.sleep(0.15)

    def _press_game_key(self, key: str):
        """フォーカスを奪わずPostMessageで送信、失敗時のみフォーカスして送信"""
        hwnd = self._get_fortnite_hwnd()
        sent = False
        if hwnd and HAS_WIN32:
            vk = _vk_code(key)
            if vk:
                try:
                    win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, vk, 0)
                    time.sleep(0.05)
                    win32api.PostMessage(hwnd, win32con.WM_KEYUP, vk,
                                        (1 << 31) | (1 << 30))
                    sent = True
                except Exception:
                    pass
        if not sent:
            try:
                pyautogui.keyDown(key)
                time.sleep(0.05)
                pyautogui.keyUp(key)
            except Exception:
                pass

    def _click_loop(self):
        was_buying = False
        while self.running:
            if self.buying:
                # 購入開始時のみ1回だけフォーカス
                if not was_buying:
                    hwnd = self._get_fortnite_hwnd()
                    if hwnd and HAS_WIN32:
                        self._focus_fortnite(hwnd)
                    was_buying = True
                self._press_game_key(self.buy_key)
                cps = self._cps_var.get() if self._cps_var else 10
                time.sleep(1.0 / max(1, cps))
            else:
                was_buying = False
                time.sleep(0.05)

    def _afk_loop(self):
        last = time.time()
        while self.running:
            time.sleep(1)
            if time.time() - last >= 55:
                last = time.time()
                if self.buying:
                    continue
                self._log('[AFK] 動作防止: 前進→後退')
                hwnd = self._get_fortnite_hwnd()
                if hwnd and HAS_WIN32:
                    self._focus_fortnite(hwnd)
                try:
                    pyautogui.keyDown('w')
                    time.sleep(0.4)
                    pyautogui.keyUp('w')
                    time.sleep(0.15)
                    pyautogui.keyDown('s')
                    time.sleep(0.4)
                    pyautogui.keyUp('s')
                except Exception:
                    pass

    def _scan_loop(self):
        while self.running:
            try:
                self._do_scan()
            except Exception as e:
                self._log(f'[ERROR] {e}')
            time.sleep(0.4)

    def _do_scan(self):
        img = self._capture_screen()
        if img is None:
            return
        self.root.after(0, lambda i=img: self._update_preview(i))
        if not HAS_TESS:
            return
        text  = self._run_ocr(img)
        found = self._parse_chars(text)
        self._log(f'[SCAN] {", ".join(found[:3]) if found else "未検出"}')
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

    def _capture_screen(self):
        try:
            x, y, w, h = 0, 0, 1920, 1080
            hwnd = self._get_fortnite_hwnd()
            if hwnd:
                r = win32gui.GetWindowRect(hwnd)
                x, y, w, h = r[0], r[1], r[2]-r[0], r[3]-r[1]
            with mss.mss() as sct:
                shot = sct.grab({'left': x, 'top': y, 'width': max(w,1), 'height': max(h,1)})
            return Image.frombytes('RGB', shot.size, shot.bgra, 'raw', 'BGRX')
        except Exception as e:
            self._log(f'[ERROR] キャプチャ失敗: {e}')
            return None

    def _run_ocr(self, img: Image.Image) -> str:
        w, h = img.width, img.height
        x1, x2 = int(w * 0.10), int(w * 0.90)  # 横を広げた
        y1, y2 = int(h * 0.10), int(h * 0.65)  # 縦も広げた
        crop = img.crop((x1, y1, x2, y2))
        # 2倍に拡大してOCR精度向上
        crop = crop.resize((crop.width * 2, crop.height * 2), Image.LANCZOS)
        gray = crop.convert('L')
        enhanced = ImageEnhance.Contrast(gray).enhance(3.0)
        result = pytesseract.image_to_string(
            enhanced, config='--psm 11 --oem 3 -l eng')
        # デバッグ: OCRが読んだ生テキストをログに出す
        lines = [l.strip() for l in result.splitlines() if l.strip()]
        if lines:
            self._log(f'[OCR] {" | ".join(lines[:4])}')
        return result

    def _parse_chars(self, text: str) -> list[str]:
        raw_lines = [l.strip() for l in text.splitlines() if len(l.strip()) >= 3]
        if not raw_lines:
            return []

        # レアリティ・属性・UI文字の行を除外し、キャラ名候補だけ残す
        candidate_lines = []
        for line in raw_lines:
            lw = line.lower().strip()
            # $記号や数字だけの行はスキップ
            if lw.startswith('$') or lw.replace('.','').replace(',','').replace('/','').isdigit():
                continue
            # 短すぎる行はスキップ
            if len(lw) < 3:
                continue
            # スキップワードを含む行はスキップ
            words = set(lw.split())
            if words & OCR_SKIP_WORDS:
                continue
            # レアリティ名そのものの行はスキップ（日本語も）
            rarity_names = {'アンコモン','レア','エピック','レジェンダリー','ミシック',
                            'シークレット','エターナル','goat','brainrot god'}
            if lw in rarity_names or any(r in lw for r in rarity_names):
                continue
            candidate_lines.append(lw)

        if not candidate_lines:
            return []

        scored = []
        for c in CHARACTERS:
            name_l = c['name'].lower()
            name_len = len(name_l)
            best = 0.0
            for line in candidate_lines:
                line_len = len(line)
                if not (name_len * 0.6 <= line_len <= name_len * 1.8):
                    continue
                s = difflib.SequenceMatcher(None, name_l, line).ratio()
                if s > best:
                    best = s
            if best >= 0.82:
                scored.append((best, c['name']))

        if not scored:
            return []

        scored.sort(reverse=True)
        top = scored[0][0]
        return [name for score, name in scored if score >= top * 0.98 and score >= 0.82]

    def _update_cps_label(self, *_):
        v = self._cps_var.get() if self._cps_var else 10
        self._cps_lbl.configure(text=f'{v} 回/秒')

    def _start_key_capture(self):
        self._key_label.configure(text='[ ? ]  ← キーを押して', fg=PINK)
        self._key_label.bind('<KeyPress>', self._on_key_captured)
        self._key_label.focus_set()

    def _on_key_captured(self, event):
        key = event.keysym.lower()
        if key in ('escape', 'return', 'tab'):
            self._key_label.configure(text=f'[ {self.buy_key.upper()} ]', fg=YELLOW)
            self._key_label.unbind('<KeyPress>')
            return
        self.buy_key = key
        self._key_label.configure(text=f'[ {key.upper()} ]', fg=YELLOW)
        self._key_label.unbind('<KeyPress>')
        self._log(f'[KEY] 購入キー設定: {key.upper()}')
        self._save_config()

    def _update_preview(self, img: Image.Image):
        try:
            pw = self._preview_lbl.winfo_width()
            if pw < 50:
                pw = 400
            ph = min(int(img.height * pw / img.width), 340)

            if self._ai_vision_on:
                # AI視点: OCR処理と同じ白黒＋コントラスト強調
                iw, ih = img.width, img.height
                x1, x2 = int(iw * 0.10), int(iw * 0.90)
                y1, y2 = int(ih * 0.10), int(ih * 0.65)
                crop = img.crop((x1, y1, x2, y2))
                crop = crop.resize((crop.width * 2, crop.height * 2), Image.LANCZOS)
                gray = crop.convert('L')
                enhanced = ImageEnhance.Contrast(gray).enhance(3.0)
                preview = enhanced.convert('RGB').resize((pw, ph), Image.LANCZOS)
                d = ImageDraw.Draw(preview)
                d.rectangle([2, 2, pw-3, ph-3], outline='#00ffcc', width=1)
                d.text((6, 6), 'AI VISION // OCR VIEW', fill='#00ffcc')
            else:
                preview = img.resize((pw, ph), Image.LANCZOS).convert('RGB')
                d = ImageDraw.Draw(preview)
                rx1 = int(pw * 0.10); rx2 = int(pw * 0.90)
                ry1 = int(ph * 0.10); ry2 = int(ph * 0.65)
                d.rectangle([rx1, ry1, rx2, ry2], outline='#ff0000', width=2)
                d.text((rx1+2, ry1+2), 'OCR ZONE', fill='#ff0000')

            photo = ImageTk.PhotoImage(preview)
            self._preview_lbl.configure(image=photo, text='')
            self._preview_lbl.image = photo
            self._preview_photo = photo
        except Exception:
            pass

    def _log(self, msg: str):
        self.log_q.put(f'[{datetime.now().strftime("%H:%M:%S")}] {msg}')

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

    def _save_config(self):
        with open(SAVE_FILE, 'w', encoding='utf-8') as f:
            json.dump({'selected': list(self.selected),
                       'buy_key': self.buy_key,
                       'cps': self._cps_var.get() if self._cps_var else 10},
                      f, ensure_ascii=False, indent=2)

    def _load_config(self):
        if not os.path.exists(SAVE_FILE):
            return
        try:
            with open(SAVE_FILE, encoding='utf-8') as f:
                data = json.load(f)
            self.selected = set(data.get('selected', []))
            self.buy_key  = data.get('buy_key', 'e')
            if self._cps_var and data.get('cps'):
                self._cps_var.set(data['cps'])
        except Exception:
            pass


if __name__ == '__main__':
    FortniteBot()
