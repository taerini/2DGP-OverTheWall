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
from projectile import Rock, Seed

with open('resource/giant_meta.json') as f:         # 갑옷 거인 시트(giant_armor.png)는 예전 320px 칸 형식 그대로
    ARMOR_META = json.load(f)
ARMOR_ROWS = [r for r, _ in ARMOR_META['rows']]
ARMOR_FRAMES = dict(ARMOR_META['rows'])


class Sheet:
    """거인 픽셀 시트 하나 (tools/make_giant_px.py 가 만든 png + meta)"""
    def __init__(self, name):
        with open(f'resource/{name}_meta.json') as f:
            self.meta = json.load(f)
        self.name = name
        self.cell = self.meta['cell']            # 셀 크기 (그림 단위)
        self.cell_px = self.meta['cell_px']      # 시트에서 실제 픽셀 크기
        self.h = self.meta['height']             # 그림 단위 키
        self.rows = [r for r, _ in self.meta['rows']]
        self.frames = dict(self.meta['rows'])
        self.nape = self.meta['nape']
        self.walk_nape = sum(dy for _, dy in self.nape['walk']) / len(self.nape['walk']) / self.h
        self.run_nape = sum(dy for _, dy in self.nape['run']) / len(self.nape['run']) / self.h
        self.kneel_nape = self.nape['kneel'][-1][1] / self.h


SHEETS = {'basic': Sheet('giant_px'), 'thin': Sheet('giant_thin'),
          'female': Sheet('giant_female'), 'beast': Sheet('giant_beast_px'),
          'melon': Sheet('giant_melon')}
# 날뛰는 거인은 마른 거인, 영리한 거인(보스)은 여성형 거인, 돌 던지는 거인(보스)은 짐승 거인 그림. 나머지는 기본 거인
KIND_SHEET = {'erratic': 'thin', 'smart': 'female', 'thrower': 'beast', 'melon': 'melon'}


def giant_height(k, sh=SHEETS['basic']):
    """크기 k 거인의 키. 서 있을 때 목덜미가 (서 있는 층 + k - 1)층 한가운데쯤 오게 맞춘다."""
    return ((k - 1) * LANE_GAP + 70 - (k - 1) * 6.25) / sh.walk_nape


def max_lane(k):
    """머리가 화면을 넘지 않는 가장 높은 층 (0부터). 크기 1 → 5층, 크기 4 → 2층, 크기 5 → 1층"""
    return 5 - k


# 종류별 능력치. size 는 고를 수 있는 크기들
KINDS = {
    'normal':   dict(size=(1, 2, 3, 4, 5), speed=(55, 80), hp=1.0),
    'erratic':  dict(size=(1, 2), speed=(105, 130), hp=0.9),   # 마른 거인: 빠르고, 붙으면 돌진 공격
    'climber':  dict(size=(1, 2, 3), speed=(50, 70), hp=1.0),
    'swarm':    dict(size=(1,), speed=(85, 110), hp=0.8),
    'armed':    dict(size=(1, 2, 3, 4, 5), speed=(48, 66), hp=1.3),
    'smart':    dict(size=(3,), speed=(125, 125), hp=3.2, boss='빠르고 영리한 거인'),
    'thrower':  dict(size=(4,), speed=(26, 26), hp=3.0, boss='돌 던지는 거인'),
    'colossal': dict(size=(5,), speed=(20, 20), hp=3.0, boss='거대 거인'),
    'melon':    dict(size=(4,), speed=(30, 30), hp=3.2, boss='수박 거인'),   # 키 4층, 수박씨를 뱉는다
}
KNEEL_TIME = 2.6
WAKE_DIST = 1300.0       # 미리 서 있는 거인은 주인공이 이만큼 가까워지면 움직이기 시작한다
RUN_MULT = 2.6           # 달릴 때 걷는 속도의 몇 배
RUN_FAR = 1400.0         # 주인공과 이만큼 멀면 늘 달린다 (먼 요새에서 벽까지 금방 온다)
NO_RUN = ('thrower', 'colossal', 'melon')    # 느릿느릿 걷는 보스
CHASE_R = 450.0          # 보스가 아닌 거인은 주인공이 이 반경(+몸 크기) 안에 오면 뛰어와서 공격한다
# 마른 거인(날뛰는 거인)의 돌진: 쫓아가다 멈춰 서서 앞쪽에 빨간 범위를 띄우고 → 앞으로 확 덮친다
LUNGE_CHASE_R = 340.0    # 빨라서 쫓기 시작하는 반경은 조금 좁게
LUNGE_START = 170.0      # 주인공과 이 거리(+키의 20%) 안이면 멈춰 서서 돌진 준비
LUNGE_WARN = 0.55        # 웅크리고 빨간 범위를 보여 주는 시간
LUNGE_TIME = 0.22        # 덮치는 시간
LUNGE_DIST = 230.0       # 덮치며 나아가는 거리 (+키의 40%)
LUNGE_END = 0.35         # 덮친 뒤 웅크린 채 멈춰 있는 시간
LUNGE_CD = 1.6           # 다음 돌진까지
LUNGE_WARN_FRAMES = (0, 1, 2, 3, 4)   # grab 줄: 웅크리며 팔을 당김
LUNGE_FRAMES = (5, 6)                 # grab 줄: 팔을 내지르며 덮침
LUNGE_END_FRAME = 7
DEATH_FRAME = 0.11       # 쓰러지는 모션 한 장 시간 (8장: 무릎 꿇고 → 앞으로 엎어짐)
DEAD_FADE = (2.8, 3.6)   # 바닥에 누운 채 이 시간부터 흐려져서 사라진다
GRAB_TIME = 0.7          # 손을 뻗기 시작해서 거두기까지
GRAB_CD = 1.2            # 잡기를 거둔 뒤 다음 잡기까지
SWAT_WARN = 0.45         # 목 뒤 후려치기: 목덜미 근처에 머물면 이만큼 뒤에 휩쓴다 (경고 표시는 없음)
COUNTER_WARN = 0.35      # 베였는데 안 죽으면 이만큼 뒤 반격
COUNTER_RATE = 0.6       # 목덜미를 베였는데 버텼을 때 목 뒤를 후려치는 확률
SWAT_CD = (2.2, 3.4)     # 후려친 뒤 다음 후려치기까지
SWAT_SWING = 0.3         # 손을 올린 뒤 실제로 휘두르는 시간 (주인공이 떠나도 끝까지 휘두른다)
SWAT_FRAMES = (3, 4, 5, 6)   # 휘두를 때 쓰는 공격(grab) 줄 프레임: 큰 궤적
HIT_GRAB_CD = 0.15       # 맞으면 공격 쿨다운을 이만큼으로 줄여 곧바로 반격한다
GUARD_REACT = 0.8        # 서 있다가 목을 베이면 이만큼 손으로 목을 가린다 (그동안 목덜미 피해 15%)
# 휘두르기 공격 범위: 앞쪽으로 키 × GRAB_FRONT + GRAB_PAD, 높이는 발밑부터 키의 GRAB_HIGH 까지
# (목덜미는 키의 약 69% 높이라 목 높이에서 베는 주인공은 맞지 않는다)
GRAB_FRONT = 0.6         # 실제로 맞는 앞쪽 거리 (예전 0.3의 2배)
GRAB_START = 0.5         # 이 거리 안에 들어오면 휘두르기 시작 (예전 0.25의 2배)
GRAB_PAD = 40            # 예전 20의 2배
GRAB_HIGH = 0.65         # 예전 15~55% 에서 0~65% 로
BLAST_WARN = 1.2         # 거대 거인 폭발 전에 위험 지역을 보여 주는 시간
BLAST_R = 240
GRAB_HIT_AT = 0.3        # state_t 가 이 값 아래로 내려가는 순간 잡는다 (뻗은 지 0.4초 뒤)
PART_RATE = {'neck': 1.0, 'ankle': 0.3, 'body': 0.15, 'raw': 1.0}
PART_NAME = {'neck': '목덜미', 'ankle': '발목', 'body': '몸통'}
DMG_SPREAD = (0.85, 1.15)    # 벨 때마다 피해가 이 범위에서 흔들린다
CRIT_RATE = 0.2
CRIT_MULT = 1.5
HP_BY_SIZE = {1: 110, 2: 175, 3: 245, 4: 320, 5: 400}
# 수박 거인: 숨을 들이켜고(입 크게 벌림) → '후!!!!' 하며 수박씨를 가로로 곧게 뱉는다.
# 주인공이 있는 층을 노린다: 5층은 점프, 4층은 선 채로, 3층은 쭈그려, 2층은 엎드려서. 1층(발밑)은 안전하다
MELON_INHALE = 0.8       # 숨 들이켜는 시간 (노린 층에 빨간 띠로 예고)
MELON_SPIT = 2.0         # 씨를 뱉는 시간
MELON_SEEDS = 10         # 한 번에 뱉는 씨 수
MELON_CD = 3.0           # 다 뱉고 나서 다음 공격까지
MELON_RANGE = 1000.0     # 주인공이 가로로 이만큼 안에 있으면 공격한다
MELON_RECOVER = 0.35     # 뱉고 나서 원래 자세로 돌아오는 시간
MELON_MOUTH = (0.21, 0.57)   # 입 위치: 키에 대한 비율 (앞쪽으로, 발밑에서 위로). giant_melon 그림에서 잰 값
MELON_HEIGHT = 520.0     # 키: 수박 머리 2.5층, 덩굴 몸 1.5층 (서 있으면 입이 3층, 목이 2층 높이)
MELON_POSE_GAP = 60.0    # 입 높이 차이가 이보다 크면 점프 / 쭈그리기 자세를 쓴다
MELON_JUMP_HOLD = (4, 5)     # 씨를 뱉는 동안 번갈아 쓰는 공중 프레임 (jump 줄)
MELON_JUMP_RISE = 14.0       # 공중 프레임에서 그림이 떠 있는 높이 (그림 단위)
MELON_CROUCH_DROP = 22.0     # 가장 깊이 숙인 프레임(crouch 3번)에서 수박이 내려간 높이 (그림 단위)   # 크기별 기본 체력. 처음 공격력(40)으로 목덜미 3 / 4~5 / 6 / 8 / 9~10번


def floor_of(y):
    return max(0, min(4, int((y - LANE_Y[0]) // LANE_GAP)))


class Giant:
    def __init__(self, kind, x, lane, k, hp_mult=1.0):
        info = KINDS[kind]
        self.kind = kind
        self.boss = info.get('boss')
        self.k = k
        self.sh = SHEETS[KIND_SHEET.get(kind, 'basic')]
        self.size = MELON_HEIGHT if kind == 'melon' else giant_height(k, self.sh)
        self.speed = random.uniform(*info['speed']) * (1.12 - 0.08 * k)
        self.max_hp = HP_BY_SIZE[k] * info['hp'] * hp_mult
        self.hp = self.max_hp
        self.armor = info.get('armor', 0)
        self.max_armor = self.armor
        self.x, self.y = float(x), float(LANE_Y[lane])
        self.lane = lane
        self.vy = 0.0
        self.dir = -1
        self.scale = self.size / self.sh.h
        self.state, self.state_t = 'walk', 0.0
        self.anim_t = random.uniform(0, 3)
        self.kneel_t = 0.0
        self.kneel_age = 0.0                     # 이번에 주저앉은 뒤 지난 시간 (모션용)
        self.grab_cd = 0.0
        self.turn_t = random.uniform(2, 5)       # 날뛰는 거인: 방향 바꾸기
        self.climb_cd = random.uniform(2, 5)     # 벽 타는 거인
        self.swat_cd = random.uniform(1.5, 3.0)   # 목 뒤 후려치기 (보스는 아직 안 쓴다)
        self.swat_warn = SWAT_WARN
        self.guard_t, self.guard_cd = 0.0, 3.0   # 영리한 거인: 목덜미 가리기
        self.throw_cd = 2.5                      # 돌 던지는 거인
        self.blast_cd = 8.0                      # 거대 거인
        self.melon_cd = 2.0                      # 수박 거인: 다음 씨 뱉기까지
        self.melon_floor = 3                     # 수박 거인: 노리는 층 (0부터)
        self.seeds_left = 0
        self.steam_t = 0.0
        self.flash_t = 0.0
        self.crit = False                        # 마지막으로 맞은 공격이 치명타였나
        self.waiting = False                     # 미리 서 있는 거인: 주인공이 다가올 때까지 제자리
        self.running = False
        self.chasing = False                     # 주인공을 쫓아가는 중
        self.run_t = 0.0                         # 남은 질주 시간
        self.run_cd = random.uniform(1.5, 5.0)   # 다음 질주까지
        self.step = random.uniform(0, 100)       # 걸어온 거리 (걷기·달리기 모션용)
        self.grabbed = False
        self.sheet = render.image(self.sh.name + '.png', pixel=True)
        self.sheet_flash = render.image(self.sh.name + '_flash.png', pixel=True)   # 맞았을 때 하얗게 번쩍이는 판
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
            return 'death', min(self.sh.frames['death'] - 1, int(self.state_t / DEATH_FRAME))
        if self.kneel_t > 0:
            # 주저앉은 채 또 베여도 다시 일어섰다 앉지 않는다: 앉는 모션은 처음 한 번만
            k = min(self.kneel_age, self.kneel_t)
            return 'kneel', min(self.sh.frames['kneel'] - 1, int(k / 0.08))
        if self.state == 'lunge_warn':
            k = 1 - self.state_t / LUNGE_WARN
            return 'grab', LUNGE_WARN_FRAMES[min(len(LUNGE_WARN_FRAMES) - 1, int(k * len(LUNGE_WARN_FRAMES)))]
        if self.state == 'lunge':
            k = 1 - self.state_t / LUNGE_TIME
            return 'grab', LUNGE_FRAMES[min(len(LUNGE_FRAMES) - 1, int(k * len(LUNGE_FRAMES)))]
        if self.state == 'lunge_end':
            return 'grab', LUNGE_END_FRAME
        if self.state in ('grab', 'wall'):
            if self.state == 'wall':
                return 'grab', int(self.state_t / 0.15) % self.sh.frames['grab']
            return 'grab', min(self.sh.frames['grab'] - 1, int((GRAB_TIME - self.state_t) / (GRAB_TIME / self.sh.frames['grab'])))
        if self.state in ('inhale', 'spit', 'melon_end'):
            return self.melon_frame()
        if self.state == 'throw':
            # 던지기 줄은 없앴다: 팔을 앞으로 뻗는 잡기 동작으로 던진다
            return 'grab', min(self.sh.frames['grab'] - 1, int((0.9 - self.state_t) / (0.9 / self.sh.frames['grab'])))
        if self.state == 'swat':
            if self.state_t > SWAT_SWING:
                return 'guard', 0      # 손을 목 뒤로 올린 자세
            k = (SWAT_SWING - self.state_t) / SWAT_SWING
            return 'grab', SWAT_FRAMES[min(len(SWAT_FRAMES) - 1, int(k * len(SWAT_FRAMES)))]
        if self.guarding():
            return 'guard', int(self.anim_t * 3) % 2
        if self.running:
            return 'run', int(self.step / (18 * self.k ** 0.5) * self.sh.frames['run'] / 6) % self.sh.frames['run']
        return 'walk', int(self.step / (11 * self.k ** 0.5) * self.sh.frames['walk'] / 6) % self.sh.frames['walk']

    def nape(self):
        """판정용 목덜미 위치. 무릎을 꿇으면 바로 주저앉은 높이로 계산한다."""
        if self.kneel_t > 0:
            dx, dy = self.sh.nape['kneel'][-1]
        else:
            row, fr = self.frame()
            dx, dy = self.sh.nape[row][fr]
            if row == 'walk':
                dy = self.sh.walk_nape * self.sh.h
            elif row == 'run':
                dy = self.sh.run_nape * self.sh.h
        lift, sq = self.melon_pose()
        return self.x + dx * self.scale * (-self.dir), self.y + lift + dy * self.scale * sq

    def neck_floor(self):
        return floor_of(self.nape()[1])

    def reach_x(self):
        return self.size * 0.14 + 22

    def get_bb(self):
        h = self.size * (self.sh.kneel_nape + 0.12 if self.kneel_t > 0 else 1.0)
        lift, sq = self.melon_pose()
        return self.x - self.size * 0.15, self.y + lift, self.x + self.size * 0.15, self.y + lift + h * sq

    # ------------------------------------------------ 수박 거인
    def melon_weight(self):
        """공격 자세(점프·쭈그리기)로 얼마나 바뀌었나 0~1"""
        if self.kind != 'melon' or self.kneel_t > 0:
            return 0.0
        if self.state == 'inhale':
            k = min(1.0, (1 - self.state_t / MELON_INHALE) / 0.4)
            return k * k * (3 - 2 * k)
        if self.state == 'spit':
            return 1.0
        if self.state == 'melon_end':
            return max(0.0, self.state_t / MELON_RECOVER)
        return 0.0

    def melon_need(self):
        """노린 층에 입을 맞추려면 서 있을 때보다 얼마나 높여야(+) / 낮춰야(-) 하나"""
        stand = self.size * MELON_MOUTH[1]                     # 서 있을 때 입 높이 (발밑에서)
        want = LANE_Y[self.melon_floor] + 22 - self.y           # 노린 층에서 주인공 몸 가운데 높이
        return want - stand

    def melon_style(self):
        """이번 공격 자세: 'jump' / 'crouch' / 'stand'"""
        need = self.melon_need()
        if need > MELON_POSE_GAP:
            return 'jump'
        if need < -MELON_POSE_GAP:
            return 'crouch'
        return 'stand'

    def melon_pose(self):
        """(그림 위에 더 띄울 높이, 세로로 찌그러진 비율). 점프·쭈그리기는 그림이 하고, 모자란 만큼만 채운다"""
        w = self.melon_weight()
        if w <= 0:
            return 0.0, 1.0
        style, need = self.melon_style(), self.melon_need()
        if style == 'jump':
            if self.state == 'inhale':
                return 0.0, 1.0                                # 무릎 굽혀 뛰어오르는 중: 그림만
            return max(0.0, need - MELON_JUMP_RISE * self.scale) * w, 1.0
        return 0.0, 1.0                                        # 쭈그리기는 그림이 몸을 숙인다 (수박은 찌그러뜨리지 않는다)

    def mouth(self):
        """입 위치. 씨를 뱉을 때는 노린 층 높이에 맞춰져 있다"""
        h = self.size * MELON_MOUTH[1]
        style = self.melon_style()
        if self.state in ('spit', 'melon_end') and style == 'jump':
            h += self.melon_need() * self.melon_weight()
        elif style == 'crouch':
            h -= MELON_CROUCH_DROP * self.scale * self.melon_weight()   # 숙인 그림의 입 높이
        return self.x + self.dir * self.size * MELON_MOUTH[0], self.y + h

    def melon_frame(self):
        """수박 거인 공격 프레임: 선 채로는 숨 들이켜기·뱉기 그림, 점프·쭈그리기는 그 줄 그림"""
        style = self.melon_style()
        if self.state == 'inhale':
            k = 1 - self.state_t / MELON_INHALE
            if style == 'jump':
                return 'jump', min(3, int(k * 4))                     # 무릎 굽히기 → 뛰어오르기
            if style == 'crouch':
                return 'crouch', min(3, int(k * 4))
            n = self.sh.frames['inhale']
            return 'inhale', min(n - 1, int(k * n))
        if self.state == 'spit':
            if style == 'jump':
                return 'jump', MELON_JUMP_HOLD[int(self.anim_t * 8) % 2]
            if style == 'crouch':
                return 'crouch', 3
            return 'spit', int(self.anim_t * 14) % self.sh.frames['spit']
        k = 1 - self.state_t / MELON_RECOVER                          # melon_end: 원래 자세로
        if style == 'jump':
            return 'jump', min(7, 6 + int(k * 2))                      # 내려와 착지
        if style == 'crouch':
            return 'crouch', max(0, 3 - int(k * 4))
        return 'walk', 0

    def melon_start(self):
        """주인공이 가까우면 그쪽을 보고 숨을 들이켠다. 노릴 층은 이때 정한다"""
        p = play_mode.player
        if self.melon_cd > 0 or p.dead or abs(p.x - self.x) > MELON_RANGE:
            return False
        if not (camera.x + 60 < self.x < camera.x + SCREEN_W - 60):
            return False                        # 화면에 보일 때만 (안 보이는 곳에서 쏘지 않는다)
        self.dir = 1 if p.x > self.x else -1
        self.melon_floor = max(1, min(4, p.floor()))
        self.state, self.state_t = 'inhale', MELON_INHALE
        self.seeds_left = MELON_SEEDS
        return True

    def update_melon(self):
        if self.state == 'inhale':
            if self.state_t <= 0:
                self.state, self.state_t = 'spit', MELON_SPIT
                mx, my = self.mouth()
                effect.add(effect.FloatText(mx + self.dir * 30, my + 50, '후!!!!', (255, 250, 240), 44))
                camera.shake(0.15, 5)
            return
        if self.state == 'spit':
            # 2초 동안 고르게 나눠 뱉는다
            due = MELON_SEEDS - int(self.state_t / MELON_SPIT * MELON_SEEDS)
            while MELON_SEEDS - self.seeds_left < min(MELON_SEEDS, due):
                self.seeds_left -= 1
                mx, my = self.mouth()
                game_world.add_object(Seed(mx, my, self.dir), LAYER_PROJECTILE)
                effect.steam(mx, my, 1, 6, (255, 220, 210), 14)
            if self.state_t <= 0:
                self.state, self.state_t = 'melon_end', MELON_RECOVER
            return
        if self.state_t <= 0:                   # melon_end: 원래 자세로 돌아왔다
            self.state = 'walk'
            self.melon_cd = MELON_CD

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
                return 0.0, False
            if self.guarding():
                dmg *= 0.15
        elif part == 'ankle':
            if self.armor > 0:
                self.armor -= 1
                effect.add(effect.Spark(self.x, self.y + 20, (255, 220, 160)))
            if self.kneel_t <= 0:
                self.kneel_age = 0.0
                camera.shake(0.08 * self.k)
                effect.steam(self.x, self.y + 6, 2 + self.k, self.size * 0.12, (170, 160, 150), 16 + 6 * self.k)
            self.kneel_t = 1.6 if self.kind == 'colossal' else KNEEL_TIME
            self.guard_t = 0.0
            if self.state in ('grab', 'throw', 'lunge_warn', 'lunge', 'lunge_end', 'inhale', 'spit', 'melon_end'):
                if self.kind == 'melon':
                    self.melon_cd = MELON_CD
                self.state = 'walk'
        elif self.armor > 0:
            dmg *= 0.4
        # 휘두르는 중에 베여도 공격은 끊기지 않는다. 걷다가 베이면 곧바로 반격할 준비 (손이 닿으면 바로 휘두른다)
        if self.state == 'walk' and self.kneel_t <= 0:
            self.grab_cd = min(self.grab_cd, HIT_GRAB_CD)
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
            effect.damage_number(hx, hy + 46, dmg, self.crit, 24)
        if self.hp <= 0:
            self.die()
            return dmg, True
        # 서 있다가 목덜미를 베였는데 버텼다: 가끔 곧바로 목 뒤를 후려치고, 아니면 한 번 손으로 목을 가린다
        if part == 'neck' and not self.boss and self.kneel_t <= 0 and self.state == 'walk':
            if random.random() < COUNTER_RATE and self.player_near_nape(1.6):
                self.start_swat(COUNTER_WARN)
            elif self.guard_t <= 0:
                self.guard_t = GUARD_REACT
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
        self.guard_t = max(0.0, self.guard_t - dt)
        self.swat_cd = max(0.0, self.swat_cd - dt)
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
        elif self.state in ('lunge_warn', 'lunge', 'lunge_end'):
            self.update_lunge(dt)
        elif self.state == 'swat':
            self.update_swat()
        elif self.state == 'throw':
            if self.state_t < 0.45 and not self.grabbed:
                self.grabbed = True
                self.throw_rock()
            if self.state_t <= 0:
                self.state = 'walk'
        elif self.state in ('inhale', 'spit', 'melon_end'):
            self.update_melon()
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

    def update_chase(self):
        """반경 안의 주인공을 향해 돌아선다. 손이 닿을 만큼 붙으면 멈춰 선다. 쫓는 중이면 True."""
        was = self.chasing
        self.chasing = False
        if not self.boss:
            cx, cy = play_mode.player.center()
            dx = cx - self.x
            r = LUNGE_CHASE_R if self.lunger() else CHASE_R
            self.chasing = math.hypot(dx, cy - (self.y + self.size * 0.35)) < r + self.size * 0.3
            if self.lunger() and play_mode.player.floor() != self.lane:
                self.chasing = False             # 빠른 마른 거인은 같은 층에 있는 주인공만 알아챈다
        if self.chasing:
            if abs(dx) > self.size * 0.08 + 8:
                self.dir = 1 if dx > 0 else -1
        elif was:
            self.dir = -1                        # 놓치면 다시 벽으로
        return self.chasing

    def chase_close(self):
        """쫓다가 공격할 거리까지 붙었나 (더 다가가지 않고 공격한다)"""
        dx = abs(play_mode.player.center()[0] - self.x)
        if self.lunger():
            return dx < LUNGE_START + self.size * 0.2
        return dx < self.size * 0.2 + 16

    def lunger(self):
        """돌진으로 공격하는 거인인가 (마른 거인)"""
        return self.sh is SHEETS['thin'] and not self.boss

    def lunge_reach(self):
        """돌진이 닿는 앞쪽 거리: 나아가는 거리 + 팔 길이"""
        return LUNGE_DIST + self.size * 0.4 + self.size * GRAB_FRONT + GRAB_PAD

    def try_lunge(self):
        """쫓다가 붙었고 주인공이 앞쪽 손 닿는 높이에 있으면 멈춰 서서 돌진 준비"""
        p = play_mode.player
        if self.grab_cd > 0 or p.invuln > 0 or not self.chasing or not self.chase_close():
            return
        cx, cy = p.center()
        rel = (cx - self.x) * self.dir
        if 0 < rel < self.lunge_reach() and self.y <= cy < self.y + self.size * GRAB_HIGH:
            self.state, self.state_t = 'lunge_warn', LUNGE_WARN
            self.grabbed = False

    def in_lunge_zone(self, cx, cy):
        rel = (cx - self.x) * self.dir
        return -10 < rel < self.size * GRAB_FRONT + GRAB_PAD and self.y <= cy < self.y + self.size * GRAB_HIGH

    def update_lunge(self, dt):
        if self.state == 'lunge_warn':
            if self.state_t <= 0:
                self.state, self.state_t = 'lunge', LUNGE_TIME
                effect.steam(self.x, self.y + 4, 2 + self.k, self.size * 0.1, (170, 160, 150), 14 + 5 * self.k)
            return
        if self.state == 'lunge':
            # 앞으로 확 나아간다. 벽·길 끝에서는 멈춘다
            step = (LUNGE_DIST + self.size * 0.4) / LUNGE_TIME * dt
            nx = self.x + self.dir * step
            stop = WALL_X + self.size * 0.14 + 6
            if (self.lane == 0 and nx <= stop) or not map_data.segment_at(self.lane, nx):
                nx = self.x
            self.x = nx
            self.step += step
            if not self.grabbed and self.in_lunge_zone(*play_mode.player.center()):
                self.grabbed = True
                play_mode.player.hurt(self.x, self.power())
            for a in play_mode.allies():
                if self.in_lunge_zone(*a.center()):
                    a.hurt(self.x)
            if self.state_t <= 0:
                self.state, self.state_t = 'lunge_end', LUNGE_END
            return
        if self.state_t <= 0:
            self.state = 'walk'
            self.grab_cd = LUNGE_CD

    def walk(self, dt):
        speed = self.speed
        if self.update_chase():
            if self.chase_close():
                speed = 0.0
        elif self.kind == 'erratic':
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
            p = play_mode.player
            nx, ny = self.nape()
            near = math.hypot(p.x - nx, p.y + 18 - ny) < 140
            if self.guard_t <= 0 and (self.guard_cd <= 0 or (near and self.guard_cd < 2.0)):
                self.guard_t, self.guard_cd = 1.4, 4.0
            if self.guarding():
                speed *= 0.4
        elif self.kind == 'melon':
            self.melon_cd -= dt
            if self.melon_start():
                return
        elif self.kind == 'thrower':
            self.throw_cd -= dt
            p = play_mode.player
            if self.throw_cd <= 0 and abs(p.x - self.x) < 800 and p.x < self.x:
                self.throw_cd = 3.2
                self.state, self.state_t = 'throw', 0.9
                self.grabbed = False
                return
        if self.guarding() and self.kind != 'smart':
            speed = 0.0                          # 목을 가리는 동안은 멈춰 선다

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
        if self.guarding() and self.kind != 'smart':
            return                               # 목을 다 가린 뒤에 공격한다
        if self.lunger():
            self.try_lunge()
        else:
            self.try_grab()
        if self.state == 'walk':
            self.try_swat()

    def update_run(self, dt, speed):
        """멀리 있으면 늘 달리고, 가까이에선 가끔 갑자기 질주한다. 달리는 속도를 돌려준다."""
        self.run_t = max(0.0, self.run_t - dt)
        self.run_cd -= dt
        if self.run_cd <= 0:
            self.run_t = random.uniform(1.2, 2.6)
            self.run_cd = self.run_t + (random.uniform(1.5, 4.0) if self.kind == 'erratic' else random.uniform(3.0, 8.0))
        far = abs(play_mode.player.x - self.x) > RUN_FAR
        was = self.running
        chase = self.chasing and speed > 0
        self.running = self.kind not in NO_RUN and not self.guarding() and speed > 0 and (far or self.run_t > 0 or chase)
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
        """앞쪽, 발밑부터 키의 GRAB_HIGH 높이까지 맞는다. 목 높이는 안전하다."""
        rel = (cx - self.x) * self.dir
        low, high = self.y, self.y + self.size * GRAB_HIGH
        return 0 < rel < self.size * front + GRAB_PAD + extra and low < cy < high

    def try_grab(self):
        p = play_mode.player
        if self.grab_cd > 0 or p.invuln > 0:
            return
        if self.player_in_grab_zone(GRAB_START):
            self.state, self.state_t = 'grab', GRAB_TIME
            self.grabbed = False

    def swat_r(self):
        """목 뒤 후려치기가 닿는 반지름 (목덜미 중심)"""
        return 46 + self.size * 0.06

    def player_near_nape(self, scale=1.0):
        px, py = play_mode.player.center()
        nx, ny = self.nape()
        return math.hypot(px - nx, py - ny) < self.swat_r() * scale

    def start_swat(self, warn):
        self.state, self.state_t = 'swat', warn + SWAT_SWING
        self.swat_warn = warn
        self.grabbed = False

    def try_swat(self):
        """목덜미 근처에 머무는 주인공을 손바닥으로 후려친다 (보스는 아직 안 쓴다)"""
        if self.boss or self.swat_cd > 0 or play_mode.player.invuln > 0:
            return
        if self.player_near_nape(1.3):
            self.start_swat(SWAT_WARN)

    def update_swat(self):
        """손을 올리고(swat_warn) → 휘두르기 시작할 때 한 번 판정 → 끝까지 휘두른 뒤 걷기로"""
        if not self.grabbed and self.state_t <= SWAT_SWING:
            self.grabbed = True
            if self.player_near_nape():
                play_mode.player.hurt(self.x, self.power())
        if self.state_t <= 0:
            self.state = 'walk'
            self.swat_cd = random.uniform(*SWAT_CD)

    def update_grab(self):
        if not self.grabbed and self.state_t < GRAB_HIT_AT:
            self.grabbed = True
            if self.player_in_grab_zone(GRAB_FRONT, 20):
                play_mode.player.hurt(self.x, self.power())
            for a in play_mode.allies():
                if self.in_grab_zone(*a.center(), GRAB_FRONT, 20):
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
        if self.state == 'lunge_warn' and self.alive() and self.kneel_t <= 0:
            # 돌진: 앞으로 덮칠 길 전체 (발밑 ~ 키의 GRAB_HIGH)
            k = min(1.0, 1 - self.state_t / LUNGE_WARN)
            x1, x2 = sorted((self.x, self.x + self.dir * self.lunge_reach()))
            sx1, sy1 = camera.to_screen(x1, self.y)
            sx2, sy2 = camera.to_screen(x2, self.y + self.size * GRAB_HIGH)
            render.rect(sx1, sy1, sx2, sy2, DANGER, 40 + 90 * k)
            fill = (sx2 - sx1) * k
            if self.dir < 0:
                render.rect(sx1, sy1, sx1 + fill, sy1 + 4, DANGER, 230)
            else:
                render.rect(sx2 - fill, sy1, sx2, sy1 + 4, DANGER, 230)
        if self.state == 'grab' and not self.grabbed:
            # 휘두르기: 손이 닿는 앞쪽, 발밑부터 키의 GRAB_HIGH 높이 (in_grab_zone 과 같은 범위)
            k = min(1.0, (GRAB_TIME - self.state_t) / (GRAB_TIME - GRAB_HIT_AT))
            reach = self.size * GRAB_FRONT + GRAB_PAD + 20
            low = self.y
            high = self.y + self.size * GRAB_HIGH
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
        if self.state == 'inhale' and self.alive() and self.kneel_t <= 0:
            # 수박씨가 날아갈 층: 입 앞쪽으로 그 층 한 줄 전체
            k = min(1.0, 1 - self.state_t / MELON_INHALE)
            mx, my = self.mouth()
            low = LANE_Y[self.melon_floor]
            x1, x2 = sorted((mx, mx + self.dir * Seed.RANGE))
            sx1, sy1 = camera.to_screen(x1, low)
            sx2, sy2 = camera.to_screen(x2, low + 60)
            render.rect(sx1, sy1, sx2, sy2, DANGER, 30 + 80 * k)
            fill = (sx2 - sx1) * k
            if self.dir < 0:
                render.rect(sx2 - fill, sy1, sx2, sy1 + 4, DANGER, 230)
            else:
                render.rect(sx1, sy1, sx1 + fill, sy1 + 4, DANGER, 230)
            # 공기를 빨아들이는 바람줄: 앞쪽에서 입으로 모여든다
            msx, msy = camera.to_screen(mx, my)
            for i in range(7):
                ph = (self.anim_t * 2.2 + i / 7) % 1.0
                ang = (i / 6 - 0.5) * 1.6
                d = 30 + 150 * (1 - ph)
                x0 = msx + self.dir * d * math.cos(ang)
                y0 = msy + d * math.sin(ang)
                ux, uy = (msx - x0) / d, (msy - y0) / d
                render.line(x0, y0, x0 + ux * 22, y0 + uy * 22, (235, 240, 245), 200 * ph)
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
        r = self.sh.rows.index(row)
        if self.armor > 0:
            img, skin = self.sheet_armor, zone_color(self.x, 'skin')
        else:
            # 기본 거인은 원본 그림 색 그대로 그린다 (구간 피부색을 곱하지 않음). 거대 거인만 붉게
            img, skin = self.sheet, (255, 255, 255)
            if self.kind == 'colossal':
                skin = (255, 199, 178)
        alpha = 1.0
        if self.state == 'dead' and self.state_t > DEAD_FADE[0]:
            alpha = max(0.0, 1 - (self.state_t - DEAD_FADE[0]) / (DEAD_FADE[1] - DEAD_FADE[0]))
        if self.flash_t > 0:
            skin = (255, 255, 255)
            if self.armor <= 0:
                img = self.sheet_flash
        render.tint(img, skin, alpha)
        sx, sy = camera.to_screen(self.x, self.y)
        if img is self.sheet_armor:
            # 갑옷 시트는 줄 구성과 프레임 수, 칸 크기가 달라서 따로 맞춘다
            m = ARMOR_META
            n = ARMOR_FRAMES[row]
            fr = min(n - 1, fr * n // self.sh.frames[row])
            r, nrows, cpx, cell = ARMOR_ROWS.index(row), len(ARMOR_ROWS), m['cell_px'], m['cell']
            scale = self.size / m['height']
        else:
            sh = self.sh
            m, nrows, cpx, cell, scale = sh.meta, len(sh.rows), sh.cell_px, sh.cell, self.scale
        w = cell * scale
        lift, sq = self.melon_pose()
        img.clip_composite_draw(fr * cpx, (nrows - 1 - r) * cpx, cpx, cpx, 0,
                                'h' if self.dir > 0 else '', sx, sy + lift + (cell / 2 - m['base']) * scale * sq, w, w * sq)
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
