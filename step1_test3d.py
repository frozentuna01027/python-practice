# -*- coding: utf-8 -*-
"""
ZOMBIE ARENA  (Ursina 製の簡易FPSサバイバル)
 
操作:  WASD 移動 / SPACE ジャンプ / マウス 視点 / 左クリック 攻撃(クールタイム1秒)
ルール: ゾンビに触れたらゲームオーバー。ただしゾンビは登れないので、
        高さ SAFE_HEIGHT 以上の足場に立てば触られない。
        アイテムで 移動速度UP / 攻撃クールタイム短縮 ができる。
"""
from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController
import math
import random
 
# ==============================================================
#  設定値（ここをいじるとゲームバランスを変えられる）
# ==============================================================
FIELD_HALF = 30                 # フィールドの半分の広さ（60x60）
ZOMBIE_LIMIT = 28.7             # ゾンビが動ける範囲（壁の内側）
ZOMBIE_RADIUS = 0.45
PLAYER_START = Vec3(0, 0, -24)
 
BASE_PLAYER_SPEED = 5           # プレイヤー初期速度
MAX_PLAYER_SPEED = 11           # 速度の上限
SPEED_UP_AMOUNT = 1.5           # 速度アイテム1個で増える量
 
BASE_ATTACK_COOLDOWN = 1.0      # 攻撃クールタイム（秒）
MIN_ATTACK_COOLDOWN = 0.4       # クールタイムの下限
COOLDOWN_DOWN_AMOUNT = 0.15     # クールタイムアイテム1個で減る量
 
SAFE_HEIGHT = 1.8               # これ以上の高さにいるとゾンビに触られない
TOUCH_DISTANCE = 0.9            # この距離まで近づかれたら接触
 
INITIAL_ZOMBIES = 6
MAX_ZOMBIES = 22
ITEM_INTERVAL = 10.0            # アイテム再出現の間隔（秒）
MAX_ITEMS = 7
ITEM_PICKUP_RADIUS = 1.4
 
# Ursina標準フォントは日本語が表示できません。日本語を使いたい場合は
# フォントファイルのパスを指定してください（例: 'C:/Windows/Fonts/meiryo.ttc'）
JP_FONT = None
if JP_FONT:
    Text.default_font = JP_FONT
 
app = Ursina()
window.title = 'ZOMBIE ARENA'
 
# ==============================================================
#  ゲーム状態
# ==============================================================
game_state = 'title'            # 'title' / 'playing' / 'gameover'
kills = 0
best_kills = 0
game_time = 0.0
attack_cd = BASE_ATTACK_COOLDOWN
attack_timer = 0.0
spawn_timer = 0.0
item_timer = 0.0
 
enemies = []
items = []
obstacles = []                  # (x, z, 半幅x, 半幅z)  ゾンビが通れない場所
item_points = []               # アイテムの出現地点
 
 
# ==============================================================
#  ユーティリティ
# ==============================================================
def hsv(h, s, v, a=1):
    return color.hsv(h, s, v, a)
 
 
def set_text(txt, s):
    """同じ文字列なら再生成しない（毎フレームのText更新は重いので）"""
    if getattr(txt, '_last', None) != s:
        txt.text = s
        txt._last = s
 
 
def is_blocked(x, z, r=ZOMBIE_RADIUS):
    for ox, oz, hw, hd in obstacles:
        if abs(x - ox) < hw + r and abs(z - oz) < hd + r:
            return True
    return False
 
 
def ray_aabb(origin, direction, bmin, bmax):
    """レイとAABB(直方体)の交差判定。当たれば距離、外れなら None"""
    tmin, tmax = 0.0, 1e9
    for i in range(3):
        o, d, lo, hi = origin[i], direction[i], bmin[i], bmax[i]
        if abs(d) < 1e-8:
            if o < lo or o > hi:
                return None
        else:
            t1, t2 = (lo - o) / d, (hi - o) / d
            if t1 > t2:
                t1, t2 = t2, t1
            tmin, tmax = max(tmin, t1), min(tmax, t2)
            if tmin > tmax:
                return None
    return tmin
 
 
# ==============================================================
#  フィールド作成
# ==============================================================
def add_block(x, z, w, d, h, col):
    """地面から立ち上がる柱状ブロック（足場・壁・箱）。ゾンビは通れない"""
    e = Entity(model='cube', texture='white_cube', color=col,
               scale=(w, h, d), position=(x, h / 2, z), collider='box')
    obstacles.append((x, z, w / 2, d / 2))
    return e
 
 
def add_stairs(x0, z0, dx, dz, n, size, step_h, col):
    for i in range(n):
        add_block(x0 + i * dx, z0 + i * dz, size, size, step_h * (i + 1), col)
 
 
def add_tree(x, z):
    Entity(model='cube', texture='white_cube', color=hsv(25, .6, .35),
           scale=(.7, 3, .7), position=(x, 1.5, z), collider='box')
    Entity(model='sphere', color=hsv(115, .6, .4), scale=3.4, position=(x, 4.0, z))
    Entity(model='sphere', color=hsv(105, .6, .5), scale=2.4, position=(x, 5.4, z))
    obstacles.append((x, z, .4, .4))
 
 
def add_item_point(x, surface_y, z):
    item_points.append({'pos': Vec3(x, surface_y + 0.9, z), 'used': False})
 
 
def build_world():
    # 地面と空
    Entity(model='plane', scale=FIELD_HALF * 2, texture='grass',
           texture_scale=(12, 12), collider='box')
    Sky()
 
    # 外周の壁（ジャンプでは越えられない高さ）
    wall_col = hsv(210, .1, .45)
    wall_h = 10
    span = FIELD_HALF * 2 + 4
    for x, z, w, d in [(0, FIELD_HALF + 1, span, 2), (0, -FIELD_HALF - 1, span, 2),
                       (FIELD_HALF + 1, 0, 2, span), (-FIELD_HALF - 1, 0, 2, span)]:
        Entity(model='cube', texture='white_cube', color=wall_col,
               scale=(w, wall_h, d), position=(x, wall_h / 2, z), collider='box')
 
    stone = hsv(30, .25, .8)
    sand = hsv(40, .45, .85)
    crate = hsv(28, .6, .55)
    cover = hsv(200, .15, .6)
 
    # --- 西の砦: 階段(1.2 → 2.4 → 3.6) + 広い高台
    add_stairs(-26, -12, 3.2, 0, 3, 3, 1.2, stone)
    add_block(-15.6, -12, 6, 6, 3.6, stone)
    add_item_point(-15.6, 3.6, -12)
 
    # --- 東の砦: 隙間のある足場をジャンプで渡っていくアスレチック
    for x, z, h in [(10, -14, 1.2), (13.5, -11, 2.0), (17, -8, 2.8), (20.5, -5, 3.6)]:
        add_block(x, z, 2.5, 2.5, h, sand)
    add_block(23.5, -0.5, 5, 5, 3.6, sand)
    add_item_point(23.5, 3.6, -0.5)
 
    # --- 中央の見張り台: 階段 + 高台 + さらに高い展望ブロック
    add_stairs(-9, 3, 2.9, 0, 3, 2.8, 1.2, stone)
    add_block(1.2, 3, 5.6, 5.6, 3.6, stone)
    add_block(2.8, 3, 2.4, 2.4, 4.8, stone)
    add_item_point(2.8, 4.8, 3)
 
    # --- 北西の塔
    add_stairs(-22, 12.5, 0, 3.2, 3, 3, 1.2, sand)
    add_block(-22, 23.3, 6, 6, 3.6, sand)
    add_item_point(-22, 3.6, 23.3)
 
    # --- 遮蔽物の壁（ゾンビも弾も遮る）
    add_block(0, 12, 10, 1.2, 3.0, cover)
    add_block(-14, 18, 1.2, 8, 3.0, cover)
    add_block(14, 14, 1.2, 8, 3.0, cover)
 
    # --- 木箱（低いので足場にはなるが、安全ではない高さ）
    for x, z in [(-6, -14), (6, -18), (4, -8), (-10, 0), (12, 4), (-4, 24), (22, 22)]:
        add_block(x, z, 2, 2, 1.2, crate)
 
    # --- 木（飾り兼、障害物）
    placed, tries = 0, 0
    while placed < 16 and tries < 400:
        tries += 1
        x, z = random.uniform(-27, 27), random.uniform(-27, 27)
        if is_blocked(x, z, 3.0):
            continue
        if math.hypot(x - PLAYER_START.x, z - PLAYER_START.z) < 8:
            continue
        add_tree(x, z)
        placed += 1
 
    # --- 地上のアイテム出現地点
    placed, tries = 0, 0
    while placed < 10 and tries < 400:
        tries += 1
        x, z = random.uniform(-26, 26), random.uniform(-26, 26)
        if is_blocked(x, z, 1.8):
            continue
        add_item_point(x, 0, z)
        placed += 1
 
 
# ==============================================================
#  敵（ゾンビ）: 複数のパーツを組み合わせて人型にする
# ==============================================================
class Zombie(Entity):
    def __init__(self, position, base_speed):
        super().__init__(position=position)
        self.base_speed = base_speed
        self.side = random.choice((-1, 1))      # 障害物を避ける時の回り込み方向
        self.walk_t = random.uniform(0, 6)
        self.dead = False
 
        skin = hsv(random.randint(80, 120), .35, .6)
        shirt = hsv(random.choice((210, 0, 280, 30)), .55, .5)
        pants = hsv(230, .5, .3)
 
        def part(parent, col, scale, **kw):
            return Entity(parent=parent, model='cube', texture='white_cube',
                          color=col, scale=scale, **kw)
 
        # 胴体・頭
        part(self, shirt, (.8, .9, .4), y=1.15)
        self.head = Entity(parent=self, y=1.9)
        part(self.head, skin, .55)
        part(self.head, color.red, (.1, .09, .05), position=(-.13, .06, .28))
        part(self.head, color.red, (.1, .09, .05), position=(.13, .06, .28))
 
        # 腕（前に突き出す）
        self.arm_l = Entity(parent=self, position=(-.52, 1.45, 0))
        self.arm_r = Entity(parent=self, position=(.52, 1.45, 0))
        for arm in (self.arm_l, self.arm_r):
            part(arm, skin, (.22, .22, .75), z=.375)
 
        # 脚（歩きアニメーション用に付け根を回転軸にする）
        self.leg_l = Entity(parent=self, position=(-.2, .7, 0))
        self.leg_r = Entity(parent=self, position=(.2, .7, 0))
        for leg in (self.leg_l, self.leg_r):
            part(leg, pants, (.3, .7, .3), y=-.35)
 
    def chase(self, tx, tz, step):
        dx, dz = tx - self.x, tz - self.z
        if math.hypot(dx, dz) < 0.05:
            return
        base = math.atan2(dx, dz)
        # 障害物があれば少しずつ角度を変えて回り込む
        for off in (0, 40, -40, 80, -80, 125, -125):
            a = base + math.radians(off * self.side)
            nx = max(-ZOMBIE_LIMIT, min(ZOMBIE_LIMIT, self.x + math.sin(a) * step))
            nz = max(-ZOMBIE_LIMIT, min(ZOMBIE_LIMIT, self.z + math.cos(a) * step))
            if not is_blocked(nx, nz):
                self.x, self.z = nx, nz
                self.rotation_y = math.degrees(a)
                return
 
    def nudge(self, dx, dz):
        """ゾンビ同士が重ならないための押し出し"""
        nx, nz = self.x + dx, self.z + dz
        if not is_blocked(nx, nz):
            self.x, self.z = nx, nz
 
    def animate_walk(self, dt):
        self.walk_t += dt * self.base_speed * 2.2
        s = math.sin(self.walk_t) * 35
        self.leg_l.rotation_x = s
        self.leg_r.rotation_x = -s
        self.arm_l.rotation_x = math.sin(self.walk_t * .5) * 6
        self.arm_r.rotation_x = -math.sin(self.walk_t * .5) * 6
 
 
def spawn_zombie():
    if len(enemies) >= MAX_ZOMBIES:
        return
    for _ in range(40):
        x, z = random.uniform(-27, 27), random.uniform(-27, 27)
        if is_blocked(x, z, 1.0):
            continue
        if math.hypot(x - player.x, z - player.z) < 16:   # プレイヤーの近くには出さない
            continue
        enemies.append(Zombie(Vec3(x, 0, z), random.uniform(2.3, 3.2)))
        return
 
 
def separate_zombies():
    for i, a in enumerate(enemies):
        for b in enemies[i + 1:]:
            dx, dz = a.x - b.x, a.z - b.z
            d2 = dx * dx + dz * dz
            if d2 < 0.64:
                if d2 < 1e-6:
                    dx, dz, d2 = random.uniform(-1, 1), random.uniform(-1, 1), 1.0
                d = math.sqrt(d2)
                push = (0.8 - d) * 0.5
                a.nudge(dx / d * push, dz / d * push)
                b.nudge(-dx / d * push, -dz / d * push)
 
 
# ==============================================================
#  アイテム
# ==============================================================
class Item(Entity):
    def __init__(self, kind, point):
        super().__init__(position=point['pos'])
        self.kind = kind
        self.point = point
        self.t = random.uniform(0, 6)
        hue = 185 if kind == 'speed' else 28
        self.gem = Entity(parent=self)
        if kind == 'speed':        # 水色のひし形 = 移動速度UP
            Entity(parent=self.gem, model='cube', texture='white_cube',
                   color=hsv(hue, .8, 1), scale=.55, rotation=(45, 45, 0))
        else:                      # オレンジの球 = クールタイム短縮
            Entity(parent=self.gem, model='sphere', color=hsv(hue, .9, 1), scale=.65)
        # 遠くからでも見える光の柱
        Entity(parent=self, model='cube', color=hsv(hue, .5, 1, .35),
               scale=(.12, 7, .12), y=3.5)
 
    def update(self):
        self.t += time.dt
        self.gem.rotation_y += 120 * time.dt
        self.gem.y = math.sin(self.t * 3) * .12
 
 
def spawn_item(point=None, kind=None):
    free = [p for p in item_points if not p['used']]
    if not free:
        return
    point = point or random.choice(free)
    point['used'] = True
    items.append(Item(kind or random.choice(('speed', 'cooldown')), point))
 
 
def popup(msg, col):
    t = Text(text=msg, origin=(0, 0), position=(0, .32), scale=2, color=col)
    destroy(t, delay=1.4)
 
 
def pick_up(item):
    global attack_cd
    if item.kind == 'speed':
        player.speed = min(MAX_PLAYER_SPEED, player.speed + SPEED_UP_AMOUNT)
        popup(f'SPEED UP!  ({player.speed:.1f})', color.cyan)
    else:
        attack_cd = max(MIN_ATTACK_COOLDOWN, attack_cd - COOLDOWN_DOWN_AMOUNT)
        popup(f'COOLDOWN DOWN!  ({attack_cd:.2f}s)', color.orange)
    item.point['used'] = False
    items.remove(item)
    destroy(item)
 
 
# ==============================================================
#  プレイヤー
# ==============================================================
class Player(FirstPersonController):
    """プレイ中以外は操作を受け付けない"""
    def update(self):
        if game_state == 'playing':
            super().update()
 
    def input(self, key):
        if game_state == 'playing':
            super().input(key)
 
 
build_world()
player = Player(position=PLAYER_START)
player.speed = BASE_PLAYER_SPEED
mouse.locked = False
 
 
def spark(pos):
    s = Entity(model='sphere', color=color.yellow, scale=.3, position=pos)
    s.animate_scale(.01, duration=.2)
    destroy(s, delay=.25)
 
 
def kill_zombie(zb):
    global kills
    zb.dead = True
    enemies.remove(zb)
    zb.animate_scale(.01, duration=.25)
    destroy(zb, delay=.3)
    kills += 1
 
 
def attack():
    """レイ判定の攻撃。壁や柱に遮られると当たらない。外してもクールタイムは発生する"""
    global attack_timer
    if attack_timer > 0:
        return
    attack_timer = attack_cd
 
    origin = camera.world_position
    direction = camera.forward
    wall = raycast(origin, direction, distance=80, traverse_target=scene, ignore=[player])
    best, best_t = None, (wall.distance if wall.hit else 80)
 
    o = (origin.x, origin.y, origin.z)
    d = (direction.x, direction.y, direction.z)
    for zb in enemies:
        bmin = (zb.x - .55, 0, zb.z - .5)
        bmax = (zb.x + .55, 2.2, zb.z + .5)
        t = ray_aabb(o, d, bmin, bmax)
        if t is not None and t < best_t:
            best, best_t = zb, t
 
    if best:
        spark(Vec3(o[0] + d[0] * best_t, o[1] + d[1] * best_t, o[2] + d[2] * best_t))
        kill_zombie(best)
    elif wall.hit:
        spark(wall.world_point)
 
 
# ==============================================================
#  UI（HUD / タイトル / ゲームオーバー）
# ==============================================================
def ui_text(parent, text, y, scale=1.5, col=color.white, x=0, origin=(0, 0)):
    return Text(parent=parent, text=text, position=(x, y), origin=origin,
                scale=scale, color=col)
 
 
# --- HUD
hud = Entity(parent=camera.ui)
kills_text = Text(parent=hud, text='Kills: 0', position=(-.85, .47), scale=1.8, color=color.black)
time_text = Text(parent=hud, text='Time: 0s', position=(-.85, .41), scale=1.4, color=color.black)
status_text = ui_text(hud, '', .47, scale=1.3, col=color.black, x=.85, origin=(.5, .5))
safe_text = ui_text(hud, "SAFE ZONE - zombies can't reach you", .40, scale=1.6, col=color.lime)
cd_text = ui_text(hud, 'ATTACK', -.385, scale=1.1, col=color.black)
cd_bg = Entity(parent=hud, model='quad', color=hsv(0, 0, 0, .5), scale=(.4, .025), position=(0, -.42))
cd_fill = Entity(parent=hud, model='quad', color=color.lime, origin=(-.5, 0),
                 position=(-.2, -.42, -.01), scale=(.4, .025))
cd_ready_prev = True
 
# --- タイトル画面
title_ui = Entity(parent=camera.ui)
Entity(parent=title_ui, model='quad', color=hsv(220, .6, .08, .75), scale=(3, 1.5), z=1)
ui_text(title_ui, 'ZOMBIE ARENA', .27, scale=4.5, col=color.lime)
ui_text(title_ui, 'Survive. Shoot. Climb.', .17, scale=1.6)
ui_text(title_ui, 'Press ENTER to start', .05, scale=2.2, col=color.yellow)
ui_text(title_ui, 'WASD: Move    SPACE: Jump    MOUSE: Look', -.07, scale=1.2)
ui_text(title_ui, 'LEFT CLICK: Attack (1 sec cooldown - make every shot count!)', -.11, scale=1.2)
ui_text(title_ui, 'Touch a zombie = GAME OVER', -.17, scale=1.2, col=color.red)
ui_text(title_ui, "Zombies can't climb! Stand on high ground (2.4m+) to be safe.", -.21, scale=1.2)
ui_text(title_ui, 'Cyan item: Speed Up      Orange item: Cooldown Down', -.25, scale=1.2, col=color.cyan)
title_best = ui_text(title_ui, '', -.34, scale=1.4, col=color.orange)
 
# --- ゲームオーバー画面
gameover_ui = Entity(parent=camera.ui)
Entity(parent=gameover_ui, model='quad', color=hsv(0, .8, .1, .75), scale=(3, 1.5), z=1)
ui_text(gameover_ui, 'GAME OVER', .22, scale=5, col=color.red)
go_stats = ui_text(gameover_ui, '', .08, scale=2.2)
go_best = ui_text(gameover_ui, '', 0, scale=1.6, col=color.orange)
ui_text(gameover_ui, 'Press R to retry      Press T for title', -.12, scale=1.8, col=color.yellow)
 
 
def set_cursor(flag):
    if hasattr(player, 'cursor'):
        player.cursor.enabled = flag
 
 
# ==============================================================
#  ゲーム進行
# ==============================================================
def clear_entities():
    for zb in enemies:
        destroy(zb)
    enemies.clear()
    for it in items:
        it.point['used'] = False
        destroy(it)
    items.clear()
 
 
def reset_player():
    player.position = PLAYER_START
    player.rotation_y = 0
    player.camera_pivot.rotation_x = 0
    player.speed = BASE_PLAYER_SPEED
 
 
def show_title():
    global game_state
    clear_entities()
    reset_player()
    game_state = 'title'
    set_text(title_best, f'Best: {best_kills} kills')
    title_ui.enabled = True
    gameover_ui.enabled = False
    hud.enabled = False
    set_cursor(False)
    mouse.locked = False
 
 
def start_game():
    global game_state, kills, game_time, attack_cd, attack_timer, spawn_timer, item_timer
    clear_entities()
    reset_player()
    kills = 0
    game_time = 0.0
    attack_cd = BASE_ATTACK_COOLDOWN
    attack_timer = 0.0
    spawn_timer = 3.0
    item_timer = ITEM_INTERVAL
 
    for _ in range(INITIAL_ZOMBIES):
        spawn_zombie()
 
    # 最初のアイテム: 高台2か所 + 地上3か所
    platforms = [p for p in item_points if p['pos'].y > 1]
    ground = [p for p in item_points if p['pos'].y <= 1]
    for p in random.sample(platforms, min(2, len(platforms))):
        spawn_item(p)
    for p in random.sample(ground, min(3, len(ground))):
        spawn_item(p)
 
    title_ui.enabled = False
    gameover_ui.enabled = False
    hud.enabled = True
    set_cursor(True)
    mouse.locked = True
    game_state = 'playing'
 
 
def game_over():
    global game_state, best_kills
    game_state = 'gameover'
    best_kills = max(best_kills, kills)
    go_stats.text = f'Kills: {kills}      Time: {int(game_time)}s'
    go_best.text = f'Best: {best_kills} kills'
    gameover_ui.enabled = True
    hud.enabled = False
    set_cursor(False)
    mouse.locked = False
 
 
# ==============================================================
#  Ursina のコールバック
# ==============================================================
def input(key):
    if game_state == 'title':
        if key in ('enter', 'left mouse down'):
            start_game()
    elif game_state == 'gameover':
        if key == 'r':
            start_game()
        elif key == 't':
            show_title()
    elif game_state == 'playing':
        if key == 'left mouse down':
            attack()
 
 
def update():
    global game_time, attack_timer, spawn_timer, item_timer, cd_ready_prev
    if game_state != 'playing':
        return
 
    dt = time.dt
    game_time += dt
    attack_timer = max(0.0, attack_timer - dt)
 
    # --- ゾンビの出現（時間とともに間隔が短くなる）
    spawn_timer -= dt
    if spawn_timer <= 0:
        spawn_zombie()
        spawn_timer = max(1.2, 3.5 - game_time * 0.03)
 
    # --- アイテムの再出現
    item_timer -= dt
    if item_timer <= 0:
        item_timer = ITEM_INTERVAL
        if len(items) < MAX_ITEMS:
            spawn_item()
 
    # --- アイテム取得
    px, py, pz = player.x, player.y + 1.0, player.z
    for it in items[:]:
        if (it.x - px) ** 2 + (it.y - py) ** 2 + (it.z - pz) ** 2 < ITEM_PICKUP_RADIUS ** 2:
            pick_up(it)
 
    # --- ゾンビの移動
    speed_bonus = min(game_time * 0.02, 1.8)
    for zb in enemies:
        zb.chase(px, pz, (zb.base_speed + speed_bonus) * dt)
        zb.animate_walk(dt)
    separate_zombies()
 
    # --- 接触判定: 足元が低い位置にいる時だけ触られる（高所なら安全）
    if player.y < SAFE_HEIGHT:
        for zb in enemies:
            if math.hypot(zb.x - px, zb.z - pz) < TOUCH_DISTANCE:
                game_over()
                return
 
    # --- HUD更新
    set_text(kills_text, f'Kills: {kills}')
    set_text(time_text, f'Time: {int(game_time)}s')
    set_text(status_text, f'Speed {player.speed:.1f}   Cooldown {attack_cd:.2f}s')
 
    safe = player.y >= SAFE_HEIGHT
    if safe_text.enabled != safe:
        safe_text.enabled = safe
 
    ratio = 1.0 - attack_timer / attack_cd
    cd_fill.scale_x = max(0.001, 0.4 * ratio)
    ready = attack_timer <= 0
    if ready != cd_ready_prev:
        cd_ready_prev = ready
        cd_fill.color = color.lime if ready else color.orange
        set_text(cd_text, 'ATTACK READY' if ready else 'RELOADING')
 
 
show_title()
app.run()