#!/usr/bin/env python3

import pygame
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

def main():
    pygame.init()
    pygame.display.set_caption("Smart Notes")
    screen = pygame.display.set_mode((1280, 720))
    clock = pygame.time.Clock()
    n1 = Note(pygame.math.Vector2(100, 100), 40)
    n2 = Note(pygame.math.Vector2(200, 100), 30)
    while True:
        print(f"frame = {clock.get_time()} (fps = {clock.get_fps()})")
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return
        screen.fill((100, 200, 50))
        n1.render(screen, clock.get_time())
        n2.render(screen, clock.get_time())
        pygame.display.flip()
        clock.tick(60)

if __name__ == "__main__":
    main()
