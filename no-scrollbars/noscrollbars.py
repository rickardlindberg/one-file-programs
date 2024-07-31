import sys
import random

class App:

    def __init__(self):
        self.clips = Clips()

    def event(self, event):
        if event.key_down("ctrl+q"):
            sys.exit(0)
        else:
            self.clips.event(event)

    def update(self, elapsed_ms):
        pass

    def draw(self, canvas):
        canvas.fill(color=(255, 0, 100))
        self.clips.draw(canvas.deflate(40))

class Clips:

    def __init__(self):
        self.clips = [Clip(x) for x in range(50)]
        self.rectangle = None

    def event(self, event):
        if self.rectangle and event.mouse_motion():
            sum_clip_lenghts = sum(clip.length for clip in self.clips)
            frame_in_pixels = self.rectangle.width / sum_clip_lenghts
            max_magnification = 200 / frame_in_pixels
            for clip in self.clips:
                foo = clip.rectangle.center.distance_to(event.mouse_point()).x
                LIM = self.rectangle.width * 0.25
                if foo < LIM:
                    clip.magnification = max(1, max_magnification * ((LIM-foo)/LIM))
                else:
                    clip.magnification = 1

    def draw(self, canvas):
        canvas.stroke(color=(25, 25, 25))
        canvas.columns([
            {
                "fn": clip.draw,
                "proportion": clip.length*clip.magnification,
            }
            for clip in self.clips
        ])
        self.rectangle = canvas.rectangle

class Clip:

    def __init__(self, x):
        self.length = 1
        self.text = str(x)
        self.magnification = 1
        self.rectangle = None

    def draw(self, canvas):
        self.rectangle = canvas.rectangle
        if self.magnification == 1:
            sub = canvas.deflate(height=20)
        else:
            sub = canvas
        sub.stroke(color=(20, 20, 100))
        sub.text(self.text)
