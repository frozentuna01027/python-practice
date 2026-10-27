#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ミニクエスト - ドラクエ1風 トップダウンRPG (pygame)
  実行:  pip install pygame  →  python miniquest.py
  操作:  矢印キー / WASD = 移動   Z・Enter・Space = 決定 / メニュー   X・Esc = キャンセル
"""
import os
import sys
import json
import math
import random
import pygame

W, H = 640, 480
TILE = 40
VW, VH = 15, 11            # 画面に映るマス数
OX, OY = 20, 20            # マップ表示領域の左上
WHITE, BLACK = (255, 255, 255), (0, 0, 0)
HERE = os.path.dirname(os.path.abspath(__file__))
SAVE_PATH = os.path.join(HERE, "miniquest_save.json")

# ------------------------------------------------------------ データ
# (ちから, すばやさ, さいだいHP, さいだいMP)   index = レベル-1
LV_TABLE = [(4, 4, 15, 0), (5, 4, 22, 0), (7, 6, 24, 5), (7, 8, 31, 16),
            (12, 10, 35, 20), (16, 10, 38, 24), (18, 17, 40, 26), (22, 18, 46, 29),
            (30, 22, 50, 36), (35, 31, 54, 40), (40, 35, 62, 50), (48, 40, 63, 58),
            (52, 48, 70, 64), (60, 55, 74, 70), (65, 60, 80, 80)]
EXP_TABLE = [0, 10, 30, 70, 130, 220, 350, 520, 750, 1050, 1400, 1800, 2300, 2900, 3600]
MAX_LV = len(LV_TABLE)

SPELLS = {"ヒール": (3, 3), "ファイア": (5, 2)}          # 名前: (おぼえるLV, 消費MP)
WEAPONS = [("なし", 0), ("どうのつるぎ", 10), ("てつのつるぎ", 20)]
ARMORS = [("ぬののふく", 0), ("かわのよろい", 8), ("てつのよろい", 16)]
SHOP = [("やくそう", 8, "herb", 0), ("どうのつるぎ", 100, "weapon", 1),
        ("てつのつるぎ", 350, "weapon", 2), ("かわのよろい", 70, "armor", 1),
        ("てつのよろい", 400, "armor", 2)]
INN_PRICE = 6

# 名前: (HP, こうげき, ぼうぎょ, 経験値, ゴールド)
ENEMIES = {"スライム": (8, 6, 2, 3, 4), "コウモリ": (14, 10, 4, 6, 8),
           "ゴースト": (22, 16, 6, 12, 14), "おおサソリ": (34, 22, 12, 20, 24),
           "ゴーレム": (70, 32, 14, 45, 60), "まおう": (180, 40, 20, 0, 0)}
ZONES = {0: ["スライム"], 1: ["スライム", "コウモリ"], 2: ["コウモリ", "ゴースト"],
         3: ["ゴースト", "おおサソリ"], 4: ["おおサソリ", "ゴーレム"],
         5: ["ゴーレム", "ゴースト", "おおサソリ"]}
WALKABLE = set(".TBCVD")


# ------------------------------------------------------------ フォント
def load_font(size):
    for fn in ("font.ttf", "font.otf", "font.ttc"):          # 同じフォルダに置けば最優先
        p = os.path.join(HERE, fn)
        if os.path.exists(p):
            return pygame.font.Font(p, size)
    prefer = ["notosanscjkjp", "notosansjp", "notosanscjk", "yugothic", "meiryo", "msgothic",
              "hiraginosans", "hiraginokakugothicpron", "ipagothic", "ipaexgothic", "ipapgothic",
              "takaogothic", "vlgothic", "applegothic", "droidsansfallback", "arialunicodems"]
    for n in prefer:
        p = pygame.font.match_font(n)
        if p:
            return pygame.font.Font(p, size)
    for n in pygame.font.get_fonts():
        if any(k in n for k in ("cjk", "gothic", "mincho", "jp", "japan", "meiryo", "hiragino")):
            p = pygame.font.match_font(n)
            if p:
                return pygame.font.Font(p, size)
    return pygame.font.Font(None, size)


# ------------------------------------------------------------ マップ生成
def build_map():
    w, h = 48, 36
    cpos, vpos, bpos = (6, 29), (22, 22), (38, 4)
    rows = None
    for seed in range(300):
        rng = random.Random(seed + 11)
        m = [["~"] * w for _ in range(h)]
        for y in range(10, 34):
            for x in range(2, 42):
                m[y][x] = "."
        for y in range(2, 8):
            for x in range(32, 45):
                m[y][x] = "."
        for x, y in ((2, 10), (41, 10), (2, 33), (41, 33), (32, 2), (44, 2), (32, 7), (44, 7)):
            m[y][x] = "~"
        for y in range(15, 20):
            for x in range(13, 19):
                m[y][x] = "~"

        def blob(ch, n, rmax):
            for _ in range(n):
                cx, cy, r = rng.randint(2, 44), rng.randint(3, 33), rng.randint(1, rmax)
                for dy in range(-r, r + 1):
                    for dx in range(-r, r + 1):
                        x, y = cx + dx, cy + dy
                        if 0 <= x < w and 0 <= y < h and dx * dx + dy * dy <= r * r + 1 and m[y][x] == ".":
                            m[y][x] = ch
        blob("T", 30, 3)
        blob("M", 16, 2)
        for kx, ky in (cpos, vpos, bpos):
            for dy in range(-1, 2):
                for dx in range(-1, 2):
                    m[ky + dy][kx + dx] = "."
        m[7][36] = m[10][36] = "."
        m[8][36] = m[9][36] = "B"
        m[cpos[1]][cpos[0]] = "C"
        m[vpos[1]][vpos[0]] = "V"
        m[bpos[1]][bpos[0]] = "D"
        rows = ["".join(r) for r in m]
        # 到達可能チェック
        seen, stack = set(), [(cpos[0], cpos[1] + 1)]
        while stack:
            x, y = stack.pop()
            if (x, y) in seen or not (0 <= x < w and 0 <= y < h) or rows[y][x] not in WALKABLE:
                continue
            seen.add((x, y))
            stack += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
        if vpos in seen and bpos in seen:
            break
    return rows, cpos, vpos, bpos


# ------------------------------------------------------------ 絵(すべてコードで描画)
def make_tiles():
    T = {}

    def base(col):
        s = pygame.Surface((TILE, TILE))
        s.fill(col)
        return s

    def grass():
        s = base((72, 176, 72))
        for x, y in ((6, 8), (26, 12), (14, 28), (32, 30), (8, 22), (30, 4)):
            pygame.draw.rect(s, (50, 140, 56), (x, y, 4, 2))
        return s

    def water():
        s = base((40, 90, 200))
        for y in (8, 20, 32):
            pygame.draw.line(s, (110, 160, 240), (4, y), (14, y), 2)
            pygame.draw.line(s, (110, 160, 240), (24, y + 4), (34, y + 4), 2)
        return s

    T["."] = grass()
    s = grass()
    for cx, cy in ((12, 16), (28, 14), (20, 30)):
        pygame.draw.rect(s, (100, 60, 30), (cx - 2, cy + 6, 4, 8))
        pygame.draw.circle(s, (24, 100, 40), (cx, cy), 10)
        pygame.draw.circle(s, (40, 130, 56), (cx - 3, cy - 3), 5)
    T["T"] = s
    s = grass()
    pts = [(1, 37), (14, 8), (23, 22), (29, 14), (39, 37)]
    pygame.draw.polygon(s, (130, 95, 60), pts)
    pygame.draw.polygon(s, (95, 66, 40), [(14, 8), (23, 22), (18, 37), (10, 37)])
    pygame.draw.polygon(s, WHITE, [(14, 8), (10, 17), (14, 15), (18, 17)])
    pygame.draw.polygon(s, BLACK, pts, 2)
    T["M"] = s
    T["~"] = water()
    s = water()
    pygame.draw.rect(s, (140, 100, 60), (6, 0, 28, TILE))
    for y in range(0, TILE, 8):
        pygame.draw.line(s, (90, 60, 30), (6, y), (33, y), 2)
    pygame.draw.line(s, (70, 45, 20), (6, 0), (6, TILE), 3)
    pygame.draw.line(s, (70, 45, 20), (33, 0), (33, TILE), 3)
    T["B"] = s

    def castle(col, roof):
        s = grass()
        pygame.draw.rect(s, col, (5, 14, 30, 22))
        for x in (3, 29):
            pygame.draw.rect(s, col, (x, 6, 8, 30))
            for i in range(3):
                pygame.draw.rect(s, col, (x + i * 3, 3, 2, 4))
            pygame.draw.rect(s, BLACK, (x + 3, 14, 2, 5))
            pygame.draw.rect(s, BLACK, (x, 6, 8, 30), 1)
        pygame.draw.rect(s, BLACK, (5, 14, 30, 22), 1)
        pygame.draw.rect(s, BLACK, (16, 24, 8, 12))
        pygame.draw.line(s, BLACK, (20, 14), (20, 3), 2)
        pygame.draw.polygon(s, roof, [(20, 3), (30, 6), (20, 9)])
        return s
    T["C"] = castle((190, 190, 200), (220, 40, 40))
    T["D"] = castle((90, 60, 120), (170, 0, 0))
    s = grass()
    pygame.draw.rect(s, (230, 220, 190), (3, 19, 15, 15))
    pygame.draw.polygon(s, (200, 60, 50), [(1, 19), (10, 8), (20, 19)])
    pygame.draw.rect(s, BLACK, (8, 26, 5, 8))
    pygame.draw.rect(s, (230, 220, 190), (22, 14, 16, 20))
    pygame.draw.polygon(s, (60, 90, 200), [(20, 14), (30, 4), (40, 14)])
    pygame.draw.rect(s, (60, 40, 20), (27, 24, 6, 10))
    pygame.draw.rect(s, (255, 230, 120), (24, 18, 4, 4))
    T["V"] = s
    return T


def make_hero(frame):
    s = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
    blue = (40, 60, 200)
    pygame.draw.rect(s, blue, (12, 3, 16, 8))
    pygame.draw.rect(s, (255, 210, 170), (13, 11, 14, 8))
    pygame.draw.rect(s, BLACK, (15, 13, 2, 3))
    pygame.draw.rect(s, BLACK, (23, 13, 2, 3))
    pygame.draw.rect(s, blue, (10, 19, 20, 12))
    pygame.draw.rect(s, (230, 190, 60), (10, 25, 20, 2))
    pygame.draw.rect(s, (200, 200, 215), (3, 17, 7, 14))
    pygame.draw.rect(s, (160, 40, 40), (5, 20, 3, 8))
    pygame.draw.rect(s, (220, 220, 235), (31, 8, 3, 20))
    pygame.draw.rect(s, (120, 80, 40), (29, 27, 7, 3))
    if frame == 0:
        pygame.draw.rect(s, (110, 70, 40), (12, 31, 6, 6))
        pygame.draw.rect(s, (110, 70, 40), (22, 31, 6, 6))
    else:
        pygame.draw.rect(s, (110, 70, 40), (10, 31, 6, 5))
        pygame.draw.rect(s, (110, 70, 40), (24, 31, 6, 5))
    return s


def draw_enemy(s, name, cx, cy):
    if name == "スライム":
        c = (60, 120, 230)
        pygame.draw.ellipse(s, c, (cx - 70, cy - 20, 140, 90))
        pygame.draw.polygon(s, c, [(cx - 28, cy - 12), (cx, cy - 75), (cx + 28, cy - 12)])
        pygame.draw.ellipse(s, (160, 200, 255), (cx - 48, cy - 4, 30, 16))
        for dx in (-28, 28):
            pygame.draw.ellipse(s, WHITE, (cx + dx - 10, cy + 8, 20, 24))
            pygame.draw.circle(s, BLACK, (cx + dx, cy + 22), 6)
        pygame.draw.arc(s, BLACK, (cx - 25, cy + 28, 50, 28), math.pi, 2 * math.pi, 3)
    elif name == "コウモリ":
        c = (120, 60, 180)
        for sg in (-1, 1):
            pygame.draw.polygon(s, c, [(cx + sg * 20, cy - 10), (cx + sg * 115, cy - 65), (cx + sg * 95, cy - 10),
                                       (cx + sg * 105, cy + 20), (cx + sg * 65, cy + 5), (cx + sg * 20, cy + 28)])
        pygame.draw.ellipse(s, c, (cx - 36, cy - 45, 72, 95))
        pygame.draw.polygon(s, c, [(cx - 30, cy - 38), (cx - 22, cy - 70), (cx - 8, cy - 42)])
        pygame.draw.polygon(s, c, [(cx + 30, cy - 38), (cx + 22, cy - 70), (cx + 8, cy - 42)])
        for dx in (-14, 14):
            pygame.draw.circle(s, (255, 240, 80), (cx + dx, cy - 15), 8)
            pygame.draw.circle(s, BLACK, (cx + dx, cy - 15), 3)
        pygame.draw.polygon(s, WHITE, [(cx - 10, cy + 8), (cx - 5, cy + 22), (cx, cy + 8)])
        pygame.draw.polygon(s, WHITE, [(cx + 10, cy + 8), (cx + 5, cy + 22), (cx, cy + 8)])
    elif name == "ゴースト":
        c = (225, 225, 240)
        pygame.draw.circle(s, c, (cx, cy - 20), 55)
        pygame.draw.rect(s, c, (cx - 55, cy - 20, 110, 75))
        for i in range(4):
            pygame.draw.circle(s, BLACK, (cx - 41 + i * 27, cy + 58), 14)
        for dx in (-22, 22):
            pygame.draw.ellipse(s, (30, 30, 60), (cx + dx - 11, cy - 38, 22, 30))
        pygame.draw.ellipse(s, (30, 30, 60), (cx - 12, cy + 8, 24, 20))
        for dx in (-62, 62):
            pygame.draw.ellipse(s, c, (cx + dx - 14, cy - 5, 28, 50))
    elif name == "おおサソリ":
        c = (205, 80, 40)
        for i in range(4):
            pygame.draw.line(s, (130, 40, 20), (cx - 40 + i * 25, cy + 30), (cx - 55 + i * 30, cy + 62), 5)
        pygame.draw.ellipse(s, c, (cx - 62, cy - 10, 124, 72))
        for px, py in ((cx + 62, cy + 10), (cx + 82, cy - 12), (cx + 86, cy - 38), (cx + 72, cy - 60), (cx + 48, cy - 70)):
            pygame.draw.circle(s, c, (px, py), 13)
        pygame.draw.polygon(s, (255, 220, 60), [(cx + 40, cy - 66), (cx + 20, cy - 56), (cx + 42, cy - 52)])
        for sg in (-1,):
            pygame.draw.polygon(s, c, [(cx - 62, cy + 5), (cx - 100, cy - 25), (cx - 112, cy - 5), (cx - 95, cy + 5), (cx - 112, cy + 20), (cx - 85, cy + 25)])
        for dx in (-25, 5):
            pygame.draw.circle(s, WHITE, (cx + dx, cy + 8), 7)
            pygame.draw.circle(s, BLACK, (cx + dx, cy + 8), 3)
    elif name == "ゴーレム":
        c, d = (135, 135, 150), BLACK
        for r in ((cx - 42, cy + 70, 30, 38), (cx + 12, cy + 70, 30, 38), (cx - 48, cy - 32, 96, 104),
                  (cx - 90, cy - 28, 38, 95), (cx + 52, cy - 28, 38, 95), (cx - 30, cy - 75, 60, 46)):
            pygame.draw.rect(s, c, r)
            pygame.draw.rect(s, d, r, 3)
        for dx in (-16, 6):
            pygame.draw.rect(s, (255, 220, 0), (cx + dx, cy - 58, 12, 9))
        pygame.draw.line(s, d, (cx - 20, cy - 10), (cx + 5, cy + 20), 3)
        pygame.draw.line(s, d, (cx + 5, cy + 20), (cx - 5, cy + 50), 3)
    else:  # まおう
        pygame.draw.polygon(s, (60, 30, 90), [(cx - 85, cy + 110), (cx - 42, cy - 30), (cx + 42, cy - 30), (cx + 85, cy + 110)])
        pygame.draw.polygon(s, (110, 20, 40), [(cx - 30, cy - 30), (cx, cy + 110), (cx + 30, cy - 30)])
        pygame.draw.ellipse(s, (110, 160, 100), (cx - 32, cy - 95, 64, 70))
        for sg in (-1, 1):
            pygame.draw.polygon(s, (230, 220, 190), [(cx + sg * 22, cy - 85), (cx + sg * 50, cy - 125), (cx + sg * 38, cy - 78)])
            pygame.draw.polygon(s, (60, 30, 90), [(cx + sg * 40, cy - 25), (cx + sg * 110, cy + 20), (cx + sg * 92, cy + 35), (cx + sg * 36, cy + 5)])
            pygame.draw.circle(s, (255, 40, 40), (cx + sg * 13, cy - 62), 6)
        pygame.draw.line(s, BLACK, (cx - 14, cy - 40), (cx + 14, cy - 40), 3)


# ------------------------------------------------------------ 主人公
class Hero:
    def __init__(self):
        self.name = "ゆうしゃ"
        self.lv, self.exp, self.gold, self.herbs = 1, 0, 0, 0
        self.weapon, self.armor = 0, 0
        self.hp, self.mp = self.maxhp, self.maxmp

    maxhp = property(lambda s: LV_TABLE[s.lv - 1][2])
    maxmp = property(lambda s: LV_TABLE[s.lv - 1][3])
    atk = property(lambda s: LV_TABLE[s.lv - 1][0] + WEAPONS[s.weapon][1])
    defense = property(lambda s: LV_TABLE[s.lv - 1][1] // 2 + ARMORS[s.armor][1])
    agi = property(lambda s: LV_TABLE[s.lv - 1][1])

    def spells(self):
        return [(n, mp) for n, (lv, mp) in SPELLS.items() if self.lv >= lv]


# ------------------------------------------------------------ ゲーム本体
class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((W, H))
        pygame.display.set_caption("ミニクエスト")
        self.canvas = pygame.Surface((W, H))
        self.f, self.fb, self.fs = load_font(22), load_font(44), load_font(18)
        self.tiles = make_tiles()
        self.hero_img = [make_hero(0), make_hero(1)]
        self.map, self.castle_pos, self.town_pos, self.boss_pos = build_map()
        self.mw, self.mh = len(self.map[0]), len(self.map)
        self.pages, self.pi, self.char, self.then = [], 0, 0.0, None
        self.choice = None
        self.show_status = False
        self.en = None
        self.blink = self.shake = self.flash = 0.0
        self.moving, self.mv_t, self.mv_from, self.mv_to = False, 0.0, (0, 0), (0, 0)
        self.walk_frame, self.face = 0, 1
        self.hero = Hero()
        self.px, self.py = self.castle_pos[0], self.castle_pos[1] + 1
        self.flags = {"king": False}
        self.mode = "title"
        self.title_menu()

    # ---------- ユーティリティ
    def tile(self, x, y):
        if 0 <= x < self.mw and 0 <= y < self.mh:
            return self.map[y][x]
        return "~"

    def wrap(self, text, width=540):
        out = []
        for para in text.split("\n"):
            line = ""
            for ch in para:
                if self.f.size(line + ch)[0] > width:
                    out.append(line)
                    line = ch
                else:
                    line += ch
            out.append(line)
        return "\n".join(out)

    def say(self, *pages, then=None):
        self.pages = [self.wrap(p) for p in pages]
        self.pi, self.char, self.then = 0, 0.0, then

    def open_choice(self, opts, cb, pos=(175, 30), cancel=None):
        self.choice = {"opts": opts, "cur": 0, "cb": cb, "pos": pos, "cancel": cancel}

    def zone(self):
        if self.py < 9:
            return 5
        d = math.hypot(self.px - self.castle_pos[0], self.py - self.castle_pos[1])
        return min(4, int(d // 8))

    # ---------- タイトル / セーブ
    def title_menu(self):
        opts = ["はじめから"] + (["つづきから"] if os.path.exists(SAVE_PATH) else [])
        self.open_choice(opts, lambda i: self.new_game() if i == 0 else self.load_game(), pos=(245, 320))

    def new_game(self):
        self.hero = Hero()
        self.px, self.py = self.castle_pos[0], self.castle_pos[1] + 1
        self.flags = {"king": False}
        self.mode = "field"
        self.say("ときは いま。 せかいは まおうの\nやぼうに ふるえていた……",
                 "ゆうしゃよ ぼうけんの たびに でよう!\nまずは おしろの おうさまに あいに ゆこう。")

    def save_game(self):
        d = {"hero": vars(self.hero), "px": self.px, "py": self.py, "flags": self.flags}
        with open(SAVE_PATH, "w", encoding="utf-8") as fp:
            json.dump(d, fp, ensure_ascii=False)

    def load_game(self):
        try:
            with open(SAVE_PATH, encoding="utf-8") as fp:
                d = json.load(fp)
            self.hero = Hero()
            self.hero.__dict__.update(d["hero"])
            self.px, self.py, self.flags = d["px"], d["py"], d["flags"]
            self.mode = "field"
            self.say("ぼうけんのしょを よみこみました。")
        except Exception:
            self.new_game()

    # ---------- 入力
    def on_key(self, k):
        confirm = k in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_z, pygame.K_SPACE)
        cancel = k in (pygame.K_ESCAPE, pygame.K_x, pygame.K_BACKSPACE)
        if self.pages:
            if confirm:
                self.advance_msg()
            return
        if self.choice:
            ch = self.choice
            if k in (pygame.K_UP, pygame.K_w):
                ch["cur"] = (ch["cur"] - 1) % len(ch["opts"])
            elif k in (pygame.K_DOWN, pygame.K_s):
                ch["cur"] = (ch["cur"] + 1) % len(ch["opts"])
            elif confirm:
                self.choice = None
                ch["cb"](ch["cur"])
            elif cancel and ch["cancel"]:
                self.choice = None
                ch["cancel"]()
            return
        if self.show_status:
            if confirm or cancel:
                self.show_status = False
            return
        if self.mode == "ending":
            if confirm:
                self.mode = "title"
                self.title_menu()
            return
        if self.mode == "field" and not self.moving and confirm:
            self.field_menu()

    def advance_msg(self):
        if self.char < len(self.pages[self.pi]):
            self.char = len(self.pages[self.pi])
            return
        self.pi += 1
        if self.pi >= len(self.pages):
            self.pages, cb, self.then = [], self.then, None
            if cb:
                cb()
        else:
            self.char = 0.0

    # ---------- フィールドメニュー
    def field_menu(self):
        self.open_choice(["じゅもん", "どうぐ", "つよさ"], self.field_cmd, cancel=lambda: None)

    def field_cmd(self, i):
        h = self.hero
        if i == 0:
            sp = h.spells()
            if not sp:
                self.say("まだ じゅもんを おぼえていない。")
                return
            self.open_choice([f"{n} MP{mp}" for n, mp in sp], lambda j: self.field_spell(sp[j]),
                             cancel=self.field_menu)
        elif i == 1:
            if h.herbs <= 0:
                self.say("どうぐを なにも もっていない。")
                return
            self.open_choice([f"やくそう x{h.herbs}"], lambda j: self.use_herb(False), cancel=self.field_menu)
        else:
            self.show_status = True

    def field_spell(self, sp):
        n, mp = sp
        h = self.hero
        if n != "ヒール":
            self.say("ここでは つかえない。")
        elif h.mp < mp:
            self.say("MPが たりない!")
        else:
            h.mp -= mp
            v = random.randint(15, 25)
            h.hp = min(h.maxhp, h.hp + v)
            self.say(f"{h.name}は ヒールを となえた!\nHPが {v}ポイント かいふくした!")

    def use_herb(self, in_battle):
        h = self.hero
        h.herbs -= 1
        v = random.randint(25, 35)
        h.hp = min(h.maxhp, h.hp + v)
        msg = f"{h.name}は やくそうを つかった!\nHPが {v}ポイント かいふくした!"
        self.say(msg, then=self.enemy_turn if in_battle else None)

    # ---------- 移動
    def can_move(self):
        return (self.mode == "field" and not self.pages and not self.choice
                and not self.show_status and not self.moving)

    def update_move(self, dt):
        if self.moving:
            self.mv_t += dt / 0.15
            if self.mv_t >= 1:
                self.moving = False
                self.px, self.py = self.mv_to
                self.walk_frame ^= 1
                self.on_step()
            return
        if not self.can_move():
            return
        k = pygame.key.get_pressed()
        dx = dy = 0
        if k[pygame.K_LEFT] or k[pygame.K_a]:
            dx = -1
        elif k[pygame.K_RIGHT] or k[pygame.K_d]:
            dx = 1
        elif k[pygame.K_UP] or k[pygame.K_w]:
            dy = -1
        elif k[pygame.K_DOWN] or k[pygame.K_s]:
            dy = 1
        if dx or dy:
            if dx:
                self.face = dx
            nx, ny = self.px + dx, self.py + dy
            if self.tile(nx, ny) in WALKABLE:
                self.moving, self.mv_t = True, 0.0
                self.mv_from, self.mv_to = (self.px, self.py), (nx, ny)

    def on_step(self):
        t = self.tile(self.px, self.py)
        if t == "C":
            return self.ev_castle()
        if t == "V":
            return self.ev_town()
        if t == "D":
            return self.ev_boss()
        d = math.hypot(self.px - self.castle_pos[0], self.py - self.castle_pos[1])
        rate = {".": 0.08, "T": 0.14}.get(t, 0)
        if d < 3:
            rate = 0
        if random.random() < rate:
            self.flash = 0.35
            self.start_battle(random.choice(ZONES[self.zone()]))

    # ---------- 城 / 町 / ボス
    def ev_castle(self):
        h = self.hero

        def menu():
            self.open_choice(["おうさまと はなす", "ぼうけんを きろくする", "やすませてもらう", "でる"],
                             cmd, pos=(175, 30), cancel=lambda: None)

        def cmd(i):
            if i == 0:
                self.say("おうさま「ゆうしゃよ まおうは\nきたの しまの しろに おる。\nはしを わたって うちたおすのじゃ!」",
                         then=menu)
            elif i == 1:
                self.save_game()
                self.say("ぼうけんのしょに きろくしました。", then=menu)
            elif i == 2:
                h.hp, h.mp = h.maxhp, h.maxmp
                self.say("ゆっくり やすんだ。 HPと MPが\nぜんかいふくした!", then=menu)

        if not self.flags["king"]:
            self.flags["king"] = True
            self.say("おうさま「おお ゆうしゃよ! よくぞ きた!\nまおうを たおし この せかいに\nへいわを とりもどしてくれ!」",
                     "おうさま「まずは そとで てきを たおして\nちからを つけるのじゃ。 ゆけ!」",
                     then=menu)
        else:
            self.say("おうさま「おお ゆうしゃよ! よくぞ もどった!」", then=menu)

    def ev_town(self):
        h = self.hero

        def menu():
            self.open_choice(["やどや", "どうぐや", "でる"], cmd, pos=(175, 30), cancel=lambda: None)

        def cmd(i):
            if i == 0:
                self.open_choice([f"とまる ({INN_PRICE}G)", "やめる"], inn, pos=(175, 30), cancel=menu)
            elif i == 1:
                shop()

        def inn(i):
            if i == 1:
                return menu()
            if h.gold < INN_PRICE:
                return self.say("おかねが たりません。", then=menu)
            h.gold -= INN_PRICE
            h.hp, h.mp = h.maxhp, h.maxmp
            self.say("ゆっくり おやすみなさい……", "おはようございます! HPと MPが\nぜんかいふくしました!", then=menu)

        def shop():
            labels = [f"{n} {p}G" for n, p, _, _ in SHOP] + ["やめる"]
            self.open_choice(labels, buy, pos=(175, 30), cancel=menu)

        def buy(i):
            if i >= len(SHOP):
                return menu()
            n, p, kind, idx = SHOP[i]
            if h.gold < p:
                return self.say("おかねが たりません。", then=shop)
            if kind == "herb":
                if h.herbs >= 9:
                    return self.say("それいじょうは もてません。", then=shop)
                h.herbs += 1
            elif kind == "weapon":
                if h.weapon >= idx:
                    return self.say("いまの ぶきの ほうが\nつよいですよ。", then=shop)
                h.weapon = idx
            else:
                if h.armor >= idx:
                    return self.say("いまの ぼうぐの ほうが\nじょうぶですよ。", then=shop)
                h.armor = idx
            h.gold -= p
            self.say(f"{n}を かいました。 まいどあり!", then=shop)

        self.say("ようこそ! ここは ちいさな まちです。", then=menu)

    def ev_boss(self):
        self.say("ここは まおうの しろ……\nおくから おそろしい けはいが する!",
                 then=lambda: self.start_battle("まおう"))

    # ---------- 戦闘
    def start_battle(self, name):
        hp, atk, df, exp, gold = ENEMIES[name]
        self.en = {"name": name, "hp": hp, "atk": atk, "def": df, "exp": exp, "gold": gold,
                   "boss": name == "まおう"}
        self.mode = "battle"
        self.say(f"{name}が あらわれた!", then=self.battle_menu)

    def battle_menu(self):
        self.open_choice(["たたかう", "じゅもん", "どうぐ", "にげる"], self.b_cmd)

    def b_cmd(self, i):
        h = self.hero
        if i == 0:
            self.player_attack()
        elif i == 1:
            sp = h.spells()
            if not sp:
                return self.say("まだ じゅもんを おぼえていない。", then=self.battle_menu)
            self.open_choice([f"{n} MP{mp}" for n, mp in sp], lambda j: self.b_spell(sp[j]),
                             cancel=self.battle_menu)
        elif i == 2:
            if h.herbs <= 0:
                return self.say("どうぐを なにも もっていない。", then=self.battle_menu)
            self.open_choice([f"やくそう x{h.herbs}"], lambda j: self.use_herb(True), cancel=self.battle_menu)
        else:
            if self.en["boss"]:
                return self.say("にげられない!", then=self.enemy_turn)
            if random.random() < 0.55:
                self.say(f"{h.name}は にげだした!", then=self.end_battle)
            else:
                self.say("しかし まわりこまれてしまった!", then=self.enemy_turn)

    def player_attack(self):
        h, en = self.hero, self.en
        if random.random() < 1 / 32:
            dmg = random.randint(h.atk // 2, h.atk)
            msg = f"{h.name}の こうげき!\nかいしんの いちげき! {dmg}ポイント!"
        elif random.random() < 1 / 40:
            self.say(f"{h.name}の こうげき!\nミス! {en['name']}は ひらりと かわした!", then=self.enemy_turn)
            return
        else:
            base = max(1, h.atk - en["def"] // 2)
            dmg = random.randint(max(1, base // 2), max(1, base))
            msg = f"{h.name}の こうげき!\n{en['name']}に {dmg}ポイントの ダメージ!"
        en["hp"] -= dmg
        self.blink = 0.35
        self.say(msg, then=self.after_player)

    def b_spell(self, sp):
        n, mp = sp
        h, en = self.hero, self.en
        if h.mp < mp:
            return self.say("MPが たりない!", then=self.battle_menu)
        h.mp -= mp
        if n == "ヒール":
            v = random.randint(15, 25)
            h.hp = min(h.maxhp, h.hp + v)
            self.say(f"{h.name}は ヒールを となえた!\nHPが {v}ポイント かいふくした!", then=self.enemy_turn)
        else:
            dmg = random.randint(8, 16) + h.lv
            en["hp"] -= dmg
            self.blink = 0.35
            self.say(f"{h.name}は ファイアを となえた!\n{en['name']}に {dmg}ポイントの ダメージ!",
                     then=self.after_player)

    def after_player(self):
        if self.en["hp"] <= 0:
            self.win()
        else:
            self.enemy_turn()

    def enemy_turn(self):
        h, en = self.hero, self.en
        if en["boss"] and random.random() < 0.33:
            dmg = random.randint(12, 22)
            msg = f"{en['name']}は ほのおを はいた!\n{h.name}は {dmg}ポイントの ダメージ!"
        elif random.random() < 1 / 30:
            dmg = 0
            msg = f"{en['name']}の こうげき!\nミス! ダメージを うけない!"
        else:
            base = max(1, en["atk"] - h.defense // 2)
            dmg = random.randint(max(1, base // 2), max(1, base))
            msg = f"{en['name']}の こうげき!\n{h.name}は {dmg}ポイントの ダメージを うけた!"
        h.hp = max(0, h.hp - dmg)
        if dmg:
            self.shake = 0.3
        self.say(msg, then=self.after_enemy)

    def after_enemy(self):
        if self.hero.hp <= 0:
            self.say(f"{self.hero.name}は しんでしまった……", then=self.revive)
        else:
            self.battle_menu()

    def revive(self):
        h = self.hero
        h.hp, h.mp, h.gold = h.maxhp, h.maxmp, h.gold // 2
        self.px, self.py = self.castle_pos[0], self.castle_pos[1] + 1
        self.en, self.mode = None, "field"
        self.say("おうさま「おお ゆうしゃよ! しんでしまうとは\nなさけない!」",
                 "おうさま「ゴールドは はんぶん うばわれたが\nいのちは とりとめた。 また がんばるのじゃ!」")

    def win(self):
        h, en = self.hero, self.en
        pages = [f"{en['name']}を たおした!"]
        if not en["boss"]:
            pages.append(f"けいけんち {en['exp']}ポイントと\n{en['gold']}ゴールドを かくとく!")
        h.exp += en["exp"]
        h.gold += en["gold"]
        old, ohp, omp = h.lv, h.maxhp, h.maxmp
        while h.lv < MAX_LV and h.exp >= EXP_TABLE[h.lv]:
            h.lv += 1
        if h.lv > old:
            h.hp += h.maxhp - ohp
            h.mp += h.maxmp - omp
            pages.append(f"{h.name}は レベル{h.lv}に あがった!\nさいだいHP {ohp}→{h.maxhp}")
            for n, (lv, _) in SPELLS.items():
                if old < lv <= h.lv:
                    pages.append(f"{n}の じゅもんを おぼえた!")
        if en["boss"]:
            pages += ["まおうは くずれさり おそろしい けはいは\nきえさった……",
                      "こうして せかいに へいわが もどった。\nゆうしゃの でんせつは かたりつがれるだろう……"]
            self.say(*pages, then=lambda: setattr(self, "mode", "ending"))
        else:
            self.say(*pages, then=self.end_battle)

    def end_battle(self):
        self.en, self.mode = None, "field"

    # ---------- 更新
    def update(self, dt):
        if self.pages and self.char < len(self.pages[self.pi]):
            self.char += dt * 45
        self.blink = max(0, self.blink - dt)
        self.shake = max(0, self.shake - dt)
        self.flash = max(0, self.flash - dt)
        self.update_move(dt)

    # ---------- 描画
    def win_box(self, rect):
        r = pygame.Rect(rect)
        pygame.draw.rect(self.canvas, BLACK, r, border_radius=6)
        pygame.draw.rect(self.canvas, WHITE, r, 3, border_radius=6)

    def txt(self, s, x, y, lh=30, font=None, col=WHITE):
        for i, line in enumerate(s.split("\n")):
            self.canvas.blit((font or self.f).render(line, True, col), (x, y + i * lh))

    def draw_status(self):
        h = self.hero
        self.win_box((30, 30, 135, 172))
        self.txt(f"{h.name}\nLV {h.lv:>3}\nHP {h.hp:>3}\nMP {h.mp:>3}\nG {h.gold:>5}\nE {h.exp:>5}",
                 42, 38, lh=25, font=self.f)

    def draw_field(self):
        c = self.canvas
        cx, cy = float(self.px), float(self.py)
        if self.moving:
            t = min(1.0, self.mv_t)
            cx = self.mv_from[0] + (self.mv_to[0] - self.mv_from[0]) * t
            cy = self.mv_from[1] + (self.mv_to[1] - self.mv_from[1]) * t
        ox = int(round(OX + (VW // 2) * TILE - cx * TILE))
        oy = int(round(OY + (VH // 2) * TILE - cy * TILE))
        c.set_clip(pygame.Rect(OX, OY, VW * TILE, VH * TILE))
        for j in range(int(cy) - VH // 2 - 2, int(cy) + VH // 2 + 3):
            for i in range(int(cx) - VW // 2 - 2, int(cx) + VW // 2 + 3):
                c.blit(self.tiles[self.tile(i, j)], (ox + i * TILE, oy + j * TILE))
        img = self.hero_img[self.walk_frame if self.moving else 0]
        if self.face < 0:
            img = pygame.transform.flip(img, True, False)
        c.blit(img, (OX + (VW // 2) * TILE, OY + (VH // 2) * TILE))
        c.set_clip(None)
        pygame.draw.rect(c, WHITE, (OX - 2, OY - 2, VW * TILE + 4, VH * TILE + 4), 2)
        if not self.show_status and self.mode == "field":
            self.draw_status()

    def draw_battle(self):
        c = self.canvas
        c.fill(BLACK)
        pygame.draw.rect(c, WHITE, (OX - 2, OY - 2, VW * TILE + 4, VH * TILE + 4), 2)
        en = self.en
        if en and en["hp"] > 0 and not (self.blink > 0 and int(self.blink * 20) % 2 == 0):
            draw_enemy(c, en["name"], 340, 215)
        self.draw_status()

    def draw_title(self):
        c = self.canvas
        c.fill((10, 10, 60))
        for i in range(60):
            x, y = (i * 97) % W, (i * 53) % 260
            pygame.draw.rect(c, (200, 200, 255), (x, y, 2, 2))
        t = self.fb.render("ミニクエスト", True, (255, 230, 120))
        c.blit(t, (W // 2 - t.get_width() // 2, 120))
        s = self.f.render("~ まおうを たおして せかいを すくえ ~", True, WHITE)
        c.blit(s, (W // 2 - s.get_width() // 2, 190))
        h = self.fs.render("いどう: 矢印/WASD   けってい・メニュー: Z/Enter   キャンセル: X/Esc", True, (180, 180, 220))
        c.blit(h, (W // 2 - h.get_width() // 2, 430))

    def draw_overlays(self):
        c = self.canvas
        if self.show_status:
            h = self.hero
            self.win_box((90, 40, 460, 290))
            eq = f"{WEAPONS[h.weapon][0]} / {ARMORS[h.armor][0]}"
            nxt = EXP_TABLE[h.lv] - h.exp if h.lv < MAX_LV else 0
            lines = (f"{h.name}   レベル {h.lv}\nHP {h.hp}/{h.maxhp}   MP {h.mp}/{h.maxmp}\n"
                     f"こうげき {h.atk}   ぼうぎょ {h.defense}\nけいけんち {h.exp}  (つぎまで {nxt})\n"
                     f"ゴールド {h.gold}   やくそう {h.herbs}\nそうび {eq}")
            self.txt(lines, 112, 56, lh=38)
        if self.choice:
            ch = self.choice
            wd = max(self.f.size(o)[0] for o in ch["opts"]) + 56
            x, y = ch["pos"]
            self.win_box((x, y, wd, len(ch["opts"]) * 32 + 22))
            for i, o in enumerate(ch["opts"]):
                if i == ch["cur"]:
                    pygame.draw.polygon(c, WHITE, [(x + 14, y + 16 + i * 32), (x + 14, y + 32 + i * 32),
                                                   (x + 28, y + 24 + i * 32)])
                c.blit(self.f.render(o, True, WHITE), (x + 36, y + 12 + i * 32))
        if self.pages:
            self.win_box((30, 345, 580, 120))
            self.txt(self.pages[self.pi][:int(self.char)], 50, 358)
            if self.char >= len(self.pages[self.pi]) and int(pygame.time.get_ticks() / 400) % 2 == 0:
                pygame.draw.polygon(c, WHITE, [(578, 440), (594, 440), (586, 452)])

    def draw(self):
        c = self.canvas
        c.fill(BLACK)
        if self.mode == "title":
            self.draw_title()
        elif self.mode == "battle":
            self.draw_battle()
        elif self.mode == "ending":
            t = self.fb.render("THE END", True, (255, 230, 120))
            c.blit(t, (W // 2 - t.get_width() // 2, 180))
            s = self.f.render("あそんでくれて ありがとう!   (Z/Enterで タイトルへ)", True, WHITE)
            c.blit(s, (W // 2 - s.get_width() // 2, 260))
        else:
            self.draw_field()
        self.draw_overlays()
        if self.flash > 0:
            ov = pygame.Surface((W, H))
            ov.fill(WHITE)
            ov.set_alpha(int(255 * self.flash / 0.35))
            c.blit(ov, (0, 0))
        off = (0, 0)
        if self.shake > 0:
            off = (random.randint(-6, 6), random.randint(-6, 6))
        self.screen.fill(BLACK)
        self.screen.blit(c, off)
        pygame.display.flip()


def main():
    g = Game()
    clock = pygame.time.Clock()
    while True:
        dt = clock.tick(60) / 1000.0
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if e.type == pygame.KEYDOWN:
                g.on_key(e.key)
        g.update(dt)
        g.draw()


if __name__ == "__main__":
    main()