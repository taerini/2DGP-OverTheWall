import random

import camera
import effect
import render
from config import *

MAX_HP = 900.0     # 혼자 베어서는 오래 걸린다. 동료·수레 대포와 함께 부순다


class Fortress:
    """적 요새. 근처에서 공격하면 내구도가 깎이고 0 이 되면 승리."""

    def __init__(self):
        self.image = render.image('fortress.png')
        self.cracks = render.image('cracks.png')
        self.hp = MAX_HP
        self.fire_t = 0.0

    def damage(self, amount, x, y):
        if self.hp <= 0:
            return
        self.hp = max(0.0, self.hp - amount)
        effect.add(effect.Spark(x, y, (255, 200, 140)))
        effect.burst(x, y, 4, (160, 140, 130), 22, 90)
        if camera.visible(x - 60, x + 60):
            camera.shake(0.12)
        if self.hp <= 0:
            for _ in range(6):
                effect.burst(FORTRESS_X + random.uniform(20, 300), random.uniform(100, 600), 14, (255, 160, 80), 70, 320)
            camera.shake(1.5)

    def update(self, dt):
        # 많이 부서질수록 불길이 오른다
        self.fire_t -= dt
        k = 1 - self.hp / MAX_HP
        if k > 0.2 and self.fire_t <= 0 and camera.visible(FORTRESS_X, MAP_W):
            self.fire_t = 0.5 / k
            effect.steam(FORTRESS_X + random.uniform(40, 300), random.uniform(150, 600), 2, 20, (255, 140, 70), 40)

    def draw(self):
        if not camera.visible(FORTRESS_X - 40, MAP_W):
            return
        sx, _ = camera.to_screen(FORTRESS_X, 0)
        self.image.draw_to_origin(sx - 30, 0)
        k = 1 - self.hp / MAX_HP
        if k > 0.05:
            self.cracks.opacify(min(1.0, k * 1.3))
            self.cracks.composite_draw(0, 'h', sx + 140, 360, 150 * 1.6, 720)
            self.cracks.opacify(1.0)
