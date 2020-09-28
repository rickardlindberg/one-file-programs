#!/usr/bin/env python3

import pygame
import pygame.freetype
import sys

class Network(object):

    def __init__(self, root_note):
        self.root_note = root_note

    def make_root(self, node):
        node.make_root()
        self.root_note = node

    def update(self, rect, elapsed_ms):
        self.full_width = int(rect.width * 0.3)
        self.notes = []
        self.links = []
        middle_stripe = self._stripe(rect, 0.3)
        self.root_note.update(middle_stripe, elapsed_ms, self.full_width)
        self.notes.append(self.root_note)
        sizes = [
            (rect.width*0.05, rect.width*0.15),
            (rect.width*0.03, rect.width*0.1),
        ]
        self._stripe_left(
            self.root_note,
            middle_stripe,
            sizes,
            elapsed_ms
        )
        self._stripe_right(
            self.root_note,
            middle_stripe,
            sizes,
            elapsed_ms
        )

    def _stripe_left(self, note, rect, widths, elapsed_ms):
        if not widths:
            return
        if note.incoming:
            padding = 5
            space_width, stripe_width = widths[0]
            stripe = rect.copy()
            stripe.width = stripe_width
            stripe.right = rect.left - space_width
            stripe.height = (rect.height-padding) / len(note.incoming) - padding
            stripe.top += padding
            for link in note.incoming:
                link.start.update(stripe, elapsed_ms, self.full_width)
                self.notes.append(link.start)
                self.links.append(link)
                self._stripe_left(link.start, stripe, widths[1:], elapsed_ms)
                stripe = stripe.move(0, stripe.height+padding)

    def _stripe_right(self, note, rect, widths, elapsed_ms):
        if not widths:
            return
        if note.outgoing:
            padding = 5
            space_width, stripe_width = widths[0]
            stripe = rect.copy()
            stripe.width = stripe_width
            stripe.left = rect.right + space_width
            stripe.height = (rect.height-padding) / len(note.outgoing) - padding
            stripe.top += padding
            for link in note.outgoing:
                link.end.update(stripe, elapsed_ms, self.full_width)
                self.notes.append(link.end)
                self.links.append(link)
                self._stripe_right(link.end, stripe, widths[1:], elapsed_ms)
                stripe = stripe.move(0, stripe.height+padding)

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

class Note(object):

    def __init__(self, data):
        self.data = data
        self.incoming = []
        self.outgoing = []
        self.animation = Animation()
        self.rect = None
        self.target = None
        self.previous = None
        self.full_width = None

    def _make_card(self, full_width):
        if self.full_width == full_width:
            return
        self.full_width = full_width
        size = (full_width, int(full_width*3/5))
        border_size = 4
        self.card = pygame.Surface(size, pygame.SRCALPHA)
        border = pygame.Rect((0, 0), size)
        border.width -= border_size
        border.height -= border_size
        border.x += border_size
        border.y += border_size
        pygame.draw.rect(self.card, (50, 50, 50, 150), border)
        border.x -= border_size
        border.y -= border_size
        pygame.draw.rect(self.card, (250, 250, 250), border)
        font = pygame.freetype.Font(
            "/usr/share/fonts/dejavu/DejaVuSerif.ttf",
            20
        )
        text, rect = font.render(self.data["text"])
        self.card.blit(text, rect.move(
            pygame.math.Vector2(self.card.get_rect().center)-pygame.math.Vector2(rect.center)
        ))

    def make_root(self):
        pass

    def link(self, other_note, data):
        return Link(data, self, other_note)

    def update(self, rect, elapsed_ms, full_width):
        self._make_card(full_width)
        target = self._get_target(rect)
        if self.rect is None:
            self.rect = self.target = self.previous = target
        elif target != self.target:
            if self.animation.active():
                self.rect = self.target
            self.target = target
            self.previous = self.rect
            self.animation.start(200)
        if self.animation.active():
            x_diff = self.target.width - self.previous.width
            y_diff = self.target.height - self.previous.height
            percent = self.animation.advance(elapsed_ms)
            self.rect = self.previous.inflate(x_diff*percent, y_diff*percent).move(
                (
                    pygame.math.Vector2(self.target.center)-
                    pygame.math.Vector2(self.previous.center)
                )*percent
            )

    def _get_target(self, rect):
        target = self.card.get_rect()
        target = target.fit(rect)
        target.center = rect.center
        return target

    def draw(self, screen):
        screen.blit(
            pygame.transform.smoothscale(self.card, self.rect.size),
            self.rect
        )

class Link(object):

    def __init__(self, data, start, end):
        self.data = data
        self.start = start
        self.end = end
        self.start.outgoing.append(self)
        self.end.incoming.append(self)

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
    root.link(Note({"text": "first child"}), {})
    second = Note({"text": "second child"})
    root.link(second, {})
    hidden = Note({"text": f"hidden?"})
    hidden.link(second, {})
    for i in range(10):
        Note({"text": f"pre {i}"}).link(root, {})
    for i in range(10):
        Note({"text": f"pre {i}"}).link(hidden, {})
    second.link(Note({"text": "second 1"}), {})
    second.link(Note({"text": "second 2"}), {})
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
