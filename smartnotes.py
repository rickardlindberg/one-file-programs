#!/usr/bin/env python3

import pygame
import sys

def main():
    pygame.init()
    screen = pygame.display.set_mode((1280, 720))
    clock = pygame.time.Clock()
    box = pygame.Surface((20, 20))
    box.fill((123, 214, 55))
    box_rect = box.get_rect()
    while True:
        print(f"frame = {clock.get_time()} (fps = {clock.get_fps()})")
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return
        box_rect = box_rect.move((1, 1))
        screen.fill((100, 200, 50))
        screen.blit(box, box_rect.topleft)
        pygame.display.flip()
        clock.tick(60)

if __name__ == "__main__":
    main()
