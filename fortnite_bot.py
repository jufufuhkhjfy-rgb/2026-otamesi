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
    # ── GOAT ──
    {"name": "SKIBIDI TOILET",            "rarity": "GOAT",         "img": "2025/10/SKIBIDI-TOILET.webp"},
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
        self._preview_photo = None
        self._cps_var    = None  # clicks per second

        IMG_DIR.mkdir(exist_ok=True)
        self.root = tk.Tk()
        self.root.title('NEURAL LINK // INTERFACE_V.2.0')
        self.root.configure(bg=BG)
        self.root.resizable(True, True)

        self._build_ui()
        self._load_config()
        self._key_label.configure(text=f'[ {self.buy_key.upper()} ]')
        self.root.after(150, self._poll_log)
        self._refresh_windows()
        self._log('[SYSTEM] NEURAL LINK v2.0 起動完了')
        self._log(f'[TESS] {"OK" if HAS_TESS else "未検出 — pip install pytesseract 後 Tesseract本体も必要"}')
        threading.Thread(target=self._download_all_images, daemon=True).start()
        self.root.mainloop()

    def _build_ui(self):
        bar = tk.Frame(self.root, bg=BG)
        bar.pack(fill='x')
        tk.Label(bar, text='▶  NEURAL LINK // INTERFACE_V.2.0',
                 font=FONT_TITLE, fg=CYAN, bg=BG).pack(side='left', padx=12, pady=7)
        for txt, col, cmd in [('X', RED, self.root.destroy), ('—', WHITE, self.root.iconify)]:
            lbl = tk.Label(bar, text=txt, font=FONT_BOLD, fg=BG, bg=col,
                           width=3, cursor='hand2', padx=2, pady=5)
            lbl.pack(side='right', padx=1, pady=4)
            lbl.bind('<Button-1>', lambda _, c=cmd: c())
        tk.Frame(self.root, bg=CYAN, height=1).pack(fill='x')

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill='both', expand=True)
        self._build_left(body)
        tk.Frame(body, bg=GRAY, width=1).pack(side='left', fill='y')
        self._build_right(body)

        sb = tk.Frame(self.root, bg='#0d0d0d', height=22)
        sb.pack(fill='x', side='bottom')
        self._status_var = tk.StringVar(value='SYSTEM IDLE')
        tk.Label(sb, textvariable=self._status_var, font=('Courier New', 8),
                 fg=CYAN2, bg='#0d0d0d').pack(side='left', padx=8)

    def _build_left(self, parent):
        left = tk.Frame(parent, bg=BG, width=580)
        left.pack(side='left', fill='both', expand=True)
        left.pack_propagate(False)

        ctrl = tk.Frame(left, bg=BG2)
        ctrl.pack(fill='x', padx=8, pady=6)

        tk.Label(ctrl, text='ウィンドウ', font=FONT_MONO, fg=CYAN, bg=BG2).grid(
            row=0, column=0, sticky='w', padx=4)
        self._window_var = tk.StringVar()
        self._window_cb = ttk.Combobox(ctrl, textvariable=self._window_var,
                                        width=24, state='readonly', font=FONT_MONO)
        self._window_cb.grid(row=0, column=1, padx=4, pady=2)
        tk.Button(ctrl, text='↺', font=('Courier New', 11), fg=CYAN, bg=BG2,
                  bd=0, cursor='hand2', command=self._refresh_windows).grid(row=0, column=2, padx=2)

        tk.Label(ctrl, text='購入キー', font=FONT_MONO, fg=CYAN, bg=BG2).grid(
            row=1, column=0, sticky='w', padx=4, pady=2)
        self._key_label = tk.Label(ctrl, text=f'[ {self.buy_key.upper()} ]',
                                    font=('Courier New', 10, 'bold'), fg=YELLOW, bg=BG2,
                                    cursor='hand2')
        self._key_label.grid(row=1, column=1, sticky='w', padx=4)
        self._key_label.bind('<Button-1>', lambda _: self._start_key_capture())
        tk.Label(ctrl, text='←クリックして変更', font=FONT_SMALL, fg=GRAY, bg=BG2).grid(
            row=1, column=2, padx=2)
        tk.Button(ctrl, text='テスト送信', font=FONT_SMALL, fg=BG, bg=GREEN,
                  bd=0, cursor='hand2', padx=4,
                  command=lambda: threading.Thread(
                      target=self._press_game_key, args=(self.buy_key,), daemon=True
                  ).start()).grid(row=1, column=3, padx=4)

        tk.Label(ctrl, text='連打速度', font=FONT_MONO, fg=CYAN, bg=BG2).grid(
            row=2, column=0, sticky='w', padx=4, pady=2)
        self._cps_var = tk.IntVar(value=10)
        spd_frame = tk.Frame(ctrl, bg=BG2)
        spd_frame.grid(row=2, column=1, columnspan=2, sticky='w', padx=4)
        tk.Scale(spd_frame, from_=1, to=20, orient='horizontal', variable=self._cps_var,
                 length=160, bg=BG2, fg=CYAN, troughcolor=GRAY, highlightthickness=0,
                 font=FONT_SMALL, showvalue=False).pack(side='left')
        self._cps_lbl = tk.Label(spd_frame, font=FONT_MONO, fg=YELLOW, bg=BG2)
        self._cps_lbl.pack(side='left', padx=4)
        self._cps_var.trace_add('write', self._update_cps_label)
        self._update_cps_label()

        sel_f = tk.Frame(left, bg='#0d0d0d')
        sel_f.pack(fill='x', padx=8, pady=2)
        tk.Label(sel_f, text='選択中: ', font=FONT_BOLD, fg=CYAN, bg='#0d0d0d').pack(side='left')
        self._sel_label = tk.Label(sel_f, text='なし', font=FONT_MONO,
                                    fg=YELLOW, bg='#0d0d0d', wraplength=420, justify='left')
        self._sel_label.pack(side='left')

        self._scan_btn = CyberpunkButton(left, '▶ スキャン開始',
                                          command=self._toggle_scan,
                                          color=CYAN, width=560, height=42)
        self._scan_btn.pack(padx=8, pady=6)

        tk.Label(left, text='キャラクター一覧  (クリックで選択/解除)',
                 font=FONT_BOLD, fg=CYAN, bg=BG).pack(anchor='w', padx=10)

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
        right = tk.Frame(parent, bg=BG2, width=400)
        right.pack(side='right', fill='both')
        right.pack_propagate(False)

        hdr = tk.Frame(right, bg=BG2)
        hdr.pack(fill='x', padx=8, pady=(6,0))
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
        lf.pack(fill='x', padx=8, pady=(0,4))
        tk.Label(lf, text='LOG OUTPUT:', font=FONT_BOLD, fg=CYAN2, bg=BG2).pack(anchor='w')
        self._log_text = tk.Text(lf, height=14, font=('Courier New', 8),
                                  fg=GREEN, bg='#050505', bd=0,
                                  state='disabled', wrap='word')
        lsb = ttk.Scrollbar(lf, orient='vertical', command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=lsb.set)
        self._log_text.pack(side='left', fill='x', expand=True)
        lsb.pack(side='right', fill='y')

        tk.Button(right, text='ログ消去', font=FONT_SMALL, fg=BG, bg=PINK,
                  bd=0, padx=6, pady=2, cursor='hand2',
                  command=self._clear_log).pack(anchor='w', padx=8, pady=4)

    def _build_char_grid(self):
        COLS = 4
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
                tk.Label(self._grid_inner,
                         text=f'── {rarity} ──',
                         font=FONT_BOLD, fg=color, bg=BG).grid(
                    row=grid_row, column=0, columnspan=COLS,
                    sticky='w', padx=6, pady=(10, 2))
                grid_row += 1

            cell = tk.Frame(self._grid_inner, bg='#141414',
                            highlightthickness=2, highlightbackground=GRAY,
                            cursor='hand2', width=128, height=118)
            cell.grid(row=grid_row, column=col, padx=3, pady=3, sticky='nsew')
            cell.grid_propagate(False)

            img_lbl = tk.Label(cell, bg='#141414', cursor='hand2')
            img_lbl.place(x=8, y=4, width=112, height=80)
            ph = ImageTk.PhotoImage(make_placeholder(80))
            img_lbl.configure(image=ph)
            img_lbl.image = ph

            tk.Label(cell, text=name[:17], font=('Courier New', 7),
                     fg=WHITE, bg='#141414', wraplength=120).place(
                     x=0, y=86, width=128, height=18)
            tk.Label(cell, text=rarity, font=('Courier New', 6, 'bold'),
                     fg=color, bg='#0a0a0a').place(x=0, y=103, width=128, height=13)

            for w in [cell, img_lbl]:
                w.bind('<Button-1>', lambda _, n=name, c=cell: self._toggle_select(n, c))

            self._cells[name] = cell
            col += 1
            if col >= COLS:
                col = 0
                grid_row += 1

        for name in self.selected:
            if name in self._cells:
                self._cells[name].configure(highlightbackground=CYAN, highlightthickness=3)

    def _toggle_select(self, name: str, cell: tk.Frame):
        if name in self.selected:
            self.selected.discard(name)
            cell.configure(highlightbackground=GRAY, highlightthickness=2)
        else:
            self.selected.add(name)
            cell.configure(highlightbackground=CYAN, highlightthickness=3)
        self._sel_label.configure(
            text=', '.join(sorted(self.selected)) if self.selected else 'なし')
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
        # キャラ名は画面中央・上から15〜55%の範囲に表示される
        x1, x2 = int(w * 0.2), int(w * 0.8)
        y1, y2 = int(h * 0.15), int(h * 0.55)
        crop = img.crop((x1, y1, x2, y2))
        # 白文字を強調: 明るいピクセルだけ残す
        import numpy as np
        arr = np.array(crop.convert('L'))
        bright = np.where(arr > 160, 255, 0).astype(np.uint8)
        enhanced = Image.fromarray(bright)
        return pytesseract.image_to_string(
            enhanced,
            config='--psm 6 --oem 3 -l eng')

    def _parse_chars(self, text: str) -> list[str]:
        tl = text.lower()
        return [c['name'] for c in CHARACTERS
                if any(w in tl for w in c['name'].lower().split() if len(w) > 3)]

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
            pw = 380
            ph = min(int(img.height * pw / img.width), 280)
            preview = img.resize((pw, ph), Image.LANCZOS).convert('RGB')
            # OCR範囲を赤枠で表示
            d = ImageDraw.Draw(preview)
            rx1 = int(pw * 0.2); rx2 = int(pw * 0.8)
            ry1 = int(ph * 0.15); ry2 = int(ph * 0.55)
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
