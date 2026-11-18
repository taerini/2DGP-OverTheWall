"""PixelLab 동료 시트 합치기 (96×96 칸, 줄 8개, 줄마다 8프레임, 오른쪽을 봄).

PixelLab 에서 만든 캐릭터(오른쪽 방향) 프레임을 resource/<이름>_src/ 에 받아 두고,
줄마다 프레임을 골라 한 장으로 붙인다. 그림 자체는 고치지 않는다.
- 캔버스 크기마다 발바닥 높이가 다르다 (FOOT). 칸 아래에서 BASE(8)px 위에 발바닥이 오도록 맞춘다.
- 폴더 이름 대신 'east' 를 쓰면 서 있는 기본 모습(east.png) 한 장을 그 줄 전체에 쓴다.

실행: python tools/make_ally_px.py [ally_red|ally_hood ...]   (안 주면 전부)
  →  resource/ally_red_px.png (빨간 목도리 동료),
     ally_hood_px.png (후드 동료)
(필요: pillow)
"""
import json
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'resource')

CELL = 96
BASE = 8
FOOT = {64: 64, 84: 72, 88: 75}  # 캔버스 크기별 발바닥 높이
ALL8 = [0, 1, 2, 3, 4, 5, 6, 7]
STILL = ('east', [0] * 8)        # 서 있는 기본 모습 한 장

# 캐릭터별 줄: (시트 줄 이름, PixelLab 애니메이션 폴더, 쓸 프레임 번호 8개, 발바닥 높이를 따로 줄 때)
# 줄 순서는 player.ROWS 와 같다
CHARS = {
    # 동료는 날기(wire)·베기(slashQ)·공중(air) 만 쓴다. 나머지 줄은 서 있는 모습으로 채운다
    'ally_red': dict(src='ally_red_src', out='ally_red_px', rows=[
        ('idle',   *STILL),
        ('run',    *STILL),
        ('wire',   'wire_fly', [1, 2, 3, 4, 5, 6, 7, 1]),              # 0번은 몸을 눕히는 중이라 뺀다
        ('air',    *STILL),
        ('slashQ', 'slashQ',   ALL8),
        ('slashW', 'slashQ',   ALL8),
        ('spinE',  *STILL),
        ('hit',    *STILL),
    ]),
    'ally_hood': dict(src='ally_hood_src', out='ally_hood_px', rows=[
        ('idle',   *STILL),
        ('run',    *STILL),
        ('wire',   'wire_fly', ALL8),
        ('air',    *STILL),
        ('slashQ', 'slashQ_side', ALL8),          # 옆모습을 지키며 베기 (얼굴이 드러나지 않게)
        ('slashW', 'slashQ_side', ALL8),
        ('spinE',  *STILL),
        ('hit',    *STILL),
    ]),
}


def frame(src, folder, i):
    if folder == 'east':
        return Image.open(os.path.join(OUT, src, 'east.png')).convert('RGBA')
    return Image.open(os.path.join(OUT, src, folder, 'east', 'frame_%03d.png' % i)).convert('RGBA')


def build(c):
    rows = c['rows']
    sheet = Image.new('RGBA', (CELL * 8, CELL * len(rows)), (0, 0, 0, 0))
    for r, (_, folder, picks, *foot) in enumerate(rows):
        for col, i in enumerate(picks):
            im = frame(c['src'], folder, i)
            x = col * CELL + (CELL - im.width) // 2
            if foot and foot[0] == 'ground':
                feet = im.getbbox()[3]          # 넘어지며 몸이 뜨는 장도 그림 맨 아래를 바닥에 붙인다
            else:
                feet = foot[0] if foot else FOOT[im.height]
            y = r * CELL + CELL - BASE - feet
            sheet.alpha_composite(im, (x, y))
    sheet.save(os.path.join(OUT, c['out'] + '.png'))
    meta = {'cell': [CELL, CELL], 'base': BASE, 'rows': [[row[0], 8] for row in rows]}
    with open(os.path.join(OUT, c['out'] + '_meta.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=1)
    print('resource/%s.png' % c['out'], sheet.size)


def main():
    for name in sys.argv[1:] or list(CHARS):
        build(CHARS[name])


if __name__ == '__main__':
    main()
