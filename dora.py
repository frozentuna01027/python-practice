import pygame
import random

# ゲームの設定
WIDTH, HEIGHT = 800, 600
FPS = 60
TILE_SIZE = 50

# 色の定義
WHITE = (255, 255, 255)
GREEN = (0, 255, 0)
RED = (255, 0, 0)
BLUE = (0, 0, 255)

# NPCのクラス
class NPC:
    def __init__(self):
        self.position = (random.randint(1, 10), random.randint(1, 10))
        self.has_quest = True

    def talk(self):
        if self.has_quest:
            print("クエストを受けました！")

# キャラクターのクラス
class Player:
    def __init__(self):
        self.position = [1, 1]
        self.level = 1
        self.experience = 0

    def move(self, direction):
        if direction == "UP":
            self.position[1] -= 1
        elif direction == "DOWN":
            self.position[1] += 1
        elif direction == "LEFT":
            self.position[0] -= 1
        elif direction == "RIGHT":
            self.position[0] += 1

# 敵キャラクターのクラス
class Enemy:
    def __init__(self):
        self.position = [random.randint(1, 10), random.randint(1, 10)]
        self.health = 10

    def attack(self, player):
        if self.position == player.position:
            player.experience += 5
            print("敵と戦った！経験値を獲得！")

# 初期化
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("RPG Game")
clock = pygame.time.Clock()

# プレイヤー、敵、NPCのインスタンスを作成
player = Player()
enemy = Enemy()
npcs = [NPC() for _ in range(3)]

# メインループ
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    keys = pygame.key.get_pressed()
    if keys[pygame.K_UP]:
        player.move("UP")
    if keys[pygame.K_DOWN]:
        player.move("DOWN")
    if keys[pygame.K_LEFT]:
        player.move("LEFT")
    if keys[pygame.K_RIGHT]:
        player.move("RIGHT")

    # 敵と戦う
    enemy.attack(player)

    # 描画
    screen.fill(WHITE)

    # プレイヤーの描画
    pygame.draw.rect(screen, BLUE, (player.position[0] * TILE_SIZE, player.position[1] * TILE_SIZE, TILE_SIZE, TILE_SIZE))
    
    # 敵の描画
    pygame.draw.rect(screen, RED, (enemy.position[0] * TILE_SIZE, enemy.position[1] * TILE_SIZE, TILE_SIZE, TILE_SIZE))

    # NPCの描画
    for npc in npcs:
        pygame.draw.rect(screen, GREEN, (npc.position[0] * TILE_SIZE, npc.position[1] * TILE_SIZE, TILE_SIZE, TILE_SIZE))
   
    pygame.display.flip()
    clock.tick(FPS)

pygame.quit()
