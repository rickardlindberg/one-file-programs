import sys
import random

class App:

    def __init__(self):
        self.main_rectangle = None
        self.clips = [Clip(random.randint(10, 25*60)) for x in range(40)]

    def event(self, event):
        if event.key_down("ctrl+q"):
            sys.exit(0)
        elif event.mouse_motion(inside=self.main_rectangle):
            print(event.mouse_point())

    def update(self, elapsed_ms):
        pass

    def draw(self, canvas):
        canvas.fill(color=(255, 0, 100))
        main = canvas.deflate(40)
        main.stroke(color=(25, 25, 25))
        main.columns([
            {
                "fn": clip.draw,
                "proportion": clip.length*clip.magnification,
            }
            for clip in self.clips
        ])
        self.main_rectangle = main.rectangle

class Clip:

    def __init__(self, length):
        self.length = length
        self.magnification = 1
        self.rectangle = None

    def draw(self, canvas):
        canvas.stroke(color=(20, 20, 100))
        canvas.text(str(self.length))
        self.rectangle = canvas.rectangle
