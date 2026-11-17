"""벽 너머 리소스 생성기.

모든 이미지는 외부 리소스 없이 이 스크립트가 직접 그린다.
실행: python tools/make_sprites.py  →  resource/*.png, resource/giant_meta.json, docs/hero_sheet_guide.png
"""
import json
import math
import os
import random

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'resource')
DOCS = os.path.join(ROOT, 'docs')
FONT_KR = 'C:/Windows/Fonts/malgunbd.ttf'

S = 4                    # 슈퍼샘플링 배율 (크게 그리고 줄여서 부드럽게)
CLEAR = (0, 0, 0, 0)
W, H = 1280, 720


def save(img, name, folder=OUT):
    img.save(os.path.join(folder, name))
    print('saved', name, img.size)


def shrink(img):
    return img.resize((img.width // S, img.height // S), Image.LANCZOS)


def make_sheet(rows, cell_w, cell_h):
    """rows: 프레임(Image) 리스트의 리스트. 위에서부터 한 줄씩 배치한다."""
    cols = max(len(r) for r in rows)
    sheet = Image.new('RGBA', (cols * cell_w, len(rows) * cell_h), CLEAR)
    for r, frames in enumerate(rows):
        for c, fr in enumerate(frames):
            sheet.paste(fr, (c * cell_w, r * cell_h), fr)
    return sheet


# ---------------------------------------------------------------- 그리기 도구
class Pen:
    """y 가 위로 커지는 로컬 좌표로 그린다. (ox, oy)는 셀 안에서 로컬 원점(발밑)의 위치, k 는 배율."""

    def __init__(self, img, ox, oy, k=1.0):
        self.img = img
        self.d = ImageDraw.Draw(img)
        self.ox, self.oy, self.k = ox, oy, k

    def p(self, x, y):
        return (self.ox + x * self.k) * S, (self.oy - y * self.k) * S

    def circle(self, c, r, col):
        x, y = self.p(*c)
        r = r * self.k * S
        self.d.ellipse((x - r, y - r, x + r, y + r), fill=col)

    def ellipse(self, c, rx, ry, col):
        x, y = self.p(*c)
        self.d.ellipse((x - rx * self.k * S, y - ry * self.k * S, x + rx * self.k * S, y + ry * self.k * S), fill=col)

    def limb(self, a, b, w, col):
        self.d.line([self.p(*a), self.p(*b)], fill=col, width=max(1, int(w * self.k * S)))
        self.circle(a, w / 2, col)
        self.circle(b, w / 2, col)

    def poly(self, pts, col):
        self.d.polygon([self.p(*q) for q in pts], fill=col)

    def line(self, pts, col, w=1.0):
        self.d.line([self.p(*q) for q in pts], fill=col, width=max(1, int(w * self.k * S)), joint='curve')


def add(a, b):
    return a[0] + b[0], a[1] + b[1]


def mul(a, s):
    return a[0] * s, a[1] * s


def down_dir(a):
    """아래를 0 으로, 앞쪽(+x)으로 기울수록 + 인 각도의 방향 벡터"""
    return math.sin(a), -math.cos(a)


def polar(a):
    return math.cos(a), math.sin(a)


def rotate(p, c, a):
    x, y = p[0] - c[0], p[1] - c[1]
    ca, sa = math.cos(a), math.sin(a)
    return c[0] + x * ca - y * sa, c[1] + x * sa + y * ca


def ik(a, b, l1, l2, bend):
    """a 에서 b 로 뻗는 두 마디의 가운데 관절. bend 는 꺾이는 쪽 (+1/-1)"""
    dx, dy = b[0] - a[0], b[1] - a[1]
    d = max(1e-3, min(l1 + l2 - 1e-3, math.hypot(dx, dy)))
    t = (l1 * l1 - l2 * l2 + d * d) / (2 * d)
    h = math.sqrt(max(0.0, l1 * l1 - t * t))
    ux, uy = dx / d, dy / d
    return a[0] + ux * t - uy * h * bend, a[1] + uy * t + ux * h * bend


# ================================================================ 주인공
HERO_CELL = 64
HERO_BASE = 8            # 발 기준선: 칸 아래에서 8px 위
HERO_ROWS = [('idle', 4), ('run', 6), ('wire', 4), ('air', 2),
             ('slashQ', 4), ('slashW', 4), ('spinE', 6), ('hit', 3)]

THIGH, SHIN, TORSO, NECK, HEAD_R = 8.5, 8.5, 12.0, 1.4, 3.7
UARM, FARM, SWORD = 6.3, 6.0, 11.0

INK = (9, 10, 12, 255)
INK_BACK = (38, 40, 46, 255)
CAPE = (60, 112, 72, 255)          # 조사병단 초록 망토 (주인공·동료 모두)
CAPE_DARK = (36, 74, 48, 255)
CAPE_EDGE = (128, 178, 128, 255)
BLADE = (232, 244, 255, 255)
BLADE_GLOW = (150, 205, 255, 110)
EYE = (235, 245, 245, 255)
HERO_OUTLINE = (255, 246, 222)    # 주인공만 밝은 테두리를 둘러 동료와 구분한다
SCARF = (196, 34, 42, 255)        # 미카사: 초록 망토 대신 빨간 목도리
SCARF_DARK = (122, 18, 26, 255)
SCARF_EDGE = (238, 98, 92, 255)
BOB = (238, 202, 74, 255)          # 아르민: 노란 단발머리
BOB_EDGE = (168, 128, 30, 255)


def cape_shape(anchor, ang, length, bend, wave, phase, w0=2.8, w1=8.6):
    """망토의 중심선을 따라 폭을 넓혀 가며 양쪽 가장자리와 밑단을 만든다."""
    n = 9
    center = []
    for i in range(n):
        t = i / (n - 1)
        a = ang + bend * t
        base = add(anchor, mul(polar(ang + bend * t * 0.5), length * t))
        nrm = polar(a + math.pi / 2)
        off = wave * t * math.sin(phase + t * 4.2)
        center.append((add(base, mul(nrm, off)), a, w0 + (w1 - w0) * t))
    left, right = [], []
    for c, a, w in center:
        nrm = polar(a + math.pi / 2)
        left.append(add(c, mul(nrm, w / 2)))
        right.append(add(c, mul(nrm, -w / 2)))
    # 밑단은 물결 모양으로
    end_c, end_a, end_w = center[-1]
    hem = []
    for i in range(1, 6):
        s = i / 6
        p = add(right[-1], mul(add(left[-1], mul(right[-1], -1)), s))
        bump = 1.1 if i % 2 else -0.3
        hem.append(add(p, mul(polar(end_a), bump)))
    outline = left + hem[::-1] + right[::-1]
    return outline, [c for c, _, _ in center]


def hero_pose(P):
    """포즈 값으로 관절 위치를 계산한다. 몸 기준 좌표 → 회전 → 이동 순서."""
    lean = P.get('lean', 0.0)
    up = (math.sin(lean), math.cos(lean))
    fwd = (math.cos(lean), -math.sin(lean))
    hip = P.get('hip', (0.0, 0.0))

    sh = add(hip, mul(up, TORSO))
    head = add(add(sh, mul(up, NECK + HEAD_R)), (P.get('head_dx', 0.0), 0))
    legs = []
    for th, kn in P['legs']:
        knee = add(hip, mul(down_dir(th), THIGH))
        foot = add(knee, mul(down_dir(th - kn), SHIN))
        legs.append((knee, foot))
    arms = []
    for ua, el in P['arms']:
        elbow = add(sh, mul(down_dir(ua), UARM))
        hand = add(elbow, mul(down_dir(ua + el), FARM))
        arms.append((elbow, hand))
    swords = [add(arms[i][1], mul(down_dir(sa), SWORD)) for i, sa in enumerate(P['swords'])]

    ca = P['cape']
    anchor = add(add(sh, mul(up, -1.2)), mul(fwd, -1.6))
    cape, cape_mid = cape_shape(anchor, ca[0], ca[1], ca[2], ca[3], ca[4])
    # 목도리: 목에 감긴 띠 + 망토와 같은 방향으로 날리는 짧고 가는 꼬리
    neck_a = add(add(sh, mul(up, 0.9)), mul(fwd, -1.4))
    neck_b = add(add(sh, mul(up, 0.9)), mul(fwd, 1.5))
    scarf, scarf_mid = cape_shape(neck_a, ca[0], ca[1] * 0.55, ca[2], ca[3] * 0.8, ca[4] + 0.7, 1.8, 2.4)

    hair = []
    for k, (ang, ln) in enumerate([(2.2, 1.9), (2.65, 2.4), (3.05, 2.0), (1.8, 1.3)]):
        a = ang - lean
        base1 = add(head, mul(polar(a - 0.35), HEAD_R * 0.9))
        base2 = add(head, mul(polar(a + 0.35), HEAD_R * 0.9))
        tip = add(head, mul(polar(a + 0.25), HEAD_R + ln))
        hair.append([base1, tip, base2])
    eye = add(add(head, mul(fwd, HEAD_R * 0.48)), mul(up, 0.5))

    pts = dict(hip=hip, sh=sh, head=head, legs=legs, arms=arms, swords=swords,
               cape=cape, cape_mid=cape_mid, hair=hair, eye=eye,
               scarf=scarf, scarf_mid=scarf_mid, neck_a=neck_a, neck_b=neck_b,
               hu=add(head, up), hf=add(head, fwd))

    # 바닥 맞추기: 가장 낮은 발이 y=0 에 닿게
    if P.get('ground', True):
        low = min(f[1] for _, f in legs)
        pts = map_points(pts, lambda q: (q[0], q[1] - low))

    rot = P.get('rot', 0.0)
    if rot:
        pivot = P.get('pivot', pts['hip'])
        pts = map_points(pts, lambda q: rotate(q, pivot, rot))
    off = P.get('offset', (0.0, 0.0))
    if off != (0.0, 0.0):
        pts = map_points(pts, lambda q: add(q, off))
    return pts


def map_points(obj, f):
    if isinstance(obj, dict):
        return {k: map_points(v, f) for k, v in obj.items()}
    if isinstance(obj, tuple) and len(obj) == 2 and all(isinstance(v, (int, float)) for v in obj):
        return f(obj)
    if isinstance(obj, (list, tuple)):
        return type(obj)(map_points(v, f) for v in obj)
    return obj


def bob_shape(pts):
    """단발머리: 정수리·뒤통수를 덮고 턱선까지 내려오며, 이마 위로 앞머리가 일자로 떨어진다"""
    H = pts['head']
    up = add(pts['hu'], mul(H, -1))
    fwd = add(pts['hf'], mul(H, -1))
    R = HEAD_R

    def hp(dx, dy):
        return add(H, add(mul(fwd, dx * R), mul(up, dy * R)))
    pts_ = [hp(0.66, 0.30)]                                  # 앞머리 끝
    for i in range(12):                                     # 정수리 → 뒤통수 (머리보다 조금 크게)
        a = math.radians(40 + 140 * i / 11)
        pts_.append(hp(-0.05 + 1.14 * math.cos(a), 0.06 + 1.14 * math.sin(a)))
    pts_ += [hp(-1.16, -0.35), hp(-1.08, -0.95), hp(-0.62, -1.02),   # 뒤로 떨어져 턱선에서 끊긴다
             hp(-0.30, -0.80), hp(-0.22, -0.05), hp(0.12, 0.30)]      # 얼굴 옆선 → 앞머리 밑단
    return pts_


def draw_hero(pen, pts, body=None, wear='cape', hair='spiky'):
    """body = (몸, 뒤쪽 팔다리, 눈) 색. 없으면 검은 실루엣 (동료).
    wear: cape(초록 망토) / scarf(빨간 목도리). hair: spiky(뾰족 머리) / bob(노란 단발)"""
    ink, ink_back, eye = body or (INK, INK_BACK, EYE)
    hip, sh = pts['hip'], pts['sh']
    # 뒤쪽 팔·칼·다리
    (be, bh), (fe, fh) = pts['arms']
    (bk, bf), (fk, ff) = pts['legs']
    pen.limb(sh, be, 2.0, ink_back)
    pen.limb(be, bh, 1.9, ink_back)
    sword(pen, bh, pts['swords'][0], ink_back)
    pen.limb(hip, bk, 2.7, ink_back)
    pen.limb(bk, bf, 2.4, ink_back)
    pen.limb(bf, add(bf, (1.6, 0)), 1.8, ink_back)
    # 망토 또는 목도리 꼬리
    if wear == 'scarf':
        pen.poly(pts['scarf'], SCARF)
        pen.line(pts['scarf'] + [pts['scarf'][0]], SCARF_EDGE, 0.45)
    else:
        pen.poly(pts['cape'], CAPE)
        pen.line(pts['cape'] + [pts['cape'][0]], CAPE_EDGE, 0.55)
        mid = pts['cape_mid']
        pen.line(mid[2:-1], CAPE_DARK, 0.7)
    # 몸통
    pen.limb(hip, sh, 4.8, ink)
    pen.limb(hip, fk, 2.9, ink)
    pen.limb(fk, ff, 2.6, ink)
    pen.limb(ff, add(ff, (1.8, -0.1)), 2.0, ink)
    pen.limb(sh, pts['head'], 1.8, ink)
    if hair == 'spiky':
        for tri in pts['hair']:
            pen.poly(tri, ink)
    pen.circle(pts['head'], HEAD_R, ink)
    pen.circle(pts['eye'], 0.62, eye)
    if hair == 'bob':
        bob = bob_shape(pts)
        pen.poly(bob, BOB)
        pen.line(bob + [bob[0]], BOB_EDGE, 0.4)
    if wear == 'scarf':
        pen.limb(pts['neck_a'], pts['neck_b'], 2.3, SCARF)
        pen.line([pts['neck_a'], pts['neck_b']], SCARF_DARK, 0.5)
    # 앞쪽 팔·칼
    pen.limb(sh, fe, 2.1, ink)
    pen.limb(fe, fh, 2.0, ink)
    sword(pen, fh, pts['swords'][1], ink)


def sword(pen, hand, tip, ink=INK):
    pen.line([hand, tip], BLADE_GLOW, 2.6)
    pen.line([hand, tip], BLADE, 0.9)
    pen.circle(hand, 1.1, ink)


def hero_poses():
    rows = {}
    rows['idle'] = []
    for i in range(4):
        b = math.sin(i / 4 * 2 * math.pi)
        rows['idle'].append(dict(
            lean=0.03, legs=[(-0.07, 0.04), (0.09, 0.08)],
            arms=[(0.22, 0.45), (0.12 + 0.03 * b, 0.55)], swords=[-0.75, -0.55],
            cape=(-math.pi / 2 - 0.16 - 0.03 * b, 19.5, 0.12, 0.7, i * math.pi / 2), head_dx=0.0))
    rows['run'] = []
    for i in range(6):
        ph = i / 6 * 2 * math.pi
        legs = []
        for j in range(2):
            pj = ph + j * math.pi
            legs.append((0.78 * math.sin(pj), 0.2 + 1.25 * (0.5 + 0.5 * math.sin(pj - 1.3))))
        rows['run'].append(dict(
            lean=0.36 + 0.03 * math.sin(ph * 2), legs=legs,
            arms=[(-1.05 + 0.15 * math.sin(ph), 0.7), (-0.9 - 0.15 * math.sin(ph), 0.65)],
            swords=[-1.62, -1.5],
            cape=(math.pi - 0.02, 21.0, 0.32, 2.0, ph * 2)))
    rows['wire'] = []
    for i in range(4):
        ph = i / 4 * 2 * math.pi
        rows['wire'].append(dict(
            ground=False, hip=(0.0, 0.0), rot=-1.28, offset=(-2.0, 21.0),
            lean=0.0, legs=[(-0.1 + 0.04 * math.sin(ph), 0.12), (0.22, 0.95 + 0.08 * math.sin(ph))],
            arms=[(0.55, 0.5), (0.4, 0.55)], swords=[-1.75, -1.95],
            cape=(-math.pi / 2 - 0.42, 22.0, 0.18, 1.9, ph * 1.5)))
    rows['air'] = [
        dict(ground=False, hip=(0.0, 0.0), offset=(0.0, 18.0), lean=0.12,
             legs=[(0.35, 1.35), (0.85, 1.6)], arms=[(-0.9, 0.5), (1.1, 0.4)], swords=[-1.6, 1.3],
             cape=(-math.pi / 2 - 0.5, 18.0, -0.2, 1.4, 0.0)),
        dict(ground=False, hip=(0.0, 0.0), offset=(0.0, 18.0), lean=0.05,
             legs=[(-0.15, 0.4), (0.4, 0.9)], arms=[(-1.6, 0.4), (1.7, 0.3)], swords=[-2.0, 2.1],
             cape=(math.pi / 2 + 0.55, 17.0, 0.35, 1.6, 1.0)),
    ]
    rows['slashQ'] = [
        dict(lean=-0.12, legs=[(-0.35, 0.9), (0.55, 1.3)], arms=[(2.85, 0.15), (3.0, 0.1)],
             swords=[3.35, 3.2], cape=(-math.pi / 2 - 0.75, 20.0, -0.25, 1.5, 0.0)),
        dict(lean=0.25, legs=[(-0.45, 0.9), (0.6, 1.4)], arms=[(1.8, 0.2), (1.95, 0.1)],
             swords=[1.75, 1.6], cape=(math.pi - 0.45, 20.0, 0.2, 2.0, 1.2)),
        dict(lean=0.55, legs=[(-0.6, 0.9), (0.75, 1.7)], arms=[(0.75, 0.15), (0.6, 0.2)],
             swords=[0.35, 0.55], cape=(math.pi - 0.55, 21.0, 0.25, 2.2, 2.4)),
        dict(lean=0.22, legs=[(-0.3, 0.5), (0.4, 0.9)], arms=[(0.3, 0.4), (0.15, 0.5)],
             swords=[-0.6, -0.4], cape=(math.pi + 0.35, 19.0, 0.35, 1.6, 3.6)),
    ]
    rows['slashW'] = [
        dict(lean=0.62, legs=[(-1.05, 0.25), (0.85, 1.55)], arms=[(-1.1, 0.55), (-0.95, 0.5)],
             swords=[-1.62, -1.5], cape=(math.pi - 0.1, 21.0, 0.15, 1.8, 0.0)),
        dict(lean=0.66, legs=[(-1.1, 0.2), (0.9, 1.6)], arms=[(0.6, 0.2), (0.8, 0.15)],
             swords=[1.25, 1.45], cape=(math.pi - 0.05, 22.0, 0.2, 2.0, 1.5)),
        dict(lean=0.6, legs=[(-1.1, 0.2), (0.95, 1.55)], arms=[(1.45, 0.0), (1.55, 0.0)],
             swords=[1.6, 1.55], cape=(math.pi - 0.08, 22.0, 0.2, 2.2, 3.0)),
        dict(lean=0.32, legs=[(-0.6, 0.4), (0.55, 1.0)], arms=[(2.0, 0.1), (2.2, 0.05)],
             swords=[2.3, 2.45], cape=(math.pi + 0.2, 20.0, 0.3, 1.8, 4.5)),
    ]
    rows['spinE'] = []
    for i in range(6):
        a = -i / 6 * 2 * math.pi
        rows['spinE'].append(dict(
            ground=False, hip=(0.0, 0.0), rot=a, pivot=(0.0, 4.0), offset=(0.0, 18.0),
            lean=0.2, legs=[(0.95, 1.7), (0.55, 1.25)], arms=[(-1.55, 0.0), (1.6, 0.0)],
            swords=[-1.6, 1.62], cape=(-math.pi / 2 - 1.0, 21.0, -0.5, 2.5, i)))
    rows['hit'] = []
    for i in range(3):
        rows['hit'].append(dict(
            lean=-0.42 - 0.08 * i, legs=[(-0.25, 0.35), (0.35, 0.55)],
            arms=[(2.3 - 0.1 * i, -0.3), (2.5, -0.35)], swords=[2.65, 2.85],
            cape=(math.pi / 2 - 1.1 + 0.1 * i, 17.0, 0.3, 1.4, i)))
    return rows


def render_hero_cell(P, cell, k, outline=HERO_OUTLINE, wear='cape', hair='spiky'):
    img = Image.new('RGBA', (cell * S, cell * S), CLEAR)
    pen = Pen(img, cell / 2, cell - HERO_BASE * k, k)
    draw_hero(pen, hero_pose(P), wear=wear, hair=hair)
    img = shrink(img)
    return add_outline(img, outline) if outline else img


def add_outline(img, col):
    """실루엣 바깥으로 1px 테두리를 두른다"""
    a = img.getchannel('A').point(lambda v: 255 if v > 90 else 0).filter(ImageFilter.MaxFilter(3))
    out = Image.new('RGBA', img.size, col + (0,))
    out.putalpha(a.point(lambda v: v * 230 // 255))
    out.alpha_composite(img)
    return out


def make_ally(poses=None):
    """동료용 시트: 주인공과 같은 동작, 몸은 검은 실루엣.
    ally1.png(초록 망토: 리바이), ally2.png(빨간 목도리: 미카사), ally3.png(노란 단발 + 초록 망토: 아르민)"""
    poses = poses or hero_poses()
    for wear, hair, name_ in (('cape', 'spiky', 'ally1.png'), ('scarf', 'spiky', 'ally2.png'),
                              ('cape', 'bob', 'ally3.png')):
        rows = [[render_hero_cell(P, HERO_CELL, 1.0, None, wear, hair) for P in poses[name]]
                for name, n in HERO_ROWS]
        save(make_sheet(rows, HERO_CELL, HERO_CELL), name_)


def make_hero():
    poses = hero_poses()
    rows = []
    for name, n in HERO_ROWS:
        assert len(poses[name]) == n, name
        rows.append([render_hero_cell(P, HERO_CELL, 1.0) for P in poses[name]])
    save(make_sheet(rows, HERO_CELL, HERO_CELL), 'hero.png')
    make_ally(poses)

    # 설명용 큰 시트 (128px 칸)
    big = 128
    label_w = 220
    cols = max(n for _, n in HERO_ROWS)
    guide = Image.new('RGBA', (label_w + cols * big, 50 + len(HERO_ROWS) * big), (216, 220, 226, 255))
    d = ImageDraw.Draw(guide)
    f_title = ImageFont.truetype(FONT_KR, 20)
    f_lab = ImageFont.truetype(FONT_KR, 16)
    d.text((14, 12), '주인공 · 게임용 64×64 칸 (키 약 38px) · 설명용 2배 · 빨간 점선 = 발 기준선', font=f_title, fill=(20, 20, 24))
    names = {'idle': '대기', 'run': '달리기', 'wire': '와이어 비행', 'air': '공중',
             'slashQ': '목덜미 베기 Q', 'slashW': '발목 베기 W', 'spinE': '회전 베기 E', 'hit': '피격'}
    for r, (name, n) in enumerate(HERO_ROWS):
        y0 = 50 + r * big
        d.text((14, y0 + big / 2 - 20), names[name], font=f_lab, fill=(20, 20, 24))
        d.text((14, y0 + big / 2 + 2), f'{name} · {n}프레임', font=f_lab, fill=(90, 94, 100))
        for c, P in enumerate(poses[name]):
            x0 = label_w + c * big
            d.rectangle((x0, y0, x0 + big - 1, y0 + big - 1), fill=(200, 205, 212) if c % 2 else (206, 211, 218))
            fr = render_hero_cell(P, big, 2.0)
            guide.paste(fr, (x0, y0), fr)
            by = y0 + big - HERO_BASE * 2
            for xx in range(x0, x0 + big, 6):
                d.line((xx, by, xx + 3, by), fill=(200, 80, 90))
    os.makedirs(DOCS, exist_ok=True)
    save(guide, 'hero_sheet_guide.png', DOCS)


# ================================================================ 거인
GIANT_CELL = 128
GIANT_BASE = 4
GIANT_K = 2.5            # 큰 거인을 확대해도 흐리지 않게 2.5배 해상도로 그린다
GIANT_PX = int(GIANT_CELL * GIANT_K)
GIANT_ROWS = [('walk', 6), ('grab', 4), ('kneel', 3), ('death', 6), ('guard', 2), ('throw', 3), ('run', 6)]
G_THIGH, G_SHIN, G_TORSO, G_NECK, G_HEAD = 25.0, 25.0, 38.0, 4.0, 15.0
G_UARM, G_FARM = 24.0, 22.0
G_HEIGHT = G_THIGH + G_SHIN + G_TORSO + G_NECK + G_HEAD * 2   # 117
G_HEAD_UP, G_HEAD_FWD = G_HEAD * 0.85, 3.0      # 목 위에서 머리 중심까지 (위, 앞)
G_NAPE_UP, G_NAPE_FWD = G_NECK + 3.0, -9.0      # 어깨선에서 목덜미까지 (위, 앞)

SKIN = (240, 236, 228, 255)
SKIN_BACK = (206, 202, 196, 255)
SKIN_SHADE = (178, 174, 170, 255)
SKIN_LINE = (126, 120, 118, 255)
HOLE = (14, 12, 14, 255)
PLATE = (150, 112, 82, 255)


def giant_pose(P):
    lean = P.get('lean', 0.0)
    up = (math.sin(lean), math.cos(lean))
    fwd = (math.cos(lean), -math.sin(lean))
    hip = (0.0, 0.0)
    sh = add(hip, mul(up, G_TORSO))
    neck_top = add(sh, mul(up, G_NECK))
    head = add(add(neck_top, mul(up, G_HEAD_UP)), mul(fwd, G_HEAD_FWD + P.get('head_fwd', 0.0)))
    legs = []
    for th, kn in P['legs']:
        knee = add(hip, mul(down_dir(th), G_THIGH))
        foot = add(knee, mul(down_dir(th - kn), G_SHIN))
        legs.append((knee, foot))
    arms = []
    for i, arm in enumerate(P['arms']):
        if arm[0] == 'ik':
            target = arm[1](sh, up, fwd)
            elbow = ik(sh, target, G_UARM, G_FARM, arm[2])
            arms.append((elbow, target))
        else:
            ua, el = arm
            elbow = add(sh, mul(down_dir(ua), G_UARM))
            hand = add(elbow, mul(down_dir(ua + el), G_FARM))
            arms.append((elbow, hand))
    nape = add(add(sh, mul(up, G_NAPE_UP)), mul(fwd, G_NAPE_FWD))
    pts = dict(hip=hip, sh=sh, head=head, legs=legs, arms=arms, nape=nape, up=up, fwd=fwd)
    if P.get('ground', True):
        low = min(f[1] for _, f in legs)
        pts = map_points({k: v for k, v in pts.items() if k not in ('up', 'fwd')}, lambda q: (q[0], q[1] - low))
        pts['up'], pts['fwd'] = up, fwd
    rot = P.get('rot', 0.0)
    if rot:
        pivot = P.get('pivot', (0.0, 0.0))
        vecs = (pts.pop('up'), pts.pop('fwd'))
        pts = map_points(pts, lambda q: rotate(q, pivot, rot))
        pts['up'] = rotate(vecs[0], (0, 0), rot)
        pts['fwd'] = rotate(vecs[1], (0, 0), rot)
    off = P.get('offset', (0.0, 0.0))
    vecs = (pts.pop('up'), pts.pop('fwd'))
    pts = map_points(pts, lambda q: add(q, off))
    pts['up'], pts['fwd'] = vecs
    return pts


def draw_giant(pen, pts, armored=False, rock=False, head=True):
    """head=False 면 기본 머리(동그란 머리·그늘·텅 빈 눈·꿰맨 웃음)를 그리지 않는다 (종류별 머리를 따로 그릴 때)"""
    hip, sh, up, fwd = pts['hip'], pts['sh'], pts['up'], pts['fwd']
    (be, bh), (fe, fh) = pts['arms']
    (bk, bf), (fk, ff) = pts['legs']
    # 뒤쪽 팔·다리
    pen.limb(sh, be, 8.0, SKIN_BACK)
    pen.limb(be, bh, 7.0, SKIN_BACK)
    pen.circle(bh, 5.0, SKIN_BACK)
    pen.limb(hip, bk, 10.5, SKIN_BACK)
    pen.limb(bk, bf, 9.0, SKIN_BACK)
    pen.ellipse(add(bf, mul(fwd, 3)), 6.5, 3.2, SKIN_BACK)
    # 몸통: 엉덩이에서 어깨로 넓어지는 모양
    def tp(a, b):   # a: 앞뒤, b: 위아래
        return add(add(hip, mul(fwd, a)), mul(up, b))
    torso = [tp(-8, -3), tp(9, -3), tp(11, 14), tp(14, G_TORSO - 4), tp(9, G_TORSO + 3),
             tp(-12, G_TORSO + 3), tp(-16, G_TORSO - 6), tp(-11, 14)]
    pen.poly(torso, SKIN)
    back = [tp(-8, -3), tp(-1, -2), tp(-3, 16), tp(-5, G_TORSO - 2), tp(-12, G_TORSO + 3),
            tp(-16, G_TORSO - 6), tp(-11, 14)]
    pen.poly(back, SKIN_SHADE)
    for i in range(4):
        y = G_TORSO - 13 - i * 5.5
        pen.line([tp(-2, y + 1), tp(5, y - 0.5), tp(10, y + 0.8)], SKIN_LINE, 1.4)
    # 앞쪽 다리
    pen.limb(hip, fk, 11.0, SKIN)
    pen.limb(fk, ff, 9.5, SKIN)
    pen.ellipse(add(ff, mul(fwd, 3)), 7.0, 3.4, SKIN)
    pen.circle(fk, 5.0, SKIN)
    if armored:
        for a, b, w, h in ((-6, G_TORSO - 15, 19, 14), (-6, G_TORSO - 31, 19, 14), (-5, -2, 17, 7)):
            corners = [tp(a, b), tp(a + w, b), tp(a + w, b + h), tp(a, b + h)]
            pen.poly(corners, (205, 180, 150, 255))
            pen.line(corners + [corners[0]], PLATE, 1.6)
    # 목·머리
    pen.limb(sh, add(sh, mul(up, G_NECK + 4)), 10, SKIN)
    if head:
        head = pts['head']
        pen.circle(head, G_HEAD, SKIN)
        # 뒤통수 그늘
        shade = [add(head, mul(polar(math.atan2(up[1], up[0]) + math.pi / 2 + t * math.pi / 8), G_HEAD))
                 for t in range(9)]
        pen.poly(shade + [add(head, mul(up, -G_HEAD * 0.2))], SKIN_SHADE)
        # 텅 빈 눈과 꿰맨 웃음
        for ex in (2.5, 9.0):
            pen.ellipse(add(add(head, mul(fwd, ex)), mul(up, 3.0)), 2.6, 3.4, HOLE)
        mouth = []
        for i in range(11):
            t = i / 10
            mouth.append(add(add(head, mul(fwd, -6 + 18 * t)), mul(up, -5.5 - 3.2 * math.sin(t * math.pi) + 1.5 * t)))
        pen.line(mouth, (60, 38, 40, 255), 1.6)
        for q in mouth[1:-1]:
            pen.line([add(q, mul(up, 1.6)), add(q, mul(up, -1.8))], (60, 38, 40, 255), 0.9)
    # 앞쪽 팔
    pen.limb(sh, fe, 8.5, SKIN)
    pen.limb(fe, fh, 7.5, SKIN)
    pen.circle(fh, 5.6, SKIN)
    if rock:
        pen.circle(add(fh, mul(up, 5)), 7.0, (92, 88, 86, 255))


def giant_poses():
    rows = {}
    rows['walk'] = []
    for i in range(6):
        ph = i / 6 * 2 * math.pi
        legs, arms = [], []
        for j in range(2):
            pj = ph + j * math.pi
            legs.append((0.36 * math.sin(pj), 0.12 + 0.45 * max(0.0, math.sin(pj - 1.4))))
            arms.append((-0.32 * math.sin(pj), 0.18))
        rows['walk'].append(dict(lean=0.1, legs=legs, arms=arms))
    # 달리기: 몸을 앞으로 숙이고 보폭을 크게, 팔꿈치를 굽혀 크게 휘두른다
    rows['run'] = []
    for i in range(6):
        ph = i / 6 * 2 * math.pi
        legs, arms = [], []
        for j in range(2):
            pj = ph + j * math.pi
            legs.append((0.72 * math.sin(pj), 0.25 + 1.0 * max(0.0, math.sin(pj - 1.2))))
            arms.append((-0.75 * math.sin(pj) + 0.2, 1.0))
        rows['run'].append(dict(lean=0.38, legs=legs, arms=arms, head_fwd=1.5))
    rows['grab'] = [
        dict(lean=0.18, legs=[(-0.2, 0.15), (0.25, 0.3)], arms=[(-0.4, 0.2), (0.9, 0.35)]),
        dict(lean=0.35, legs=[(-0.3, 0.1), (0.35, 0.45)], arms=[(-0.5, 0.2), (1.45, 0.05)]),
        dict(lean=0.42, legs=[(-0.3, 0.1), (0.35, 0.5)], arms=[(-0.5, 0.2), (1.2, 0.7)]),
        dict(lean=0.2, legs=[(-0.2, 0.15), (0.25, 0.3)], arms=[(-0.3, 0.2), (0.55, 0.9)]),
    ]
    # 발목을 베이면 엉덩이를 바닥에 붙이고 주저앉는다 (목덜미가 키의 40% 높이까지 내려옴)
    rows['kneel'] = [
        dict(lean=0.25, legs=[(-0.3, 0.6), (0.5, 0.9)], arms=[(-0.2, 0.2), (0.3, 0.2)]),
        dict(lean=0.5, legs=[(0.3, 1.6), (0.9, 1.9)], arms=[(0.2, 0.2), (0.6, 0.3)]),
        dict(lean=0.8, legs=[(math.pi / 2 - 0.25, math.pi - 0.35), (math.pi / 2 - 0.05, math.pi - 0.3)],
             arms=[(0.7, 0.2), (1.0, 0.2)], head_fwd=2.0),
    ]
    rows['death'] = []
    # 무릎부터 꺾이며 앞으로 엎어져, 끝에는 바닥에 완전히 엎드려 눕는다 (주저앉기와 한눈에 구별되게)
    for legs, lean, dx in (
            ([(-0.3, 0.6), (0.5, 0.9)], 0.35, -4),
            ([(-0.2, 1.1), (0.9, 1.3)], 0.75, -14),
            ([(-0.05, math.pi / 2 + 0.05), (math.pi / 2 - 0.15, math.pi / 2 - 0.1)], 1.15, -26)):
        rows['death'].append(dict(lean=lean, legs=legs, arms=[(0.4 + lean, 0.2), (0.6 + lean, 0.1)],
                                  head_fwd=2.0, offset=(dx, 0.0)))
    # 바닥에 털썩: 다리는 뒤로 쭉 뻗고, 팔은 몸 옆에 늘어진다
    flat = math.pi / 2
    for lean, x, y, legs, arms in (
            (flat - 0.3, -6.5, 26, [(-0.8, -0.5), (-0.5, -0.6)], [(0.2, 0.3), (0.5, 0.2)]),
            (flat + 0.04, -8.5, 21, [(-1.1, 0.3), (-1.05, 0.2)], [(-1.2, 0.1), (-1.0, 0.2)]),
            (flat + 0.04, -8.5, 20, [(-1.1, 0.3), (-1.05, 0.2)], [(-1.25, 0.05), (-1.05, 0.15)])):
        rows['death'].append(dict(lean=lean, legs=legs, arms=arms, head_fwd=1.0,
                                  ground=False, offset=(x, y)))
    nape_hand = ('ik', lambda sh, up, fwd: add(add(sh, mul(up, G_NAPE_UP)), mul(fwd, G_NAPE_FWD + 1.0)), -1)
    rows['guard'] = [
        dict(lean=0.12, legs=[(-0.25, 0.2), (0.3, 0.3)], arms=[nape_hand, (0.25, 0.2)]),
        dict(lean=0.08, legs=[(0.25, 0.3), (-0.25, 0.2)], arms=[nape_hand, (-0.2, 0.2)]),
    ]
    rows['throw'] = [
        dict(lean=-0.12, legs=[(-0.3, 0.2), (0.35, 0.3)], arms=[(0.2, 0.2), (-2.4, -0.6)], rock=True),
        dict(lean=0.05, legs=[(-0.3, 0.2), (0.35, 0.3)], arms=[(-0.2, 0.2), (3.1, 0.2)], rock=True),
        dict(lean=0.3, legs=[(-0.35, 0.15), (0.4, 0.4)], arms=[(-0.4, 0.2), (1.5, 0.1)]),
    ]
    return rows


def make_giants():
    poses = giant_poses()
    meta = {'cell': GIANT_CELL, 'cell_px': GIANT_PX, 'base': GIANT_BASE, 'height': G_HEIGHT, 'rows': [], 'nape': {}}
    for armored, name in ((False, 'giant.png'), (True, 'giant_armor.png')):
        rows = []
        for row, n in GIANT_ROWS:
            frames = []
            napes = []
            for P in poses[row]:
                img = Image.new('RGBA', (GIANT_PX * S, GIANT_PX * S), CLEAR)
                pen = Pen(img, GIANT_PX / 2, GIANT_PX - GIANT_BASE * GIANT_K, GIANT_K)
                pts = giant_pose(P)
                draw_giant(pen, pts, armored, P.get('rock', False))
                # 오른쪽을 보고 그렸으므로 뒤집어서 왼쪽을 보게 한다
                frames.append(ImageOps.mirror(shrink(img)))
                napes.append((round(-pts['nape'][0], 1), round(pts['nape'][1], 1)))
            rows.append(frames)
            meta['nape'][row] = napes
        save(make_sheet(rows, GIANT_PX, GIANT_PX), name)
    meta['rows'] = [[r, n] for r, n in GIANT_ROWS]
    with open(os.path.join(OUT, 'giant_meta.json'), 'w') as f:
        json.dump(meta, f, indent=1)
    print('saved giant_meta.json')


# ---------------------------------------------------------------- 거인 종류별 생김새
HAIR_Y = (238, 200, 74, 255)        # 거인 1: 노란 가르마 단발
HAIR_Y_DARK = (176, 136, 40, 255)
FUR = (134, 108, 88, 255)           # 거인 2: 짐승 털
FUR_BACK = (108, 86, 70, 255)
FUR_DARK = (86, 66, 54, 255)


def head_axes(pts):
    return pts['head'], pts['up'], pts['fwd']


def draw_bob_hair(pen, pts):
    """노란 단발: 정수리·뒤통수를 덮고 턱선에서 끊긴다. 가르마를 타서 앞머리가 앞쪽으로 넘어간다."""
    H, up, fwd = head_axes(pts)
    R = G_HEAD

    def hp(dx, dy):
        return add(H, add(mul(fwd, dx * R), mul(up, dy * R)))
    hair = [hp(0.80, 0.42), hp(0.74, 0.70)]                    # 앞머리 끝 → 이마 위
    for i in range(14):                                       # 정수리 → 뒤통수
        a = math.radians(62 + 140 * i / 13)
        hair.append(hp(-0.04 + 1.1 * math.cos(a), 0.08 + 1.1 * math.sin(a)))
    hair += [hp(-1.12, -0.42), hp(-1.04, -0.98), hp(-0.30, -1.02),    # 뒤로 떨어져 턱선에서 일자로 끊긴다
             hp(-0.22, -0.55), hp(-0.30, 0.02), hp(0.05, 0.46)]       # 귀 앞 옆머리 → 가르마 쪽 앞머리 밑단
    pen.poly(hair, HAIR_Y)
    pen.line([hp(0.42, 1.0), hp(0.10, 1.12), hp(-0.30, 1.04)], HAIR_Y_DARK, 1.4)   # 가르마


def draw_bob_face(pen, pts):
    """기존 거인과 같은 그림체(단색 도형, 검은 눈)로 생김새만 다르게:
    위아래로 긴 달걀형 밝은 얼굴(그늘 없음: 얼굴 아래 그늘이 수염처럼 보여서), 기존보다 작은 세로 눈, 입 없음"""
    H, up, fwd = head_axes(pts)
    R = G_HEAD
    ang = math.atan2(up[1], up[0])

    def at(a, rx, ry):   # 머리 기준 각도 a (0 = 위쪽, + = 뒤쪽으로 돈다)
        return add(H, add(mul(up, ry * R * math.cos(a)), mul(fwd, -rx * R * math.sin(a))))
    # 달걀형 머리: 위는 둥글고 턱 쪽은 조금 좁다
    head = []
    for i in range(32):
        a = i / 32 * 2 * math.pi
        rx = 0.92 - 0.14 * max(0.0, -math.cos(a))
        head.append(at(a, rx, 1.08))
    pen.poly(head, SKIN)
    # 기존 거인과 같은 세로로 긴 검은 눈. 앞머리에서 떨어진 얼굴 가운데, 뒤쪽 눈은 조금 작게 (옆모습 원근)
    for ex, ey, rx, ry in ((3.2, 0.6, 1.7, 2.4), (9.2, 0.4, 2.0, 2.8)):
        pen.ellipse(add(add(H, mul(fwd, ex)), mul(up, ey)), rx, ry, HOLE)


def draw_giant_bob(pen, pts, rock=False):
    draw_giant(pen, pts, False, rock, head=False)
    draw_bob_face(pen, pts)
    draw_bob_hair(pen, pts)
    # 앞팔이 머리를 가리는 동작(막기 등)이 있어 앞팔을 다시 얹는다
    (fe, fh) = pts['arms'][1]
    pen.limb(pts['sh'], fe, 8.5, SKIN)
    pen.limb(fe, fh, 7.5, SKIN)
    pen.circle(fh, 5.6, SKIN)
    if rock:
        pen.circle(add(fh, mul(pts['up'], 5)), 7.0, (92, 88, 86, 255))


# 짐승 거인: 짧고 굵은 다리, 크고 긴 몸통, 솟은 어깨 혹, 땅에 닿을 듯한 긴 팔, 혹 앞 아래에 붙은 아주 작은 머리
BEAST = dict(G_THIGH=19.0, G_SHIN=17.0, G_TORSO=46.0, G_NECK=0.0, G_HEAD=6.5,
             G_UARM=25.0, G_FARM=23.0, G_HEAD_UP=3.0, G_HEAD_FWD=13.0, G_NAPE_UP=5.5, G_NAPE_FWD=4.0)


def furry(poly, step, length, seed):
    """다각형 가장자리를 따라 바깥으로 털 뭉치를 뾰족뾰족 낸다"""
    rnd = random.Random(seed)
    area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(poly, poly[1:] + poly[:1]))
    sign = 1 if area > 0 else -1
    out = []
    for a, b in zip(poly, poly[1:] + poly[:1]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy) or 1.0
        nrm = (dy / ln * sign, -dx / ln * sign)
        m = max(1, int(ln / step))
        for k in range(m):
            t = k / m
            out.append((a[0] + dx * t, a[1] + dy * t))
            tm = t + 0.5 / m
            tip = (a[0] + dx * tm, a[1] + dy * tm)
            out.append(add(tip, mul(nrm, length * rnd.uniform(0.55, 1.0))))
    return out


def furry_limb(pen, a, b, w, col, seed, tuft=3.0):
    """털 덮인 팔다리: 굵은 막대 + 양옆으로 삐죽 나온 털 뭉치"""
    rnd = random.Random(seed)
    pen.limb(a, b, w, col)
    dx, dy = b[0] - a[0], b[1] - a[1]
    ln = math.hypot(dx, dy) or 1.0
    d = (dx / ln, dy / ln)
    n = (-d[1], d[0])
    count = max(2, int(ln / 5))
    for i in range(count):
        t = (i + 0.5) / count
        p = add(a, mul((dx, dy), t))
        for side in (1, -1):
            edge = add(p, mul(n, side * (w / 2 - 0.6)))
            tip = add(add(edge, mul(n, side * tuft * rnd.uniform(0.6, 1.0))), mul(d, rnd.uniform(0.5, 2.5)))
            pen.poly([add(edge, mul(d, -2.0)), tip, add(edge, mul(d, 2.0))], col)


def draw_giant_beast(pen, pts, rock=False):
    hip, sh, up, fwd = pts['hip'], pts['sh'], pts['up'], pts['fwd']
    (be, bh), (fe, fh) = pts['arms']
    (bk, bf), (fk, ff) = pts['legs']
    T = G_TORSO

    def tp(a, b):
        return add(add(hip, mul(fwd, a)), mul(up, b))
    # 뒤쪽 팔·다리
    furry_limb(pen, sh, be, 13.0, FUR_BACK, 1)
    furry_limb(pen, be, bh, 11.5, FUR_BACK, 2)
    pen.circle(bh, 6.5, SKIN_BACK)
    furry_limb(pen, hip, bk, 17.0, FUR_BACK, 3)
    furry_limb(pen, bk, bf, 14.0, FUR_BACK, 4)
    pen.ellipse(add(bf, mul(fwd, 4)), 8.5, 4.0, SKIN_BACK)
    # 몸통: 엉덩이 → 불룩한 배 → 앞으로 솟은 가슴 → 등 위로 솟은 혹
    body = [tp(-15, -4), tp(14, -4), tp(21, 12), tp(24, T - 14), tp(20, T - 2), tp(8, T + 4),
            tp(-6, T + 10), tp(-20, T + 4), tp(-26, T - 10), tp(-22, 12)]
    pen.poly(furry(body, 5.5, 4.2, 5), FUR)
    pen.poly(body, FUR)
    rnd = random.Random(6)
    for i in range(26):                                       # 털결
        a, b = rnd.uniform(-20, 18), rnd.uniform(0, T + 2)
        q = tp(a, b)
        pen.line([q, add(add(q, mul(up, -4.0)), mul(fwd, -1.5))], FUR_DARK, 1.0)
    # 앞쪽 다리
    furry_limb(pen, hip, fk, 18.0, FUR, 7)
    furry_limb(pen, fk, ff, 15.0, FUR, 8)
    pen.ellipse(add(ff, mul(fwd, 4)), 9.0, 4.2, SKIN)
    # 아주 작은 머리: 혹 앞 아래, 뒤로 털 갈기
    head = pts['head']
    R = G_HEAD
    mane = [add(head, mul(polar(math.atan2(up[1], up[0]) + math.pi * (0.2 + 1.1 * t / 10)), R + 4.5)) for t in range(11)]
    pen.poly(furry([head] + mane, 2.5, 2.5, 9), FUR)
    pen.circle(head, R, SKIN)
    for ex in (2.0, 4.6):
        pen.ellipse(add(add(head, mul(fwd, ex)), mul(up, 1.4)), 0.9, 1.3, HOLE)
    pen.line([add(add(head, mul(fwd, 0.5)), mul(up, -2.6)), add(add(head, mul(fwd, 5.0)), mul(up, -2.2))],
             (60, 38, 40, 255), 0.9)
    # 앞쪽 팔
    furry_limb(pen, sh, fe, 14.0, FUR, 10)
    furry_limb(pen, fe, fh, 12.5, FUR, 11)
    pen.circle(fh, 7.0, SKIN)
    if rock:
        pen.circle(add(fh, mul(up, 6)), 8.0, (92, 88, 86, 255))


# 갑옷 거인: 근육질 체형(넓은 어깨, 굵은 팔다리·목)을 온몸 단단한 판이 감싼다. 각진 얼굴, 깊은 눈, 굳은 입
PLATED = dict(G_THIGH=25.0, G_SHIN=24.0, G_TORSO=40.0, G_NECK=5.0, G_HEAD=12.5,
              G_UARM=24.0, G_FARM=23.0, G_HEAD_UP=10.5, G_HEAD_FWD=3.0, G_NAPE_UP=8.0, G_NAPE_FWD=-9.0)
PL = (226, 218, 200, 255)           # 판
PL_HI = (248, 244, 234, 255)        # 판 윗면 빛
PL_BACK = (192, 184, 168, 255)      # 뒤쪽 팔다리의 판
PL_SEAM = (112, 96, 82, 255)        # 이음매
PL_UNDER = (128, 98, 90, 255)       # 판 사이로 보이는 속살(관절)


def plate_limb(pen, a, b, w, col, seed_hi=True):
    """관절은 속살, 마디는 판으로 덮인 팔다리 한 마디"""
    pen.limb(a, b, w * 0.8, PL_UNDER)
    dx, dy = b[0] - a[0], b[1] - a[1]
    ln = math.hypot(dx, dy) or 1.0
    d = (dx / ln, dy / ln)
    n = (-d[1], d[0])
    a2, b2 = add(a, mul(d, w * 0.25)), add(b, mul(d, -w * 0.3))
    h1, h2 = w * 0.56, w * 0.5
    quad = [add(a2, mul(n, h1)), add(b2, mul(n, h2)), add(b2, mul(n, -h2)), add(a2, mul(n, -h1))]
    pen.poly(quad, col)
    pen.circle(mul(add(quad[0], quad[3]), 0.5), h1 * 0.98, col)
    pen.line(quad + [quad[0]], PL_SEAM, 0.9)
    if seed_hi:
        pen.line([add(a2, mul(n, h1 * 0.55)), add(b2, mul(n, h2 * 0.55))], PL_HI, 1.0)
    mid = mul(add(a2, b2), 0.5)
    pen.line([add(mid, mul(n, h1)), add(mid, mul(n, -h1))], PL_SEAM, 0.7)


def draw_giant_plated(pen, pts, rock=False):
    hip, sh, up, fwd = pts['hip'], pts['sh'], pts['up'], pts['fwd']
    (be, bh), (fe, fh) = pts['arms']
    (bk, bf), (fk, ff) = pts['legs']
    T = G_TORSO

    def tp(a, b):
        return add(add(hip, mul(fwd, a)), mul(up, b))
    # 뒤쪽 팔·다리
    plate_limb(pen, sh, be, 12.5, PL_BACK, False)
    plate_limb(pen, be, bh, 11.5, PL_BACK, False)
    pen.circle(bh, 6.5, PL_BACK)
    plate_limb(pen, hip, bk, 15.0, PL_BACK, False)
    plate_limb(pen, bk, bf, 13.0, PL_BACK, False)
    pen.ellipse(add(bf, mul(fwd, 3.5)), 7.5, 3.8, PL_BACK)
    # 몸통: 넓은 어깨에서 허리로 좁아지는 역삼각형
    body = [tp(-9, -3), tp(10, -3), tp(12, 12), tp(18, T - 7), tp(13, T + 4), tp(-14, T + 4),
            tp(-20, T - 8), tp(-12, 12)]
    pen.poly(body, PL_UNDER)
    back = [tp(-8.5, -2), tp(-1, -2), tp(-3, 14), tp(-6, T - 4), tp(-13, T + 3), tp(-19, T - 8), tp(-11.5, 12)]
    pen.poly(back, PL_BACK)
    pen.line(back + [back[0]], PL_SEAM, 0.9)
    # 가슴판 2장
    for poly in ([tp(-4, T - 15), tp(7, T - 16), tp(16, T - 8), tp(12, T + 3), tp(-4, T + 3)],
                 [tp(-5, T - 14), tp(-4, T + 2), tp(-12, T + 2), tp(-11, T - 12)]):
        pen.poly(poly, PL)
        pen.line(poly + [poly[0]], PL_SEAM, 1.0)
    pen.line([tp(-1, T - 3), tp(8, T - 2), tp(13, T - 6)], PL_HI, 1.0)
    # 배를 덮는 마디판 (3줄 × 2칸)
    for i in range(3):
        y0, y1 = T - 17 - i * 8.5, T - 24.5 - i * 8.5
        for x0, x1 in ((-3.0, 4.0), (4.6, 11.0 - i * 0.8)):
            cell = [tp(x0, y0), tp(x1, y0 - 0.4), tp(x1 - 0.4, y1), tp(x0 + 0.3, y1 + 0.3)]
            pen.poly(cell, PL)
            pen.line(cell + [cell[0]], PL_SEAM, 0.8)
    # 골반 판
    hipplate = [tp(-9, -3), tp(11, -3), tp(12, 6), tp(-10, 6)]
    pen.poly(hipplate, PL)
    pen.line(hipplate + [hipplate[0]], PL_SEAM, 0.9)
    # 앞쪽 다리: 허벅지 판, 무릎 덮개, 정강이 판, 발 덮개
    plate_limb(pen, hip, fk, 16.0, PL)
    plate_limb(pen, fk, ff, 14.0, PL)
    pen.circle(fk, 6.5, PL)
    pen.line([add(fk, mul(fwd, 6.0)), add(fk, mul(up, 6.0)), add(fk, mul(fwd, -6.0))], PL_SEAM, 0.9)
    foot = add(ff, mul(fwd, 3.5))
    pen.ellipse(foot, 8.2, 4.0, PL)
    pen.line([add(foot, mul(fwd, -2)), add(add(foot, mul(fwd, 4)), mul(up, 2.5))], PL_SEAM, 0.8)
    # 굵은 목: 세로로 겹친 판
    neck_top = add(sh, mul(up, G_NECK + 5))
    pen.limb(sh, neck_top, 14, PL_UNDER)
    for k in (-4.5, 0.0, 4.5):
        a, b = add(sh, mul(fwd, k)), add(neck_top, mul(fwd, k * 0.8))
        pen.limb(a, b, 4.0, PL)
        pen.line([a, b], PL_SEAM, 0.5)
    # 각진 머리
    H, R = pts['head'], G_HEAD

    def hp(dx, dy):
        return add(H, add(mul(fwd, dx * R), mul(up, dy * R)))
    head = [hp(-0.9, 0.55), hp(-0.55, 1.0), hp(0.45, 1.02), hp(0.95, 0.6), hp(1.0, -0.2), hp(0.85, -0.85),
            hp(0.45, -1.08), hp(-0.35, -1.0), hp(-0.95, -0.4)]
    pen.poly(head, PL)
    pen.line(head + [head[0]], PL_SEAM, 1.0)
    pen.line([hp(-0.5, 0.95), hp(-0.8, 0.0), hp(-0.55, -0.85)], PL_SEAM, 0.9)        # 옆머리 판
    pen.line([hp(-0.3, 0.98), hp(0.1, 0.62), hp(0.95, 0.62)], PL_SEAM, 0.8)          # 이마 판
    pen.line([hp(0.05, 0.40), hp(0.55, 0.36), hp(0.98, 0.30)], PL_SEAM, 2.2)         # 두꺼운 눈썹뼈
    for dx in (0.22, 0.70):                                                           # 깊고 가는 눈
        c = hp(dx, 0.14)
        pen.ellipse(c, 2.4, 1.0, HOLE)
        pen.circle(add(c, mul(fwd, 0.6)), 0.45, (230, 220, 200, 255))
    pen.line([hp(0.82, 0.25), hp(1.0, -0.25), hp(0.86, -0.32)], PL_SEAM, 0.9)        # 코
    pen.line([hp(0.35, -0.55), hp(0.92, -0.52)], HOLE, 1.3)                           # 굳게 다문 입
    pen.line([hp(0.10, -0.30), hp(0.25, -0.95), hp(0.6, -1.06)], PL_SEAM, 0.9)        # 턱 판
    # 앞쪽 팔: 어깨 보호대(견갑) → 위팔 판 → 팔뚝 보호대 → 주먹
    plate_limb(pen, sh, fe, 13.5, PL)
    plate_limb(pen, fe, fh, 12.5, PL)
    pen.circle(fh, 7.0, PL)
    pen.line([add(fh, mul(fwd, -4)), add(fh, mul(fwd, 4))], PL_SEAM, 0.8)
    pad = add(add(sh, mul(fwd, 1.5)), mul(up, -1.0))
    pen.circle(pad, 10.0, PL)
    for r in (10.0, 6.5):
        arc = [add(pad, mul(polar(math.atan2(up[1], up[0]) + math.pi * (-0.55 + 1.1 * t / 8)), r)) for t in range(9)]
        pen.line(arc, PL_SEAM, 0.9)
    pen.line([add(pad, mul(up, 7.5)), add(add(pad, mul(up, 4.0)), mul(fwd, 6.0))], PL_HI, 1.0)
    if rock:
        pen.circle(add(fh, mul(up, 6)), 8.0, (92, 88, 86, 255))


# 초대형 거인: 길쭉한 몸(긴 다리·몸통·목), 피부 없이 드러난 붉은 근육과 밝은 힘줄, 털 없는 해골형 머리와 드러난 이빨
COLOSSAL = dict(G_THIGH=28.0, G_SHIN=28.0, G_TORSO=38.0, G_NECK=8.0, G_HEAD=8.5,
                G_UARM=27.0, G_FARM=25.0, G_HEAD_UP=9.5, G_HEAD_FWD=2.0, G_NAPE_UP=9.0, G_NAPE_FWD=-6.0)
MU = (178, 60, 54, 255)             # 근육
MU_BACK = (140, 44, 42, 255)        # 뒤쪽 팔다리 근육
MU_DARK = (112, 30, 32, 255)        # 근육결·근육 사이
TENDON = (228, 198, 150, 255)       # 힘줄
TEETH = (238, 226, 200, 255)


def muscle_limb(pen, a, b, w, col, bands=(), fibers=True):
    """근육 한 마디: 근육결 선 + 정해진 위치(0~1)에 힘줄 띠"""
    pen.limb(a, b, w, col)
    dx, dy = b[0] - a[0], b[1] - a[1]
    ln = math.hypot(dx, dy) or 1.0
    d = (dx / ln, dy / ln)
    n = (-d[1], d[0])
    if fibers:
        for k in (-0.22, 0.12):
            pen.line([add(add(a, mul(d, w * 0.4)), mul(n, w * k)),
                      add(add(b, mul(d, -w * 0.4)), mul(n, w * (k + 0.08)))], MU_DARK, 0.7)
    for t in bands:
        c = add(a, mul((dx, dy), t))
        pen.limb(add(c, mul(n, w * 0.52)), add(c, mul(n, -w * 0.52)), 2.6, TENDON)


def draw_giant_colossal(pen, pts, rock=False):
    hip, sh, up, fwd = pts['hip'], pts['sh'], pts['up'], pts['fwd']
    (be, bh), (fe, fh) = pts['arms']
    (bk, bf), (fk, ff) = pts['legs']
    T = G_TORSO

    def tp(a, b):
        return add(add(hip, mul(fwd, a)), mul(up, b))
    # 뒤쪽 팔·다리
    muscle_limb(pen, sh, be, 8.5, MU_BACK, fibers=False)
    muscle_limb(pen, be, bh, 7.5, MU_BACK, (0.9,), fibers=False)
    pen.circle(bh, 5.0, MU_BACK)
    muscle_limb(pen, hip, bk, 11.0, MU_BACK, fibers=False)
    muscle_limb(pen, bk, bf, 9.0, MU_BACK, (0.92,), fibers=False)
    pen.ellipse(add(bf, mul(fwd, 3)), 6.5, 3.2, MU_BACK)
    # 몸통: 넓은 어깨, 가는 허리
    body = [tp(-8, -3), tp(9, -3), tp(10, 14), tp(13, T - 6), tp(9, T + 3), tp(-11, T + 3), tp(-14, T - 8), tp(-10, 14)]
    pen.poly(body, MU)
    back = [tp(-8, -2), tp(-2, -2), tp(-4, 15), tp(-6, T - 2), tp(-11, T + 3), tp(-14, T - 8), tp(-10, 14)]
    pen.poly(back, MU_BACK)
    # 가슴 근육 두 덩어리 + 근육결
    for poly in ([tp(2, T - 13), tp(10, T - 12), tp(13, T - 5), tp(9, T + 2), tp(2, T + 1)],
                 [tp(1, T - 12), tp(1, T + 1), tp(-6, T + 1), tp(-7, T - 9)]):
        pen.line(poly + [poly[0]], MU_DARK, 1.0)
    for k in range(4):
        pen.line([tp(3, T - 2 - k * 2.5), tp(10, T - 5 - k * 2.0)], MU_DARK, 0.6)
    # 가운데 흉골 힘줄 + 복근 4줄 × 2칸 (사이가 밝은 힘줄)
    pen.line([tp(1.5, T + 2), tp(1.5, T - 13), tp(2.0, 2)], TENDON, 1.6)
    for i in range(5):
        y = T - 13 - i * 6.0
        pen.line([tp(-4.5, y), tp(1.5, y + 0.3), tp(8.5 - i * 0.4, y - 0.3)], TENDON, 1.2)
    pen.line([tp(-4.5, T - 13), tp(-4.0, 2)], TENDON, 1.0)
    pen.line([tp(8.5, T - 13), tp(7.0, 4)], TENDON, 1.0)
    # 골반 쪽 V자 힘줄
    pen.line([tp(10, 10), tp(4, 0), tp(1.5, -3)], TENDON, 1.4)
    # 앞쪽 다리: 무릎 힘줄, 발목 띠
    muscle_limb(pen, hip, fk, 12.0, MU)
    muscle_limb(pen, fk, ff, 10.0, MU, (0.9,))
    knee = add(fk, mul(fwd, 3.0))
    pen.ellipse(knee, 3.2, 4.6, TENDON)
    pen.line([add(knee, mul(up, 4.0)), add(add(knee, mul(up, 12.0)), mul(fwd, -1.0))], TENDON, 1.6)
    pen.ellipse(add(ff, mul(fwd, 3)), 7.0, 3.4, MU)
    pen.line([add(add(ff, mul(fwd, 1)), mul(up, -1)), add(add(ff, mul(fwd, 8)), mul(up, -1))], MU_DARK, 0.8)
    # 긴 목: 양쪽으로 비스듬한 힘줄 두 줄
    neck_top = add(sh, mul(up, G_NECK + 4))
    pen.limb(sh, neck_top, 9.0, MU)
    pen.line([add(sh, mul(fwd, 2.5)), add(neck_top, mul(fwd, -2.5))], TENDON, 1.5)
    pen.line([add(sh, mul(fwd, -2.0)), add(neck_top, mul(fwd, 2.5))], TENDON, 1.2)
    # 해골형 머리: 길쭉한 머리통, 깊은 눈구멍, 콧구멍, 입술 없이 드러난 이빨
    H, R = pts['head'], G_HEAD

    def hp(dx, dy):
        return add(H, add(mul(fwd, dx * R), mul(up, dy * R)))
    skull = [add(H, add(mul(fwd, 0.95 * R * math.cos(t)), mul(up, 1.18 * R * math.sin(t))))
             for t in (i / 28 * 2 * math.pi for i in range(28))]
    pen.poly(skull, MU)
    pen.line([hp(-0.2, 1.1), hp(-0.85, 0.3), hp(-0.7, -0.6)], MU_DARK, 0.8)          # 옆머리 근육결
    pen.line([hp(0.1, 1.15), hp(0.55, 0.85), hp(0.9, 0.45)], TENDON, 1.0)            # 이마 힘줄
    for dx, sc in ((0.62, 1.0), (0.18, 0.8)):                                        # 깊은 눈구멍 + 작은 눈
        c = hp(dx, 0.22)
        pen.ellipse(c, 1.9 * sc, 1.5 * sc, MU_DARK)
        pen.circle(add(c, mul(fwd, 0.3)), 0.6 * sc, (240, 230, 210, 255))
    pen.line([hp(0.45, 0.42), hp(0.95, 0.40)], MU_DARK, 1.2)                          # 눈썹뼈 그늘
    pen.ellipse(hp(0.86, -0.12), 0.8, 0.9, MU_DARK)                                   # 콧구멍
    teeth = [hp(0.15, -0.42), hp(0.98, -0.40), hp(0.95, -0.80), hp(0.18, -0.84)]       # 드러난 이빨
    pen.poly(teeth, TEETH)
    pen.line([hp(0.16, -0.62), hp(0.97, -0.60)], MU_DARK, 0.6)
    for i in range(7):
        x = 0.24 + i * 0.11
        pen.line([hp(x, -0.42), hp(x, -0.82)], MU_DARK, 0.45)
    pen.line([hp(0.05, -0.30), hp(0.12, -0.95), hp(0.55, -1.12)], MU_DARK, 0.8)      # 턱 근육결
    # 앞쪽 팔: 어깨 근육, 팔꿈치·손목 힘줄
    muscle_limb(pen, sh, fe, 9.0, MU)
    muscle_limb(pen, fe, fh, 8.0, MU, (0.12, 0.88))
    pen.circle(fh, 5.6, MU)
    delt = add(sh, mul(up, -1.0))
    pen.circle(delt, 6.0, MU)
    pen.line([add(delt, mul(up, 5.0)), add(add(delt, mul(up, -5.0)), mul(fwd, 2.0))], MU_DARK, 0.8)
    if rock:
        pen.circle(add(fh, mul(up, 5)), 7.0, (92, 88, 86, 255))


# 망치 거인: 마르고 긴 잿빛 몸(돌을 깎은 듯한 선), 눈 틈 하나만 있는 매끈한 머리, 뒤쪽 손에 긴 자루 돌망치
MAUL = dict(G_THIGH=27.0, G_SHIN=27.0, G_TORSO=38.0, G_NECK=6.0, G_HEAD=10.0,
            G_UARM=26.0, G_FARM=24.0, G_HEAD_UP=9.0, G_HEAD_FWD=2.5, G_NAPE_UP=8.0, G_NAPE_FWD=-7.5)
ASH = (198, 198, 192, 255)
ASH_BACK = (160, 160, 156, 255)
ASH_LINE = (112, 112, 110, 255)
ASH_HI = (226, 226, 222, 255)
HAFT = (112, 86, 62, 255)
MAUL_HEAD = (128, 124, 118, 255)
MAUL_EDGE = (82, 80, 78, 255)


def ash_limb(pen, a, b, w, col, carve=True):
    """돌을 깎은 듯한 팔다리 한 마디: 가운데 홈 선 하나"""
    pen.limb(a, b, w, col)
    if carve:
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy) or 1.0
        d, n = (dx / ln, dy / ln), (-dy / ln, dx / ln)
        pen.line([add(add(a, mul(d, w * 0.5)), mul(n, w * 0.15)), add(add(b, mul(d, -w * 0.5)), mul(n, -w * 0.1))],
                 ASH_LINE, 0.7)


def draw_maul(pen, hand, up, fwd):
    """긴 자루 돌망치: 손에서 아래·뒤로 늘어뜨린 자루 끝에 네모난 돌덩이"""
    down = mul(up, -1)
    tip = add(add(hand, mul(down, 34.0)), mul(fwd, -6.0))
    top = add(add(hand, mul(down, -14.0)), mul(fwd, 2.4))
    pen.line([top, tip], HAFT, 2.6)
    d = add(tip, mul(top, -1))
    ln = math.hypot(*d) or 1.0
    d = mul(d, 1 / ln)
    n = (-d[1], d[0])
    c = add(tip, mul(d, 2.0))
    block = [add(add(c, mul(n, 9.0)), mul(d, -5.0)), add(add(c, mul(n, 9.0)), mul(d, 5.0)),
             add(add(c, mul(n, -9.0)), mul(d, 5.0)), add(add(c, mul(n, -9.0)), mul(d, -5.0))]
    pen.poly(block, MAUL_HEAD)
    pen.line(block + [block[0]], MAUL_EDGE, 1.0)
    for k in (-4.5, 0.0, 4.5):
        pen.line([add(add(c, mul(n, k)), mul(d, -5.0)), add(add(c, mul(n, k)), mul(d, 5.0))], MAUL_EDGE, 0.6)


def draw_giant_maul(pen, pts, rock=False):
    hip, sh, up, fwd = pts['hip'], pts['sh'], pts['up'], pts['fwd']
    (be, bh), (fe, fh) = pts['arms']
    (bk, bf), (fk, ff) = pts['legs']
    T = G_TORSO

    def tp(a, b):
        return add(add(hip, mul(fwd, a)), mul(up, b))
    # 망치는 뒤쪽 손에, 몸 뒤로
    draw_maul(pen, bh, up, fwd)
    ash_limb(pen, sh, be, 7.0, ASH_BACK, False)
    ash_limb(pen, be, bh, 6.0, ASH_BACK, False)
    pen.circle(bh, 4.6, ASH_BACK)
    ash_limb(pen, hip, bk, 9.0, ASH_BACK, False)
    ash_limb(pen, bk, bf, 7.5, ASH_BACK, False)
    pen.ellipse(add(bf, mul(fwd, 3)), 6.0, 2.8, ASH_BACK)
    # 마른 몸통: 갈비뼈 쪽이 드러나는 홈 선
    body = [tp(-7, -3), tp(8, -3), tp(8, 14), tp(11, T - 6), tp(8, T + 3), tp(-10, T + 3), tp(-12, T - 8), tp(-9, 14)]
    pen.poly(body, ASH)
    back = [tp(-7, -2), tp(-2, -2), tp(-4, 15), tp(-5, T - 2), tp(-10, T + 3), tp(-12, T - 8), tp(-9, 14)]
    pen.poly(back, ASH_BACK)
    pen.line([tp(1, T + 2), tp(2, T - 10), tp(1.5, 3)], ASH_LINE, 0.9)
    for i in range(5):
        y = T - 6 - i * 4.2
        pen.line([tp(2.5, y), tp(7.5, y - 1.6), tp(10, y - 0.6)], ASH_LINE, 0.8)
    pen.line([tp(3, T - 1), tp(9, T - 3)], ASH_HI, 1.0)
    pen.line([tp(8, 9), tp(3, 0)], ASH_LINE, 0.9)
    # 앞쪽 다리
    ash_limb(pen, hip, fk, 10.0, ASH)
    ash_limb(pen, fk, ff, 8.5, ASH)
    pen.circle(fk, 4.6, ASH)
    pen.ellipse(add(ff, mul(fwd, 3)), 6.5, 3.0, ASH)
    # 목·매끈한 머리 + 가로 눈 틈 하나
    neck_top = add(sh, mul(up, G_NECK + 4))
    pen.limb(sh, neck_top, 7.5, ASH)
    pen.line([add(sh, mul(fwd, 2)), add(neck_top, mul(fwd, -1.5))], ASH_LINE, 0.7)
    H, R = pts['head'], G_HEAD

    def hp(dx, dy):
        return add(H, add(mul(fwd, dx * R), mul(up, dy * R)))
    head = [add(H, add(mul(fwd, 0.9 * R * math.cos(t)), mul(up, 1.12 * R * math.sin(t))))
            for t in (i / 28 * 2 * math.pi for i in range(28))]
    pen.poly(head, ASH)
    pen.line([hp(-0.6, 0.8), hp(-0.85, 0.0), hp(-0.55, -0.85)], ASH_LINE, 0.8)
    pen.line([hp(0.15, 0.22), hp(0.92, 0.20)], HOLE, 1.3)
    pen.line([hp(0.0, 0.95), hp(0.55, 0.75)], ASH_HI, 1.0)
    # 앞쪽 팔
    ash_limb(pen, sh, fe, 7.5, ASH)
    ash_limb(pen, fe, fh, 6.5, ASH)
    pen.circle(fh, 5.0, ASH)
    if rock:
        pen.circle(add(fh, mul(up, 5)), 7.0, (92, 88, 86, 255))


def make_giant_kind(sheet, draw_fn, overrides=None, meta_name=None):
    """거인 한 종류의 시트를 만든다 (껍질 버전은 만들지 않는다). overrides 로 몸 비율을 바꾸고, meta_name 이 있으면 목덜미 좌표를 따로 저장"""
    g = globals()
    overrides = overrides or {}
    saved = {k: g[k] for k in overrides}
    g.update(overrides)
    try:
        poses = giant_poses()
        height = G_THIGH + G_SHIN + G_TORSO + G_NECK + G_HEAD * 2
        meta = {'cell': GIANT_CELL, 'cell_px': GIANT_PX, 'base': GIANT_BASE, 'height': height,
                'rows': [[r, n] for r, n in GIANT_ROWS], 'nape': {}}
        rows = []
        for row, n in GIANT_ROWS:
            frames, napes = [], []
            for P in poses[row]:
                img = Image.new('RGBA', (GIANT_PX * S, GIANT_PX * S), CLEAR)
                pen = Pen(img, GIANT_PX / 2, GIANT_PX - GIANT_BASE * GIANT_K, GIANT_K)
                pts = giant_pose(P)
                draw_fn(pen, pts, P.get('rock', False))
                frames.append(ImageOps.mirror(shrink(img)))
                napes.append((round(-pts['nape'][0], 1), round(pts['nape'][1], 1)))
            rows.append(frames)
            meta['nape'][row] = napes
        save(make_sheet(rows, GIANT_PX, GIANT_PX), sheet + '.png')
    finally:
        g.update(saved)
    if meta_name:
        with open(os.path.join(OUT, meta_name), 'w') as f:
            json.dump(meta, f, indent=1)
        print('saved', meta_name)


def make_giant_kinds():
    make_giant_kind('giant_bob', draw_giant_bob)                                   # 목덜미 좌표는 giant_meta.json 과 같다
    make_giant_kind('giant_beast', draw_giant_beast, BEAST, 'giant_beast_meta.json')
    make_giant_kind('giant_plated', draw_giant_plated, PLATED, 'giant_plated_meta.json')
    make_giant_kind('giant_colossal', draw_giant_colossal, COLOSSAL, 'giant_colossal_meta.json')
    make_giant_kind('giant_maul', draw_giant_maul, MAUL, 'giant_maul_meta.json')


# ================================================================ 소품 · 지형
BODY = (11, 12, 14, 255)
RIM = (255, 255, 255, 235)


def rimmed(mask_img, dx=-2, dy=2, soft=False):
    """검은 실루엣 + 오른쪽 위 가장자리 빛. mask_img: 'L' 모드(S배 크기)."""
    shifted = ImageChops.offset(mask_img, dx * S // 2, dy * S // 2)
    rim = ImageChops.subtract(mask_img, shifted)
    out = Image.new('RGBA', mask_img.size, CLEAR)
    out.paste(BODY, (0, 0), mask_img)
    out.paste(RIM, (0, 0), rim)
    return shrink(out)


def prop_canvas(w, h):
    m = Image.new('L', (w * S, h * S), 0)
    return m, ImageDraw.Draw(m)


def make_props():
    """와이어 지점. 모두 아래 가운데가 바닥, 바닥에서 100px 위가 와이어를 거는 점."""
    out = {}
    # 1. 소나무
    w, h = 72, 116
    m, d = prop_canvas(w, h)
    cx = w / 2
    d.rectangle(((cx - 2) * S, (h - 22) * S, (cx + 2) * S, h * S), fill=255)
    for i in range(5):
        top = h - 104 + i * 15
        half = 9 + i * 6
        d.polygon([(cx * S, top * S), ((cx - half) * S, (top + 22) * S), ((cx - half * 0.45) * S, (top + 19) * S),
                   ((cx + half * 0.45) * S, (top + 19) * S), ((cx + half) * S, (top + 22) * S)], fill=255)
    d.polygon([(cx * S, (h - 112) * S), ((cx - 4) * S, (h - 98) * S), ((cx + 4) * S, (h - 98) * S)], fill=255)
    out['pine'] = rimmed(m)
    # 2. 거목
    w, h = 140, 128
    m, d = prop_canvas(w, h)
    cx = w / 2
    d.polygon([((cx - 13) * S, h * S), ((cx - 7) * S, (h - 92) * S), ((cx + 7) * S, (h - 92) * S), ((cx + 14) * S, h * S)], fill=255)
    for bx, by, rx, ry in ((cx, h - 104, 46, 14), (cx - 26, h - 98, 30, 11), (cx + 30, h - 100, 32, 12),
                           (cx + 4, h - 116, 34, 12), (cx - 14, h - 110, 26, 9)):
        d.ellipse(((bx - rx) * S, (by - ry) * S, (bx + rx) * S, (by + ry) * S), fill=255)
    d.line([((cx + 4) * S, (h - 60) * S), ((cx + 30) * S, (h - 70) * S), ((cx + 46) * S, (h - 66) * S)], fill=255, width=3 * S)
    d.line([((cx - 4) * S, (h - 44) * S), ((cx - 30) * S, (h - 54) * S), ((cx - 44) * S, (h - 50) * S)], fill=255, width=3 * S)
    out['bigtree'] = rimmed(m)
    # 3. 성탑
    w, h = 48, 124
    m, d = prop_canvas(w, h)
    cx = w / 2
    d.rectangle(((cx - 9) * S, (h - 92) * S, (cx + 9) * S, h * S), fill=255)
    d.rectangle(((cx - 12) * S, (h - 98) * S, (cx + 12) * S, (h - 90) * S), fill=255)
    d.polygon([((cx - 13) * S, (h - 98) * S), (cx * S, (h - 122) * S), ((cx + 13) * S, (h - 98) * S)], fill=255)
    out['tower'] = rimmed(m)
    # 4. 굴뚝
    w, h = 30, 116
    m, d = prop_canvas(w, h)
    cx = w / 2
    d.rectangle(((cx - 6) * S, (h - 104) * S, (cx + 6) * S, h * S), fill=255)
    d.rectangle(((cx - 9) * S, (h - 110) * S, (cx + 9) * S, (h - 103) * S), fill=255)
    out['chimney'] = rimmed(m)
    # 5. 크레인
    w, h = 130, 124
    m, d = prop_canvas(w, h)
    cx = w / 2
    d.rectangle(((cx - 3) * S, (h - 104) * S, (cx + 3) * S, h * S), fill=255)
    d.polygon([((cx - 30) * S, (h - 100) * S), ((cx + 58) * S, (h - 104) * S), ((cx + 58) * S, (h - 100) * S), ((cx - 30) * S, (h - 97) * S)], fill=255)
    d.line([(cx * S, (h - 118) * S), ((cx + 56) * S, (h - 103) * S)], fill=255, width=S)
    d.line([(cx * S, (h - 118) * S), ((cx - 28) * S, (h - 99) * S)], fill=255, width=S)
    d.rectangle(((cx - 2) * S, (h - 120) * S, (cx + 2) * S, (h - 104) * S), fill=255)
    d.line([((cx + 50) * S, (h - 100) * S), ((cx + 50) * S, (h - 62) * S)], fill=255, width=S)
    d.rectangle(((cx + 46) * S, (h - 62) * S, (cx + 54) * S, (h - 54) * S), fill=255)
    for i in range(6):
        y = h - 4 - i * 16
        d.line([((cx - 3) * S, y * S), ((cx + 3) * S, (y - 8) * S)], fill=0, width=S)
    out['crane'] = rimmed(m)
    for k, img in out.items():
        save(img, f'prop_{k}.png')


def make_story_props():
    """이야기 구간의 와이어 지점: 부러진 돌기둥, 부두 말뚝"""
    # 부러진 돌기둥
    w, h = 44, 118
    m, d = prop_canvas(w, h)
    cx = w / 2
    d.rectangle(((cx - 12) * S, (h - 8) * S, (cx + 12) * S, h * S), fill=255)
    d.polygon([((cx - 9) * S, (h - 8) * S), ((cx - 9) * S, (h - 104) * S), ((cx - 3) * S, (h - 112) * S),
               ((cx + 2) * S, (h - 102) * S), ((cx + 9) * S, (h - 108) * S), ((cx + 9) * S, (h - 8) * S)], fill=255)
    for y in range(h - 92, h - 10, 20):
        d.line([((cx - 9) * S, y * S), ((cx + 9) * S, y * S)], fill=0, width=S)
    save(rimmed(m), 'prop_pillar.png')
    # 부두 말뚝: 굵은 나무 기둥 두 개와 밧줄
    w, h = 60, 114
    m, d = prop_canvas(w, h)
    for px, top in ((18, h - 108), (42, h - 92)):
        d.rectangle(((px - 5) * S, top * S, (px + 5) * S, h * S), fill=255)
        d.ellipse(((px - 6) * S, (top - 3) * S, (px + 6) * S, (top + 3) * S), fill=255)
    d.line([(18 * S, (h - 96) * S), (30 * S, (h - 84) * S), (42 * S, (h - 82) * S)], fill=255, width=2 * S)
    d.line([(18 * S, (h - 70) * S), (30 * S, (h - 60) * S), (42 * S, (h - 62) * S)], fill=255, width=2 * S)
    save(rimmed(m), 'prop_post.png')


def make_lanes():
    """길 조각: 가운데(반복) 128px, 왼쪽 끝, 오른쪽 끝. 윗면은 이미지 위에서 12px 아래."""
    rnd = random.Random(3)
    top = 12

    def slab(w, h, thick, left_cap=False, right_cap=False, ground=False):
        m, d = prop_canvas(w, h)
        x0, x1 = 0, w
        if ground:
            d.rectangle((0, top * S, w * S, h * S), fill=255)
        else:
            pts = []
            if left_cap:
                pts = [(w * S, top * S), (6 * S, top * S), (0, (top + 3) * S), (10 * S, (top + thick) * S), (w * S, (top + thick + 1) * S)]
            elif right_cap:
                pts = [(0, top * S), ((w - 6) * S, top * S), (w * S, (top + 3) * S), ((w - 10) * S, (top + thick) * S), (0, (top + thick + 1) * S)]
            else:
                pts = [(0, top * S), (w * S, top * S), (w * S, (top + thick + 1) * S), (0, (top + thick + 1) * S)]
            d.polygon(pts, fill=255)
        # 풀
        span0 = 8 if left_cap else 0
        span1 = w - 8 if right_cap else w
        x = span0 + rnd.uniform(0, 3)
        while x < span1:
            hgt = rnd.uniform(3, 9)
            lean = rnd.uniform(-3, 3)
            d.line([(x * S, (top + 1) * S), ((x + lean) * S, (top - hgt) * S)], fill=255, width=int(1.1 * S))
            x += rnd.uniform(2.5, 6)
        # 윗면 울퉁불퉁
        x = span0
        while x < span1:
            r = rnd.uniform(1.0, 2.2)
            d.ellipse(((x - r) * S, (top - r * 0.6) * S, (x + r) * S, (top + r) * S), fill=255)
            x += rnd.uniform(3, 6)
        return rimmed(m, -1, 2)

    save(slab(128, 40, 22), 'lane_mid.png')
    save(slab(24, 40, 22, left_cap=True), 'lane_left.png')
    save(slab(24, 40, 22, right_cap=True), 'lane_right.png')
    save(slab(128, 90, 0, ground=True), 'ground_mid.png')


def make_buildings():
    rnd = random.Random(5)
    # 우리 벽 (160 x 720)
    w, h = 170, 720
    img = Image.new('RGBA', (w, h), CLEAR)
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, 150, h), fill=(24, 27, 32, 255))
    for y in range(0, h, 26):
        off = 0 if (y // 26) % 2 else 22
        for x in range(-off, 150, 44):
            d.rectangle((x + 1, y + 1, x + 42, y + 24), outline=(36, 40, 46, 255))
    d.rectangle((146, 0, 150, h), fill=(150, 160, 168, 255))
    d.rectangle((150, 0, 152, h), fill=(60, 66, 72, 255))
    # 성문
    d.rectangle((60, h - 150, 150, h - 60), fill=(10, 10, 12, 255))
    d.pieslice((60, h - 196, 150, h - 106), 180, 360, fill=(10, 10, 12, 255))
    for x in range(66, 150, 12):
        d.line((x, h - 190, x, h - 62), fill=(40, 42, 46, 255), width=3)
    # 망루 장식
    for y in range(40, h - 200, 160):
        d.rectangle((120, y, 160, y + 6), fill=(30, 32, 38, 255))
    save(img, 'wall.png')

    # 금 (내구도가 떨어지면 보임)
    crack = Image.new('RGBA', (150 * S, h * S), CLEAR)
    d = ImageDraw.Draw(crack)
    for _ in range(14):
        x, y = rnd.uniform(20, 140), rnd.uniform(200, 660)
        pts = [(x * S, y * S)]
        for _ in range(6):
            x += rnd.uniform(-14, 14)
            y += rnd.uniform(-22, 10)
            pts.append((x * S, y * S))
        d.line(pts, fill=(170, 150, 130, 220), width=2 * S, joint='curve')
    save(shrink(crack), 'cracks.png')

    # 적 요새 (340 x 720)
    w = 340
    img = Image.new('RGBA', (w, h), CLEAR)
    d = ImageDraw.Draw(img)
    d.polygon([(30, h), (40, 140), (w, 140), (w, h)], fill=(18, 16, 22, 255))
    for x in range(40, w, 40):
        d.rectangle((x, 112, x + 22, 142), fill=(18, 16, 22, 255))
    d.rectangle((150, 40, 230, 140), fill=(16, 14, 20, 255))
    for x in range(150, 230, 24):
        d.rectangle((x, 20, x + 14, 42), fill=(16, 14, 20, 255))
    d.line([(40, 140), (30, h)], fill=(140, 125, 160, 255), width=3)
    d.line([(40, 141), (w, 141)], fill=(110, 100, 130, 255), width=2)
    for y in range(190, h - 140, 70):
        for x in range(80, w - 20, 64):
            if rnd.random() < 0.8:
                d.rectangle((x, y, x + 10, y + 16), fill=(255, 170, 70, 255))
    d.rectangle((44, h - 130, 130, h - 40), fill=(5, 4, 6, 255))
    d.pieslice((44, h - 172, 130, h - 88), 180, 360, fill=(5, 4, 6, 255))
    glow = Image.new('RGBA', (w, h), CLEAR)
    gd = ImageDraw.Draw(glow)
    gd.ellipse((50, h - 160, 124, h - 50), fill=(255, 120, 40, 90))
    img = Image.alpha_composite(img, glow.filter(ImageFilter.GaussianBlur(14)))
    save(img, 'fortress.png')

    # 피난민 (12 x 22, 4 프레임, 왼쪽으로 달림)
    frames = []
    for i in range(4):
        c = Image.new('RGBA', (16 * S, 24 * S), CLEAR)
        pen = Pen(c, 8, 23)
        ph = i / 4 * 2 * math.pi
        hip = (0, 9)
        pen.limb(hip, (0.6, 16), 3.2, (12, 12, 14, 255))
        pen.circle((1.2, 19), 2.6, (12, 12, 14, 255))
        for j in range(2):
            a = 0.6 * math.sin(ph + j * math.pi)
            k = add(hip, mul(down_dir(-a), 4.5))
            pen.limb(hip, k, 2.0, (12, 12, 14, 255))
            pen.limb(k, add(k, mul(down_dir(-a - 0.4), 4.5)), 1.8, (12, 12, 14, 255))
        pen.limb((0.6, 15), (-3.5, 12 + math.sin(ph) * 1.5), 1.6, (12, 12, 14, 255))
        frames.append(shrink(c))
    save(make_sheet([frames], 16, 24), 'refugee.png')

    # 대포
    c = Image.new('RGBA', (40 * S, 24 * S), CLEAR)
    pen = Pen(c, 14, 20)
    pen.limb((0, 6), (20, 6), 7, (14, 14, 16, 255))
    pen.circle((-2, 6), 5, (14, 14, 16, 255))
    pen.line([(-2, 10), (20, 9.6)], (160, 160, 170, 255), 0.9)
    pen.circle((-2, 1), 5, (40, 34, 30, 255))
    save(shrink(c), 'cannon.png')


def make_effects():
    def soft(size, col, power=1.6):
        img = Image.new('RGBA', (size, size), CLEAR)
        px = img.load()
        c = (size - 1) / 2
        for y in range(size):
            for x in range(size):
                r = math.hypot(x - c, y - c) / c
                if r < 1:
                    px[x, y] = col[:3] + (int(col[3] * (1 - r) ** power),)
        return img

    save(soft(64, (255, 255, 255, 255), 1.4), 'puff.png')
    save(soft(16, (255, 255, 255, 255), 1.2), 'dot.png')
    nape = soft(32, (255, 70, 50, 255), 0.9)
    d = ImageDraw.Draw(nape)
    d.ellipse((11, 11, 21, 21), fill=(255, 92, 70, 255))
    save(nape, 'nape.png')

    def ring(size, width, dashed):
        img = Image.new('RGBA', (size * S, size * S), CLEAR)
        d = ImageDraw.Draw(img)
        r0 = width * S
        box = (r0, r0, size * S - r0, size * S - r0)
        if dashed:
            for a in range(0, 360, 30):
                d.arc(box, a, a + 18, fill=(255, 255, 255, 255), width=width * S)
        else:
            d.ellipse(box, outline=(255, 255, 255, 255), width=width * S)
        return shrink(img)

    save(ring(48, 2, True), 'ring_dash.png')
    save(ring(48, 2, False), 'ring.png')

    # 베기 궤적 (오른쪽을 봤을 때 기준)
    def arc_img(start, end, rx, ry, width):
        size = 128
        img = Image.new('RGBA', (size * S, size * S), CLEAR)
        d = ImageDraw.Draw(img)
        c = size / 2
        steps = 40
        for i in range(steps):
            t0, t1 = i / steps, (i + 1) / steps
            a0 = math.radians(start + (end - start) * t0)
            a1 = math.radians(start + (end - start) * t1)
            alpha = int(255 * math.sin(t0 * math.pi) ** 0.7)
            ww = max(1, int(width * S * (0.3 + 0.7 * math.sin(t0 * math.pi))))
            d.line([((c + rx * math.cos(a0)) * S, (c - ry * math.sin(a0)) * S),
                    ((c + rx * math.cos(a1)) * S, (c - ry * math.sin(a1)) * S)],
                   fill=(215, 238, 255, alpha), width=ww)
        img = shrink(img)
        glow = img.filter(ImageFilter.GaussianBlur(4))
        return Image.alpha_composite(glow, img)

    # 일섬: 가운데가 가장 밝고 양 끝이 가늘어지는 긴 빛줄기
    streak = Image.new('RGBA', (256, 32), CLEAR)
    px = streak.load()
    for y in range(32):
        for x in range(256):
            t = x / 255
            half = 14 * math.sin(t * math.pi) ** 0.8 + 0.5
            d = abs(y - 15.5) / half
            if d < 1:
                px[x, y] = (255, 255, 255, int(255 * (1 - d) ** 1.5))
    save(streak, 'streak.png')

    save(arc_img(120, -60, 46, 50, 7), 'arc_q.png')
    save(arc_img(200, 340, 54, 22, 6), 'arc_w.png')
    save(arc_img(0, 350, 58, 58, 6), 'arc_e.png')


# ================================================================ 배경
SKIES = [
    [(0x6f, 0x84, 0x94), (0x9f, 0xb1, 0xbb), (0xc9, 0xd3, 0xd2)],
    [(0x0d, 0x16, 0x12), (0x1c, 0x2e, 0x25), (0x2f, 0x46, 0x39)],
    [(0x07, 0x0a, 0x14), (0x14, 0x1b, 0x30), (0x27, 0x32, 0x50)],
    [(0x0e, 0x07, 0x08), (0x3a, 0x1a, 0x14), (0xa8, 0x48, 0x2a)],
    [(0x06, 0x06, 0x0b), (0x15, 0x14, 0x1f), (0x2d, 0x27, 0x33)],
    # 이야기 구간 (6~9): 무너진 벽 아래 · 노을 평야 · 처음 본 바다 · 항구 요새
    [(0x5d, 0x8a, 0xb8), (0x9c, 0xc0, 0xd8), (0xd8, 0xe4, 0xe0)],
    [(0x24, 0x1a, 0x3a), (0x8e, 0x44, 0x52), (0xf0, 0xa0, 0x5a)],
    [(0x2e, 0x74, 0xc0), (0x78, 0xb6, 0xe2), (0xd8, 0xee, 0xf4)],
    [(0x40, 0x38, 0x34), (0x86, 0x72, 0x5e), (0xc4, 0xac, 0x8a)],
]
BG_W = 1600


def make_sky(k):
    img = Image.new('RGBA', (8, 360))
    px = img.load()
    c = SKIES[k]
    for y in range(360):
        t = y / 359
        if t < 0.55:
            a, b, u = c[0], c[1], t / 0.55
        else:
            a, b, u = c[1], c[2], (t - 0.55) / 0.45
        col = tuple(int(a[i] + (b[i] - a[i]) * u) for i in range(3)) + (255,)
        for x in range(8):
            px[x, y] = col
    save(img, f'sky_{k + 1}.png')


class Wrap:
    """가로로 이어 붙여도 이음매가 없도록 3배 폭에 그리고 가운데만 잘라 쓴다."""

    def __init__(self, h=H):
        self.img = Image.new('RGBA', (BG_W * 3, h), CLEAR)
        self.d = ImageDraw.Draw(self.img)

    def each(self, f):
        for k in (0, BG_W, BG_W * 2):
            f(k)

    def result(self, blur=0):
        img = self.img
        if blur:
            img = img.filter(ImageFilter.GaussianBlur(blur))
        return img.crop((BG_W, 0, BG_W * 2, img.height))


def hills(wrap, base_y, amp, col, seed, waves=3):
    rnd = random.Random(seed)
    ph = [rnd.uniform(0, 6.28) for _ in range(waves)]
    pts = []
    for x in range(0, BG_W * 3 + 1, 8):
        y = base_y
        for i in range(waves):
            y += amp / (i + 1) * math.sin(x / BG_W * 2 * math.pi * (i + 1) + ph[i])
        pts.append((x, y))
    pts += [(BG_W * 3, H), (0, H)]
    wrap.d.polygon(pts, fill=col)


def pine_shape(d, x, base, hgt, col):
    tiers = 5
    for i in range(tiers):
        top = base - hgt + i * hgt / (tiers + 1)
        half = hgt * (0.08 + i * 0.05)
        d.polygon([(x, top), (x - half, top + hgt * 0.22), (x + half, top + hgt * 0.22)], fill=col)
    d.rectangle((x - hgt * 0.02, base - hgt * 0.15, x + hgt * 0.02, base), fill=col)


def giant_silhouette(d, x, base, hgt, col):
    """먼 배경에 서 있는 거인 실루엣 (머리, 몸통, 팔다리)"""
    head = hgt * 0.13
    d.ellipse((x - head, base - hgt, x + head, base - hgt + head * 2), fill=col)
    d.polygon([(x - hgt * 0.1, base - hgt * 0.78), (x + hgt * 0.1, base - hgt * 0.78),
               (x + hgt * 0.07, base - hgt * 0.42), (x - hgt * 0.07, base - hgt * 0.42)], fill=col)
    for sx in (-1, 1):
        d.line([(x + sx * hgt * 0.04, base - hgt * 0.44), (x + sx * hgt * 0.09, base)], fill=col,
               width=max(2, int(hgt * 0.06)))
        d.line([(x + sx * hgt * 0.1, base - hgt * 0.76), (x + sx * hgt * 0.16, base - hgt * 0.46)], fill=col,
               width=max(2, int(hgt * 0.045)))


def make_story_backgrounds():
    """이야기 구간 배경 6~9. 구간 1~5 와 다른 시드를 써서 기존 그림은 바뀌지 않는다."""
    rnd = random.Random(29)
    # --- 6. 무너진 벽 아래 (낮): 먼 곳에 끝없이 뻗은 거대한 벽과 뚫린 틈, 가까이엔 돌무더기
    far = Wrap()
    for _ in range(8):
        x, y, rx, ry = rnd.uniform(0, BG_W), rnd.uniform(40, 240), rnd.uniform(140, 300), rnd.uniform(18, 40)
        far.each(lambda k, x=x, y=y, rx=rx, ry=ry: far.d.ellipse((x + k - rx, y - ry, x + k + rx, y + ry), fill=(240, 244, 246, 90)))
    col = (150, 160, 172, 170)
    breach = rnd.uniform(300, 1200)

    def great_wall(k):
        far.d.rectangle((k, 300, breach + k, H), fill=col)
        far.d.rectangle((breach + 170 + k, 300, BG_W + k, H), fill=col)
        far.d.polygon([(breach + k, 300), (breach + 40 + k, 380), (breach + 90 + k, 460), (breach + 130 + k, 420),
                       (breach + 170 + k, 300), (breach + 170 + k, H), (breach + k, H)], fill=col)
        for bx in range(0, BG_W, 46):
            if not breach - 10 < bx < breach + 180:
                far.d.rectangle((bx + k, 288, bx + k + 24, 300), fill=col)
    far.each(great_wall)
    hills(far, 520, 22, (170, 178, 168, 150), 31)
    save(far.result(4), 'far_6.png')
    mid = Wrap()
    hills(mid, 580, 26, (104, 110, 104, 215), 32)
    for _ in range(12):
        x, w = rnd.uniform(0, BG_W), rnd.uniform(60, 160)
        base, hgt = 600 + rnd.uniform(-10, 20), rnd.uniform(30, 90)

        def rubble(k, x=x, w=w, base=base, hgt=hgt):
            pts = [(x + k, base), (x + k + w * 0.2, base - hgt * 0.7), (x + k + w * 0.45, base - hgt),
                   (x + k + w * 0.6, base - hgt * 0.6), (x + k + w * 0.85, base - hgt * 0.8), (x + k + w, base),
                   (x + k + w, H), (x + k, H)]
            mid.d.polygon(pts, fill=(84, 88, 90, 225))
        mid.each(rubble)
    save(mid.result(3), 'mid_6.png')

    # --- 7. 노을 평야: 지는 해와 길게 뻗은 언덕, 외딴 나무
    far = Wrap()
    sun_x = rnd.uniform(400, 1200)
    for r, a in ((260, 30), (180, 50), (120, 80)):
        far.each(lambda k, r=r, a=a: far.d.ellipse((sun_x + k - r, 470 - r, sun_x + k + r, 470 + r), fill=(255, 200, 120, a)))
    far.each(lambda k: far.d.ellipse((sun_x + k - 62, 470 - 62, sun_x + k + 62, 470 + 62), fill=(255, 220, 160, 230)))
    for _ in range(6):
        x, y, rx, ry = rnd.uniform(0, BG_W), rnd.uniform(140, 330), rnd.uniform(160, 340), rnd.uniform(8, 18)
        far.each(lambda k, x=x, y=y, rx=rx, ry=ry: far.d.ellipse((x + k - rx, y - ry, x + k + rx, y + ry), fill=(120, 60, 80, 120)))
    hills(far, 500, 30, (110, 56, 66, 190), 41)
    save(far.result(5), 'far_7.png')
    mid = Wrap()
    hills(mid, 570, 22, (54, 30, 40, 225), 42)
    for _ in range(7):
        x, hgt = rnd.uniform(0, BG_W), rnd.uniform(100, 170)
        base = 575 + rnd.uniform(-6, 14)
        mid.each(lambda k, x=x, hgt=hgt, base=base: pine_shape(mid.d, x + k, base, hgt, (46, 26, 34, 230)))
    save(mid.result(3), 'mid_7.png')

    # --- 8. 처음 본 바다: 수평선, 반짝이는 물결, 모래 언덕
    far = Wrap()
    for _ in range(7):
        x, y, rx, ry = rnd.uniform(0, BG_W), rnd.uniform(60, 260), rnd.uniform(120, 260), rnd.uniform(16, 34)
        far.each(lambda k, x=x, y=y, rx=rx, ry=ry: far.d.ellipse((x + k - rx, y - ry, x + k + rx, y + ry), fill=(255, 255, 255, 120)))
    far.each(lambda k: far.d.rectangle((k, 430, BG_W + k, H), fill=(52, 116, 176, 235)))
    far.each(lambda k: far.d.rectangle((k, 430, BG_W + k, 436), fill=(150, 200, 230, 235)))
    for _ in range(90):
        x, y = rnd.uniform(0, BG_W), rnd.uniform(445, 640)
        w = rnd.uniform(10, 40) * (0.5 + (y - 440) / 200)
        far.each(lambda k, x=x, y=y, w=w: far.d.line([(x + k, y), (x + k + w, y)], fill=(200, 230, 248, 150), width=2))
    save(far.result(1), 'far_8.png')
    mid = Wrap()
    hills(mid, 610, 20, (214, 194, 150, 235), 51)
    for _ in range(14):
        x, y = rnd.uniform(0, BG_W), rnd.uniform(600, 640)
        mid.each(lambda k, x=x, y=y: mid.d.line([(x + k, y), (x + k - 6, y - 18)], fill=(150, 140, 96, 220), width=2))
    save(mid.result(2), 'mid_8.png')

    # --- 9. 항구 요새: 먼지 낀 하늘 아래 끝없이 행진하는 거인 무리, 가까이엔 항구 성벽
    far = Wrap()
    for _ in range(10):
        x, y, rx, ry = rnd.uniform(0, BG_W), rnd.uniform(200, 460), rnd.uniform(160, 320), rnd.uniform(40, 80)
        far.each(lambda k, x=x, y=y, rx=rx, ry=ry: far.d.ellipse((x + k - rx, y - ry, x + k + rx, y + ry), fill=(150, 126, 100, 60)))
    x = 0
    while x < BG_W:
        hgt = rnd.uniform(150, 230)
        far.each(lambda k, x=x, hgt=hgt: giant_silhouette(far.d, x + k, 520, hgt, (92, 78, 66, 170)))
        x += rnd.uniform(40, 90)
    hills(far, 520, 8, (92, 78, 66, 170), 61)
    save(far.result(3), 'far_9.png')
    mid = Wrap()
    x = 0
    while x < BG_W:
        w = rnd.uniform(160, 300)
        top = rnd.uniform(470, 540)

        def bastion(k, x=x, w=w, top=top):
            mid.d.rectangle((x + k, top, x + k + w, H), fill=(44, 36, 32, 230))
            for bx in range(int(x), int(x + w) - 14, 30):
                mid.d.rectangle((bx + k, top - 14, bx + k + 16, top), fill=(44, 36, 32, 230))
        mid.each(bastion)
        x += w + rnd.uniform(20, 120)
    for _ in range(3):
        x, top = rnd.uniform(0, BG_W), rnd.uniform(280, 360)

        def crane(k, x=x, top=top):
            mid.d.rectangle((x + k, top, x + k + 10, H), fill=(44, 36, 32, 230))
            mid.d.polygon([(x + k - 60, top + 8), (x + k + 180, top), (x + k + 180, top + 8), (x + k - 60, top + 16)],
                          fill=(44, 36, 32, 230))
        mid.each(crane)
    save(mid.result(2), 'mid_9.png')


def make_backgrounds():
    rnd = random.Random(11)
    # --- 1. 들판
    far = Wrap()
    for _ in range(9):
        x, y, rx, ry = rnd.uniform(0, BG_W), rnd.uniform(40, 300), rnd.uniform(140, 320), rnd.uniform(20, 46)
        far.each(lambda k: far.d.ellipse((x + k - rx, y - ry, x + k + rx, y + ry), fill=(220, 228, 228, 70)))
    hills(far, 470, 40, (150, 168, 170, 140), 1)
    save(far.result(6), 'far_1.png')
    mid = Wrap()
    hills(mid, 540, 34, (110, 130, 118, 210), 2)
    for _ in range(22):
        x, hgt = rnd.uniform(0, BG_W), rnd.uniform(90, 170)
        base = 560 + rnd.uniform(-10, 30)
        mid.each(lambda k: pine_shape(mid.d, x + k, base, hgt, (78, 100, 86, 230)))
    save(mid.result(3), 'mid_1.png')

    # --- 2. 거목의 숲
    far = Wrap()
    for _ in range(18):
        x, w = rnd.uniform(0, BG_W), rnd.uniform(18, 46)
        far.each(lambda k: far.d.rectangle((x + k - w / 2, 0, x + k + w / 2, H), fill=(40, 64, 52, 120)))
    for _ in range(14):
        x, y, rx, ry = rnd.uniform(0, BG_W), rnd.uniform(60, 220), rnd.uniform(90, 200), rnd.uniform(30, 60)
        far.each(lambda k: far.d.ellipse((x + k - rx, y - ry, x + k + rx, y + ry), fill=(36, 58, 46, 110)))
    save(far.result(8), 'far_2.png')
    mid = Wrap()
    for _ in range(9):
        x, w = rnd.uniform(0, BG_W), rnd.uniform(36, 70)
        top = rnd.uniform(60, 180)

        def trunk(k, x=x, w=w, top=top):
            mid.d.polygon([(x + k - w * 0.7, H), (x + k - w * 0.4, top), (x + k + w * 0.4, top), (x + k + w * 0.7, H)], fill=(20, 34, 28, 220))
            mid.d.ellipse((x + k - w * 2.4, top - 60, x + k + w * 2.4, top + 30), fill=(20, 34, 28, 220))
            mid.d.line([(x + k, top + 140), (x + k + w * 2, top + 110)], fill=(20, 34, 28, 220), width=8)
        mid.each(trunk)
    save(mid.result(3), 'mid_2.png')

    # --- 3. 달밤의 고성
    far = Wrap()
    for _ in range(160):
        x, y, r = rnd.uniform(0, BG_W), rnd.uniform(0, 420), rnd.choice((1, 1, 1.5, 2))
        a = rnd.randint(90, 230)
        far.each(lambda k: far.d.ellipse((x + k - r, y - r, x + k + r, y + r), fill=(220, 225, 255, a)))
    save(far.result(0), 'far_3.png')
    moon = Image.new('RGBA', (220, 220), CLEAR)
    md = ImageDraw.Draw(moon)
    md.ellipse((40, 40, 180, 180), fill=(230, 228, 200, 90))
    moon = moon.filter(ImageFilter.GaussianBlur(16))
    md = ImageDraw.Draw(moon)
    md.ellipse((60, 60, 160, 160), fill=(222, 220, 196, 255))
    md.ellipse((84, 82, 104, 98), fill=(205, 202, 180, 255))
    md.ellipse((118, 112, 132, 124), fill=(208, 205, 184, 255))
    save(moon, 'moon.png')
    mid = Wrap()
    col = (30, 38, 62, 230)
    for _ in range(5):
        x = rnd.uniform(0, BG_W)
        w, top = rnd.uniform(220, 380), rnd.uniform(330, 420)

        def castle(k, x=x, w=w, top=top):
            d = mid.d
            d.rectangle((x + k, top, x + k + w, H), fill=col)
            for cx in range(int(x), int(x + w), 28):
                d.rectangle((cx + k, top - 16, cx + k + 16, top), fill=col)
            for tx in (x - 20, x + w - 30):
                d.rectangle((tx + k, top - 150, tx + k + 50, H), fill=col)
                d.polygon([(tx + k - 8, top - 150), (tx + k + 25, top - 230), (tx + k + 58, top - 150)], fill=col)
        mid.each(castle)
    save(mid.result(4), 'mid_3.png')

    # --- 4. 불타는 마을
    far = Wrap()
    for _ in range(10):
        x = rnd.uniform(0, BG_W)
        for j in range(8):
            r = 30 + j * 12
            y = 520 - j * 55
            xx = x + j * 18
            far.each(lambda k, xx=xx, y=y, r=r: far.d.ellipse((xx + k - r, y - r, xx + k + r, y + r), fill=(40, 22, 20, 60)))
    for _ in range(8):
        x, r = rnd.uniform(0, BG_W), rnd.uniform(120, 220)
        far.each(lambda k, x=x, r=r: far.d.ellipse((x + k - r * 1.6, 560 - r * 0.6, x + k + r * 1.6, 560 + r * 0.6), fill=(255, 130, 40, 70)))
    save(far.result(14), 'far_4.png')
    mid = Wrap()
    for _ in range(9):
        x, r = rnd.uniform(0, BG_W), rnd.uniform(60, 120)
        mid.each(lambda k, x=x, r=r: mid.d.ellipse((x + k - r * 1.4, 600 - r, x + k + r * 1.4, 600 + r), fill=(230, 120, 40, 90)))
    x = 0
    while x < BG_W:
        w = rnd.uniform(70, 150)
        base = 600 + rnd.uniform(-10, 20)
        hgt = w * rnd.uniform(0.45, 0.7)

        def roof(k, x=x, w=w, base=base, hgt=hgt):
            mid.d.polygon([(x + k, base), (x + k + w / 2, base - hgt), (x + k + w, base), (x + k + w, H), (x + k, H)], fill=(26, 12, 10, 235))
            mid.d.rectangle((x + k + w * 0.7, base - hgt * 0.9, x + k + w * 0.7 + 10, base - hgt * 0.4), fill=(26, 12, 10, 235))
        mid.each(roof)
        x += w * rnd.uniform(0.7, 1.1)
    save(mid.result(3), 'mid_4.png')

    # --- 5. 적 요새
    far = Wrap()
    x = 0
    while x < BG_W:
        w = rnd.uniform(90, 200)
        top = rnd.uniform(330, 470)

        def factory(k, x=x, w=w, top=top):
            d = far.d
            d.rectangle((x + k, top, x + k + w, H), fill=(28, 26, 36, 230))
            for wy in range(int(top + 20), 640, 26):
                for wx in range(int(x + 10), int(x + w - 10), 22):
                    if (wx * 7 + wy * 3) % 5 < 2:
                        d.rectangle((wx + k, wy, wx + k + 6, wy + 9), fill=(255, 160, 70, 200))
        far.each(factory)
        if rnd.random() < 0.6:
            cx = x + w * 0.6
            ctop = top - rnd.uniform(100, 200)
            far.each(lambda k, cx=cx, ctop=ctop, top=top: far.d.rectangle((cx + k, ctop, cx + k + 14, top), fill=(28, 26, 36, 230)))
            for j in range(7):
                r = 16 + j * 9
                far.each(lambda k, cx=cx, ctop=ctop, j=j, r=r: far.d.ellipse((cx + k + 7 + j * 14 - r, ctop - 20 - j * 34 - r, cx + k + 7 + j * 14 + r, ctop - 20 - j * 34 + r), fill=(90, 86, 96, 50)))
        x += w + rnd.uniform(10, 60)
    save(far.result(4), 'far_5.png')
    mid = Wrap()
    for _ in range(6):
        x = rnd.uniform(0, BG_W)
        top = rnd.uniform(240, 330)

        def crane(k, x=x, top=top):
            d = mid.d
            d.rectangle((x + k, top, x + k + 10, H), fill=(16, 15, 22, 230))
            d.polygon([(x + k - 60, top + 8), (x + k + 180, top), (x + k + 180, top + 8), (x + k - 60, top + 16)], fill=(16, 15, 22, 230))
            d.line([(x + k + 150, top + 6), (x + k + 150, top + 140)], fill=(16, 15, 22, 230), width=3)
        mid.each(crane)
    hills(mid, 610, 14, (16, 15, 22, 230), 9)
    save(mid.result(2), 'mid_5.png')

    make_story_backgrounds()

    # --- 공통: 안개 띠, 빛줄기, 비네트
    fog = Image.new('RGBA', (512, 200), CLEAR)
    px = fog.load()
    for y in range(200):
        a = int(150 * math.sin(y / 199 * math.pi) ** 2)
        for x in range(512):
            px[x, y] = (255, 255, 255, a)
    save(fog, 'fog.png')

    shafts = Image.new('RGBA', (W, H), CLEAR)
    d = ImageDraw.Draw(shafts)
    for x0, w0, a in ((120, 70, 26), (380, 110, 20), (690, 60, 30), (900, 140, 16), (1180, 80, 22)):
        d.polygon([(x0, 0), (x0 + w0, 0), (x0 + w0 - 380, H), (x0 - 380, H)], fill=(255, 255, 255, a))
    save(shafts.filter(ImageFilter.GaussianBlur(10)), 'shafts.png')

    vig = Image.new('RGBA', (320, 180), CLEAR)
    px = vig.load()
    for y in range(180):
        for x in range(320):
            r = math.hypot((x - 159.5) / 160, (y - 89.5) / 90)
            px[x, y] = (0, 0, 0, int(200 * max(0.0, r - 0.6) ** 1.5 / 0.4 ** 1.5 * 0.6))
    save(vig, 'vignette.png')


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    make_hero()
    make_giants()
    make_giant_kinds()
    make_props()
    make_story_props()
    make_lanes()
    make_buildings()
    make_effects()
    for k in range(len(SKIES)):
        make_sky(k)
    make_backgrounds()
