import math
import random

import camera
import game_world
import render
from config import LAYER_EFFECT


class Puff:
    """김·연기·폭발. 커지면서 사라진다."""

    def __init__(self, x, y, color=(235, 235, 235), size=30, life=1.0, vx=0.0, vy=30.0, alpha=0.7):
        self.img = render.image('puff.png')
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.color, self.size, self.life, self.alpha = color, size, life, alpha
        self.t = 0.0

    def update(self, dt):
        self.t += dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        if self.t >= self.life:
            game_world.remove_object(self)

    def draw(self):
        k = self.t / self.life
        s = self.size * (0.6 + 0.9 * k)
        sx, sy = camera.to_screen(self.x, self.y)
        render.tint(self.img, self.color, self.alpha * (1 - k))
        self.img.draw(sx, sy, s, s)
        render.untint(self.img)


def steam(x, y, n=6, spread=30, color=(240, 240, 240), size=34):
    for _ in range(n):
        game_world.add_object(Puff(x + random.uniform(-spread, spread), y + random.uniform(-spread / 2, spread / 2),
                                   color, random.uniform(size * 0.6, size * 1.2), random.uniform(0.9, 1.6),
                                   random.uniform(-15, 15), random.uniform(30, 70)), LAYER_EFFECT)


def burst(x, y, n=10, color=(255, 170, 80), size=40, speed=160):
    for _ in range(n):
        a = random.uniform(0, 6.28)
        v = random.uniform(speed * 0.3, speed)
        game_world.add_object(Puff(x, y, color, random.uniform(size * 0.5, size), random.uniform(0.4, 0.8),
                                   math.cos(a) * v, math.sin(a) * v, 0.9), LAYER_EFFECT)


class Spark:
    def __init__(self, x, y, color=(255, 255, 255)):
        self.img = render.image('dot.png')
        self.parts = []
        for _ in range(8):
            a = random.uniform(0, 6.28)
            v = random.uniform(80, 240)
            self.parts.append([x, y, math.cos(a) * v, math.sin(a) * v])
        self.color = color
        self.t = 0.0

    def update(self, dt):
        self.t += dt
        for p in self.parts:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[3] -= 500 * dt
        if self.t > 0.4:
            game_world.remove_object(self)

    def draw(self):
        render.tint(self.img, self.color, 1 - self.t / 0.4)
        for x, y, _, _ in self.parts:
            sx, sy = camera.to_screen(x, y)
            self.img.draw(sx, sy, 6, 6)
        render.untint(self.img)


class Slash:
    """베기 궤적. 주인공을 따라다닌다."""

    def __init__(self, owner, kind, face, size, dy=0.0, life=0.22):
        self.img = render.image({'Q': 'arc_q.png', 'W': 'arc_w.png', 'E': 'arc_e.png'}[kind])
        self.owner, self.kind, self.face, self.size, self.dy = owner, kind, face, size, dy
        self.life = life
        self.t = 0.0

    def update(self, dt):
        self.t += dt
        if self.t >= self.life:
            game_world.remove_object(self)

    def draw(self):
        k = self.t / self.life
        sx, sy = camera.to_screen(self.owner.x, self.owner.y + self.dy)
        self.img.opacify(1 - k * k)
        if self.kind == 'E':
            self.img.composite_draw(-k * 6.0, '', sx, sy, self.size, self.size)
        else:
            self.img.composite_draw(0, '' if self.face > 0 else 'h', sx + self.face * self.size * 0.15, sy,
                                    self.size, self.size)
        self.img.opacify(1.0)


class FloatText:
    def __init__(self, x, y, s, color=(255, 255, 255), size=16):
        self.x, self.y, self.s, self.color, self.size = x, y, s, color, size
        self.t = 0.0

    def update(self, dt):
        self.t += dt
        self.y += 30 * dt
        if self.t > 0.9:
            game_world.remove_object(self)

    def draw(self):
        sx, sy = camera.to_screen(self.x, self.y)
        render.text(self.s, sx, sy, self.size, self.color, 'center', alpha=1 - self.t / 0.9)


class Ring:
    """퍼지는 원 (폭발 범위 표시)"""

    def __init__(self, x, y, radius, color=(255, 200, 150), life=0.5):
        self.img = render.image('ring.png')
        self.x, self.y, self.radius, self.color, self.life = x, y, radius, color, life
        self.t = 0.0

    def update(self, dt):
        self.t += dt
        if self.t >= self.life:
            game_world.remove_object(self)

    def draw(self):
        k = self.t / self.life
        r = self.radius * (0.3 + 0.7 * k) * 2.1
        sx, sy = camera.to_screen(self.x, self.y)
        render.tint(self.img, self.color, 1 - k)
        self.img.draw(sx, sy, r, r)
        render.untint(self.img)


class Streak:
    """일섬: 목덜미를 가로지르는 긴 빛줄기. 순식간에 뻗고 가늘어지며 사라진다."""

    def __init__(self, x, y, angle, length, width, color=(150, 215, 255), life=0.22):
        self.img = render.image('streak.png')
        self.x, self.y, self.angle = x, y, angle
        self.length, self.width, self.color, self.life = length, width, color, life
        self.t = 0.0

    def update(self, dt):
        self.t += dt
        if self.t >= self.life:
            game_world.remove_object(self)

    def draw(self):
        k = self.t / self.life
        grow = min(1.0, k / 0.25)
        thin = 1 - max(0.0, (k - 0.25) / 0.75)
        sx, sy = camera.to_screen(self.x, self.y)
        length = self.length * (0.4 + 0.6 * grow)
        render.tint(self.img, self.color, thin)
        self.img.composite_draw(self.angle, '', sx, sy, length * 1.1, self.width * 2.2 * thin + 2)
        render.tint(self.img, (255, 255, 255), thin)
        self.img.composite_draw(self.angle, '', sx, sy, length, self.width * thin + 1)
        render.untint(self.img)


class BigArc:
    """목덜미를 벨 때의 큰 베기 궤적"""

    def __init__(self, x, y, size, face, angle=0.0, life=0.26):
        self.img = render.image('arc_q.png')
        self.x, self.y, self.size, self.face, self.angle, self.life = x, y, size, face, angle, life
        self.t = 0.0

    def update(self, dt):
        self.t += dt
        if self.t >= self.life:
            game_world.remove_object(self)

    def draw(self):
        k = self.t / self.life
        s = self.size * (0.75 + 0.45 * (1 - (1 - k) ** 3))
        sx, sy = camera.to_screen(self.x, self.y)
        flip = '' if self.face > 0 else 'h'
        render.tint(self.img, (140, 210, 255), (1 - k) * 0.9)
        self.img.composite_draw(self.angle * self.face, flip, sx, sy, s * 1.25, s * 1.25)
        render.tint(self.img, (255, 255, 255), 1 - k * k)
        self.img.composite_draw(self.angle * self.face, flip, sx, sy, s, s)
        render.untint(self.img)


class Spray:
    """베인 자리에서 튀는 핏빛 불꽃. dir 방향으로 쏠려 뿜어진다."""

    def __init__(self, x, y, direction, n=22, colors=((255, 90, 70), (255, 230, 220), (200, 40, 40))):
        self.img = render.image('dot.png')
        self.parts = []
        for _ in range(n):
            a = direction + random.uniform(-0.9, 0.9)
            v = random.uniform(150, 520)
            self.parts.append([x, y, math.cos(a) * v, math.sin(a) * v, random.uniform(4, 10), random.choice(colors)])
        self.t = 0.0

    def update(self, dt):
        self.t += dt
        for p in self.parts:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[2] *= 1 - 3 * dt
            p[3] -= 900 * dt
        if self.t > 0.6:
            game_world.remove_object(self)

    def draw(self):
        a = 1 - self.t / 0.6
        for x, y, _, _, s, col in self.parts:
            sx, sy = camera.to_screen(x, y)
            render.tint(self.img, col, a)
            self.img.draw(sx, sy, s, s)
        render.untint(self.img)


class PopText(FloatText):
    """크게 튀어나왔다가 작아지는 피해 숫자"""

    def draw(self):
        k = self.t / 0.9
        pop = 1.6 - 0.6 * min(1.0, self.t / 0.12)
        sx, sy = camera.to_screen(self.x, self.y)
        render.text(self.s, sx, sy, int(self.size * pop), self.color, 'center', alpha=1 - k * k)


DAMAGE_SHOW = 137    # 피해 숫자를 보여 줄 때만 곱한다 (실제 체력 계산과는 상관없음)


def damage_number(x, y, dmg, crit, size):
    """튀어나오는 피해 숫자. 치명타는 더 크고 주황빛이다."""
    n = str(int(dmg * DAMAGE_SHOW))
    if crit:
        add(PopText(x, y, n, (255, 180, 60), int(size * 1.35)))
    else:
        add(PopText(x, y, n, (255, 236, 205), size))


def add(o):
    game_world.add_object(o, LAYER_EFFECT)
