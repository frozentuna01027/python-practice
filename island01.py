"""
無人島脱出ゲーム（迷路ステージ追加版）
木片10個でボート脱出。体力は1分で0→ヤシの実(E)で半分回復。🥺に捕まる/体力0でゲームオーバー
謎1：切り株の紙(E)→小屋の「敵の首」2つをE長押し(10秒)で回収→敵が消える
謎2：👈😁👉にE→🫵🫪🫵が4秒後に追跡→😁の生首6つをジャンプで踏みつぶす
迷路：謎を残したままボートで島を出ると、暗い迷路に落ちる。光の柱に着くと島の最初から。
※このバージョンで追加した部分は「【迷路追加】」マーカーで囲んである。エディタで検索すれば追加点が全部見つかる。
操作: WASD=移動 / Q長押し=ダッシュ / Space=ジャンプ / E=調べる / Enter=再スタート / Esc=終了 / ;=デバッグメニュー
"""
from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController
import math, os, random, shutil

# ===== 0. 起動と設定 =====
app = Ursina(title='Island')
random.seed(1)
font = application.asset_folder / 'msgothic.ttc'      # Windows標準のMSゴシックをこのフォルダにコピーして使う
if not font.exists() and os.path.exists(r'C:\Windows\Fonts\msgothic.ttc'):
    shutil.copy(r'C:\Windows\Fonts\msgothic.ttc', font)
if font.exists(): Text.default_font = font.name

SIZE = 80                                             # 島の半径
WALK_SPEED, DASH_SPEED = 5, 9                         # 歩き／Qダッシュ
ENEMY_SPEED, CHASE_RANGE = 4.5, 25                    # 敵：歩きより少し遅い／この距離で追跡開始
BOSS_SPEED, BOSS_WAIT = 7, 4                          # ボス：歩きでは追いつかれる／動き出すまでの秒数
HP_MAX, HP_DRAIN = 100, 100 / 60                      # 体力：何もしないと60秒で0
GRAVITY, JUMP_SPEED = 26, 10.5                        # 落下加速度／ジャンプ初速（跳ぶ高さ ≒ 2m）
STEP_SNAP, FOLLOW = 0.45, 30                          # 吸着する段差／下り坂で地面に追従する速さ
DEBUG_KEY = ';'
ENEMY_STARTS = [(0, 60), (-45, -35), (45, -40), (-35, 45), (55, 15)]

# ===== 【迷路追加】ここから：迷路ステージの設定 =====
MAZE_N = 10                                           # 【迷路追加】迷路のセル数（10×10＝21×21の壁グリッド／旧8×8）
PASS_W, WALL_T = 4.2, 1                               # 【迷路追加】通路の幅／壁の厚さ(m)（通路を1.05倍に広げた）
PITCH = PASS_W + WALL_T
MAZE_SPAN = MAZE_N * PITCH + WALL_T                   # 【迷路追加】迷路の一辺（53m＝旧41mの約1.3倍）
MAZE_H = 3.0                                          # 壁の高さ（目の高さ2mより高い＝地上では先が見えない）
MAZE_JUMP = 13.0                                      # 【迷路追加】迷路でのジャンプ初速（頂点≒3.2m→壁の上から全体が見える）
PLAYER_R = 0.45                                       # 迷路での当たり半径
MRES = 0.5                                            # 当たり判定テーブルの刻み(m)
MGRID = int(MAZE_SPAN / MRES) + 3
MAZE_ORIGIN = Vec3(1000, 0, 0)                        # 島から遥か東に作る

in_maze = False                                       # 【迷路追加】迷路ステージ中か
maze_pending = None                                   # 【迷路追加】迷路へ切り替わるまでの残り秒
maze_out = None                                       # 【迷路追加】ゴール後に島へ戻るまでの残り秒
maze_root = None                                      # 【迷路追加】迷路のジオメトリをまとめた親
maze_grid = []                                        # 【迷路追加】壁=1／通路=0 のグリッド
maze_solid = []                                       # 【迷路追加】当たり判定用のソリッドテーブル
maze_prev = Vec3(0, 0, 0)                             # 【迷路追加】1フレーム前の位置（押し戻し用）
maze_goal = Vec3(0, 0, 0)                             # 【迷路追加】ゴール（光の柱）の位置
maze_start = Vec3(0, 0, 0)                            # 【迷路追加】迷路の開始位置
maze_fog = None                                       # 【迷路追加】不気味な霧
# ===== 【迷路追加】ここまで：迷路ステージの設定 =====

# ===== 1. 地形：高さの関数 → 格子点 → 三角形 =====
def height(x, z):
    d = math.hypot(x, z) / SIZE
    return max((1 - d * d) * 8 - 1 + math.sin(x * 0.1) * math.cos(z * 0.12) * 1.5 * (1 - d), -3)   # お椀形＋起伏

def ground_color(x, h, z):                            # 高さと場所で地面の色を変える
    k = (math.sin(x * 0.35) * math.cos(z * 0.3) + 1) / 2
    if h < 0.3: return color.rgb32(200, 180, 130)     # 波打ち際
    if h < 1: return color.rgb32(235, 215, 155)       # 砂浜
    if h > 6.5: return color.rgb32(135, 130, 115)     # 山頂は岩
    return color.rgb32(55 + 30 * k, 125 + 30 * k, 45 + 15 * k)   # 草地

n = 50                                                                # 格子の数（1辺）
verts = [(x, height(x, z), z) for x in range(-100, 101, 4) for z in range(-100, 101, 4)]
tris = [t for i in range(n) for j in range(n) for a in (i * (n + 1) + j,)
        for t in ((a, a + 1, a + n + 1), (a + 1, a + n + 2, a + n + 1))]   # 反時計回り＝法線が上向き
ground = Entity(model=Mesh(vertices=verts, triangles=tris, colors=[ground_color(*v) for v in verts]),
                double_sided=True)                   # コライダー無し（接地は自前計算）
sea = Entity(model='plane', scale=500, color=color.rgba32(30, 110, 190, 200))
SKY_BLUE, SKY_DARK = color.rgb32(20, 130, 255), color.rgb32(25, 15, 45)
sky = Sky(texture=None, color=SKY_BLUE)

# ===== 2. 共通パーツ =====
def beam(col, parent=scene, pos=(0, 10, 0)):          # 目印の光の柱
    return Entity(parent=parent, model='cube', position=pos, scale=(0.08, 20, 0.08), color=col)

def draw(e, parts):                                   # 部品の表 (形, 位置, 大きさ, 色[, 傾き]) から立体を組み立てる
    for model, pos, scale, col, *tilt in parts:
        Entity(parent=e, model=model, position=pos, scale=scale, color=col, rotation_z=tilt[0] if tilt else 0)

def build(cx, cz, walls, tex='brick', col=color.white, lift=0):   # 壁の表から建物を作る
    y0 = height(cx, cz) + lift
    for dx, dz, w, d, h in walls:
        Entity(model='cube', position=(cx + dx, y0 + h / 2, cz + dz), scale=(w, h, d), color=col,
               texture=tex, texture_scale=(max(w, d) / 2, h / 2), collider='box')

# ===== 3. 建造物：遺跡（レンガ）と廃墟小屋2つ =====
build(0, 10, [(-5, 0, 0.5, 10, 3.0), (5, 0, 0.5, 10, 1.5), (-3, 5, 4, 0.5, 3.5), (3, 5, 4, 0.5, 1.0),
              (-3, -5, 4, 0.5, 2.5), (2, -5, 3, 0.5, 3.0), (-5, -5, 1, 1, 4.5)])
HUTS = [(25, -10), (-50, 5)]
HUT_WALLS = [(0, 2.5, 5, 0.3, 3.0), (-2.5, 0, 0.3, 5, 3.0), (2.5, 0, 0.3, 5, 1.8),
             (-1.5, -2.5, 2, 0.3, 3.0), (1.8, -2.5, 1.4, 0.3, 1.4)]
for x, z in HUTS:
    build(x, z, HUT_WALLS, None, color.rgb32(110, 85, 60), -0.4)
    build(x - 1, z + 1, [(0, 0, 3, 3.5, 0.2)], None, color.rgb32(70, 55, 40), 2.6)    # 一部だけ残った屋根

# ===== 4. ヤシの木と実（2本に1本・2つずつ） =====
rng = random.Random(7)                                # 装飾用の乱数（配置に影響させない）
decor = Entity()
coconut_spots, count = [], 0
for _ in range(60):
    x, z = random.uniform(-SIZE, SIZE), random.uniform(-SIZE, SIZE)
    if 0.5 < height(x, z) < 4:
        y = height(x, z)
        Entity(model='cube', position=(x, y + 2.5, z), scale=(0.4, 5, 0.4), color=color.rgb32(110, 80, 50), collider='box')  # 幹
        Entity(model='sphere', position=(x, y + 5.5, z), scale=(4, 1.5, 4), color=color.rgb32(40, 140, 50))                   # 葉
        for k in range(6):                                                                                     # 垂れ下がる葉
            a = math.radians(k * 60)
            Entity(parent=decor, model='cube', position=(x + math.sin(a) * 1.2, y + 4.75, z + math.cos(a) * 1.2),
                   rotation=(25, k * 60, 0), scale=(0.6, 0.05, 2.7), color=color.rgb32(30 + k * 6, 130, 45))
        count += 1
        if count % 2 == 0: coconut_spots += [(x + 0.9, z + 0.3), (x - 0.8, z - 0.4)]

# ===== 5. アイテム：木片・実・ボート・切り株の紙 =====
spots = [(0, 10), (-30, -20), (20, -30), (-40, 20), (35, 25), (10, 40), (-15, -50), (50, -10), (-55, -10), (45, 45)]
head_spots = [(x - 1, z + 1.2) for x, z in HUTS]                       # 敵の首：各小屋に1つ
stomp_spots = [(70 * math.cos(math.radians(a)), 70 * math.sin(math.radians(a))) for a in (30, 100, 170, 240, 320)] + [(0, 0)]

def wood(x, z):
    w = Entity(position=(x, height(x, z) + 0.5, z), collider='box')    # 当たり判定(1m立方)
    Entity(parent=w, model='cube', scale=(1, 0.25, 0.25), color=color.orange)
    beam(color.yellow, w)
    return w

def coconut(x, z):
    return Entity(model='sphere', position=(x, height(x, z) + 0.2, z), scale=0.45,
                  color=color.rgb32(110, 70, 35), collider='box')

def make_boat():                                      # 部品をshipの子にして、まとめて消せるように
    ship = Entity(position=(0, height(0, -72) + 0.4, -72))
    draw(ship, [('cube', (0, 3, 0), (0.2, 5, 0.2), color.dark_gray), ('cube', (0, 3.5, 0), (0.05, 3, 3), color.white)])
    ship.beam = beam(color.cyan, ship)
    hull = Entity(parent=ship, model='cube', scale=(7, 1, 3), color=color.rgb32(120, 80, 50), collider='box')
    hull.beam = ship.beam                             # 演出で光の柱を消せるように持ち回す
    return hull

y = height(-60, 20)                                   # 切り株と白い紙：スタート地点から遠い場所
stump = Entity(model='cube', position=(-60, y + 0.4, 20), scale=(1.4, 0.8, 1.4), color=color.rgb32(100, 70, 40), collider='box')
Entity(model='cube', position=(-60, y + 0.85, 20), scale=(0.6, 0.05, 0.8), rotation_y=25)
beam(color.white, pos=(-60, y + 10, 20))

# ===== 6. 装飾と空（最後に combine() で1メッシュに） =====
KEEP = [(0, 10, 8), (25, -10, 5), (-50, 5, 5), (-60, 20, 4), (0, -50, 4), (6, -56, 4), (0, -72, 8)]   # 置かない場所

def scatter(cnt, hmin, hmax):                         # 高さが範囲内でKEEPの外の点を cnt 個選ぶ
    pts = []
    while len(pts) < cnt:
        x, z = rng.uniform(-75, 75), rng.uniform(-75, 75)
        if hmin < height(x, z) < hmax and all(math.hypot(x - kx, z - kz) > kr for kx, kz, kr in KEEP):
            pts.append((x, z))
    return pts

def deco(model, x, z, scale, col, lift=0, **kw):      # 地面の高さ+lift に小物を1つ置く
    return Entity(parent=decor, model=model, position=(x, height(x, z) + lift, z), scale=scale, color=col, **kw)

for x, z in scatter(50, 0.2, 6):                      # 岩
    s, g = rng.uniform(0.5, 1.6), rng.uniform(100, 150)
    deco('cube', x, z, (s * 1.3, s, s), color.rgb32(g, g, g - 10), s / 3, rotation=(rng.uniform(0, 30), rng.uniform(0, 360), 0))
for x, z in scatter(60, 1.2, 5):                      # 茂み
    s = rng.uniform(1, 1.8)
    deco('icosphere', x, z, (s * 1.3, s, s * 1.3), color.rgb32(30, rng.uniform(95, 130), 40), s * 0.4)
for cx, cz in scatter(24, 1.2, 5):                    # 花畑
    col = rng.choice([color.red, color.yellow, color.pink, color.white, color.violet])
    for _ in range(6):
        deco('diamond', cx + rng.uniform(-1.5, 1.5), cz + rng.uniform(-1.5, 1.5), (0.25, 0.4, 0.25), col, 0.25)
for x, z in scatter(220, 1.0, 5.5):                   # 草むら
    for _ in range(3):
        deco('quad', x + rng.uniform(-0.3, 0.3), z + rng.uniform(-0.3, 0.3), (0.25, rng.uniform(0.5, 0.9)),
             color.rgb32(40, rng.uniform(120, 170), 40), 0.3, rotation_y=rng.uniform(0, 180))
for x, z in scatter(40, 0.25, 0.9):                   # 貝殻
    deco('icosphere', x, z, 0.25, rng.choice([color.white, color.pink]), 0.1)
for x, z in scatter(6, 0.3, 0.9):                     # 流木
    deco('cube', x, z, (0.2, 0.2, 1.8), color.rgb32(120, 90, 60), 0.1, rotation_y=rng.uniform(0, 180))

cx, cz = 6, -56                                       # 出発地点のそばの焚き火
for k in range(8):
    deco('cube', cx + math.cos(k * math.tau / 8), cz + math.sin(k * math.tau / 8), (0.35, 0.25, 0.35), color.gray, 0.1, rotation_y=k * 40)
for k in range(3):
    deco('cube', cx, cz, (0.15, 0.15, 1.1), color.rgb32(90, 60, 40), 0.2, rotation_y=k * 60)    # 薪
deco('diamond', cx, cz, (0.5, 1, 0.5), color.orange, 0.7)                                       # 炎
for x, z, h in [(-8, 3, 3.5), (8, 3, 1.5), (-8, 17, 2.5), (8, 17, 4)]:        # 折れた柱
    deco('cube', x, z, (0.8, h, 0.8), color.rgb32(150, 145, 135), h / 2)
for _ in range(14):                                   # 瓦礫
    s = rng.uniform(0.2, 0.6)
    deco('cube', rng.uniform(-9, 9), rng.uniform(1, 19), (s * 1.5, s, s), color.rgb32(140, 135, 125), s / 2, rotation_y=rng.uniform(0, 180))
for hx, hz in HUTS:                                   # 小屋の外の木箱
    for dx, dz in ((2.6, -3.6), (3.4, -3.2)):
        deco('cube', hx + dx, hz + dz, 0.7, color.rgb32(140, 100, 60), 0.35, rotation_y=dx * 20)
decor.combine()                                       # 小物を全部1つのメッシュに → 描画1回で軽い
decor.double_sided = True                             # 草の葉(quad)を裏からも見えるように

clouds = Entity()                                     # 雲：ふくらみ4つ×12個
for _ in range(12):
    cx, cy, cz = rng.uniform(-250, 250), rng.uniform(70, 100), rng.uniform(-250, 250)
    for k in range(4):
        Entity(parent=clouds, model='icosphere', position=(cx + k * 14 - 21, cy + rng.uniform(-3, 3), cz + rng.uniform(-6, 6)),
               scale=(rng.uniform(18, 28), 9, rng.uniform(14, 20)))
clouds.combine()
sun = Entity(model='sphere', position=(250, 220, 300), scale=50, color=color.yellow)

def set_sky(col):                                     # 空の色：雲は色合いを合わせ、太陽は昼だけ
    sky.color = col
    clouds.color = color.white if col == SKY_BLUE else color.gray
    sun.enabled = col == SKY_BLUE

# ===== 7. キャラクター：顔は「部品の表」で作る（頭の中心が原点） =====
YELLOW, BROWN = color.rgb32(255, 205, 50), color.rgb32(60, 30, 20)
BROW, LIP = color.rgb32(120, 70, 20), color.rgb32(120, 50, 30)
FACE = [('sphere', (0, 0, 0), (1, 1, 1), YELLOW),                                                   # 🥺
        ('sphere', (-0.17, 0.05, 0.44), (0.2, 0.27, 0.08), BROWN), ('sphere', (0.17, 0.05, 0.44), (0.2, 0.27, 0.08), BROWN),
        ('sphere', (-0.14, 0.13, 0.48), (0.07, 0.07, 0.04), color.white), ('sphere', (0.14, 0.13, 0.48), (0.07, 0.07, 0.04), color.white),
        ('cube', (-0.17, 0.35, 0.40), (0.18, 0.04, 0.04), BROW, -20), ('cube', (0.17, 0.35, 0.40), (0.18, 0.04, 0.04), BROW, 20),
        ('cube', (0, -0.27, 0.45), (0.1, 0.03, 0.03), LIP)]
GRIN = [('sphere', (0, 0, 0), (1, 1, 1), YELLOW)] + \
       [('cube', (s * 0.2 + dx, 0.15, 0.46), (0.15, 0.04, 0.04), BROW, rot) for s in (-1, 1) for dx, rot in ((-0.06, -35), (0.06, 35))] + \
       [('cube', (0, -0.17, 0.46), (0.52, 0.24, 0.04), LIP), ('cube', (0, -0.08, 0.485), (0.48, 0.07, 0.03), color.white)]   # 😁
WARP = [('sphere', (0, 0, 0), (1.25, 0.85, 1), YELLOW, 8),                                         # 🫪
        ('sphere', (-0.25, 0.12, 0.42), (0.28, 0.38, 0.1), BROWN), ('sphere', (0.22, -0.02, 0.46), (0.14, 0.14, 0.1), BROWN),
        ('cube', (-0.05, -0.22, 0.44), (0.5, 0.07, 0.06), BROWN, -14), ('cube', (-0.25, 0.38, 0.38), (0.3, 0.05, 0.05), BROWN, -20)]
HAND = [('cube', (0, 0, 0), (0.45, 0.5, 0.3), YELLOW), ('cube', (0, 0.1, 0.4), (0.14, 0.14, 0.6), YELLOW),
        ('cube', (0.27, -0.05, 0.1), (0.14, 0.2, 0.2), YELLOW)]

def make_enemy(x, z):                                 # 🥺（腕と脚は付け根の関節を回して振る）
    e = Entity(position=(x, height(x, z), z), walk=0)
    draw(e, [('cube', (0, 1.4, 0), (0.9, 1.0, 0.5), color.rgb32(230, 120, 40))])
    draw(Entity(parent=e, y=2.4), FACE)
    e.arms = [Entity(parent=e, position=(s * 0.6, 1.85, 0), rotation_x=-80) for s in (-1, 1)]
    e.legs = [Entity(parent=e, position=(s * 0.25, 0.9, 0)) for s in (-1, 1)]
    for a in e.arms: Entity(parent=a, model='cube', y=-0.4, scale=(0.25, 0.8, 0.25), color=YELLOW)
    for l in e.legs: Entity(parent=l, model='cube', y=-0.45, scale=(0.3, 0.9, 0.3), color=color.rgb32(50, 60, 140))
    return e

def make_head(x, z):                                  # 小屋に置く敵の首（入口を向く）
    h = Entity(position=(x, height(x, z) + 0.5, z), rotation_y=180, collider='box')
    draw(h, FACE); beam(color.red, h)
    return h

def make_boss(x, z):                                  # 👈😁👉：変化後は顔が🫪、手は正面(🫵)
    b = Entity(position=(x, height(x, z) + 1.4, z), rotation_y=180, scale=1.6, collider='box', t=0)
    b.grin, b.warp = Entity(parent=b), Entity(parent=b, enabled=False)
    draw(b.grin, GRIN); draw(b.warp, WARP)
    b.hands = [Entity(parent=b, position=(s * 1.2, 0, 0), rotation_y=s * 90) for s in (-1, 1)]
    for h in b.hands: draw(h, HAND)
    beam(color.magenta, b)
    return b

def make_stomp(x, z):                                 # 踏みつぶす😁の生首（乗る高さ1.4m）
    gy = height(x, z)
    s = Entity(position=(x, gy + 0.7, z), scale=1.4, rotation_y=random.uniform(0, 360), collider='box', top=gy + 1.4)
    draw(s, GRIN); beam(color.magenta, s)
    return s

# ===== 8. プレイヤーとHUD =====
player = FirstPersonController()
player.gravity = 0                                    # FPCの接地判定は止め、update() で自前に行う
player.vy = 0
woods, coconuts, enemies, heads, stomps = [], [], [], [], []
boat = boss = ride = None
ending = False                                        # ALLクリアの舟出演出中か

def jump():                                           # Space：自前の速度でジャンプ
    if player.grounded:                               # 【迷路追加】迷路では高く跳んで迷路の全体を見渡せる
        player.vy, player.grounded = (MAZE_JUMP if in_maze else JUMP_SPEED), False

player.jump = jump                                    # FPCの input(space) から呼ばれる

def gauge(pos, origin, w, h, col):                    # 黒背景＋色付きバー（scale_x で増減）
    back = Entity(parent=camera.ui, model='quad', color=color.black66, z=0.1, scale=(w, h), origin=origin, position=pos)
    return back, Entity(parent=camera.ui, model='quad', color=col, scale=(w, h), origin=origin, position=pos)

prog_label = Text('首を回収中…', origin=(0, 0), position=(0, -0.07), scale=1.3, enabled=False)
prog_back, prog_bar = gauge((-0.15, -0.11), (-0.5, 0), 0.3, 0.025, color.orange)
prog_back.enabled = prog_bar.enabled = False
hp_label = Text('体力', parent=camera.ui, origin=(-0.5, 0.5), position=window.top_left + Vec2(0.02, -0.02), scale=1.3)
hp_back, hp_bar = gauge(window.top_left + Vec2(0.1, -0.02), (-0.5, 0.5), 0.4, 0.035, color.lime)
alert = Text('認識された', origin=(0, 0), scale=3, color=color.red, enabled=False)
msg = Text('', origin=(0, 0), y=0.3, scale=2, color=color.yellow)

def hud(on): hp_label.enabled = hp_back.enabled = hp_bar.enabled = on     # 体力まわりをまとめて切替

def say(text, sec=1, col=color.yellow):               # 画面中央に sec 秒だけ文字を出す
    global msg_time
    msg.text, msg.color, msg_time = text, col, sec

# ===== 9. 終了・舟出演出・リセット =====
def end_game(title, col):
    global game_over
    game_over = True
    player.enabled = False
    say(title + '\n\nEnterキーで再スタート', 999, col)

END_CAM = Vec3(5.5, 2.7, -5.5)                        # 演出カメラ位置（舟から見た相対）

def escape_ending():                                  # ALLクリアのときだけ：海の上で三人称の舟出
    global ride, ending
    ride, ending = boat.parent, True                  # ボートをそのまま使い回す
    camera.world_parent = scene                       # 三人称にするためカメラを切り離す
    rider = Entity(parent=ride, position=(0, 0.5, 0.3))                                   # 乗っている自分
    Entity(parent=rider, model='cube', y=0.45, scale=(0.62, 0.9, 0.4), color=color.rgb32(70, 120, 200))
    for s in (-1, 1):                                                                      # 手を振る腕
        Entity(parent=rider, model='cube', position=(s * 0.45, 0.85, 0), rotation_z=s * 40,
               scale=(0.16, 0.5, 0.16), color=color.rgb32(70, 120, 200))
    draw(Entity(parent=rider, y=1.35, rotation_y=180, scale=0.8), GRIN)                    # 笑顔（GRINを流用）
    boat.beam.enabled = False                         # 目印の光の柱は消す
    hud(False)                                        # ゲージは隠す

def restart():
    global boat, boss, ride, ending, boss_state, boss_wait, quest_started, solved, peace, game_over, hold, hp, last_pos
    global in_maze, maze_pending, maze_out
    for e in woods + coconuts + enemies + heads + stomps + [boss, boat.parent if boat else None]:
        if e: destroy(e)
    heads.clear(); stomps.clear()
    woods[:] = [wood(x, z) for x, z in spots]
    coconuts[:] = [coconut(x, z) for x, z in coconut_spots]
    enemies[:] = [make_enemy(x, z) for x, z in ENEMY_STARTS]
    boat = boss = ride = None
    ending = False                                    # ride は boat.parent なので上のループで消える
    boss_state, boss_wait = 'none', 0                 # none → idle → wait(4秒) → chase → dead
    quest_started = solved = peace = game_over = False     # 紙／敵を消した／島が平和／終了
    hold, hp = 0, HP_MAX
    # --- 【迷路追加】ここから：迷路まわりの初期化（島に戻るときも必ず通る） ---
    in_maze, maze_pending, maze_out = False, None, None    # 迷路ステージも完全に初期化
    destroy_maze()                                         # 迷路のジオメトリを破棄
    set_fog(0)                                             # 霧を消す
    # --- 【迷路追加】ここまで ---
    set_sky(SKY_BLUE); hud(True)
    player.position, player.rotation_y, player.camera_pivot.rotation_x = (0, height(0, -50) + 2, -50), 0, 0
    last_pos = player.position
    debug_menu.enabled = False
    player.enabled = True
    say('木片を10個集めよう！体力が尽きる前にヤシの実を食べよう', 3)

# ===== 10. ゲームの進行 =====
def collect_wood(w):
    global boat
    woods.remove(w); destroy(w)
    if woods: say(f'残り {len(woods)}/10')
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
    if solved: return
    start_quest1()
    for e in heads + enemies: destroy(e)
    heads.clear(); enemies.clear()
    solved, hold = True, 0
    boss, boss_state = make_boss(0, 30), 'idle'
    say('首を2つ集めた…敵が消えていく\n島の謎が解けた！\nだが島のどこかに奇妙な顔が現れた…', 5)

def remove_head(h):
    global hold
    heads.remove(h); destroy(h)
    hold = 0
    if heads: say(f'敵の首を回収した！残り{len(heads)}つ', 2)
    else: solve_quest1()

def trigger_boss():                                   # 認識された：🫵🫪🫵に変化・空が暗く・生首が出現
    global boss_state, boss_wait
    solve_quest1()
    if boss_state != 'idle': return
    boss_state, boss_wait = 'wait', BOSS_WAIT
    boss.grin.enabled, boss.warp.enabled = False, True
    for h in boss.hands: h.rotation_y = 0             # 指が外向き(👈👉)から、こちら向き(🫵)に
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
    if stomps: say(f'踏みつぶした！残り {len(stomps)}/6')
    else:
        destroy(boss)
        boss, boss_state, peace = None, 'dead', True
        set_sky(SKY_BLUE)
        say('すべて踏みつぶした…奇妙な顔が消えた\nボートで島を出よう！', 4)

def stomp_all():
    trigger_boss()
    for st in stomps[:]: stomp_one(st)

# ===== 11. 迷路ステージ（島から遥か東／ゴールで島の最初から） =====
# ===== 【迷路追加】ここから：迷路のテクスチャ・生成・当たり判定・移動・ゴール =====
# 【迷路追加】
def maze_texture():                                   # 不気味なレンガのテクスチャをその場で生成
    path = application.asset_folder / 'maze_wall.png'
    try:
        if not path.exists():
            from PIL import Image
            S = 128
            img = Image.new('RGB', (S, S))
            px = img.load()
            r = random.Random(4242)
            g = 16
            noise = [[r.random() for _ in range(g + 1)] for _ in range(g + 1)]

            def nz(x, y):                             # 粗いノイズをバイリニア補間
                fx, fy = x / S * g, y / S * g
                ix, iy = min(g - 1, int(fx)), min(g - 1, int(fy))
                tx, ty = fx - ix, fy - iy
                a, b = noise[ix][iy], noise[ix + 1][iy]
                c, d = noise[ix][iy + 1], noise[ix + 1][iy + 1]
                return (a * (1 - tx) + b * tx) * (1 - ty) + (c * (1 - tx) + d * tx) * ty

            for y in range(S):
                shift = 32 if (y // 32) % 2 else 0    # レンガを互い違いに積む
                for x in range(S):
                    v = nz(x, y)
                    mortar = ((x + shift) % 32) < 2 or (y % 32) < 2
                    k = (0.5 + 0.5 * v) * (0.32 if mortar else 1.0)
                    px[x, y] = (int(min(255, 42 * k + 10)), int(min(255, 30 * k + 7)), int(min(255, 48 * k + 14)))
            for _ in range(8):                        # 血のような染み
                cx0, cy0, rr = r.uniform(0, S), r.uniform(0, S), r.uniform(6, 15)
                for yy in range(max(0, int(cy0 - rr)), min(S, int(cy0 + rr) + 1)):
                    for xx in range(max(0, int(cx0 - rr)), min(S, int(cx0 + rr) + 1)):
                        dd = math.hypot(xx - cx0, yy - cy0)
                        if dd < rr:
                            kk = (1 - dd / rr) ** 2
                            R, G, B = px[xx, yy]
                            px[xx, yy] = (min(255, int(R + 120 * kk)), int(G * (1 - 0.75 * kk)), int(B * (1 - 0.6 * kk)))
            img.save(path)
        try:
            tex = load_texture(path.name)
        except Exception:
            tex = load_texture(str(path))
        try:                                          # タイル状に繰り返す
            tex.wrap_u = 'repeat'
            tex.wrap_v = 'repeat'
        except Exception:
            pass
        return tex
    except Exception:
        return None

# 【迷路追加】
def span(i):                                          # グリッド番号 → (開始位置, 幅)。偶数=壁、奇数=通路
    k, odd = divmod(i, 2)
    return (k * PITCH + WALL_T, PASS_W) if odd else (k * PITCH, WALL_T)

# 【迷路追加】
def gen_maze(n, seed=1234):                           # 再帰バックトラック法（固定シードで毎回同じ迷路）
    r = random.Random(seed)
    g = [[1] * (2 * n + 1) for _ in range(2 * n + 1)]     # 1=壁 / 0=通路
    seen = [[False] * n for _ in range(n)]
    g[1][1] = 0
    seen[0][0] = True
    stack = [(0, 0)]
    while stack:
        cx, cz = stack[-1]
        cand = []
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, nz = cx + dx, cz + dz
            if 0 <= nx < n and 0 <= nz < n and not seen[nx][nz]:
                cand.append((nx, nz, dx, dz))
        if not cand:
            stack.pop()
            continue
        nx, nz, dx, dz = r.choice(cand)
        seen[nx][nz] = True
        g[2 * cx + 1 + dx][2 * cz + 1 + dz] = 0           # 間の壁を壊す
        g[2 * nx + 1][2 * nz + 1] = 0
        stack.append((nx, nz))
    return g

# 【迷路追加】
def maze_blocked(x, z):                               # 迷路内の座標が壁かどうか
    a = int((x - MAZE_ORIGIN.x) / MRES)
    b = int((z - MAZE_ORIGIN.z) / MRES)
    if a < 0 or b < 0 or a >= MGRID or b >= MGRID: return True
    return maze_solid[a][b]

# 【迷路追加】
def set_fog(density=0.0):                             # 迷路の霧（0で解除）
    global maze_fog
    try:
        from panda3d.core import Fog
        if density <= 0:
            if maze_fog is not None:
                maze_fog = None
                render.clearFog()
            return
        if maze_fog is None:
            maze_fog = Fog('maze_fog')
            maze_fog.setColor(0.03, 0.02, 0.05)
            render.setFog(maze_fog)
        maze_fog.setExpDensity(density)
    except Exception:
        pass

# 【迷路追加】
def build_maze():                                     # 壁を1メッシュにまとめて生成＋当たり判定テーブル
    global maze_root, maze_grid, maze_solid, maze_goal, maze_start
    maze_grid = gen_maze(MAZE_N)
    maze_root = Entity(position=MAZE_ORIGIN)
    tex = maze_texture()
    rr = random.Random(2024)
    TUV = 0.25                                        # テクスチャの繰り返し（4mで1枚）
    verts, tris, uvs, cols = [], [], [], []

    def add_quad(p0, p1, p2, p3, uv, sh):
        b = len(verts)
        verts.extend((p0, p1, p2, p3))
        uvs.extend(uv)
        tris.extend((b, b + 1, b + 2, b, b + 2, b + 3))
        cols.extend((sh, sh, sh, sh))

    N2 = 2 * MAZE_N
    def is_open(i, j):
        return 0 <= i <= N2 and 0 <= j <= N2 and maze_grid[i][j] == 0

    for i in range(N2 + 1):
        for j in range(N2 + 1):
            if maze_grid[i][j] == 0: continue
            x0, w = span(i)
            z0, d = span(j)
            x1, z1 = x0 + w, z0 + d
            gg = rr.randint(78, 112)                  # 壁ごとに濃さを変えてまだらに見せる
            sh = color.rgb32(gg, int(gg * 0.80), int(gg * 1.10))
            sht = color.rgb32(int(gg * 0.72), int(gg * 0.60), int(gg * 0.84))
            if is_open(i - 1, j):                     # -x 面
                add_quad((x0, 0, z0), (x0, 0, z1), (x0, MAZE_H, z1), (x0, MAZE_H, z0),
                         [(z0 * TUV, 0), (z1 * TUV, 0), (z1 * TUV, MAZE_H * TUV), (z0 * TUV, MAZE_H * TUV)], sh)
            if is_open(i + 1, j):                     # +x 面
                add_quad((x1, 0, z1), (x1, 0, z0), (x1, MAZE_H, z0), (x1, MAZE_H, z1),
                         [(z1 * TUV, 0), (z0 * TUV, 0), (z0 * TUV, MAZE_H * TUV), (z1 * TUV, MAZE_H * TUV)], sh)
            if is_open(i, j - 1):                     # -z 面
                add_quad((x1, 0, z0), (x0, 0, z0), (x0, MAZE_H, z0), (x1, MAZE_H, z0),
                         [(x1 * TUV, 0), (x0 * TUV, 0), (x0 * TUV, MAZE_H * TUV), (x1 * TUV, MAZE_H * TUV)], sh)
            if is_open(i, j + 1):                     # +z 面
                add_quad((x0, 0, z1), (x1, 0, z1), (x1, MAZE_H, z1), (x0, MAZE_H, z1),
                         [(x0 * TUV, 0), (x1 * TUV, 0), (x1 * TUV, MAZE_H * TUV), (x0 * TUV, MAZE_H * TUV)], sh)
            add_quad((x0, MAZE_H, z0), (x1, MAZE_H, z0), (x1, MAZE_H, z1), (x0, MAZE_H, z1),   # 壁の上面
                     [(x0 * TUV, z0 * TUV), (x1 * TUV, z0 * TUV), (x1 * TUV, z1 * TUV), (x0 * TUV, z1 * TUV)], sht)

    f = MAZE_SPAN                                     # 床（迷路全体を覆う1枚板）
    add_quad((0, 0, 0), (f, 0, 0), (f, 0, f), (0, 0, f),
             [(0, 0), (f * TUV, 0), (f * TUV, f * TUV), (0, f * TUV)], color.rgb32(34, 27, 40))

    Entity(parent=maze_root, model=Mesh(vertices=verts, triangles=tris, uvs=uvs, colors=cols),
           texture=tex, color=color.white, double_sided=True)
    
    # ===== 【追加】島が見えないように迷路の四方を黒い壁で囲む =====
    FENCE_H, FENCE_GAP, FENCE_T = 40, 6, 1
    half = MAZE_SPAN / 2
    side = MAZE_SPAN + FENCE_GAP * 2 + FENCE_T
    off = half + FENCE_GAP
    for px, pz, sx, sz in ((-off + half, half, FENCE_T, side),
                           (off + half, half, FENCE_T, side),
                           (half, -off + half, side, FENCE_T),
                           (half, off + half, side, FENCE_T)):
        Entity(parent=maze_root, model='cube', position=(px, FENCE_H / 2, pz),
               scale=(sx, FENCE_H, sz), color=color.black)
    # ===== 【追加】ここまで =====

    # --- スタートとゴール ---
    c0 = span(1)[0] + PASS_W / 2
    c1 = span(N2 - 1)[0] + PASS_W / 2
    maze_start = Vec3(MAZE_ORIGIN.x + c0, 0, MAZE_ORIGIN.z + c0)
    maze_goal = Vec3(MAZE_ORIGIN.x + c1, 0, MAZE_ORIGIN.z + c1)
    Entity(parent=maze_root, model='cube', position=(c1, 6, c1), scale=(0.6, 12, 0.6), color=color.rgba32(120, 255, 255, 220))   # 光の柱
    Entity(parent=maze_root, model='sphere', position=(c1, 0.25, c1), scale=1.5, color=color.rgba32(120, 255, 255, 140))

    # --- 当たり判定テーブル（壁を半径ぶん膨らませて0.5m刻みで塗る） ---
    maze_solid = [[False] * MGRID for _ in range(MGRID)]
    for i in range(N2 + 1):
        for j in range(N2 + 1):
            if maze_grid[i][j] == 0: continue
            x0, w = span(i)
            z0, d = span(j)
            a0 = max(0, int((x0 - PLAYER_R) / MRES)); a1 = min(MGRID - 1, int((x0 + w + PLAYER_R) / MRES))
            b0 = max(0, int((z0 - PLAYER_R) / MRES)); b1 = min(MGRID - 1, int((z0 + d + PLAYER_R) / MRES))
            for a in range(a0, a1 + 1):
                row = maze_solid[a]
                for b in range(b0, b1 + 1):
                    row[b] = True

    # --- 雰囲気づくり：暗がりの赤い眼と瓦礫 ---
    cells = [(i, j) for i in range(1, N2, 2) for j in range(1, N2, 2)]
    for i, j in rr.sample(cells, 10):
        x0, _ = span(i); z0, _ = span(j)
        ex, ez = x0 + rr.uniform(1, PASS_W - 1), z0 + rr.uniform(1, PASS_W - 1)
        for dx in (-0.17, 0.17):
            Entity(parent=maze_root, model='sphere', position=(ex + dx, 1.7 + rr.uniform(-0.25, 0.25), ez),
                   scale=0.11, color=color.rgba32(255, 40, 40, 255))
    for _ in range(26):                               # 床の瓦礫
        i, j = rr.choice(cells)
        x0, _ = span(i); z0, _ = span(j)
        s = rr.uniform(0.15, 0.5)
        Entity(parent=maze_root, model='cube', position=(x0 + rr.uniform(0.5, PASS_W - 0.5), s / 2, z0 + rr.uniform(0.5, PASS_W - 0.5)),
               scale=(s * 1.4, s, s), rotation_y=rr.uniform(0, 180), color=color.rgb32(52, 44, 58))

# 【迷路追加】
def destroy_maze():
    global maze_root, maze_grid, maze_solid
    if maze_root is not None:
        destroy(maze_root)
        maze_root = None
    maze_grid, maze_solid = [], []

# 【迷路追加】
def enter_maze(title, col=color.light_gray):           # ボートで島を出た（謎が残っている）とき
    global maze_pending
    player.enabled = False
    say(title + '\n\n…ふと足元が崩れ、暗い迷路へ落ちていく', 3.5, col)
    maze_pending = 3.5

# 【迷路追加】
def enter_maze_now():
    global in_maze, maze_prev, maze_out, game_over, ending, hp
    build_maze()
    in_maze, game_over, ending, maze_out = True, False, False, None
    hp = HP_MAX
    hud(False)                                        # 迷路では体力ゲージを隠す
    player.enabled = True
    player.vy = 0
    player.camera_pivot.rotation_x = 0
    player.rotation_y = 0
    player.position = maze_start + Vec3(0, 0.05, 0)
    maze_prev = Vec3(player.x, player.y, player.z)
    set_sky(SKY_DARK)
    set_fog(0.035)
    say('…ここはどこだ？\nSpaceで跳ぶと迷路の形が見える\nシアンの光の柱がゴールだ', 4.5, color.violet)

# 【迷路追加】
def leave_maze():                                     # ゴール：迷路を消して島の最初から
    global in_maze, maze_out, maze_pending
    in_maze, maze_out, maze_pending = False, None, None
    set_fog(0)
    restart()
    say('光の柱に触れた…\n気がつくと島の浜辺に戻されていた（はじめから）', 4.5, color.cyan)

# 【迷路追加】
def reach_goal():
    global maze_out
    if maze_out is not None: return
    maze_out = 2.2
    player.enabled = False
    say('光の柱にたどり着いた…視界が白く染まる', 2.2, color.cyan)

# 【迷路追加】
def update_maze():
    global maze_prev, maze_out
    if maze_out is not None:
        maze_out -= time.dt
        if maze_out <= 0:
            maze_out = None
            leave_maze()
        return
    player.speed = DASH_SPEED if held_keys['q'] else WALK_SPEED      # 迷路でもQダッシュ
    x, z = player.x, player.z                         # 壁は軸ごとに押し戻す（壁づたいに滑れる）
    px, pz = maze_prev.x, maze_prev.z
    if maze_blocked(x, z):
        if not maze_blocked(x, pz): player.z = pz
        elif not maze_blocked(px, z): player.x = px
        else: player.x, player.z = px, pz
    maze_prev = Vec3(player.x, player.y, player.z)
    apply_ground(0.0)                                 # 迷路は完全な平面（height()は使わない）
    if math.hypot(player.x - maze_goal.x, player.z - maze_goal.z) < 1.7:
        reach_goal()

# ===== 【迷路追加】ここまで：迷路のテクスチャ・生成・当たり判定・移動・ゴール =====

# ===== 【迷路追加】ここから：迷路から島へ強制帰還（デバッグメニュー6番） =====
def warp_to_island():
    """迷路ステージ中なら、島の進行状況を保ったまま島のスタート地点へ戻す。迷路にいなければ何もしない。"""
    global in_maze, maze_pending, maze_out, game_over, hp, last_pos
    if not in_maze:                                   # 迷路にいないときは何もしない
        say('いまは迷路ステージにいない（島にいる）', 2, color.light_gray)
        return
    in_maze, maze_pending, maze_out = False, None, None    # 迷路の状態を解除
    destroy_maze()                                         # 迷路のジオメトリを破棄
    set_fog(0)                                             # 霧を消す
    set_sky(SKY_BLUE)                                      # 空を昼に戻す
    hud(True)                                              # 体力ゲージを戻す
    hp = HP_MAX
    game_over = False
    player.enabled = True
    player.vy, player.grounded = 0, True
    player.camera_pivot.rotation_x = 0
    player.rotation_y = 0
    player.position = Vec3(0, height(0, -50) + 2, -50)      # 島のスタート地点
    last_pos = player.position
    say('迷路から島へ帰還した（デバッグ）', 2.5, color.cyan)
# ===== 【迷路追加】ここまで：迷路から島へ強制帰還 =====

# ===== 12. デバッグメニュー（;キーで開閉。数字キーかクリックで実行） =====
DEBUG = [('木片を全部回収する（ボートが出る）', lambda: [collect_wood(w) for w in woods[:]]),
         ('謎1のフラグを立てる（紙を読む→首が出る）', start_quest1),
         ('謎1の首を全部回収する（敵が消えボス出現）', solve_quest1),
         ('謎2：ボスを覚醒させる（🫵🫪🫵に変化・空が暗くなる）', trigger_boss),
         ('謎2の生首を全部踏みつぶす（島が平和に）', stomp_all),
         ('迷路ステージから島へ帰る（迷路にいるときのみ）', warp_to_island)]   # 【迷路追加】旧：テスト用に迷路へワープする項目を置き換え
debug_menu = Entity(parent=camera.ui, enabled=False)
Entity(parent=debug_menu, model='quad', scale=(0.82, 0.86), color=color.rgba32(0, 0, 0, 150), z=0.1)
Text('デバッグメニュー（;キーで開閉）', parent=debug_menu, y=0.4, origin=(0, 0), scale=1.3, color=color.yellow)
def run_debug(action):                                # 実行前にメニューを閉じる（閉じたままだとゲームが止まる）
    debug_menu.enabled = False
    player.enabled = not game_over
    action()

for i, (label, action) in enumerate(DEBUG):
    Button(text=f'{i + 1}. {label}', parent=debug_menu, scale=(0.76, 0.095), y=0.29 - i * 0.105, text_color=color.white,
           color=color.rgb32(60, 60, 60), highlight_color=color.azure, on_click=lambda a=action: run_debug(a))

# ===== 13. 毎フレームの処理 =====
def dist_to(e): return math.hypot(player.x - e.x, player.z - e.z)

def chase(e, speed, lift=0):                          # eをプレイヤーへ向け、地形の高さに沿って動かす
    dx, dz = player.x - e.x, player.z - e.z
    d = math.hypot(dx, dz)
    e.x += dx / d * speed * time.dt
    e.z += dz / d * speed * time.dt
    e.y = height(e.x, e.z) + lift
    e.rotation_y = math.degrees(math.atan2(dx, dz))

def apply_ground(gy):                                 # 地面の高さgyに対して接地／落下を処理
    if player.vy <= 0 and player.y - gy < STEP_SNAP:  # 地面のすぐ上なら吸着して歩く
        player.y = gy if player.y < gy else lerp(player.y, gy, min(1, FOLLOW * time.dt))   # 上りは即座／下りはなめらか
        player.vy, player.grounded = 0, True
    else:                                             # ジャンプ中／高い所からは落下
        player.vy -= GRAVITY * time.dt
        player.y += player.vy * time.dt
        player.grounded = False
        if player.y < gy - 1: player.y, player.vy = gy, 0

def update():
    global last_pos, msg_time, hp, hold, boss_state, boss_wait, maze_pending
    if debug_menu.enabled: return                     # メニュー中はゲーム全体を一時停止
    msg_time -= time.dt
    if msg.text and msg_time < 0: msg.text = ''
    sea.y = math.sin(time.time()) * 0.05              # 海がゆらゆら
    clouds.rotation_y += time.dt * 0.5                # 雲が流れる
    # --- 【迷路追加】ここから：迷路への切替と迷路中の更新（島の処理は一切通さない） ---
    if maze_pending is not None:                       # 迷路へ落ちる演出の待ち
        maze_pending -= time.dt
        if maze_pending <= 0:
            maze_pending = None
            enter_maze_now()
        return
    if in_maze:                                       # 迷路ステージ中はこちらの更新だけを回す
        update_maze()
        return
    # --- 【迷路追加】ここまで ---
    if game_over:
        if ending:                                    # ALLクリア演出：舟が沖へ、カメラが三人称で追う
            if ride.z > -190: ride.z -= 4 * time.dt
            camera.world_position = ride.world_position + END_CAM
            camera.look_at(ride.world_position + Vec3(0, 1.9, 0))
        return
    player.speed = DASH_SPEED if held_keys['q'] else WALK_SPEED
    for w in woods: w.rotation_y += 60 * time.dt      # 木片をくるくる

    hp -= HP_DRAIN * time.dt
    hp_bar.scale_x = 0.4 * max(hp, 0) / HP_MAX
    hp_bar.color = color.red if hp < 30 else color.lime
    if hp <= 0: return end_game('ゲームオーバー', color.red)

    target = look() if held_keys['e'] else None       # 敵の首：Eを10秒押し続けると回収
    hold = hold + time.dt if target in heads else 0
    prog_bar.scale_x = 0.3 * min(hold / 10, 1)
    prog_label.enabled = prog_back.enabled = prog_bar.enabled = hold > 0
    if hold >= 10: remove_head(target)

    if boss_state == 'wait':                          # ボス：認識されて4秒待ってから追跡
        boss_wait -= time.dt
        if boss_wait <= 0: boss_state = 'chase'
    alert.enabled = boss_state == 'wait'
    if boss_state == 'chase':
        if dist_to(boss) < 2.0: return end_game('ゲームオーバー', color.red)
        chase(boss, BOSS_SPEED, 1.4)
        boss.t += time.dt
        boss.warp.rotation_z = math.sin(boss.t * 6) * 10     # ゆらゆら揺れる

    for st in stomps[:]:                              # 生首の「上に乗った」ら踏みつぶす
        if dist_to(st) < 0.7 and st.top - 0.2 < player.y < st.top + 0.8: stomp_one(st)

    for e in enemies:                                 # 敵：範囲内に入ったら追いかける
        d = dist_to(e)
        if d < 1.3: return end_game('ゲームオーバー', color.red)
        if d < CHASE_RANGE:
            chase(e, ENEMY_SPEED); e.walk += time.dt * 8
        swing = math.sin(e.walk) if d < CHASE_RANGE else 0   # 追跡中だけ腕と脚を振る
        e.legs[0].rotation_x, e.legs[1].rotation_x = swing * 35, -swing * 35
        e.arms[0].rotation_x, e.arms[1].rotation_x = -80 + swing * 10, -80 - swing * 10

    gy = height(player.x, player.z)                   # 接地：高さ関数から自前で計算
    for st in stomps:                                 # 生首の上には乗れる（踏む判定のため）
        if math.hypot(player.x - st.x, player.z - st.z) < 0.75 and gy < st.top <= player.y + 0.25: gy = st.top
    apply_ground(gy)

    if math.hypot(player.x, player.z) > SIZE * 0.95: player.position = last_pos   # 沖には出られない
    else: last_pos = player.position

def look():                                           # 画面中央(照準)の先5m以内にあるもの
    return raycast(camera.world_position, camera.forward, distance=5, ignore=[player]).entity

def input(key):
    global hp
    if key == 'escape': application.quit()
    if key == DEBUG_KEY:                              # メニューを開くとプレイヤーを止め、マウスを使えるように
        debug_menu.enabled = not debug_menu.enabled
        player.enabled = not (debug_menu.enabled or game_over)
    elif debug_menu.enabled and key.isdigit() and 1 <= int(key) <= len(DEBUG):
        run_debug(DEBUG[int(key) - 1][1])
    elif game_over and key == 'enter': restart()
    elif key == 'e' and not (game_over or debug_menu.enabled or in_maze):
        target = look()                               # 照準の先にあるもので分岐
        if target in woods: collect_wood(target)
        elif target in coconuts:                      # ヤシの実：体力を半分回復
            coconuts.remove(target); destroy(target)
            hp = min(HP_MAX, hp + HP_MAX / 2)
            say('ヤシの実を食べた！体力回復')
        elif target == stump:                         # 切り株の紙
            start_quest1()
            if not solved: say('紙にはこう書かれている…\n「敵の首を2つ集めよ。首は廃墟小屋にある」', 5)
        elif target in heads: say('Eを10秒間押し続けて首を回収する', 2)
        elif boss and target == boss and boss_state == 'idle': trigger_boss()
        elif boat and target == boat:                 # ボートでクリア。謎の解決度で結末が変わる
            if peace:                                 #   全謎クリア：舟出演出つき
                end_game('すべての謎を解決し、島は平和になった！\nALLクリア！', color.gold)
                escape_ending()
            # 【迷路追加】ここから：謎が残っている／何もなしえない結末は迷路ステージへ
            elif solved: enter_maze('ゲームクリア\nしかしまだ謎は残っている...', color.gold)
            else: enter_maze('ゲームクリア？\nあなたは何もなしえず島を出た...', color.light_gray)
            # 【迷路追加】ここまで

restart()
app.run()
