#!/usr/bin/env python3

import os
import cairo
import pygame
import smartnotes
import subprocess
import unittest
import tempfile

MANUAL_MODE = os.environ.get("MANUAL_MODE", None) == "yes"

MS_PER_FRAME = 20

class BaseEvent(object):

    def mouse_motion(self, rect=None):
        return False

    def left_mouse_down(self, rect=None):
        return False

    def left_mouse_up(self, rect=None):
        return False

    def mouse_pos(self):
        return None

    def key_down_text(self):
        return None

    def key_down(self, description=None):
        return False

    def window_gained_focus(self):
        return False

    def window_lost_focus(self):
        return False

class KeyEvent(BaseEvent):

    def __init__(self, description):
        self.description = description

    def key_down(self, description=None):
        return self.description == description

class GuiDriverWindow(smartnotes.WindowFocusMixin):

    def set_title(self, title):
        pass

    def close(self):
        pass

class GuiDriver(object):

    def __init__(self, widget_cls, *args, **kwargs):
        self.window = GuiDriverWindow()
        self.cairo_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 800, 600)
        self.canvas = smartnotes.CairoCanvas(self.cairo_surface)
        self.widget = widget_cls(self.window, None, *args, **kwargs)

    def iteration(self, events=[], elapsed_ms=1000):
        for event in events:
            self.widget.process_event(event)
        while elapsed_ms > 0:
            elapsed_ms_per_frame = min(elapsed_ms, MS_PER_FRAME)
            elapsed_ms -= elapsed_ms_per_frame
            self.widget.update(pygame.Rect(0, 0, 800, 600), elapsed_ms_per_frame)
            self.widget.draw(self.canvas)

    def write_to_png(self, path):
        self.cairo_surface.write_to_png(path)

class SmartNotesEndToEndTests(unittest.TestCase):

    def setUp(self):
        self.driver = GuiDriver(smartnotes.SmartNotesWidget, "test_resources/example.notes")

    def assert_drawn_image_is(self, name):
        try:
            expected_path = os.path.join("test_resources", name)
            actual_path = os.path.join("test_resources", "actual_{}".format(name))
            self.driver.write_to_png(actual_path)
            subprocess.check_call(["diff", expected_path, actual_path])
            os.remove(actual_path)
        except:
            if MANUAL_MODE and manual_compare_accept(expected_path, actual_path):
                return
            self.fail(
                f"Drawn image did not match\n"
                f"\n"
                f"  Examine:\n"
                f"    eog {actual_path}\n"
                f"  Accept:\n"
                f"    cp {actual_path} {expected_path}\n"
            )

    def test_main_screen(self):
        self.driver.iteration(elapsed_ms=300+1)
        self.assert_drawn_image_is("main_screen.png")

    def test_search_bar(self):
        self.driver.iteration(events=[KeyEvent("/")], elapsed_ms=100)
        self.assert_drawn_image_is("search_bar_half_way.png")
        self.driver.iteration(elapsed_ms=100+MS_PER_FRAME+1)
        self.assert_drawn_image_is("search_bar_animation_completed.png")
        self.driver.iteration(events=[KeyEvent("ctrl+g")], elapsed_ms=100)
        self.assert_drawn_image_is("search_bar_half_way_hide.png")
        self.driver.iteration(elapsed_ms=500)
        self.assert_drawn_image_is("main_screen.png")

def manual_compare_accept(expected, actual):
    with tempfile.TemporaryDirectory() as tmp_dir:
        subprocess.call([
            "compare",
            expected,
            actual,
            "-compose",
            "src",
            os.path.join(tmp_dir, "diff.png")
        ])
        subprocess.call([
            "montage",
            "-mode", "concatenate",
            "-tile", "x1",
            "-geometry", "+5+5",
            "-label", "%f",
            expected,
            actual,
            os.path.join(tmp_dir, "diff.png"),
            os.path.join(tmp_dir, "comparison.png")
        ])
        comparison = subprocess.Popen([
            "eog",
            os.path.join(tmp_dir, "comparison.png")
        ])
        accept = input("Enter 'y' to accept: ") == "y"
        comparison.kill()
        if accept:
            subprocess.check_call([
                "cp",
                actual,
                expected,
            ])
        return accept

if __name__ == "__main__":
    unittest.main()
