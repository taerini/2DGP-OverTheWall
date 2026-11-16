import math

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
