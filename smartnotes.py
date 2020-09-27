#!/usr/bin/env python3

import pygame
import pygame.freetype
import sys

class Note(object):

    def __init__(self, data):
        self.data = data
        self.incoming = []
        self.outgoing = []
        size = len(data["text"]*10)
        self.image = pygame.Surface((size, size))
        self.image.fill((123, 214, 55))
        self.animation = Animation()
        self.rect = None
        self.target = None
        self.previous = None

    def make_root(self):
        pass

    def link(self, other_note, data):
        return Link(data, self, other_note)

    def update(self, rect, elapsed_ms):
        rect = self.image.get_rect().move(
            pygame.math.Vector2(rect.center) -
            pygame.math.Vector2(self.image.get_rect().center)
        )
        if self.rect is None:
            self.rect = self.target = self.previous = rect
        elif rect != self.target:
            if self.animation.active():
                self.rect = self.target
            self.target = rect
            self.previous = self.rect
            self.animation.start(200)
        if self.animation.active():
            self.rect = self.previous.move(
                (
                    pygame.math.Vector2(self.target.center)-
                    pygame.math.Vector2(self.previous.center)
                )*self.animation.advance(elapsed_ms)
            )

    def draw(self, screen):
        font = pygame.freetype.SysFont(
            pygame.freetype.get_default_font(),
            11
        )
        text, rect = font.render(self.data["text"])
        screen.blit(self.image, self.rect)
        screen.blit(text, rect.move(
            pygame.math.Vector2(self.rect.center)-pygame.math.Vector2(rect.center)
        ))

class Network(object):

    def __init__(self, root_note):
        self.root_note = root_note

    def make_root(self, node):
        node.make_root()
        self.root_note = node

    def update(self, rect, elapsed_ms):
        self.notes = []
        self.links = []
        middle_stripe = self._stripe(rect, 0.4)
        self.root_note.update(middle_stripe, elapsed_ms)
        self.notes.append(self.root_note)
        self._stripe_left(self.root_note, middle_stripe, [rect.width*0.2, rect.width*0.1], elapsed_ms)
        self._stripe_right(self.root_note, middle_stripe, [rect.width*0.2, rect.width*0.1], elapsed_ms)

    def _stripe_left(self, note, rect, widths, elapsed_ms):
        if not widths:
            return
        if note.incoming:
            stripe = rect.copy()
            stripe.width = widths[0]
            stripe.right = rect.left
            stripe.height = rect.height / len(note.incoming)
            for link in note.incoming:
                link.start.update(stripe, elapsed_ms)
                self.notes.append(link.start)
                self.links.append(link)
                self._stripe_left(link.start, stripe, widths[1:], elapsed_ms)
                stripe = stripe.move(0, stripe.height)

    def _stripe_right(self, note, rect, widths, elapsed_ms):
        if not widths:
            return
        if note.outgoing:
            stripe = rect.copy()
            stripe.width = widths[0]
            stripe.left = rect.right
            stripe.height = rect.height / len(note.outgoing)
            for link in note.outgoing:
                link.end.update(stripe, elapsed_ms)
                self.notes.append(link.end)
                self.links.append(link)
                self._stripe_right(link.end, stripe, widths[1:], elapsed_ms)
                stripe = stripe.move(0, stripe.height)

    def _stripe(self, rect, factor=0.2):
        stripe = rect.copy()
        stripe.width *= factor
        stripe.centerx = rect.centerx
        return stripe

    def draw(self, screen):
        for note in self.notes:
            note.draw(screen)
        for link in self.links:
            link.draw(screen)

class Link(object):

    def __init__(self, data, start, end):
        self.data = data
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

    def __init__(self, clock):
        self.height = 50
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
        self.image = pygame.Surface(rect.size)
        self.image.fill((100, 100, 100))
        text, text_rect = self.font.render(
            f"elapsed_ms = {elapsed_ms} | fps = {int(round(self.clock.get_fps()))}"
        )
        percent = self.animation.advance(elapsed_ms)
        if self.visible:
            alpha = int(255 * percent)
        else:
            alpha = 255 - int(255 * percent)
        self.image.set_alpha(alpha)
        self.image.blit(
            text,
            (
                self.image.get_width()-text_rect.width-10,
                self.image.get_height()/2-text_rect.height/2
            )
        )
        self.rect = rect

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
    root = Note({"text": "root"})
    root.link(Note({"text": "first child"}), {"label": "foo"})
    second = Note({"text": "second child"})
    root.link(second, {"label": "bar"})
    Note({"text": f"hidden?"}).link(second, {"label": "bar"})
    for i in range(5):
        Note({"text": f"pre {i}"}).link(root, {"label": f"haha {i}"})
    second.link(Note({"text": "second 1"}), {"label": "second 1"})
    second.link(Note({"text": "second 2"}), {"label": "second 2"})
    network = Network(root)
    debug_bar = DebugBar(clock)
    animation = Animation()
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                debug_bar.toggle()
                animation.start(200)
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_F1:
                if network.root_note == root:
                    network.make_root(second)
                else:
                    network.make_root(root)
        screen.fill((100, 200, 50))
        elapsed_ms = clock.get_time()
        rect = screen.get_rect()
        network_rect = rect.copy()
        if debug_bar.visible:
            network_rect.height -= debug_bar.height*animation.advance(elapsed_ms)
        else:
            network_rect.height -= debug_bar.height-debug_bar.height*animation.advance(elapsed_ms)
        network.update(network_rect, elapsed_ms)
        debug_bar_rect = rect.copy()
        debug_bar_rect.height = debug_bar.height
        debug_bar_rect.top = network_rect.bottom
        debug_bar.update(debug_bar_rect, elapsed_ms)
        network.draw(screen)
        debug_bar.draw(screen)
        pygame.display.flip()
        clock.tick(60)

if __name__ == "__main__":
    main()
