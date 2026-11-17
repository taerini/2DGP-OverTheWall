"""효과 그림을 픽셀 그림으로 직접 그리기.

베기 궤적(초승달), 일섬, 연기, 고리를 아주 작은 캔버스에 한 칸씩 찍어 '*_px.png' 로 저장한다.
게임에서는 픽셀 그대로 크게 늘려 그려서(render.image(..., pixel=True)) 각진 픽셀 느낌이 난다.

실행: python tools/make_fx_px.py  →  resource/arc_q_px.png, arc_w_px.png, arc_e_px.png,
                                      streak_px.png, puff_px.png, ring_px.png
(필요: pillow)
"""
import math
import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'resource')

WHITE = (255, 255, 255, 255)
LIGHT = (196, 236, 255, 255)
EDGE = (120, 196, 255, 230)
FAINT = (90, 160, 230, 150)


def crescent(n, r_out, r_in, shift, squash=1.0):
    """오른쪽으로 휘어 나가는 초승달: 큰 원에서 왼쪽으로 민 작은 원을 뺀다. 안쪽일수록 밝다."""
    im = Image.new('RGBA', (n, n))
    c = (n - 1) / 2
    for y in range(n):
        for x in range(n):
            dx, dy = x - c, (y - c) / squash
            d_out = math.hypot(dx, dy)
            d_in = math.hypot(dx + shift, dy)
            if d_out <= r_out and d_in > r_in:
                t = (d_in - r_in) / max(1.0, r_out - r_in + shift)     # 0 = 안쪽 가장자리
                if r_out - d_out < 1.0:
                    col = EDGE
                elif t < 0.18:
                    col = WHITE
                elif t < 0.45:
                    col = LIGHT
                elif t < 0.8:
                    col = EDGE
                else:
                    col = FAINT
                im.putpixel((x, y), col)
    return im


def ring(n, r, w):
    im = Image.new('RGBA', (n, n))
    c = (n - 1) / 2
    for y in range(n):
        for x in range(n):
            d = math.hypot(x - c, y - c)
            if r - w <= d <= r:
                im.putpixel((x, y), WHITE if d > r - w / 2 else LIGHT)
    return im


def streak():
    """일섬: 가운데가 두껍고 양 끝으로 갈수록 가늘어지는 빛줄기 (64×8)"""
    im = Image.new('RGBA', (64, 8))
    for x in range(64):
        k = 1 - abs(x - 31.5) / 32           # 가운데 1, 끝 0
        half = max(0, round(k * 3.5))
        for y in range(4 - half, 4 + half):
            core = abs(y - 3.5) < half - 1
            im.putpixel((x, y), WHITE if core else EDGE)
    return im


def puff():
    """연기 한 덩이 (16×16): 둥근 덩어리, 위쪽이 밝다"""
    im = Image.new('RGBA', (16, 16))
    for y in range(16):
        for x in range(16):
            d = math.hypot(x - 7.5, y - 7.5)
            if d <= 7.2:
                col = (255, 255, 255, 230) if (y < 7 and d < 5.5) else (210, 210, 210, 200)
                if d > 6.2:
                    col = (170, 170, 170, 150)
                im.putpixel((x, y), col)
    return im


def main():
    items = {
        'arc_q_px': crescent(32, 15, 13, 5),               # 가로로 휘두르는 큰 초승달
        'arc_w_px': crescent(32, 15, 13, 5, squash=0.45),   # 아래쪽을 낮게 쓸어 베는 납작한 초승달
        'arc_e_px': ring(32, 15, 3),                       # 회오리: 둥근 고리
        'streak_px': streak(),
        'puff_px': puff(),
        'ring_px': ring(16, 7.5, 2),
    }
    for name, im in items.items():
        im.save(os.path.join(OUT, name + '.png'))
        print(name + '.png', im.size)


if __name__ == '__main__':
    main()
