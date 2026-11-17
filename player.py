import math

import camera
import effect
import map_data
import play_mode
import render
from config import *
from giant import floor_of
from state_machine import StateMachine, wire_fire, arrive, fall, land, tornado

CELL, BASE = 96, 8
DRAW = 72                    # 화면에 그리는 칸 크기 (96칸을 줄여 키를 약 48px 로 맞춤)
ROWS = ['idle', 'run', 'wire', 'air', 'slashQ', 'slashW', 'spinE', 'hit']
FRAMES = {row: 8 for row in ROWS}   # PixelLab 주인공 시트(hero_px.png): 줄마다 8프레임. air 는 0~3 상승, 4~7 하강

WALK_SPEED = 130.0
RUN_MAX = 440.0
GAS_MAX = 100.0
START_HP = 100.0             # 처음 체력 (생명은 하나뿐). 게이지로 보이고 버티는 동안 천천히 다시 찬다
HIT_DMG = 10.0               # 거인 공격 한 번(세기 1)에 깎이는 체력
REGEN = 1.5                  # 초당 다시 차는 체력
REGEN_DELAY = 3.0            # 마지막으로 맞은 뒤 이만큼 지나야 차기 시작한다
WIRE_COST = 6.0
HOOK_SPEED = 3400.0
REEL_SPEED = 780.0
ATTACK = 100.0               # 공격력. 목덜미 100%, 발목 30%, 몸통 15%
Q_COOLDOWN = 0.35
Q_TIME = 0.26
TORNADO_CD = 6.0
TORNADO_RISE = 0.4
FORT_DAMAGE = 6.0            # 혼자 요새를 베면 오래 걸린다
PART_ORDER = {'neck': 0, 'ankle': 1, 'body': 2}
AIR_NECK_V = 75.0           # 공중에서 목덜미와 이만큼 높이 차이 안이면 목을 벤다


class Ground:
    def __init__(self, p):
        self.p = p

    def enter(self, e):
        p = self.p
        p.vy = 0.0
        if e[0] == 'LAND' and p.land_speed < -500:
            effect.steam(p.x, p.y + 4, 3, 10, (200, 200, 200), 14)

    def exit(self, e):
        pass

    def do(self, dt):
        # 달리기는 가스를 쓰지 않는다. 땅에 있으면 가스가 천천히 찬다.
        p = self.p
        mx, _ = camera.to_world(*p.mouse)
        dx = mx - p.x
        target = 0.0
        if abs(dx) > 14:
            target = math.copysign(min(RUN_MAX, (abs(dx) - 14) * 2.0), dx)
        accel = 1700.0 if abs(target) > abs(p.vx) else 2600.0
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
            p.rope += HOOK_SPEED * dt
            if p.rope >= dist:
                p.reeling = True
                p.reel_speed = max(360.0, math.hypot(p.vx, p.vy))
            if p.lane is None:
                p.vy -= GRAVITY * dt
                p.move_x(p.vx * dt)
                p.y += p.vy * dt
            else:
                p.vx *= 0.9
            return
        p.lane = None
        top = REEL_SPEED * p.reel_mult
        p.reel_speed = min(top, p.reel_speed + 4200 * dt)
        step = p.reel_speed * dt
        ux, uy = (hx - cx) / max(dist, 1e-3), (hy - cy) / max(dist, 1e-3)
        p.vx, p.vy = ux * p.reel_speed, uy * p.reel_speed
        if step >= dist - 14:
            # 도착: 살짝 튕겨 나가며 떨어진다
            p.x, p.y = hx - ux * 10, hy - 16 - uy * 10
            p.vx = ux * p.reel_speed * 0.5
            p.vy = 250 + max(0.0, uy * p.reel_speed * 0.3)
            # 튕겨 올라도 바로 위층까지는 넘지 않게: 고른 층에 내려앉는다
            lane = int((hy - LANE_Y[0]) // LANE_GAP)
            if lane < 4:
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
        if p.hit_t <= 0:
            p.vx += max(-420 * dt, min(420 * dt, target - p.vx))
        p.vy = max(-900.0, p.vy - GRAVITY * dt)
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
        self.image = render.image('hero_px.png')
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

        # 강화로 바뀌는 값
        self.max_hp = START_HP
        self.hp = START_HP
        self.dead = False             # 생명은 하나뿐: 체력이 다하면 그대로 끝
        self.safe_t = 0.0             # 마지막으로 맞은 뒤 지난 시간 (체력이 다시 차는 조건)
        self.gas_max = GAS_MAX
        self.gas = GAS_MAX
        self.blade = 1.0
        self.gas_cost = 1.0
        self.reel_mult = 1.0
        self.reach = 700.0
        self.has_tornado = False
        self.tornado_cd = TORNADO_CD

        self.cool = {'Q': 0.0, 'W': 0.0}
        self.action, self.action_t = None, 0.0
        self.invuln, self.hit_t = 0.0, 0.0
        self.no_gas_t = 0.0

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
                self.TORNADO: {arrive: self.AIR, fall: self.AIR},
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
        if self.state_machine.cur_state is self.TORNADO:
            return
        if self.gas < WIRE_COST * self.gas_cost:
            self.no_gas_t = 0.8
            return
        cx, cy = self.center()
        wx, wy = camera.to_world(sx, sy)
        target = map_data.find_anchor(cx, cy, wx, wy, self.reach)
        if target is None:
            return
        self.use_gas(WIRE_COST)
        self.state_machine.handle_event(('WIRE', target))

    def slash(self):
        """Q: 지금 있는 층에 따라 목덜미 / 발목 / 몸통을 벤다."""
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
            key = (PART_ORDER[part], abs(g.x - self.x))
            if best_key is None or key < best_key:
                best, best_key = (g, part), key
        low = best is not None and best[1] == 'ankle'
        self.action, self.action_t = ('W' if low else 'Q'), Q_TIME
        self.anim_t = 0.0
        if low:
            effect.add(effect.Slash(self, 'W', self.face, 90, 8))
        else:
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
        """W: 가까운 거인의 목 높이까지 회오리처럼 솟아올라 목덜미를 벤다."""
        if not self.has_tornado or self.cool['W'] > 0 or self.state_machine.cur_state is self.TORNADO:
            return
        best, best_d = None, 1e9
        for g in play_mode.giants():
            if g.alive() and g.lane is not None:
                d = abs(g.x - self.x)
                if d <= g.reach_x() + 70 and d < best_d:
                    best, best_d = g, d
        if best is None:
            effect.add(effect.FloatText(self.x, self.y + 56, '근처에 거인이 없다', (220, 220, 220), 14))
            return
        self.cool['W'] = self.tornado_cd
        self.action = None
        self.state_machine.handle_event(('TORNADO', best))

    def hurt(self, src_x, n=1):
        if self.invuln > 0:
            return
        dmg = n * HIT_DMG
        self.hp = max(0.0, self.hp - dmg)
        self.safe_t = 0.0
        self.invuln = 1.0
        self.hit_t = 0.45
        self.action = None
        camera.shake(0.25)
        d = 1 if self.x >= src_x else -1
        self.vx, self.vy = d * 330.0, 380.0
        self.face = -d
        self.state_machine.handle_event(('FALL', None))
        effect.add(effect.FloatText(self.x, self.y + 50, f'-{n}', (255, 110, 90), 18 + 4 * (n - 1)))
        if self.hp <= 0:
            self.die()

    def die(self):
        """생명은 하나뿐이다. 다시 살아나지 않고 쓰러진 채 게임이 끝난다."""
        self.hp = 0
        self.dead = True
        self.invuln = 99.0            # 쓰러진 뒤에는 더 맞지 않는다
        play_mode.on_player_down()

    # ------------------------------------------------ 갱신
    def update(self, dt):
        self.anim_t += dt
        for k in self.cool:
            self.cool[k] = max(0.0, self.cool[k] - dt)
        self.invuln = max(0.0, self.invuln - dt)
        self.hit_t = max(0.0, self.hit_t - dt)
        # 맞지 않고 버티는 동안 체력이 천천히 다시 찬다
        self.safe_t += dt
        if not self.dead and self.safe_t >= REGEN_DELAY:
            self.hp = min(self.max_hp, self.hp + REGEN * dt)
        self.no_gas_t = max(0.0, self.no_gas_t - dt)
        if self.action:
            self.action_t -= dt
            if self.action_t <= 0:
                self.action = None
        if self.x < WALL_X + 350 or ZONES[zone_of(self.x)].get('rest'):
            self.gas = min(self.gas_max, self.gas + 30 * dt)
        self.state_machine.update(dt)

        self.preview = None
        if self.gas >= WIRE_COST * self.gas_cost:
            cx, cy = self.center()
            wx, wy = camera.to_world(*self.mouse)
            self.preview = map_data.find_anchor(cx, cy, wx, wy, self.reach)

    # ------------------------------------------------ 그리기
    def pick_frame(self):
        st = self.state_machine.cur_state
        if self.dead:
            return 'hit', 7, 0.0          # 쓰러진 자세 그대로
        if st is self.TORNADO:
            return 'spinE', int(self.anim_t * 30) % 8, 0.0
        if self.hit_t > 0:
            return 'hit', min(7, int((0.45 - self.hit_t) / 0.45 * 8)), 0.0
        if self.action:
            k = 1 - self.action_t / Q_TIME
            if st is self.AIR or st is self.WIRE:
                # 공중(와이어로 나는 중 포함): 몸을 한 바퀴 돌리며 벤다. 끝나면 다시 날기 자세로 (속도는 그대로)
                return 'spinE', min(7, int(k * 8)), 0.0
            row = {'Q': 'slashQ', 'W': 'slashW'}[self.action]
            return row, min(FRAMES[row] - 1, int(k * FRAMES[row])), 0.0
        if st is self.WIRE and self.reeling:
            vx, vy = self.vx * self.face, self.vy
            rad = max(-0.9, min(0.9, math.atan2(vy, max(1.0, vx)) - 0.05))
            return 'wire', int(self.anim_t * 20) % 8, rad
        if st is self.AIR or st is self.WIRE:
            return 'air', (0 if self.vy > 0 else 4) + int(self.anim_t * 12) % 4, 0.0
        if abs(self.vx) > 25:
            return 'run', int(self.anim_t * (8 + abs(self.vx) / 22)) % 8, 0.0
        return 'idle', int(self.anim_t * 8) % 8, 0.0

    def draw(self):
        cx, cy = self.center()
        # 와이어 줄
        if self.hook:
            hx, hy = self.hook
            d = math.hypot(hx - cx, hy - (self.y + 16))
            k = 1.0 if self.reeling else min(1.0, self.rope / max(d, 1))
            ex, ey = cx + (hx - cx) * k, self.y + 16 + (hy - self.y - 16) * k
            sx1, sy1 = camera.to_screen(cx, self.y + 16)
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
        r = ROWS.index(row)
        alpha = 0.35 if self.invuln > 0 and not self.dead and int(self.invuln * 12) % 2 else 1.0
        self.image.opacify(alpha)
        flip = '' if self.face > 0 else 'h'
        self.image.clip_composite_draw(frame * CELL, (len(ROWS) - 1 - r) * CELL, CELL, CELL,
                                       rad * self.face, flip, sx, sy + (CELL / 2 - BASE) * DRAW / CELL, DRAW, DRAW)
        self.image.opacify(1.0)

        # 생명·가스는 왼쪽 위 HUD 에만 보인다 (머리 위 막대는 없앴다)
        if self.no_gas_t > 0:
            render.text('가스 부족', sx, sy + 62, 14, (255, 140, 110), 'center', alpha=min(1.0, self.no_gas_t * 2))
