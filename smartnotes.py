#!/usr/bin/env python3

import datetime
import sys
import uuid
import webbrowser
import cairo
import pygame
import contextlib
import json
import os
import subprocess
import tempfile

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
COLOR_NOTE_BG            = (250, 250, 250)
COLOR_NOTE_TEXT          = (20, 20, 20)
COLOR_NOTE_DATE_TEXT     = (100, 100, 100)
COLOR_NOTE_TAG_TEXT      = (100, 100, 255)
FONT_MONOSPACE           = "Monospace"
FONT_TEXT                = "San-Serif"
EDITOR_COMMAND           = ["gvim", "--nofork", None]
NUM_SEARCH_RESULTS       = 6
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
TAG_ATTRIBUTES           = [
    {"name": "title", "textalign": "center"},
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

    def __init__(self, window, parent, db, note_id, state):
        Widget.__init__(self, window, parent)
        self.db = db
        self.note_id = note_id
        self.state = state

    def is_deleted(self):
        try:
            self.db.get_note_data(self.note_id)
            return False
        except NoteNotFound:
            return True

    def update(self, rect, elapsed_ms):
        Widget.update(self, rect, elapsed_ms)
        self.data = self.db.get_note_data(self.note_id)
        self.full_width = self.state.get_full_note_width()
        self.full_height = int(self.full_width*3/5)
        self.card_full_size = (self.full_width, self.full_height)
        self.card_full_rect = pygame.Rect((0, 0), self.card_full_size)

    def draw(self, canvas):
        border_size = 3
        border = self.rect.copy()
        border.width -= border_size
        border.height -= border_size
        border.x += border_size
        border.y += border_size
        canvas.fill_rect(border, color=(0, 0, 0, 50))
        border.x -= border_size
        border.y -= border_size
        canvas.fill_rect(border, color=COLOR_NOTE_BG)
        canvas.draw_rect(border, (0, 0, 0, 120), 1)
        canvas.blit(
            canvas.create_image(
                self.card_full_size,
                self._draw_card
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

    def _draw_card(self, canvas):
        border = 8
        status_height = self.full_width/20
        rect = self.card_full_rect
        rect = rect.inflate(-border*4, -border*3-status_height)
        rect.top = border
        if DEBUG_NOTE_BORDER:
            canvas.draw_rect(rect, (200, 50, 50), 1)
        attributes = {
            "textalign": "left",
        }
        for tag in TAG_ATTRIBUTES:
            if tag["name"] in self.data.get("tags", []):
                for key in list(attributes.keys()):
                    if key in tag:
                        attributes[key] = tag[key]
        canvas.render_text(
            self.data["text"],
            rect,
            size=self.full_width/10,
            textalign=attributes["textalign"],
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

    def __init__(self, window, parent, path):
        VBox.__init__(self, window, parent)
        self.set_title(format_title("Smart Notes", path))
        self.link_source = None
        self.link_target = None
        self.full_note_width = 0
        self.toggle_table_network_after_event_processing = False
        self.db = NoteDb(path)
        self.pos = (0, 0)
        self.search_bar = self.add(self.instantiate(SearchBar,
            self.db,
            self,
            open_callback=self._on_search_note_open,
            dismiss_callback=self._on_search_dismiss
        ))
        self.network = self.add(self.instantiate(NetworkWidget,
            self.db,
            self,
            request_search_callback=self._on_search_request
        ))
        self.table = self.add(self.instantiate(TableWidget,
            self.db,
            self,
            request_search_callback=self._on_search_request
        ))
        self.table.toggle_visible()
        self.debug_bar = self.add(self.instantiate(DebugBar))
        self.network.focus()

    def bubble_event(self, event):
        if event.key_down(KEY_TOGGLE_TABLE_NETWORK):
            self.toggle_table_network()
        else:
            VBox.bubble_event(self, event)

    def toggle_table_network(self):
        self.toggle_table_network_after_event_processing = True

    def get_full_note_width(self):
        return max(100, self.full_note_width)

    def set_full_note_width(self, width):
        self.full_note_width = width

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

    def process_event(self, event):
        if event.mouse_motion():
            self.pos = event.mouse_pos()
            self.set_link_target(None)
            self.clear_quick_focus()
        if self.link_source and event.left_mouse_up():
            if self.link_target:
                self.db.create_link(
                    self.link_source.note_id,
                    self.link_target.note_id
                )
                self.set_link_source(None)
                self.set_link_target(None)
                return
            self.set_link_source(None)
            self.set_link_target(None)
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
        if self.toggle_table_network_after_event_processing:
            self.network.toggle_visible()
            self.table.toggle_visible()
            if self.network.is_visible():
                self.network.focus()
            else:
                self.table.focus()
            self.clear_quick_focus()
            self.toggle_table_network_after_event_processing = False

    def _on_search_note_open(self, note_id):
        self.network.open_note(note_id)

    def _on_search_dismiss(self, close):
        if close:
            self.search_bar.hide()
        self.network.focus()

    def _on_search_request(self):
        self.search_bar.start_search()

    def update(self, rect, elapsed_ms):
        VBox.update(self, rect, elapsed_ms)
        self.rect = rect

    def draw(self, canvas):
        canvas.fill_rect(self.rect, color=COLOR_BACKGROUND)
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

class SearchBar(VBox):

    SEARCH_FIELD_HEIHGT = 50
    VPADDING = 8

    def __init__(self, window, parent, db, state, open_callback, dismiss_callback):
        VBox.__init__(self, window, parent, height=0, visible=False)
        self.db = db
        self.state = state
        self.open_callback = open_callback
        self.dismiss_callback = dismiss_callback
        self.animation = Animation()
        self.notes = []
        self.search_results = self.instantiate(SearchResults,
            db, state, open_callback,
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

    def __init__(self, window, parent, db, state, open_callback, hpadding):
        HBox.__init__(self, window, parent)
        self.db = db
        self.state = state
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
        self.num_results = max(3, min(12, num))

    def update_search_text(self, text):
        self.text = text

    def update(self, rect, elapsed_ms):
        self.wanted_height = int(round((rect.width-self.hpadding)/self.num_results*3/5))
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
                        self.state,
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

    def __init__(self, window, parent, db, state, note_id, open_callback):
        NoteBaseWidget.__init__(self, window, parent, db, note_id, state)
        self.open_callback = open_callback

    def process_event(self, event):
        if event.mouse_motion(rect=self.rect):
            self.state.set_link_target(self)
            self.quick_focus()
        if event.left_mouse_down(rect=self.rect):
            self.state.set_link_source(self)
        elif event.left_mouse_up(rect=self.rect):
            self.open_callback(self.note_id)
        else:
            NoteBaseWidget.process_event(self, event)

    def update(self, rect, elapsed_ms):
        NoteBaseWidget.update(self, rect, elapsed_ms)
        self.rect = self._get_target(rect, align="center")

class NetworkWidget(Widget):

    def __init__(self, window, parent, db, state, request_search_callback):
        Widget.__init__(self, window, parent)
        self.db = db
        self.state = state
        self.request_search_callback = request_search_callback
        self.pos = (-1, -1)
        self.notes = []
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
        if event.key_down(KEY_OPEN_SEARCH) and self.has_focus():
            self.request_search_callback()
        elif event.key_down(KEY_CREATE_NOTE) and self.has_focus():
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

    def open_note(self, note_id):
        self.make_root(self.instantiate(NetworkNote, self, self.db, note_id, self.state))

    def make_root(self, note):
        if note is not self.root_note:
            self.root_note = note
            self.clear_quick_focus()

    def update(self, rect, elapsed_ms):
        Widget.update(self, rect, elapsed_ms)
        self.rect = rect
        self.stripe_rects = []
        padding = 8
        self.state.set_full_note_width(int(rect.width * 0.3))
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

    def __init__(self, window, parent, network, db, note_id, state):
        NoteBaseWidget.__init__(self, window, parent, db, note_id, state)
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

    def process_event(self, event):
        if event.mouse_motion(rect=self.rect):
            self.state.set_link_target(self)
            self.quick_focus()
        if event.left_mouse_up(self.rect):
            self.network.make_root(self)
        elif self.has_focus() and event.key_down(KEY_EDIT_NOTE):
            self.clear_quick_focus()
            self.post_event(
                USER_EVENT_EXTERNAL_TEXT_ENTRY,
                entry=NoteText(self.db, self.note_id)
            )
        elif self.has_focus() and event.key_down(KEY_DELETE_NOTE):
            self.clear_quick_focus()
            self.db.delete_note(self.note_id)
        elif self.has_focus() and event.key_down(KEY_UNLINK_NOTE):
            link_id = self.get_link_id()
            if link_id:
                self.db.delete_link(link_id)
                self.clear_quick_focus()
        elif self.has_focus() and event.key_down(KEY_OPEN_LINKS):
            for link in self.data.get("links", []):
                webbrowser.open(link)
        elif self.has_focus() and event.key_down(KEY_CREATE_NOTE):
            self.clear_quick_focus()
            with self.db.transaction():
                child_note_id = self.db.create_note(text=NEW_NOTE_TEXT)
                self.db.create_link(self.note_id, child_note_id)
            self.post_event(
                USER_EVENT_EXTERNAL_TEXT_ENTRY,
                entry=NoteText(self.db, child_note_id)
            )
        elif self.has_focus() and event.key_down(KEY_OPEN_SEARCH):
            self.clear_quick_focus()
            self.network.request_search_callback()
        elif self.has_focus() and event.left_mouse_down():
            self.state.set_link_source(self)
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
                self.incoming.append(by_id.pop(link_id))
            else:
                self.instantiate(LinkWidget,
                    self.db,
                    link_id,
                    self.instantiate(NetworkNote, self.network, self.db, link_data["from"], self.state),
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
                self.instantiate(LinkWidget,
                    self.db,
                    link_id,
                    self,
                    self.instantiate(NetworkNote, self.network, self.db, link_data["to"], self.state)
                )
        return self.outgoing

    def get_link_id(self):
        if self.side == "left" and len(self.outgoing) == 1:
            return self.outgoing[0].link_id
        if self.side == "right" and len(self.incoming) == 1:
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

    def __init__(self, window, parent, db, link_id, start, end):
        Widget.__init__(self, window, parent)
        self.db = db
        self.link_id = link_id
        self.start = start
        self.end = end
        self.start.outgoing.append(self)
        self.end.incoming.append(self)
        self.start_pos = None
        self.end_pos = None

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
        canvas._set_color(COLOR_LINE)
        canvas.set_line_width(1.5)
        canvas.stroke()

class TableWidget(Widget):

    def __init__(self, window, parent, db, state, request_search_callback):
        Widget.__init__(self, window, parent)
        self.db = db
        self.state = state
        self.request_search_callback = request_search_callback

    def update(self, rect, elapsed_ms):
        Widget.update(self, rect, elapsed_ms)

    def draw(self, canvas):
        Widget.draw(self, canvas)

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

class NoteDb(Immutable):

    def __init__(self, path):
        Immutable.__init__(self, read_json_file(path, {
            "version": 1,
            "notes": {},
            "links": {},
        }))
        self.path = path

    def get_notes(self, expression=""):
        def match(item):
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

    def get_outgoing_links(self, note_id):
        return [
            (link_id, link)
            for link_id, link in self._get("links").items()
            if link["from"] == note_id
        ]

    def get_incoming_links(self, note_id):
        return [
            (link_id, link)
            for link_id, link in self._get("links").items()
            if link["to"] == note_id
        ]

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

class NoteNotFound(ValueError):
    pass

class LinkNotFound(ValueError):
    pass

class NoteText(ExternalTextEntry):

    LINK_PREFIX = "link: "
    TAG_PREFIX = "tag: "

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
        extra.append("# Usage:\n")
        extra.append("# {}http://...\n".format(self.LINK_PREFIX))
        extra.append("# {}name\n".format(self.TAG_PREFIX))
        extra.append("#\n")
        extra.append("# Tags with special formatting:\n")
        for tag in TAG_ATTRIBUTES:
            extra.append("# {}{}\n".format(self.TAG_PREFIX, tag["name"]))
        extra.append("--\n")
        return data["text"] + "".join(extra)

    def _new_text(self):
        self.db.update_note(self.note_id, **self._text_to_note_fields())

    def _text_to_note_fields(self):
        try:
            return self._parse_footer()
        except ParseError:
            return {
                "text": self.text,
                "links": [],
                "tags": [],
            }

    def _parse_footer(self):
        data = {
            "text": "",
            "links": [],
            "tags": [],
        }
        parts = self.text.splitlines(True)
        if parts and parts.pop(-1).rstrip() == "--":
            while parts and parts[-1].rstrip() != "--":
                part = parts.pop(-1)
                if part.startswith(self.LINK_PREFIX):
                    data["links"].insert(0, part[len(self.LINK_PREFIX):].rstrip())
                elif part.startswith(self.TAG_PREFIX):
                    data["tags"].insert(0, part[len(self.TAG_PREFIX):].rstrip())
                elif part.startswith("#"):
                    pass
                else:
                    raise ParseError("unknown field")
            if parts:
                parts.pop(-1)
                while parts and parts[-1].strip() == "":
                    parts.pop(-1)
                data["text"] = "".join(parts)
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
        split=True,
        color=(0, 0, 0)
    ):
        if box.height <= 0:
            return
        text = text.strip().replace("\n", " ")
        if not text:
            return
        if DEBUG_TEXT_BORDER:
            self.ctx.set_source_rgb(1, 0.1, 0.1)
            self.ctx.rectangle(box[0], box[1], box[2], box[3])
            self.ctx.set_line_width(1)
            self.ctx.stroke()
        if face is not None:
            self.ctx.select_font_face(face)
        self._set_color(color)
        metrics, scale_factor = self._find_best_fit(text, box, split, size)
        self.ctx.save()
        xoffset = 0
        yoffset = 0
        self._translate_box(box, metrics["width"]*scale_factor, metrics["height"]*scale_factor, boxalign)
        self.ctx.scale(scale_factor, scale_factor)
        for x, y, width, part in metrics["parts"]:
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
            metrics = self._get_metrics([text])
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
        split_times = 1
        target_ratio = box.width / box.height
        metrics = self._get_metrics(self._split_text(text, split_times))
        diff = abs(metrics["ratio"] - target_ratio)
        while True:
            split_times += 1
            new_metrics = self._get_metrics(self._split_text(text, split_times))
            new_diff = abs(new_metrics["ratio"] - target_ratio)
            if new_metrics == metrics or new_diff > diff:
                return metrics
            else:
                diff = new_diff
                metrics = new_metrics

    def _split_text(self, text, times):
        words = text.split(" ")
        words_per_part = max(1, int(round(len(words) / times)))
        parts = []
        start = 0
        while start < len(words):
            parts.append(" ".join(words[start:start+words_per_part]))
            start += words_per_part
        return parts

    def _get_metrics(self, splits):
        width = 0
        height = 0
        start_y = None
        parts = []
        font_ascent, font_descent = self.ctx.font_extents()[0:2]
        extra = font_descent*0.9
        for text in splits:
            extents = self.ctx.text_extents(text)
            height += font_ascent
            parts.append((-extents.x_bearing, height, extents.width, text))
            width = max(width, extents.width)
            height += font_descent
            height += extra
        height -= extra
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

def main():
    if len(sys.argv) < 2:
        sys.exit("Usage: smartnotes.py <file>")
    pygame_main(
        SmartNotesWidget,
        sys.argv[1]
    )

def genid():
    return uuid.uuid4().hex

def utcnow_timestamp_string():
    return datetime.datetime.utcnow().isoformat()

def pygame_main(root_widget_cls, *args, **kwargs):
    pygame.init()
    root_widget = root_widget_cls(PygameWindow(), None, *args, **kwargs)
    screen = pygame.display.set_mode((1280, 720), pygame.RESIZABLE)
    clock = pygame.time.Clock()
    external_text_entries = ExternalTextEntries()
    pygame.time.set_timer(USER_EVENT_CHECK_EXTERNAL, 1000)
    pygame_cairo_surface = create_pygame_cairo_surface(screen)
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return
            elif event.type == pygame.VIDEORESIZE:
                pygame_cairo_surface = create_pygame_cairo_surface(screen)
            elif event.type == USER_EVENT_CHECK_EXTERNAL:
                external_text_entries.check()
            elif event.type == USER_EVENT_EXTERNAL_TEXT_ENTRY:
                external_text_entries.add(event.entry)
            else:
                root_widget.process_event(PygameEvent(event))
        root_widget.update(screen.get_rect(), clock.get_time())
        pygame_cairo_surface.lock()
        root_widget.draw(CairoCanvas(create_cairo_image(pygame_cairo_surface)))
        pygame_cairo_surface.unlock()
        screen.blit(pygame_cairo_surface, (0, 0))
        pygame.display.flip()
        clock.tick(60)

def create_pygame_cairo_surface(screen):
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

def create_cairo_image(pygame_cairo_surface):
    return cairo.ImageSurface.create_for_data(
        pygame_cairo_surface.get_buffer(),
        cairo.FORMAT_ARGB32,
        *pygame_cairo_surface.get_size()
    )

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

def format_title(name, path):
    return "{} ({}) - {}".format(
        os.path.basename(path),
        os.path.abspath(os.path.dirname(path)),
        name
    )

def strip_last_word(text):
    remaining_parts = text.rstrip().split(" ")[:-1]
    if remaining_parts:
        return " ".join(remaining_parts) + " "
    else:
        return ""

if __name__ == "__main__":
    main()
