"""PixelLab 배경 정리 (모든 구간).

resource/bg_px_src/ 의 PixelLab 원본을 게임 배경 형식에 맞게 바꾼다.
- 먼·중간 배경: 하늘을 지우고, 밝기를 구간 색 범위로 다시 칠하고(원래 배경처럼 반투명),
  좌우를 뒤집어 이어 붙여 끊김 없이 반복되게 만든 뒤 3배로 키운다 (픽셀 그대로).
- 하늘: 원래 하늘 그라데이션을 색 띠로 끊는다.
- 땅: 위쪽 하늘색을 지우고 왼쪽 절반을 뒤집어 이어 붙여 128px 타일로.
- 발판: 떠 있는 땅 한 덩이를 2배로 키워 왼끝·가운데·오른끝(24 / 128 / 24px)으로 자른다.
- 소품: 발이 바닥에 닿게 아래 여백만 자른다.
- 구간 3~9: 하늘이 투명한 원본을 구간 색으로 다시 칠하고(불·창문 불빛은 그대로), 그림 아래 빈 곳을 메운다.

실행: python tools/make_bg_px.py
  →  resource/far_px_N.png, mid_px_N.png, sky_px_N.png (N = 1~9), ground_px.png,
     lane_px_left.png, lane_px_mid.png, lane_px_right.png, prop_px_*.png
(필요: pillow)
"""
import os

from PIL import Image, ImageDraw, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'resource')
SRC = os.path.join(OUT, 'bg_px_src')
SCALE = 3                        # 먼·중간 배경 픽셀 크기
SKY_BANDS = 10


def src(name):
    return Image.open(os.path.join(SRC, name)).convert('RGBA')


def save(im, name):
    im.save(os.path.join(OUT, name))
    print(name, im.size)


def lum(c):
    return (0.3 * c[0] + 0.59 * c[1] + 0.11 * c[2]) / 255


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def recolor(im, keep, dark, light, alpha, gain):
    """keep(c) 가 None 이면 지우고, 'cloud' 면 구름색, 아니면 밝기를 dark~light 로 다시 칠한다."""
    out = Image.new('RGBA', im.size)
    for y in range(im.height):
        for x in range(im.width):
            c = im.getpixel((x, y))
            k = keep(c)
            if k is None:
                continue
            if k == 'cloud':
                out.putpixel((x, y), (222, 230, 230, 90))
            else:
                out.putpixel((x, y), lerp(dark, light, min(1.0, lum(c) * gain)) + (alpha,))
    return out


def loop_wide(im):
    """좌우를 뒤집어 이어 붙여 반복 이음매를 없애고 SCALE 배로 키운다."""
    w = Image.new('RGBA', (im.width * 2, im.height))
    w.paste(im, (0, 0))
    w.paste(ImageOps.mirror(im), (im.width, 0))
    return w.resize((w.width * SCALE, w.height * SCALE), Image.NEAREST)


def layers():
    # 구간 1: 분홍빛 하늘을 지우고 회청색 안개 톤으로
    def far1(c):
        if c[3] < 128:
            return None
        if c[1] >= 225:
            return 'cloud'
        if c[0] > 215 and c[2] > 235:
            return None
        return 'land'

    def mid1(c):
        if c[3] < 128 or (c[2] > c[1] + 40 and c[0] > c[1] + 20):   # 분홍 하늘, 보라 먼 산
            return None
        return 'land'

    solid = lambda c: None if c[3] < 128 else 'land'
    save(loop_wide(recolor(src('far1_raw.png'), far1, (104, 122, 130), (186, 200, 204), 150, 1.4)), 'far_px_1.png')
    save(loop_wide(recolor(src('mid1_raw.png'), mid1, (58, 76, 66), (150, 170, 154), 220, 1.8)), 'mid_px_1.png')
    # 구간 2: 어두운 초록 숲
    save(loop_wide(recolor(src('far2_raw.png'), solid, (16, 30, 24), (70, 104, 84), 200, 1.1)), 'far_px_2.png')
    save(loop_wide(recolor(src('mid2_raw.png'), solid, (10, 20, 16), (44, 70, 54), 235, 1.3)), 'mid_px_2.png')
    # 구간 3~: 하늘이 투명한 원본(farN_raw / midN_raw). 밝기를 구간 색 범위로 다시 칠하고 아래 빈 곳은 메운다
    for n, (far, mid, glow) in ZONE_LAYERS.items():
        save(loop_wide(fill_below(retone(src('far%d_raw.png' % n), *far, glow))), 'far_px_%d.png' % n)
        save(loop_wide(fill_below(retone(src('mid%d_raw.png' % n), *mid, glow))), 'mid_px_%d.png' % n)


# 구간 3~9 배경 색: (먼 배경 (어두운 색, 밝은 색, 불투명도), 중간 배경 (...), 불빛 남기기)
# 불빛 남기기: 불·창문처럼 주황·노랑으로 빛나는 픽셀은 원래 색 그대로 둔다
ZONE_LAYERS = {
    3: (((22, 28, 48), (74, 88, 126), 215), ((12, 15, 28), (54, 64, 98), 240), False),     # 달밤의 고성
    6: (((118, 130, 144), (206, 214, 222), 175), ((60, 66, 70), (150, 158, 152), 235), False),   # 무너진 벽 아래
    7: (((96, 46, 60), (220, 136, 112), 200), ((34, 18, 26), (124, 66, 68), 238), False),    # 노을 평야
    4: (((40, 20, 18), (150, 72, 42), 220), ((20, 10, 10), (92, 42, 28), 242), True),       # 불타는 마을
    8: (((48, 104, 160), (204, 232, 250), 235), ((118, 102, 74), (228, 208, 162), 242), False),  # 처음 본 바다
    5: (((14, 13, 20), (74, 70, 88), 230), ((8, 8, 12), (50, 46, 60), 242), True),          # 공업 도시
    9: (((62, 52, 44), (164, 140, 112), 195), ((26, 21, 19), (94, 78, 62), 238), False),    # 항구 요새
}


def is_glow(c):
    return c[0] > 180 and c[0] - c[2] > 90 and c[1] > 70


def retone(im, dark, light, alpha, glow):
    """불투명한 픽셀만 남겨 밝기(아래위 2% 를 잘라 0~1 로 편다)를 dark~light 로 다시 칠한다."""
    px = [(x, y, im.getpixel((x, y))) for y in range(im.height) for x in range(im.width)]
    px = [p for p in px if p[2][3] >= 128]
    ls = sorted(lum(c) for _, _, c in px)
    lo, hi = ls[int(len(ls) * 0.02)], ls[int(len(ls) * 0.98)]
    out = Image.new('RGBA', im.size)
    for x, y, c in px:
        if glow and is_glow(c):
            out.putpixel((x, y), c[:3] + (255,))
            continue
        t = max(0.0, min(1.0, (lum(c) - lo) / max(1e-6, hi - lo)))
        out.putpixel((x, y), lerp(dark, light, t) + (alpha,))
    return out


def fill_below(im):
    """세로줄마다 처음 그림이 나온 곳 아래의 빈 픽셀을 그 줄의 가장 어두운 색으로 메운다 (땅 아래가 비지 않게)."""
    for x in range(im.width):
        col = [im.getpixel((x, y)) for y in range(im.height)]
        top = next((y for y, c in enumerate(col) if c[3] > 0), None)
        if top is None:
            continue
        dark = min((c for c in col if c[3] > 0), key=lum)
        for y in range(top, im.height):
            if col[y][3] == 0:
                im.putpixel((x, y), dark)
    return im


def skies():
    for n in range(1, 10):
        # 원래 하늘(sky_N)이 지워졌으면 이미 띠로 끊은 하늘을 다시 쓴다 (같은 결과)
        name = 'sky_%d.png' % n
        if not os.path.exists(os.path.join(OUT, name)):
            name = 'sky_px_%d.png' % n
        sky = Image.open(os.path.join(OUT, name)).convert('RGBA')
        out = Image.new('RGBA', sky.size)
        band = sky.height / SKY_BANDS
        for y in range(sky.height):
            c = sky.getpixel((0, int(int(y / band) * band + band / 2)))
            for x in range(sky.width):
                out.putpixel((x, y), c)
        save(out, 'sky_px_%d.png' % n)


GROUND_FEET = 32                 # 원본 땅 그림에서 발이 닿을 줄 (빽빽한 풀밭 가운데)
GROUND_DRAW = 78                 # background.py 가 땅을 길 높이보다 이만큼 아래에서 그린다


def ground():
    g = src('ground_raw.png')
    ImageDraw.floodfill(g, (64, 0), (0, 0, 0, 0), thresh=40)       # 풀 위 하늘색
    # 발 줄이 그림 아래에서 GROUND_DRAW 위에 오도록: 위 빈 줄은 자르고 아래는 흙을 이어 붙인다
    top = g.getbbox()[1]
    g = g.crop((0, top, g.width, g.height))
    h = GROUND_DRAW + GROUND_FEET - top
    if h > g.height:
        ext = Image.new('RGBA', (g.width, h))
        ext.paste(g, (0, 0))
        dirt = g.crop((0, g.height - 20, g.width, g.height))
        for y in range(g.height, h, 20):
            ext.paste(dirt, (0, y))
        g = ext
    half = g.crop((0, 0, 64, g.height))
    t = Image.new('RGBA', (128, g.height))
    t.paste(half, (0, 0))
    t.paste(ImageOps.mirror(half), (64, 0))
    save(t, 'ground_px.png')


def lanes():
    s = src('ledge_raw.png')
    s = s.crop(s.getbbox())
    s = s.resize((s.width * 2, s.height * 2), Image.NEAREST)
    h = s.height
    save(s.crop((0, 0, 24, h)), 'lane_px_left.png')
    save(s.crop((s.width - 24, 0, s.width, h)), 'lane_px_right.png')
    cx = s.width // 2
    half = s.crop((cx - 64, 0, cx, h))
    mid = Image.new('RGBA', (128, h))
    mid.paste(half, (0, 0))
    mid.paste(ImageOps.mirror(half), (64, 0))
    save(mid, 'lane_px_mid.png')


PROP_SCALE = 0.85                # 나무를 원본보다 조금 낮게


def props():
    for name in ('pine', 'bigtree'):
        p = src(name + '_raw.png')
        p = p.crop((0, 0, p.width, p.getbbox()[3]))
        p = p.resize((round(p.width * PROP_SCALE), round(p.height * PROP_SCALE)), Image.NEAREST)
        save(p, 'prop_px_%s.png' % name)
    # 구간 3~ 소품 (PixelLab 오브젝트): 둘레 여백만 잘라 원본 크기 그대로 (예전 소품과 키가 비슷하다)
    for name in ('tower', 'pillar', 'chimney', 'post', 'crane'):
        p = src(name + '_raw.png')
        save(p.crop(p.getbbox()), 'prop_px_%s.png' % name)


if __name__ == '__main__':
    layers()
    skies()
    ground()
    lanes()
    props()
