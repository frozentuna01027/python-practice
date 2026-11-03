"""
無人島脱出ゲーム
木片10個でボート脱出。体力は1分で0→ヤシの実(E)で半分回復。🥺に捕まる／体力0でゲームオーバー
謎1：切り株の紙(E)→小屋の「敵の首」2つをE長押し(10秒)で回収→敵が消える
謎2：👈😁👉にE→🫵🫪🫵が4秒後に追跡→😁の生首6つをジャンプで踏みつぶす
操作: WASD=移動 / Q長押し=ダッシュ / Space=ジャンプ / E=調べる / Enter=再スタート / Esc=終了 / ;=デバッグメニュー
"""
from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController
import math, os, random, shutil

app = Ursina(title='Island')
random.seed(1)
font = application.asset_folder / 'msgothic.ttc'      # 日本語フォント：Windows標準のMSゴシックをこのフォルダにコピーして使う
if not font.exists() and os.path.exists(r'C:\Windows\Fonts\msgothic.ttc'):
    shutil.copy(r'C:\Windows\Fonts\msgothic.ttc', font)
if font.exists():
    Text.default_font = font.name

# ===== 設定 =====
SIZE = 80                                             # 島の半径
WALK_SPEED, DASH_SPEED = 5, 9                         # 歩き／Qダッシュ
ENEMY_SPEED, CHASE_RANGE = 4.5, 25                    # 敵：歩きより少し遅い／この距離に入ると追ってくる
ENEMY_STARTS = [(0, 60), (-45, -35), (45, -40), (-35, 45), (55, 15)]
BOSS_SPEED, BOSS_WAIT = 7, 4                          # ボス：歩きでは追いつかれ、ダッシュなら逃げ切れる／動き出すまでの秒数
HP_MAX = 100
HP_DRAIN = HP_MAX / 60                                # 何もしないと60秒で体力0
DEBUG_KEY = ';'

# ===== 1. 地形：高さの関数 → 格子点 → 三角形でつなぐ =====
def height(x, z):
    d = math.hypot(x, z) / SIZE
    h = (1 - d * d) * 8 - 1                                         # お椀を伏せた形
    return max(h + math.sin(x * 0.1) * math.cos(z * 0.12) * 1.5 * (1 - d), -3)   # ＋起伏

def ground_color(x, h, z):                                          # 高さと場所で地面の色を変える
    k = (math.sin(x * 0.35) * math.cos(z * 0.3) + 1) / 2            # 0〜1のまだら模様
    if h < 0.3:
        return color.rgb32(200, 180, 130)                           # 波打ち際の濡れた砂
    if h < 1:
        return color.rgb32(235, 215, 155)                           # 砂浜
    if h > 6.5:
        return color.rgb32(135, 130, 115)                           # 山頂は岩
    return color.rgb32(55 + 30 * k, 125 + 30 * k, 45 + 15 * k)      # 草地（濃い緑〜明るい緑のまだら）

n = 50                                                              # 格子の数（1辺）
verts = [(x, height(x, z), z) for x in range(-100, 101, 4) for z in range(-100, 101, 4)]
colors = [ground_color(*v) for v in verts]
tris = []
for i in range(n):
    for j in range(n):
        a = i * (n + 1) + j
        # ★修正：上から見て反時計回りに張る（法線が +y を向く）。元の (a, a+n+1, a+1) は時計回りで法線が真下を向き、地面が裏返っていた
        tris += [(a, a + 1, a + n + 1), (a + 1, a + n + 2, a + n + 1)]
Entity(model=Mesh(vertices=verts, triangles=tris, colors=colors), collider='mesh', double_sided=True)
sea = Entity(model='plane', scale=500, color=color.rgba32(30, 110, 190, 200))      # 海
SKY_BLUE, SKY_DARK = color.rgb32(20, 130, 255), color.rgb32(25, 15, 45)
sky = Sky(texture=None, color=SKY_BLUE)

# ===== 2. 共通パーツ =====
def beam(col, parent=scene, pos=(0, 10, 0)):          # 目印の光の柱
    return Entity(parent=parent, model='cube', position=pos, scale=(0.08, 20, 0.08), color=col)

def draw(e, parts):                                   # 部品の表 (形, 位置, 大きさ, 色[, 傾き]) から立体を組み立てる
    for model, pos, scale, col, *tilt in parts:
        Entity(parent=e, model=model, position=pos, scale=scale, color=col, rotation_z=tilt[0] if tilt else 0)

def build(cx, cz, walls, tex='brick', col=color.white, lift=0):   # 壁の表 (ずれx, ずれz, 横幅, 奥行, 高さ) から建物を作る
    y0 = height(cx, cz) + lift
    for dx, dz, w, d, h in walls:
        Entity(model='cube', position=(cx + dx, y0 + h / 2, cz + dz), scale=(w, h, d), color=col,
               texture=tex, texture_scale=(max(w, d) / 2, h / 2), collider='box')

build(0, 10, [(-5, 0, 0.5, 10, 3.0), (5, 0, 0.5, 10, 1.5), (-3, 5, 4, 0.5, 3.5), (3, 5, 4, 0.5, 1.0),
              (-3, -5, 4, 0.5, 2.5), (2, -5, 3, 0.5, 3.0), (-5, -5, 1, 1, 4.5)])           # 遺跡（レンガの壁）
HUTS = [(25, -10), (-50, 5)]                          # 廃墟小屋2つ（朽ちた木の壁＋一部だけ残った屋根。入口は手前中央）
for x, z in HUTS:
    build(x, z, [(0, 2.5, 5, 0.3, 3.0), (-2.5, 0, 0.3, 5, 3.0), (2.5, 0, 0.3, 5, 1.8),
                 (-1.5, -2.5, 2, 0.3, 3.0), (1.8, -2.5, 1.4, 0.3, 1.4)], None, color.rgb32(110, 85, 60), -0.4)
    build(x - 1, z + 1, [(0, 0, 3, 3.5, 0.2)], None, color.rgb32(70, 55, 40), 2.6)

# ===== 3. ヤシの木と、その下のヤシの実（2本に1本・2つずつ） =====
rng = random.Random(7)                                # 装飾用の乱数（ゲームの配置に影響しないよう別にする）
decor = Entity()                                      # 装飾の親。小物を子として置き、最後にcombine()で1つにまとめる
coconut_spots, count = [], 0
for _ in range(60):
    x, z = random.uniform(-SIZE, SIZE), random.uniform(-SIZE, SIZE)
    if 0.5 < height(x, z) < 4:
        y = height(x, z)
        Entity(model='cube', position=(x, y + 2.5, z), scale=(0.4, 5, 0.4), color=color.rgb32(110, 80, 50), collider='box')   # 幹
        Entity(model='sphere', position=(x, y + 5.5, z), scale=(4, 1.5, 4), color=color.rgb32(40, 140, 50))                    # 葉
        for k in range(6):                                                                                                      # 垂れ下がるヤシの葉
            a = math.radians(k * 60)
            Entity(parent=decor, model='cube', position=(x + math.sin(a) * 1.2, y + 4.75, z + math.cos(a) * 1.2),
                   rotation=(25, k * 60, 0), scale=(0.6, 0.05, 2.7), color=color.rgb32(30 + k * 6, 130, 45))
        count += 1
        if count % 2 == 0:
            coconut_spots += [(x + 0.9, z + 0.3), (x - 0.8, z - 0.4)]

# ===== 4. アイテム：木片・ボート・切り株の紙 =====
spots = [(0, 10), (-30, -20), (20, -30), (-40, 20), (35, 25), (10, 40), (-15, -50), (50, -10), (-55, -10), (45, 45)]
head_spots = [(x - 1, z + 1.2) for x, z in HUTS]                 # 敵の首：各小屋の中に1つずつ
stomp_spots = [(70 * math.cos(math.radians(a)), 70 * math.sin(math.radians(a))) for a in (30, 100, 170, 240, 320)] + [(0, 0)]   # 海岸5＋中央1

def wood(x, z):
    w = Entity(position=(x, height(x, z) + 0.5, z), collider='box')            # 当たり判定(1m立方)
    Entity(parent=w, model='cube', scale=(1, 0.25, 0.25), color=color.orange)
    beam(color.yellow, w)
    return w

def coconut(x, z):
    return Entity(model='sphere', position=(x, height(x, z) + 0.2, z), scale=0.45, color=color.rgb32(110, 70, 35), collider='box')

def make_boat():                                                               # 部品をshipの子にして、まとめて消せるように
    ship = Entity(position=(0, height(0, -72) + 0.4, -72))
    draw(ship, [('cube', (0, 3, 0), (0.2, 5, 0.2), color.dark_gray), ('cube', (0, 3.5, 0), (0.05, 3, 3), color.white)])   # マスト・帆
    beam(color.cyan, ship)
    return Entity(parent=ship, model='cube', scale=(7, 1, 3), color=color.rgb32(120, 80, 50), collider='box')            # 船体

y = height(-60, 20)                                                            # 切り株と白い紙：スタート地点から遠い場所
stump = Entity(model='cube', position=(-60, y + 0.4, 20), scale=(1.4, 0.8, 1.4), color=color.rgb32(100, 70, 40), collider='box')
Entity(model='cube', position=(-60, y + 0.85, 20), scale=(0.6, 0.05, 0.8), rotation_y=25)
beam(color.white, pos=(-60, y + 10, 20))

# ===== 4.5 装飾：小物を大量に置き、最後に combine() で1つにまとめて軽くする =====
KEEP = [(0, 10, 8), (25, -10, 5), (-50, 5, 5), (-60, 20, 4), (0, -50, 4), (6, -56, 4), (0, -72, 8)]   # 置かない場所：建物・切り株・出発地点・焚き火・ボート

def scatter(n, hmin, hmax):                           # 高さが範囲内でKEEPの外にある場所を、ランダムにn個選ぶ
    pts = []
    while len(pts) < n:
        x, z = rng.uniform(-75, 75), rng.uniform(-75, 75)
        if hmin < height(x, z) < hmax and all(math.hypot(x - kx, z - kz) > kr for kx, kz, kr in KEEP):
            pts.append((x, z))
    return pts

def deco(model, x, z, scale, col, lift=0, **kw):      # 地面の高さ+liftの位置に小物を1つ置く
    return Entity(parent=decor, model=model, position=(x, height(x, z) + lift, z), scale=scale, color=col, **kw)

for x, z in scatter(50, 0.2, 6):                      # 岩
    s, g = rng.uniform(0.5, 1.6), rng.uniform(100, 150)
    deco('cube', x, z, (s * 1.3, s, s), color.rgb32(g, g, g - 10), s / 3, rotation=(rng.uniform(0, 30), rng.uniform(0, 360), 0))
for x, z in scatter(60, 1.2, 5):                      # 茂み
    s = rng.uniform(1, 1.8)
    deco('icosphere', x, z, (s * 1.3, s, s * 1.3), color.rgb32(30, rng.uniform(95, 130), 40), s * 0.4)
for cx, cz in scatter(24, 1.2, 5):                    # 花畑：色とりどりの花を6本ずつ
    col = rng.choice([color.red, color.yellow, color.pink, color.white, color.violet])
    for _ in range(6):
        deco('diamond', cx + rng.uniform(-1.5, 1.5), cz + rng.uniform(-1.5, 1.5), (0.25, 0.4, 0.25), col, 0.25)
for x, z in scatter(220, 1.0, 5.5):                    # 草むら：細い葉を3枚ずつ
    for _ in range(3):
        deco('quad', x + rng.uniform(-0.3, 0.3), z + rng.uniform(-0.3, 0.3), (0.25, rng.uniform(0.5, 0.9)),
             color.rgb32(40, rng.uniform(120, 170), 40), 0.3, rotation_y=rng.uniform(0, 180))
for x, z in scatter(40, 0.25, 0.9):                   # 砂浜の貝殻
    deco('icosphere', x, z, 0.25, rng.choice([color.white, color.pink]), 0.1)
for x, z in scatter(6, 0.3, 0.9):                     # 流木
    deco('cube', x, z, (0.2, 0.2, 1.8), color.rgb32(120, 90, 60), 0.1, rotation_y=rng.uniform(0, 180))
cx, cz = 6, -56                                       # 出発地点のそばの焚き火
for k in range(8):
    deco('cube', cx + math.cos(k * math.tau / 8), cz + math.sin(k * math.tau / 8), (0.35, 0.25, 0.35), color.gray, 0.1, rotation_y=k * 40)   # 囲いの石
for k in range(3):
    deco('cube', cx, cz, (0.15, 0.15, 1.1), color.rgb32(90, 60, 40), 0.2, rotation_y=k * 60)                                                # 薪
deco('diamond', cx, cz, (0.5, 1, 0.5), color.orange, 0.7)                                                                                    # 炎
for x, z, h in [(-8, 3, 3.5), (8, 3, 1.5), (-8, 17, 2.5), (8, 17, 4)]:       # 遺跡のまわりの折れた柱
    deco('cube', x, z, (0.8, h, 0.8), color.rgb32(150, 145, 135), h / 2)
for _ in range(14):                                   # 瓦礫
    s = rng.uniform(0.2, 0.6)
    deco('cube', rng.uniform(-9, 9), rng.uniform(1, 19), (s * 1.5, s, s), color.rgb32(140, 135, 125), s / 2, rotation_y=rng.uniform(0, 180))
for hx, hz in HUTS:                                   # 小屋の外の木箱
    for dx, dz in ((2.6, -3.6), (3.4, -3.2)):
        deco('cube', hx + dx, hz + dz, 0.7, color.rgb32(140, 100, 60), 0.35, rotation_y=dx * 20)
decor.combine()                                       # ここまでの小物を全部1つのメッシュに → 描画1回で軽い
decor.double_sided = True                             # 草の葉(quad)を裏からも見えるように

clouds = Entity()                                     # 雲：ふくらみを4つ重ねたものを12個、これも1つにまとめる
for _ in range(12):
    cx, cy, cz = rng.uniform(-250, 250), rng.uniform(70, 100), rng.uniform(-250, 250)
    for k in range(4):
        Entity(parent=clouds, model='icosphere', position=(cx + k * 14 - 21, cy + rng.uniform(-3, 3), cz + rng.uniform(-6, 6)),
               scale=(rng.uniform(18, 28), 9, rng.uniform(14, 20)))
clouds.combine()
sun = Entity(model='sphere', position=(250, 220, 300), scale=50, color=color.yellow)

def set_sky(col):                                     # 空の色を変える：雲は色合いを合わせ、太陽は昼だけ出す
    sky.color = col
    clouds.color = color.white if col == SKY_BLUE else color.gray
    sun.enabled = col == SKY_BLUE

# ===== 5. キャラクター：顔は「部品の表」で作る（頭の中心が原点） =====
YELLOW, BROWN = color.rgb32(255, 205, 50), color.rgb32(60, 30, 20)
BROW, LIP = color.rgb32(120, 70, 20), color.rgb32(120, 50, 30)
FACE = [('sphere', (0, 0, 0), (1, 1, 1), YELLOW),                                                   # 🥺 頭
        ('sphere', (-0.17, 0.05, 0.44), (0.2, 0.27, 0.08), BROWN), ('sphere', (0.17, 0.05, 0.44), (0.2, 0.27, 0.08), BROWN),     # うるうるの目
        ('sphere', (-0.14, 0.13, 0.48), (0.07, 0.07, 0.04), color.white), ('sphere', (0.14, 0.13, 0.48), (0.07, 0.07, 0.04), color.white),   # ハイライト
        ('cube', (-0.17, 0.35, 0.40), (0.18, 0.04, 0.04), BROW, -20), ('cube', (0.17, 0.35, 0.40), (0.18, 0.04, 0.04), BROW, 20),            # 困り眉
        ('cube', (0, -0.27, 0.45), (0.1, 0.03, 0.03), LIP)]                                                                                    # 口
GRIN = [('sphere', (0, 0, 0), (1, 1, 1), YELLOW)] + \
       [('cube', (s * 0.2 + dx, 0.15, 0.46), (0.15, 0.04, 0.04), BROW, rot) for s in (-1, 1) for dx, rot in ((-0.06, -35), (0.06, 35))] + \
       [('cube', (0, -0.17, 0.46), (0.52, 0.24, 0.04), LIP), ('cube', (0, -0.08, 0.485), (0.48, 0.07, 0.03), color.white)]   # 😁 笑った目「^ ^」・口・歯
WARP = [('sphere', (0, 0, 0), (1.25, 0.85, 1), YELLOW, 8),                                         # 🫪 ひしゃげた頭・大きさの違う目・ゆがんだ口
        ('sphere', (-0.25, 0.12, 0.42), (0.28, 0.38, 0.1), BROWN), ('sphere', (0.22, -0.02, 0.46), (0.14, 0.14, 0.1), BROWN),
        ('cube', (-0.05, -0.22, 0.44), (0.5, 0.07, 0.06), BROWN, -14), ('cube', (-0.25, 0.38, 0.38), (0.3, 0.05, 0.05), BROWN, -20)]
HAND = [('cube', (0, 0, 0), (0.45, 0.5, 0.3), YELLOW), ('cube', (0, 0.1, 0.4), (0.14, 0.14, 0.6), YELLOW), ('cube', (0.27, -0.05, 0.1), (0.14, 0.2, 0.2), YELLOW)]

def make_enemy(x, z):                                 # 🥺：頭・胴体・腕・脚（腕と脚は付け根の「関節」を回して振る）
    e = Entity(position=(x, height(x, z), z), walk=0)
    draw(e, [('cube', (0, 1.4, 0), (0.9, 1.0, 0.5), color.rgb32(230, 120, 40))])
    draw(Entity(parent=e, y=2.4), FACE)
    e.arms = [Entity(parent=e, position=(s * 0.6, 1.85, 0), rotation_x=-80) for s in (-1, 1)]    # 前に伸ばした腕
    e.legs = [Entity(parent=e, position=(s * 0.25, 0.9, 0)) for s in (-1, 1)]
    for a in e.arms:
        Entity(parent=a, model='cube', y=-0.4, scale=(0.25, 0.8, 0.25), color=YELLOW)
    for l in e.legs:
        Entity(parent=l, model='cube', y=-0.45, scale=(0.3, 0.9, 0.3), color=color.rgb32(50, 60, 140))
    return e

def make_head(x, z):                                  # 小屋に置く敵の首（入口を向く）
    h = Entity(position=(x, height(x, z) + 0.5, z), rotation_y=180, collider='box')
    draw(h, FACE)
    beam(color.red, h)
    return h

def make_boss(x, z):                                  # 👈😁👉：笑顔と外を指す両手。変化後は顔が🫪、手は正面(🫵)
    b = Entity(position=(x, height(x, z) + 1.4, z), rotation_y=180, scale=1.6, collider='box', t=0)
    b.grin, b.warp = Entity(parent=b), Entity(parent=b, enabled=False)
    draw(b.grin, GRIN)
    draw(b.warp, WARP)
    b.hands = [Entity(parent=b, position=(s * 1.2, 0, 0), rotation_y=s * 90) for s in (-1, 1)]    # 指は手の+z方向。±90で外向き
    for h in b.hands:
        draw(h, HAND)
    beam(color.magenta, b)
    return b

def make_stomp(x, z):                                 # 踏みつぶす😁の生首（ジャンプして乗る高さ1.4m）
    gy = height(x, z)
    s = Entity(position=(x, gy + 0.7, z), scale=1.4, rotation_y=random.uniform(0, 360), collider='box', top=gy + 1.4)
    draw(s, GRIN)
    beam(color.magenta, s)
    return s

# ===== 6. ゲームの状態と画面表示 =====
player = FirstPersonController()
woods, coconuts, enemies, heads, stomps = [], [], [], [], []
boat = boss = None

def gauge(pos, origin, w, h, col):                    # 黒い背景＋色付きバー（バーのscale_xを変えて増減させる）
    back = Entity(parent=camera.ui, model='quad', color=color.black66, z=0.1, scale=(w, h), origin=origin, position=pos)
    return back, Entity(parent=camera.ui, model='quad', color=col, scale=(w, h), origin=origin, position=pos)

prog_label = Text('首を回収中…', origin=(0, 0), position=(0, -0.07), scale=1.3, enabled=False)
prog_back, prog_bar = gauge((-0.15, -0.11), (-0.5, 0), 0.3, 0.025, color.orange)       # 首の回収ゲージ
prog_back.enabled = prog_bar.enabled = False
Text('体力', parent=camera.ui, origin=(-0.5, 0.5), position=window.top_left + Vec2(0.02, -0.02), scale=1.3)
hp_back, hp_bar = gauge(window.top_left + Vec2(0.1, -0.02), (-0.5, 0.5), 0.4, 0.035, color.lime)   # 体力ゲージ
alert = Text('認識された', origin=(0, 0), scale=3, color=color.red, enabled=False)
msg = Text('', origin=(0, 0), y=0.3, scale=2, color=color.yellow)

def say(text, sec=1, col=color.yellow):               # 画面中央にsec秒だけ文字を出す
    global msg_time
    msg.text, msg.color, msg_time = text, col, sec

def end_game(title, col):
    global game_over
    game_over = True
    player.enabled = False
    say(title + '\n\nEnterキーで再スタート', 999, col)

def restart():                                        # 全部を最初の状態に戻す（最初の起動でも呼ぶ）
    global boat, boss, boss_state, boss_wait, quest_started, solved, peace, game_over, hold, hp, last_pos
    for e in woods + coconuts + enemies + heads + stomps + [boss, boat.parent if boat else None]:
        if e:
            destroy(e)
    heads.clear()
    stomps.clear()
    woods[:] = [wood(x, z) for x, z in spots]
    coconuts[:] = [coconut(x, z) for x, z in coconut_spots]
    enemies[:] = [make_enemy(x, z) for x, z in ENEMY_STARTS]
    boat = boss = None
    boss_state, boss_wait = 'none', 0                 # none → idle(待機) → wait(4秒待ち) → chase(追跡) → dead
    quest_started = solved = peace = game_over = False      # 紙を読んだ／敵を消した／島が平和になった／終了
    hold, hp = 0, HP_MAX                              # Eを押し続けた秒数／体力
    set_sky(SKY_BLUE)
    player.position, player.rotation_y, player.camera_pivot.rotation_x = (0, height(0, -50) + 2, -50), 0, 0
    last_pos = player.position
    debug_menu.enabled = False
    player.enabled = True
    say('木片を10個集めよう！体力が尽きる前にヤシの実を食べよう', 3)

# ===== 7. ゲームの進行（通常プレイもデバッグメニューも、同じ関数を呼ぶ） =====
def collect_wood(w):
    global boat
    woods.remove(w)
    destroy(w)
    if woods:
        say(f'残り {len(woods)}/10')
    else:
        boat = make_boat()
        say('ボートが完成した！脱出しよう！', 3)

def start_quest1():                                   # 紙を読んだ：小屋に敵の首が出現
    global quest_started
    if not quest_started:
        quest_started = True
        heads[:] = [make_head(x, z) for x, z in head_spots]

def solve_quest1():                                   # 首を2つ集めた：敵が消え、👈😁👉が出現
    global solved, hold, boss, boss_state
    if solved:
        return
    start_quest1()
    for e in heads + enemies:
        destroy(e)
    heads.clear()
    enemies.clear()
    solved, hold = True, 0
    boss, boss_state = make_boss(0, 30), 'idle'
    say('首を2つ集めた…敵が消えていく\n島の謎が解けた！\nだが島のどこかに奇妙な顔が現れた…', 5)

def remove_head(h):
    global hold
    heads.remove(h)
    destroy(h)
    hold = 0
    if heads:
        say(f'敵の首を回収した！残り{len(heads)}つ', 2)
    else:
        solve_quest1()

def trigger_boss():                                   # 👈😁👉に認識された：🫵🫪🫵に変化・空が暗く・生首が出現（前提の謎1も自動で解く）
    global boss_state, boss_wait
    solve_quest1()
    if boss_state != 'idle':
        return
    boss_state, boss_wait = 'wait', BOSS_WAIT
    boss.grin.enabled, boss.warp.enabled = False, True
    for h in boss.hands:
        h.rotation_y = 0                              # 指が外向き(👈👉)から、こちら向き(🫵)に
    boss.collider = None
    boss.rotation_y = math.degrees(math.atan2(player.x - boss.x, player.z - boss.z))
    msg.text = ''
    set_sky(SKY_DARK)
    stomps[:] = [make_stomp(x, z) for x, z in stomp_spots]

def stomp_one(st):                                    # 生首を踏みつぶす。全部つぶすと島が平和になる
    global boss, boss_state, peace
    stomps.remove(st)
    st.collider = None                                # 当たり判定を消す → プレイヤーは地面に落ちる
    st.animate_scale_y(0.1, duration=0.15)            # ぺちゃんこ
    destroy(st, delay=0.5)
    if stomps:
        say(f'踏みつぶした！残り {len(stomps)}/6')
    else:
        destroy(boss)
        boss, boss_state, peace = None, 'dead', True
        set_sky(SKY_BLUE)
        say('すべて踏みつぶした…奇妙な顔が消えた\nボートで島を出よう！', 4)

def stomp_all():
    trigger_boss()
    for st in stomps[:]:
        stomp_one(st)

# ===== 8. デバッグメニュー（;キーで開閉。1〜5キーかクリックで実行） =====
DEBUG = [('木片を全部回収する（ボートが出る）', lambda: [collect_wood(w) for w in woods[:]]),
         ('謎1のフラグを立てる（紙を読む→首が出る）', start_quest1),
         ('謎1の首を全部回収する（敵が消えボス出現）', solve_quest1),
         ('謎2：ボスを覚醒させる（🫵🫪🫵に変化・空が暗くなる）', trigger_boss),
         ('謎2の生首を全部踏みつぶす（島が平和に）', stomp_all)]
debug_menu = Entity(parent=camera.ui, enabled=False)
Entity(parent=debug_menu, model='quad', scale=(0.8, 0.78), color=color.rgba32(0, 0, 0, 150), z=0.1)
Text('デバッグメニュー（;キーで開閉）', parent=debug_menu, y=0.36, origin=(0, 0), scale=1.3, color=color.yellow)
for i, (label, action) in enumerate(DEBUG):
    Button(text=f'{i + 1}. {label}', parent=debug_menu, scale=(0.72, 0.095), y=0.26 - i * 0.11, text_color=color.white,
           color=color.rgb32(60, 60, 60), highlight_color=color.azure, on_click=action)

# ===== 9. 毎フレームの処理 =====
def dist_to(e):
    return math.hypot(player.x - e.x, player.z - e.z)

def chase(e, speed, lift=0):                          # eをプレイヤーの方へ向けて、地形の高さに沿って動かす
    dx, dz = player.x - e.x, player.z - e.z
    d = math.hypot(dx, dz)
    e.x += dx / d * speed * time.dt
    e.z += dz / d * speed * time.dt
    e.y = height(e.x, e.z) + lift
    e.rotation_y = math.degrees(math.atan2(dx, dz))

def update():
    global last_pos, msg_time, hp, hold, boss_state, boss_wait
    if debug_menu.enabled:                            # デバッグメニュー中はゲーム全体を一時停止
        return
    msg_time -= time.dt
    if msg.text and msg_time < 0:
        msg.text = ''
    sea.y = math.sin(time.time()) * 0.05              # 海がゆらゆら揺れる
    clouds.rotation_y += time.dt * 0.5                # 雲がゆっくり流れる
    if game_over:
        return
    player.speed = DASH_SPEED if held_keys['q'] else WALK_SPEED
    for w in woods:
        w.rotation_y += 60 * time.dt                  # 木片をくるくる回す

    hp -= HP_DRAIN * time.dt                          # 体力：時間とともに減る
    hp_bar.scale_x = 0.4 * max(hp, 0) / HP_MAX
    hp_bar.color = color.red if hp < 30 else color.lime
    if hp <= 0:
        return end_game('ゲームオーバー', color.red)

    target = look() if held_keys['e'] else None       # 敵の首：Eを10秒押し続けると回収
    hold = hold + time.dt if target in heads else 0
    prog_bar.scale_x = 0.3 * min(hold / 10, 1)
    prog_label.enabled = prog_back.enabled = prog_bar.enabled = hold > 0
    if hold >= 10:
        remove_head(target)

    if boss_state == 'wait':                          # ボス：認識されて4秒待ってから追跡
        boss_wait -= time.dt
        if boss_wait <= 0:
            boss_state = 'chase'
    alert.enabled = boss_state == 'wait'
    if boss_state == 'chase':
        if dist_to(boss) < 2.0:
            return end_game('ゲームオーバー', color.red)
        chase(boss, BOSS_SPEED, 1.4)
        boss.t += time.dt
        boss.warp.rotation_z = math.sin(boss.t * 6) * 10     # ゆらゆら揺れる

    for st in stomps[:]:                              # 生首の「上に乗った」ら踏みつぶす
        if dist_to(st) < 0.7 and st.top - 0.2 < player.y < st.top + 0.8:
            stomp_one(st)

    for e in enemies:                                 # 敵：範囲内に入ったら追いかける
        d = dist_to(e)
        if d < 1.3:
            return end_game('ゲームオーバー', color.red)
        if d < CHASE_RANGE:
            chase(e, ENEMY_SPEED)
            e.walk += time.dt * 8
        swing = math.sin(e.walk) if d < CHASE_RANGE else 0     # 追跡中だけ腕と脚を振る
        e.legs[0].rotation_x, e.legs[1].rotation_x = swing * 35, -swing * 35
        e.arms[0].rotation_x, e.arms[1].rotation_x = -80 + swing * 10, -80 - swing * 10

    # ★追加：地面より下に落ちたら地形の上に戻す（コライダーが効かない環境用の保険）
    gy = height(player.x, player.z)
    if player.y < gy - 0.5:
        player.position = (player.x, gy + 1.5, player.z)
        player.camera_pivot.rotation_x = 0
        last_pos = player.position
        say('', 1)

    if math.hypot(player.x, player.z) > SIZE * 0.95:  # 沖には出られない
        player.position = last_pos
    else:
        last_pos = player.position

def look():                                           # 画面中央(照準)の先5m以内にあるもの
    return raycast(camera.world_position, camera.forward, distance=5, ignore=[player]).entity

def input(key):
    global hp
    if key == 'escape':
        application.quit()
    if key == DEBUG_KEY:                              # メニューを開くとプレイヤーを止め、マウスを使えるようにする
        debug_menu.enabled = not debug_menu.enabled
        player.enabled = not (debug_menu.enabled or game_over)
    elif debug_menu.enabled and key in ('1', '2', '3', '4', '5'):
        DEBUG[int(key) - 1][1]()
    elif game_over and key == 'enter':
        restart()
    elif key == 'e' and not (game_over or debug_menu.enabled):
        target = look()                               # Eを押したとき、照準の先にあるもので分岐
        if target in woods:
            collect_wood(target)
        elif target in coconuts:                      # ヤシの実：体力を半分回復
            coconuts.remove(target)
            destroy(target)
            hp = min(HP_MAX, hp + HP_MAX / 2)
            say('ヤシの実を食べた！体力回復')
        elif target == stump:                         # 切り株の紙
            start_quest1()
            if not solved:
                say('紙にはこう書かれている…\n「敵の首を2つ集めよ。首は廃墟小屋にある」', 5)
        elif target in heads:
            say('Eを10秒間押し続けて首を回収する', 2)
        elif boss and target == boss and boss_state == 'idle':
            trigger_boss()
        elif boat and target == boat:                 # ボートに乗ってクリア。謎の解決度で結末が変わる
            if peace:
                end_game('すべての謎を解決し、島は平和になった！\nALLクリア！', color.gold)
            elif solved:
                end_game('ゲームクリア\nしかしまだ謎は残っている...', color.gold)
            else:
                end_game('ゲームクリア？\nあなたは何もなしえず島を出た...', color.light_gray)

restart()
app.run()
