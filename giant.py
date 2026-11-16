import json
import math
import random

import camera
import effect
import game_world
import map_data
import play_mode
import render
from config import *
from projectile import Rock

with open('resource/giant_meta.json') as f:
    META = json.load(f)
CELL = META['cell']            # 셀 크기 (그림 단위)
CELL_PX = META['cell_px']      # 시트에서 실제 픽셀 크기
SHEET_H = META['height']       # 그림 단위 키
ROWS = [r for r, _ in META['rows']]
FRAMES = dict(META['rows'])
NAPE = META['nape']
WALK_NAPE = sum(dy for _, dy in NAPE['walk']) / len(NAPE['walk']) / SHEET_H
RUN_NAPE = sum(dy for _, dy in NAPE['run']) / len(NAPE['run']) / SHEET_H
KNEEL_NAPE = NAPE['kneel'][2][1] / SHEET_H


def giant_height(k):
    """크기 k 거인의 키. 서 있을 때 목덜미가 (서 있는 층 + k - 1)층 한가운데쯤 오게 맞춘다."""
    return ((k - 1) * LANE_GAP + 70 - (k - 1) * 6.25) / WALK_NAPE


def max_lane(k):
    """머리가 화면을 넘지 않는 가장 높은 층 (0부터). 크기 1 → 5층, 크기 4 → 2층, 크기 5 → 1층"""
    return 5 - k


# 종류별 능력치. size 는 고를 수 있는 크기들
KINDS = {
    'normal':   dict(size=(1, 2, 3, 4, 5), speed=(55, 80), hp=1.0),
    'erratic':  dict(size=(1, 2), speed=(70, 95), hp=0.9),
    'climber':  dict(size=(1, 2, 3), speed=(50, 70), hp=1.0),
    'swarm':    dict(size=(1,), speed=(85, 110), hp=0.8),
    'armed':    dict(size=(1, 2, 3, 4, 5), speed=(48, 66), hp=1.3),
    'smart':    dict(size=(3,), speed=(125, 125), hp=3.2, boss='빠르고 영리한 거인'),
    'thrower':  dict(size=(4,), speed=(26, 26), hp=3.0, boss='돌 던지는 거인'),
    'colossal': dict(size=(5,), speed=(20, 20), hp=3.0, boss='거대 거인'),
}
KNEEL_TIME = 2.6
WAKE_DIST = 1300.0       # 미리 서 있는 거인은 주인공이 이만큼 가까워지면 움직이기 시작한다
RUN_MULT = 2.6           # 달릴 때 걷는 속도의 몇 배
RUN_FAR = 1400.0         # 주인공과 이만큼 멀면 늘 달린다 (먼 요새에서 벽까지 금방 온다)
NO_RUN = ('thrower', 'colossal')    # 느릿느릿 걷는 보스
DEATH_FRAME = 0.14       # 쓰러지는 모션 한 장 시간
DEAD_FADE = (2.8, 3.6)   # 바닥에 누운 채 이 시간부터 흐려져서 사라진다
GRAB_TIME = 0.8          # 손을 뻗기 시작해서 거두기까지
GRAB_CD = 1.6            # 잡기를 거둔 뒤 다음 잡기까지
BLAST_WARN = 1.2         # 거대 거인 폭발 전에 위험 지역을 보여 주는 시간
BLAST_R = 240
GRAB_HIT_AT = 0.3        # state_t 가 이 값 아래로 내려가는 순간 잡는다 (뻗은 지 0.5초 뒤)
PART_RATE = {'neck': 1.0, 'ankle': 0.3, 'body': 0.15, 'raw': 1.0}
PART_NAME = {'neck': '목덜미', 'ankle': '발목', 'body': '몸통'}
DMG_SPREAD = (0.85, 1.15)    # 벨 때마다 피해가 이 범위에서 흔들린다
CRIT_RATE = 0.2
CRIT_MULT = 1.8


def floor_of(y):
    return max(0, min(4, int((y - LANE_Y[0]) // LANE_GAP)))


class Giant:
    def __init__(self, kind, x, lane, k, hp_mult=1.0):
        info = KINDS[kind]
        self.kind = kind
        self.boss = info.get('boss')
        self.k = k
        self.size = giant_height(k)
        self.speed = random.uniform(*info['speed']) * (1.12 - 0.08 * k)
        self.max_hp = (70 + 60 * (k - 1)) * info['hp'] * hp_mult
        self.hp = self.max_hp
        self.armor = info.get('armor', 0)
        self.max_armor = self.armor
        self.x, self.y = float(x), float(LANE_Y[lane])
        self.lane = lane
        self.vy = 0.0
        self.dir = -1
        self.scale = self.size / SHEET_H
        self.state, self.state_t = 'walk', 0.0
        self.anim_t = random.uniform(0, 3)
        self.kneel_t = 0.0
        self.kneel_age = 0.0                     # 이번에 주저앉은 뒤 지난 시간 (모션용)
        self.grab_cd = 0.0
        self.turn_t = random.uniform(2, 5)       # 날뛰는 거인: 방향 바꾸기
        self.climb_cd = random.uniform(2, 5)     # 벽 타는 거인
        self.guard_t, self.guard_cd = 0.0, 3.0   # 영리한 거인: 목덜미 가리기
        self.throw_cd = 2.5                      # 돌 던지는 거인
        self.blast_cd = 8.0                      # 거대 거인
        self.steam_t = 0.0
        self.flash_t = 0.0
        self.crit = False                        # 마지막으로 맞은 공격이 치명타였나
        self.waiting = False                     # 미리 서 있는 거인: 주인공이 다가올 때까지 제자리
        self.running = False
        self.run_t = 0.0                         # 남은 질주 시간
        self.run_cd = random.uniform(1.5, 5.0)   # 다음 질주까지
        self.step = random.uniform(0, 100)       # 걸어온 거리 (걷기·달리기 모션용)
        self.grabbed = False
        self.sheet = render.image('giant.png')
        self.sheet_armor = render.image('giant_armor.png')
        self.nape_img = render.image('nape.png')
        self.ring = render.image('ring.png')
        self.ring_dash = render.image('ring_dash.png')
        self.blast = render.image('dot.png')

    # ------------------------------------------------ 상태 조회
    def alive(self):
        return self.state != 'dead'

    def guarding(self):
        return self.guard_t > 0 and self.kneel_t <= 0

    def frame(self):
        if self.state == 'dead':
            return 'death', min(FRAMES['death'] - 1, int(self.state_t / DEATH_FRAME))
        if self.kneel_t > 0:
            # 주저앉은 채 또 베여도 다시 일어섰다 앉지 않는다: 앉는 모션은 처음 한 번만
            k = min(self.kneel_age, self.kneel_t)
            return 'kneel', min(2, int(k / 0.1))
        if self.state in ('grab', 'wall'):
            if self.state == 'wall':
                return 'grab', int(self.state_t / 0.15) % 4
            return 'grab', min(3, int((GRAB_TIME - self.state_t) / (GRAB_TIME / 4)))
        if self.state == 'throw':
            return 'throw', min(2, int((0.9 - self.state_t) / 0.3))
        if self.guarding():
            return 'guard', int(self.anim_t * 3) % 2
        if self.running:
            return 'run', int(self.step / (18 * self.k ** 0.5)) % 6
        return 'walk', int(self.step / (11 * self.k ** 0.5)) % 6

    def nape(self):
        """판정용 목덜미 위치. 무릎을 꿇으면 바로 주저앉은 높이로 계산한다."""
        if self.kneel_t > 0:
            dx, dy = NAPE['kneel'][2]
        else:
            row, fr = self.frame()
            dx, dy = NAPE[row][fr]
            if row == 'walk':
                dy = WALK_NAPE * SHEET_H
            elif row == 'run':
                dy = RUN_NAPE * SHEET_H
        return self.x + dx * self.scale * (-self.dir), self.y + dy * self.scale

    def neck_floor(self):
        return floor_of(self.nape()[1])

    def reach_x(self):
        return self.size * 0.14 + 22

    def get_bb(self):
        h = self.size * (KNEEL_NAPE + 0.12 if self.kneel_t > 0 else 1.0)
        return self.x - self.size * 0.15, self.y, self.x + self.size * 0.15, self.y + h

    def part_for(self, floor):
        """그 층에서 베면 어디를 베는가. 목 층 이상이면 목, 서 있는 층이면 발목, 그 사이는 몸통"""
        if self.lane is None:
            return None
        neck = self.neck_floor()
        top = self.get_bb()[3]
        if floor == neck or (floor == neck + 1 and floor <= 4 and top > LANE_Y[floor]):
            return 'neck'
        if floor > neck:
            return None
        if floor == self.lane:
            return 'ankle'
        if floor > self.lane:
            return 'body'
        return None

    # ------------------------------------------------ 피해
    def hit(self, part, dmg):
        """피해를 준다. (실제로 들어간 피해, 이번에 쓰러졌는가)를 돌려준다."""
        self.waiting = False
        self.crit = False
        if not self.alive():
            return 0.0, False
        nx, ny = self.nape()
        dmg *= PART_RATE[part]
        if part == 'neck':
            if self.armor > 0:
                effect.add(effect.Spark(nx, ny, (255, 220, 160)))
                effect.add(effect.FloatText(nx, ny + 20, '튕김! 발목부터 베어 껍질을 깨라', (255, 210, 150), 15))
                return 0.0, False
            if self.guarding():
                dmg *= 0.15
                effect.add(effect.FloatText(nx, ny + 20, '가렸다! 발목부터', (255, 220, 160), 15))
        elif part == 'ankle':
            if self.armor > 0:
                self.armor -= 1
                effect.add(effect.Spark(self.x, self.y + 20, (255, 220, 160)))
                effect.add(effect.FloatText(self.x, self.y + 50,
                                            '껍질 깨짐' if self.armor == 0 else f'껍질 {self.armor}', (255, 210, 150), 15))
            if self.kneel_t <= 0:
                self.kneel_age = 0.0
                camera.shake(0.08 * self.k)
                effect.steam(self.x, self.y + 6, 2 + self.k, self.size * 0.12, (170, 160, 150), 16 + 6 * self.k)
            self.kneel_t = 1.6 if self.kind == 'colossal' else KNEEL_TIME
            self.guard_t = 0.0
            if self.state in ('grab', 'throw'):
                self.state = 'walk'
        elif self.armor > 0:
            dmg *= 0.4
        # 손을 뻗는 중에 베이면 움찔하며 잡기를 놓친다
        if self.state == 'grab' and not self.grabbed:
            self.state = 'walk'
            self.grab_cd = 1.5
        # 매번 조금씩 다른 피해, 가끔 치명타
        self.crit = part != 'raw' and random.random() < CRIT_RATE
        dmg *= random.uniform(*DMG_SPREAD) * (CRIT_MULT if self.crit else 1.0)
        self.hp -= dmg
        self.flash_t = 0.12
        if part == 'neck':
            hx, hy = nx, ny
        elif part == 'ankle':
            hx, hy = self.x, self.y + 14
        else:
            hx, hy = self.x, play_mode.player.y + 18
        effect.add(effect.Spark(hx, hy, (255, 120, 100) if part == 'neck' else (255, 240, 230)))
        if part in PART_NAME and part != 'neck':
            effect.add(effect.FloatText(hx, hy + 24, PART_NAME[part], (230, 230, 230), 13))
            effect.damage_number(hx, hy + 46, dmg, self.crit, 18)
        if self.hp <= 0:
            self.die()
            return dmg, True
        return dmg, False

    def die(self):
        # 주저앉은 채 죽으면 일어서는 장면 없이 무릎 꿇은 모션부터 엎어진다
        self.state, self.state_t = 'dead', DEATH_FRAME * 2 if self.kneel_t > 0 else 0.0
        self.kneel_t = 0.0
        self.guard_t = 0.0
        nx, ny = self.nape()
        effect.steam(nx, ny, 8, self.size * 0.3, (245, 245, 245), self.size * 0.4)
        camera.shake(0.06 * self.k)
        if self.kind == 'colossal':
            self.explode(300)
        play_mode.on_giant_killed(self)

    def explode(self, radius, n=1):
        cx, cy = self.x, self.y + self.size * 0.5
        effect.burst(cx, cy, 18, (255, 170, 90), 80, 320)
        effect.add(effect.Ring(cx, cy, radius, (255, 190, 140), 0.6))
        camera.shake(0.5)
        p = play_mode.player
        px, py = p.center()
        if math.hypot(px - cx, py - cy) < radius:
            p.hurt(cx, n)
        for a in play_mode.allies():
            ax, ay = a.center()
            if math.hypot(ax - cx, ay - cy) < radius:
                a.hurt(cx, 2)
        for c in play_mode.carts():
            if abs(c.x - cx) < radius:
                c.damage(4, cx)

    # ------------------------------------------------ 갱신
    def update(self, dt):
        if self.waiting:
            if abs(play_mode.player.x - self.x) > WAKE_DIST:
                return
            self.waiting = False
        self.anim_t += dt
        self.state_t += dt if self.state in ('dead', 'wall') else -dt
        self.flash_t = max(0.0, self.flash_t - dt)
        self.grab_cd = max(0.0, self.grab_cd - dt)
        if self.state == 'dead':
            self.steam_t -= dt
            if self.steam_t <= 0 and self.state_t < 1.8:
                self.steam_t = 0.25
                nx, ny = self.nape()
                effect.steam(nx, ny, 2, self.size * 0.2, (235, 235, 235), self.size * 0.3)
            if self.state_t > DEAD_FADE[1]:
                game_world.remove_object(self)
            return

        if self.lane is None:
            self.fall(dt)
            return
        if self.kneel_t > 0:
            self.kneel_t -= dt
            self.kneel_age += dt
            return
        if self.kind == 'colossal':
            self.colossal(dt)

        if self.state == 'grab':
            self.update_grab()
        elif self.state == 'throw':
            if self.state_t < 0.45 and not self.grabbed:
                self.grabbed = True
                self.throw_rock()
            if self.state_t <= 0:
                self.state = 'walk'
        elif self.state == 'climb':
            self.y += 70 * dt
            if self.y >= LANE_Y[self.lane + 1]:
                self.lane += 1
                self.y = LANE_Y[self.lane]
                self.state = 'walk'
        elif self.state == 'wall':
            dps = 0.22 * self.k * (2.0 if self.boss else 1.0)
            play_mode.wall.damage(dps * dt)
            if int(self.state_t / 0.6) != int((self.state_t - dt) / 0.6):
                effect.steam(WALL_X + 5, self.y + self.size * 0.6, 2, 12, (150, 140, 130), 22)
        else:
            self.walk(dt)

    def walk(self, dt):
        speed = self.speed
        if self.kind == 'erratic':
            self.turn_t -= dt
            if self.turn_t <= 0:
                if self.dir < 0 and random.random() < 0.5:
                    self.dir, self.turn_t = 1, random.uniform(0.8, 1.6)
                else:
                    self.dir, self.turn_t = -1, random.uniform(2.0, 4.0)
            speed *= 1.0 + 0.5 * max(0.0, math.sin(self.anim_t * 2.3))
        elif self.kind == 'climber':
            self.climb_cd -= dt
            if self.climb_cd <= 0 and self.lane < max_lane(self.k):
                self.climb_cd = random.uniform(3, 6)
                seg = map_data.segment_at(self.lane + 1, self.x)
                if seg and seg[0] + 40 < self.x < seg[1] - 80:
                    self.state = 'climb'
                    return
        elif self.kind == 'smart':
            self.guard_cd -= dt
            self.guard_t = max(0.0, self.guard_t - dt)
            p = play_mode.player
            nx, ny = self.nape()
            near = math.hypot(p.x - nx, p.y + 18 - ny) < 140
            if self.guard_t <= 0 and (self.guard_cd <= 0 or (near and self.guard_cd < 2.0)):
                self.guard_t, self.guard_cd = 1.4, 4.0
            if self.guarding():
                speed *= 0.4
        elif self.kind == 'thrower':
            self.throw_cd -= dt
            p = play_mode.player
            if self.throw_cd <= 0 and abs(p.x - self.x) < 800 and p.x < self.x:
                self.throw_cd = 3.2
                self.state, self.state_t = 'throw', 0.9
                self.grabbed = False
                return

        speed = self.update_run(dt, speed)
        self.x += self.dir * speed * dt
        self.step += speed * dt
        if self.x > FORTRESS_X:
            self.x, self.dir = FORTRESS_X, -1
        stop = WALL_X + self.size * 0.14 + 6
        if self.lane == 0 and self.x <= stop:
            self.x = stop
            self.state, self.state_t = 'wall', 0.0
            return
        if not map_data.segment_at(self.lane, self.x):
            self.lane = None
            self.vy = 0.0
            return
        self.try_grab()

    def update_run(self, dt, speed):
        """멀리 있으면 늘 달리고, 가까이에선 가끔 갑자기 질주한다. 달리는 속도를 돌려준다."""
        self.run_t = max(0.0, self.run_t - dt)
        self.run_cd -= dt
        if self.run_cd <= 0:
            self.run_t = random.uniform(1.2, 2.6)
            self.run_cd = self.run_t + (random.uniform(1.5, 4.0) if self.kind == 'erratic' else random.uniform(3.0, 8.0))
        far = abs(play_mode.player.x - self.x) > RUN_FAR
        was = self.running
        self.running = self.kind not in NO_RUN and not self.guarding() and (far or self.run_t > 0)
        if not self.running:
            return speed
        # 땅을 박차는 발걸음마다 흙먼지
        if int(self.step / (18 * self.k ** 0.5)) % 3 == 0 and camera.visible(self.x - 60, self.x + 60) and                 int((self.step - speed * dt * RUN_MULT) / (18 * self.k ** 0.5)) % 3 != 0:
            effect.steam(self.x, self.y + 4, 1 + self.k // 2, self.size * 0.06, (170, 160, 150), 10 + 4 * self.k)
        if not was:
            self.step = 0.0
        return speed * RUN_MULT

    def fall(self, dt):
        self.vy -= GRAVITY * dt
        y_prev = self.y
        self.y += self.vy * dt
        self.x += self.dir * self.speed * 0.5 * dt
        lane = map_data.landing_lane(self.x, y_prev, self.y)
        if lane is not None:
            self.y, self.lane, self.vy = LANE_Y[lane], lane, 0.0
            effect.steam(self.x, self.y, 2 + self.k, self.size * 0.15, (170, 160, 150), 16 + 6 * self.k)
            camera.shake(0.08 * self.k)

    def player_in_grab_zone(self, front, extra=0.0):
        return self.in_grab_zone(*play_mode.player.center(), front, extra)

    def in_grab_zone(self, cx, cy, front, extra=0.0):
        """앞쪽, 손이 닿는 높이(키의 15~55%)만 잡힌다. 목 높이와 (크기 2 이상의) 발목 높이는 안전하다."""
        rel = (cx - self.x) * self.dir
        low, high = self.y + self.size * 0.15, self.y + self.size * 0.55
        if self.k == 1:
            low = self.y
        return 0 < rel < self.size * front + 20 + extra and low < cy < high

    def try_grab(self):
        p = play_mode.player
        if self.grab_cd > 0 or p.invuln > 0:
            return
        if self.player_in_grab_zone(0.25):
            self.state, self.state_t = 'grab', GRAB_TIME
            self.grabbed = False

    def update_grab(self):
        if not self.grabbed and self.state_t < GRAB_HIT_AT:
            self.grabbed = True
            if self.player_in_grab_zone(0.3, 10):
                play_mode.player.hurt(self.x, self.power())
            for a in play_mode.allies():
                if self.in_grab_zone(*a.center(), 0.3, 10):
                    a.hurt(self.x)
        if self.state_t <= 0:
            self.state = 'walk'
            self.grab_cd = GRAB_CD

    def power(self):
        """주인공에게 주는 피해. 크기 3 이상이거나 보스면 2"""
        return 2 if self.k >= 3 or self.boss else 1

    def throw_rock(self):
        p = play_mode.player
        hx, hy = self.x - self.size * 0.1, self.y + self.size * 1.05
        game_world.add_object(Rock(hx, hy, p.x, p.y + 18), LAYER_PROJECTILE)

    def colossal(self, dt):
        self.steam_t -= dt
        if self.steam_t <= 0:
            self.steam_t = 0.3
            effect.steam(self.x + random.uniform(-60, 60), self.y + self.size * random.uniform(0.3, 0.9),
                         1, 30, (230, 210, 200), 60)
        self.blast_cd -= dt
        if self.blast_cd <= 0:
            self.blast_cd = 9.0
            self.explode(BLAST_R, 2)

    # ------------------------------------------------ 그리기
    def draw_danger(self):
        """곧 공격이 들어올 자리를 빨갛게 칠한다. 들어올 때가 가까울수록 진해진다."""
        if self.state == 'grab' and not self.grabbed:
            # 잡기: 손이 닿는 앞쪽, 키의 15~55% 높이 (in_grab_zone 과 같은 범위)
            k = min(1.0, (GRAB_TIME - self.state_t) / (GRAB_TIME - GRAB_HIT_AT))
            reach = self.size * 0.3 + 30
            low = self.y if self.k == 1 else self.y + self.size * 0.15
            high = self.y + self.size * 0.55
            x1, x2 = sorted((self.x, self.x + self.dir * reach))
            sx1, sy1 = camera.to_screen(x1, low)
            sx2, sy2 = camera.to_screen(x2, high)
            render.rect(sx1, sy1, sx2, sy2, DANGER, 40 + 90 * k)
            # 손끝 쪽에서 몸 쪽으로 차오르는 띠: 다 차면 잡힌다
            fill = (sx2 - sx1) * k
            if self.dir < 0:
                render.rect(sx1, sy1, sx1 + fill, sy1 + 4, DANGER, 230)
            else:
                render.rect(sx2 - fill, sy1, sx2, sy1 + 4, DANGER, 230)
        if self.kind == 'colossal' and self.alive() and self.blast_cd < BLAST_WARN:
            k = 1 - self.blast_cd / BLAST_WARN
            cx, cy = camera.to_screen(self.x, self.y + self.size * 0.5)
            render.tint(self.blast, DANGER, 0.25 + 0.35 * k)
            self.blast.draw(cx, cy, BLAST_R * 2, BLAST_R * 2)
            render.untint(self.blast)
            render.tint(self.ring, DANGER, 0.9)
            r = BLAST_R * 2 * k
            self.ring.draw(cx, cy, r, r)
            render.untint(self.ring)

    def draw_body(self):
        """몸은 길보다 뒤에 그린다 (큰 거인이 여러 층에 걸쳐 서 있으므로)"""
        if not camera.visible(self.x - self.size * 0.5, self.x + self.size * 0.5):
            return
        row, fr = self.frame()
        r = ROWS.index(row)
        img = self.sheet_armor if self.armor > 0 else self.sheet
        skin = zone_color(self.x, 'skin')
        if self.kind == 'colossal':
            skin = (skin[0], int(skin[1] * 0.78), int(skin[2] * 0.7))
        alpha = 1.0
        if self.state == 'dead' and self.state_t > DEAD_FADE[0]:
            alpha = max(0.0, 1 - (self.state_t - DEAD_FADE[0]) / (DEAD_FADE[1] - DEAD_FADE[0]))
        if self.flash_t > 0:
            skin = (255, 255, 255)
        render.tint(img, skin, alpha)
        w = CELL * self.scale
        sx, sy = camera.to_screen(self.x, self.y)
        img.clip_composite_draw(fr * CELL_PX, (len(ROWS) - 1 - r) * CELL_PX, CELL_PX, CELL_PX, 0,
                                'h' if self.dir > 0 else '', sx, sy + (CELL / 2 - META['base']) * self.scale, w, w)
        render.untint(img)

    def draw(self):
        """약점 표시는 길 위에 그린다."""
        if not self.alive() or not camera.visible(self.x - self.size * 0.5, self.x + self.size * 0.5):
            return
        sx, sy = camera.to_screen(self.x, self.y)
        nx, ny = self.nape()
        nsx, nsy = camera.to_screen(nx, ny)
        s = max(12.0, self.size * 0.09) * (1 + 0.12 * math.sin(self.anim_t * 6))
        self.nape_img.opacify(0.35 if self.guarding() or self.armor > 0 else 1.0)
        self.nape_img.draw(nsx, nsy, s, s)
        self.nape_img.opacify(1.0)

        # 목덜미를 벨 수 있는 자리에 있으면 표시
        p = play_mode.player
        if abs(p.x - self.x) <= self.reach_x() + SLASH_REACH and self.part_for(p.floor()) == 'neck':
            render.tint(self.ring, (255, 110, 90), 0.9)
            self.ring.draw(nsx, nsy, s * 2.4, s * 2.4)
            render.untint(self.ring)

        self.draw_danger()

        # 손을 뻗는 중: 곧 잡힌다는 경고
        if self.state == 'grab' and not self.grabbed:
            a = 0.6 + 0.4 * math.sin(self.anim_t * 30)
            render.text('!', nsx, nsy + 44, 30, (255, 80, 60), 'center', alpha=a)

        if self.max_armor > 0 and self.armor > 0:
            for i in range(self.armor):
                render.rect(nsx - self.armor * 6 + i * 12, nsy + 22, nsx - self.armor * 6 + i * 12 + 9,
                            nsy + 27, (220, 180, 130), 230)
        if not self.boss and self.hp < self.max_hp:
            k = max(0.0, self.hp / self.max_hp)
            render.rect(nsx - 16, nsy + 14, nsx + 16, nsy + 17, (0, 0, 0), 140)
            render.rect(nsx - 16, nsy + 14, nsx - 16 + 32 * k, nsy + 17, (230, 90, 70), 220)
        # 크기 표시
        render.text(f'{self.k}', sx, sy + self.size * (KNEEL_NAPE if self.kneel_t > 0 else 1.0) + 12, 12,
                    (230, 220, 210), 'center', alpha=0.7)
