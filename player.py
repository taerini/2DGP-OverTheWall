import json
import math

import camera
import effect
import map_data
import play_mode
import render
import sound
from config import *
from giant import floor_of
from state_machine import StateMachine, wire_fire, arrive, fall, land, tornado

# 주인공 시트 (resource/hero/, tools/make_hero.py): 애니메이션풍 PixelLab 캐릭터. 줄마다 프레임 수가 다르다 (부드럽게 대부분 16장)
with open('resource/hero/hero_meta.json') as _f:
    _META = json.load(_f)
CELL, BASE = _META['cell'][0], _META['base']
DRAW = CELL * HERO_HEIGHT / _META['height']   # 화면에 그리는 칸 크기: 서 있는 키가 HERO_HEIGHT 가 되게
ROWS = [name for name, _ in _META['rows']]
FRAMES = {name: n for name, n in _META['rows']}   # air 는 앞 절반 상승, 뒤 절반 하강


LAUNCH_CROUCH = 7       # launch 줄에서 웅크리는 장 수
AIR_RISE_V = 650.0      # 이 속도 이상으로 오르면 공중 줄 첫 장, 0 에 가까우면 상승 마지막 장
AIR_FALL_V = 750.0      # 이 속도 이상으로 떨어지면 하강 마지막 장


def smooth(k):
    """0~1 을 처음과 끝이 부드럽게 잇는다"""
    return k * k * (3 - 2 * k)


def loop(row, t, fps8):
    """반복 동작의 프레임: 8장 기준 초당 fps8 장 빠르기를 줄 길이에 맞춘다 (16장이면 두 배로 넘겨 한 바퀴 시간이 같다)"""
    return int(t * fps8 * FRAMES[row] / 8) % FRAMES[row]

WALK_SPEED = 130.0
RUN_MAX = 440.0
GAS_MAX = 100.0
START_HP = 100.0             # 처음 체력 (생명은 하나뿐). 게이지로 보이고 버티는 동안 천천히 다시 찬다
HIT_DMG = 10.0               # 거인 공격 한 번(세기 1)에 깎이는 체력
REGEN = 1.5                  # 초당 다시 차는 체력
REGEN_DELAY = 3.0            # 마지막으로 맞은 뒤 이만큼 지나야 차기 시작한다
WIRE_COST = 6.0
REEL_SPEED = 780.0
ATTACK = 40.0                # 처음 공격력 (칼날 강화로 오른다). 목덜미 100%, 몸통 15%
Q_COOLDOWN = 0.35
TORNADO_CD = Q_COOLDOWN   # 회오리도 Q 처럼 제한 없이 쓴다
TORNADO_RISE = 0.4
FORT_DAMAGE = 6.0            # 혼자 요새를 베면 오래 걸린다
PART_ORDER = {'neck': 0, 'ankle': 1, 'body': 2}
AIR_NECK_V = 75.0           # 공중에서 목덜미와 이만큼 높이 차이 안이면 목을 벤다
DEATH_KNOCK = (360.0, 460.0)  # 쓰러질 때 뒤로 튕겨 나가는 속도 (가로, 위)
DEATH_ANIM = 0.9            # 쓰러지는 모션(death 줄 8장) 시간. 끝나면 마지막 장(누운 자세) 그대로


class Ground:
    def __init__(self, p):
        self.p = p

    def enter(self, e):
        p = self.p
        p.vy = 0.0
        if e[0] == 'LAND' and p.land_speed < -HERO_LAND_SPEED:
            # 세게 착지: 빠를수록 깊고 오래 웅크리고, 먼지와 흔들림도 커진다
            k = min(1.0, (-p.land_speed - HERO_LAND_SPEED) / (HERO_FALL_MAX - HERO_LAND_SPEED))
            p.land_t = p.land_total = 0.22 + 0.16 * k
            p.vx *= 0.35
            for d in (-1, 1):
                for i in range(2 + int(2 * k)):
                    effect.add(effect.Puff(p.x + d * (6 + i * 7), p.y + 3, (205, 198, 184), 14 + 7 * i, 0.4,
                                           d * (70 + 45 * i), 14, 0.55))
            camera.shake(0.08 + 0.12 * k, 2 + 4 * k)
            sound.sfx('land')

    def exit(self, e):
        self.p.curve_k = self.p.land_t = self.p.recover_t = 0.0

    def curve(self, dt, target):
        """급커브: 들어가며 감속 → 한가운데서 가장 느림 → 빠져나오며 다시 가속.
        실제 속력 × 진행 방향의 가로 성분이 화면의 가로 속도다. 도는 중에 원래 쪽을 고르면 되돌아 나온다"""
        p = self.p
        was = p.curve_k
        back = target * p.curve_from > 0
        k = was + (-dt if back else dt) / HERO_CURVE_TIME
        if int(k * 16) != int(was * 16):            # 발이 땅을 긁으며 바깥쪽으로 흙먼지가 튄다
            load = math.sin(math.pi * min(1.0, max(0.0, k)))
            effect.add(effect.Puff(p.x + p.curve_from * 8, p.y + 3, (205, 198, 184), 10 + 9 * load, 0.3,
                                   p.curve_from * 55 * load, 16, 0.3 + 0.25 * load))
        if was < 0.5 <= k:
            sound.sfx('dash')
        if k >= 1.0 or k <= 0.0:
            out = k >= 1.0
            p.vx = -p.curve_v * HERO_CURVE_EXIT if out else p.curve_v
            p.face = 1 if p.vx > 0 else -1
            p.curve_k = 0.0
            p.run_phase = 0.3                       # 커브 그림 마지막이 달리기 3번째 장과 이어진다
            p.recover_t = HERO_CURVE_RECOVER if out else 0.0
        else:
            p.curve_k = k
            if k < 0.5:
                speed = 1 + (HERO_CURVE_MIN - 1) * smooth(k * 2)
            else:
                speed = HERO_CURVE_MIN + (HERO_CURVE_EXIT - HERO_CURVE_MIN) * smooth(k * 2 - 1)
            p.vx = p.curve_v * speed * math.cos(math.pi * smooth(k))
            p.face = p.curve_from if k < 0.5 else -p.curve_from
        p.move_x(p.vx * dt)

    def do(self, dt):
        # 달리기는 가스를 쓰지 않는다. 땅에 있으면 가스가 천천히 찬다.
        p = self.p
        if p.auto_x is not None:     # 시작 장면: 성문에서 걸어 나온다
            dx = p.auto_x - p.x
            p.vx = math.copysign(min(RUN_MAX * 0.8, abs(dx) * 4), dx) if abs(dx) > 4 else 0.0   # 성벽 속에서 달려 나온다
            if abs(p.vx) > 20:
                p.face = 1 if p.vx > 0 else -1
            p.x += p.vx * dt                  # 성문(벽 안쪽)에서 나오므로 벽 경계에 막히지 않게 직접 옮긴다
            return
        if p.dead:                   # 쓰러졌으면 조작 없이 미끄러지다 멈춘다
            p.vx = math.copysign(max(0.0, abs(p.vx) - 1400 * dt), p.vx)
            p.move_x(p.vx * dt)
            if not map_data.segment_at(p.lane, p.x):
                p.state_machine.handle_event(('FALL', None))
            return
        mx, _ = camera.to_world(*p.mouse)
        dx = mx - p.x
        target = 0.0
        if abs(dx) > 4:              # 서 있지 않는다: 목표 바로 앞까지 천천히라도 달린다
            target = math.copysign(max(HERO_JOG, min(RUN_MAX, abs(dx) * 2.0)), dx)
        if p.land_t > 0:             # 착지 충격을 받는 동안은 거의 못 나아간다
            p.land_t = max(0.0, p.land_t - dt)
            target *= 0.2
        elif p.curve_k <= 0 and abs(p.vx) >= HERO_CURVE_SPEED and target * p.vx < 0:
            p.curve_k, p.curve_v, p.curve_from = 1e-6, p.vx, 1 if p.vx > 0 else -1
            sound.sfx('skid')
        if p.curve_k > 0:
            self.curve(dt, target)
            p.gas = min(p.gas_max, p.gas + 6 * dt)
            if not map_data.segment_at(p.lane, p.x):
                p.state_machine.handle_event(('FALL', None))
            return
        accel = 1700.0 if abs(target) > abs(p.vx) else 2600.0
        if p.recover_t > 0:          # 커브를 빠져나온 직후: 다시 속도를 붙이는 데 시간이 걸린다
            p.recover_t = max(0.0, p.recover_t - dt)
            if target * p.vx > 0 and abs(target) > abs(p.vx):
                accel = HERO_CURVE_ACCEL
        if p.vx < target:
            p.vx = min(target, p.vx + accel * dt)
        else:
            p.vx = max(target, p.vx - accel * dt)
        p.gas = min(p.gas_max, p.gas + 6 * dt)
        if abs(p.vx) > 20:
            p.face = 1 if p.vx > 0 else -1
        p.move_x(p.vx * dt)
        if not map_data.segment_at(p.lane, p.x):
            p.state_machine.handle_event(('FALL', None))


class Wire:
    def __init__(self, p):
        self.p = p

    def enter(self, e):
        p = self.p
        p.hook = e[1]
        p.rope = 0.0
        p.reeling = False
        p.hook_t = 0.0
        p.launching = p.lane is not None     # 땅에서 걸면 웅크렸다가 튀어 오른다
        p.hook_time = HERO_WIRE_WINDUP if p.launching else 0.05   # 거리와 상관없이 바로 걸린다
        p.launch_t = 0.0
        p.face = 1 if p.hook[0] >= p.x else -1

    def exit(self, e):
        self.p.hook = None

    def do(self, dt):
        p = self.p
        hx, hy = p.hook
        cx, cy = p.x, p.y + 16
        dist = math.hypot(hx - cx, hy - cy)
        if not p.reeling:
            # 갈고리가 날아가는 동안에는 하던 움직임을 이어 간다
            p.hook_t += dt
            p.rope = dist * min(1.0, p.hook_t / p.hook_time)
            if p.hook_t >= p.hook_time:
                p.reeling = True
                p.reel_speed = max(620.0 if p.launching else 360.0, math.hypot(p.vx, p.vy))
                if p.launching:
                    p.launch_t = HERO_WIRE_SPRING
                    effect.add(effect.Puff(p.x, p.y + 3, (205, 198, 184), 24, 0.32, 0, 18, 0.55))
                    sound.sfx('dash')
            if p.lane is None:
                p.vy -= GRAVITY * dt
                p.move_x(p.vx * dt)
                p.y += p.vy * dt
            else:
                p.vx *= 0.9
            return
        p.lane = None
        p.launch_t = max(0.0, p.launch_t - dt)
        top = REEL_SPEED * p.reel_mult
        p.reel_speed = min(top, p.reel_speed + 4200 * dt)
        step = p.reel_speed * dt
        if p.slash_t > 0:
            k = 1 - p.slash_t / p.slash_total
            if HERO_WIRE_SLASH_HIT < k < HERO_WIRE_SLASH_HIT + 0.2:
                step *= HERO_WIRE_SLASH_DASH  # 내리치는 순간 앞으로 튀어 나간다
                if not p.slash_struck:
                    p.slash_struck = True
                    camera.shake(0.12, 5)
        ux, uy = (hx - cx) / max(dist, 1e-3), (hy - cy) / max(dist, 1e-3)
        p.vx, p.vy = ux * p.reel_speed, uy * p.reel_speed
        if step >= dist - 14:
            # 도착: 살짝 튕겨 나가며 떨어진다
            p.x, p.y = hx - ux * 10, hy - 16 - uy * 10
            p.vx = ux * p.reel_speed * 0.5
            p.vy = 250 + max(0.0, uy * p.reel_speed * 0.3)
            # 튕겨 올라도 바로 위층까지는 넘지 않게: 고른 층에 내려앉는다
            lane = int((hy - LANE_Y[0]) // LANE_GAP)
            if lane < TOP_FLOOR:
                room = max(0.0, LANE_Y[lane + 1] - 12 - p.y)
                p.vy = min(p.vy, math.sqrt(2 * GRAVITY * room))
            p.state_machine.handle_event(('ARRIVE', None))
            return
        p.move_x(ux * step)
        p.y += uy * step


class Air:
    def __init__(self, p):
        self.p = p

    def enter(self, e):
        self.p.lane = None

    def exit(self, e):
        pass

    def do(self, dt):
        p = self.p
        mx, _ = camera.to_world(*p.mouse)
        target = max(-260.0, min(260.0, (mx - p.x) * 1.5))
        if p.hit_t <= 0 and not p.dead:
            p.vx += max(-420 * dt, min(420 * dt, target - p.vx))
        p.vy = max(-HERO_FALL_MAX, p.vy - GRAVITY * (HERO_FALL_GRAVITY if p.vy < 0 else 1.0) * dt)
        p.move_x(p.vx * dt)
        y_prev = p.y
        p.y += p.vy * dt
        if p.vy <= 0:
            lane = map_data.landing_lane(p.x, y_prev, p.y)
            if lane is not None:
                p.y = LANE_Y[lane]
                p.lane = lane
                p.land_speed = p.vy
                p.state_machine.handle_event(('LAND', None))


class Tornado:
    """회오리 베기: 회오리처럼 돌며 거인의 목 높이까지 수직으로 솟아올라 목덜미를 벤다."""

    def __init__(self, p):
        self.p = p

    def enter(self, e):
        p = self.p
        self.giant = e[1]
        self.t = 0.0
        self.y0 = p.y
        self.x0 = p.x
        p.lane = None
        p.vx = p.vy = 0.0
        p.anim_t = 0.0
        effect.add(effect.Slash(p, 'E', p.face, 70, 18, TORNADO_RISE + 0.1))

    def exit(self, e):
        pass

    def do(self, dt):
        p = self.p
        g = self.giant
        self.t += dt
        k = min(1.0, self.t / TORNADO_RISE)
        ease = 1 - (1 - k) ** 2
        nx, ny = g.nape()
        p.x = self.x0 + (nx + g.dir * 6 - self.x0) * ease
        p.y = self.y0 + (ny - 18 - self.y0) * ease
        if int(self.t / 0.05) != int((self.t - dt) / 0.05):
            effect.add(effect.Puff(p.x, p.y + 10, (220, 235, 255), 22, 0.4, 0, -20, 0.5))
        if k >= 1.0:
            if g.alive():
                dealt, killed = g.hit('neck', ATTACK * p.blade)
                if dealt > 0:
                    play_mode.neck_juice(g, dealt, killed, p.face)
            effect.add(effect.Slash(p, 'Q', p.face, 110, 22))
            p.vy = 220.0
            p.state_machine.handle_event(('ARRIVE', None))


class Player:
    def __init__(self):
        self.image = render.image('hero/hero.png')
        self.ring = render.image('ring_dash.png')
        self.x, self.y = WALL_X + 70.0, float(LANE_Y[0])
        self.vx = self.vy = 0.0
        self.face = 1
        self.lane = 0
        self.mouse = (SCREEN_W * 0.42, 300)
        self.hook, self.rope, self.reeling, self.reel_speed = None, 0.0, False, 0.0
        self.preview = None
        self.land_speed = 0.0
        self.anim_t = 0.0
        self.run_phase = 0.0          # 달리기 그림 진행: 달린 거리로 넘어간다
        self.turn_t = 0.0             # 방향 전환 그림이 남은 시간
        self.slash_t = 0.0            # 칼을 휘두르는 남은 시간
        self.slash_total = HERO_SLASH_TIME   # 이번 베기의 전체 시간
        self.slash_struck = False     # 와이어 베기: 내리치는 순간을 지났나
        self.curve_k, self.curve_v, self.curve_from = 0.0, 0.0, 1   # 커브: 진행 0~1 (0 이면 안 도는 중), 처음 속도, 달리던 방향
        self.recover_t = 0.0          # 커브 뒤 다시 가속하는 남은 시간
        self.land_t, self.land_total = 0.0, 1.0                  # 세게 착지: 남은 시간, 전체 시간
        self.hook_t, self.hook_time, self.launch_t = 0.0, 1.0, 0.0
        self.launching = False        # 와이어: 땅에서 웅크렸다 튀어 오르는 중인가
        self.hidden = False           # 시작 장면: 성문이 열리기 전에는 보이지 않는다
        self.auto_x = None            # 시작 장면: 마우스 대신 이 x 를 향해 걷는다

        # 강화로 바뀌는 값
        self.max_hp = START_HP
        self.hp = START_HP
        self.dead = False             # 생명은 하나뿐: 체력이 다하면 그대로 끝
        self.death_t = 0.0            # 쓰러진 뒤 지난 시간
        self.safe_t = 0.0             # 마지막으로 맞은 뒤 지난 시간 (체력이 다시 차는 조건)
        self.gas_max = GAS_MAX
        self.gas = GAS_MAX
        self.blade = 1.0
        self.gas_cost = 1.0
        self.reel_mult = 1.0
        self.has_tornado = False
        self.tornado_cd = TORNADO_CD

        self.cool = {'Q': 0.0, 'W': 0.0}
        self.invuln, self.hit_t = 0.0, 0.0

        self.GROUND = Ground(self)
        self.WIRE = Wire(self)
        self.AIR = Air(self)
        self.TORNADO = Tornado(self)
        self.state_machine = StateMachine(
            self.GROUND,
            {
                self.GROUND: {wire_fire: self.WIRE, fall: self.AIR, tornado: self.TORNADO},
                self.WIRE: {wire_fire: self.WIRE, arrive: self.AIR, fall: self.AIR, tornado: self.TORNADO},
                self.AIR: {wire_fire: self.WIRE, land: self.GROUND, tornado: self.TORNADO},
                self.TORNADO: {wire_fire: self.WIRE, arrive: self.AIR, fall: self.AIR},
            }
        )

    # ------------------------------------------------ 공용
    def center(self):
        return self.x, self.y + 18

    def floor(self):
        """지금 몇 층 높이에 있는가 (0부터)"""
        return floor_of(self.y + 10)

    def get_bb(self):
        return self.x - 7, self.y, self.x + 7, self.y + 36

    def move_x(self, dx):
        self.x = max(WALL_X + 10.0, min(FORTRESS_X - 8.0, self.x + dx))

    def use_gas(self, amount):
        self.gas = max(0.0, self.gas - amount * self.gas_cost)

    # ------------------------------------------------ 입력
    def fire_wire(self, sx, sy):
        # 클릭하면 언제든 바로 와이어를 건다 (가스가 없어도, 회오리 베기 중이어도)
        cx, cy = self.center()
        wx, wy = camera.to_world(sx, sy)
        target = map_data.find_anchor(cx, cy, wx, wy)
        if target is None:
            return
        self.use_gas(WIRE_COST)
        sound.sfx('wire')
        self.state_machine.handle_event(('WIRE', target))

    def slash(self):
        """Q: 달리거나 날아가는 그대로 칼을 휘두른다. 지금 있는 층에 따라 목덜미 또는 몸통에 맞는다."""
        if self.cool['Q'] > 0 or self.state_machine.cur_state is self.TORNADO:
            return
        self.cool['Q'] = Q_COOLDOWN
        floor = self.floor()
        best, best_key = None, None
        for g in play_mode.giants():
            if not g.alive() or abs(g.x - self.x) > g.reach_x() + SLASH_REACH:
                continue
            part = g.part_for(floor)
            # 공중(와이어 비행 중 포함)에서는 층과 상관없이 목덜미 높이를 지나가면 목을 벤다
            if self.lane is None and part != 'neck' and g.lane is not None:
                nx, ny = g.nape()
                if abs(ny - (self.y + 18)) < AIR_NECK_V:
                    part = 'neck'
            if part is None:
                continue
            if part == 'ankle':           # 주인공은 발목을 베지 않는다: 발치에서 베면 몸통에 맞는다
                part = 'body'
            key = (PART_ORDER[part], abs(g.x - self.x))
            if best_key is None or key < best_key:
                best, best_key = (g, part), key
        on_wire = self.state_machine.cur_state is self.WIRE and self.reeling
        self.slash_total = HERO_WIRE_SLASH_TIME if on_wire else HERO_SLASH_TIME
        self.slash_t = self.slash_total
        self.slash_struck = False
        sound.sfx('slash')
        if self.curve_k > 0 or self.land_t > 0 or self.turn_t > 0:   # 칼 휘두르는 그림을 못 쓰는 동작 중에는 궤적만
            effect.add(effect.Slash(self, 'Q', self.face, 110, 22))
        if best:
            g, part = best
            dealt, killed = g.hit(part, ATTACK * self.blade)
            if part == 'neck' and dealt > 0:
                self.face = 1 if g.nape()[0] >= self.x else -1
                play_mode.neck_juice(g, dealt, killed, self.face)
        if self.x >= FORTRESS_X - 110:
            play_mode.fortress.damage(FORT_DAMAGE * self.blade, self.x + 20, self.y + 18)

    def tornado(self):
        """W: 거인 발목 앞(같은 줄 땅 위)에 있을 때만, 그 거인의 목 높이까지 회오리처럼 솟아올라 목덜미를 벤다."""
        if not self.has_tornado or self.cool['W'] > 0 or self.state_machine.cur_state is self.TORNADO:
            return
        if self.lane is None:            # 공중·와이어 중에는 못 쓴다
            return
        floor = self.floor()
        best, best_d = None, 1e9
        for g in play_mode.giants():
            if not g.alive() or g.part_for(floor) != 'ankle':
                continue
            d = abs(g.x - self.x)
            if d <= g.reach_x() + SLASH_REACH and d < best_d:
                best, best_d = g, d
        if best is None:
            return
        self.cool['W'] = self.tornado_cd
        self.state_machine.handle_event(('TORNADO', best))

    def hurt(self, src_x, n=1):
        if self.invuln > 0:
            return
        dmg = n * HIT_DMG
        self.hp = max(0.0, self.hp - dmg)
        self.safe_t = 0.0
        self.invuln = 1.0
        self.hit_t = 0.45
        camera.shake(0.25)
        sound.sfx('player_hurt')
        d = 1 if self.x >= src_x else -1
        self.vx, self.vy = d * 330.0, 380.0
        if self.hp <= 0:              # 마지막 한 방: 더 세게 뒤로 튕겨 나간다
            self.vx, self.vy = d * DEATH_KNOCK[0], DEATH_KNOCK[1]
        self.face = -d                # 때린 쪽을 본 채 뒤로 넘어간다
        self.state_machine.handle_event(('FALL', None))
        effect.add(effect.PixelNumber(self.x, self.y + 50, f'-{int(dmg)}', (255, 110, 90), 21 + 4 * (n - 1)))
        if self.hp <= 0:
            self.die()

    def die(self):
        """생명은 하나뿐이다. 다시 살아나지 않고 쓰러진 채 게임이 끝난다."""
        self.hp = 0
        self.dead = True
        self.death_t = 0.0
        self.hook, self.reeling = None, False
        self.invuln = 99.0            # 쓰러진 뒤에는 더 맞지 않는다
        play_mode.on_player_down()

    # ------------------------------------------------ 갱신
    def update(self, dt):
        self.anim_t += dt
        if self.dead:
            self.death_t += dt
        for k in self.cool:
            self.cool[k] = max(0.0, self.cool[k] - dt)
        self.invuln = max(0.0, self.invuln - dt)
        self.hit_t = max(0.0, self.hit_t - dt)
        if self.slash_t > 0:
            self.slash_t = max(0.0, self.slash_t - dt)
            if self.slash_t <= 0:
                self.run_phase = 0.3          # 베기 그림의 끝이 달리기 3번째 장과 이어진다
        # 맞지 않고 버티는 동안 체력이 천천히 다시 찬다
        self.safe_t += dt
        if not self.dead and self.safe_t >= REGEN_DELAY:
            self.hp = min(self.max_hp, self.hp + REGEN * dt)
        if self.x < WALL_X + 350 or ZONES[zone_of(self.x)].get('rest'):
            self.gas = min(self.gas_max, self.gas + 30 * dt)
        was_face = self.face
        self.state_machine.update(dt)
        self.run_phase = (self.run_phase + max(abs(self.vx), HERO_JOG) * dt / HERO_STRIDE) % 1.0
        self.update_turn(dt, was_face)

        self.preview = None
        cx, cy = self.center()
        wx, wy = camera.to_world(*self.mouse)
        self.preview = map_data.find_anchor(cx, cy, wx, wy)

    # ------------------------------------------------ 그리기
    def update_turn(self, dt, was_face):
        """땅에서 보는 방향이 바뀌면 앞모습을 거쳐 돈다. 도는 중에 다시 바꾸면 지금 모습에서 되돌아간다"""
        self.turn_t = max(0.0, self.turn_t - dt)
        if self.face != was_face:
            on_ground = self.state_machine.cur_state is self.GROUND
            self.turn_t = HERO_TURN_TIME - self.turn_t if on_ground and not self.dead and self.curve_k <= 0 else 0.0

    def swing_frame(self):
        """칼 휘두르기 진행 칸. 앞쪽을 빠르게 넘겨 키를 누르자마자 칼이 나간다"""
        n = FRAMES['slash']
        return min(n - 1, int((1 - self.slash_t / self.slash_total) ** 0.7 * n))

    def wire_slash_frame(self):
        """와이어 베기 칸: 젖히는 앞부분(9장)은 빠르게, 내리치고 돌아오는 뒷부분은 천천히"""
        n = FRAMES['wire_slash']
        k = 1 - self.slash_t / self.slash_total
        if k < HERO_WIRE_SLASH_HIT:
            return int(k / HERO_WIRE_SLASH_HIT * 9)
        return min(n - 1, 9 + int((k - HERO_WIRE_SLASH_HIT) / (1 - HERO_WIRE_SLASH_HIT) * (n - 9)))

    def pick_frame(self):
        st = self.state_machine.cur_state
        if self.dead:                     # 뒤로 넘어가는 모션 뒤 누운 자세 그대로
            return 'death', min(FRAMES['death'] - 1, int(self.death_t / DEATH_ANIM * FRAMES['death'])), 0.0
        if st is self.TORNADO:
            return 'spinE', loop('spinE', self.anim_t, 30), 0.0
        if self.hit_t > 0:
            return 'hit', min(FRAMES['hit'] - 1, int((0.45 - self.hit_t) / 0.45 * FRAMES['hit'])), 0.0
        if self.curve_k > 0 and st is self.GROUND:
            return 'curve', min(FRAMES['curve'] - 1, int(smooth(self.curve_k) * FRAMES['curve'])), 0.0
        if self.land_t > 0 and st is self.GROUND:
            k = 1 - self.land_t / self.land_total
            return 'land', min(FRAMES['land'] - 1, int(k * FRAMES['land'])), 0.0
        if st is self.WIRE and self.launching:
            if not self.reeling:              # 웅크리며 힘을 모은다
                return 'launch', min(LAUNCH_CROUCH - 1, int(self.hook_t / self.hook_time * LAUNCH_CROUCH)), 0.0
            if self.launch_t > 0:             # 스프링처럼 튀어 오른다
                n = FRAMES['launch'] - LAUNCH_CROUCH
                return 'launch', LAUNCH_CROUCH + min(n - 1, int((1 - self.launch_t / HERO_WIRE_SPRING) * n)), 0.0
        if self.turn_t > 0 and st is self.GROUND:
            n = FRAMES['curve']               # 느릴 때도 서지 않고, 다리를 굴리며 도는 그림을 쓴다
            return 'curve', min(n - 1, int((1 - self.turn_t / HERO_TURN_TIME) * n)), 0.0
        if st is self.WIRE and self.reeling:
            vx, vy = self.vx * self.face, self.vy
            rad = max(-0.9, min(0.9, math.atan2(vy, max(1.0, vx)) - 0.05))
            if self.slash_t > 0:              # 와이어로 날아가며 벤다
                return 'wire_slash', self.wire_slash_frame(), rad
            return 'wire', loop('wire', self.anim_t, 20), rad
        if self.slash_t > 0:
            return 'slash', self.swing_frame(), 0.0
        if st is self.AIR or st is self.WIRE:
            # 프레임을 속도로 고른다: 막 뛰어오를 땐 앞 절반의 처음(웅크리기 시작) → 꼭대기에서 끝(다 웅크림),
            # 떨어지기 시작하면 뒤 절반의 처음 → 빨리 떨어질수록 끝(다리를 펴고 팔을 벌림)
            if self.vy < -HERO_LAND_SPEED:    # 빠르게 떨어지는 중
                return 'fall', loop('fall', self.anim_t, 10), 0.0
            half = FRAMES['air'] // 2
            if self.vy > 0:
                k = 1 - min(1.0, self.vy / AIR_RISE_V)
                return 'air', min(half - 1, int(k * half)), 0.0
            k = min(1.0, -self.vy / AIR_FALL_V)
            return 'air', half + min(half - 1, int(k * half)), 0.0
        return 'run', int(self.run_phase * FRAMES['run']) % FRAMES['run'], 0.0   # 서 있는 그림은 쓰지 않는다

    def draw(self):
        if self.hidden:
            return
        cx, cy = self.center()
        # 와이어 줄
        if self.hook:
            hx, hy = self.hook
            wy = self.y + HERO_HEIGHT * 0.3            # 와이어가 나오는 허리 높이
            d = math.hypot(hx - cx, hy - wy)
            k = 1.0 if self.reeling else min(1.0, self.rope / max(d, 1))
            ex, ey = cx + (hx - cx) * k, wy + (hy - wy) * k
            sx1, sy1 = camera.to_screen(cx, wy)
            sx2, sy2 = camera.to_screen(ex, ey)
            nx, ny = -(sy2 - sy1), sx2 - sx1
            n = math.hypot(nx, ny) or 1
            nx, ny = nx / n * 1.5, ny / n * 1.5
            render.line(sx1 + nx, sy1 + ny, sx2 + nx, sy2 + ny, (230, 236, 245), 230)
            render.line(sx1 - nx, sy1 - ny, sx2 - nx, sy2 - ny, (200, 210, 225), 200)
        # 와이어가 닿을 나무 미리 보기
        if self.preview and not (self.hook and self.hook == self.preview):
            px, py = camera.to_screen(*self.preview)
            render.tint(self.ring, (255, 255, 255), 0.75)
            self.ring.composite_draw(self.anim_t * 1.5, '', px, py, 30, 30)
            render.untint(self.ring)

        row, frame, rad = self.pick_frame()
        sx, sy = camera.to_screen(self.x, self.y)
        alpha = 0.35 if self.invuln > 0 and not self.dead and int(self.invuln * 12) % 2 else 1.0
        self.image.opacify(alpha)
        flip = '' if self.face > 0 else 'h'
        size, angle = DRAW, rad * self.face
        if row == 'curve':                # 오른쪽으로 달리다 왼쪽으로 도는 그림: 반대면 통째로 뒤집는다
            came_from = self.curve_from if self.curve_k > 0 else -self.face
            flip = '' if came_from > 0 else 'h'
            arc = math.sin(math.pi * smooth(self.curve_k))
            size = DRAW * (1 + HERO_CURVE_DEPTH * arc)    # 원을 돌며 화면 쪽으로 다가오고
            sy -= HERO_CURVE_DROP * arc                   # 조금 아래로 내려왔다가 돌아간다
            angle = came_from * HERO_CURVE_LEAN * arc     # 몸은 커브 안쪽으로 기운다
        h = (CELL / 2 - BASE) * size / CELL           # 발에서 그림 가운데까지: 기울어도 발은 제자리
        px, py = sx - math.sin(angle) * h, sy + math.cos(angle) * h
        if row == 'wire_slash':           # 날아가는 몸은 몸 가운데를 축으로 돈다
            px, py = sx, sy + h
        self.image.clip_composite_draw(frame * CELL, (len(ROWS) - 1 - ROWS.index(row)) * CELL, CELL, CELL,
                                       angle, flip, px, py, size, size)
        self.image.opacify(1.0)

        # 생명·가스는 왼쪽 위 HUD 에만 보인다 (머리 위 막대는 없앴다)
