import math
import random

import camera
import effect
import game_world
import map_data
import play_mode
import render
from config import *


class Rock:
    """돌 던지는 거인의 돌. 정해진 시간에 목표 지점에 닿도록 포물선으로 난다."""
    FLIGHT = 1.0
    SPLASH = 46.0

    def __init__(self, x, y, tx, ty):
        self.img = render.image('puff.png')
        self.x, self.y = x, y
        self.vx = (tx - x) / Rock.FLIGHT
        self.vy = (ty - y) / Rock.FLIGHT + 0.5 * GRAVITY * Rock.FLIGHT
        self.t = 0.0
        self.tx, self.ty = tx, ty
        self.mark = render.image('dot.png')

    def update(self, dt):
        self.t += dt
        y_prev = self.y
        self.vy -= GRAVITY * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        p = play_mode.player
        px, py = p.center()
        if math.hypot(px - self.x, py - self.y) < 22:
            p.hurt(self.x, 2)
            self.crash()
            return
        if self.vy < 0 and map_data.landing_lane(self.x, y_prev, self.y) is not None or self.t > 3:
            # 떨어진 자리 근처도 맞는다
            if math.hypot(px - self.x, py - self.y) < Rock.SPLASH:
                p.hurt(self.x, 2)
            self.crash()

    def crash(self):
        effect.burst(self.x, self.y, 6, (120, 110, 100), 22, 120)
        game_world.remove_object(self)

    def draw(self):
        # 떨어질 자리: 날아갈수록 진해진다
        k = min(1.0, self.t / Rock.FLIGHT)
        mx, my = camera.to_screen(self.tx, self.ty)
        render.tint(self.mark, DANGER, 0.3 + 0.5 * k)
        self.mark.draw(mx, my, Rock.SPLASH * 2, Rock.SPLASH * 2)
        render.untint(self.mark)
        sx, sy = camera.to_screen(self.x, self.y)
        render.tint(self.img, (70, 66, 64))
        self.img.draw(sx, sy, 30, 30)
        render.tint(self.img, (40, 38, 36))
        self.img.draw(sx, sy, 18, 18)
        render.untint(self.img)


class Seed:
    """수박 거인이 뱉는 수박씨. 입 높이(노린 층)를 따라 가로로 곧게 빠르게 난다."""
    SPEED = 980.0
    RANGE = 1300.0
    HIT_R = 20.0

    def __init__(self, x, y, d):
        self.img = render.image('dot.png')
        self.x, self.y = x, y
        self.vx = d * Seed.SPEED
        self.vy = random.uniform(-25, 25)          # 살짝씩 흩어진다
        self.left = Seed.RANGE
        self.spin = random.uniform(0, 6.28)

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.spin += 18 * dt
        self.left -= Seed.SPEED * dt
        p = play_mode.player
        px, py = p.center()
        if not p.dead and abs(px - self.x) < Seed.HIT_R and abs(py - self.y) < Seed.HIT_R + 8:
            p.hurt(self.x, 1)
            self.pop()
            return
        for a in play_mode.allies():
            ax, ay = a.center()
            if abs(ax - self.x) < Seed.HIT_R and abs(ay - self.y) < Seed.HIT_R + 8:
                a.hurt(self.x)
                self.pop()
                return
        if self.left <= 0:
            game_world.remove_object(self)

    def pop(self):
        effect.burst(self.x, self.y, 4, (60, 40, 32), 12, 90)
        game_world.remove_object(self)

    def draw(self):
        sx, sy = camera.to_screen(self.x, self.y)
        d = 1 if self.vx > 0 else -1
        # 지나온 쪽으로 옅은 꼬리
        for k in (1, 2, 3):
            render.rect(sx - d * (8 + k * 10) - 4, sy - 2, sx - d * (8 + k * 10) + 4, sy + 2, (255, 240, 225), 150 - 40 * k)
        # 픽셀 수박씨: 돌면서 세운 모양 / 눕힌 모양이 번갈아 나온다 (눕힌 모양은 뾰족한 쪽이 날아가는 쪽)
        rows = SEED if int(self.spin / 1.2) % 2 == 0 else (SEED_SIDE if d < 0 else [r[::-1] for r in SEED_SIDE])
        u = 3
        render.pixel_map(rows, sx - len(rows[0]) * u / 2, sy - len(rows) * u / 2, u, SEED_COLORS)


# 수박씨: 한쪽이 뾰족한 검은 씨, 가운데에 동그란 반사 빛
SEED = ['...K...',
        '..KKK..',
        '.KKKKK.',
        '.KKKKK.',
        'KKKWWKK',
        'KKKWWKK',
        'KKKKKKK',
        '.KKKKK.',
        '..KKK..']
SEED_SIDE = [''.join(r[i] for r in SEED) for i in range(len(SEED[0]))]   # 눕힌 모양 (뾰족한 쪽이 왼쪽)
SEED_COLORS = {'K': (20, 16, 14), 'W': (236, 236, 240)}


FORT_BALL = 10.0        # 대포알이 요새에 주는 피해


class CannonBall:
    SPEED = 900.0

    def __init__(self, x, y, tx, ty):
        self.img = render.image('dot.png')
        self.x, self.y = x, y
        d = math.hypot(tx - x, ty - y) or 1
        self.vx, self.vy = (tx - x) / d * CannonBall.SPEED, (ty - y) / d * CannonBall.SPEED
        self.left = d

    def update(self, dt):
        step = CannonBall.SPEED * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.left -= step
        if self.left <= 0:
            effect.burst(self.x, self.y, 8, (255, 170, 90), 26, 140)
            for g in play_mode.giants():
                if g.alive():
                    l, b, r, t = g.get_bb()
                    px, py = max(l, min(r, self.x)), max(b, min(t, self.y))
                    if math.hypot(px - self.x, py - self.y) < 50:
                        g.hit('raw', 55 * play_mode.player.blade)
            if self.x >= FORTRESS_X - 30:
                play_mode.fortress.damage(FORT_BALL * play_mode.player.blade, self.x, self.y)
            game_world.remove_object(self)

    def draw(self):
        sx, sy = camera.to_screen(self.x, self.y)
        render.tint(self.img, (255, 200, 140))
        self.img.draw(sx, sy, 14, 14)
        render.untint(self.img)
