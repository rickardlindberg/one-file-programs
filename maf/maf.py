#!/usr/bin/env python3

from datetime import date
import doctest
import os
import sys

###############################################################################
# App Engine
###############################################################################

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "yes"

import cairo
import pygame

DEBUG_TEXT_BORDER = True

class PygameCairoEngine:

    def run(self, app):
        pygame.init()
        pygame.key.set_repeat(500, 30)
        root_widget = app(PygameWindow())
        screen = pygame.display.set_mode((1280, 720), pygame.RESIZABLE)
        clock = pygame.time.Clock()
        pygame_cairo_surface = self.create_pygame_cairo_surface(screen)
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                elif event.type == pygame.VIDEORESIZE:
                    pygame_cairo_surface = self.create_pygame_cairo_surface(screen)
                else:
                    root_widget.process_event(PygameEvent(event))
            root_widget.update(Rectangle(*screen.get_rect()), clock.get_time())
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

    def draw_line(self, p1, p2, color=(0, 0, 0), thickness=1):
        self.ctx.move_to(p1.x, p1.y)
        self.ctx.line_to(p2.x, p2.y)
        self._set_color(color)
        self.ctx.set_line_width(thickness)
        self.ctx.stroke()

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
        if not text.strip():
            return
        if DEBUG_TEXT_BORDER:
            self.ctx.set_source_rgb(1, 0.1, 0.1)
            self.ctx.rectangle(box.x, box.y, box.width, box.height)
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
            xoffset = box.width-text_width
        elif boxalign in ["topcenter", "center", "bottomcenter"]:
            xoffset = box.width/2-text_width/2
        else:
            xoffset = 0
        if boxalign in ["bottomleft", "bottomcenter", "bottomright"]:
            yoffset = box.height-text_height
        elif boxalign in ["midleft", "center", "midright"]:
            yoffset = box.height/2-text_height/2
        else:
            yoffset = 0
        self.ctx.translate(box.x+xoffset, box.y+yoffset)

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
        return Rect(
            0,
            0,
            self.surface.get_width(),
            self.surface.get_height()
        )

class PygameWindow:

    def set_title(self, title):
        pygame.display.set_caption(title)

    def close(self):
        pygame.event.post(pygame.event.Event(pygame.QUIT))

class PygameEvent(object):

    def __init__(self, event):
        self.event = event

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

class Rectangle:

    def __init__(self, x, y, width, height):
        self.x = x
        self.y = y
        self.width = width
        self.height = height

    def split_into_rows(self, rows, padding):
        total_padding = padding * (len(rows) - 1)
        total_proportion = sum(row.proportion for row in rows)
        total_space = (self.height - total_padding)
        y = self.y
        for row in rows:
            row_height = total_space * (row.proportion / total_proportion)
            yield (row.item, Rectangle(
                self.x,
                y,
                self.width,
                row_height,
            ))
            y += row_height
            y += padding

    def deflate(self, number_of_pixels):
        return Rectangle(
            self.x + number_of_pixels,
            self.y + number_of_pixels,
            self.width - number_of_pixels*2,
            self.height - number_of_pixels*2,
        )

    @property
    def bottom_left(self):
        return Point(self.x, self.y+self.height)

    @property
    def bottom_right(self):
        return Point(self.x+self.width, self.y+self.height)

    @property
    def top_left(self):
        return Point(self.x, self.y)

    def __repr__(self):
        return f"Rectangle(x={self.x}, y={self.y}, width={self.width}, height={self.height})"

class Item:

    def __init__(self, item, proportion=1):
        self.item = item
        self.proportion = proportion

class Point:

    def __init__(self, x, y):
        self.x = x
        self.y = y

###############################################################################
# App
###############################################################################

class Time:

    def __init__(self, minutes, seconds):
        self.minutes = minutes
        self.seconds = seconds

    def total_seconds(self):
        return self.minutes * 60 + self.seconds

BACKGROUND = (250, 250, 250)
COLD = "cold"
HOT = "hot"
EASY = "easy"
MEDIUM = "medium"
RUNS = {
    "Landet 5k, 1km <120, resten 120-130": [
        {
            "date": date(2024, 7, 13),
            "time": Time(35, 57),
            "weather": COLD,
            "effort": MEDIUM,
        },
        {
            "date": date(2024, 7, 17),
            "time": Time(37, 13),
            "weather": HOT,
            "effort": EASY,
        },
        {
            "date": date(2024, 7, 23),
            "time": Time(35, 39),
            "weather": HOT,
            "effort": EASY,
        },
    ],
    "Test 8k, 120-130, 1km <120": [
        {
            "date": date(2024, 7, 13),
            "time": Time(55, 11),
            "weather": COLD,
            "effort": MEDIUM,
        },
        {
            "date": date(2024, 7, 14),
            "time": Time(56, 12),
            "weather": COLD,
            "effort": MEDIUM,
        },
        {
            "date": date(2024, 7, 16),
            "time": Time(54, 12),
            "weather": COLD,
            "effort": MEDIUM,
        },
    ],
}

class MAFApp(object):

    def __init__(self, window):
        self.area = None

    def process_event(self, event):
        pass

    def update(self, area, elapsed_ms):
        self.area = area

    def draw(self, canvas):
        canvas.fill_rect(self.area, BACKGROUND)
        for run, area in self.area.deflate(5).split_into_rows([Item(x) for x in RUNS], 5):
            canvas.fill_rect(area, (100, 100, 100))
            top, bottom = area.deflate(5).split_into_rows([
                Item(run, proportion=10),
                Item("haha", proportion=90),
            ], 5)
            canvas.render_text(run, top[1])
            self.draw_diagram(canvas, run, bottom[1])

    def draw_diagram(self, canvas, run, area):
        area = area.deflate(20)
        canvas.draw_line(area.bottom_left, area.top_left, thickness=3)
        canvas.draw_line(area.bottom_left, area.bottom_right, thickness=3)
        xs = [laps["date"].toordinal() for laps in RUNS[run]]
        ys = [laps["time"].total_seconds() for laps in RUNS[run]]
        xfactor = 1
        yfactor = 1
        if len(RUNS[run]) >= 2:
            xfactor = area.width / (max(xs) - min(xs))
            yfactor = area.height / (max(ys) - min(ys))
        last_point = None
        for laps in RUNS[run]:
            x = area.x + (laps["date"].toordinal() - min(xs)) * xfactor
            y = area.y + area.height - (laps["time"].total_seconds() - min(ys)) * yfactor
            canvas.fill_rect(
                Rectangle(x, y, 0, 0).deflate(-5),
                (200, 100, 0)
            )
            current_point = Point(x, y)
            if last_point is not None:
                canvas.draw_line(last_point, current_point)
            last_point = current_point

###############################################################################
# Main
###############################################################################

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
        PygameCairoEngine().run(MAFApp)
