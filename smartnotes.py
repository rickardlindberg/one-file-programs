#!/usr/bin/env python3

import pygame
import pygame.freetype
import sys

class Note(object):

    def __init__(self, center, radius):
        self.animation = Animation()
        self.center = center
        self.radius = pygame.math.Vector2(radius, radius)
        self.image = pygame.Surface((30, 30))
        self.image.fill((123, 214, 55))

    def tick(self, screen, elapsed_ms):
        if not self.animation.active():
            self.animation.start(2000)
        self.rect = self.image.get_rect().move(
            self.radius.rotate(
                self.animation.advance(elapsed_ms)*360
            ) + self.center
        )
        screen.blit(self.image, self.rect)

class DebugBar(object):

    HEIGHT = 50

    def __init__(self, clock):
        self.clock = clock
        self.visible = True
        self.animation = Animation()
        self.font = pygame.freetype.SysFont(
            pygame.freetype.get_default_font(),
            18
        )

    def toggle(self):
        self.visible = not self.visible
        self.animation.start(200)

    def tick(self, screen, elapsed_ms):
        if not self.visible and not self.animation.active():
            return
        self.image = pygame.Surface((screen.get_width(), self.HEIGHT))
        self.image.fill((100, 100, 100))
        text, text_rect = self.font.render(
            f"elapsed_ms = {elapsed_ms} | fps = {int(round(self.clock.get_fps()))}"
        )
        percent = self.animation.advance(elapsed_ms)
        if self.visible:
            alpha = int(255 * percent)
            offset = self.image.get_height()-int(self.image.get_height()*percent)
        else:
            alpha = 255 - int(255 * percent)
            offset = int(self.image.get_height()*percent)
        self.image.set_alpha(alpha)
        self.image.blit(
            text,
            (
                self.image.get_width()-text_rect.width-10,
                self.image.get_height()/2-text_rect.height/2
            )
        )
        self.rect = self.image.get_rect().move((0, screen.get_height()-self.image.get_height()+offset))
        screen.blit(self.image, self.rect)

class Animation(object):

    def __init__(self):
        self.duration_ms = 1
        self.progress = 1
        self.last_consumed = True

    def start(self, duration_ms):
        self.duration_ms = duration_ms
        self.progress = 0
        self.last_consumed = False

    def advance(self, elapsed_ms):
        percent = float(self.progress) / float(self.duration_ms)
        if self.progress == self.duration_ms:
            self.last_consumed = True
        else:
            self.progress = min(self.duration_ms, self.progress+elapsed_ms)
        return percent

    def active(self):
        return self.progress < self.duration_ms or not self.last_consumed

def main():
    pygame.init()
    pygame.display.set_caption("Smart Notes")
    screen = pygame.display.set_mode((1280, 720))
    clock = pygame.time.Clock()
    n1 = Note(pygame.math.Vector2(100, 100), 40)
    n2 = Note(pygame.math.Vector2(200, 100), 30)
    debug_bar = DebugBar(clock)
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                debug_bar.toggle()
        screen.fill((100, 200, 50))
        elapsed_ms = clock.get_time()
        n1.tick(screen, elapsed_ms)
        n2.tick(screen, elapsed_ms)
        pygame.draw.aaline(
            screen,
            (0, 0, 0),
            n1.rect.midright,
            n2.rect.midleft,
        )
        debug_bar.tick(screen, elapsed_ms)
        pygame.display.flip()
        clock.tick(60)

if __name__ == "__main__":
    main()
