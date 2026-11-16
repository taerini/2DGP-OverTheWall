import math

import camera
import effect
import game_world
import play_mode
import render
from config import *
from projectile import CannonBall

RANGE = 1100.0
RELOAD = 2.4

CART_HP = 12
CART_SPEED = 95.0           # 맵이 길어서, 부서져 벽에서 다시 나와도 전선까지 금방 복귀하게
CART_RANGE = 650.0
CART_RELOAD = 2.8
CART_REBUILD = 15.0
CART_STOP = FORTRESS_X - 520     # 수레가 멈춰 서서 요새를 포격하는 자리
CRUSH_CD = 0.8                    # 거인이 수레를 밟고 지나가면 이 간격으로 1씩 부순다


class Cannon:
    """우리 벽 위에 놓이는 성 대포. 벽에 가까운 거인을 자동으로 쏜다."""

    def __init__(self, index):
        self.image = render.image('cannon.png')
        self.x = WALL_X - 6
        self.y = 300 + index * 95
        self.angle = 0.0
        self.reload = 0.5 + index * 0.4

    def update(self, dt):
        self.reload -= dt
        target, best = None, RANGE
        for g in play_mode.giants():
            if g.alive() and g.x - WALL_X < best:
                target, best = g, g.x - WALL_X
        if target is None:
            return
        tx, ty = target.x + target.dir * target.speed * 0.4, target.y + target.size * 0.6
        self.angle = math.atan2(ty - self.y, tx - self.x)
        if self.reload <= 0:
            self.reload = RELOAD
            mx, my = self.x + math.cos(self.angle) * 22, self.y + math.sin(self.angle) * 22
            game_world.add_object(CannonBall(mx, my, tx, ty), LAYER_PROJECTILE)
            effect.burst(mx, my, 4, (230, 220, 210), 18, 60)

    def draw(self):
        if not camera.visible(self.x - 30, self.x + 30):
            return
        sx, sy = camera.to_screen(self.x, self.y)
        render.rect(sx - 14, sy - 12, sx + 16, sy - 4, (20, 22, 26))
        self.image.composite_draw(self.angle, '', sx, sy)


class CartCannon:
    """수레 대포. 맨 아래 길을 따라 요새 쪽으로 밀고 나가며, 앞의 거인을 쏘고 끝내 요새를 포격한다.
    거인에게 밟히면 부서지고, 잠시 뒤 우리 벽에서 다시 만들어진다."""

    def __init__(self, index):
        self.image = render.image('cannon.png')
        self.wheel = render.image('dot.png')
        self.index = index
        self.stop = CART_STOP - index * 80
        self.angle = 0.0
        self.rebuild_t = 0.0
        self.reset()

    def reset(self):
        self.x, self.y = WALL_X + 60.0 + self.index * 30, float(LANE_Y[0])
        self.hp = CART_HP
        self.reload = 1.0
        self.crush_t = 0.0
        self.roll = 0.0

    def alive(self):
        return self.rebuild_t <= 0

    def damage(self, n, src_x):
        if not self.alive():
            return
        self.hp -= n
        effect.add(effect.Spark(self.x, self.y + 16, (255, 220, 160)))
        effect.add(effect.FloatText(self.x, self.y + 50, f'-{n}', (255, 150, 110), 14))
        if self.hp <= 0:
            self.rebuild_t = CART_REBUILD
            effect.burst(self.x, self.y + 14, 12, (255, 160, 80), 40, 200)
            effect.add(effect.FloatText(self.x, self.y + 64, '수레 대포 파괴!', (255, 140, 100), 16))
            if camera.visible(self.x - 50, self.x + 50):
                camera.shake(0.3)

    def muzzle(self):
        return self.x + math.cos(self.angle) * 20, self.y + 22 + math.sin(self.angle) * 20

    def fire(self, tx, ty):
        mx, my = self.muzzle()
        self.angle = math.atan2(ty - my, tx - mx)
        if self.reload <= 0:
            self.reload = CART_RELOAD
            mx, my = self.muzzle()
            game_world.add_object(CannonBall(mx, my, tx, ty), LAYER_PROJECTILE)
            effect.burst(mx, my, 4, (230, 220, 210), 18, 60)

    def update(self, dt):
        if not self.alive():
            self.rebuild_t -= dt
            if self.rebuild_t <= 0:
                self.reset()
            return
        self.reload -= dt
        self.crush_t = max(0.0, self.crush_t - dt)

        # 맨 아래 길의 거인이 수레 위를 지나가면 부서진다
        for g in play_mode.giants():
            if g.alive() and g.lane == 0 and abs(g.x - self.x) < g.size * 0.15 + 18 and self.crush_t <= 0:
                self.crush_t = CRUSH_CD
                self.damage(1, g.x)
                break

        # 앞쪽 가장 가까운 거인을 쏜다. 거인이 있으면 멈춰 서서 쏜다
        target, best = None, CART_RANGE
        for g in play_mode.giants():
            if g.alive() and g.x > self.x - 40 and g.x - self.x < best:
                target, best = g, g.x - self.x
        if target:
            self.fire(target.x + target.dir * target.speed * 0.4, target.y + target.size * 0.5)
            return
        if self.x < self.stop:
            self.x = min(self.stop, self.x + CART_SPEED * dt)
            self.roll += CART_SPEED * dt / 9
            self.angle *= 0.9
        else:
            self.fire(FORTRESS_X + 60, 230 + self.index * 60)

    def draw(self):
        if not self.alive() or not camera.visible(self.x - 40, self.x + 40):
            return
        sx, sy = camera.to_screen(self.x, self.y)
        mx, my = camera.to_screen(*self.muzzle())
        self.image.composite_draw(self.angle, '', (sx + mx) / 2, (sy + 22 + my) / 2)
        render.rect(sx - 20, sy + 8, sx + 20, sy + 18, (70, 52, 38))
        render.rect(sx - 20, sy + 16, sx + 20, sy + 18, (110, 84, 60))
        render.tint(self.wheel, (40, 34, 30))
        for wx in (-12, 12):
            self.wheel.composite_draw(self.roll, '', sx + wx, sy + 8, 16, 16)
        render.untint(self.wheel)
        k = self.hp / CART_HP
        render.rect(sx - 16, sy + 42, sx + 16, sy + 45, (10, 10, 14), 160)
        render.rect(sx - 16, sy + 42, sx - 16 + 32 * k, sy + 45, (240, 200, 110), 230)
