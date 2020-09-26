#!/usr/bin/env python3

import pygame

def main():
    pygame.init()
    screen = pygame.display.set_mode((1280, 720))
    clock = pygame.time.Clock()
    while True:
        print(f"frame = {clock.get_time()} (fps = {clock.get_fps()})")
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                break
        screen.fill((100, 200, 50))
        pygame.display.flip()
        clock.tick(60)

if __name__ == "__main__":
    main()
