import sys
import random

CLIP_LENGHTS = [random.randint(10, 25*60) for x in range(40)]

class App:

    def __init__(self):
        self.main_rectangle = None

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
                "fn": lambda canvas: canvas.stroke(color=(20, 20, 100)),
                "proportion": length,
            }
            for length
            in CLIP_LENGHTS
        ])
        self.main_rectangle = main.rectangle
