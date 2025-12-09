import pygame
from game_lib import Bird, PipeManager, check_collision, init_display

def main():
    screen = init_display()
    pygame.display.set_caption("Assembly Engine Flappy Bird")
    clock = pygame.time.Clock()
    
    bird = Bird(50, 300)
    pipe_manager = PipeManager(400)
    
    running = True
    game_over = False
    
    while running:
        clock.tick(30)
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE and not game_over:
                    bird.jump()
                if event.key == pygame.K_r and game_over:
                    # Reset
                    bird = Bird(50, 300)
                    pipe_manager = PipeManager(400)
                    game_over = False

        screen.fill((135, 206, 235))  # Sky blue
        
        if not game_over:
            bird.move()
            pipe_manager.update()
            
            if check_collision(bird, pipe_manager):
                game_over = True
        
        bird.draw(screen)
        pipe_manager.draw(screen)
        
        if game_over:
            # Draw Game Over text
            font = pygame.font.SysFont('Arial', 30)
            text = font.render("GAME OVER - Press R", True, (255, 0, 0))
            screen.blit(text, (50, 250))

        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    main()
