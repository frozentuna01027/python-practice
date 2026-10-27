import pygame
import random

pygame.init()
pygame.mixer.init()

screen = pygame.display.set_mode((500, 500))
pygame.display.set_caption("Move Hero")

hero_color = (0, 255, 0)

my_font = pygame.font.SysFont(None, 60)
score_font = pygame.font.SysFont(None, 36)
info_font = pygame.font.SysFont(None, 36)

speed = 20
max_fps = 25

food_sizes = [30, 25, 20, 15, 10]   # ★追加：5段階のサイズ

# ★追加：体の丸の色（6個分。先頭が頭、以降が体）
body_colors = [
    (173,255,47),
    (124,252,0), 
    (50,205,50),    
    (0,255,0), 
    (34,139,34), 
    (0,100,0),    
]

clock = pygame.time.Clock()
sound = pygame.mixer.Sound("voice.mp3")


def reset_game():
    """ゲームの状態を初期化する"""
    global hero_x, hero_y, dx, dy, rect_x, rect_y
    global snake, score, fps, game_over, food_level   # ★food_levelを追加

    # スタート位置をランダムに（20刻みでグリッドに合わせる）
    hero_x = random.randint(6, 19) * 20
    hero_y = random.randint(6, 19) * 20

    # 進む向きもランダムに
    dx, dy = random.choice([(speed, 0), (-speed, 0), (0, speed), (0, -speed)])

    rect_x = 100
    rect_y = 100
    score = 0
    fps = 10
    game_over = False
    food_level = 0   # ★追加：最初は一番大きいサイズ

    # 体は進行方向の後ろ側に並べる
    snake = []
    for i in range(6):
        snake.append((hero_x - i * dx, hero_y - i * dy))


reset_game()

running = True

while running:

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        if event.type == pygame.KEYDOWN:
            if game_over:
                # ゲームオーバー中: Qで終了、Cでリスタート
                if event.key == pygame.K_q:
                    running = False
                if event.key == pygame.K_c:
                    reset_game()
            else:
                # プレイ中: 矢印キーで向きを変える（真逆には曲がれない）
                if event.key == pygame.K_LEFT and dx == 0:
                    dx, dy = -speed, 0
                if event.key == pygame.K_RIGHT and dx == 0:
                    dx, dy = speed, 0
                if event.key == pygame.K_UP and dy == 0:
                    dx, dy = 0, -speed
                if event.key == pygame.K_DOWN and dy == 0:
                    dx, dy = 0, speed

    if not game_over:
        # 自動で前進
        hero_x += dx
        hero_y += dy
        snake.insert(0, (hero_x, hero_y))
        snake.pop()

        # エサとの当たり判定
        food_size = food_sizes[food_level]                     # ★追加
        food_cx = rect_x + food_size / 2                       # ★追加：エサの中心
        food_cy = rect_y + food_size / 2                       # ★追加
        if abs(hero_x - food_cx) < food_size / 2 + 15 and abs(hero_y - food_cy) < food_size / 2 + 15:   # ★変更
            rect_x = random.randint(20, 480)
            rect_y = random.randint(20, 480)
            sound.play()
            score += 1
            fps = min(fps + 10, max_fps)
            food_level = min(food_level + 1, len(food_sizes) - 1)   # ★追加：最後の段階で止まる

        # 画面外ならゲームオーバー
        if hero_x > 500 or hero_x < 0 or hero_y > 500 or hero_y < 0:
            game_over = True

    # ---------- 描画 ----------
    screen.fill((255, 105, 229))

    score_text = score_font.render(f"Score: {score}", True, (255, 255, 255))
    screen.blit(score_text, (10, 10))

    for i, (x, y) in enumerate(snake):
        color = body_colors[i]   # ★追加：i番目の色を取り出す
        if i == 0:
            pygame.draw.circle(screen, color, (x, y), 20)   # ★変更：hero_color → color
            pygame.draw.circle(screen, (255, 255, 255), (x + 5, y - 5), 3)
            pygame.draw.circle(screen, (255, 255, 255), (x + 5, y + 5), 3)
            pygame.draw.circle(screen, (0, 0, 0), (x + 5, y - 5), 1)
            pygame.draw.circle(screen, (0, 0, 0), (x + 5, y + 5), 1)
            pygame.draw.line(screen, (255, 0, 0), (x + 20, y), (x + 30, y - 4), 2)
        else:
            radius = max(4, 20 - i * 2)
            pygame.draw.circle(screen, color, (x, y), radius)   # ★変更：hero_color → color

    food_size = food_sizes[food_level]   # ★変更
    pygame.draw.rect(screen, (217, 234, 211), (rect_x, rect_y, food_size, food_size))   # ★変更

    # ゲームオーバー表示
    if game_over:
        msg = my_font.render("Game Over", True, (0, 0, 0))
        screen.blit(msg, (150, 190))
        info = info_font.render("Q: Quit   C: Restart", True, (0, 0, 0))
        screen.blit(info, (135, 260))

    pygame.display.update()
    clock.tick(fps)

pygame.quit()