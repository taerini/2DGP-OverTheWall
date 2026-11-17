"""바람 픽셀 그림 생성기: 수박 거인이 '후' 하고 내뿜는 바람 덩어리.

몽글몽글한 공기 뭉치(동그라미 몇 개를 겹친 모양)에 안쪽 소용돌이 한 줄. 크기 4가지 × 흩어지는 단계 4장.
작게 그리고 게임에서 3배로 키워 그린다 (배경 그림과 같은 픽셀 크기).
그림은 오른쪽으로 부는 모양 (왼쪽으로 불 때는 게임에서 뒤집는다).
실행: python tools/make_wind_px.py
  →  resource/wind_px.png   가로: 흩어지는 단계 (0 = 막 나옴 → 3 = 거의 사라짐), 세로: 크기 (위에서부터 작은 것 → 큰 것)
                            칸 크기 CELL × CELL (게임의 effect.Wind 와 맞춘다)
(필요: pillow)
"""
import math
import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'resource')
CELL = 28
FRAMES = 4

LIGHT = (252, 253, 255)      # 위쪽 밝은 면
BODY = (232, 240, 248)       # 몸
SHADE = (196, 214, 230)      # 아래 그늘
EDGE = (160, 184, 206)       # 테두리
SWIRL = (176, 198, 220)      # 안쪽 소용돌이

# 크기: (공기 뭉치를 이루는 동그라미들 (가운데 기준 x, y, 반지름), 소용돌이 반지름(0 이면 없음))
# 오른쪽(부는 쪽)이 크고 둥글고, 뒤(왼쪽)로 작은 뭉치가 꼬리처럼 따라온다
SIZES = [
    ([(0, 0, 2.6), (-3, 1, 1.6)], 0),
    ([(1, 0, 3.6), (-3, 1, 2.4), (-6, 2, 1.4)], 0),
    ([(2, -1, 4.6), (-3, 1, 3.4), (5, 2, 2.8), (-7, 2, 2.0)], 2.2),
    ([(2, -1, 6.0), (-4, 1, 4.4), (7, 2, 3.6), (-9, 3, 2.6), (3, 4, 3.6)], 3.2),
]


def inside(circles, x, y):
    return any((x - cx) ** 2 + (y - cy) ** 2 <= r * r for cx, cy, r in circles)


def puff(circles, swirl_r, frame):
    # 흩어질수록 작은 뭉치들이 서로 벌어지고(퍼지고), 하나하나는 줄어든다
    grow = 1 + 0.22 * frame
    cs = [(cx * grow, cy * grow - 0.4 * frame, r * (1 - 0.2 * frame)) for cx, cy, r in circles]
    cs = [c for c in cs if c[2] >= 0.9]
    im = Image.new('RGBA', (CELL, CELL), (0, 0, 0, 0))
    o = CELL // 2
    keep = set()
    for y in range(-o, o):
        for x in range(-o, o):
            if inside(cs, x + 0.5, y + 0.5):
                keep.add((x, y))
    alpha = [255, 235, 205, 160][frame]
    for x, y in keep:
        nb = [(x + dx, y + dy) in keep for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
        if not all(nb):
            col = EDGE
        elif (x, y - 1) not in keep or (x, y - 2) not in keep:
            col = LIGHT                                   # 위쪽 가장자리: 빛
        elif (x, y + 1) not in keep or (x + 1, y + 1) not in keep:
            col = SHADE                                   # 아래쪽: 그늘
        else:
            col = BODY
        im.putpixel((x + o, y + o), col + (alpha,))
    # 안쪽 소용돌이: 앞쪽 큰 동그라미 가운데에서 바깥으로 돌아 나가는 한 줄
    if swirl_r and frame < 2:
        cx, cy, _ = cs[0]
        for s in range(60):
            t = 1.7 * math.pi * s / 59
            rr = swirl_r * grow * (0.25 + 0.75 * s / 59)
            px, py = round(cx - rr * math.cos(t)), round(cy - rr * math.sin(t))
            if (px, py) in keep:
                im.putpixel((px + o, py + o), SWIRL + (alpha,))
    return im


def main():
    sheet = Image.new('RGBA', (CELL * FRAMES, CELL * len(SIZES)), (0, 0, 0, 0))
    for si, (circles, sw) in enumerate(SIZES):
        for f in range(FRAMES):
            sheet.alpha_composite(puff(circles, sw, f), (f * CELL, si * CELL))
    path = os.path.join(OUT, 'wind_px.png')
    sheet.save(path)
    print('saved', path, sheet.size)


if __name__ == '__main__':
    main()
