import math

import camera
import game_world
import map_data
import play_mode
import render
import wall as wall_mod
from config import *

MINI_W, MINI_H = 440, 46
WALL_SEGS = 10           # 왼쪽 위 벽 막대 칸 수
LOW_HP = 0.25            # 생명이 이 비율 아래면 화면 가장자리가 붉게 맥박친다
# 게이지 색: 50% 이하 노랑, 25% 이하 빨강 (생명·가스·성벽 모두)
WARN_K, DANGER_K = 0.5, 0.25
COL_HP = (88, 200, 96)           # 생명 (넉넉할 때 초록)
COL_GAS = (170, 225, 255)        # 가스
COL_WALL = (150, 190, 215)       # 성벽
COL_WARN = (238, 200, 64)
COL_DANGER = (232, 64, 56)


def level_col(k, base):
    """남은 비율에 따라 게이지 색: 넉넉하면 제 색, 50% 이하 노랑, 25% 이하 빨강"""
    if k <= DANGER_K:
        return COL_DANGER
    if k <= WARN_K:
        return COL_WARN
    return base
HP_W = 60                # 생명 게이지 칸 수 (픽셀 2개 = 1칸)
GHOST_DELAY = 0.5        # 맞은 뒤 깎인 만큼 하얗게 남겨 두는 시간
GHOST_SPEED = 0.6        # 그 뒤 하얀 부분이 줄어드는 속도 (게이지 비율/초)
KEY_DIM = 0.4            # 스킬 키: 평소 흐린 정도 (누르거나 재사용 대기 중이면 또렷하게)
KEY_FADE = 0.8           # 또렷했다가 다시 흐려지는 시간
KEY_NEW = 3.0            # W 를 처음 얻으면 이만큼 또렷하게 보여 준다


class Hud:
    def __init__(self):
        self.time = 0.0
        self.banner_t = 0.0
        self.banner = ''
        self.sub = ''
        self.msg_t = 0.0
        self.msg = ''
        self.icon_wall = self.icon_gas = None
        self.key_glow = {'Q': 0.0, 'W': 0.0}    # 1 이면 또렷, 0 이면 흐림
        self.had_tornado = False
        self.ghost = 1.0                        # 깎이기 전 체력 비율 (하얗게 남는 부분)
        self.ghost_t = 0.0

    def show_banner(self, title, sub=''):
        self.banner, self.sub, self.banner_t = title, sub, 3.0

    def show_message(self, s, t=2.5):
        self.msg, self.msg_t = s, t

    def update(self, dt):
        self.time += dt
        self.banner_t = max(0.0, self.banner_t - dt)
        self.msg_t = max(0.0, self.msg_t - dt)
        p = play_mode.player
        if p.has_tornado and not self.had_tornado:
            self.key_glow['W'] = KEY_NEW / KEY_FADE      # 새로 얻은 W 는 몇 초 또렷하게
        self.had_tornado = p.has_tornado
        # 깎인 체력은 잠깐 하얗게 남았다가 천천히 줄어든다
        k = p.hp / p.max_hp
        if k >= self.ghost:
            self.ghost, self.ghost_t = k, 0.0
        else:
            if self.ghost_t <= 0 and p.hit_t > 0:
                self.ghost_t = GHOST_DELAY
            self.ghost_t -= dt
            if self.ghost_t <= 0:
                self.ghost = max(k, self.ghost - GHOST_SPEED * dt)
        for k in self.key_glow:
            if p.cool[k] > 0:
                self.key_glow[k] = max(self.key_glow[k], 1.0)
            else:
                self.key_glow[k] = max(0.0, self.key_glow[k] - dt / KEY_FADE)

    def bar(self, x, y, w, h, k, col, back=(10, 10, 14)):
        render.rect(x - 1, y - 1, x + w + 1, y + h + 1, back, 170)
        render.rect(x, y, x + w * max(0.0, min(1.0, k)), y + h, col, 235)

    def draw(self):
        p = play_mode.player
        wall = play_mode.wall
        self.draw_low_hp(p)
        # 왼쪽 위 (패널 없이 작게): 둥근 가스 게이지 + 그 옆에 생명 게이지 + 그 아래 우리 벽
        if self.icon_wall is None:
            self.icon_wall = render.image('ui_wall.png', pixel=True)
        k = p.gas / p.gas_max
        render.pixel_orb(46, SCREEN_H - 46, k, level_col(k, COL_GAS), u=3)
        k = p.hp / p.max_hp
        render.pixel_gauge(78, SCREEN_H - 40, HP_W, k, level_col(k, COL_HP), ghost=self.ghost, u=2, h=6)
        k = wall.hp / wall_mod.MAX_HP
        self.icon_wall.draw(90, SCREEN_H - 66, 16, 16)
        render.pixel_bar(102, SCREEN_H - 72, WALL_SEGS, k, level_col(k, COL_WALL), u=2, seg_w=3, seg_h=2)

        self.draw_skills()

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

    def draw_low_hp(self, p):
        """생명이 적으면 화면 가장자리가 붉게 맥박친다"""
        if p.dead or p.hp > p.max_hp * LOW_HP:
            return
        a = 0.5 + 0.5 * math.sin(self.time * 5)
        for i in range(10):
            t = 9 * (i + 1)
            al = (20 - i * 1.8) * (0.4 + 0.6 * a)       # 겹쳐 그려서 가장자리일수록 진하다 (가장 진할 때 약 60%)
            render.rect(0, 0, SCREEN_W, t, (180, 20, 20), al)
            render.rect(0, SCREEN_H - t, SCREEN_W, SCREEN_H, (180, 20, 20), al)
            render.rect(0, 0, t, SCREEN_H, (180, 20, 20), al)
            render.rect(SCREEN_W - t, 0, SCREEN_W, SCREEN_H, (180, 20, 20), al)

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
        names = (('Q', '베기', 0.35), ('W', '회오리', max(0.01, p.tornado_cd)))
        # 왼쪽 아래 구석의 작은 픽셀 키캡 + 아래 이름. 평소엔 흐리고, 누르거나 재사용 대기 중이면 또렷하게
        for i, (k, name, full) in enumerate(names):
            x = 16 + i * 52
            y = 24
            locked = k == 'W' and not p.has_tornado
            ready = p.cool[k] <= 0 and not locked
            a = KEY_DIM + (1 - KEY_DIM) * min(1.0, self.key_glow[k])
            render.pixel_key(x, y, k, ready, p.cool[k] / full if p.cool[k] > 0 else 0.0, u=2, alpha=a)
            col = (240, 236, 224) if ready else (130, 128, 124)
            render.text('강화 카드' if locked else name, x + 20, y - 11, 11, col, 'center', alpha=a)

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
            render.text('목덜미를 손으로 가린다 · 손을 내린 틈에 베기', SCREEN_W / 2, 114, 13, (230, 200, 160), 'center')
