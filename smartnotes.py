#!/usr/bin/env python3

import pygame
import pygame.freetype
import sys

class Note(object):

    def __init__(self, center, radius):
        self.incoming = []
        self.outgoing = []
        self.animation = Animation()
        self.center = center
        self.radius = pygame.math.Vector2(radius, radius)
        self.image = pygame.Surface((30, 30))
        self.image.fill((123, 214, 55))

    def iter_incoming(self):
        for link in self.incoming:
            yield (link, link.start)
            for x in link.start.iter_incoming():
                yield x

    def iter_outgoing(self):
        for link in self.outgoing:
            yield (link, link.end)
            for x in link.end.iter_outgoing():
                yield x

    def update(self, rect, elapsed_ms):
        if not self.animation.active():
            self.animation.start(2000)
        self.rect = self.image.get_rect().move(
            self.radius.rotate(
                self.animation.advance(elapsed_ms)*360
            ) + self.center
        )

    def draw(self, screen):
        screen.blit(self.image, self.rect)

class Network(object):

    def __init__(self, root_note):
        self.root_note = root_note

    def update(self, rect, elapsed_ms):
        self.root_note.update(rect, elapsed_ms)
        for (link, note) in self.root_note.iter_incoming():
            note.update(rect, elapsed_ms)
        for (link, note) in self.root_note.iter_outgoing():
            note.update(rect, elapsed_ms)
        for (link, note) in self.root_note.iter_incoming():
            link.update(rect, elapsed_ms)
        for (link, note) in self.root_note.iter_outgoing():
            link.update(rect, elapsed_ms)

    def draw(self, screen):
        self.root_note.draw(screen)
        for (link, note) in self.root_note.iter_incoming():
            note.draw(screen)
        for (link, note) in self.root_note.iter_outgoing():
            note.draw(screen)
        for (link, note) in self.root_note.iter_incoming():
            link.draw(screen)
        for (link, note) in self.root_note.iter_outgoing():
            link.draw(screen)

class Link(object):

    def __init__(self, start, end):
        self.data = {"label": "label"}
        self.start = start
        self.end = end
        self.start.outgoing.append(self)
        self.end.incoming.append(self)
        self.font = pygame.freetype.SysFont(
            pygame.freetype.get_default_font(),
            10
        )

    def update(self, rect, elapsed_ms):
        pass

    def draw(self, screen):
        start = pygame.math.Vector2(self.start.rect.midright)
        end = pygame.math.Vector2(self.end.rect.midleft)
        norm_arrow = (start-end).normalize()*8
        left_arrow = norm_arrow.rotate(30)+end
        right_arrow = norm_arrow.rotate(-30)+end
        pygame.draw.aaline(
            screen,
            (0, 0, 0),
            start,
            end,
        )
        pygame.draw.aaline(
            screen,
            (0, 0, 0),
            end,
            left_arrow,
        )
        pygame.draw.aaline(
            screen,
            (0, 0, 0),
            end,
            right_arrow,
        )
        if self.data.get("label"):
            direction = end - start
            text, rect = self.font.render(
                self.data["label"],
                rotation=-int(pygame.math.Vector2((0, 0)).angle_to(direction))
            )
            screen.blit(text, rect.move(start-rect.center+direction/2))

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

    def update(self, rect, elapsed_ms):
        if not self.visible and not self.animation.active():
            return
        self.image = pygame.Surface((rect.width, self.HEIGHT))
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
        self.rect = self.image.get_rect().move((0, rect.height-self.image.get_height()+offset))

    def draw(self, screen):
        if not self.visible and not self.animation.active():
            return
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
    l = Link(n1, n2)
    network = Network(n1)
    debug_bar = DebugBar(clock)
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                debug_bar.toggle()
        screen.fill((100, 200, 50))
        elapsed_ms = clock.get_time()
        rect = screen.get_rect()
        network.update(rect, elapsed_ms)
        debug_bar.update(rect, elapsed_ms)
        network.draw(screen)
        debug_bar.draw(screen)
        pygame.display.flip()
        clock.tick(60)

if __name__ == "__main__":
    main()
