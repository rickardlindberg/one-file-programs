import sys
import random

class App:

    def __init__(self):
        self.frames = Frames()

    def event(self, event):
        if event.key_down("ctrl+q"):
            sys.exit(0)
        else:
            self.frames.event(event)

    def update(self, elapsed_ms):
        pass

    def draw(self, canvas):
        canvas.fill(color=(255, 0, 100))
        self.frames.draw(canvas.deflate(40))

class Frames:

    def __init__(self):
        self.frames = [Frame(x) for x in range(50)]
        self.rectangle = None

    def event(self, event):
        if event.mouse_motion():
            print(self.find_position(event.mouse_point()))

    def draw(self, canvas):
        canvas.stroke(color=(25, 25, 25))
        canvas.columns([
            {
                "fn": frame.draw,
                "proportion": 1,
            }
            for frame in self.frames
        ])
        self.rectangle = canvas.rectangle

    def find_position(self, mouse_point):
        if self.rectangle:
            positions = []
            for frame in self.frames:
                if frame.rectangle.contains(mouse_point):
                    positions.append(
                        frame.number + frame.rectangle.percent(mouse_point).x
                    )
            if positions:
                return sum(positions) / len(positions)
        return len(self.frames) / 2

class Frame:

    def __init__(self, number):
        self.number = number
        self.rectangle = None

    def draw(self, canvas):
        self.rectangle = canvas.rectangle
        canvas.stroke(color=(20, 20, 100))
        canvas.text(str(self.number))
