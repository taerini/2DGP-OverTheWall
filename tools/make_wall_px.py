"""우리 벽 픽셀 그림 생성기: 거대한 돌 성벽(부벽 기둥, 빗물 얼룩, 성가퀴)과 옆에서 본 아주 큰 성문.

작게(1/3) 그린 뒤 3배로 키운다 (배경 그림과 같은 픽셀 크기).
실행: python tools/make_wall_px.py
  →  resource/wall_px.png       성벽 한 칸 (왼쪽으로 이어 붙인다, 위쪽 성가퀴 사이는 투명)
     resource/wall_px_end.png   성벽 오른쪽 끝 (큰 모서리 기둥)
     resource/gate_px_side.png  옆에서 본 성문 문짝 (벽 앞면에 붙어 위로 올라가며 열린다)
(필요: pillow)
"""
import os
import random

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'resource')
S = 3                    # 키우는 배율
H = 240                  # 그림 높이 (작은 그림 기준, ×3 = 화면 720)
TILE = 180               # 성벽 한 칸 폭 (×3 = 540)
MERLON = (14, 9, 10)     # 성가퀴: 폭, 사이 폭, 높이

STONE = (148, 140, 128)
STONE_D = (118, 111, 102)
JOINT = (92, 86, 80)
PILLAR = (164, 156, 143)
PILLAR_HI = (186, 178, 164)
PILLAR_SH = (96, 90, 84)
STAIN = (70, 66, 62)
MOSS = (92, 108, 74)


def mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def stone_wall(w, seed):
    """돌 벽면: 줄눈 + 돌마다 조금씩 다른 밝기 + 아래로 갈수록 어두워짐"""
    rnd = random.Random(seed)
    im = Image.new('RGBA', (w, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    course = 8
    for row, y in enumerate(range(0, H, course)):
        off = 0 if row % 2 else 9
        x = -off
        while x < w:
            bw = rnd.choice((16, 18, 20, 22))
            dark = 0.25 + 0.55 * (y / H) + rnd.uniform(-0.12, 0.12)
            col = mix(STONE, STONE_D, max(0.0, min(1.0, dark)))
            d.rectangle((x, y, x + bw - 1, y + course - 1), fill=col + (255,))
            d.line((x, y, x + bw - 1, y), fill=mix(col, (210, 200, 185), 0.18) + (255,))      # 윗면 빛
            d.line((x + bw - 1, y, x + bw - 1, y + course - 1), fill=JOINT + (255,))          # 세로 줄눈
            d.line((x, y + course - 1, x + bw - 1, y + course - 1), fill=JOINT + (255,))      # 가로 줄눈
            x += bw
    # 빗물 얼룩: 위에서 아래로 흘러내린 어두운 자국
    for _ in range(w // 9):
        sx = rnd.randrange(w)
        sy = rnd.randrange(10, H // 2)
        ln = rnd.randrange(30, 140)
        for y in range(sy, min(H, sy + ln)):
            a = 1 - (y - sy) / ln
            if rnd.random() < 0.85:
                px = im.getpixel((sx, y))
                im.putpixel((sx, y), mix(px[:3], STAIN, 0.35 * a) + (255,))
        sx += rnd.choice((-1, 1))
    # 아래쪽 이끼
    for _ in range(w // 3):
        x, y = rnd.randrange(w), rnd.randrange(H - 26, H)
        im.putpixel((x, y), MOSS + (255,))
    return im


def pillar(im, x, pw, seed):
    """부벽 기둥: 벽에서 튀어나온 넓은 기둥. 왼쪽은 밝고 오른쪽 옆면은 그늘"""
    rnd = random.Random(seed)
    d = ImageDraw.Draw(im)
    side = max(4, pw // 4)
    for y in range(0, H):
        t = y / H
        d.line((x, y, x + pw - side - 1, y), fill=mix(PILLAR, STONE_D, 0.5 * t) + (255,))
        d.line((x + pw - side, y, x + pw - 1, y), fill=mix(PILLAR_SH, (60, 56, 52), 0.5 * t) + (255,))
    d.line((x, 0, x, H), fill=PILLAR_HI + (255,))
    d.line((x + 1, 0, x + 1, H), fill=mix(PILLAR_HI, PILLAR, 0.5) + (255,))
    for y in range(6, H, 12):                                                    # 큰 돌 줄눈
        d.line((x + 2, y, x + pw - side - 1, y), fill=JOINT + (255,))
    # 기둥에도 얼룩
    for _ in range(3):
        sx = x + rnd.randrange(3, pw - side - 1)
        sy = rnd.randrange(10, 80)
        for y in range(sy, min(H, sy + rnd.randrange(40, 120))):
            px = im.getpixel((sx, y))
            im.putpixel((sx, y), mix(px[:3], STAIN, 0.3) + (255,))


def crenel(im):
    """위쪽 성가퀴: 톱니 사이를 투명하게 판다"""
    mw, gap, mh = MERLON
    d = ImageDraw.Draw(im)
    x = 0
    while x < im.width:
        d.rectangle((x + mw, 0, x + mw + gap - 1, mh - 1), fill=(0, 0, 0, 0))
        d.line((x, mh, x + mw - 1, mh), fill=(0, 0, 0, 0))
        d.line((x, 0, x + mw - 1, 0), fill=PILLAR_HI + (255,))                  # 성가퀴 윗면 빛
        x += mw + gap
    d.line((0, mh, im.width, mh), fill=PILLAR_HI + (255,))


def up(im):
    return im.resize((im.width * S, im.height * S), Image.NEAREST)


def wall_tile():
    im = stone_wall(TILE, 1)
    pillar(im, 0, 26, 2)
    pillar(im, 98, 22, 3)
    crenel(im)
    return im


def wall_end():
    """오른쪽 끝: 크고 두꺼운 모서리 기둥 (벽 두께가 보이는 옆면 그늘 포함)"""
    w = 60
    im = stone_wall(w, 7)
    pillar(im, 4, 50, 8)
    crenel(im)
    return im


GATE_T, GATE_H = 9, 110     # 성문을 옆에서 본 두께 · 높이 (작은 그림 기준, ×3 = 27 × 330)


def gate_side():
    """옆에서 본 성문: 쇠띠를 두른 두꺼운 나무 문짝. 아래 끝에는 뾰족한 쇠날"""
    w, h = GATE_T, GATE_H + 4
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    wood, wood_hi, wood_d = (96, 70, 50), (128, 96, 70), (58, 42, 32)
    iron, iron_hi = (58, 58, 64), (98, 98, 106)
    d.rectangle((0, 0, w - 1, GATE_H - 1), fill=wood + (255,))
    d.line((0, 0, 0, GATE_H - 1), fill=wood_hi + (255,))            # 왼쪽 모서리 빛
    d.line((w - 1, 0, w - 1, GATE_H - 1), fill=wood_d + (255,))     # 오른쪽 그늘
    for y in range(3, GATE_H - 4, 7):                               # 나뭇결
        d.point((2 + (y // 7) % 4, y), fill=wood_d + (255,))
    for y in range(6, GATE_H - 4, 16):                              # 쇠띠 + 못
        d.rectangle((0, y, w - 1, y + 2), fill=iron + (255,))
        d.line((0, y, w - 1, y), fill=iron_hi + (255,))
        d.point((w // 2, y + 1), fill=(160, 160, 168, 255))
    for x in (1, 4, 7):                                             # 아래 끝 쇠날
        d.polygon([(x - 1, GATE_H), (x + 1, GATE_H), (x, GATE_H + 3)], fill=iron + (255,))
    return im


def main():
    up(wall_tile()).save(os.path.join(OUT, 'wall_px.png'))
    up(wall_end()).save(os.path.join(OUT, 'wall_px_end.png'))
    up(gate_side()).save(os.path.join(OUT, 'gate_px_side.png'))
    print('wall_px', TILE * S, H * S, 'gate', GATE_T * S, GATE_H * S)


if __name__ == '__main__':
    main()
