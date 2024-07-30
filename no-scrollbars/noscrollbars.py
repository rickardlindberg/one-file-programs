import sys

class App:

    def __init__(self):
        self.deflate_factor = AnimatedValue(10, 100, 0.05)

    def event(self, event):
        if event.key_down("ctrl+q"):
            sys.exit(0)

    def update(self, elapsed_ms):
        self.deflate_factor.update(elapsed_ms)

    def draw(self, canvas):
        canvas.fill(color=(255, 0, 100))
        canvas.with_rectangle(lambda rectangle: rectangle.deflate(self.deflate_factor.get())).stroke(color=(25, 25, 25))

class AnimatedValue:

    def __init__(self, start, end, speed):
        self.start = start
        self.end = end
        self.speed = speed
        self.value = start

    def update(self, elapsed_ms):
        self.value += elapsed_ms*self.speed
        if self.value > self.end or self.value < self.start:
            self.speed *= -1

    def get(self):
        return self.value
