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
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

pyautogui.FAILSAFE = True

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

IMG_BASE  = 'https://brainrot.fnjpnews.com/wp-content/uploads/2025/10/'
IMG_DIR   = Path('images')
SAVE_FILE = 'fortnite_bot_config.json'

# ═══════════════════════════════════════════
# キャラクターデータベース (name, rarity, img)
# ═══════════════════════════════════════════
CHARACTERS = [
    # ── アンコモン ──
    {"name": "Fishini Bossini",           "rarity": "アンコモン",     "img": "Fishini-Bossini.png"},
    {"name": "Lirili Larilla",            "rarity": "アンコモン",     "img": "Lirili-Larilla.png"},
    {"name": "Tim Cheese",                "rarity": "アンコモン",     "img": "Tim-Cheese.png"},
    {"name": "Fluriflura",                "rarity": "アンコモン",     "img": "Fluriflura.png"},
    {"name": "Penguino Cocosino",         "rarity": "アンコモン",     "img": "Penguino-Cocosino.png"},
    {"name": "Svinina Bombardino",        "rarity": "アンコモン",     "img": "Svinina-Bombardino.png"},
    {"name": "Pipi Kiwi",                 "rarity": "アンコモン",     "img": "Default_5_6.webp"},
    {"name": "Pipi Avocado",              "rarity": "アンコモン",     "img": "Default_9_4.webp"},
    # ── レア ──
    {"name": "Trippi Troppi",             "rarity": "レア",           "img": "Default_1_6.webp"},
    {"name": "Tung Tung Tung Sahur",      "rarity": "レア",           "img": "Tung-Sahur.webp"},
    {"name": "Grangster Footera",         "rarity": "レア",           "img": "Grangster-Footera.webp"},
    {"name": "Boneca Ambalabu",           "rarity": "レア",           "img": "Default_1_9.webp"},
    {"name": "Pipi Corni",                "rarity": "レア",           "img": "Pipi-Corni.webp"},
    {"name": "Ta Ta Ta Ta Sahur",         "rarity": "レア",           "img": "Ta-Ta-Ta-Ta-Sahur.webp"},
    {"name": "Burballoni Watermeloni",    "rarity": "レア",           "img": "Burballoni-Watermeloni.webp"},
    {"name": "Pipi Potato",               "rarity": "レア",           "img": "Pipi-Potato.webp"},
    # ── エピック ──
    {"name": "Cappuccino Assassino",      "rarity": "エピック",       "img": "Cappuccino-Assassino.webp"},
    {"name": "Brr Brr Patapim",           "rarity": "エピック",       "img": "Brr-Brr-Patapim.webp"},
    {"name": "Trulimero Trulicina",       "rarity": "エピック",       "img": "Trulimero-Trulicina.webp"},
    {"name": "Bananita Dolphinita",       "rarity": "エピック",       "img": "Bananita-Dolphinita.webp"},
    {"name": "Los Lirilitos",             "rarity": "エピック",       "img": "Los-Lirilitos.webp"},
    {"name": "Salamino Pinguino",         "rarity": "エピック",       "img": "Salamino-Pinguino.webp"},
    {"name": "Tric Trac Baraboom",        "rarity": "エピック",       "img": "Tric-Trac-Baraboom.webp"},
    {"name": "Los Tung TungCitos",        "rarity": "エピック",       "img": "Los-Tung-TungCitos.webp"},
    {"name": "Tukanno Bananno",           "rarity": "エピック",       "img": "Tukanno-Bananno.webp"},
    {"name": "Blueberrinni Octopussini",  "rarity": "エピック",       "img": "Blueberrinni-Octopussini.webp"},
    {"name": "Spijiniro Golubiro",        "rarity": "エピック",       "img": "Spijiniro-Golubiro.webp"},
    {"name": "Penguini Zucchini",         "rarity": "エピック",       "img": "Penguini-Zucchini.webp"},
    {"name": "Blueberrini Tatticini",     "rarity": "エピック",       "img": "Blueberrini-Tatticini.webp"},
    {"name": "Gingobalo Gingobali",       "rarity": "エピック",       "img": "Gingobalo-Gingobali.webp"},
    # ── レジェンダリー ──
    {"name": "Burbaloni Loliloli",        "rarity": "レジェンダリー", "img": "Burbaloni-Loliloli.webp"},
    {"name": "Chimpanzini Bananini",      "rarity": "レジェンダリー", "img": "Chimpanzini-Bananini.webp"},
    {"name": "Ballerina Cappuccina",      "rarity": "レジェンダリー", "img": "Ballerina-Cappuccina.webp"},
    {"name": "Chef Crabracadabra",        "rarity": "レジェンダリー", "img": "Chef-Crabracadabra.webp"},
    {"name": "Glorbo Fruttodillo",        "rarity": "レジェンダリー", "img": "Glorbo-Fruttodillo.webp"},
    {"name": "Cacto Hipopotamo",          "rarity": "レジェンダリー", "img": "Cacto-Hipopotamo.webp"},
    {"name": "Ballerino Lololo",          "rarity": "レジェンダリー", "img": "Ballerino-Lololo.webp"},
    {"name": "Lerulerulerule",            "rarity": "レジェンダリー", "img": "Lerulerulerule.webp"},
    {"name": "Bambini Crostini",          "rarity": "レジェンダリー", "img": "Bambini-Crostini.webp"},
    {"name": "Francescoo",                "rarity": "レジェンダリー", "img": "Francescoo.webp"},
    {"name": "Zibra Zubra Zibralini",     "rarity": "レジェンダリー", "img": "Zibra-Zubra-Zibralini.webp"},
    {"name": "Bambu Di Miale",            "rarity": "レジェンダリー", "img": "Bambu-Di-Miale.webp"},
    {"name": "Mangolini Parrocini",       "rarity": "レジェンダリー", "img": "Mangolini-Parrocini.webp"},
    {"name": "Lampu Lampu Sahur",         "rarity": "レジェンダリー", "img": "Lampu-Lampu-Sahur.webp"},
    {"name": "Octopuss Coconuss",         "rarity": "レジェンダリー", "img": "Octopuss-Coconuss.webp"},
    {"name": "Leonelli Cactuselli",       "rarity": "レジェンダリー", "img": "Leonelli-Cactuselli.webp"},
    {"name": "Elefantucci Bananucci",     "rarity": "レジェンダリー", "img": "Elefantucci-Bananucci.webp"},
    {"name": "Avocadini Antilopini",      "rarity": "レジェンダリー", "img": "Avocadini-Antilopini.webp"},
    {"name": "Dragonini Ananasini",       "rarity": "レジェンダリー", "img": "Dragonini-Ananasini.webp"},
    # ── ミシック ──
    {"name": "Frigo Camelo",              "rarity": "ミシック",       "img": "Frigo-Camelo.webp"},
    {"name": "Orangutini Annassini",      "rarity": "ミシック",       "img": "Orangutini-Annassini.webp"},
    {"name": "Bombardiro Crocodilo",      "rarity": "ミシック",       "img": "Bombardiro-Crocodilo.webp"},
    {"name": "Bombombini Gusini",         "rarity": "ミシック",       "img": "Bombombini-Gusini.webp"},
    {"name": "Gorillo Watermellondrillo", "rarity": "ミシック",       "img": "Gorillo-Watermellondrillo.webp"},
    {"name": "Sigma Boy",                 "rarity": "ミシック",       "img": "Sigma-Boy.webp"},
    {"name": "Matteo",                    "rarity": "ミシック",       "img": "Matteo.webp"},
    {"name": "Los Spijuniritos",          "rarity": "ミシック",       "img": "Los-Spijuniritos.webp"},
    {"name": "Rhino Toasterino",          "rarity": "ミシック",       "img": "Rhino-Toasterino.webp"},
    {"name": "Ganganzelli Trulala",       "rarity": "ミシック",       "img": "Ganganzelli-Trulala.webp"},
    {"name": "Te Te Te Sahur",            "rarity": "ミシック",       "img": "Te-Te-Te-Sahur.webp"},
    {"name": "Fireworkito Explodito",     "rarity": "ミシック",       "img": "Fireworkito-Explodito.webp"},
    {"name": "Strawberrelli Flamingelli", "rarity": "ミシック",       "img": "Strawberrelli-Flamingelli.webp"},
    {"name": "Elefantino Frigorifero",    "rarity": "ミシック",       "img": "Elefantino-Frigorifero.webp"},
    {"name": "To To To Sahur",            "rarity": "ミシック",       "img": "To-To-To-Sahur.webp"},
    {"name": "Elefante Cafettino",        "rarity": "ミシック",       "img": "Elefante-Cafettino.webp"},
    {"name": "Antoniooo",                 "rarity": "ミシック",       "img": "Antoniooo.webp"},
    {"name": "Kudanile Astronaute",       "rarity": "ミシック",       "img": "Kudanile-Astronaute.webp"},
    {"name": "Girafa Celeste",            "rarity": "ミシック",       "img": "Girafa-Celeste.webp"},
    {"name": "Mr Peppermint",             "rarity": "ミシック",       "img": "Mr-Peppermint.webp"},
    {"name": "Perochello Lemonchello",    "rarity": "ミシック",       "img": "Perochello-Lemonchello.webp"},
    {"name": "Tang Tang Kelentang",       "rarity": "ミシック",       "img": "Tang-Tang-Kelentang.webp"},
    {"name": "Avocadorilla",              "rarity": "ミシック",       "img": "Avocadorilla.webp"},
    {"name": "Patapimus Maximus",         "rarity": "ミシック",       "img": "Patapimus-Maximus.webp"},
    {"name": "Tirilikalika Tirilikaliko", "rarity": "ミシック",       "img": "Tirilikalika-Tirilikaliko.webp"},
    {"name": "Santoniooo",                "rarity": "ミシック",       "img": "Santoniooo.webp"},
    {"name": "Los Matteos",               "rarity": "ミシック",       "img": "Los-Matteos.webp"},
    {"name": "Los Sigma Boys",            "rarity": "ミシック",       "img": "Los_Sigma_Boys.webp"},
    {"name": "Eaglucci Cocosucci",        "rarity": "ミシック",       "img": "Eaglucci-Cocosucci.webp"},
    {"name": "Ti Ti Ti Sahur",            "rarity": "ミシック",       "img": "Ti-Ti-Ti-Sahur.webp"},
    {"name": "Fishinis Santinis",         "rarity": "ミシック",       "img": "Fishinis-Santinis.webp"},
    # ── Brainrot God ──
    {"name": "Cocofanto Elefanto",            "rarity": "Brainrot God", "img": "Cocofanto-Elefanto.webp"},
    {"name": "Tob Tobi Tob",                  "rarity": "Brainrot God", "img": "Tob-Tobi-Tob.webp"},
    {"name": "Tralalero Tralala",             "rarity": "Brainrot God", "img": "Tralalero-Tralala.webp"},
    {"name": "Odin Din Din Dun",              "rarity": "Brainrot God", "img": "Odin-Din-Din-Dun.webp"},
    {"name": "Akulini Cactusini",             "rarity": "Brainrot God", "img": "Akulini-Cactusini.webp"},
    {"name": "Chachechicha",                  "rarity": "Brainrot God", "img": "Chachechicha.webp"},
    {"name": "Espressona Signora",            "rarity": "Brainrot God", "img": "Espressona-Signora.webp"},
    {"name": "La Vaca Saturno Saturnita",     "rarity": "Brainrot God", "img": "La-Vaca-Saturno-Saturnita.webp"},
    {"name": "Centralucci Nuclearucci",       "rarity": "Brainrot God", "img": "Centralucci-Nuclearucci.webp"},
    {"name": "Ecco Cavallo Virtuoso",         "rarity": "Brainrot God", "img": "Ecco-Cavallo-Virtuoso.webp"},
    {"name": "Los Vaguitas Saturnitas",       "rarity": "Brainrot God", "img": "Los-Vaguitas-Saturnitas.webp"},
    {"name": "Bulbito Bandito Traktorito",    "rarity": "Brainrot God", "img": "Bulbito-Traktorito.webp"},
    {"name": "Bananananito Bandito",          "rarity": "Brainrot God", "img": "Bananananito-Bandito.webp"},
    {"name": "Chillin Chili",                 "rarity": "Brainrot God", "img": "Chillin-Chili.webp"},
    {"name": "Trippi Troppi Troppa Trippa",   "rarity": "Brainrot God", "img": "Trippi-Troppi-Troppa-Trippa.webp"},
    {"name": "Brri Bicus Dicus",              "rarity": "Brainrot God", "img": "Brri-Bicus-Dicus.webp"},
    {"name": "Cioccolatini Pancioncioni",     "rarity": "Brainrot God", "img": "Cioccolatini-Pancioncioni.webp"},
    {"name": "Brr Es Teh Patipum",            "rarity": "Brainrot God", "img": "Brr-Es-Teh-Patipum.webp"},
    {"name": "Torrtuginni Dragonfrutinni",    "rarity": "Brainrot God", "img": "Torrtuginni-Dragonfrutinni.webp"},
    {"name": "Los Bros",                      "rarity": "Brainrot God", "img": "Los-Bros.webp"},
    {"name": "Bim Bim Bim Sadim",             "rarity": "Brainrot God", "img": "Bim-Bim-Bim-Sadim.webp"},
    {"name": "Bambini Tankini",               "rarity": "Brainrot God", "img": "Bambini-Tankini.webp"},
    {"name": "Hotti Coccolli",                "rarity": "Brainrot God", "img": "Hotti-Coccolli.webp"},
    {"name": "Jiqi Jiqi Shizhon",             "rarity": "Brainrot God", "img": "Default2_7_9.webp"},
    {"name": "Los Crocodillitos",             "rarity": "Brainrot God", "img": "Los-Crocodillitos.webp"},
    {"name": "Agarrini La Palini",            "rarity": "Brainrot God", "img": "Default2_6_4.webp"},
    {"name": "Alessiooooooo",                 "rarity": "Brainrot God", "img": "Alessiooooooo.webp"},
    {"name": "Dig Torto Dolf",                "rarity": "Brainrot God", "img": "Dig_Torto_Dolf.webp"},
    {"name": "Karkerkar Kurkur",              "rarity": "Brainrot God", "img": "Karkerkar-Kurkur.webp"},
    {"name": "Il Costruttore Di Pomodori",    "rarity": "Brainrot God", "img": "Il-Costruttore-Di-Pomodori.webp"},
    {"name": "Piccionetta Machina",           "rarity": "Brainrot God", "img": "Piccionetta-Machina.webp"},
    {"name": "Pipoqueira Motoqueira",         "rarity": "Brainrot God", "img": "Pipoqueira-Motoqueira.webp"},
    {"name": "Il Piccione Musculone",         "rarity": "Brainrot God", "img": "Il-Piccione-Musculone.webp"},
    {"name": "Job Job Job Sahur",             "rarity": "Brainrot God", "img": "Job-Job-Job-Sahur.webp"},
    {"name": "Las Sis",                       "rarity": "Brainrot God", "img": "Las-Sis.webp"},
    {"name": "La Matcha Assassino",           "rarity": "Brainrot God", "img": "La-Matcha-Assassino.webp"},
    {"name": "Il Mastodontico Telepiedone",   "rarity": "Brainrot God", "img": "Il-Mastodontico-Telepiedone.webp"},
    {"name": "Los Christmas Bros",            "rarity": "Brainrot God", "img": "Los-Christmas-Bros.webp"},
    {"name": "Il Bisonte Giuppitere",         "rarity": "Brainrot God", "img": "Il-Bisonte-Giuppitere.webp"},
    {"name": "Malame Amarale",                "rarity": "Brainrot God", "img": "Malame-Amarale.webp"},
    {"name": "Linguicine Serpentine",         "rarity": "Brainrot God", "img": "Linguicine_Serpentine.webp"},
    {"name": "Belugelo Beluga",               "rarity": "Brainrot God", "img": "Belugelo-Beluga.webp"},
    {"name": "Bella Pancasita",               "rarity": "Brainrot God", "img": "Bella-Pancasita.webp"},
    {"name": "Rhino Helicopterino",           "rarity": "Brainrot God", "img": "Rhino-Helicopterino.webp"},
    {"name": "Missilpython Turbozzo",         "rarity": "Brainrot God", "img": "Missilpython-Turbozzo.webp"},
    {"name": "Auglurini Arbuzini",            "rarity": "Brainrot God", "img": "Auglurini-Arbuzini.webp"},
    # ── シークレット ──
    {"name": "Los Tralaleritos",              "rarity": "シークレット", "img": "Los-Orcaleritos.webp"},
    {"name": "Los Tralaleritas",              "rarity": "シークレット", "img": "Los-Tralaleritas.webp"},
    {"name": "Trenostruzzo Turbo",            "rarity": "シークレット", "img": "Trenostruzzo-Turbo.webp"},
    {"name": "Kravilino Cekicino",            "rarity": "シークレット", "img": "Kravilino-Cekicino.webp"},
    {"name": "Los Orcaleritos",               "rarity": "シークレット", "img": "Los-Orcaleritos-1.webp"},
    {"name": "Las Agarrinis",                 "rarity": "シークレット", "img": "Las-Agarrinis.webp"},
    {"name": "Los Couples",                   "rarity": "シークレット", "img": "Los-Couples.webp"},
    {"name": "Piccione Macchina",             "rarity": "シークレット", "img": "Piccione-Macchina.webp"},
    {"name": "Peeling Peely",                 "rarity": "シークレット", "img": "Peeling-Peely.webp"},
    {"name": "Pakrahmatmamat",                "rarity": "シークレット", "img": "Pakrah-matmamat.webp"},
    {"name": "Pakrahmatmamatcita",            "rarity": "シークレット", "img": "Pakrahmatmamatcita.webp"},
    {"name": "Pickolini Malakini",            "rarity": "シークレット", "img": "Pickolini-Malakini.webp"},
    {"name": "Los Job Jobsitos",              "rarity": "シークレット", "img": "Los-Job-Jobsitos.webp"},
    {"name": "TrenoStruzzo Turbo 4000",       "rarity": "シークレット", "img": "TrenoStruzzo-Turbo-4000.webp"},
    {"name": "Anpali Babel",                  "rarity": "シークレット", "img": "Anpali-Babel.webp"},
    {"name": "Los Karkeritos",                "rarity": "シークレット", "img": "Los-Karkeritos.webp"},
    {"name": "Orcalero Orcala",               "rarity": "シークレット", "img": "Orcalero-Orcala.webp"},
    {"name": "Frogino Assassino",             "rarity": "シークレット", "img": "Frogino-Assassino.webp"},
    {"name": "Ketchuru and Musturu",          "rarity": "シークレット", "img": "Ketchuru-and-Musturu.webp"},
    {"name": "Pot Hotspot",                   "rarity": "シークレット", "img": "Pot-Hotspot.webp"},
    {"name": "Tatoruman",                     "rarity": "シークレット", "img": "Tatoruman.webp"},
    {"name": "Fragola La La La",              "rarity": "シークレット", "img": "Fragola-La-La-La.webp"},
    {"name": "21",                            "rarity": "シークレット", "img": "21.webp"},
    {"name": "Los Mobilis",                   "rarity": "シークレット", "img": "Los-Mobilis.webp"},
    {"name": "Frogatto Piratto",              "rarity": "シークレット", "img": "Frogatto-Piratto.webp"},
    {"name": "Garamaramadungdung",            "rarity": "シークレット", "img": "Garamaramadungdung.webp"},
    {"name": "Papero Aspiratorino",           "rarity": "シークレット", "img": "Papero-Aspiratorino.webp"},
    {"name": "Bun Din Din Dun",               "rarity": "シークレット", "img": "Bun-Din-Din-Dun.webp"},
    {"name": "Pirulitoita Bicicleteira",      "rarity": "シークレット", "img": "Pirulitoita-Bicicleteira.webp"},
    {"name": "Chachechi Sahur",               "rarity": "シークレット", "img": "Chachechi-Sahur.webp"},
    {"name": "Il Sacro Cabrospaghetti",       "rarity": "シークレット", "img": "Il-Sacro-Cabrospaghetti.webp"},
    {"name": "Owlito Tactito",                "rarity": "シークレット", "img": "Owlito-Tactito.webp"},
    {"name": "La Grande Combinacion",         "rarity": "シークレット", "img": "La-Grande-Combinacion.webp"},
    {"name": "Rosalero",                      "rarity": "シークレット", "img": "Rosalero.webp"},
    {"name": "Clove Clove Clove Sahur",       "rarity": "シークレット", "img": "Clove-Clove-Clove-Sahur.webp"},
    {"name": "Los Santacitos",                "rarity": "シークレット", "img": "Los-Santacitos.webp"},
    {"name": "Paquito El Taquito",            "rarity": "シークレット", "img": "Paquito-El-Taquito.webp"},
    {"name": "Cornball Sahur",                "rarity": "シークレット", "img": "Cornball-Sahur.webp"},
    {"name": "Nuclearo Dinossauro",           "rarity": "シークレット", "img": "Nuclearo-Dinossauro.webp"},
    {"name": "67",                            "rarity": "シークレット", "img": "67.webp"},
    {"name": "Los Esok Sekolitos",            "rarity": "シークレット", "img": "Los-Esok-Sekolitos.webp"},
    {"name": "Roobinha Acerolinha",           "rarity": "シークレット", "img": "Roobinha-Acerolinha.webp"},
    {"name": "Coccoblade",                    "rarity": "シークレット", "img": "Coccoblade.webp"},
    {"name": "Cacasito Satelito",             "rarity": "シークレット", "img": "Cacasito-Satelito.webp"},
    {"name": "Dilly Pickle",                  "rarity": "シークレット", "img": "Dilly_Pickle.webp"},
    {"name": "Chop Chop Chop Sahur",          "rarity": "シークレット", "img": "Chop-Chop-Chop-Sahur.webp"},
    {"name": "Crocodila Bicicleteira",        "rarity": "シークレット", "img": "Crocodila-Bicicleteira.webp"},
    {"name": "Pingus Kingus",                 "rarity": "シークレット", "img": "Pingus-Kingus.webp"},
    {"name": "Ketupat Kepat Prekupat",        "rarity": "シークレット", "img": "Ketupat-Kepat-Prekupat.webp"},
    {"name": "Lovey Lovey Bear",              "rarity": "シークレット", "img": "Lovey-Lovey-Bear.webp"},
    {"name": "Coccobladina",                  "rarity": "シークレット", "img": "Coccobladina.webp"},
    {"name": "Carrot Carrot Sahur",           "rarity": "シークレット", "img": "Carrot-Carrot-Sahur.webp"},
    {"name": "Rang Reng Kelerang",            "rarity": "シークレット", "img": "Rang-Reng-Kelerang.webp"},
    {"name": "Cobracadabra",                  "rarity": "シークレット", "img": "Cobracadabra.webp"},
    {"name": "Los Garamadungcitos",           "rarity": "シークレット", "img": "Los-Garamadungcitos.webp"},
    {"name": "Aquanaut",                      "rarity": "シークレット", "img": "Aquanaut.webp"},
    {"name": "Re Delle Carte",                "rarity": "シークレット", "img": "Re-Delle-Carte.webp"},
    {"name": "Tung Ballerina Sahur",          "rarity": "シークレット", "img": "Tung-Ballerina-Sahur.webp"},
    {"name": "Baskuru And Egguru",            "rarity": "シークレット", "img": "Baskuru-And-Egguru.webp"},
    {"name": "Pitiata Baem",                  "rarity": "シークレット", "img": "Pitiata-Baem.webp"},
    {"name": "Los 67",                        "rarity": "シークレット", "img": "Los-67.webp"},
    {"name": "Tralalero Kingala",             "rarity": "シークレット", "img": "Tralalero-Kingala.webp"},
    {"name": "Penguini Armorini Kingini",     "rarity": "シークレット", "img": "Penguini-Armorini-Kingini.webp"},
    {"name": "Chimpanzini Kingini",           "rarity": "シークレット", "img": "Chimpanzini-Kingini.webp"},
    {"name": "Tictac Tictac Sahur",           "rarity": "シークレット", "img": "Tictac-Tictac-Sahur.webp"},
    {"name": "La Royals",                     "rarity": "シークレット", "img": "La-Royals.webp"},
    {"name": "Alligarto Alligarto",           "rarity": "シークレット", "img": "Alligarto-Alligarto.webp"},
    {"name": "Cannelloni Dragoni",            "rarity": "シークレット", "img": "Cannelloni-Dragoni.webp"},
    {"name": "Vulturino Skeletono",           "rarity": "シークレット", "img": "Vulturino-Skeletono.webp"},
    {"name": "Chocone Dragone",               "rarity": "シークレット", "img": "Chocone-Dragone.webp"},
    # ── エターナル ──
    {"name": "Gigalitraktos Spidorobos",  "rarity": "エターナル",   "img": "Gigalitraktos-Spidorobos.webp"},
    {"name": "Burguro dan Fryuro",        "rarity": "エターナル",   "img": "Burguro-dan-Fryuro.webp"},
    {"name": "Bearini Plammini Guardini", "rarity": "エターナル",   "img": "Bearini-Plammini-Guardini.webp"},
    {"name": "Tiramisubmarini",           "rarity": "エターナル",   "img": "Tiramisubmarini.webp"},
    {"name": "Tralaledon",                "rarity": "エターナル",   "img": "Tralaledon.webp"},
    {"name": "Garbagzilla",               "rarity": "エターナル",   "img": "Garbagzilla.webp"},
    {"name": "Fishini Mechinini",         "rarity": "エターナル",   "img": "Fishini-Mechinini.webp"},
    {"name": "Cannone Maledettone",       "rarity": "エターナル",   "img": "Cannone-Maledettone.webp"},
    {"name": "La Superior Combinacion",   "rarity": "エターナル",   "img": "La-Superior-Combinacion.webp"},
    {"name": "Il Maledettones",           "rarity": "エターナル",   "img": "Il-Maledettones.webp"},
    # ── GOAT ──
    {"name": "SKIBIDI TOILET",            "rarity": "GOAT",         "img": "SKIBIDI-TOILET.webp"},
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
        self.buy_pos     = None
        self.selected: set[str] = set()
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

        tk.Label(ctrl, text='購入ボタン位置', font=FONT_MONO, fg=CYAN, bg=BG2).grid(
            row=1, column=0, sticky='w', padx=4, pady=2)
        self._cal_label = tk.Label(ctrl, text='未設定', font=FONT_MONO, fg=RED, bg=BG2)
        self._cal_label.grid(row=1, column=1, sticky='w', padx=4)
        tk.Button(ctrl, text='設定(3秒)', font=FONT_SMALL, fg=BG, bg=YELLOW,
                  bd=0, cursor='hand2', command=self._start_calibrate).grid(row=1, column=2, padx=2)

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
        ok = 0
        for char in CHARACTERS:
            name   = char['name']
            fname  = char['img']
            path   = IMG_DIR / fname
            if path.exists():
                self._load_image_to_cell(name, path)
                ok += 1
                continue
            try:
                url = IMG_BASE + fname
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=10) as r:
                    path.write_bytes(r.read())
                self._load_image_to_cell(name, path)
                ok += 1
                time.sleep(0.03)
            except Exception:
                pass
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

    def _start_calibrate(self):
        self._log('[CAL] 3秒後にマウス位置を記録します...')
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

    def _update_preview(self, img: Image.Image):
        try:
            pw = 380
            ph = min(int(img.height * pw / img.width), 280)
            photo = ImageTk.PhotoImage(img.resize((pw, ph), Image.LANCZOS))
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
                       'buy_pos': list(self.buy_pos) if self.buy_pos else None},
                      f, ensure_ascii=False, indent=2)

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
