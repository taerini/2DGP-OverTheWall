import math

import camera
import game_world
import map_data
import play_mode
import render
import wall as wall_mod
import fortress as fortress_mod
from config import *

MINI_W, MINI_H = 440, 46


class Hud:
    def __init__(self):
        self.time = 0.0
        self.banner_t = 0.0
        self.banner = ''
        self.sub = ''
        self.msg_t = 0.0
        self.msg = ''

    def show_banner(self, title, sub=''):
        self.banner, self.sub, self.banner_t = title, sub, 3.0

    def show_message(self, s, t=2.5):
        self.msg, self.msg_t = s, t

    def update(self, dt):
        self.time += dt
        self.banner_t = max(0.0, self.banner_t - dt)
        self.msg_t = max(0.0, self.msg_t - dt)

    def bar(self, x, y, w, h, k, col, back=(10, 10, 14)):
        render.rect(x - 1, y - 1, x + w + 1, y + h + 1, back, 170)
        render.rect(x, y, x + w * max(0.0, min(1.0, k)), y + h, col, 235)

    def draw(self):
        p = play_mode.player
        wall, fort = play_mode.wall, play_mode.fortress
        # 왼쪽 위: 벽, 체력, 가스
        render.rect(10, SCREEN_H - 96, 300, SCREEN_H - 10, (0, 0, 0), 90)
        render.text('우리 벽', 22, SCREEN_H - 26, 15, (230, 230, 230))
        self.bar(92, SCREEN_H - 33, 196, 12, wall.hp / wall_mod.MAX_HP, (120, 190, 230))
        render.text(f'{int(wall.hp)}', 288, SCREEN_H - 26, 13, (230, 230, 230), 'right')
        render.text('체력', 22, SCREEN_H - 52, 15, (230, 230, 230))
        for i in range(p.max_hp):
            col = (230, 80, 70) if i < p.hp else (60, 40, 40)
            render.rect(92 + i * 22, SCREEN_H - 59, 108 + i * 22, SCREEN_H - 45, col, 240)
        render.text('가스', 22, SCREEN_H - 78, 15, (230, 230, 230))
        self.bar(92, SCREEN_H - 85, 196, 12, p.gas / p.gas_max, (160, 225, 255) if p.gas > 20 else (255, 120, 90))

        # 오른쪽 위: 요새, 처치 수, 다음 강화
        render.rect(SCREEN_W - 300, SCREEN_H - 96, SCREEN_W - 10, SCREEN_H - 10, (0, 0, 0), 90)
        render.text('적 요새', SCREEN_W - 288, SCREEN_H - 26, 15, (230, 230, 230))
        self.bar(SCREEN_W - 210, SCREEN_H - 33, 188, 12, fort.hp / fortress_mod.MAX_HP, (190, 120, 220))
        render.text(f'처치 {play_mode.kills}', SCREEN_W - 288, SCREEN_H - 52, 15, (230, 230, 230))
        left = play_mode.next_upgrade - play_mode.kills
        render.text(f'다음 강화까지 {left}', SCREEN_W - 22, SCREEN_H - 52, 15, (255, 220, 140), 'right')
        t = int(play_mode.play_time)
        render.text(f'{t // 60:02d}:{t % 60:02d}', SCREEN_W - 288, SCREEN_H - 78, 15, (200, 200, 200))
        render.text(ZONES[zone_of(p.x)]['name'], SCREEN_W - 22, SCREEN_H - 78, 15, (200, 200, 200), 'right')

        self.draw_minimap()
        self.draw_skills()
        self.draw_boss()

        # 벽 경고
        if wall.hit_t < 0.6 and p.x > WALL_X + 1300:
            a = 0.5 + 0.5 * math.sin(self.time * 12)
            render.rect(0, 0, 8, SCREEN_H, (255, 60, 40), 160 * a)
            render.text('◀ 벽이 공격받고 있다!', 20, 380, 20, (255, 120, 100), alpha=0.6 + 0.4 * a)

        if self.banner_t > 0:
            a = min(1.0, self.banner_t, (3.0 - self.banner_t) * 3)
            render.text(self.banner, SCREEN_W / 2, 470, 44, (245, 240, 230), 'center', FONT_TITLE, a)
            render.text(self.sub, SCREEN_W / 2, 422, 18, (220, 220, 220), 'center', alpha=a)
        if self.msg_t > 0:
            render.text(self.msg, SCREEN_W / 2, 560, 20, (255, 210, 150), 'center', alpha=min(1.0, self.msg_t))

    def draw_minimap(self):
        p = play_mode.player
        x0, y0 = SCREEN_W / 2 - MINI_W / 2, SCREEN_H - 10 - MINI_H
        render.rect(x0, y0, x0 + MINI_W, y0 + MINI_H, (0, 0, 0), 120)

        def mx(x):
            return x0 + x / MAP_W * MINI_W

        def my(y):
            return y0 + 4 + (y - LANE_Y[0]) / (LANE_Y[4] - LANE_Y[0] + 110) * (MINI_H - 8)

        for z in range(1, ZONE_COUNT):
            render.rect(mx(z * ZONE_W), y0, mx(z * ZONE_W) + 1, y0 + MINI_H, (255, 255, 255), 40)
        for i in range(5):
            for x1, x2 in map_data.lanes[i]:
                render.rect(mx(x1), my(LANE_Y[i]), mx(x2), my(LANE_Y[i]) + 1, (200, 200, 200), 90)
        render.rect(x0, y0, mx(WALL_X), y0 + MINI_H, (140, 160, 180), 220)
        render.rect(mx(FORTRESS_X), y0, x0 + MINI_W, y0 + MINI_H, (150, 110, 180), 220)
        render.rect(mx(camera.x), y0, mx(camera.x + SCREEN_W), y0 + 1, (255, 255, 255), 150)
        render.rect(mx(camera.x), y0 + MINI_H - 1, mx(camera.x + SCREEN_W), y0 + MINI_H, (255, 255, 255), 150)
        for g in play_mode.giants():
            if not g.alive():
                continue
            col = (255, 70, 50) if g.x < WALL_X + 900 else (230, 215, 200)
            s = 3 if g.boss else 2
            gx, gy = mx(g.x), my(g.y) + 3
            render.rect(gx - s, gy - s, gx + s, gy + s, col, 240)
        for a in game_world.objects(LAYER_ALLY):
            render.rect(mx(a.x) - 2, my(a.y), mx(a.x) + 2, my(a.y) + 4, (140, 190, 255), 240)
        for c in play_mode.carts():
            render.rect(mx(c.x) - 3, my(c.y), mx(c.x) + 3, my(c.y) + 3, (240, 200, 110), 240)
        px, py = mx(p.x), my(p.y) + 3
        render.rect(px - 3, py - 3, px + 3, py + 3, (120, 230, 130), 255)

    def draw_skills(self):
        p = play_mode.player
        names = (('Q', '베기', 0.35), ('W', '회오리', p.tornado_cd))
        for i, (k, name, full) in enumerate(names):
            x = SCREEN_W / 2 - 65 + i * 70
            y = 14
            locked = k == 'W' and not p.has_tornado
            ready = p.cool[k] <= 0 and not locked
            render.rect(x, y, x + 60, y + 44, (0, 0, 0), 150)
            if p.cool[k] > 0:
                h = 44 * p.cool[k] / full
                render.rect(x, y, x + 60, y + h, (90, 90, 100), 170)
            col = (240, 240, 240) if ready else (120, 120, 120)
            render.text(k, x + 30, y + 30, 18, col, 'center')
            render.text('강화 카드' if locked else name, x + 30, y + 11, 12, col, 'center')
        render.text(f'{p.floor() + 1}층', SCREEN_W / 2 - 80, 36, 18, (200, 230, 200), 'right')

    def draw_boss(self):
        p = play_mode.player
        boss = None
        for g in play_mode.giants():
            if g.boss and g.alive() and abs(g.x - p.x) < 1500:
                boss = g
        if boss is None:
            return
        w = 420
        x0 = SCREEN_W / 2 - w / 2
        render.text(boss.boss, SCREEN_W / 2, 88, 17, (255, 220, 200), 'center')
        self.bar(x0, 66, w, 8, boss.hp / boss.max_hp, (220, 80, 60))
        if boss.armor > 0:
            render.text(f'껍질 {boss.armor} · 발목을 베어 껍질을 깨야 목덜미가 통한다', SCREEN_W / 2, 114, 13, (230, 200, 160), 'center')
        elif boss.kind == 'smart':
            render.text('목덜미를 손으로 가린다 · 발목을 베어 주저앉힌 뒤 베기', SCREEN_W / 2, 114, 13, (230, 200, 160), 'center')
