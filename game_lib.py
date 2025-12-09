import pygame
import random

# Initialize Pygame for component usage
pygame.init()

class Bird:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.velocity = 0
        self.gravity = 0.5
        self.jump_strength = -10
        self.size = 20
        self.rect = pygame.Rect(x, y, self.size, self.size)

    def jump(self):
        self.velocity = self.jump_strength

    def move(self):
        self.velocity += self.gravity
        self.y += self.velocity
        self.rect.y = int(self.y)

    def draw(self, screen):
        pygame.draw.rect(screen, (255, 255, 0), self.rect)

class PipeManager:
    def __init__(self, width, gap_size=150):
        self.pipes = []
        self.width = width
        self.gap_size = gap_size
        self.timer = 0
        self.spawn_rate = 100  # Frames

    def update(self):
        self.timer += 1
        if self.timer >= self.spawn_rate:
            self.spawn_pipe()
            self.timer = 0
        
        # Move pipes
        for pipe in self.pipes:
            pipe['x'] -= 3
        
        # Remove off-screen pipes
        self.pipes = [p for p in self.pipes if p['x'] > -50]

    def spawn_pipe(self):
        height = random.randint(50, 400)
        self.pipes.append({
            'x': self.width,
            'top_height': height,
            'bottom_y': height + self.gap_size,
            'rect_top': pygame.Rect(self.width, 0, 50, height),
            'rect_bottom': pygame.Rect(self.width, height + self.gap_size, 50, 600 - (height + self.gap_size))
        })

    def draw(self, screen):
        for pipe in self.pipes:
            # Update rects for collision (simple sync)
            pipe['rect_top'].x = pipe['x']
            pipe['rect_bottom'].x = pipe['x']
            
            pygame.draw.rect(screen, (0, 255, 0), pipe['rect_top'])
            pygame.draw.rect(screen, (0, 255, 0), pipe['rect_bottom'])

def check_collision(bird, pipe_manager):
    if bird.y > 600 or bird.y < 0:
        return True
    
    for pipe in pipe_manager.pipes:
        if bird.rect.colliderect(pipe['rect_top']) or bird.rect.colliderect(pipe['rect_bottom']):
            return True
    return False

def init_display():
    return pygame.display.set_mode((400, 600))
