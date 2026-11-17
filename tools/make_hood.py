"""두건 주인공 스프라이트 시트 생성기 (주인공 시트 형식: 64×64 칸, 줄 8개, 줄마다 8프레임).

몸·두건·망토·다리는 새로 그리지 않는다. 원본 그림(resource/hood_src.png)의 4번째 옆모습을
그대로 오려서 기울이고, 찌그러뜨리고, 망토를 구부리고, 다리 조각을 돌려 프레임을 만든다.
칼과 손, 칼 궤적만 원본 그림체(굵은 검은 선 + 흰 면)에 맞춰 코드로 그린다.

실행: python tools/make_hood.py  →  resource/hero_hood.png, resource/hero_hood_meta.json
(필요: pillow, numpy)
"""
import json
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'resource')
SRC = os.path.join(OUT, 'hood_src.png')

# 원본 그림에서 옆모습(오른쪽을 봄) 위치 (원본 픽셀 좌표)
FIG = (1165, 280, 1430, 780)     # 오려낼 범위
NECK_Y = 485                     # 두건 아래, 망토가 시작되는 높이
HEM_Y = 706                      # 망토 밑단 아래 = 다리가 시작되는 높이
FOOT_Y = 775                     # 발바닥
HIP = (1296, 706)                # 다리가 도는 축
CLOAK_X = (1180, 1410)           # 망토 뒤쪽 끝 ~ 앞쪽 끝

CELL = 64                        # 주인공 시트와 같은 칸 크기
BASE = 8                         # 발 기준선: 칸 아래에서 8px 위
CHAR_H = 38                      # 칸 안 캐릭터 키(px), 기존 주인공과 같게
SS = 8                           # 크게 변환한 뒤 줄여서 부드럽게
PAD = 320                        # 망토·칼이 뻗을 여백(원본 픽셀)
BOLD = 5                         # 줄였을 때 선이 너무 얇아지지 않게 검은 선을 굵힌다(원본 픽셀)
N = 8                            # 줄마다 프레임 수
ROWS = ['idle', 'run', 'wire', 'air', 'slashQ', 'slashW', 'spinE', 'hit']

INK = (18, 18, 18, 255)
WHITE = (255, 255, 255, 255)
BLADE_LEN = 200                  # 칼날 길이(원본 픽셀)


# ---------------------------------------------------------------- 원본 오리기
def cut_out():
    """흰 배경만 투명하게 (얼굴·다리 안쪽 흰색은 남긴다)"""
    im = Image.open(SRC).convert('RGB')
    lum = im.convert('L')
    mask = lum.point(lambda v: 255 if v > 200 else 0)
    ImageDraw.floodfill(mask, (0, 0), 128)        # 바깥과 이어진 흰색 = 배경
    outside = np.asarray(mask) == 128
    inside = ~outside
    near = np.asarray(Image.fromarray((inside * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5))) > 0
    l = np.asarray(lum).astype(float)
    alpha = np.where(inside, 255.0, 0.0)
    edge = outside & near                          # 외곽선 가장자리의 부드러운 픽셀
    alpha[edge] = np.clip((245 - l[edge]) / (245 - 40), 0, 1) * 255
    rgb = np.asarray(im).copy()
    rgb[edge] = INK[:3]
    return Image.fromarray(np.dstack([rgb, alpha.astype(np.uint8)]), 'RGBA')


def pieces(src):
    """몸(두건+망토)과 다리를 나눈다. 좌표는 PAD 를 붙인 넓은 캔버스 기준"""
    x0, y0, x1, y1 = FIG
    fig = src.crop(FIG)
    W, H = fig.width + PAD * 2, fig.height + PAD * 2
    body = Image.new('RGBA', (W, H))
    body.paste(fig.crop((0, 0, fig.width, HEM_Y - y0)), (PAD, PAD))
    # 다리: 밑단 아래를 떼어 내고, 돌려도 윗부분이 망토 밖으로 안 보이게 맨 윗줄을 위로 늘려 둔다
    leg = fig.crop((0, HEM_Y + 2 - y0, fig.width, fig.height))
    ext = 34
    leg_ext = Image.new('RGBA', (leg.width, leg.height + ext))
    leg_ext.paste(leg.crop((0, 0, leg.width, 1)).resize((leg.width, ext)), (0, 0))
    leg_ext.paste(leg, (0, ext))
    off = (x0 - PAD, y0 - PAD)                     # 캔버스 좌표 + off = 원본 좌표
    hip = (HIP[0] - off[0], HIP[1] - off[1])
    leg_top = (PAD, HEM_Y + 2 - y0 + PAD - ext)
    return body, leg_ext, leg_top, hip, off


# ---------------------------------------------------------------- 망토 휘날리기
def warp_cloak(body, off, P):
    """망토를 아래로 갈수록 바람 방향으로 밀고 물결치게 구부린다 (두건은 그대로)"""
    a = np.asarray(body).astype(float)
    a[..., :3] *= a[..., 3:] / 255                  # 알파를 곱해서 섞어야 가장자리가 안 번진다
    H, W = a.shape[:2]
    ys, xs = np.mgrid[0:H, 0:W].astype(float)
    t = np.clip((ys + off[1] - NECK_Y) / (HEM_Y - NECK_Y), 0, 1.15)
    s = np.clip((xs + off[0] - CLOAK_X[0]) / (CLOAK_X[1] - CLOAK_X[0]), 0, 1)
    back = (1 - s) ** 1.8                            # 뒤쪽일수록 더 날린다 (엉덩이·다리 쪽 앞자락은 거의 그대로)
    wave = P['amp'] * t ** 1.3 * np.sin(P['ph'] - 4.2 * t - 3.0 * s) * (0.4 + 0.6 * back)
    dx = -P['wind'] * t ** 1.6 * (0.1 + 0.9 * back) + wave
    dy = -P['rise'] * t ** 2 * back + 0.5 * wave
    sx, sy = xs - dx, ys - dy                        # 출력 픽셀이 가져올 원본 위치
    x0, y0 = np.floor(sx).astype(int), np.floor(sy).astype(int)
    fx, fy = (sx - x0)[..., None], (sy - y0)[..., None]

    def at(yy, xx):
        ok = (xx >= 0) & (xx < W) & (yy >= 0) & (yy < H)
        v = a[np.clip(yy, 0, H - 1), np.clip(xx, 0, W - 1)]
        v[~ok] = 0
        return v

    v = (at(y0, x0) * (1 - fx) * (1 - fy) + at(y0, x0 + 1) * fx * (1 - fy)
         + at(y0 + 1, x0) * (1 - fx) * fy + at(y0 + 1, x0 + 1) * fx * fy)
    al = v[..., 3:]
    v[..., :3] = np.where(al > 0, v[..., :3] * 255 / np.maximum(al, 1e-3), 0)
    return Image.fromarray(np.clip(v, 0, 255).astype(np.uint8), 'RGBA')


# ---------------------------------------------------------------- 칼 (원본 그림체에 맞춰 그림)
def draw_sword(layer, hip, hand, ang, smear, blen=1.0):
    """hand: 엉덩이 기준 손 위치(원본 픽셀, 위가 +), ang: 칼 방향(도, 앞=0, 위=90)"""
    d = ImageDraw.Draw(layer)

    def P(v):
        return hip[0] + v[0], hip[1] - v[1]

    def at(r, a):
        return hand[0] + r * math.cos(math.radians(a)), hand[1] + r * math.sin(math.radians(a))

    if smear:                                        # 칼 궤적: 반투명 흰 부채꼴 + 검은 테
        a0, a1 = smear
        steps = max(4, int(abs(a1 - a0) / 6))
        outer = [P(at(BLADE_LEN * blen + 15, a0 + (a1 - a0) * i / steps)) for i in range(steps + 1)]
        inner = [P(at(BLADE_LEN * blen * 0.45, a1 + (a0 - a1) * i / steps)) for i in range(steps + 1)]
        d.polygon(outer + inner, fill=(255, 255, 255, 170), outline=INK, width=7)

    u = (math.cos(math.radians(ang)), math.sin(math.radians(ang)))
    n = (-u[1], u[0])

    def q(r, w=0.0):
        return P((hand[0] + u[0] * r + n[0] * w, hand[1] + u[1] * r + n[1] * w))

    d.line([q(-28), q(30)], fill=INK, width=20)                       # 손잡이
    d.line([q(30, 32), q(30, -32)], fill=INK, width=17)               # 날밑
    L = BLADE_LEN * blen                                               # blen < 1: 칼이 화면 안쪽을 향해 짧아 보임
    blade = [q(40, 14), q(40 + L * 0.82, 12), q(40 + L), q(40 + L * 0.82, -12), q(40, -14)]
    d.polygon(blade, fill=WHITE, outline=INK, width=9)
    hx, hy = P(hand)
    d.ellipse((hx - 22, hy - 22, hx + 22, hy + 22), fill=WHITE, outline=INK, width=9)   # 손


def bold_lines(img):
    """검은 선을 조금 굵혀서 64px 로 줄여도 원본처럼 또렷하게"""
    a = np.asarray(img).copy()
    dark = ((a[..., :3].max(2) < 55) & (a[..., 3] > 128)).astype(np.uint8) * 255   # 초록 망토는 빼고 검은 선만
    grown = np.asarray(Image.fromarray(dark).filter(ImageFilter.MaxFilter(BOLD))) > 0
    a[grown, :3] = INK[:3]
    a[grown, 3] = 255
    return Image.fromarray(a, 'RGBA')


def draw_sword_on(canvas, hip, P):
    layer = Image.new('RGBA', canvas.size)
    draw_sword(layer, hip, P['sword'][0], P['sword'][1], P['smear'], P['blen'])
    canvas.alpha_composite(layer)


# ---------------------------------------------------------------- 한 프레임 만들기
def frame(parts, P):
    body, leg, leg_top, hip, off = parts
    canvas = Image.new('RGBA', body.size)

    # 다리 두 개 (원본 다리를 복사해서 뒷다리로 쓴다, 뒷다리는 조금 어둡게). +각도 = 발이 뒤로
    lx, ly = hip[0] - leg_top[0], hip[1] - leg_top[1]
    sh = (1 - (HIP[0] - CLOAK_X[0]) / (CLOAK_X[1] - CLOAK_X[0])) ** 1.8
    mx = round(-P['wind'] * (0.1 + 0.9 * sh) * 0.9)     # 엉덩이 쪽 밑단이 밀린 만큼만 다리도 같이 옮긴다
    my = round(-P['rise'] * sh * 0.9)
    if P['sword'] and P['sback']:                        # 칼을 등 뒤로 들 때는 몸보다 먼저 그린다
        draw_sword_on(canvas, hip, P)
    if P['steps']:
        # 무릎이 망토 속에 있다고 보고, 망토 밑으로 보이는 정강이(다리 조각)를 옮기고 살짝 기울인다.
        # (앞뒤 dx, 들어 올림 dy, 각도) — 위로 들면 다리 윗부분이 망토 속으로 들어가 짧아 보인다. 0번이 먼 다리
        items = list(P['steps'])
    else:
        items = [(0, 0, a) for a in sorted(P['legs'], reverse=True)]   # 뒤로 간 다리를 먼저 그린다
    for rank, (sdx, sdy, ang) in enumerate(items):
        lg = leg
        if rank == 0:
            arr = np.asarray(leg).copy()
            arr[..., :3] = (arr[..., :3] * 0.82).astype(np.uint8)
            lg = Image.fromarray(arr, 'RGBA')
        lg = lg.rotate(-ang, resample=Image.BICUBIC, center=(lx, ly))
        canvas.alpha_composite(lg, (leg_top[0] + mx + P['legx'] + round(sdx), leg_top[1] + my - round(sdy)))

    canvas.alpha_composite(warp_cloak(body, off, P))
    if P['sword'] and not P['sback']:
        draw_sword_on(canvas, hip, P)
    canvas = bold_lines(canvas)
    if P['flash']:                                       # 맞은 순간 하얗게 번쩍
        arr = np.asarray(canvas).astype(float)
        arr[..., :3] += (255 - arr[..., :3]) * P['flash']
        canvas = Image.fromarray(arr.astype(np.uint8), 'RGBA')

    # 몸 전체 변형: 축(pivot)을 기준으로 찌그러뜨리고(sx, sy) 기울인 뒤(tilt) 줄여서 칸에 놓는다
    k = CHAR_H / (FOOT_Y - FIG[1])
    piv = (hip[0] + P['pivot'][0], hip[1] - P['pivot'][1])
    h = (FOOT_Y - HIP[1] + P['pivot'][1]) * k            # 서 있을 때 축의 높이(px)
    A = ((CELL / 2 + P['dx']) * SS, (CELL - BASE - h * P['sy'] - P['dy']) * SS)
    th = math.radians(P['tilt'])
    c, s = math.cos(th), math.sin(th)
    kk = k * SS
    # 출력 → 입력 역변환: p = piv + S⁻¹ R⁻¹ (out - A) / kk
    m00, m01 = c / P['sx'] / kk, s / P['sx'] / kk
    m10, m11 = -s / P['sy'] / kk, c / P['sy'] / kk
    coef = (m00, m01, piv[0] - m00 * A[0] - m01 * A[1],
            m10, m11, piv[1] - m10 * A[0] - m11 * A[1])
    big = canvas.convert('RGBa').transform((CELL * SS, CELL * SS), Image.AFFINE, coef, resample=Image.BICUBIC)
    return big.resize((CELL, CELL), Image.LANCZOS).convert('RGBA')


# ---------------------------------------------------------------- 동작별 자세 (줄마다 8프레임)
def pose(**kw):
    P = dict(tilt=0, sx=1.0, sy=1.0, dx=0, dy=0, legs=(3, -3), wind=10, rise=0, amp=7, ph=0.0,
             sword=None, smear=None, pivot=(0, 0), flash=0.0, blen=1.0, sback=False, legx=0, steps=None)
    P.update(kw)
    return P


def poses():
    R = {}
    tau = 2 * math.pi

    # 대기: 숨 쉬듯 들썩, 칼은 앞으로 내려 든다
    R['idle'] = []
    for i in range(N):
        ph = tau * i / N
        b = math.sin(ph)
        R['idle'].append(pose(sy=1 + 0.05 * b, sx=1 - 0.035 * b, tilt=2 + 2 * b, legs=(5, -5),
                              wind=12 + 8 * b, amp=9, ph=ph, sword=((75, 95 + 6 * b), -70 + 4 * b)))

    # 달리기: 상체를 앞으로 숙이고, 망토 속 무릎을 높이 들며 뛴다. 걷기와 다르게
    #  · 발이 땅에 닿는 시간이 짧아서 걸음 사이에 두 발이 모두 뜨는 순간이 있다 (몸이 위로 솟음)
    #  · 디딜 때 몸이 꾹 눌리고(찌그러짐), 발을 들 때 뒤꿈치를 뒤로 차올렸다가 무릎을 들어 앞으로 뻗는다
    #  칼은 등 뒤로 수평하게 들어 몸 뒤에서 끝만 보인다
    R['run'] = []
    tilt_r = 24
    reach, lift = 50, 62                       # 발이 앞뒤로 움직이는 폭, 무릎을 들 때 발이 올라가는 높이 (원본 픽셀)
    STANCE = 0.34                              # 한 바퀴 중 발이 땅에 닿아 있는 비율 (0.5 미만이라 두 발이 다 뜨는 때가 생김)

    def step(f):
        """한 다리의 (앞뒤, 높이, 정강이 각도, 디딤 세기)"""
        f = (f % tau) / tau
        if f < STANCE:                         # 딛기: 앞 → 뒤로 밀며 땅을 찬다
            u = f / STANCE
            return reach * (1 - 2 * u), 0.0, -12 + 40 * u, math.sin(math.pi * u)
        u = (f - STANCE) / (1 - STANCE)        # 들기: 뒤꿈치를 뒤로 차올렸다가 무릎을 들어 앞으로
        e = 0.5 - 0.5 * math.cos(math.pi * u)
        return -reach + 2 * reach * e, lift * math.sin(math.pi * u) ** 0.8, 28 - 40 * u + 35 * math.sin(math.pi * u), 0.0

    for i in range(N):
        ph = tau * i / N
        legs, press = [], 0.0
        for off in (math.pi, 0.0):             # 먼 다리, 가까운 다리 (반 박자 엇갈림)
            dx, dy, ang, p = step(ph + off)
            legs.append((dx, dy, ang - tilt_r))   # 몸을 숙인 만큼 빼서 화면에서 정강이가 세워져 보이게
            press = max(press, p)
        R['run'].append(pose(tilt=tilt_r + 3 * press, steps=legs, legx=25, dx=1,
                             sy=1 - 0.1 * press, sx=1 + 0.07 * press, dy=3.5 * (1 - press),
                             wind=150 + 30 * (1 - press), rise=45, amp=24, ph=ph,
                             sword=((10, 115), 195 - 6 * press), sback=True))

    # 와이어 비행: 거의 눕고 몸이 늘어남, 망토가 길게 날림, 칼은 앞으로
    R['wire'] = []
    for i in range(N):
        ph = tau * i / N
        R['wire'].append(pose(tilt=60 + 3 * math.sin(ph), sx=1.12, sy=0.92, dy=8,
                              legs=(62 + 10 * math.sin(ph), 42 + 10 * math.sin(ph + 1.5)),
                              wind=230, rise=110, amp=32, ph=ph, sword=((100, 135), 12 + 8 * math.sin(ph))))

    # 공중: 0~3 올라갈 때(다리를 당기고 망토는 아래로 끌림), 4~7 떨어질 때(망토가 위로 부풂)
    R['air'] = []
    for i in range(N):
        q = tau * (i % 4) / 4
        if i < 4:
            R['air'].append(pose(tilt=10, sy=1.12, sx=0.92, dy=10, legs=(-35 + 6 * math.sin(q), -60 + 6 * math.sin(q)),
                                 wind=40, rise=-70, amp=16, ph=q, sword=((85, 125), 65 + 8 * math.sin(q))))
        else:
            R['air'].append(pose(tilt=-8, sy=0.95, sx=1.06, dy=10, legs=(35 + 8 * math.sin(q), -25 + 8 * math.sin(q)),
                                 wind=25, rise=170, amp=30, ph=q, sword=((95, 115), 120 + 8 * math.sin(q))))

    # 목덜미 베기 Q: 뒤로 젖히며 칼을 머리 위로 → 앞으로 뛰어들며 내려침 → 망토가 앞으로 넘어옴
    tilt = [-22, -30, 8, 42, 48, 34, 16, 6]
    sx = [1.1, 1.15, 0.9, 1.2, 1.15, 1.06, 1.0, 1.0]
    sy = [0.88, 0.84, 1.12, 0.9, 0.92, 0.97, 1.02, 1.0]
    dx = [-1, -2, -4, -10, -11, -9, -4, -1]       # 숙인 만큼 몸을 왼쪽으로 옮겨 칼끝이 칸 안에 들게
    dy = [0, 0, 4, 4, 3, 0, 0, 0]                 # 내려칠 때 살짝 떠서 칼끝이 땅을 뚫지 않게
    # 칼 각도는 몸 기준이라 숙인 만큼(tilt) 더해 둔다 → 화면에서는 머리 위 → 앞 → 앞 아래로 내려침
    ang = [118, 148, 95, 40, 30, 4, -10, -20]
    hand = [(40, 175), (25, 195), (80, 180), (110, 135), (110, 115), (100, 105), (90, 100), (80, 100)]
    wind = [20, 5, 70, 180, 190, 100, -40, -60]
    rise = [0, 0, 30, 60, 60, 20, 0, 0]
    legs = [(15, -15), (20, -20), (30, -30), (45, -45), (45, -45), (35, -35), (15, -15), (6, -6)]
    smear = [None, None, (148, 95), (95, 40), (40, 30), None, None, None]
    R['slashQ'] = [pose(tilt=tilt[i], sx=sx[i], sy=sy[i], dx=dx[i], dy=dy[i], sword=(hand[i], ang[i]),
                        smear=smear[i], wind=wind[i], rise=rise[i], amp=20, ph=tau * i / N, legs=legs[i])
                   for i in range(N)]

    # 발목 베기 W: 낮게 웅크렸다가 앞으로 미끄러지며 칼을 아래로 크게 휘두름
    tilt = [6, 10, 30, 42, 46, 40, 24, 10]
    sx = [1.1, 1.15, 1.15, 1.22, 1.18, 1.1, 1.03, 1.0]
    sy = [0.86, 0.8, 0.8, 0.78, 0.8, 0.86, 0.95, 1.0]
    dx = [-1, -2, -6, -12, -13, -11, -5, -1]
    dy = [0, 0, 2, 4, 4, 2, 0, 0]                 # 미끄러지며 살짝 떠서 칼끝이 땅을 뚫지 않게
    # 화면 기준 뒤(190°) → 아래 → 앞(-15°)으로 발목 높이를 쓸고 지나간다 (몸 기울기만큼 더해 둠)
    ang = [196, 215, 265, 317, 366, 385, 364, 335]
    hand = [(30, 100), (15, 95), (55, 120), (95, 135), (115, 135), (115, 120), (95, 105), (80, 95)]
    wind = [30, 20, 90, 200, 210, 130, -20, -50]
    rise = [0, 0, 10, 40, 40, 10, 0, 0]
    legs = [(25, -12), (30, -18), (45, -35), (58, -48), (58, -48), (45, -35), (22, -15), (6, -6)]
    smear = [None, None, (215, 265), (265, 317), (317, 366), None, None, None]
    blen = [1, 1, 0.8, 0.45, 0.6, 1, 1, 1]       # 아래를 지날 때는 칼이 화면 안쪽으로 돌아 짧아 보이게
    R['slashW'] = [pose(tilt=tilt[i], sx=sx[i], sy=sy[i], dx=dx[i], dy=dy[i], sword=(hand[i], ang[i]), smear=smear[i], blen=blen[i],
                        wind=wind[i], rise=rise[i], amp=20, ph=tau * i / N, legs=legs[i])
                   for i in range(N)]

    # 회전 베기 E: 몸통 가운데를 축으로 한 바퀴, 칼을 쭉 뻗고 궤적이 따라옴
    R['spinE'] = []
    for i in range(N):
        R['spinE'].append(pose(tilt=45 * i, pivot=(0, 150), dy=10, sx=1.06, sy=0.95, legs=(40, 22),
                               wind=170, rise=70, amp=26, ph=tau * i / N,
                               sword=((105, 150), 0), smear=(80, 0)))

    # 피격: 하얗게 번쩍이며 뒤로 크게 젖혀짐, 망토가 앞으로 휙 넘어왔다가 돌아옴
    tilt = [-34, -40, -30, -20, -12, -7, -3, -1]
    sx = [1.18, 1.12, 1.05, 0.98, 0.97, 1.0, 1.0, 1.0]
    sy = [0.82, 0.86, 0.94, 1.04, 1.04, 1.0, 1.0, 1.0]
    dx = [-4, -6, -6, -5, -3, -2, -1, 0]
    wind = [-110, -130, -95, -45, 0, 18, 12, 10]
    rise = [40, 50, 35, 10, 0, 0, 0, 0]
    legs = [(-35, -12), (-40, -18), (-28, -10), (-16, -5), (-6, 0), (0, 0), (4, -4), (5, -5)]
    hand = [(55, 150), (45, 165), (55, 145), (65, 125), (70, 110), (72, 104), (74, 98), (75, 95)]
    ang = [112, 125, 100, 60, 10, -30, -60, -70]
    flash = [0.45, 0.25, 0.08, 0, 0, 0, 0, 0]
    R['hit'] = [pose(tilt=tilt[i], sx=sx[i], sy=sy[i], dx=dx[i], wind=wind[i], rise=rise[i], amp=18,
                     ph=tau * i / N, legs=legs[i], sword=(hand[i], ang[i]), flash=flash[i])
                for i in range(N)]
    return R


def main():
    parts = pieces(cut_out())
    P = poses()
    sheet = Image.new('RGBA', (N * CELL, len(ROWS) * CELL))
    for r, name in enumerate(ROWS):
        assert len(P[name]) == N, name
        for c, p in enumerate(P[name]):
            fr = frame(parts, p)
            a = np.asarray(fr)[..., 3]
            edges = [n for n, e in (('위', a[0]), ('아래', a[-1]), ('왼', a[:, 0]), ('오른', a[:, -1])) if e.max() > 40]
            if edges:
                print(f'  칸 밖으로 잘림: {name} {c}번 ({", ".join(edges)})')
            sheet.alpha_composite(fr, (c * CELL, r * CELL))
    sheet.save(os.path.join(OUT, 'hero_hood.png'))
    meta = {'cell': [CELL, CELL], 'base': BASE, 'rows': [[name, N] for name in ROWS]}
    with open(os.path.join(OUT, 'hero_hood_meta.json'), 'w') as f:
        json.dump(meta, f, indent=1)
    print('saved hero_hood.png', sheet.size, 'hero_hood_meta.json')


if __name__ == '__main__':
    main()
