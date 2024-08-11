#!/usr/bin/env python3

from collections import defaultdict
import contextlib
import datetime
import difflib
import doctest
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import uuid
import webbrowser

###############################################################################
# App Engine
###############################################################################

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "yes"

import cairo
import pygame

class PygameCairoEngine:

    def run(self, app):
        pygame.init()
        pygame.key.set_repeat(500, 30)
        root_widget = app(PygameWindow())
        screen = pygame.display.set_mode((1280, 720), pygame.RESIZABLE)
        clock = pygame.time.Clock()
        external_text_entries = ExternalTextEntries()
        pygame.time.set_timer(USER_EVENT_CHECK_EXTERNAL, 1000)
        pygame_cairo_surface = self.create_pygame_cairo_surface(screen)
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                elif event.type == pygame.VIDEORESIZE:
                    pygame_cairo_surface = self.create_pygame_cairo_surface(screen)
                elif event.type == USER_EVENT_CHECK_EXTERNAL:
                    external_text_entries.check()
                elif event.type == USER_EVENT_EXTERNAL_TEXT_ENTRY:
                    external_text_entries.add(event.entry)
                else:
                    root_widget.process_event(PygameEvent(event))
            root_widget.update(screen.get_rect(), clock.get_time())
            pygame_cairo_surface.lock()
            root_widget.draw(CairoCanvas(self.create_cairo_image(pygame_cairo_surface)))
            pygame_cairo_surface.unlock()
            screen.blit(pygame_cairo_surface, (0, 0))
            pygame.display.flip()
            clock.tick(60)

    def create_pygame_cairo_surface(self, screen):
        return pygame.Surface(
            screen.get_size(),
            depth=32,
            masks=(
                0x00FF0000,
                0x0000FF00,
                0x000000FF,
                0x00000000,
            )
        )

    def create_cairo_image(self, pygame_cairo_surface):
        return cairo.ImageSurface.create_for_data(
            pygame_cairo_surface.get_buffer(),
            cairo.FORMAT_ARGB32,
            *pygame_cairo_surface.get_size()
        )

class CairoCanvas(object):

    def __init__(self, surface):
        self.surface = surface
        self.ctx = cairo.Context(self.surface)

    def create_image(self, size, fn):
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size[0], size[1])
        fn(CairoCanvas(surface))
        return surface

    def blit(self, image, pos, alpha=255, scale_to_fit=None):
        self.ctx.save()
        self.ctx.translate(pos[0], pos[1])
        if scale_to_fit:
            self.ctx.scale(
                max(0.001, scale_to_fit[0] / image.get_width()),
                max(0.001, scale_to_fit[1] / image.get_height())
            )
        self.ctx.set_source_surface(image, 0, 0)
        self.ctx.paint_with_alpha(alpha/255)
        self.ctx.restore()

    def fill_rect(self, rect, color=(0, 0, 0)):
        self._set_color(color)
        self.ctx.rectangle(rect.x, rect.y, rect.width, rect.height)
        self.ctx.fill()

    def draw_rect(self, rect, color, width):
        if width % 2 == 0:
            offset = 0
        else:
            offset = 0.5
        self._set_color(color)
        self.ctx.rectangle(rect.x+offset, rect.y+offset, rect.width, rect.height)
        self.ctx.set_line_width(width)
        self.ctx.stroke()

    def _set_color(self, color):
        if len(color) == 4:
            self.ctx.set_source_rgba(color[0]/255, color[1]/255, color[2]/255, color[3]/255)
        else:
            self.ctx.set_source_rgb(color[0]/255, color[1]/255, color[2]/255)

    def render_text(self, text, box,
        size=40,
        boxalign="center",
        face=None,
        textalign="left",
        italic=False,
        split=True,
        color=(0, 0, 0)
    ):
        if box.height <= 0:
            return
        if not text.strip():
            return
        if DEBUG_TEXT_BORDER:
            self.ctx.set_source_rgb(1, 0.1, 0.1)
            self.ctx.rectangle(box[0], box[1], box[2], box[3])
            self.ctx.set_line_width(1)
            self.ctx.stroke()
        if face is not None:
            cairo_family = face
            cairo_slant = cairo.FontSlant.ITALIC if italic else cairo.FontSlant.NORMAL
            self.ctx.select_font_face(
                cairo_family,
                cairo_slant
            )
        self._set_color(color)
        metrics, scale_factor = self._find_best_fit(text, box, split, size)
        self.ctx.save()
        xoffset = 0
        yoffset = 0
        self._translate_box(box, metrics["width"]*scale_factor, metrics["height"]*scale_factor, boxalign)
        self.ctx.scale(scale_factor, scale_factor)
        for x, y, width, part in metrics["parts"]:
            if not split:
                x = 0
            if textalign == "center":
                x_align_offset = (metrics["width"]-width)/2
            elif textalign == "right":
                x_align_offset = metrics["width"]-width
            else:
                x_align_offset = 0
            self.ctx.move_to(x+x_align_offset, y)
            self.ctx.show_text(part)
        if DEBUG_TEXT_BORDER:
            self.ctx.set_source_rgb(0.1, 1, 0.1)
            self.ctx.rectangle(0, 0, metrics["width"], metrics["height"])
            self.ctx.set_line_width(2/scale_factor)
            self.ctx.stroke()
        self.ctx.restore()

    def _find_best_fit(self, text, box, split, size):
        self.ctx.set_font_size(size)
        if split:
            metrics = self._find_best_split(text, box)
        else:
            metrics = self._get_metrics(text.splitlines())
        scale_factor = box.width / metrics["width"]
        if metrics["height"] * scale_factor > box.height:
            scale_factor = box.height / metrics["height"]
        scale_factor = min(scale_factor, 1)
        size = int(size*scale_factor)
        if scale_factor < 1:
            while True:
                self.ctx.set_font_size(size)
                metrics = self._get_metrics([x[-1] for x in metrics["parts"]])
                if size < 2:
                    break
                if metrics["width"] <= box.width and metrics["height"] <= box.height:
                    break
                size -= 1
        return metrics, 1

    def _find_best_split(self, text, box):
        raw_text = RawText(text)
        target_ratio = box.width / box.height
        metrics = self._get_metrics(raw_text.to_lines())
        diff = abs(metrics["ratio"] - target_ratio)
        while raw_text.shrink():
            new_metrics = self._get_metrics(raw_text.to_lines())
            new_diff = abs(new_metrics["ratio"] - target_ratio)
            if new_diff > diff:
                pass
            else:
                diff = new_diff
                metrics = new_metrics
        return metrics

    def _get_metrics(self, splits):
        width = 0
        height = 0
        start_y = None
        parts = []
        font_ascent, font_descent = self.ctx.font_extents()[0:2]
        extra = font_descent*0.9
        for text in splits:
            extents = self.ctx.text_extents(text)
            if text == "":
                height += font_ascent*0.2
            else:
                height += font_ascent
            parts.append((-extents.x_bearing, height, extents.width, text))
            width = max(width, extents.width)
            height += font_descent
            height += extra
        height -= extra
        if height == 0:
            height = 0.1
        return {
            "parts": parts,
            "width": width,
            "height": height,
            "ratio": width / height,
        }

    def _translate_box(self, box, text_width, text_height, boxalign):
        # topleft      topcenter     topright
        # midleft        center      midright
        # bottomleft  bottomcenter  bottomright
        if boxalign in ["topright", "midright", "bottomright"]:
            xoffset = box[2]-text_width
        elif boxalign in ["topcenter", "center", "bottomcenter"]:
            xoffset = box[2]/2-text_width/2
        else:
            xoffset = 0
        if boxalign in ["bottomleft", "bottomcenter", "bottomright"]:
            yoffset = box[3]-text_height
        elif boxalign in ["midleft", "center", "midright"]:
            yoffset = box[3]/2-text_height/2
        else:
            yoffset = 0
        self.ctx.translate(box[0]+xoffset, box[1]+yoffset)

    def move_to(self, x, y):
        self.ctx.move_to(x, y)

    def line_to(self, x, y):
        self.ctx.line_to(x, y)

    def curve_to(self, *args):
        self.ctx.curve_to(*args)

    def set_source_rgb(self, *args):
        self.ctx.set_source_rgb(*args)

    def set_line_width(self, *args):
        self.ctx.set_line_width(*args)

    def stroke(self, *args):
        self.ctx.stroke(*args)

    def get_rect(self):
        return pygame.Rect(
            0,
            0,
            self.surface.get_width(),
            self.surface.get_height()
        )

###############################################################################
# App
###############################################################################

DEBUG_NOTE_BORDER = os.environ.get("DEBUG_NOTE_BORDER") == "yes"
DEBUG_TEXT_BORDER = os.environ.get("DEBUG_TEXT_BORDER") == "yes"
DEBUG_ANIMATIONS = os.environ.get("DEBUG_ANIMATIONS") == "yes"
DEBUG = DEBUG_NOTE_BORDER or DEBUG_TEXT_BORDER or DEBUG_ANIMATIONS

USER_EVENT_CHECK_EXTERNAL      = pygame.USEREVENT
USER_EVENT_EXTERNAL_TEXT_ENTRY = pygame.USEREVENT + 1

COLOR_SELECTION          = (214, 138, 208)
COLOR_SEARCH_BAR         = (108, 138, 173)
COLOR_BACKGROUND         = (134, 169, 214)
COLOR_ACTIVE             = (25, 204, 25)
COLOR_INACTIVE           = (204, 204, 204)
COLOR_LINE               = (114, 127, 178)
COLOR_VIRTUAL_LINE       = (185, 118, 169)
COLOR_NOTE_BG            = (250, 250, 250)
COLOR_NOTE_TEXT          = (20, 20, 20)
COLOR_NOTE_DATE_TEXT     = (100, 100, 100)
COLOR_NOTE_TAG_TEXT      = (100, 100, 255)
FONT_MONOSPACE           = "Monospace"
FONT_TEXT                = "San-Serif"
EDITOR_COMMAND           = ["gvim", "--nofork", None]
NUM_SEARCH_RESULTS       = 8
NEW_NOTE_TEXT            = "Enter note text...\n"
KEY_QUIT                 = "ctrl+q"
KEY_UNDO                 = "ctrl+z"
KEY_REDO                 = "ctrl+y"
KEY_TOGGLE_DEBUG_BAR     = "f1"
KEY_CLEAR_FOCUS          = "escape"
KEY_DISMISS              = "ctrl+g"
KEY_INCREASE             = "ctrl+shift+="
KEY_DECREASE             = "ctrl+-"
KEY_OPEN_SEARCH          = "/"
KEY_CREATE_NOTE          = "c"
KEY_EDIT_NOTE            = "e"
KEY_DELETE_NOTE          = "d"
KEY_UNLINK_NOTE          = "u"
KEY_OPEN_LINKS           = "g"
KEY_TOGGLE_TABLE_NETWORK = "t"
KEY_MOVE_UP              = "1"
KEY_MOVE_DOWN            = "2"
BIB_COLOR                = (250, 150, 150)
TAG_ATTRIBUTES           = [
    {"name": "title",     "textalign": "center"},

    {"name": "bib",       "textalign": "center", "bg": BIB_COLOR},
    {"name": "blog",      "textalign": "center", "bg": BIB_COLOR},
    {"name": "book",      "textalign": "center", "bg": BIB_COLOR},

    {"name": "lit",       "bg": (150, 250, 150)},
    {"name": "ref",       "bg": (150, 250, 150)},
    {"name": "quote",     "bg": (150, 250, 150), "italic": True},

    {"name": "toc",       "bg": (199, 134, 214)},
    {"name": "structure", "bg": (134, 189, 214)},
    {"name": "main",      "bg": (238, 238, 205)},
    {"name": "link",      "bg": (134, 209, 214), "italic": True, "textalign": "center"},
]

class Widget(object):

    def __init__(self, window, parent, width=-1, height=-1, visible=True):
        self._window = window
        self._parent = parent
        self._width = width
        self._height = height
        self._visible = visible
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.allotted_rect = pygame.Rect(0, 0, 0, 0)

    def set_title(self, title):
        self._window.set_title(title)

    def instantiate(self, cls, *args, **kwargs):
        return cls(self._window, self, *args, **kwargs)

    def focus(self):
        self._window.set_focus(self)

    def quick_focus(self):
        self._window.set_quick_focus(self)

    def clear_quick_focus(self):
        return self._window.clear_quick_focus()

    def has_focus(self):
        return self._window.is_focused(self)

    def save_focus(self):
        self._window.save_focus()

    def restore_focus(self):
        self._window.restore_focus()

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

    def quit(self):
        self._window.close()

    def post_event(self, event_type, **kwargs):
        pygame.event.post(pygame.event.Event(event_type, **kwargs))

    def process_event(self, event):
        if self.has_focus() and event.key_down():
            self.bubble_event(event)

    def update(self, rect, elapsed_ms):
        self.allotted_rect = rect

    def draw(self, canvas):
        if self.has_focus():
            canvas.draw_rect(
                self.get_focus_rect().inflate(
                    -self.get_focus_rect_size(),
                    -self.get_focus_rect_size()
                ),
                COLOR_SELECTION,
                self.get_focus_rect_size()
            )

    def get_focus_rect_size(self):
        return 2

    def get_focus_rect(self):
        return self.allotted_rect

    def get_used_rect(self):
        return self.allotted_rect

    def bubble_event(self, event):
        if self._parent:
            self._parent.bubble_event(event)

class Padding(Widget):

    def __init__(self, window, parent, widget, hpadding=None, vpadding=None, **kwargs):
        Widget.__init__(self, window, parent, **kwargs)
        self.widget = widget
        self.hpadding = (lambda rect: 0) if hpadding is None else hpadding
        self.vpadding = (lambda rect: 0) if vpadding is None else vpadding

    def process_event(self, event):
        Widget.process_event(self, event)
        self.widget.process_event(event)

    def update(self, rect, elapsed_ms):
        Widget.update(self, rect, elapsed_ms)
        self.widget.update(
            rect.inflate(-self.hpadding(rect)*2, -self.vpadding(rect)*2),
            elapsed_ms
        )

    def draw(self, canvas):
        self.widget.draw(canvas)
        Widget.draw(self, canvas)

class NoteBaseWidget(Widget):

    def __init__(self, window, parent, db, overlay, note_id, settings):
        Widget.__init__(self, window, parent)
        self.db = db
        self.overlay = overlay
        self.note_id = note_id
        self.settings = settings

    def is_deleted(self):
        try:
            self.db.get_note_data(self.note_id)
            return False
        except NoteNotFound:
            return True

    def bubble_event(self, event):
        if event.key_down(KEY_EDIT_NOTE):
            self.clear_quick_focus()
            self.post_event(
                USER_EVENT_EXTERNAL_TEXT_ENTRY,
                entry=NoteText(self.db, self.note_id)
            )
        elif event.key_down(KEY_DELETE_NOTE):
            self.clear_quick_focus()
            self.db.delete_note(self.note_id)
        elif event.key_down(KEY_OPEN_LINKS):
            for link in self.db.get_note_data(self.note_id).get("links", []):
                webbrowser.open(link)
        elif event.key_down(KEY_CREATE_NOTE):
            self.clear_quick_focus()
            with self.db.transaction():
                child_note_id = self.db.create_note(text=NEW_NOTE_TEXT)
                self.db.create_link(self.note_id, child_note_id)
            self.post_event(
                USER_EVENT_EXTERNAL_TEXT_ENTRY,
                entry=NoteText(self.db, child_note_id)
            )
        else:
            Widget.bubble_event(self, event)

    def process_event(self, event):
        if event.mouse_motion(rect=self.rect):
            self.overlay.set_link_target(self)
            self.quick_focus()
        if self.has_focus() and event.left_mouse_down(self.rect):
            self.overlay.set_link_source(self)
        elif self.has_focus() and event.left_mouse_up(self.rect):
            self.open_me()
        else:
            Widget.process_event(self, event)

    def update(self, rect, elapsed_ms):
        Widget.update(self, rect, elapsed_ms)
        self.data = self.db.get_note_data(self.note_id)
        self.full_width = self.settings.get_full_width()
        self.full_height = int(
            self.full_width * self.settings.get_height_width_ratio()
        )
        self.card_full_size = (self.full_width, self.full_height)
        self.card_full_rect = pygame.Rect((0, 0), self.card_full_size)

    def draw(self, canvas):
        attributes = {
            "textalign": "left",
            "bg": COLOR_NOTE_BG,
            "italic": False,
        }
        for tag in TAG_ATTRIBUTES:
            if tag["name"] in self.data.get("tags", []):
                for key in list(attributes.keys()):
                    if key in tag:
                        attributes[key] = tag[key]
        border_size = 3
        border = self.rect.copy()
        border.width -= border_size
        border.height -= border_size
        border.x += border_size
        border.y += border_size
        canvas.fill_rect(border, color=(0, 0, 0, 50))
        border.x -= border_size
        border.y -= border_size
        canvas.fill_rect(border, color=attributes["bg"])
        canvas.draw_rect(border, (0, 0, 0, 120), 1)
        canvas.blit(
            canvas.create_image(
                self.card_full_size,
                lambda canvas: self._draw_card(canvas, attributes)
            ),
            self.rect,
            scale_to_fit=self.rect.size
        )
        Widget.draw(self, canvas)

    def get_focus_rect(self):
        border_size = 3
        border = self.rect.copy()
        border.width -= border_size
        border.height -= border_size
        return border.inflate(-7, -7).move(1, 1).inflate(2, 2)

    def _draw_card(self, canvas, attributes):
        border = 8
        status_height = self.full_width/20
        rect = self.card_full_rect
        rect = rect.inflate(-border*4, -border*3-status_height)
        rect.top = border
        if DEBUG_NOTE_BORDER:
            canvas.draw_rect(rect, (200, 50, 50), 1)
        if self.data.get("type", "text") == "code":
            header = rect.copy()
            header.height = status_height
            body = rect.copy()
            body.y += (header.height*1.5)
            body.height -= (header.height*1.5)
            canvas.render_text(
                "{} - {}".format(
                    "/".join(self.data["filepath"]),
                    "/".join(self.data["chunkpath"])
                ),
                header,
                size=self.full_width/12,
                textalign="left",
                boxalign="topright",
                color=COLOR_NOTE_TAG_TEXT,
                face=FONT_MONOSPACE,
                split=False
            )
            canvas.render_text(
                self._code_lines(self.data["fragments"]),
                body,
                size=self.full_width/12,
                textalign="left",
                boxalign="left",
                color=COLOR_NOTE_TEXT,
                face=FONT_MONOSPACE,
                split=False
            )
        else:
            if self.data["text"].startswith("# "):
                lines = self.data["text"].splitlines()
                header_text = lines[0][2:]
                body_text = "\n".join(lines[1:])
                header = rect.copy()
                header.height = int(rect.height*0.2)
                body = rect.copy()
                body.y += (header.height*1.1)
                body.height -= (header.height*1.1)
                canvas.render_text(
                    header_text,
                    header,
                    size=self.full_width/10,
                    textalign="center",
                    boxalign="center",
                    color=COLOR_NOTE_TEXT,
                    face=FONT_TEXT
                )
                canvas.render_text(
                    body_text,
                    body,
                    size=self.full_width/10,
                    textalign=attributes["textalign"],
                    italic=attributes["italic"],
                    boxalign="center",
                    color=COLOR_NOTE_TEXT,
                    face=FONT_TEXT
                )
            else:
                canvas.render_text(
                    self.data["text"],
                    rect,
                    size=self.full_width/10,
                    textalign=attributes["textalign"],
                    italic=attributes["italic"],
                    boxalign="center",
                    color=COLOR_NOTE_TEXT,
                    face=FONT_TEXT
                )
        rect = rect.inflate(border*2, 0)
        rect.height = status_height
        rect.bottom = self.card_full_rect.bottom - border
        if DEBUG_NOTE_BORDER:
            canvas.draw_rect(rect, (200, 50, 50), 1)
        canvas.render_text(
            self.data["timestamp_created"][:10],
            rect,
            size=status_height,
            face=FONT_MONOSPACE,
            boxalign="bottomleft",
            split=False,
            color=COLOR_NOTE_DATE_TEXT
        )
        tags = self.data.get("tags", [])
        links = self.data.get("links", [])
        if tags or links:
            right = rect.right
            rect.width -= (rect.height*1.3) * len(links)
            canvas.render_text(
                " ".join("#{}".format(tag) for tag in self.data["tags"]),
                rect,
                size=status_height,
                face=FONT_MONOSPACE,
                boxalign="bottomright",
                split=False,
                color=COLOR_NOTE_TAG_TEXT
            )
            rect.width = rect.height
            rect.right = right
            for link in links:
                canvas.draw_rect(
                    rect,
                    (50, 150, 50),
                    1
                )
                rect = rect.move(-rect.height*1.3, 0)

    def _code_lines(self, fragments):
        MAX = 15
        lines = []
        for fragment in fragments[:MAX]:
            if fragment["type"] == "chunk":
                lines.append("{}<<{}>>".format(
                    fragment["prefix"],
                    "/".join(fragment["path"])
                ))
            else:
                lines.append("{}".format(
                    fragment["text"],
                ))
        if len(fragments) > MAX:
            lines.append("...")
        return "\n".join(lines)

    def _get_target(self, alotted_rect, align="center"):
        target = self.card_full_rect
        target = target.fit(alotted_rect)
        if align == "left":
            target.midright = alotted_rect.midright
        elif align == "right":
            target.midleft = alotted_rect.midleft
        else:
            target.center = alotted_rect.center
        return target

    def get_link_source_point(self):
        return self.rect.center

    def hit_test(self, pos):
        return self.rect.collidepoint(pos)

class WindowFocusMixin(object):

    def __init__(self):
        self.focused_widget = None
        self.quick_focused_widget = None
        self.saved_focus = None

    def set_focus(self, widget):
        self.focused_widget = widget

    def set_quick_focus(self, widget):
        self.quick_focused_widget = widget

    def clear_quick_focus(self):
        if self.quick_focused_widget is not None:
            self.quick_focused_widget = None
            return True
        else:
            return False

    def is_focused(self, widget):
        if self.quick_focused_widget is None:
            return widget is self.focused_widget
        else:
            return widget is self.quick_focused_widget

    def save_focus(self):
        if self.saved_focus is None:
            self.saved_focus = (self.focused_widget, self.quick_focused_widget)
            self.focused_widget = None
            self.quick_focused_widget = None

    def restore_focus(self):
        if self.saved_focus is not None:
            self.focused_widget, self.quick_focused_widget = self.saved_focus
            self.saved_focus = None

class Box(Widget):

    def __init__(self, window, parent, **kwargs):
        Widget.__init__(self, window, parent, **kwargs)
        self.clear()

    def clear(self):
        self.children = []

    def add(self, child):
        self.children.append(child)
        return child

    def process_event(self, event):
        Widget.process_event(self, event)
        for child in self.visible_children():
            child.process_event(event)

    def update(self, rect, elapsed_ms):
        Widget.update(self, rect, elapsed_ms)
        sizes = []
        divide_indices = []
        for child in self.visible_children():
            if self.get_widget_size(child) == -1:
                divide_indices.append(len(sizes))
                sizes.append(0)
            else:
                sizes.append(self.get_widget_size(child))
        if divide_indices:
            divide_size = int(round((self.get_rect_size(rect) - sum(sizes)) / len(divide_indices)))
            for divide_index in divide_indices:
                sizes[divide_index] = divide_size
        for child, size in zip(self.visible_children(), sizes):
            rect = self.set_rect_size(rect, size)
            child.update(rect, elapsed_ms)
            rect = self.move_rect(rect, size)

    def draw(self, canvas):
        for child in self.visible_children():
            child.draw(canvas)
        Widget.draw(self, canvas)

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
        return widget.get_width()

    def get_rect_size(self, thing):
        return thing.width

    def set_rect_size(self, rect, size):
        rect = rect.copy()
        rect.width = size
        return rect

    def move_rect(self, rect, delta):
        return rect.move(delta, 0)

class TextField(Widget):

    def __init__(self, window, parent, text_changed_callback, text_size=10, **kwargs):
        Widget.__init__(self, window, parent, **kwargs)
        self.text_size = text_size
        self.text = ""
        self.text_changed_callback = text_changed_callback

    def set_text(self, text):
        self.text = text
        self.text_changed_callback(text)

    def process_event(self, event):
        if self.has_focus() and event.key_down_text():
            self.set_text(self.text + event.key_down_text())
        elif event.left_mouse_up(rect=self.get_used_rect()):
            self.focus()
        else:
            Widget.process_event(self, event)

    def draw(self, canvas):
        canvas.fill_rect(
            self.get_used_rect(),
            (250, 250, 250)
        )
        canvas.render_text(
            "{}\u2302".format(self.text),
            self.get_used_rect().inflate(-4, -4),
            face=FONT_MONOSPACE,
            size=self.text_size,
            boxalign="midleft"
        )
        Widget.draw(self, canvas)

    def get_focus_rect(self):
        return self.get_used_rect().inflate(
            self.get_focus_rect_size(),
            self.get_focus_rect_size()
        )

class Immutable(object):

    def __init__(self, data, undo_list_size=20):
        self.data = data
        self.undo_list_size = undo_list_size
        self.undo_list = []
        self.redo_list = []
        self.transaction_count = 0

    @contextlib.contextmanager
    def transaction(self):
        current_data = self.data
        self.transaction_count += 1
        try:
            yield
        except:
            self.data = current_data
            raise
        finally:
            self.transaction_count -= 1
            if self.transaction_count == 0 and self.data is not current_data:
                self.undo_list.append(current_data)
                self.undo_list = self.undo_list[-self.undo_list_size:]
                self.redo_list.clear()
                self._data_changed()

    def undo(self):
        if self.transaction_count == 0 and self.undo_list:
            self.redo_list.insert(0, self.data)
            self.data = self.undo_list.pop(-1)
            self._data_changed()

    def redo(self):
        if self.transaction_count == 0 and self.redo_list:
            self.undo_list.append(self.data)
            self.data = self.redo_list.pop(0)
            self._data_changed()

    def _get(self, *path):
        data = self.data
        for part in path:
            data = data[part]
        return data

    def _set(self, data):
        with self.transaction():
            self.data = data

    def _data_changed(self):
        pass

class ExternalTextEntry(object):

    def __init__(self, text, editor_command):
        self.text = text
        self.f = tempfile.NamedTemporaryFile(suffix="-smartnotes-external-")
        self.f.write(self.text.encode("utf-8"))
        self.f.flush()
        self.p = subprocess.Popen([
            self.f.name if part is None else part
            for part
            in editor_command
        ])

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

class SmartNotesWidget(VBox):

    def __init__(self, window):
        VBox.__init__(self, window, None)
        if len(sys.argv) < 2:
            sys.exit("Usage: smartnotes.py <file>")
        else:
            path = sys.argv[1]
        self.note_settings = NoteSettings()
        self.set_title(format_title("Smart Notes", path))
        self.toggle_table_network_after_event_processing = False
        self.db = NoteDb(path)
        self.overlay = self.instantiate(OverlayWidget, self.db)
        self.note_browser = self.instantiate(NoteBrowserWidget,
            self.db,
            self.overlay,
            self.note_settings
        )
        self.search_bar = self.add(self.instantiate(SearchBar,
            self.db,
            self.overlay,
            self.note_settings,
            open_callback=self._on_search_note_open,
            dismiss_callback=self._on_search_dismiss
        ))
        self.add(self.note_browser)
        self.debug_bar = self.add(self.instantiate(DebugBar))
        self.note_browser.focus()

    def bubble_event(self, event):
        if event.key_down(KEY_TOGGLE_TABLE_NETWORK):
            self.toggle_table_network()
        elif event.key_down(KEY_OPEN_SEARCH):
            self.clear_quick_focus()
            self.search_bar.start_search()
        else:
            VBox.bubble_event(self, event)

    def toggle_table_network(self):
        self.toggle_table_network_after_event_processing = True

    def process_event(self, event):
        try:
            self.overlay.process_event(event)
        except OverlayAbort:
            pass
        else:
            if event.mouse_motion():
                self.overlay.set_link_target(None)
                self.clear_quick_focus()
            if event.key_down(KEY_QUIT):
                self.quit()
            elif event.key_down(KEY_UNDO):
                self.db.undo()
            elif event.key_down(KEY_REDO):
                self.db.redo()
            elif event.key_down(KEY_TOGGLE_DEBUG_BAR):
                self.debug_bar.toggle()
            elif event.key_down(KEY_CLEAR_FOCUS) and self.clear_quick_focus():
                pass
            elif event.window_gained_focus():
                self.restore_focus()
            elif event.window_lost_focus():
                self.save_focus()
            else:
                VBox.process_event(self, event)

    def _on_search_note_open(self, note_id):
        self.note_browser.open_note(note_id)

    def _on_search_dismiss(self, close):
        if close:
            self.search_bar.hide()
        self.note_browser.focus()

    def update(self, rect, elapsed_ms):
        self.overlay.update(rect, elapsed_ms)
        VBox.update(self, rect, elapsed_ms)
        self.rect = rect

    def draw(self, canvas):
        canvas.fill_rect(self.rect, color=COLOR_BACKGROUND)
        VBox.draw(self, canvas)
        self.overlay.draw(canvas)

class SearchBar(VBox):

    SEARCH_FIELD_HEIHGT = 50
    VPADDING = 8

    def __init__(self, window, parent, db, overlay, note_settings, open_callback, dismiss_callback):
        VBox.__init__(self, window, parent, height=0, visible=True)
        self.db = db
        self.open_callback = open_callback
        self.dismiss_callback = dismiss_callback
        self.animation = Animation()
        self.notes = []
        self.search_results = self.instantiate(SearchResults,
            db, overlay, note_settings, open_callback,
            hpadding=self.VPADDING
        )
        self.search_field = self.instantiate(SearchField,
            self.search_results,
            self.dismiss_callback,
            text_size=20
        )
        self.add(self.instantiate(Padding,
            self.search_field,
            hpadding=lambda rect: int(rect.width*0.08),
            vpadding=lambda rect: self.VPADDING,
            height=self.SEARCH_FIELD_HEIHGT
        ))
        self.add(self.search_results)
        self.add(self.instantiate(Widget, height=self.VPADDING))
        self.ideal_height = 200

    def focus(self):
        self.search_field.focus()

    def is_visible(self):
        return Widget.is_visible(self) or self.animation.active()

    def start_search(self):
        if not Widget.is_visible(self):
            self.toggle_visible()
            self.animation.reverse(200)
        self.focus()

    def hide(self):
        if Widget.is_visible(self):
            self.toggle_visible()
            self.animation.reverse(200)

    def update(self, rect, elapsed_ms):
        self.ideal_rect = rect.copy()
        self.ideal_rect.height = self.ideal_height
        VBox.update(self, self.ideal_rect, elapsed_ms)
        self.ideal_height = self.SEARCH_FIELD_HEIHGT + self.VPADDING + self.search_results.wanted_height
        percent = self.animation.advance(elapsed_ms)
        self.update_height = self.get_height()
        if Widget.is_visible(self):
            self.alpha = int(255 * percent)
            self.resize(height=int(self.ideal_height * percent))
        else:
            self.alpha = 255 - int(255 * percent)
            self.resize(height=self.ideal_height - int(self.ideal_height * percent))

    def draw(self, canvas):
        canvas.blit(
            canvas.create_image(self.ideal_rect.size, self._draw_search_bar_image),
            (0, -self.ideal_height+self.update_height),
            alpha=self.alpha
        )

    def _draw_search_bar_image(self, canvas):
        canvas.fill_rect(
            pygame.Rect(0, 0, self.ideal_rect.width, self.ideal_rect.height),
            color=COLOR_SEARCH_BAR
        )
        VBox.draw(self, canvas)

class SearchField(TextField):

    def __init__(self, window, parent, search_results, dismiss_callback, **kwargs):
        TextField.__init__(self, window, parent, search_results.update_search_text, **kwargs)
        self.search_results = search_results
        self.dismiss_callback = dismiss_callback

    def process_event(self, event):
        if self.has_focus() and self.process_event_when_in_focus(event):
            return
        TextField.process_event(self, event)

    def process_event_when_in_focus(self, event):
        if event.key_down("ctrl+w"):
            self.set_text(strip_last_word(self.text))
        elif event.key_down("backspace"):
            self.set_text(self.text[:-1])
        elif event.key_down(KEY_DISMISS):
            self.dismiss_callback(close=True)
        elif event.key_down(KEY_INCREASE):
            self.search_results.inc_results()
        elif event.key_down(KEY_DECREASE):
            self.search_results.dec_results()
        elif event.key_down(KEY_CLEAR_FOCUS):
            self.dismiss_callback(close=False)
        else:
            return False
        return True

class SearchResults(HBox):

    def __init__(self, window, parent, db, overlay, note_settings, open_callback, hpadding):
        HBox.__init__(self, window, parent)
        self.db = db
        self.overlay = overlay
        self.note_settings = note_settings
        self.open_callback = open_callback
        self.hpadding = hpadding
        self.update_search_text("")
        self.set_num_results(NUM_SEARCH_RESULTS)
        self.by_id = {}

    def inc_results(self):
        self.set_num_results(self.num_results + 1)

    def dec_results(self):
        self.set_num_results(self.num_results - 1)

    def set_num_results(self, num):
        self.num_results = max(3, num)

    def update_search_text(self, text):
        self.text = text

    def update(self, rect, elapsed_ms):
        self.wanted_height = int(round(
            (rect.width-self.hpadding) / self.num_results
            *
            self.note_settings.get_height_width_ratio()
        ))
        self._update_notes_list()
        HBox.update(self, rect, elapsed_ms)

    def _update_notes_list(self):
        by_id = {}
        self.clear()
        self.add(self.instantiate(Widget, width=self.hpadding/2))
        for note_id, note_data in self.db.get_notes(self.text)[:self.num_results]:
            if note_id in self.by_id:
                note = self.add(self.by_id[note_id])
            else:
                note = self.add(self.instantiate(Padding,
                    self.instantiate(SearchNote,
                        self.db,
                        self.overlay,
                        self.note_settings,
                        note_id,
                        self.open_callback
                    ),
                    hpadding=lambda rect: self.hpadding/2
                ))
            by_id[note_id] = note
        while len(self.children) <= self.num_results:
            self.add(self.instantiate(Widget))
        self.add(self.instantiate(Widget, width=self.hpadding/2))
        self.by_id = by_id

class SearchNote(NoteBaseWidget):

    def __init__(self, window, parent, db, overlay, settings, note_id, open_callback):
        NoteBaseWidget.__init__(self, window, parent, db, overlay, note_id, settings)
        self.overlay = overlay
        self.open_callback = open_callback

    def open_me(self):
        self.open_callback(self.note_id)

    def update(self, rect, elapsed_ms):
        NoteBaseWidget.update(self, rect, elapsed_ms)
        self.rect = self._get_target(rect, align="center")

class NoteBrowserWidget(VBox):

    def __init__(self, window, parent, db, overlay, note_settings):
        VBox.__init__(self, window, parent)
        self.db = db
        self.note_settings = note_settings
        self.pos = (0, 0)
        self.note_id = None
        self.network = self.add(self.instantiate(NetworkWidget,
            self.db,
            overlay,
            self.note_settings
        ))
        self.table = self.add(self.instantiate(TableWidget,
            self.db,
            overlay,
            self.note_settings
        ))
        self.table.toggle_visible()
        self.toggle_table_network_after_event_processing = False

    def register_note_opened(self, note_id):
        self.note_id = note_id

    def open_note(self, note_id):
        if self.network.is_visible():
            self.network.open_note(note_id)
        else:
            self.table.open_note(note_id)

    def focus(self):
        if self.table.is_visible():
            self.table.focus()
        else:
            self.network.focus()

    def process_event(self, event):
        if event.mouse_motion():
            self.pos = event.mouse_pos()
        VBox.process_event(self, event)
        if self.toggle_table_network_after_event_processing:
            self.network.toggle_visible()
            self.table.toggle_visible()
            if self.network.is_visible():
                self.network.focus()
            else:
                self.table.focus()
            self.open_note(self.note_id)
            self.clear_quick_focus()
            self.toggle_table_network_after_event_processing = False

    def update(self, rect, elapsed_ms):
        self.note_settings.set_full_width(int(rect.width * 0.3))
        VBox.update(self, rect, elapsed_ms)

    def bubble_event(self, event):
        if event.key_down(KEY_TOGGLE_TABLE_NETWORK):
            self.toggle_table_network()
        else:
            VBox.bubble_event(self, event)

    def toggle_table_network(self):
        self.toggle_table_network_after_event_processing = True

class NetworkWidget(Widget):

    def __init__(self, window, parent, db, overlay, note_settings):
        Widget.__init__(self, window, parent)
        self.navigation_history = parent
        self.db = db
        self.overlay = overlay
        self.note_settings = note_settings
        self.pos = (-1, -1)
        self.notes = []
        self.links = []
        self.open_last_note()

    def open_last_note(self):
        self.root_note = None
        for note_id, note_data in self.db.get_notes():
            self.open_note(note_id)
            break

    def process_event(self, event):
        if event.mouse_motion():
            self.pos = event.mouse_pos()
        if event.left_mouse_up(rect=self.rect):
            self.focus()
        if event.key_down(KEY_CREATE_NOTE) and self.has_focus():
            note_id = self.db.create_note(text=NEW_NOTE_TEXT)
            self.open_note(note_id)
            self.post_event(
                USER_EVENT_EXTERNAL_TEXT_ENTRY,
                entry=NoteText(self.db, note_id)
            )
        else:
            Widget.process_event(self, event)
            for note in self.notes:
                note.process_event(event)
            for link in self.links:
                link.process_event(event)

    def open_note(self, note_id):
        if self.root_note is None or self.root_note.note_id != note_id:
            self.make_root(self.instantiate(
                NetworkNote,
                self,
                self.db,
                self.overlay,
                note_id,
                self.note_settings
            ))

    def make_root(self, note):
        if note is not self.root_note:
            self.root_note = note
            self.clear_quick_focus()
            self.navigation_history.register_note_opened(note.note_id)

    def update(self, rect, elapsed_ms):
        Widget.update(self, rect, elapsed_ms)
        self.rect = rect
        self.stripe_rects = []
        padding = 8
        self.old_notes = self.notes
        self.notes = []
        self.links = []
        middle_stripe = self._stripe(rect, 0.3)
        if self.root_note and self.root_note.is_deleted():
            self.open_last_note()
        if self.root_note is None:
            return
        self.root_note.update(
            middle_stripe,
            elapsed_ms,
            "center",
            None
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
        for note in self.notes:
            note.clear_hidden_links(self.links)

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
                    direction,
                    note.get_center() if linked not in self.old_notes else None
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

    def draw(self, canvas):
        if DEBUG_NOTE_BORDER:
            for rect in self.stripe_rects:
                canvas.draw_rect(rect, (255, 255, 0), 2)
        for link in self.links:
            link.draw(canvas)
        for note in self.notes:
            note.draw(canvas)
        Widget.draw(self, canvas)

class NetworkNote(NoteBaseWidget):

    def __init__(self, window, parent, network, db, overlay, note_id, settings):
        NoteBaseWidget.__init__(self, window, parent, db, overlay, note_id, settings)
        self.overlay = overlay
        self.network = network
        self.incoming = []
        self.outgoing = []
        self.animation = Animation()
        self.rect = None
        self.target = None
        self.previous = None

    def clear_hidden_links(self, visible_links):
        self.incoming = [x for x in self.incoming if x in visible_links]
        self.outgoing = [x for x in self.outgoing if x in visible_links]

    def open_me(self):
        self.network.make_root(self)

    def process_event(self, event):
        if self.has_focus() and event.key_down(KEY_UNLINK_NOTE):
            link_id = self.get_link_id()
            if link_id:
                self.db.delete_link(link_id)
                self.clear_quick_focus()
        elif self.has_focus() and (event.key_down(KEY_MOVE_UP) or
                                   event.key_down(KEY_MOVE_DOWN)):
            link_id = self.get_link_id()
            if link_id:
                if self.side == "left":
                    end = "to"
                else:
                    end = "from"
                if event.key_down(KEY_MOVE_UP):
                    self.db.move_link_up(link_id, end=end)
                else:
                    self.db.move_link_down(link_id, end=end)
        else:
            NoteBaseWidget.process_event(self, event)

    def update_incoming(self):
        by_id = {
            link.link_id: link
            for link in self.incoming
        }
        self.incoming = []
        for link_id, link_data in self.db.get_incoming_links(self.note_id):
            if link_id in by_id:
                self.incoming.append(by_id.pop(link_id).with_side("left"))
            else:
                self.instantiate(LinkWidget,
                    self.db,
                    link_id,
                    link_data,
                    self.instantiate(
                        NetworkNote,
                        self.network,
                        self.db,
                        self.overlay,
                        link_data["from"],
                        self.settings
                    ),
                    self,
                    side="left"
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
                self.outgoing.append(by_id.pop(link_id).with_side("right"))
            else:
                self.instantiate(LinkWidget,
                    self.db,
                    link_id,
                    link_data,
                    self,
                    self.instantiate(
                        NetworkNote,
                        self.network,
                        self.db,
                        self.overlay,
                        link_data["to"],
                        self.settings
                    ),
                    side="right"
                )
        return self.outgoing

    def get_link_id(self):
        if self.side == "left" and len(self.outgoing) == 1 and not self.outgoing[0].is_virtual():
            return self.outgoing[0].link_id
        if self.side == "right" and len(self.incoming) == 1 and not self.incoming[0].is_virtual():
            return self.incoming[0].link_id

    def get_center(self):
        return self.rect.center

    def get_link_in_point(self):
        return self.rect.midleft

    def get_link_out_point(self):
        return self.rect.midright

    def update(self, rect, elapsed_ms, side, center_position):
        NoteBaseWidget.update(self, rect, elapsed_ms)
        self.side = side
        self.true_rect = rect
        target = self._get_target(rect, side)
        if center_position:
            x = target.copy()
            x.center = center_position
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

    def draw(self, canvas):
        NoteBaseWidget.draw(self, canvas)
        if DEBUG_NOTE_BORDER:
            canvas.draw_rect(self.true_rect, (255, 0, 0), 1)

class LinkWidget(Widget):

    def __init__(self, window, parent, db, link_id, link_data, start, end, side):
        Widget.__init__(self, window, parent)
        self.db = db
        self.link_id = link_id
        self.link_data = link_data
        self.start = start
        self.end = end
        self.start.outgoing.append(self)
        self.end.incoming.append(self)
        self.start_pos = None
        self.end_pos = None
        self.with_side(side)

    def with_side(self, side):
        self.side = side
        return self

    def is_virtual(self):
        return self.link_data.get("virtual", False)

    def process_event(self, event):
        if event.mouse_motion(rect=self.allotted_rect):
            self.quick_focus()
        if event.key_down(KEY_EDIT_NOTE) and self.has_focus():
            self.post_event(
                USER_EVENT_EXTERNAL_TEXT_ENTRY,
                entry=LinkText(self.db, self.link_id)
            )
        else:
            Widget.process_event(self, event)

    def update(self, rect, elapsed_ms):
        Widget.update(self, rect, elapsed_ms)
        start = pygame.math.Vector2(self.start.get_link_out_point())
        end = pygame.math.Vector2(self.end.get_link_in_point())
        if start != self.start_pos or end != self.end_pos:
            self.start_pos = start
            self.end_pos = end
            self.padding = 3
            self.need_redraw = True
        else:
            self.need_redraw = False

    def draw(self, canvas):
        if self.start_pos.x > self.end_pos.x:
            return
        if self.need_redraw:
            self.width = max(1, int(abs(self.start_pos.x-self.end_pos.x)))
            self.height = max(1, int(abs(self.start_pos.y-self.end_pos.y)))+2*self.padding
            self.image = canvas.create_image(
                (self.width, self.height),
                self._draw_line
            )
            self.pos = (
                min(self.start_pos.x, self.end_pos.x),
                min(self.start_pos.y, self.end_pos.y)-self.padding,
            )
        canvas.blit(self.image, self.pos)
        link_text = self.link_data.get("text", "")
        draw_label = False
        if self.side == "left":
            height = self.start.rect.height / 2
            if self.start_pos.y < self.end_pos.y:
                y_offset = -height
                boxalign = "bottomleft"
            else:
                y_offset = 0
                boxalign = "topleft"
            x, y = self.start_pos
            text_rect = pygame.Rect(x, y+y_offset, self.end_pos.x-x, height)
        else:
            height = self.end.rect.height / 2
            if self.end_pos.y < self.start_pos.y:
                y_offset = -height
                boxalign = "bottomright"
            else:
                y_offset = 0
                boxalign = "topright"
            x, y = self.end_pos
            text_rect = pygame.Rect(self.start_pos.x, y+y_offset, x-self.start_pos.x, height)
        if y_offset != 0:
            center_offset = height/2
        else:
            center_offset = -height/2
        self.allotted_rect = text_rect.move(0, center_offset)
        text_rect = text_rect.inflate(-5, -5)
        if link_text:
            canvas.render_text(
                link_text,
                text_rect,
                boxalign=boxalign,
                textalign=self.side,
                face=FONT_MONOSPACE,
                italic=True,
                size=20
            )
        Widget.draw(self, canvas)

    def _draw_line(self, canvas):
        if self.start_pos.x < self.end_pos.x:
            startx = 0
            endx = self.width
            c1x = 0.6*self.width
            c2x = 0.4*self.width
        else:
            startx = self.width
            endx = 0
            c1x = 0.4*self.width
            c2x = 0.6*self.width
        if self.start_pos.y < self.end_pos.y:
            starty = self.padding
            endy = self.height-self.padding
            c1y = 0.0*(self.height-self.padding)+self.padding
            c2y = 1.0*(self.height-self.padding)+self.padding
        else:
            starty = self.height-self.padding
            endy = self.padding
            c1y = 1.0*(self.height-self.padding)+self.padding
            c2y = 0.0*(self.height-self.padding)+self.padding
        canvas.move_to(startx, starty)
        canvas.line_to(startx+0.02*(endx-startx), starty)
        canvas.curve_to(c1x, c1y, c2x, c2y, endx-0.02*(endx-startx), endy)
        canvas.line_to(endx, endy)
        canvas._set_color(COLOR_VIRTUAL_LINE if self.is_virtual() else COLOR_LINE)
        canvas.set_line_width(1.5)
        canvas.stroke()

class TableWidget(Widget):

    def __init__(self, window, parent, db, overlay, note_settings):
        Widget.__init__(self, window, parent)
        self.db = db
        self.overlay = overlay
        self.note_settings = note_settings
        self.notes = []
        self.by_id = {}

    def process_event(self, event):
        for note in self.notes:
            note.process_event(event)
        Widget.process_event(self, event)

    def open_note(self, note_id):
        self.note_id = note_id

    def update(self, rect, elapsed_ms):
        self._update_notes_list()
        self._layout(rect, elapsed_ms)
        Widget.update(self, rect, elapsed_ms)

    def draw(self, canvas):
        for note in self.notes:
            note.draw(canvas)
        Widget.draw(self, canvas)

    def _update_notes_list(self):
        by_id = {}
        self.notes.clear()
        for note_id in self.db.get_children(self.note_id):
            if note_id in self.by_id:
                note = self.by_id[note_id]
            else:
                note = self.instantiate(
                    TableNote,
                    self.db,
                    self.overlay,
                    self.note_settings,
                    note_id,
                    self.open_note
                )
            self.notes.append(note)
            by_id[note_id] = note
        self.by_id = by_id

    def _layout(self, rect, elapsed_ms):
        if not self.notes:
            return
        rows = 1
        ratio = None
        fit_box = None
        notes_per_row = None
        while True:
            new_notes_per_row = math.ceil(len(self.notes) / rows)
            ideal_box = pygame.Rect(
                0,
                0,
                self.note_settings.get_full_width() * new_notes_per_row,
                self.note_settings.get_full_width() * self.note_settings.get_height_width_ratio() * rows
            )
            new_fit_box = ideal_box.fit(rect)
            new_ratio = new_fit_box.width / ideal_box.width
            if new_ratio > 1:
                new_fit_box = ideal_box
                new_ratio = 1
            new_fit_box.center = rect.center
            if ratio is None or new_ratio > ratio:
                ratio = new_ratio
                fit_box = new_fit_box
                notes_per_row = new_notes_per_row
                rows += 1
            else:
                break
        w = self.note_settings.get_full_width() * ratio
        h = self.note_settings.get_full_width() * self.note_settings.get_height_width_ratio() * ratio
        row = 0
        col = 0
        for note in self.notes:
            if col == notes_per_row:
                col = 0
                row += 1
            note.update(
                pygame.Rect(
                    fit_box.x+w*col,
                    fit_box.y+h*row,
                    w,
                    h
                ),
                elapsed_ms
            )
            col += 1

class TableNote(NoteBaseWidget):

    def __init__(self, window, parent, db, overlay, settings, note_id, open_callback):
        NoteBaseWidget.__init__(self, window, parent, db, overlay, note_id, settings)
        self.overlay = overlay
        self.open_callback = open_callback

    def open_me(self):
        self.open_callback(self.note_id)

    def update(self, rect, elapsed_ms):
        NoteBaseWidget.update(self, rect, elapsed_ms)
        self.rect = self._get_target(rect, align="center")

class DebugBar(Widget):

    IDEAL_HEIGHT = 50

    def __init__(self, window, parent):
        Widget.__init__(self, window, parent, height=self.IDEAL_HEIGHT, visible=DEBUG)
        self.animation = Animation()
        self.average_elapsed = 0
        self.tot_elapsed_time = 0
        self.frame_count = 0
        self.fps = 0

    def is_visible(self):
        return Widget.is_visible(self) or self.animation.active()

    def toggle(self):
        self.toggle_visible()
        self.animation.reverse(200)

    def update(self, rect, elapsed_ms):
        Widget.update(self, rect, elapsed_ms)
        self.tot_elapsed_time += elapsed_ms
        self.frame_count += 1
        if self.tot_elapsed_time > 1000:
            self.average_elapsed = int(round(self.tot_elapsed_time / self.frame_count))
            self.fps = self.frame_count
            self.frame_count = 0
            self.tot_elapsed_time -= 1000
        percent = self.animation.advance(elapsed_ms)
        if Widget.is_visible(self):
            self.alpha = int(255 * percent)
            self.resize(height=int(self.IDEAL_HEIGHT * percent))
        else:
            self.alpha = 255 - int(255 * percent)
            self.resize(height=self.IDEAL_HEIGHT - int(self.IDEAL_HEIGHT * percent))
        self.rect = rect

    def draw(self, canvas):
        canvas.blit(
            canvas.create_image((self.rect.width, self.IDEAL_HEIGHT), self._draw_bar),
            self.rect,
            alpha=self.alpha
        )
        Widget.draw(self, canvas)

    def _draw_bar(self, canvas):
        rect = pygame.Rect((0, 0), (self.rect.width, self.IDEAL_HEIGHT))
        canvas.fill_rect(rect, color=(84, 106, 134))
        canvas.render_text(
            f"elapsed_ms = {self.average_elapsed} | fps = {self.fps}",
            rect.inflate(-20, -20),
            boxalign="midleft",
            size=15,
            face="Monospace"
        )

class OverlayWidget(VBox):

    def __init__(self, window, parent, db):
        VBox.__init__(self, window, parent)
        self.db = db
        self.link_source = None
        self.link_target = None
        self.pos = (0, 0)

    def process_event(self, event):
        if event.mouse_motion():
            self.pos = event.mouse_pos()
        if self.link_source and event.left_mouse_up():
            if self.link_target:
                self.db.create_link(
                    self.link_source.note_id,
                    self.link_target.note_id
                )
                self.set_link_source(None)
                self.set_link_target(None)
                raise OverlayAbort()
            self.set_link_source(None)
            self.set_link_target(None)
        VBox.process_event(self, event)

    def draw(self, canvas):
        VBox.draw(self, canvas)
        if self.link_source and not self.link_source.hit_test(self.pos):
            canvas.move_to(*self.link_source.get_link_source_point())
            canvas.line_to(*self.pos)
            if self.link_target:
                canvas._set_color(COLOR_ACTIVE)
            else:
                canvas._set_color(COLOR_INACTIVE)
            canvas.set_line_width(5)
            canvas.stroke()

    def set_link_source(self, link_source):
        self.link_source = link_source

    def set_link_target(self, link_target):
        if link_target is None:
            self.link_target = None
            return
        if self.link_source is None:
            return
        if self.link_source.note_id == link_target.note_id:
            return
        self.link_target = link_target

class OverlayAbort(ValueError):
    pass

class NoteSettings:

    def __init__(self, **kwargs):
        self.set_full_width(kwargs.get("full_width", 200))

    def get_full_width(self):
        return max(100, self.full_width)

    def set_full_width(self, full_width):
        self.full_width = full_width

    def get_height_width_ratio(self):
        return 3/5

class NoteDb(Immutable):

    def __init__(self, path):
        Immutable.__init__(self, read_json_file(path, {
            "version": 1,
            "notes": {},
            "links": {},
        }))
        self.path = path
        self.virtual_links = {}
        self.consolidate_files()
        self._create_virtual_links()

    def write_files(self):
        parts = self.collect_parts()
        for (file, chunk) in parts.keys():
            if file != tuple() and chunk == tuple():
                with open(os.path.join(*file), "w") as f:
                    f.write(self.collect(file, chunk, parts))

    def consolidate_files(self):
        with self.transaction():
            parts = self.collect_parts()
            notes = set()
            for (file, chunk) in parts.keys():
                if file != tuple() and chunk == tuple():
                    notes.update(self.consolidate(os.path.join(*file), file, chunk, parts))
            if notes:
                parts = self.collect_parts()
                report = [
                    "Consolidation report:",
                    "",
                ]
                for (file, chunk) in parts.keys():
                    if file != tuple() and chunk == tuple():
                        path = os.path.join(*file)
                        with open(path) as f:
                            file_on_disk = f.read()
                        file_in_memory = self.collect(file, chunk, parts)
                        if file_on_disk != file_in_memory:
                            report.append(f"  FAIL: {path}")
                            with open(f"{path}.orig", "w") as f:
                                f.write(file_on_disk)
                        else:
                            report.append(f"  OK:   {path}")
                report_id = self.create_note(**{
                    "type": "code",
                    "text": "<code>",
                    "filepath": [],
                    "chunkpath": [],
                    "fragments": [{"type": "line", "text": x} for x in report]
                })
                for affected_note in notes:
                    self.create_link(report_id, affected_note)

    def collect_parts(self):
        parts = defaultdict(list)
        for note_id, note in reversed(self.get_notes()):
            if note.get("type", None) == "code":
                key = (tuple(note["filepath"]), tuple(note["chunkpath"]))
                parts[key].append((note_id, note["fragments"]))
        return parts

    def consolidate(self, path, file, chunk, parts):
        if not os.path.exists(path):
            return set()
        old_lines = []
        self.collect_lines(old_lines, file, chunk, parts)
        with open(path) as f:
            new_lines = f.read().splitlines()
        sm = difflib.SequenceMatcher(a=[x[1] for x in old_lines], b=new_lines)
        note_actions = defaultdict(list)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "replace":
                first = None
                for tag, line in old_lines[i1:i2]:
                    if tag is not None:
                        note_id, prefix, fragment_index = tag
                        if first is None:
                            first = tag
                        note_actions[note_id].append(('remove', fragment_index))
                if first:
                    note_actions[first[0]].append((
                        'extend',
                        first[2],
                        [self.strip_prefix(first[1], x) for x in new_lines[j1:j2]]
                    ))
            elif tag == "delete":
                for tag, line in old_lines[i1:i2]:
                    if tag is not None:
                        note_id, prefix, fragment_index = tag
                        note_actions[note_id].append(('remove', fragment_index))
            elif tag == "insert":
                def indices(index, items):
                    index_up = index - 1
                    index_down = index
                    while index_up >= 0 or index_down < len(items):
                        if index_up >= 0:
                            yield (index_up, 1)
                            index_up -= 1
                        if index_down < len(items):
                            yield (index_down, 0)
                            index_down += 1
                    raise ValueError("ran out of indices to try")
                for index, offset in indices(i1, old_lines):
                    tag, line = old_lines[index]
                    if tag:
                        note_id, prefix, fragment_index = tag
                        note_actions[note_id].append((
                            'extend',
                            fragment_index+offset,
                            [self.strip_prefix(prefix, x) for x in new_lines[j1:j2]]
                        ))
                        break
            elif tag == "equal":
                # Nothing to do
                pass
            else:
                raise ValueError(f"Unknown op_code tag {tag}")
        notes = set()
        for note_id, actions in note_actions.items():
            note = self.get_note_data(note_id)
            self.update_note(
                note_id,
                fragments=self.consolidate_fragments(note["fragments"], actions)
            )
            notes.add(note_id)
        return notes

    def strip_prefix(self, prefix, line):
        if line.startswith(prefix):
            return line[len(prefix):]
        else:
            return line

    def consolidate_fragments(self, fragments, actions):
        removes = set()
        extends = {}
        for action in actions:
            if action[0] == 'remove':
                removes.add(action[1])
            elif action[0] == 'extend':
                extends[action[1]] = action[2]
            else:
                raise ValueError(f"Unknown action {action}")
        new_fragments = []
        for index, fragment in enumerate(fragments):
            if index in extends:
                for line in extends[index]:
                    new_fragments.append({"type": "line", "text": line})
            if index not in removes:
                new_fragments.append(fragment)
        if (index+1) in extends:
            for line in extends[index+1]:
                new_fragments.append({"type": "line", "text": line})
        return new_fragments

    def collect(self, file, chunk, parts):
        lines = []
        self.collect_lines(lines, file, chunk, parts)
        return "\n".join(line[1] for line in lines) + "\n"

    def collect_lines(self, lines, file, chunk, parts, prefix="", blank_lines_before=0):
        for index, (note_id, fragments) in enumerate(parts.get((file, chunk), [])):
            if index > 0:
                for foo in range(blank_lines_before):
                    lines.append((None, ""))
            for fragment_index, fragment in enumerate(fragments):
                if fragment["type"] == "line":
                    if fragment["text"]:
                        lines.append(((note_id, prefix, fragment_index), prefix+fragment["text"]))
                    else:
                        lines.append(((note_id, prefix, fragment_index), ""))
                elif fragment["type"] == "chunk":
                    self.collect_lines(
                        lines,
                        file,
                        tuple(list(chunk)+fragment["path"]),
                        parts,
                        prefix=prefix+fragment["prefix"],
                        blank_lines_before=fragment["blank_lines_before"],
                    )
                else:
                    raise ValueError(f"Unknown code fragment type {fragment['type']}")

    def get_notes(self, expression=""):
        def match(item):
            if item.get("type", "text") == "code":
                lower_text = "".join(
                    fragment.get("text", "") for fragment in item["fragments"]
                ).lower()
            else:
                lower_text = item["text"].lower()
            for part in expression.split(" "):
                if part.startswith("#"):
                    tagpart = part[1:]
                    for tag in item.get("tags", []):
                        if tagpart in tag:
                            break
                    else:
                        return False
                else:
                    if part.lower() not in lower_text:
                        return False
            return True
        return sorted(
            (
                item
                for item in self._get("notes").items()
                if match(item[1])
            ),
            key=lambda item: item[1]["timestamp_created"],
            reverse=True
        )

    def get_note_data(self, note_id):
        self._ensure_note_id(note_id)
        return self._get("notes", note_id)

    def get_link_data(self, link_id):
        self._ensure_link_id(link_id)
        return self._get("links", link_id)

    def update_link(self, link_id, **params):
        self._ensure_link_id(link_id)
        self._replace(links=dict(
            self._get("links"),
            **{link_id: dict(self._get("links", link_id), **params)}
        ))
    def get_children(self, note_id):
        for link_id, link in self.get_outgoing_links(note_id):
            yield link["to"]

    def _create_virtual_links(self):
        self.virtual_links = {}
        code_notes = []
        parts = defaultdict(list)
        for note_id, note in reversed(self.get_notes()):
            if note.get("type", None) == "code":
                key = (tuple(note["filepath"]), tuple(note["chunkpath"]))
                parts[key].append((note_id, note["fragments"]))
                code_notes.append((note_id, note))
        for note_id, note in code_notes:
            for fragment in note["fragments"]:
                if fragment["type"] == "chunk":
                    for (child_note_id, _) in parts[(
                        tuple(note["filepath"]),
                        tuple(note["chunkpath"]+fragment["path"])
                    )]:
                        self.virtual_links[genid()] = {
                            "from": note_id,
                            "to": child_note_id,
                            "timestamp_created": utcnow_timestamp_string(),
                            "virtual": True,
                        }

    def get_outgoing_links(self, note_id):
        return self._sort_links([
            (link_id, link)
            for link_id, link in self._links()
            if link["from"] == note_id
        ], sort_keys=["sort_index_in_from", "timestamp_created"])

    def get_incoming_links(self, note_id):
        return self._sort_links([
            (link_id, link)
            for link_id, link in self._links()
            if link["to"] == note_id
        ], sort_keys=["sort_index_in_to", "timestamp_created"])

    def _links(self):
        yield from self._get("links").items()
        yield from self.virtual_links.items()

    def _sort_links(self, links, sort_keys):
        links_by_sort_key = {}
        for link_id, link in links:
            for sort_key in sort_keys:
                if sort_key in link:
                    if sort_key not in links_by_sort_key:
                        links_by_sort_key[sort_key] = []
                    links_by_sort_key[sort_key].append((link_id, link))
                    break
            else:
                raise ValueError(f"None of the sort keys {sort_keys!r} found in link {link_id}: {link!r}.")
        sorted_combined = []
        for sort_key in sort_keys:
            sorted_combined.extend(sorted(
                links_by_sort_key.get(sort_key, []),
                key=lambda item: item[1][sort_key]
            ))
        return sorted_combined

    def create_note(self, **params):
        note_id = genid()
        self._replace(notes=dict(
            self._get("notes"),
            **{note_id: dict(params, timestamp_created=utcnow_timestamp_string())}
        ))
        return note_id

    def update_note(self, note_id, **params):
        self._ensure_note_id(note_id)
        self._replace(notes=dict(
            self._get("notes"),
            **{note_id: dict(self._get("notes", note_id), **params)}
        ))

    def delete_note(self, note_id):
        self._ensure_note_id(note_id)
        new_notes = dict(self._get("notes"))
        new_notes.pop(note_id)
        new_links = dict(self._get("links"))
        dead_links = []
        for link_id, link in new_links.items():
            if link["to"] == note_id or link["from"] == note_id:
                dead_links.append(link_id)
        for link_id in dead_links:
            new_links.pop(link_id)
        self._replace(notes=new_notes, links=new_links)

    def create_link(self, from_id, to_id):
        link_id = genid()
        self._replace(links=dict(
            self._get("links"),
            **{link_id: {
                "from": from_id,
                "to": to_id,
                "timestamp_created": utcnow_timestamp_string(),
            }}
        ))
        return link_id

    def delete_link(self, link_id):
        self._ensure_link_id(link_id)
        new_links = dict(self._get("links"))
        new_links.pop(link_id)
        self._replace(links=new_links)

    def move_link_up(self, link_id, end):
        self._ensure_link_id(link_id)
        self._move_link(link_id, self._end_to_keys(end), -1)

    def move_link_down(self, link_id, end):
        self._ensure_link_id(link_id)
        self._move_link(link_id, self._end_to_keys(end), 1)

    def _end_to_keys(self, end):
        if end == "from":
            return {"sort_index_key": "sort_index_in_from", "end_key": "from"}
        elif end == "to":
            return {"sort_index_key": "sort_index_in_to", "end_key": "to"}
        else:
            raise ValueError(f"Invalid sort index end={end}.")

    def _move_link(self, link_id_to_move, end_keys, delta):
        note_id = self._get("links", link_id_to_move)[end_keys["end_key"]]
        links_to_sort = self._sort_links([
            (link_id, link)
            for link_id, link in self._get("links").items()
            if link[end_keys["end_key"]] == note_id
        ], [end_keys["sort_index_key"], "timestamp_created"])
        link_index = None
        for index, (link_id, link) in enumerate(links_to_sort):
            if link_id == link_id_to_move:
                link_index = index
        link = links_to_sort.pop(link_index)
        links_to_sort.insert(max(0, link_index+delta), link)
        new_links = dict(self._get("links"))
        for index, (link_id, link) in enumerate(links_to_sort):
            new_links[link_id] = dict(link, **{end_keys["sort_index_key"]: index})
        if new_links != self._get("links"):
            self._replace(links=new_links)

    def _ensure_note_id(self, note_id):
        if note_id not in self._get("notes"):
            raise NoteNotFound(str(note_id))

    def _ensure_link_id(self, link_id):
        if link_id not in self._get("links"):
            raise LinkNotFound(str(link_id))

    def _replace(self, **kwargs):
        self._set(dict(self._get(), **kwargs))

    def _data_changed(self):
        write_json_file(self.path, self._get())
        self.write_files()
        self._create_virtual_links()

class NoteNotFound(ValueError):
    pass

class LinkNotFound(ValueError):
    pass

class LinkText(ExternalTextEntry):

    def __init__(self, db, link_id):
        self.db = db
        self.link_id = link_id
        ExternalTextEntry.__init__(self, self._link_to_text(), EDITOR_COMMAND)

    def _link_to_text(self):
        data = self.db.get_link_data(self.link_id)
        return data.get("text", "")

    def _new_text(self):
        with self.db.transaction():
            self.db.update_link(self.link_id, text=self.text.strip())

class NoteText(ExternalTextEntry):

    LINK_PREFIX = "link: "
    TAG_PREFIX = "tag: "
    FILEPATH_PREFIX = "filepath: "
    CHUNKPATH_PREFIX = "chunkpath: "
    SPLIT_SYNAX = "<<SPLIT>>"

    def __init__(self, db, note_id=None):
        self.db = db
        self.note_id = note_id
        ExternalTextEntry.__init__(self, self._note_to_text(), EDITOR_COMMAND)

    def _note_to_text(self):
        data = self.db.get_note_data(self.note_id)
        links = data.get("links", [])
        tags = data.get("tags", [])
        extra = []
        extra.append("\n")
        extra.append("--\n")
        for link in links:
            extra.append("{}{}\n".format(self.LINK_PREFIX, link))
        for tag in tags:
            extra.append("{}{}\n".format(self.TAG_PREFIX, tag))
        if data.get("type", "text") == "code":
            extra.append("{}{}\n".format(self.FILEPATH_PREFIX, "/".join(data["filepath"])))
            extra.append("{}{}\n".format(self.CHUNKPATH_PREFIX, "/".join(data["chunkpath"])))
        extra.append("# Usage:\n")
        extra.append("# {}http://...\n".format(self.LINK_PREFIX))
        extra.append("# {}name\n".format(self.TAG_PREFIX))
        extra.append("# {}foo/bar.py\n".format(self.FILEPATH_PREFIX))
        extra.append("# {}classes/Foo\n".format(self.CHUNKPATH_PREFIX))
        extra.append("#\n")
        extra.append("# Code Syntax:\n")
        extra.append("# <<foo, blank_lines_before=1>>\n")
        extra.append("# {}\n".format(self.SPLIT_SYNAX))
        extra.append("#\n")
        extra.append("# Tags with special formatting:\n")
        for tag in TAG_ATTRIBUTES:
            extra.append("# {}{}\n".format(self.TAG_PREFIX, tag["name"]))
        extra.append("--\n")
        if data.get("type", "text") == "code":
            return self._code_fragments_to_text(data["fragments"]) + "".join(extra)
        else:
            return data["text"] + "".join(extra)

    def _new_text(self):
        with self.db.transaction():
            fields = self._text_to_note_fields()
            if "splits" in fields:
                splits = fields.pop("splits")
                self.db.update_note(self.note_id, **dict(fields, fragments=splits[0]))
                for fragments in splits[1:]:
                    self.db.create_note(**dict(fields, fragments=fragments, text="<code>"))
            else:
                self.db.update_note(self.note_id, **fields)

    def _text_to_note_fields(self):
        try:
            return self._parse_footer()
        except ParseError:
            return {
                "text": self.text,
                "links": [],
                "tags": [],
            }

    def _code_fragments_to_text(self, fragments):
        lines = []
        for fragment in fragments:
            if fragment["type"] == "chunk":
                lines.append("{}<<{}, blank_lines_before={}>>".format(
                    fragment["prefix"],
                    "/".join(fragment["path"]),
                    fragment["blank_lines_before"]
                ))
            else:
                lines.append("{}".format(
                    fragment["text"],
                ))
        return "\n".join(lines) + "\n"

    def _text_to_code_fragments(self, text):
        splits = [[]]
        for line in text.splitlines():
            if line == self.SPLIT_SYNAX:
                splits.append([])
            else:
                match = re.match(r'^(.*)<<(.*), blank_lines_before=(\d+)>>$', line)
                if match:
                    splits[-1].append({
                        "type": "chunk",
                        "prefix": match.group(1),
                        "path": match.group(2).split("/"),
                        "blank_lines_before": int(match.group(3))
                    })
                else:
                    splits[-1].append({"type": "line", "text": line})
        return splits

    def _parse_footer(self):
        data = {
            "text": "",
            "links": [],
            "tags": [],
            "filepath": [],
            "chunkpath": [],
        }
        parts = self.text.splitlines(True)
        if parts and parts.pop(-1).rstrip() == "--":
            while parts and parts[-1].rstrip() != "--":
                part = parts.pop(-1)
                if part.startswith(self.LINK_PREFIX):
                    data["links"].insert(0, part[len(self.LINK_PREFIX):].rstrip())
                elif part.startswith(self.TAG_PREFIX):
                    data["tags"].insert(0, part[len(self.TAG_PREFIX):].rstrip())
                elif part.startswith(self.FILEPATH_PREFIX):
                    data["filepath"] = [
                        x
                        for x
                        in part[len(self.FILEPATH_PREFIX):].rstrip().split("/")
                        if x
                    ]
                elif part.startswith(self.CHUNKPATH_PREFIX):
                    data["chunkpath"] = [
                        x
                        for x
                        in part[len(self.CHUNKPATH_PREFIX):].rstrip().split("/")
                        if x
                    ]
                elif part.startswith("#"):
                    pass
                else:
                    raise ParseError("unknown field")
            if parts:
                parts.pop(-1)
                while parts and parts[-1].strip() == "":
                    parts.pop(-1)
                data["text"] = "".join(parts)
                if data["filepath"] or data["chunkpath"]:
                    data["type"] = "code"
                    data["splits"] = self._text_to_code_fragments(data["text"])
                    data.pop("text")
                else:
                    data["type"] = "text"
                    data.pop("filepath")
                    data.pop("chunkpath")
                return data
        raise ParseError("no footer found")

class ParseError(ValueError):
    pass

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

    def reverse(self, duration_ms):
        if self.active():
            self.progress = self.duration_ms - self.progress
        else:
            self.start(duration_ms)

    def advance(self, elapsed_ms):
        percent = float(self.progress) / float(self.duration_ms)
        if self.progress == self.duration_ms:
            self.last_consumed = True
        else:
            self.progress = min(self.duration_ms, self.progress+elapsed_ms)
        return percent

    def active(self):
        return self.progress < self.duration_ms or not self.last_consumed

class PygameWindow(WindowFocusMixin):

    def set_title(self, title):
        pygame.display.set_caption(title)

    def close(self):
        pygame.event.post(pygame.event.Event(pygame.QUIT))

class PygameEvent(object):

    def __init__(self, event):
        self.event = event

    def mouse_motion(self, rect=None):
        return (
            self.event.type == pygame.MOUSEMOTION and
            (rect is None or rect.collidepoint(self.event.pos))
        )

    def left_mouse_down(self, rect=None):
        return (
            self.event.type == pygame.MOUSEBUTTONDOWN and
            self.event.button == 1 and
            (rect is None or rect.collidepoint(self.event.pos))
        )

    def left_mouse_up(self, rect=None):
        return (
            self.event.type == pygame.MOUSEBUTTONUP and
            self.event.button == 1 and
            (rect is None or rect.collidepoint(self.event.pos))
        )

    def mouse_pos(self):
        return self.event.pos

    def key_down_text(self):
        return (
            self.event.type == pygame.KEYDOWN and
            self.event.unicode
        )

    def key_down(self, description=None):
        if description is None:
            return self.event.type == pygame.KEYDOWN
        parts = description.split("+")
        ctrl = False
        shift = False
        alt = False
        while parts:
            part = parts.pop(0)
            if part == "ctrl":
                ctrl = True
            elif part == "shift":
                shift = True
            elif part == "alt":
                alt = True
            elif not parts:
                key = pygame.key.key_code(part)
            else:
                raise ValueError("unknown part {}".format(part))
        return (
            self.event.type == pygame.KEYDOWN and
            self.event.key == key and
            bool(self.event.mod & pygame.KMOD_CTRL) == ctrl and
            bool(self.event.mod & pygame.KMOD_SHIFT) == shift and
            bool(self.event.mod & pygame.KMOD_ALT) == alt
        )

    def window_gained_focus(self):
        return (
            self.event.type == pygame.ACTIVEEVENT and
            self.event.state == 1 and
            self.event.gain
        )

    def window_lost_focus(self):
        return (
            self.event.type == pygame.ACTIVEEVENT and
            self.event.state == 1 and
            not self.event.gain
        )

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

class RawText:

    def __init__(self, text):
        self.paragraphs = [
            x.replace("\n", " ").strip()
            for x
            in text.strip().split("\n\n")
        ]
        self.character_limit = max(len(x) for x in self.paragraphs)

    def shrink(self):
        MIN = 10
        if self.character_limit > MIN:
            self.character_limit = max(MIN, int(self.character_limit*0.9))
            return True
        return False

    def to_lines(self):
        lines = []
        for x in self.paragraphs:
            if lines:
                lines.append("")
            lines.extend(self.split_on_limit(x))
        return lines

    def split_on_limit(self, line):
        lines = []
        word_buffer = []
        for word in line.split(" "):
            word_buffer.append(word)
            if len(" ".join(word_buffer)) > self.character_limit:
                lines.append(" ".join(word_buffer[:-1]))
                word_buffer = [word]
        lines.append(" ".join(word_buffer))
        return [x for x in lines if x]

def genid():
    return uuid.uuid4().hex

def utcnow_timestamp_string():
    return datetime.datetime.utcnow().isoformat()

def read_json_file(path, default_value):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    else:
        return default_value

def write_json_file(path, value):
    with safe_write(path) as f:
        json.dump(value, f, indent=4, sort_keys=True)

@contextlib.contextmanager
def safe_write(path):
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w") as f:
        yield f
    os.rename(tmp_path, path)

def format_title(name, path):
    return "{} ({}) - {}".format(
        os.path.basename(path),
        os.path.abspath(os.path.dirname(path)),
        name
    )

def strip_last_word(text):
    """
    >>> strip_last_word("hello there")
    'hello '
    """
    remaining_parts = text.rstrip().split(" ")[:-1]
    if remaining_parts:
        return " ".join(remaining_parts) + " "
    else:
        return ""

if __name__ == "__main__":
    if "--selftest" in sys.argv:
        (failure_count, test_count) = doctest.testmod(
            optionflags=doctest.REPORT_NDIFF|doctest.FAIL_FAST
        )
        if failure_count > 0 or test_count == 0:
            sys.exit(1)
        else:
            print("OK")
            sys.exit(0)
    else:
        PygameCairoEngine().run(SmartNotesWidget)
