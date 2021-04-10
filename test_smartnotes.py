#!/usr/bin/env python3

import os
import cairo
import pygame
import smartnotes
import subprocess
import unittest

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
        self.widget.update(pygame.Rect(0, 0, 800, 600), elapsed_ms)
        self.widget.draw(self.canvas)

    def assert_drawn_image_is(self, path):
        actual_path = os.path.join("test_resources", "actual_{}".format(path))
        self.cairo_surface.write_to_png(actual_path)
        subprocess.check_call(["diff", os.path.join("test_resources", path), actual_path])

class SmartNotesEndToEndTests(unittest.TestCase):

    def test_main_screen(self):
        driver = GuiDriver(smartnotes.SmartNotesWidget, "test_resources/example.notes")
        driver.iteration()
        driver.assert_drawn_image_is("main_screen.png")

if __name__ == "__main__":
    unittest.main()
