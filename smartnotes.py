#!/usr/bin/env python3

import cairo
import contextlib
import datetime
import io
import json
import os
import pygame
import pygame.freetype
import subprocess
import sys
import tempfile
import uuid

DEBUG_NOTE_BORDER = os.environ.get("DEBUG_NOTE_BORDER") == "yes"
DEBUG_ANIMATIONS = os.environ.get("DEBUG_ANIMATIONS") == "yes"

USER_EVENT_CHECK_EXTERNAL = pygame.USEREVENT

class Widget(object):

    def __init__(self, width=-1, height=-1):
        self._width = width
        self._height = height
        self._visible = True

    def resize(self, width=None, height=None):
        if width is not None:
            self._width = width
        if height is not None:
            self._height = height

    def get_width(self):
        return self._width

    def get_height(self):
        return self._height

    def is_visible(self):
        return self._visible

    def toggle_visible(self):
        self._visible = not self._visible

class Box(Widget):

    def __init__(self):
        Widget.__init__(self)
        self.children = []

    def add(self, child):
        self.children.append(child)
        return child

    def update(self, rect, elapsed_ms):
        sizes = []
        divide_indices = []
        for child in self.visible_children():
            if self.get_widget_size(child) == -1:
                divide_indices.append(len(sizes))
                sizes.append(0)
            else:
                sizes.append(self.get_widget_size(child))
        if divide_indices:
            divide_size = (self.get_rect_size(rect) - sum(sizes)) / len(divide_indices)
            for divide_index in divide_indices:
                sizes[divide_index] = divide_size
        for child, size in zip(self.visible_children(), sizes):
            rect = self.set_rect_size(rect, size)
            child.update(rect, elapsed_ms)
            rect = self.move_rect(rect, size)

    def draw(self, screen):
        for child in self.visible_children():
            child.draw(screen)

    def visible_children(self):
        for child in self.children:
            if child.is_visible():
                yield child

class VBox(Box):

    def get_widget_size(self, widget):
        return widget.get_height()

    def get_rect_size(self, thing):
        return thing.height

    def set_rect_size(self, rect, size):
        rect = rect.copy()
        rect.height = size
        return rect

    def move_rect(self, rect, delta):
        return rect.move(0, delta)

class HBox(Box):

    def get_widget_size(self, widget):
        return widget.get_widget_size()

    def get_rect_size(self, thing):
        return thing.width

    def set_rect_size(self, rect, size):
        rect = rect.copy()
        rect.width = size
        return rect

    def move_rect(self, rect, delta):
        return rect.move(delta, 0)

class RootWidget(VBox):

    def __init__(self, path):
        VBox.__init__(self)
        self.db = NoteDb(path)

    def run(self):
        pygame.init()
        pygame.display.set_caption("Smart Notes")
        screen = pygame.display.set_mode((1280, 720))
        clock = pygame.time.Clock()
        self.network = self.add(NetworkWidget(self.db))
        self.debug_bar = self.add(DebugBar(clock))
        self.external_text_entries = ExternalTextEntries()
        pygame.time.set_timer(USER_EVENT_CHECK_EXTERNAL, 1000)
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                else:
                    self.process_event(event)
            self.update(screen.get_rect(), clock.get_time())
            screen.fill((134, 169, 214))
            self.draw(screen)
            pygame.display.flip()
            clock.tick(60)

    def process_event(self, event):
        if event.type == pygame.KEYDOWN and event.unicode == "q":
            pygame.event.post(pygame.event.Event(pygame.QUIT))
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.debug_bar.toggle()
        elif event.type == pygame.MOUSEMOTION:
            self.network.mouse_pos(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            self.network.click(event.pos)
        elif event.type == USER_EVENT_CHECK_EXTERNAL:
            self.external_text_entries.check()
        elif event.type == pygame.KEYDOWN and event.unicode == "e":
            if self.network.selected_note:
                self.external_text_entries.add(
                    EditNoteText(self.db, self.network.selected_note.note_id)
                )
        elif event.type == pygame.KEYDOWN and event.unicode == "c":
            if self.network.selected_note:
                child_note_id = self.db.create_note(text="Enter note text...")
                self.db.create_link(self.network.selected_note.note_id, child_note_id)
                self.external_text_entries.add(
                    EditNoteText(self.db, child_note_id)
                )
        elif event.type == pygame.KEYDOWN and event.unicode == "n":
            note_id = self.db.create_note(text="Enter note text...")
            self.network.open_note(note_id)
            self.external_text_entries.add(
                EditNoteText(self.db, note_id)
            )

class NetworkWidget(Widget):

    def __init__(self, db):
        Widget.__init__(self)
        self.db = db
        self.pos = (-1, -1)
        self.notes = []
        self.selected_note = None
        self.root_note = None
        for note_id, note_data in self.db.get_notes():
            self.open_note(note_id)
            break

    def mouse_pos(self, pos):
        self.pos = pos

    def click(self, pos):
        for note in reversed(self.notes):
            if note.rect.collidepoint(pos):
                self.make_root(note)
                return

    def open_note(self, note_id):
        self.make_root(NoteWidget(self.db, note_id))

    def make_root(self, node):
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
        if self.root_note is None:
            return
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
            links = note.update_incoming()
        else:
            links = note.update_outgoing()
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

class NoteWidget(Widget):

    def __init__(self, db, note_id):
        Widget.__init__(self)
        self.db = db
        self.note_id = note_id
        self.data = None
        self.incoming = []
        self.outgoing = []
        self.animation = Animation()
        self.rect = None
        self.target = None
        self.previous = None
        self.full_width = None

    def update_incoming(self):
        by_id = {
            link.link_id: link
            for link in self.incoming
        }
        self.incoming = []
        for link_id, link_data in self.db.get_incoming_links(self.note_id):
            if link_id in by_id:
                self.incoming.append(by_id.pop(link_id))
            else:
                LinkWidget(
                    self.db,
                    link_id,
                    NoteWidget(self.db, link_data["from"]),
                    self
                )
        return self.incoming

    def update_outgoing(self):
        by_id = {
            link.link_id: link
            for link in self.outgoing
        }
        self.outgoing = []
        for link_id, link_data in self.db.get_outgoing_links(self.note_id):
            if link_id in by_id:
                self.outgoing.append(by_id.pop(link_id))
            else:
                LinkWidget(
                    self.db,
                    link_id,
                    self,
                    NoteWidget(self.db, link_data["to"])
                )
        return self.outgoing

    def _make_card(self, full_width, data):
        if self.full_width == full_width and data is self.data:
            return
        self.data = data
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

    def update(self, rect, elapsed_ms, full_width, side, fade_from_rect, selected):
        self.selected = selected
        self.true_rect = rect
        self._make_card(full_width, self.db.get_note_data(self.note_id))
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
            self.animation.start(300)
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

class LinkWidget(Widget):

    def __init__(self, db, link_id, start, end):
        Widget.__init__(self)
        self.db = db
        self.link_id = link_id
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

class DebugBar(Widget):

    IDEAL_HEIGHT = 50

    def __init__(self, clock):
        Widget.__init__(self, height=self.IDEAL_HEIGHT)
        self.clock = clock
        self.animation = Animation()
        self.font = pygame.freetype.SysFont(
            pygame.freetype.get_default_font(),
            18
        )

    def is_visible(self):
        return Widget.is_visible(self) or self.animation.active()

    def toggle(self):
        self.toggle_visible()
        self.animation.start(200)

    def update(self, rect, elapsed_ms):
        self.image = pygame.Surface(rect.size)
        self.image.fill((84, 106, 134))
        text, text_rect = self.font.render(
            f"elapsed_ms = {elapsed_ms} | fps = {int(round(self.clock.get_fps()))}"
        )
        percent = self.animation.advance(elapsed_ms)
        if Widget.is_visible(self):
            alpha = int(255 * percent)
            self.resize(height=int(self.IDEAL_HEIGHT * percent))
        else:
            alpha = 255 - int(255 * percent)
            self.resize(height=self.IDEAL_HEIGHT - int(self.IDEAL_HEIGHT * percent))
        self.image.set_alpha(alpha)
        self.image.blit(
            text,
            (
                self.image.get_width()-text_rect.width-10,
                self.IDEAL_HEIGHT/2-text_rect.height/2
            )
        )
        self.rect = rect

    def draw(self, screen):
        screen.blit(self.image, self.rect)

class Animation(object):

    def __init__(self):
        self.duration_ms = 1
        self.progress = 1
        self.last_consumed = True

    def start(self, duration_ms):
        if DEBUG_ANIMATIONS:
            duration_ms = duration_ms * 10
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

class NoteDb(object):

    def __init__(self, path):
        self.path = path
        self.data = read_json_file(self.path, {
            "version": 1,
            "notes": {},
            "links": {},
        })

    def get_notes(self):
        return self.data["notes"].items()

    def get_note_data(self, note_id):
        return self.data["notes"][note_id]

    def get_outgoing_links(self, note_id):
        return [
            (link_id, link)
            for link_id, link in self.data["links"].items()
            if link["from"] == note_id
        ]

    def get_incoming_links(self, note_id):
        return [
            (link_id, link)
            for link_id, link in self.data["links"].items()
            if link["to"] == note_id
        ]

    def create_note(self, **params):
        note_id = genid()
        self.data = dict(
            self.data,
            notes=dict(
                self.data["notes"],
                **{note_id: dict(params, timestamp_created=utcnow_timestamp_string())}
            )
        )
        self._update()
        return note_id

    def update_note(self, note_id, **params):
        self.data = dict(
            self.data,
            notes=dict(
                self.data["notes"],
                **{note_id: dict(self.data["notes"][note_id], **params)}
            )
        )
        self._update()

    def create_link(self, from_id, to_id):
        link_id = genid()
        self.data = dict(
            self.data,
            links=dict(
                self.data["links"],
                **{link_id: {
                    "from": from_id,
                    "to": to_id,
                    "timestamp_created": utcnow_timestamp_string(),
                }}
            )
        )
        self._update()
        return link_id

    def _update(self):
        write_json_file(self.path, self.data)

class ExternalTextEntries(object):

    def __init__(self):
        self.entries = []

    def add(self, entry):
        self.entries.append(entry)

    def check(self):
        self.entries = [
            entry
            for entry in self.entries
            if entry.check()
        ]

class ExternalTextEntry(object):

    def __init__(self, text):
        self.text = text
        self.f = tempfile.NamedTemporaryFile(suffix="-smartnotes-external-")
        self.f.write(self.text.encode("utf-8"))
        self.f.flush()
        self.p = subprocess.Popen(["gvim", "--nofork", self.f.name])

    def check(self):
        self.f.seek(0)
        text = self.f.read().decode("utf-8")
        if text != self.text:
            self.text = text
            self._new_text()
        if self.p.poll() is not None:
            self.f.close()
            return False
        return True

    def _new_text(self):
        pass

class EditNoteText(ExternalTextEntry):

    def __init__(self, db, note_id=None):
        self.db = db
        self.note_id = note_id
        ExternalTextEntry.__init__(self, db.get_note_data(self.note_id)["text"])

    def _new_text(self):
        self.db.update_note(self.note_id, text=self.text)

def main():
    if len(sys.argv) < 2:
        sys.exit("Usage: smartnotes.py <file>")
    RootWidget(sys.argv[1]).run()

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

def read_json_file(path, default_value):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    else:
        return default_value

def write_json_file(path, value):
    with safe_write(path) as f:
        json.dump(value, f)

@contextlib.contextmanager
def safe_write(path):
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w") as f:
        yield f
    os.rename(tmp_path, path)

def genid():
    return uuid.uuid4().hex

def utcnow_timestamp_string():
    return datetime.datetime.utcnow().isoformat()

if __name__ == "__main__":
    main()
