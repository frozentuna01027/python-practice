"""
無人島脱出ゲーム：木片を10個集めてボートで脱出しよう
・体力は1分で0になる → ヤシの実(E)で半分回復   ・🥺に捕まる／体力0でゲームオーバー
・島の謎：切り株の紙(E)を読む → 廃墟小屋の「敵の首」を2つ回収(Eを10秒長押し) → 敵が消える
操作: WASD=移動 / Q長押し=ダッシュ / Space=ジャンプ / E=調べる・回収・ボートに乗る / Enter=再スタート / Esc=終了
"""
from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController
import math, os, random, shutil

app = Ursina(title='Island')
random.seed(1)

# 日本語フォント：Windows標準のMSゴシックをこのフォルダにコピーして使う
font = application.asset_folder / 'msgothic.ttc'
if not font.exists() and os.path.exists(r'C:\Windows\Fonts\msgothic.ttc'):
    shutil.copy(r'C:\Windows\Fonts\msgothic.ttc', font)
if font.exists():
    Text.default_font = font.name

WALK_SPEED = 5      # 歩く速さ
DASH_SPEED = 9      # Qキーでダッシュ
ENEMY_SPEED = 4.5   # 敵の速さ（歩きより少しだけ遅い）
CHASE_RANGE = 25    # この距離までプレイヤーが近づくと敵が追いかけてくる
ENEMY_STARTS = [(0, 60), (-45, -35), (45, -40), (-35, 45), (55, 15)]   # 敵5体の初期位置
HP_MAX = 100
HP_DRAIN = HP_MAX / 60   # 何もしないと60秒で体力0

# ---------------------------------------------------------
# 1. 地形：高さを計算する関数（中心ほど高く、海に近づくほど低い）
# ---------------------------------------------------------
SIZE = 80          # 島の半径
STEP = 4           # 地形の格子の細かさ


def height(x, z):
    d = math.hypot(x, z) / SIZE
    h = (1 - d * d) * 8 - 1                                        # お椀を伏せた形
    h += math.sin(x * 0.1) * math.cos(z * 0.12) * 1.5 * (1 - d)    # 起伏
    return max(h, -3)


# ---------------------------------------------------------
# 2. 地形メッシュ：格子点の高さを三角形でつなぐ
# ---------------------------------------------------------
def make_terrain():
    n = int(2 * SIZE * 1.25 / STEP)
    verts, colors, tris = [], [], []
    for i in range(n + 1):
        for j in range(n + 1):
            x, z = -SIZE * 1.25 + i * STEP, -SIZE * 1.25 + j * STEP
            h = height(x, z)
            verts.append((x, h, z))
            colors.append(color.rgb32(230, 210, 150) if h < 1 else color.rgb32(70, 150, 60))
    for i in range(n):
        for j in range(n):
            a = i * (n + 1) + j
            tris.append((a, a + n + 1, a + 1))
            tris.append((a + 1, a + n + 1, a + n + 2))
    return Entity(model=Mesh(vertices=verts, triangles=tris, colors=colors),
                  collider='mesh', double_sided=True)


terrain = make_terrain()
sea = Entity(model='plane', scale=500, y=0, color=color.rgba32(30, 110, 190, 200))
Sky(texture=None, color=color.rgb32(20, 130, 255))   # 鮮やかな青空


# ---------------------------------------------------------
# 3. 廃墟：壁(直方体)を並べる
# ---------------------------------------------------------
def wall(x, z, w, d, h, y0, tex='brick', col=color.white):
    Entity(model='cube', position=(x, y0 + h / 2, z), scale=(w, h, d), color=col,
           texture=tex, texture_scale=(max(w, d) / 2, h / 2), collider='box')


def ruin(cx, cz):
    y0 = height(cx, cz)
    wall(cx - 5, cz,     0.5, 10, 3.0, y0)
    wall(cx + 5, cz,     0.5, 10, 1.5, y0)
    wall(cx - 3, cz + 5, 4,   0.5, 3.5, y0)
    wall(cx + 3, cz + 5, 4,   0.5, 1.0, y0)
    wall(cx - 3, cz - 5, 4,   0.5, 2.5, y0)
    wall(cx + 2, cz - 5, 3,   0.5, 3.0, y0)
    wall(cx - 5, cz - 5, 1,   1,   4.5, y0)


def hut(cx, cz):
    """廃墟小屋：朽ちた木の壁と、一部だけ残った屋根（入口は手前側）"""
    y0 = height(cx, cz) - 0.4                         # 斜面でも隙間が出ないよう少し埋める
    g = color.rgb32(110, 85, 60)
    wall(cx,       cz + 2.5, 5,   0.3, 3.0, y0, None, g)     # 奥の壁
    wall(cx - 2.5, cz,       0.3, 5,   3.0, y0, None, g)     # 左の壁
    wall(cx + 2.5, cz,       0.3, 5,   1.8, y0, None, g)     # 右の壁（崩れて低い）
    wall(cx - 1.5, cz - 2.5, 2,   0.3, 3.0, y0, None, g)     # 手前の壁（入口の左）
    wall(cx + 1.8, cz - 2.5, 1.4, 0.3, 1.4, y0, None, g)     # 手前の壁（入口の右・低い）
    wall(cx - 1,   cz + 1,   3,   3.5, 0.2, y0 + 3.0, None, color.rgb32(70, 55, 40))   # 残った屋根


ruin(0, 10)
HUTS = [(25, -10), (-50, 5)]
for x, z in HUTS:
    hut(x, z)


# ---------------------------------------------------------
# 4. ヤシの木：幹＋葉
# ---------------------------------------------------------
def tree(x, z):
    y0 = height(x, z)
    Entity(model='cube', position=(x, y0 + 2.5, z), scale=(0.4, 5, 0.4),
           color=color.rgb32(110, 80, 50), collider='box')
    Entity(model='sphere', position=(x, y0 + 5.5, z), scale=(4, 1.5, 4),
           color=color.rgb32(40, 140, 50))


def coconut(x, z):
    return Entity(model='sphere', position=(x, height(x, z) + 0.2, z), scale=0.45,
                  color=color.rgb32(110, 70, 35), collider='box')


coconut_spots = []                                      # ヤシの実を置く場所
count = 0
for _ in range(60):
    x, z = random.uniform(-SIZE, SIZE), random.uniform(-SIZE, SIZE)
    if 0.5 < height(x, z) < 4:
        tree(x, z)
        count += 1
        if count % 2 == 0:                              # 2本に1本の木の下に、ヤシの実を2つ
            coconut_spots += [(x + 0.9, z + 0.3), (x - 0.8, z - 0.4)]
coconuts = [coconut(x, z) for x, z in coconut_spots]


# ---------------------------------------------------------
# 5. 木片：島に10個。見つけやすいよう黄色い光の柱つき
# ---------------------------------------------------------
def wood(x, z):
    w = Entity(position=(x, height(x, z) + 0.5, z), collider='box')   # 当たり判定(1m立方)
    Entity(parent=w, model='cube', scale=(1, 0.25, 0.25), color=color.orange)   # 木片
    Entity(parent=w, model='cube', scale=(0.08, 20, 0.08), y=10, color=color.yellow)  # 光の柱
    return w


spots = [(0, 10), (-30, -20), (20, -30), (-40, 20), (35, 25),
         (10, 40), (-15, -50), (50, -10), (-55, -10), (45, 45)]
woods = [wood(x, z) for x, z in spots]
boat = None


def make_boat():
    """全部集めたら砂浜にボートを出す（部品はshipの子にして、まとめて消せるようにする）"""
    ship = Entity(position=(0, height(0, -72) + 0.4, -72))
    Entity(parent=ship, model='cube', y=3, scale=(0.2, 5, 0.2), color=color.dark_gray)     # マスト
    Entity(parent=ship, model='cube', y=3.5, scale=(0.05, 3, 3), color=color.white)        # 帆
    Entity(parent=ship, model='cube', y=10, scale=(0.1, 20, 0.1), color=color.cyan)        # 目印の光の柱
    return Entity(parent=ship, model='cube', scale=(7, 1, 3),
                  color=color.rgb32(120, 80, 50), collider='box')                          # 船体


# ---------------------------------------------------------
# 5.5 島の謎：切り株の上の紙 → 廃墟小屋の「敵の首」
# ---------------------------------------------------------
def make_stump(x, z):
    y0 = height(x, z)
    stump = Entity(model='cube', position=(x, y0 + 0.4, z), scale=(1.4, 0.8, 1.4),
                   color=color.rgb32(100, 70, 40), collider='box')
    Entity(model='cube', position=(x, y0 + 0.81, z), scale=(1.2, 0.04, 1.2), color=color.rgb32(190, 150, 100))   # 切り口
    paper = Entity(model='cube', position=(x, y0 + 0.85, z), scale=(0.6, 0.05, 0.8), rotation_y=25,
                   color=color.white, collider='box')                                                          # 白い紙
    Entity(model='cube', position=(x, y0 + 10, z), scale=(0.1, 20, 0.1), color=color.white)                    # 目印の光の柱
    return stump, paper


stump, paper = make_stump(-60, 20)                       # スタート地点から遠い場所
head_spots = [(x - 1, z + 1.2) for x, z in HUTS]         # 首は各小屋の中に1つずつ
heads = []
quest_started = False        # 紙を読んだか
solved = False               # 首を2つ集めて敵を消したか
hold = 0                     # Eを押し続けている秒数


# ---------------------------------------------------------
# 6. 敵キャラ：🥺（頭・胴体・腕・脚）
# ---------------------------------------------------------
YELLOW = color.rgb32(255, 205, 50)


def part(parent, model, pos, scale, col, **kw):
    return Entity(parent=parent, model=model, position=pos, scale=scale, color=col, **kw)


def face(e, y):
    """🥺の頭（敵の頭と、小屋に置く「首」で共用）"""
    part(e, 'sphere', (0, y, 0), (1, 1, 1), YELLOW)                                    # 頭
    for s in (-1, 1):                                                                   # s=-1:左, 1:右
        part(e, 'sphere', (s * 0.17, y + 0.05, 0.44), (0.2, 0.27, 0.08), color.rgb32(60, 30, 20))   # うるうるの大きな目
        part(e, 'sphere', (s * 0.14, y + 0.13, 0.48), (0.07, 0.07, 0.04), color.white)              # 目のハイライト
        part(e, 'cube', (s * 0.17, y + 0.35, 0.40), (0.18, 0.04, 0.04), color.rgb32(120, 70, 20),
             rotation_z=s * 20)                                                                      # 困り眉
    part(e, 'cube', (0, y - 0.27, 0.45), (0.1, 0.03, 0.03), color.rgb32(120, 50, 30))                # 小さな口


def make_enemy(x, z):
    e = Entity(position=(x, height(x, z), z))
    part(e, 'cube', (0, 1.4, 0), (0.9, 1.0, 0.5), color.rgb32(230, 120, 40))     # 胴体
    face(e, 2.4)                                                                  # 頭
    # 腕と脚は付け根に回転の中心(関節)を置き、前に伸ばした腕と歩く脚を振る
    e.arms = [Entity(parent=e, position=(s * 0.6, 1.85, 0), rotation_x=-80) for s in (-1, 1)]
    e.legs = [Entity(parent=e, position=(s * 0.25, 0.9, 0)) for s in (-1, 1)]
    for a in e.arms:
        part(a, 'cube', (0, -0.4, 0), (0.25, 0.8, 0.25), YELLOW)
    for l in e.legs:
        part(l, 'cube', (0, -0.45, 0), (0.3, 0.9, 0.3), color.rgb32(50, 60, 140))
    e.walk = 0
    return e


def make_head(x, z):
    """小屋に置く敵の首（入口の方を向く。赤い光の柱つき）"""
    h = Entity(position=(x, height(x, z) + 0.5, z), rotation_y=180, collider='box')
    face(h, 0)
    Entity(parent=h, model='cube', scale=(0.08, 20, 0.08), y=10, color=color.red)
    return h


# ---------------------------------------------------------
# 7. プレイヤー・メッセージ・ゲーム進行
# ---------------------------------------------------------
player = FirstPersonController(position=(0, height(0, -50) + 2, -50))
enemies = [make_enemy(x, z) for x, z in ENEMY_STARTS]
last_pos = player.position
game_over = False
hp = HP_MAX

# 首を回収中の進行ゲージ（画面中央の下）
prog_label = Text('首を回収中…', origin=(0, 0), position=(0, -0.07), scale=1.3, enabled=False)
prog_back = Entity(parent=camera.ui, model='quad', color=color.black66, z=0.1, scale=(0.3, 0.025),
                   origin=(-0.5, 0), position=(-0.15, -0.11), enabled=False)
prog_bar = Entity(parent=camera.ui, model='quad', color=color.orange, scale=(0.3, 0.025),
                  origin=(-0.5, 0), position=(-0.15, -0.11), enabled=False)

# 体力ゲージ（左上）
Text('体力', parent=camera.ui, origin=(-0.5, 0.5), position=window.top_left + Vec2(0.02, -0.02), scale=1.3)
hp_back = Entity(parent=camera.ui, model='quad', color=color.black66, z=0.1, scale=(0.4, 0.035),
                 origin=(-0.5, 0.5), position=window.top_left + Vec2(0.1, -0.02))
hp_bar = Entity(parent=camera.ui, model='quad', color=color.lime, scale=(0.4, 0.035),
                origin=(-0.5, 0.5), position=window.top_left + Vec2(0.1, -0.02))

msg = Text('', origin=(0, 0), y=0.3, scale=2, color=color.yellow)
msg_time = 0


def say(text, sec=1, col=color.yellow):
    """画面中央にsec秒だけ文字を出す"""
    global msg_time
    msg.text, msg.color, msg_time = text, col, sec


def end_game(title, col):
    """ゲームオーバー／クリア画面。Enterで再スタート"""
    global game_over
    game_over = True
    player.enabled = False
    say(title + '\n\nEnterキーで再スタート', 999, col)


def restart():
    """全部を最初の状態に戻す"""
    global boat, game_over, hp, quest_started, solved, hold
    for w in woods:
        destroy(w)
    woods[:] = [wood(x, z) for x, z in spots]
    for c in coconuts:
        destroy(c)
    coconuts[:] = [coconut(x, z) for x, z in coconut_spots]
    if boat:
        destroy(boat.parent)
        boat = None
    player.position = (0, height(0, -50) + 2, -50)
    player.rotation_y = 0
    player.camera_pivot.rotation_x = 0
    player.enabled = True
    for e in enemies:                                   # 消えていた敵も含めて作り直す
        destroy(e)
    enemies[:] = [make_enemy(x, z) for x, z in ENEMY_STARTS]
    for h in heads:
        destroy(h)
    heads.clear()
    quest_started = solved = False
    hold = 0
    hp = HP_MAX
    game_over = False
    say('木片を10個集めよう！体力が尽きる前にヤシの実を食べよう', 3)


say('木片を10個集めよう！体力が尽きる前にヤシの実を食べよう', 3)


def update():
    global last_pos, msg_time, hp, hold, solved
    msg_time -= time.dt
    if msg.text and msg_time < 0:                       # 表示時間が過ぎたら消す
        msg.text = ''
    if game_over:
        return

    player.speed = DASH_SPEED if held_keys['q'] else WALK_SPEED    # Qでダッシュ
    for w in woods:                                     # 木片をくるくる回す
        w.rotation_y += 60 * time.dt

    # --- 体力：時間とともに減る。0でゲームオーバー ---
    hp -= HP_DRAIN * time.dt
    hp_bar.scale_x = 0.4 * max(hp, 0) / HP_MAX
    hp_bar.color = color.red if hp < 30 else color.lime
    if hp <= 0:
        end_game('ゲームオーバー', color.red)
        return

    # --- 敵の首：照準を合わせてEを10秒押し続けると回収できる ---
    target = look() if held_keys['e'] else None
    if target in heads:
        hold += time.dt
        prog_bar.scale_x = 0.3 * min(hold / 10, 1)
        if hold >= 10:
            heads.remove(target)
            destroy(target)
            hold = 0
            if heads:
                say('敵の首を回収した！残り1つ', 2)
            else:                                       # 2つ集めたら敵が消えて、島の謎が解ける
                solved = True
                for e in enemies:
                    destroy(e)
                enemies.clear()
                say('首を2つ集めた…敵が消えていく\n島の謎が解けた！', 4)
    else:
        hold = 0
    prog_label.enabled = prog_back.enabled = prog_bar.enabled = hold > 0

    # --- 敵：範囲内にプレイヤーがいたら、まっすぐ追いかける ---
    for e in enemies:
        dx, dz = player.x - e.x, player.z - e.z
        dist = math.hypot(dx, dz)
        if dist < 1.3:                                  # 捕まった！
            end_game('ゲームオーバー', color.red)
            return
        chasing = dist < CHASE_RANGE
        if chasing:
            e.x += dx / dist * ENEMY_SPEED * time.dt
            e.z += dz / dist * ENEMY_SPEED * time.dt
            e.y = height(e.x, e.z)
            e.rotation_y = math.degrees(math.atan2(dx, dz))
            e.walk += time.dt * 8
        swing = math.sin(e.walk) if chasing else 0      # 追跡中だけ腕と脚を振る
        e.legs[0].rotation_x, e.legs[1].rotation_x = swing * 35, -swing * 35
        e.arms[0].rotation_x, e.arms[1].rotation_x = -80 + swing * 10, -80 - swing * 10

    if math.hypot(player.x, player.z) > SIZE * 0.95:    # 沖には出られない
        player.position = last_pos
    else:
        last_pos = player.position


def look():
    """画面中央(照準)の先5m以内にあるもの"""
    return raycast(camera.world_position, camera.forward, distance=5, ignore=[player]).entity


def input(key):
    global boat, hp, quest_started
    if key == 'escape':
        application.quit()
    if game_over:
        if key == 'enter':
            restart()
        return
    if key != 'e':
        return
    target = look()
    if target in woods:                                 # 木片を回収
        woods.remove(target)
        destroy(target)
        if woods:
            say(f'残り {len(woods)}/10')
        else:
            boat = make_boat()
            say('ボートが完成した！脱出しよう！', 3)
    elif target in coconuts:                            # ヤシの実を食べて体力を半分回復
        coconuts.remove(target)
        destroy(target)
        hp = min(HP_MAX, hp + HP_MAX / 2)
        say('ヤシの実を食べた！体力回復')
    elif target in (stump, paper):                      # 切り株の紙を読む
        if not quest_started:                           # 初回：小屋に敵の首が現れる
            quest_started = True
            heads[:] = [make_head(x, z) for x, z in head_spots]
        if not solved:
            say('紙にはこう書かれている…\n「敵の首を2つ集めよ。首は廃墟小屋にある」', 5)
    elif target in heads:
        say('Eを10秒間押し続けて首を回収する', 2)
    elif boat and target == boat:                       # ボートに乗ってクリア。謎を解いたかで評価が変わる
        if solved:
            end_game('ゲームクリア！\n評価：excellent!', color.gold)
        else:
            end_game('ゲームクリア！\nあなたは何もなしえず島を出た...', color.light_gray)


app.run()