import pygame
import random
 
pygame.init()
WIDTH, HEIGHT = 500, 500
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Move Hero")
 
my_font = pygame.font.SysFont(None, 50)
small_font = pygame.font.SysFont(None, 28)
clock = pygame.time.Clock()
 
def reset_game():
    global hero_x, hero_y, rect_x, rect_y, speed, direction_x, direction_y, snake, score, game_over
    hero_x = 250
    hero_y = 250
    rect_x = 100
    rect_y = 100
    speed = 20
    score = 0
    direction_x = speed
    direction_y = 0
    game_over = False
   
    snake = []
    for i in range(6):
        snake.append((hero_x - i * 30, hero_y))
 
reset_game()
 
running = True
 
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
 
        if event.type == pygame.KEYDOWN:
            if game_over:
                if event.key == pygame.K_c:    # Cキー: 復活
                    reset_game()
                elif event.key == pygame.K_e:  # Eキー: 退出
                    running = False
            else:
                if event.key == pygame.K_UP:
                    direction_x = 0
                    direction_y = -speed
                   
                elif event.key == pygame.K_DOWN:
                    direction_x = 0
                    direction_y = speed
                       
                elif event.key == pygame.K_LEFT:
                    direction_x = -speed
                    direction_y = 0
                   
                elif event.key == pygame.K_RIGHT:
                    direction_x = speed
                    direction_y = 0
 
                elif event.key == pygame.K_LSHIFT:
                    speed = 40
                    if direction_x > 0:
                        direction_x = speed
                    elif direction_x < 0:
                        direction_x = -speed
                    elif direction_y > 0:
                        direction_y = speed
                    elif direction_y < 0:
                        direction_y = -speed
           
        if event.type == pygame.KEYUP and not game_over:
            if event.key == pygame.K_LSHIFT:
                speed = 20
                if direction_x > 0:
                    direction_x = speed
                elif direction_x < 0:
                    direction_x = -speed
                elif direction_y > 0:
                    direction_y = speed
                elif direction_y < 0:
                    direction_y = -speed
 
    if not game_over:
        hero_x += direction_x
        hero_y += direction_y
        snake.insert(0, (hero_x, hero_y))
        snake.pop()
 
        if abs(hero_x - rect_x) < 30 and abs(hero_y - rect_y) < 30:
            rect_x = random.randint(20, 480)
            rect_y = random.randint(20, 480)
            speed += 2
            score += 1
 
        if hero_x > 500 or hero_x < 0 or hero_y > 500 or hero_y < 0:
            game_over = True
 
    screen.fill((209, 27, 0))
 
    for i, (x, y) in enumerate(snake):
        if i == 0:
            pygame.draw.circle(screen, (0, 200, 0), (x, y), 20)
            pygame.draw.circle(screen, (255, 200, 255), (x + 6, y - 5), 4)
            pygame.draw.circle(screen, (255, 255, 255), (x + 6, y - 6), 4)
 
            pygame.draw.circle(screen, (0, 0, 0), (x + 6, y - 5), 2)
            pygame.draw.circle(screen, (0, 0, 0), (x + 6, y - 5), 2)
 
            pygame.draw.line(screen, (255, 0, 0), (x + 20, y), (x + 30, y - 4), 2)
        else:
            radius = max(4, 20 - i * 2)
            green = max(80, 200 - i * 20)
            pygame.draw.circle(screen, (0, green, 0), (x, y), radius)
   
    pygame.draw.rect(screen, (0, 234, 19), (rect_x, rect_y, 30, 30), 30)
 
    score_text = my_font.render("Score: " + str(score), True, (255, 255, 255))
    screen.blit(score_text, (10, 10))
 
    if game_over:
        overlay = pygame.Surface((WIDTH, HEIGHT))
        overlay.set_alpha(180)
        overlay.fill((0, 0, 0))
        screen.blit(overlay, (0, 0))
 
        go_text = my_font.render("GAME OVER", True, (255, 50, 50))
        msg_text = small_font.render("Press 'C' to Restart / 'E' to Exit", True, (255, 255, 255))
       
        screen.blit(go_text, (WIDTH // 2 - go_text.get_width() // 2, 180))
        screen.blit(msg_text, (WIDTH // 2 - msg_text.get_width() // 2, 250))
 
    pygame.display.update()
    clock.tick(10)
 
pygame.quit()