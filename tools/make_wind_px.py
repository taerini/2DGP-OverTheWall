"""바람 픽셀 그림 생성기: 수박 거인이 '후' 하고 내뿜는 바람 덩어리.

옆으로 늘인 반투명 공기 뭉치(타원 몇 개를 겹친 모양)에 안쪽 소용돌이 한 줄. 크기 4가지 × 흩어지는 단계 4장.
작게 그리고 게임에서 3배로 키워 그린다 (배경 그림과 같은 픽셀 크기).
그림은 오른쪽으로 부는 모양 (왼쪽으로 불 때는 게임에서 뒤집는다).
실행: python tools/make_wind_px.py
  →  resource/wind_px.png   가로: 흩어지는 단계 (0 = 막 나옴 → 3 = 거의 사라짐), 세로: 크기 (위에서부터 작은 것 → 큰 것)
                            칸 크기 CELL_W × CELL_H (게임의 effect.Wind 와 맞춘다)
(필요: pillow)
"""
import math
import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'resource')
CELL_W, CELL_H = 44, 20      # 칸 크기 (게임의 effect.Wind 와 맞춘다)
FRAMES = 4
STRETCH = 1.8                # 옆으로 늘인 비율: 둥근 덩어리(침처럼 보임)가 아니라 밀려가는 공기처럼

# 침처럼 보이지 않게: 테두리 없이 반투명. 가운데만 조금 진하고 가장자리는 아주 옅게
CORE = (250, 252, 255, 150)  # 가운데
BODY = (236, 244, 252, 95)   # 몸
RIM = (226, 238, 250, 50)    # 가장자리 (옅은 테)
SWIRL = (255, 255, 255, 210) # 안쪽 소용돌이 (가장 또렷)

# 크기: (공기 뭉치를 이루는 동그라미들 (가운데 기준 x, y, 반지름), 소용돌이 반지름(0 이면 없음))
# 오른쪽(부는 쪽)이 크고, 뒤(왼쪽)로 작은 뭉치가 꼬리처럼 따라온다. x 는 STRETCH 만큼 늘어난다
SIZES = [
    ([(0, 0, 2.2), (-2.5, 0.5, 1.4)], 1.4),
    ([(1, 0, 3.0), (-2.5, 1, 2.0), (-5, 1.5, 1.2)], 2.0),
    ([(2, -0.5, 3.8), (-2.5, 1, 2.8), (4.5, 1.5, 2.2), (-6, 1.5, 1.6)], 2.8),
    ([(2, -1, 5.0), (-3.5, 1, 3.6), (6, 1.5, 3.0), (-8, 2, 2.2), (3, 3, 3.0)], 3.6),
]


def inside(circles, x, y, shrink=0.0):
    return any(((x - cx) / STRETCH) ** 2 + (y - cy) ** 2 <= (r - shrink) ** 2 for cx, cy, r in circles if r > shrink)


def puff(circles, swirl_r, frame):
    # 흩어질수록 작은 뭉치들이 서로 벌어지고(퍼지고), 하나하나는 줄어들며 옅어진다
    grow = 1 + 0.22 * frame
    cs = [(cx * STRETCH * grow, cy * grow - 0.3 * frame, r * (1 - 0.18 * frame)) for cx, cy, r in circles]
    cs = [c for c in cs if c[2] >= 0.9]
    fade = [1.0, 0.85, 0.65, 0.4][frame]
    im = Image.new('RGBA', (CELL_W, CELL_H), (0, 0, 0, 0))
    ox, oy = CELL_W // 2, CELL_H // 2
    for y in range(-oy, oy):
        for x in range(-ox, ox):
            px, py = x + 0.5, y + 0.5
            if not inside(cs, px, py):
                continue
            if inside(cs, px, py, 1.8):
                col = CORE
            elif inside(cs, px, py, 0.8):
                col = BODY
            else:
                col = RIM
            im.putpixel((x + ox, y + oy), col[:3] + (int(col[3] * fade),))
    # 안쪽 소용돌이: 앞쪽 큰 덩어리 가운데에서 바깥으로 돌아 나가는 한 줄 (옆으로 늘인 모양)
    if swirl_r and frame < 3:
        cx, cy, _ = cs[0]
        seen = set()
        turn = 1.5 if frame == 0 else 1.1   # 흩어질수록 소용돌이가 풀린다
        for s in range(80):
            t = turn * math.pi * s / 79
            rr = swirl_r * grow * (0.3 + 0.7 * s / 79)
            p = (round(cx - rr * STRETCH * math.cos(t)), round(cy - rr * math.sin(t)))
            if p not in seen and -ox <= p[0] < ox and -oy <= p[1] < oy:
                seen.add(p)
                im.putpixel((p[0] + ox, p[1] + oy), SWIRL[:3] + (int(SWIRL[3] * fade),))
    return im


def main():
    sheet = Image.new('RGBA', (CELL_W * FRAMES, CELL_H * len(SIZES)), (0, 0, 0, 0))
    for si, (circles, sw) in enumerate(SIZES):
        for f in range(FRAMES):
            sheet.alpha_composite(puff(circles, sw, f), (f * CELL_W, si * CELL_H))
    path = os.path.join(OUT, 'wind_px.png')
    sheet.save(path)
    print('saved', path, sheet.size)


if __name__ == '__main__':
    main()
