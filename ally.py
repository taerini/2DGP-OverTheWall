import math
import random

import camera
import effect
import play_mode
import render
from config import *
from player import CELL, BASE, ROWS, ATTACK

SPEED = 520.0
ALLY_HP = 6
SWAT_RATE = 0.2          # 서 있는 거인을 벨 때 손에 맞을 확률 (무릎 꿇은 거인은 반격하지 못한다)
REGEN_DELAY = 4.0        # 이만큼 안 맞으면
REGEN_TIME = 6.0         # 이 간격으로 체력 1 회복
DOWN_TIME = 12.0         # 쓰러지면 우리 벽으로 물러나 이만큼 쉬었다가 돌아온다
ASSAULT_X = FORTRESS_X - 900   # 주인공이 여기보다 앞이면 남는 동료는 요새를 친다
SCALE = 0.85             # 주인공과 헷갈리지 않게 조금 작게 그린다


class Ally:
    """강화로 들어오는 동료의 공통 부분: 주인공 근처를 날아다니고, 체력이 있다."""
    COLOR = (255, 255, 255)
    NAME = ''
    FORT_DMG = 8.0
    FORT_CD = 1.6

    def __init__(self, index):
        self.image = render.image('ally.png')
        self.index = index
        p = play_mode.player
        self.x, self.y = p.x - 40, p.y + 60
        self.vx = self.vy = 0.0
        self.face = 1
        self.slash_t = 0.0
        self.anim_t = 0.0
        self.max_hp = ALLY_HP
        self.hp = self.max_hp
        self.invuln = 0.0
        self.safe_t = 0.0        # 마지막으로 맞은 뒤 지난 시간
        self.regen_t = 0.0
        self.down_t = 0.0
        self.fort_cd = 1.0

    # ------------------------------------------------ 체력
    def alive(self):
        return self.down_t <= 0

    def center(self):
        return self.x, self.y + 18

    def hurt(self, src_x, n=1):
        if not self.alive() or self.invuln > 0:
            return
        self.hp -= n
        self.invuln = 0.8
        self.safe_t = 0.0
        d = 1 if self.x >= src_x else -1
        self.vx, self.vy = d * 380.0, 260.0
        effect.add(effect.FloatText(self.x, self.y + 60, f'-{n}', (255, 130, 110), 15))
        if self.hp <= 0:
            self.down_t = DOWN_TIME
            effect.add(effect.FloatText(self.x, self.y + 74, f'{self.NAME} 후퇴!', (255, 150, 130), 15))
            effect.steam(self.x, self.y + 18, 3, 14, (220, 220, 220), 20)

    def counter(self, g):
        """거인을 베고 나서 반격을 받을 수도 있다"""
        if g.alive() and g.kneel_t <= 0 and random.random() < SWAT_RATE:
            self.hurt(g.x)

    def heal(self, more=0):
        self.max_hp += more
        self.hp = self.max_hp
        if self.down_t > 0:
            self.down_t = 0.01

    def tick(self, dt):
        """공통 갱신. 쓰러져 있으면 True 를 돌려준다."""
        self.anim_t += dt
        self.slash_t = max(0.0, self.slash_t - dt)
        self.invuln = max(0.0, self.invuln - dt)
        self.fort_cd = max(0.0, self.fort_cd - dt)
        if self.down_t > 0:
            self.down_t -= dt
            self.fly_to(WALL_X + 40 + 24 * (self.index % 5), LANE_Y[0] + 10, dt, SPEED * 0.6)
            if self.down_t <= 0:
                self.hp = self.max_hp
                self.invuln = 1.5
                effect.add(effect.FloatText(self.x, self.y + 60, f'{self.NAME} 복귀', (170, 230, 180), 14))
            return True
        self.safe_t += dt
        if self.safe_t > REGEN_DELAY and self.hp < self.max_hp:
            self.regen_t += dt
            if self.regen_t >= REGEN_TIME:
                self.regen_t = 0.0
                self.hp += 1
        return False

    # ------------------------------------------------ 움직임
    def nearest_giant(self, limit):
        p = play_mode.player
        best, best_d = None, limit
        for g in play_mode.giants():
            if g.alive() and g.lane is not None:
                d = abs(g.x - p.x)
                if d < best_d:
                    best, best_d = g, d
        return best

    def fly_to(self, gx, gy, dt, speed=SPEED):
        dx, dy = gx - self.x, gy - self.y
        d = math.hypot(dx, dy)
        want = min(speed, d * 4)
        tvx, tvy = (dx / d * want, dy / d * want) if d > 1 else (0.0, 0.0)
        k = min(1.0, dt * 6)
        self.vx += (tvx - self.vx) * k
        self.vy += (tvy - self.vy) * k
        self.move(dt)

    def move(self, dt):
        self.x = max(WALL_X + 10, min(FORTRESS_X, self.x + self.vx * dt))
        self.y = max(LANE_Y[0], min(SCREEN_H - 60, self.y + self.vy * dt))
        if abs(self.vx) > 20:
            self.face = 1 if self.vx > 0 else -1

    def follow(self, dt):
        p = play_mode.player
        i, row = self.index % 4, self.index // 4
        gx = p.x - p.face * (40 + 30 * i + 18 * row)
        gy = p.y + 50 + 22 * i + 12 * row + 8 * math.sin(self.anim_t * 2 + self.index)
        self.fly_to(gx, gy, dt)

    def idle(self, dt):
        """칠 거인이 없을 때: 주인공이 요새 앞까지 왔으면 요새를 치고, 아니면 따라다닌다."""
        if play_mode.player.x < ASSAULT_X:
            self.follow(dt)
            return
        tx = FORTRESS_X - 16
        ty = LANE_Y[0] + 60 + 70 * (self.index % 6) + 6 * math.sin(self.anim_t * 3 + self.index)
        self.fly_to(tx, ty, dt, SPEED * 1.1)
        if self.fort_cd <= 0 and abs(tx - self.x) < 40 and abs(ty - self.y) < 40:
            self.fort_cd = self.FORT_CD
            self.face = 1
            self.slash_t = 0.26
            effect.add(effect.Slash(self, 'Q', 1, 60, 22))
            play_mode.fortress.damage(self.FORT_DMG * play_mode.player.blade, self.x + 20, self.y + 18)

    # ------------------------------------------------ 그리기
    def draw(self):
        if not camera.visible(self.x - 40, self.x + 40):
            return
        rad = 0.0
        if self.slash_t > 0:
            row, fr = 'slashQ', min(3, int((0.26 - self.slash_t) / 0.065))
        elif math.hypot(self.vx, self.vy) > 120:
            row, fr = 'wire', int(self.anim_t * 14) % 4
            rad = max(-0.9, min(0.9, math.atan2(self.vy, max(1.0, self.vx * self.face))))
        else:
            row, fr = 'air', 1
        r = ROWS.index(row)
        alpha = 0.4 if not self.alive() or (self.invuln > 0 and int(self.invuln * 12) % 2) else 1.0
        # 망토는 모두 조사병단 초록. 누구인지는 이름 색으로 구분한다
        self.image.opacify(alpha)
        sx, sy = camera.to_screen(self.x, self.y)
        self.image.clip_composite_draw(fr * CELL, (len(ROWS) - 1 - r) * CELL, CELL, CELL, rad * self.face,
                                       '' if self.face > 0 else 'h', sx, sy + (CELL / 2 - BASE) * SCALE,
                                       CELL * SCALE, CELL * SCALE)
        self.image.opacify(1.0)
        if not self.alive():
            render.text(f'회복 {int(self.down_t) + 1}', sx, sy + 50, 11, (200, 200, 200), 'center', alpha=0.8)
            return
        render.text(self.NAME, sx, sy + 56, 11, self.COLOR, 'center', alpha=0.8)
        k = self.hp / self.max_hp
        render.rect(sx - 12, sy + 45, sx + 12, sy + 48, (10, 10, 14), 160)
        render.rect(sx - 12, sy + 45, sx - 12 + 24 * k, sy + 48, (120, 220, 130) if k > 0.34 else (255, 120, 90), 230)


class Levi(Ally):
    """한 거인의 목덜미로 날아가 정확히 벤다. 공격력 100%, 한 번에 1마리."""
    COLOR = (160, 195, 255)
    NAME = '리바이'
    COOLDOWN = 1.6
    POWER = 1.0

    def __init__(self, index):
        super().__init__(index)
        self.target = None
        self.cd = 1.0

    def update(self, dt):
        self.cd = max(0.0, self.cd - dt)
        if self.tick(dt):
            return
        if self.target is None or not self.target.alive():
            self.target = self.nearest_giant(480)
        if self.target is None:
            self.idle(dt)
            return
        nx, ny = self.target.nape()
        self.fly_to(nx - self.target.dir * 14, ny - 10, dt)
        if self.cd <= 0 and math.hypot(nx - self.x, ny - self.y - 18) < self.target.reach_x():
            dealt, killed = self.target.hit('neck', ATTACK * self.POWER * play_mode.player.blade)
            if dealt > 0:
                play_mode.neck_juice(self.target, dealt, killed, self.face, big=False)
            effect.add(effect.Slash(self, 'Q', self.face, 60, 22))
            self.cd = self.COOLDOWN
            self.slash_t = 0.26
            self.counter(self.target)


class Scout(Levi):
    """조사병: 리바이처럼 움직이지만 느리고 약하다. 공격력 50%."""
    COLOR = (200, 210, 170)
    NAME = '조사병'
    COOLDOWN = 2.2
    POWER = 0.5
    FORT_DMG = 5.0
    FORT_CD = 2.0


class Mikasa(Ally):
    """거인들의 목 높이로 앞으로 쭉 돌진하며 지나가는 거인을 우르르 벤다. 공격력 70%, 최대 3마리."""
    COLOR = (255, 175, 165)
    NAME = '미카사'
    COOLDOWN = 3.5
    DASH_SPEED = 1150.0
    DASH_LEN = 650.0
    MAX_HITS = 3
    FORT_DMG = 14.0
    FORT_CD = 2.4

    def __init__(self, index):
        super().__init__(index)
        self.cd = 1.5
        self.dash = None     # [방향, 목표 높이, 남은 거리, 벤 거인들]

    def update(self, dt):
        self.cd = max(0.0, self.cd - dt)
        if self.tick(dt):
            self.dash = None
            return
        if self.dash:
            self.do_dash(dt)
            return
        target = self.nearest_giant(650)
        if target is None:
            self.idle(dt)
            return
        nx, ny = target.nape()
        d = 1 if nx >= self.x else -1
        # 돌진 출발점: 목표 거인 앞쪽 200px, 목 높이
        sx, sy = nx - d * 220, ny - 18
        self.fly_to(sx, sy, dt, SPEED * 1.2)
        if self.cd <= 0 and math.hypot(sx - self.x, sy - self.y) < 50:
            self.dash = [d, ny - 18, self.DASH_LEN, []]
            self.face = d

    def do_dash(self, dt):
        d, dy, left, hit = self.dash
        step = self.DASH_SPEED * dt
        self.vx, self.vy = d * self.DASH_SPEED, (dy - self.y) * 8
        self.move(dt)
        self.dash[2] -= step
        if int(self.dash[2] / 40) != int((self.dash[2] + step) / 40):
            effect.add(effect.Puff(self.x, self.y + 18, (255, 220, 215), 18, 0.35, 0, 0, 0.45))
        for g in play_mode.giants():
            if len(hit) >= self.MAX_HITS:
                break
            if not g.alive() or g in hit:
                continue
            nx, ny = g.nape()
            if abs(nx - self.x) < g.reach_x() and abs(ny - (self.y + 18)) < 70:
                hit.append(g)
                dealt, killed = g.hit('neck', ATTACK * 0.7 * play_mode.player.blade)
                if dealt > 0:
                    play_mode.neck_juice(g, dealt, killed, self.face, big=False)
                effect.add(effect.Slash(self, 'Q', self.face, 64, 22))
                self.slash_t = 0.26
        if self.dash[2] <= 0 or len(hit) >= self.MAX_HITS or self.x <= WALL_X + 12 or self.x >= FORTRESS_X:
            # 한 번 돌진에 반격은 한 번만 받는다
            if hit:
                self.counter(hit[-1])
            self.dash = None
            self.cd = self.COOLDOWN
            self.vx *= 0.3
