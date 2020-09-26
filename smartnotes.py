#!/usr/bin/env python3

import pygame
import pygame.freetype
import sys

class Note(object):

    def __init__(self, center, radius):
        self.center = center
        self.rotation = pygame.math.Vector2(radius, radius)
        self.box = pygame.Surface((30, 30))
        self.box.fill((123, 214, 55))

    def render(self, screen, ms_diff):
        self.rotation = self.rotation.rotate(ms_diff/5.0)
        screen.blit(self.box, self.center+self.rotation)
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

    def render(self, screen, ms_diff):
        if not self.visible and self.animation.is_finished():
            return
        bar = pygame.Surface((screen.get_width(), self.HEIGHT))
        bar.fill((100, 100, 100))
        text, text_rect = self.font.render(
            f"ms_diff = {ms_diff} | fps = {int(round(self.clock.get_fps()))}"
        )
        offset = 0
        if not self.animation.is_finished():
            percent = self.animation.advance(ms_diff)
            if self.visible:
                alpha = int(255 * percent)
                offset = bar.get_height()-int(bar.get_height()*percent)
            else:
                alpha = 255 - int(255 * percent)
                offset = int(bar.get_height()*percent)
            bar.set_alpha(alpha)
        bar.blit(
            text,
            (
                bar.get_width()-text_rect.width-10,
                bar.get_height()/2-text_rect.height/2
            )
        )
        screen.blit(bar, (0, screen.get_height()-bar.get_height()+offset))
class Animation(object):

    def __init__(self):
        self.duration_ms = 0
        self.progress = 0
        self.is_active = False

    def is_finished(self):
        return self.progress == self.duration_ms and not self.is_active

    def start(self, duration_ms):
        self.duration_ms = duration_ms
        self.progress = 0
        self.is_active = True

    def advance(self, ms):
        percent = float(self.progress) / float(self.duration_ms)
        if self.progress == self.duration_ms:
            self.is_active = False
        else:
            self.progress = min(self.duration_ms, self.progress+ms)
        return percent

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
        ms_diff = clock.get_time()
        n1.render(screen, ms_diff)
        n2.render(screen, ms_diff)
        debug_bar.render(screen, ms_diff)
        pygame.display.flip()
        clock.tick(60)

if __name__ == "__main__":
    main()
