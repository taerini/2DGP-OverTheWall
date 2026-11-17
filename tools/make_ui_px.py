"""픽셀 UI 아이콘 만들기.

- 가스통: PixelLab 원본(resource/ui_px_src/gas_raw.png)을 둘레 여백만 잘라 쓴다.
- 성벽: 코드로 한 칸씩 찍는다 (16×16).

실행: python tools/make_ui_px.py  →  resource/ui_gas.png, resource/ui_wall.png
(필요: pillow)
"""
import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'resource')

# 성벽 아이콘: . 투명, K 외곽선, L 밝은 돌, M 돌, D 어두운 돌(줄눈), G 문
WALL = [
    '................',
    '.KKKK.KKKK.KKKK.',
    '.KLLK.KLLK.KLLK.',
    '.KMMKKKMMKKKMMK.',
    '.KMMMMMMMMMMMMK.',
    '.KLLLDLLLLDLLLK.',
    '.KMMMDMMMMDMMMK.',
    '.KDDDDDDDDDDDDK.',
    '.KLDLLLLDLLLLDK.',
    '.KMDMMMMDMMMMDK.',
    '.KDDDDKKKKDDDDK.',
    '.KLLLKGGGGKLLLK.',
    '.KMMMKGGGGKMMMK.',
    '.KMMMKGGGGKMMMK.',
    '.KKKKKKKKKKKKKK.',
    '................',
]
COLORS = {'K': (20, 18, 24), 'L': (170, 172, 168), 'M': (128, 130, 128), 'D': (82, 84, 86), 'G': (92, 62, 40)}


def wall_icon():
    im = Image.new('RGBA', (16, 16))
    for y, row in enumerate(WALL):
        for x, ch in enumerate(row):
            if ch in COLORS:
                im.putpixel((x, y), COLORS[ch] + (255,))
    return im


def main():
    g = Image.open(os.path.join(OUT, 'ui_px_src', 'gas_raw.png')).convert('RGBA')
    g = g.crop(g.getbbox())
    g.save(os.path.join(OUT, 'ui_gas.png'))
    wall_icon().save(os.path.join(OUT, 'ui_wall.png'))
    print('ui_gas.png', g.size, 'ui_wall.png (16, 16)')


if __name__ == '__main__':
    main()
