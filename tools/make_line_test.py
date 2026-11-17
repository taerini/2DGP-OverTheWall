"""선 그림 스타일 시험: 거인 1종(걷기)과 1구간 배경을 코드로 그린다.

픽셀 그림 대신 '굵고 진한 외곽선 + 단색 + 크고 딱 떨어지는 그늘(셀 셰이딩)'으로 그린다.
- 색은 채도를 낮춘 올리브·회녹색. 멀수록 안개 색에 묻히는 납작한 실루엣
- 크게(S배) 그린 뒤 줄여서 선을 부드럽게 만든다
- 거인은 머리·몸통·팔·다리 조각을 따로 그리고, 관절에서 돌려 걷는 장면을 만든다 (컷아웃 방식)

실행: python tools/make_line_test.py
결과: resource/line_test/*.png  (보기: python tools/line_test_view.py)
"""
import json
import math
import os
import random

from PIL import Image, ImageChops, ImageDraw, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'resource', 'line_test')
os.makedirs(OUT, exist_ok=True)

S = 4                    # 크게 그리는 배율
INK = (30, 30, 28)       # 외곽선 색
LINE_W = 3.0             # 외곽선 굵기 (최종 px)
SCREEN_W, SCREEN_H = 1280, 720
LANE_Y = [70 + 115 * i for i in range(5)]


# ------------------------------------------------------------ 그리기 도구
def spline(pts, n=10, closed=True):
    """점들을 부드럽게 잇는 곡선 (캣멀롬)"""
    out = []
    m = len(pts)
    for i in (range(m) if closed else range(m - 1)):
        p0 = pts[(i - 1) % m] if closed or i > 0 else pts[0]
        p1, p2 = pts[i], pts[(i + 1) % m]
        p3 = pts[(i + 2) % m] if closed or i + 2 < m else pts[-1]
        for k in range(n):
            t = k / n
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * (2 * p1[j] + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2
                                    + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3) for j in range(2)))
    if not closed:
        out.append(pts[-1])
    return out


def ellipse_pts(cx, cy, rx, ry, n=40):
    return [(cx + rx * math.cos(2 * math.pi * i / n), cy + ry * math.sin(2 * math.pi * i / n)) for i in range(n)]


def capsule_pts(p0, p1, r0, r1, n=14):
    """p0에서 p1로 가늘어지는 팔다리 모양"""
    a = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
    pts = [(p1[0] + r1 * math.cos(a - math.pi / 2 + math.pi * i / n), p1[1] + r1 * math.sin(a - math.pi / 2 + math.pi * i / n))
           for i in range(n + 1)]
    pts += [(p0[0] + r0 * math.cos(a + math.pi / 2 + math.pi * i / n), p0[1] + r0 * math.sin(a + math.pi / 2 + math.pi * i / n))
            for i in range(n + 1)]
    return pts


class Canvas:
    """S배로 크게 그리는 RGBA 판. 좌표는 최종 px로 넘긴다."""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.img = Image.new('RGBA', (int(w * S), int(h * S)), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img)

    @staticmethod
    def _s(pts, ox=0, oy=0):
        return [((x + ox) * S, (y + oy) * S) for x, y in pts]

    def shape(self, pts, fill, shade=None, shade_k=(5, 4), ink=INK, lw=LINE_W, ox=0, oy=0):
        """채운 모양 + 그늘(오른쪽 아래로 k 만큼 밀었을 때 모양 밖으로 나가는 띠) + 외곽선"""
        sp = self._s(pts, ox, oy)
        mask = Image.new('L', self.img.size, 0)
        ImageDraw.Draw(mask).polygon(sp, fill=255)
        self.img.paste(Image.new('RGBA', self.img.size, fill + (255,)), (0, 0), mask)
        if shade:
            moved = Image.new('L', self.img.size, 0)
            moved.paste(mask, (int(-shade_k[0] * S), int(-shade_k[1] * S)))
            self.img.paste(Image.new('RGBA', self.img.size, shade + (255,)), (0, 0), ImageChops.subtract(mask, moved))
        if ink:
            self.d.line(sp + [sp[0]], fill=ink + (255,), width=max(1, int(lw * S)), joint='curve')

    def flat(self, pts, fill, ox=0, oy=0):
        """외곽선 없는 납작한 실루엣 (먼 배경)"""
        self.d.polygon(self._s(pts, ox, oy), fill=fill + (255,))

    def line(self, pts, col=INK, lw=1.6, ox=0, oy=0):
        sp = self._s(pts, ox, oy)
        self.d.line(sp, fill=col + (255,), width=max(1, int(lw * S)), joint='curve')
        r = lw * S / 2
        for x, y in (sp[0], sp[-1]):            # 선 끝을 둥글게
            self.d.ellipse((x - r, y - r, x + r, y + r), fill=col + (255,))

    def dot(self, x, y, r, col, ox=0, oy=0):
        x, y = (x + ox) * S, (y + oy) * S
        self.d.ellipse((x - r * S, y - r * S, x + r * S, y + r * S), fill=col + (255,))

    def final(self):
        return self.img.resize((self.w, self.h), Image.LANCZOS)


# ------------------------------------------------------------ 거인 (오른쪽을 보고 그린 뒤 뒤집는다)
SKIN = (196, 172, 148)
SKIN_SH = (138, 116, 104)
BACK = (160, 140, 122)        # 뒤쪽 팔다리는 한 톤 어둡게
BACK_SH = (112, 94, 86)
SCAR = (168, 92, 82)
CLOTH, CLOTH_SH = (104, 88, 72), (72, 60, 52)

PART_BOX = 340               # 조각 하나를 그리는 판 크기 (최종 px), 관절은 가운데


def part(draw_fn):
    c = Canvas(PART_BOX, PART_BOX)
    draw_fn(c, PART_BOX / 2, PART_BOX / 2)
    return c.img                                  # 크게 그린 상태 그대로 (돌린 뒤 한 번에 줄인다)


# 몸통 기준 관절 위치 (엉덩이 = 0,0)
NECK = (30, -118)
SHOULDER_F = (22, -108)
SHOULDER_B = (-18, -112)


def p_torso(c, ox, oy):
    # 굽은 등, 넓은 어깨, 앞으로 나온 목
    pts = [(-30, 8), (-36, -30), (-46, -76), (-44, -112), (-26, -134), (6, -140), (30, -132), (44, -112),
           (44, -84), (38, -52), (34, -20), (28, 8), (0, 14)]
    c.shape(spline(pts), SKIN, SKIN_SH, (30, 16), ox=ox, oy=oy)
    c.line(spline([(4, -98), (20, -90), (38, -96)], 6, False), INK, 2.0, ox, oy)            # 가슴
    c.line(spline([(10, -60), (20, -54), (32, -58)], 6, False), INK, 1.6, ox, oy)           # 배
    c.line([(18, -30), (21, -30)], INK, 2.4, ox, oy)                                         # 배꼽
    c.line(spline([(-34, -96), (-28, -84), (-30, -70)], 4, False), INK, 1.6, ox, oy)        # 등 근육
    for x, y in ((-10, -112), (-2, -104)):                                                  # 긁힌 상처
        c.line([(x, y), (x + 12, y - 6)], SCAR, 1.8, ox, oy)
    # 허리를 두른 해진 천
    rag = [(-34, -8), (36, -10), (36, 6), (30, 26), (24, 16), (16, 30), (8, 18), (-2, 32), (-10, 18), (-20, 28), (-26, 14), (-34, 10)]
    c.shape(rag, CLOTH, CLOTH_SH, (5, 5), ox=ox, oy=oy)


def p_head(c, ox, oy):
    # 목 아래(0,0). 몸에 비해 작은 머리
    c.shape([(-14, 8), (-11, -12), (14, -12), (18, 8)], SKIN, SKIN_SH, (6, 0), ox=ox, oy=oy)
    head = [(-18, -16), (-22, -36), (-14, -54), (4, -62), (22, -56), (30, -42), (32, -26), (26, -12), (12, -6), (-6, -6)]
    c.shape(spline(head), SKIN, SKIN_SH, (14, 9), ox=ox, oy=oy)
    c.shape(spline([(-14, -36), (-22, -32), (-20, -22), (-12, -24)]), SKIN, SKIN_SH, (2, 2), ox=ox, oy=oy)   # 귀
    c.line(spline([(-8, -54), (-14, -64)], 2, False), INK, 1.8, ox, oy)                      # 성긴 머리카락
    c.line(spline([(4, -62), (2, -71)], 2, False), INK, 1.8, ox, oy)
    # 얼굴: 짙은 눈두덩 아래 작은 빛나는 눈, 이를 드러낸 입
    c.shape([(4, -44), (30, -46), (28, -38), (6, -37)], SKIN_SH, None, ink=None, ox=ox, oy=oy)
    c.dot(22, -40, 2.6, (238, 226, 170), ox, oy)
    c.dot(11, -40, 2.3, (238, 226, 170), ox, oy)
    c.line([(2, -46), (31, -48)], INK, 2.4, ox, oy)                                          # 눈썹
    c.line(spline([(26, -36), (33, -28), (26, -26)], 4, False), INK, 1.8, ox, oy)            # 코
    teeth = [(8, -20), (30, -21), (28, -14), (10, -13)]
    c.shape(teeth, (226, 218, 196), None, ox=ox, oy=oy, lw=2.0)
    for x in (14, 19, 24):
        c.line([(x, -26.5), (x, -19.5)], INK, 1.0, ox, oy)


def profile_pts(length, prof):
    """근육 윤곽: prof = [(길이 비율, 앞쪽 두께, 뒤쪽 두께), ...] 를 따라 부드럽게 잇는다"""
    front = [(wf, t * length) for t, wf, wb in prof]
    back = [(-wb, t * length) for t, wf, wb in reversed(prof)]
    return spline(front + back, 6)


PROFILES = {
    'thigh': [(-0.14, 9, 9), (0.0, 22, 22), (0.35, 25, 22), (0.75, 18, 17), (1.0, 15, 14), (1.12, 8, 8)],
    'shin': [(-0.12, 9, 9), (0.0, 16, 15), (0.28, 14, 20), (0.62, 12, 14), (1.0, 10, 11)],
    'upper': [(-0.16, 10, 10), (0.0, 20, 19), (0.3, 23, 17), (0.7, 16, 15), (1.0, 13, 13), (1.12, 7, 7)],
    'lower': [(-0.1, 9, 9), (0.0, 14, 13), (0.3, 18, 15), (0.8, 11, 10), (1.0, 10, 10), (1.06, 8, 8)],
}


def limb(kind, length, skin, sh, hand=None, foot=None, scar=False):
    def fn(c, ox, oy):
        c.shape(profile_pts(length, PROFILES[kind]), skin, sh, (16, 4), ox=ox, oy=oy)
        if kind == 'upper':
            c.line(spline([(6, length * 0.2), (12, length * 0.45), (8, length * 0.62)], 4, False), INK, 1.4, ox, oy)  # 이두
        if kind == 'shin':
            c.line(spline([(-6, length * 0.2), (-10, length * 0.42)], 2, False), INK, 1.3, ox, oy)                  # 종아리
        if scar:
            c.line([(-4, length * 0.35), (8, length * 0.3)], SCAR, 1.8, ox, oy)
        if hand:
            c.shape(spline([(-hand, length - 2), (hand, length - 4), (hand + 4, length + hand * 1.3), (2, length + hand * 1.9),
                            (-hand - 2, length + hand * 1.2)]), skin, sh, (6, 3), ox=ox, oy=oy)
            for dx in (-4, 3):                                                              # 손가락 틈
                c.line([(dx, length + hand * 1.2), (dx + 1, length + hand * 1.75)], INK, 1.4, ox, oy)
        if foot:
            c.shape(spline([(-14, length - 6), (16, length - 4), (foot + 6, length + 6), (foot + 2, length + 13), (-16, length + 13)]),
                    skin, sh, (4, 4), ox=ox, oy=oy)
            for dx in (foot - 6, foot - 14):                                               # 발가락
                c.line([(dx, length + 6), (dx, length + 12)], INK, 1.4, ox, oy)
    return fn


THIGH, SHIN, UPPER, LOWER = 64, 60, 76, 70
PARTS = {
    'torso': part(p_torso),
    'head': part(p_head),
    'thigh_f': part(limb('thigh', THIGH, SKIN, SKIN_SH)),
    'shin_f': part(limb('shin', SHIN, SKIN, SKIN_SH, foot=30)),
    'upper_f': part(limb('upper', UPPER, SKIN, SKIN_SH, scar=True)),
    'lower_f': part(limb('lower', LOWER, SKIN, SKIN_SH, hand=16)),
    'thigh_b': part(limb('thigh', THIGH, BACK, BACK_SH)),
    'shin_b': part(limb('shin', SHIN, BACK, BACK_SH, foot=30)),
    'upper_b': part(limb('upper', UPPER, BACK, BACK_SH)),
    'lower_b': part(limb('lower', LOWER, BACK, BACK_SH, hand=16)),
}

FRAME_W, FRAME_H = 260, 400
FRAMES = 8
HIP_Y = 230
FOOT_PAD = 400 - (HIP_Y + THIGH + SHIN + 13)      # 그림 아래 빈 칸 (발바닥 아래)


def rot(v, deg):
    """화면(아래가 +y)에서 시계 반대 방향 회전. 아래를 보는 팔다리를 +각도로 돌리면 앞(오른쪽)으로 간다"""
    a = math.radians(deg)
    return (v[0] * math.cos(a) + v[1] * math.sin(a), -v[0] * math.sin(a) + v[1] * math.cos(a))


def add(a, b):
    return (a[0] + b[0], a[1] + b[1])


def stamp(frame, name, joint, deg):
    """조각을 관절 위치에 놓고 deg 만큼 돌려 붙인다 (모두 S배 크기에서)"""
    img = PARTS[name].rotate(deg, resample=Image.BICUBIC, center=(PART_BOX * S / 2, PART_BOX * S / 2))
    frame.alpha_composite(img, (int(joint[0] * S - PART_BOX * S / 2), int(joint[1] * S - PART_BOX * S / 2)))


def giant_frame(i):
    p = 2 * math.pi * i / FRAMES
    frame = Image.new('RGBA', (FRAME_W * S, FRAME_H * S), (0, 0, 0, 0))
    hip = (120, HIP_Y + 4 * abs(math.sin(p)) - 2)     # 한 걸음마다 쿵 하고 내려앉는다
    lean = -8                                          # 앞으로 숙인 자세
    leg = 22 * math.sin(p)
    arm = 18 * math.sin(p)

    def leg_at(prefix, a, phase):
        knee_bend = -(8 + 16 * max(0.0, math.sin(phase + 0.6)))
        stamp(frame, 'thigh_' + prefix, hip, a)
        stamp(frame, 'shin_' + prefix, add(hip, rot((0, THIGH), a)), a + knee_bend)

    def arm_at(prefix, sh, a):
        stamp(frame, 'upper_' + prefix, sh, a)
        stamp(frame, 'lower_' + prefix, add(sh, rot((0, UPPER), a)), a + 16 + 6 * math.sin(p))

    arm_at('b', add(hip, rot(SHOULDER_B, lean)), arm - 2)
    leg_at('b', -leg, p + math.pi)
    stamp(frame, 'torso', hip, lean)
    stamp(frame, 'head', add(hip, rot(NECK, lean)), lean - 6 + 3 * math.sin(2 * p))
    leg_at('f', leg, p)
    arm_at('f', add(hip, rot(SHOULDER_F, lean)), -arm - 2)
    return ImageOps.mirror(frame.resize((FRAME_W, FRAME_H), Image.LANCZOS))   # 거인은 왼쪽(우리 벽)으로 걷는다


def make_giant():
    sheet = Image.new('RGBA', (FRAME_W * FRAMES, FRAME_H), (0, 0, 0, 0))
    for i in range(FRAMES):
        sheet.alpha_composite(giant_frame(i), (i * FRAME_W, 0))
    sheet.save(os.path.join(OUT, 'giant_walk.png'))
    with open(os.path.join(OUT, 'giant_walk_meta.json'), 'w') as f:
        json.dump({'frame_w': FRAME_W, 'frame_h': FRAME_H, 'frames': FRAMES, 'foot_pad': FOOT_PAD}, f)
    return sheet


# ------------------------------------------------------------ 1구간 배경 (벽 밖, 안개 낀 숲 가장자리)
BG_W = 2560
FOG = (204, 212, 182)        # 안개 색: 멀수록 이 색에 가까워진다


def mix(a, b, t):
    return tuple(int(a[k] + (b[k] - a[k]) * t) for k in range(3))


def make_sky():
    img = Image.new('RGBA', (SCREEN_W, SCREEN_H))
    d = ImageDraw.Draw(img)
    top, bot = (170, 184, 152), (214, 220, 194)
    for y in range(SCREEN_H):
        d.line([(0, y), (SCREEN_W, y)], fill=mix(top, bot, y / SCREEN_H) + (255,))
    img.save(os.path.join(OUT, 'sky.png'))
    return img


def trunk(c, x, base, top, w, col, seed, branches=3):
    """곧게 선 마른 나무 줄기 실루엣 (가지 몇 개)"""
    random.seed(seed)
    lean = random.uniform(-14, 14)
    pts = [(x - w, base), (x - w * 0.7 + lean, top), (x + w * 0.7 + lean, top), (x + w, base)]
    c.flat(pts, col)
    for _ in range(branches):
        t = random.uniform(0.25, 0.8)
        bx, by = x + lean * t, base + (top - base) * t
        side = random.choice((-1, 1))
        L = random.uniform(30, 70) * (w / 14 + 0.5)
        c.flat([(bx, by), (bx + side * L, by - L * 0.6), (bx + side * L * 0.95, by - L * 0.6 - 4), (bx, by - w * 0.8)], col)


def make_far():
    c = Canvas(BG_W, SCREEN_H)
    # 가장 먼 줄: 안개에 거의 묻힌 키 큰 줄기들
    random.seed(1)
    x = 20
    while x < BG_W:
        trunk(c, x, 640, -40, random.uniform(10, 18), mix((150, 164, 134), FOG, 0.55), int(x), 2)
        x += random.uniform(90, 200)
    # 멀리 보이는 우리 벽: 낮고 긴 성벽 실루엣과 탑
    wall = mix((130, 144, 118), FOG, 0.45)
    for x0 in range(0, BG_W, 1280):
        pts = [(x0, 640), (x0, 470)]
        for k in range(0, 1281, 32):                                   # 성가퀴
            pts += [(x0 + k, 470), (x0 + k, 462), (x0 + k + 16, 462), (x0 + k + 16, 470)]
        pts += [(x0 + 1280, 470), (x0 + 1280, 640)]
        c.flat(pts, wall)
        for tx in (x0 + 260, x0 + 900):
            c.flat([(tx - 26, 470), (tx - 22, 400), (tx + 22, 400), (tx + 26, 470)], wall)
            c.flat([(tx - 30, 400), (tx, 360), (tx + 30, 400)], wall)
    # 조금 가까운 줄
    random.seed(2)
    x = 60
    while x < BG_W:
        trunk(c, x, 680, -40, random.uniform(14, 24), mix((120, 136, 108), FOG, 0.3), int(x) + 7, 3)
        x += random.uniform(160, 320)
    img = c.final()
    img.save(os.path.join(OUT, 'far.png'))
    return img


def make_mid():
    c = Canvas(BG_W, SCREEN_H)
    random.seed(3)
    x = 100
    while x < BG_W:                                                   # 가까운 어두운 줄기
        trunk(c, x, 720, -60, random.uniform(22, 36), (78, 92, 70), int(x) + 13, 4)
        x += random.uniform(260, 480)
    # 이끼 덮인 바위 덩어리 (외곽선 있음)
    random.seed(4)
    for k in range(7):
        bx = 150 + k * 360 + random.uniform(-60, 60)
        w = random.uniform(70, 130)
        rock = spline([(bx - w, 700), (bx - w * 0.8, 640), (bx - w * 0.2, 610), (bx + w * 0.5, 622), (bx + w, 664), (bx + w * 0.9, 700)])
        c.shape(rock, (112, 122, 100), (86, 96, 80), (16, 10), ink=(40, 44, 36), lw=2.4)
        moss = spline([(bx - w * 0.8, 646), (bx - w * 0.2, 616), (bx + w * 0.5, 628), (bx + w * 0.7, 640), (bx, 632), (bx - w * 0.5, 648)])
        c.shape(moss, (132, 154, 92), None, ink=(40, 44, 36), lw=2.0)
    img = c.final()
    img.save(os.path.join(OUT, 'mid.png'))
    return img


LEDGE_W, LEDGE_H = 360, 40
STONE, STONE_SH = (106, 112, 92), (78, 84, 70)
MOSS, MOSS_SH = (128, 150, 84), (104, 124, 70)


def make_ledge():
    """한 층 발판: 이끼 덮인 돌 띠, 이끼가 아래로 흘러내린다"""
    o = 6
    c = Canvas(LEDGE_W + 2 * o, LEDGE_H + 2 * o + 16)
    random.seed(5)
    body = [(o + 4, o + 8), (o + LEDGE_W - 4, o + 6), (o + LEDGE_W, o + 20), (o + LEDGE_W - 8, o + LEDGE_H),
            (o + 10, o + LEDGE_H + 2), (o, o + 22)]
    c.shape(body, STONE, STONE_SH, (0, 12))
    for k in range(1, 6):                                            # 돌 이음매
        x0 = o + k * LEDGE_W / 6 + random.uniform(-10, 10)
        c.line([(x0, o + 12), (x0 + random.uniform(-4, 4), o + LEDGE_H - 2)], INK, 1.4)
    moss = [(o - 2, o + 14), (o + 2, o + 2)]
    x = o + 2
    while x < o + LEDGE_W:
        x += random.uniform(14, 30)
        moss.append((min(x, o + LEDGE_W + 2), o + random.uniform(0, 4)))
    moss.append((o + LEDGE_W + 2, o + 14))
    x = o + LEDGE_W
    while x > o + 10:                                                # 아래 가장자리: 흘러내린 이끼
        drip = random.random() < 0.3
        moss.append((x, o + (random.uniform(20, 30) if drip else random.uniform(11, 15))))
        x -= random.uniform(10, 22)
    moss.append((o, o + 14))
    c.shape(moss, MOSS, MOSS_SH, (0, 4))
    img = c.final()
    img.save(os.path.join(OUT, 'ledge.png'))
    return img


def make_ground():
    c = Canvas(BG_W, 100)
    random.seed(6)
    top = [(x, 16 + 6 * math.sin(x / 90) + random.uniform(-2, 2)) for x in range(0, BG_W + 41, 40)]
    c.shape([(-10, 100)] + top + [(BG_W + 10, 100)], (92, 98, 78), (70, 76, 62), (0, 30))
    moss = [(x, y - 6 + random.uniform(-2, 2)) for x, y in top]
    under = [(x, y + 6 + (random.uniform(4, 12) if random.random() < 0.25 else 0)) for x, y in reversed(top)]
    c.shape(moss + under, MOSS, MOSS_SH, (0, 4))
    img = c.final()
    img.save(os.path.join(OUT, 'ground.png'))
    return img


def main():
    make_giant()
    make_sky()
    make_far()
    make_mid()
    make_ledge()
    make_ground()
    print('done:', OUT)


if __name__ == '__main__':
    main()
