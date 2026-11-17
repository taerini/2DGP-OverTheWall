"""기본 거인 스프라이트 시트 생성기 (기존 거인 시트 형식: 128 단위 칸 = 320px, 왼쪽을 봄).

몸은 새로 그리지 않는다. 원본 그림(resource/giant_src.png)의 4번째 옆모습에 뼈대를 넣고
(어깨-팔꿈치-손, 엉덩이-무릎-발) 그림을 뼈를 따라 휘게 해서 프레임을 만든다.
관절 근처 픽셀은 두 뼈의 움직임을 섞어서 따라가므로 팔꿈치·무릎·엉덩이가 둥글게 자연스럽게 굽는다.
레이어: 먼 팔 → 먼 다리 → 몸통 → 가까운 다리(골반까지 포함해서 몸통과 이음매가 안 보임) → 가까운 팔

실행: python tools/make_giant_basic.py
  →  resource/giant_basic.png, resource/giant_basic_flash.png(맞을 때 하얀 판), resource/giant_basic_meta.json
(필요: pillow, numpy)
"""
import json
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'resource')
SRC = os.path.join(OUT, 'giant_src.png')

# 원본 그림에서 옆모습(오른쪽을 봄) 위치와 관절 (원본 픽셀 좌표)
FIG = (1150, 160, 1390, 900)
TOP_Y, FOOT_Y = 170, 892         # 머리 꼭대기, 발바닥
SHOULDER = (1232, 420)
ELBOW = (1236, 530)
HAND = (1240, 628)
HIP = (1268, 640)
KNEE = (1262, 762)
SHOULDER_CUT = 405               # 팔 조각 윗부분
ARM_SEED = (1235, 520)           # 팔 안쪽 한 점
NAPE = (1228, 336)               # 목덜미 (목 뒤쪽 오목한 곳)

# 기존 거인 시트 형식
CELL = 128                       # 칸 크기 (그림 단위)
K = 2.5                          # 그림 단위 1 = 2.5px
CELL_PX = int(CELL * K)          # 320
BASE = 4                         # 발 기준선: 칸 아래에서 4 단위 위
HEIGHT = 118.0                   # 서 있을 때 키 (그림 단위)
ROWS = [('walk', 8), ('grab', 4), ('kneel', 4), ('death', 8), ('guard', 2), ('run', 8)]

PAD = 460                        # 팔다리가 뻗을 여백 (원본 픽셀)
SS = 2                           # 크게 변환한 뒤 줄여서 부드럽게
REPAIR = 7                       # 실루엣 가장자리 테두리 보강 두께 (원본 픽셀)
INK = (16, 14, 14)


def smooth(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------- 원본 오리기와 레이어 만들기
def load():
    im = Image.open(SRC).convert('RGB')
    lum = im.convert('L')
    mask = lum.point(lambda v: 255 if v > 200 else 0)
    ImageDraw.floodfill(mask, (0, 0), 128)        # 바깥과 이어진 흰색 = 배경
    outside = np.asarray(mask) == 128
    inside = ~outside
    near = np.asarray(Image.fromarray((inside * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5))) > 0
    l = np.asarray(lum).astype(float)
    alpha = np.where(inside, 255.0, 0.0)
    edge = outside & near
    alpha[edge] = np.clip((245 - l[edge]) / (245 - 40), 0, 1) * 255
    rgb = np.asarray(im).copy()
    rgb[edge] = INK
    return rgb, alpha


def arm_mask(rgb):
    """팔 영역: 어깨·손 아래에 칸막이를 친 뒤 팔 안쪽을 채우고, 둘레의 검은 선까지 포함한다"""
    dark = rgb.astype(int).sum(2) < 200
    fill = Image.fromarray(((~dark) * 255).astype(np.uint8))
    d = ImageDraw.Draw(fill)
    d.line((1170, SHOULDER_CUT, 1268, SHOULDER_CUT), fill=0, width=3)
    d.line((1268, SHOULDER_CUT, 1268, SHOULDER_CUT + 25), fill=0, width=5)
    d.line((1170, 650, 1300, 650), fill=0, width=3)
    ImageDraw.floodfill(fill, ARM_SEED, 128)
    inner = np.asarray(fill) == 128
    near = np.asarray(Image.fromarray((inner * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(45))) > 0
    m = inner | (dark & near)
    m[:SHOULDER_CUT] = False
    return m, dark


class Layer:
    """뼈를 따라 휘는 그림 한 장. 좌표는 FIG 를 자른 원본 픽셀 좌표(+PAD)"""

    def __init__(self, rgb, alpha, weights):
        x0, y0, x1, y1 = FIG
        a = alpha[y0:y1, x0:x1] / 255.0
        self.pm = np.dstack([rgb[y0:y1, x0:x1] * a[..., None], a])      # 알파를 곱해 둔 색
        self.h, self.w = a.shape
        self.weights = weights                                            # (x, y) → [뼈마다 가중치]


def make_layers():
    rgb, alpha = load()
    arm, dark = arm_mask(rgb)
    H, W = alpha.shape
    ys, xs = np.mgrid[0:H, 0:W].astype(float)

    # 몸통용 그림: 팔 앞쪽 선과 손 아래 선을 지운다 (바로 오른쪽 피부색으로 메움)
    body_rgb = rgb.astype(float)
    line = arm & dark & (xs > 1238)
    for y, x in zip(*np.nonzero(line)):
        sx = x
        while sx < W - 1 and (line[y, sx] or dark[y, sx]):
            sx += 1
        body_rgb[y, x] = rgb[y, min(W - 1, sx + 4)]

    # 뼈 가중치 (원본 좌표 기준, 쉬는 자세에서 팔다리가 세로로 서 있으므로 높이로 나눈다)
    def leg_w(x, y):
        a = smooth((y - (HIP[1] - 50)) / 105)         # 골반 → 허벅지 (넓게 섞어 엉덩이가 둥글게 굽음)
        b = smooth((y - (KNEE[1] - 50)) / 100)        # 허벅지 → 정강이 (넓게 섞어 무릎이 둥글게 굽음)
        return [1 - a, a * (1 - b), a * b]

    def arm_w(x, y):
        a = smooth((y - (SHOULDER[1] - 8)) / 40)      # 어깨(몸통에 붙음) → 위팔
        b = smooth((y - (ELBOW[1] - 40)) / 80)        # 위팔 → 아래팔 (넓게 섞어 팔꿈치가 둥글게 굽음)
        return [1 - a, a * (1 - b), a * b]

    def body_w(x, y):
        return [np.ones_like(y)]

    # 몸통: 엉덩이 아래로 서서히 사라짐 (가까운 다리 레이어의 골반이 그 자리를 덮는다)
    body = Layer(body_rgb, alpha * (1 - smooth((ys - 600) / 50)), body_w)
    # 다리: 골반부터 발까지. 위쪽은 서서히 나타나 몸통과 겹친다
    leg_a = alpha * smooth((ys - 555) / 45)
    leg = Layer(body_rgb, leg_a, leg_w)
    shade = 1 - 0.22 * smooth((ys - 620) / 70)        # 먼 다리: 골반은 몸통과 같은 색, 아래로 갈수록 어둡게
    far_leg = Layer(body_rgb * shade[..., None], leg_a, leg_w)
    # 팔: 윗부분은 서서히 나타나 어깨에 붙는다
    arm_a = alpha * arm * smooth((ys - SHOULDER_CUT) / 35)
    near_arm = Layer(rgb.astype(float), arm_a, arm_w)
    far_arm = Layer(rgb.astype(float) * 0.78, arm_a, arm_w)
    return dict(body=body, leg=leg, far_leg=far_leg, arm=near_arm, far_arm=far_arm)


# ---------------------------------------------------------------- 뼈 변환
def rot(c, deg):
    """화면에서 반시계로 deg 만큼 c 를 축으로 돌리는 3×3 행렬 (+각도: 아래로 늘어진 팔다리가 앞(오른쪽)으로)"""
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)
    m = np.array([[ca, sa, 0.0], [-sa, ca, 0.0], [0, 0, 1]])
    t = np.array([[1, 0, c[0]], [0, 1, c[1]], [0, 0, 1.0]])
    ti = np.array([[1, 0, -c[0]], [0, 1, -c[1]], [0, 0, 1.0]])
    return t @ m @ ti


def chain(j0, a0, j1, a1):
    """[몸에 붙은 뼈, 첫 마디, 둘째 마디] 행렬. a1 은 첫 마디에 대한 둘째 마디 굽힘"""
    m0 = rot(j0, a0)
    return [np.eye(3), m0, m0 @ rot(j1, a1)]


def local(p):
    return p[0] - FIG[0], p[1] - FIG[1]


def warp(layer, mats):
    """뼈 행렬로 레이어를 휜다. 출력 픽셀마다 '어느 원본 픽셀이 여기로 왔나'를 거꾸로 찾는다."""
    mats = [np.array(m) for m in mats]
    # 원본 좌표(크롭) 기준 행렬로 바꾼다
    sh = np.array([[1, 0, FIG[0]], [0, 1, FIG[1]], [0, 0, 1.0]])
    shi = np.linalg.inv(sh)
    mats = [shi @ m @ sh for m in mats]

    def fwd(x, y, jac=False):
        w = layer.weights(x + FIG[0], y + FIG[1])
        fx = sum(wi * (m[0, 0] * x + m[0, 1] * y + m[0, 2]) for wi, m in zip(w, mats))
        fy = sum(wi * (m[1, 0] * x + m[1, 1] * y + m[1, 2]) for wi, m in zip(w, mats))
        if not jac:
            return fx, fy
        # 섞인 회전(가중 평균)으로 기울기를 어림한다 → 거꾸로 찾을 때 크게 꺾인 관절에서도 빨리 맞아떨어짐
        j = [sum(wi * m[r, c] for wi, m in zip(w, mats)) for r, c in ((0, 0), (0, 1), (1, 0), (1, 1))]
        return fx, fy, j

    # 출력 범위: 불투명한 원본 점들을 앞으로 보내 본 범위
    sy, sx = np.nonzero(layer.pm[::6, ::6, 3] > 0.05)
    fx, fy = fwd(sx * 6.0, sy * 6.0)
    bx0, bx1 = int(fx.min()) - 12, int(fx.max()) + 12
    by0, by1 = int(fy.min()) - 12, int(fy.max()) + 12
    qy, qx = np.mgrid[by0:by1, bx0:bx1].astype(float)

    best = None
    for i in range(len(mats) - 1, -1, -1):                   # 끝 마디부터: 겹치면 끝 마디가 앞
        inv = np.linalg.inv(mats[i])
        px = inv[0, 0] * qx + inv[0, 1] * qy + inv[0, 2]
        py = inv[1, 0] * qx + inv[1, 1] * qy + inv[1, 2]
        for _ in range(12):
            fx, fy, (a, b, c, d) = fwd(px, py, jac=True)
            ex, ey = qx - fx, qy - fy
            det = a * d - b * c
            det = np.where(np.abs(det) < 0.05, 0.05, det)
            dx, dy = (d * ex - b * ey) / det, (-c * ex + a * ey) / det
            n = np.hypot(dx, dy)
            lim = np.minimum(1.0, 40.0 / np.maximum(n, 1e-6))           # 한 번에 너무 멀리 튀지 않게
            px, py = px + dx * lim, py + dy * lim
        fx, fy = fwd(px, py)
        res = np.hypot(qx - fx, qy - fy)
        col = sample(layer, px, py)
        ok = (res < 1.5)[..., None]
        col = np.where(ok, col, 0)
        best = col if best is None else np.where(best[..., 3:] > 0.02, best, col)
    return best, (bx0, by0)


def sample(layer, px, py):
    x0 = np.floor(px).astype(int)
    y0 = np.floor(py).astype(int)
    fx, fy = (px - x0)[..., None], (py - y0)[..., None]
    out = np.zeros(px.shape + (4,))
    for dx, dy, wt in ((0, 0, (1 - fx) * (1 - fy)), (1, 0, fx * (1 - fy)), (0, 1, (1 - fx) * fy), (1, 1, fx * fy)):
        xx, yy = x0 + dx, y0 + dy
        ok = (xx >= 0) & (xx < layer.w) & (yy >= 0) & (yy < layer.h)
        v = layer.pm[np.clip(yy, 0, layer.h - 1), np.clip(xx, 0, layer.w - 1)]
        out += np.where(ok[..., None], v, 0) * wt
    return out


# ---------------------------------------------------------------- 한 프레임
def ik_arm(target, bend=1):
    """손이 target(원본 좌표)에 오도록 어깨·팔꿈치 각도를 찾는다 (격자 탐색). bend: 팔꿈치가 굽는 방향"""
    hand = np.array([HAND[0], HAND[1], 1.0])
    best = None
    for a in range(-180, 181, 3):
        for b in range(0, 165, 3):
            m = chain(SHOULDER, a, ELBOW, b * bend)[2]
            h = m @ hand
            d = math.hypot(h[0] - target[0], h[1] - target[1])
            if best is None or d < best[0]:
                best = (d, a, b * bend)
    return best[1], best[2]


def frame(L, P):
    """P: tilt(+ 앞으로 숙임), legs=[(허벅지, 무릎) 가까운, 먼], arms=[(어깨, 팔꿈치) 가까운, 먼]
    허벅지·어깨 +: 앞으로 / 무릎 -: 정강이가 뒤로 굽음 / 팔꿈치 +: 아래팔이 앞으로 굽음"""
    W, H = FIG[2] - FIG[0] + 2 * PAD, FIG[3] - FIG[1] + 2 * PAD
    canvas = np.zeros((H, W, 4))
    (nt, nk), (ft, fk) = P['legs']
    (ns, ne), (fs, fe) = P['arms']
    order = [('far_arm', chain(SHOULDER, fs, ELBOW, fe)), ('far_leg', chain(HIP, ft, KNEE, fk)),
             ('body', [np.eye(3)]),
             ('leg', chain(HIP, nt, KNEE, nk)), ('arm', chain(SHOULDER, ns, ELBOW, ne))]
    for name, mats in order:
        col, (bx, by) = warp(L[name], mats)
        x0, y0 = bx + PAD, by + PAD
        h, w = col.shape[:2]
        dst = canvas[y0:y0 + h, x0:x0 + w]
        dst[:] = col + dst * (1 - col[..., 3:])                 # 알파 합성 (알파를 곱한 색끼리)
    a = canvas[..., 3:]
    rgb = np.where(a > 1e-3, canvas[..., :3] / np.maximum(a, 1e-3), 0)
    img = Image.fromarray(np.dstack([np.clip(rgb, 0, 255), np.clip(a * 255, 0, 255)]).astype(np.uint8), 'RGBA')
    img = repair_outline(img)

    # 몸 전체를 엉덩이 축으로 기울이고 줄여서 칸에 놓는다 (넉넉한 판에 그린 뒤 땅·칸에 맞춤)
    hip = (HIP[0] - FIG[0] + PAD, HIP[1] - FIG[1] + PAD)
    k = HEIGHT * K / (FOOT_Y - TOP_Y) * SS
    th = math.radians(P['tilt'])
    c, s = math.cos(th), math.sin(th)
    big_w = big_h = CELL_PX * SS * 2
    A = (big_w / 2, big_h / 2)
    m00, m01, m10, m11 = c / k, s / k, -s / k, c / k
    coef = (m00, m01, hip[0] - m00 * A[0] - m01 * A[1], m10, m11, hip[1] - m10 * A[0] - m11 * A[1])
    big = img.convert('RGBa').transform((big_w, big_h), Image.AFFINE, coef, resample=Image.BICUBIC).convert('RGBA')

    al = np.asarray(big)[..., 3] > 60
    ys = np.nonzero(al.any(1))[0]
    xs = np.nonzero(al.any(0))[0]
    floor = (CELL_PX - BASE * K) * SS
    oy = floor - ys[-1]                               # 가장 낮은 곳이 땅에 닿게
    ox = CELL_PX * SS / 2 - A[0]
    if 'knee_x' in P:                                 # 무릎을 기준으로 놓기 (쓰러질 때 무릎이 미끄러지지 않게)
        kn = chain(HIP, P['legs'][0][0], KNEE, P['legs'][0][1])[1] @ np.array([KNEE[0], KNEE[1], 1.0])
        kx, ky = kn[0] - FIG[0] + PAD - hip[0], kn[1] - FIG[1] + PAD - hip[1]
        ox = P['knee_x'] * CELL_PX * SS - (A[0] + k * (c * kx - s * ky))
    ox = min(ox, CELL_PX * SS - 2 - xs[-1])           # 칸 밖으로 안 나가게
    ox = max(ox, 2 - xs[0])
    if ys[0] + oy < 0:
        print('  칸 위로 잘림', P)
    cell = Image.new('RGBA', (CELL_PX * SS, CELL_PX * SS))
    cell.paste(big, (int(round(ox)), int(round(oy))), big)
    cell = cell.resize((CELL_PX, CELL_PX), Image.LANCZOS)

    nx, ny = NAPE[0] - FIG[0] + PAD - hip[0], NAPE[1] - FIG[1] + PAD - hip[1]
    nx, ny = A[0] + k * (c * nx - s * ny) + ox, A[1] + k * (s * nx + c * ny) + oy
    nx, ny = nx / SS, ny / SS
    return cell, ((nx - CELL_PX / 2) / K, (CELL_PX - BASE * K - ny) / K)


def repair_outline(img):
    """실루엣 가장자리에 검은 테두리를 다시 두른다 (원본 테두리 위는 그대로, 휘면서 얇아진 곳만 보강)"""
    a = np.asarray(img).copy()
    solid = Image.fromarray(((a[..., 3] > 100) * 255).astype(np.uint8))
    inner = np.asarray(solid.filter(ImageFilter.MinFilter(REPAIR * 2 + 1))) > 0
    rim = (a[..., 3] > 100) & ~inner
    a[rim, :3] = INK
    return Image.fromarray(a, 'RGBA')


# ---------------------------------------------------------------- 동작
def poses():
    R = {}
    tau = 2 * math.pi

    # 걷기: 앞으로 내딛는 다리는 무릎을 굽혀 들어 올리고, 디딘 다리는 곧게. 팔은 다리와 엇갈려 흔든다
    R['walk'] = []
    for i in range(8):
        ph = tau * i / 8
        legs, arms = [], []
        for off in (0.0, math.pi):
            f = ph + off
            legs.append((24 * math.sin(f), -6 - 42 * max(0.0, math.cos(f)) ** 1.5))
            arms.append((-20 * math.sin(f), 14 + 14 * max(0.0, -math.sin(f))))
        R['walk'].append(dict(tilt=5, legs=legs, arms=arms))

    # 달리기: 몸을 숙이고 무릎을 높이 들며, 뒤로 찬 다리는 뒤꿈치가 엉덩이 쪽으로. 팔은 굽혀서 크게 흔든다
    R['run'] = []
    for i in range(8):
        ph = tau * i / 8
        legs, arms = [], []
        for off in (0.0, math.pi):
            f = ph + off
            legs.append((40 * math.sin(f) + 10, -12 - 95 * max(0.0, math.cos(f - 0.6)) ** 1.2))
            arms.append((-48 * math.sin(f) + 10, 75))
        R['run'].append(dict(tilt=20, legs=legs, arms=arms))

    # 잡기: 몸을 숙이며 가까운 팔을 앞으로 쭉 뻗었다가 거둔다
    stance = [(16, -18), (-12, -6)]
    R['grab'] = [dict(tilt=t, legs=stance, arms=[(s, e), (-10, 20)])
                 for t, s, e in ((8, 35, 55), (18, 85, 15), (22, 98, 4), (10, 55, 50))]

    # 주저앉기: 무릎이 풀리며 엉덩이를 바닥에 털썩 붙이고, 다리는 앞으로 뻗은 채 무릎을 살짝 세운다.
    #  손은 바닥을 짚듯 앞으로, 몸은 앞으로 숙여 목덜미가 낮아진다 (허벅지 각도는 화면 기준 + 몸 기울기)
    R['kneel'] = [dict(tilt=t, legs=[(thw + t, kn), (thw + t - 6, kn + 6)], arms=[(s, e), (s - 8, e)])
                  for t, thw, kn, s, e in ((8, 20, -40, 10, 20), (14, 50, -70, 20, 30),
                                           (32, 78, -55, 40, 30), (60, 84, -38, 70, 25))]   # 마지막엔 깊이 숙여 목덜미를 키의 40% 안팎으로

    # 쓰러짐: 무릎이 꺾여 털썩 무릎을 꿇고, 무릎 꿇은 자세 그대로 상체가 앞으로 고꾸라져 엎드린다.
    #  허벅지 각도는 화면 기준(world)으로 정하고 몸 기울기를 더해 몸 기준으로 바꾼다.
    #  무릎이 바닥에 붙어 있도록 무릎 위치를 기준으로 칸에 놓는다 (엎드린 몸이 칸에 들어오게 기준을 조금씩 뒤로)
    R['death'] = []
    for t, thw, kn, s, e, kx in ((6, 15, -35, 10, 15, 0.50), (10, 22, -78, 12, 20, 0.50),
                                (12, 6, -102, 15, 25, 0.48), (22, 4, -100, 25, 25, 0.46),
                                (46, -6, -96, 60, 20, 0.42), (70, -26, -82, 100, 15, 0.38),
                                (88, -46, -60, 140, 8, 0.35), (92, -70, -28, 160, 4, 0.33)):
        R['death'].append(dict(tilt=t, legs=[(thw + t, kn), (thw + t - 4, kn + 4)],
                               arms=[(s, e), (s - 10, e)], knee_x=kx))

    # 목 가리기: 두 손을 목 뒤로 올려 목덜미를 덮는다 (팔꿈치는 위로)
    g1 = ik_arm((NAPE[0] - 6, NAPE[1] + 4), bend=-1)
    g2 = ik_arm((NAPE[0] - 2, NAPE[1] + 12), bend=-1)
    R['guard'] = [dict(tilt=4, legs=[(10, -12), (-8, -4)], arms=[g1, (g1[0] - 6, g1[1])]),
                  dict(tilt=6, legs=[(-8, -4), (10, -12)], arms=[g2, (g2[0] - 6, g2[1])])]
    return R


def main():
    L = make_layers()
    P = poses()
    sheet = Image.new('RGBA', (max(n for _, n in ROWS) * CELL_PX, len(ROWS) * CELL_PX))
    meta = {'cell': CELL, 'cell_px': CELL_PX, 'base': BASE, 'height': HEIGHT, 'rows': [], 'nape': {}}
    for r, (name, n) in enumerate(ROWS):
        assert len(P[name]) == n, name
        napes = []
        for c, p in enumerate(P[name]):
            img, (nx, ny) = frame(L, p)
            sheet.alpha_composite(ImageOps.mirror(img), (c * CELL_PX, r * CELL_PX))   # 왼쪽을 보게 뒤집는다
            napes.append([round(-nx, 1), round(ny, 1)])
        meta['nape'][name] = napes
        print('  ', name, '완료')
    meta['rows'] = [[r, n] for r, n in ROWS]
    sheet.save(os.path.join(OUT, 'giant_basic.png'))
    # 맞았을 때 번쩍이는 하얀 판: 검은 선은 두고 나머지를 흰색으로
    a = np.asarray(sheet).copy()
    light = a[..., :3].astype(int).sum(2) > 160
    a[light, :3] = 255
    Image.fromarray(a, 'RGBA').save(os.path.join(OUT, 'giant_basic_flash.png'))
    with open(os.path.join(OUT, 'giant_basic_meta.json'), 'w') as f:
        json.dump(meta, f, indent=1)
    print('saved giant_basic.png', sheet.size, 'giant_basic_flash.png giant_basic_meta.json')


if __name__ == '__main__':
    main()
