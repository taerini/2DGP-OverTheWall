import random

import camera
import effect
import render
from config import *

MAX_HP = 100.0


class Refugee:
    def __init__(self):
        self.x = WALL_X + random.uniform(120, 420)
        self.speed = random.uniform(60, 95)
        self.t = random.uniform(0, 1)


class Wall:
    """우리 벽. 내구도가 0 이 되면 패배. 벽 근처로 피난민이 달려 들어간다."""

    def __init__(self):
        self.image = render.image('wall.png')
        self.cracks = render.image('cracks.png')
        self.refugee = render.image('refugee.png')
        self.hp = MAX_HP
        self.hit_t = 9.0          # 마지막으로 맞은 뒤 지난 시간
        self.refugees = [Refugee() for _ in range(6)]
        self.spawn_t = 0.0

    def damage(self, amount):
        self.hp = max(0.0, self.hp - amount)
        self.hit_t = 0.0

    def repair(self, amount):
        self.hp = min(MAX_HP, self.hp + amount)

    def update(self, dt):
        self.hit_t += dt
        self.spawn_t -= dt
        if self.spawn_t <= 0 and len(self.refugees) < 10:
            self.spawn_t = random.uniform(1.0, 2.5)
            self.refugees.append(Refugee())
        for r in self.refugees:
            r.x -= r.speed * dt
            r.t += dt
        self.refugees = [r for r in self.refugees if r.x > WALL_X - 40]

    def draw(self):
        if not camera.visible(0, WALL_X + 450):
            return
        for r in self.refugees:
            sx, sy = camera.to_screen(r.x, LANE_Y[0])
            fr = int(r.t * 10) % 4
            self.refugee.clip_draw(fr * 16, 0, 16, 24, sx, sy + 11)
        sx, _ = camera.to_screen(0, 0)
        self.image.draw_to_origin(sx - 20, 0)
        k = 1 - self.hp / MAX_HP
        if k > 0.05:
            self.cracks.opacify(min(1.0, k * 1.3))
            self.cracks.draw_to_origin(sx - 20, 0)
            self.cracks.opacify(1.0)
