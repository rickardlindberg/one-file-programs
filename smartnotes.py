#!/usr/bin/env python3

import cairo
import io
import os
import pygame
import pygame.freetype
import sys

DEBUG_NOTE_BORDER = os.environ.get("DEBUG_NOTE_BORDER") == "yes"
DEBUG_ANIMATIONS = os.environ.get("DEBUG_ANIMATIONS") == "yes"

class Network(object):

    def __init__(self, root_note):
        self.root_note = root_note
        self.pos = (-1, -1)
        self.notes = []
        self.selected_note = None

    def mouse_pos(self, pos):
        self.pos = pos

    def click(self, pos):
        for note in reversed(self.notes):
            if note.rect.collidepoint(pos):
                self.make_root(note)
                return

    def make_root(self, node):
        node.make_root()
        self.root_note = node

    def update(self, rect, elapsed_ms):
        for note in reversed(self.notes):
            if note.rect.collidepoint(self.pos):
                self.selected_note = note
                break
        else:
            self.selected_note = None
        self.stripe_rects = []
        padding = 8
        self.full_width = int(rect.width * 0.3)
        self.old_nodes = self.notes
        self.notes = []
        self.links = []
        middle_stripe = self._stripe(rect, 0.3)
        self.root_note.update(
            middle_stripe,
            elapsed_ms,
            self.full_width,
            "center",
            None,
            self.root_note is self.selected_note
        )
        self.notes.append(self.root_note)
        sizes = [
            (rect.width*0.05, rect.width*0.15),
            (rect.width*0.03, rect.width*0.1),
        ]
        self._stripe_recursive(
            self.root_note,
            middle_stripe,
            sizes,
            elapsed_ms,
            padding,
            "left"
        )
        self._stripe_recursive(
            self.root_note,
            middle_stripe,
            sizes,
            elapsed_ms,
            padding,
            "right"
        )
        for link in self.links:
            link.update(None, elapsed_ms)

    def _stripe_recursive(self, note, parent_rect, widths, elapsed_ms, padding, direction):
        if not widths:
            return
        parent_rect = parent_rect.inflate(0, -padding)
        if direction == "left":
            links = note.incoming
        else:
            links = note.outgoing
        if links:
            space_width, stripe_width = widths[0]
            if direction == "left":
                rect = parent_rect.move(-space_width-stripe_width, 0)
                rect.width = stripe_width
            else:
                rect = parent_rect.move(parent_rect.width+space_width, 0)
                rect.width = stripe_width
            self.stripe_rects.append(rect)
            for link, y_center, height in self._vertical_stripes(rect, links):
                if direction == "left":
                    stripe = pygame.Rect(rect.x, 0, stripe_width, height)
                    linked = link.start
                else:
                    stripe = pygame.Rect(rect.x, 0, stripe_width, height)
                    linked = link.end
                stripe.centery = y_center
                linked.update(
                    stripe.inflate(0, -padding),
                    elapsed_ms,
                    self.full_width,
                    direction,
                    note.rect if linked not in self.old_nodes else None,
                    linked is self.selected_note
                )
                self.notes.insert(0, linked)
                self.links.append(link)
                self._stripe_recursive(linked, stripe, widths[1:], elapsed_ms, int(padding*0.8), direction)

    def _vertical_stripes(self, rect, links):
        if rect.collidepoint(self.pos):
            even_height = rect.height / len(links)
            even_width = even_height * 5/3
            if rect.width < even_width:
                yield from self._vertical_stripes_even(rect, links)
            else:
                yield from self._vertical_stripes_fish_eye(rect, links)
        else:
            yield from self._vertical_stripes_even(rect, links)

    def _vertical_stripes_fish_eye(self, rect, links):
        fractions = []
        even_height = rect.height / len(links)
        for index, link in enumerate(links):
            center_y = rect.y+index*even_height+even_height/2
            y_diff = abs(center_y - self.pos[1])
            fractions.append(max(even_height*3-y_diff, even_height))
        one_fraction_h = rect.height / sum(fractions)
        y = 0
        for fraction, link in zip(fractions, links):
            h = one_fraction_h * fraction
            yield (link, rect.y+y+h/2, h)
            y += h

    def _vertical_stripes_even(self, rect, links):
        even_height = rect.height / len(links)
        y = 0
        for link in links:
            yield (link, rect.y+y+even_height/2, even_height)
            y += even_height

    def _stripe(self, rect, factor=0.2):
        stripe = rect.copy()
        stripe.width *= factor
        stripe.centerx = rect.centerx
        return stripe

    def draw(self, screen):
        if DEBUG_NOTE_BORDER:
            for rect in self.stripe_rects:
                pygame.draw.rect(screen, (255, 255, 0), rect, 2)
        for link in self.links:
            link.draw(screen)
        for note in self.notes:
            note.draw(screen)

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

    def update(self, rect, elapsed_ms, full_width, side,
            fade_from_rect, selected):
        self.selected = selected
        self.true_rect = rect
        self._make_card(full_width)
        target = self._get_target(rect, side)
        if fade_from_rect:
            x = target.copy()
            x.center = fade_from_rect.center
            self.rect = self.target = self.previous = x
        if self.rect is None:
            self.rect = self.target = self.previous = target
        if target != self.target:
            if self.animation.active():
                self.rect = self.target
            self.target = target
            self.previous = self.rect
            self.animation.start(3000 if DEBUG_ANIMATIONS else 300)
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

    def _get_target(self, rect, side):
        target = self.card.get_rect()
        target = target.fit(rect)
        if side == "left":
            target.midright = rect.midright
        elif side == "right":
            target.midleft = rect.midleft
        else:
            target.center = rect.center
        return target

    def draw(self, screen):
        screen.blit(
            pygame.transform.smoothscale(self.card, self.rect.size),
            self.rect
        )
        if self.selected:
            pygame.draw.rect(screen, (255, 0, 0), self.rect.inflate(-6, -6), 2)
        if DEBUG_NOTE_BORDER:
            pygame.draw.rect(screen, (255, 0, 0), self.true_rect, 1)

class Link(object):

    def __init__(self, data, start, end):
        self.data = data
        self.start = start
        self.end = end
        self.start.outgoing.append(self)
        self.end.incoming.append(self)
        self.start_pos = None
        self.end_pos = None

    def update(self, rect, elapsed_ms):
        def draw(ctx, width, height):
            if start.x < end.x:
                startx = 0
                endx = width
                c1x = 0.6*width
                c2x = 0.4*width
            else:
                startx = width
                endx = 0
                c1x = 0.4*width
                c2x = 0.6*width
            if start.y < end.y:
                starty = PADDING
                endy = height-PADDING
                c1y = 0.0*(height-PADDING)+PADDING
                c2y = 1.0*(height-PADDING)+PADDING
            else:
                starty = height-PADDING
                endy = PADDING
                c1y = 1.0*(height-PADDING)+PADDING
                c2y = 0.0*(height-PADDING)+PADDING
            ctx.move_to(startx, starty)
            ctx.line_to(startx+0.02*(endx-startx), starty)
            ctx.curve_to(c1x, c1y, c2x, c2y, endx-0.02*(endx-startx), endy)
            ctx.line_to(endx, endy)
            ctx.set_source_rgb(0.45, 0.5, 0.7)
            ctx.set_line_width(1.5)
            ctx.stroke()
        start = pygame.math.Vector2(self.start.rect.midright)
        end = pygame.math.Vector2(self.end.rect.midleft)
        if start != self.start_pos or end != self.end_pos:
            self.start_pos = start
            self.end_pos = end
            PADDING = 3
            self.image = draw_cairo(
                max(1, int(abs(start.x-end.x))),
                max(1, int(abs(start.y-end.y)))+2*PADDING,
                draw
            )
            self.pos = (
                min(start.x, end.x),
                min(start.y, end.y)-PADDING,
            )

    def draw(self, screen):
        screen.blit(self.image, self.pos)

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
        self.image.fill((84, 106, 134))
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
            elif event.type == pygame.MOUSEMOTION:
                network.mouse_pos(event.pos)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                network.click(event.pos)
        screen.fill((134, 169, 214))
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

def draw_cairo(width, height, fn):
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    ctx = cairo.Context(surface)
    fn(ctx, width, height)
    buf = io.BytesIO()
    surface.write_to_png(buf)
    buf.seek(0)
    return pygame.image.load(buf).convert_alpha()
    #surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    #ctx = cairo.Context(surface)
    #fn(ctx, width, height)
    #buf = surface.get_data()
    #image = pygame.image.frombuffer(buf, (width, height), "ARGB")
    #return image

if __name__ == "__main__":
    main()
