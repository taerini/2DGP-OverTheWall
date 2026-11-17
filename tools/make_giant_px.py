"""PixelLab 기본 거인 시트 합치기 (기존 거인 시트 형식: 128 단위 칸, 왼쪽을 봄).

PixelLab 에서 만든 '기본 거인'(왼쪽 방향) 프레임을 resource/giant_px_src/ 에 받아 두고,
줄마다 프레임을 골라 한 장으로 붙인다. 그림은 고치지 않는다.
- 프레임 캔버스는 124×124, 발바닥은 y=106. 칸(128)에서 발바닥이 BASE(4) 위에 오도록 놓는다.
- 그림 1px = 1 단위 (cell_px = cell = 128). 서 있을 때 키 HEIGHT = 88.
- 목덜미 좌표: 걷기 0번 프레임의 머리를 본으로 잡고, 프레임마다 머리 위치를 찾아 그만큼 옮긴다.
  엎드린 death 뒤쪽 프레임은 머리가 누워서 따로 정한다.
- 맞았을 때 번쩍이는 하얀 판: 검은 외곽선만 두고 나머지를 흰색으로.

실행: python tools/make_giant_px.py [basic|thin ...]   (안 주면 전부)
  →  resource/giant_px.png · giant_px_flash.png · giant_px_meta.json  (기본 거인)
     resource/giant_thin.png · giant_thin_flash.png · giant_thin_meta.json  (마른 거인)
     resource/giant_female*.png · giant_female_meta.json  (여성형 거인)
     resource/giant_beast_px*.png · giant_beast_px_meta.json  (짐승 거인. giant_beast.png 는 make_sprites.py 의 예전 그림)
(필요: pillow, numpy)
"""
import json
import os
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'resource')

CELL = 128
BASE = 4
SRC_N = 124                      # PixelLab 프레임 캔버스
FOOT = 106                       # 프레임 안 발바닥 높이
OX = (CELL - SRC_N) // 2         # 칸 안에 놓을 x 여백
OY = CELL - BASE - FOOT          # 칸 안에 놓을 y 여백 (발바닥을 기준선에)

# 거인 종류별 설정
#   src: PixelLab 원본 폴더, out: 결과 이름(out.png, out_flash.png, out_meta.json)
#   height: 서 있을 때 키 (발바닥 106 - 머리 꼭대기)
#   head_box / nape_pt: 목덜미 본 = walk 0번 프레임의 머리 부분과 그 안의 목덜미 점 (프레임 픽셀 좌표)
#   rows: (시트 줄 이름, PixelLab 애니메이션 폴더, 쓸 프레임 번호)
#   lying: death 에서 엎드려 누운 프레임, lying_nape: 누운 프레임의 그림 왼쪽 위에서 목덜미까지
#   blend: death 에서 넘어지는 중간 프레임 → (앞 프레임, 뒤 프레임) 사이를 잇는다
GIANTS = {
    'basic': dict(
        src='giant_px_src', out='giant_px', height=88.0,
        head_box=(40, 18, 74, 50), nape_pt=(70, 44),
        rows=[
            ('walk',  'walk',   [0, 1, 2, 3, 4, 5, 6, 7]),
            ('grab',  'attack', [0, 1, 2, 3, 4, 5, 6, 7]),   # 크게 휘둘러 치는 공격
            ('kneel', 'kneel',  [0, 2, 3, 7]),               # 앞으로 털썩 무릎 꿇기
            ('death', 'death',  [0, 1, 2, 3, 4, 5, 6, 7]),   # 앞으로 쓰러져 엎드림
            ('guard', 'guard',  [1, 2]),                     # 손으로 목 뒤 가리기
            ('run',   'run',    [0, 1, 2, 3, 4, 5, 6, 7]),
        ],
        lying={5, 6, 7}, lying_nape=(26, 8), blend={3: (2, 5), 4: (2, 5)}),
    # 마른 거인 (날뛰는 거인): 늘 뛰어다녀서 walk 도 run 그림. grab 은 웅크렸다(0~4) 덮치는(5~7) 돌진
    'thin': dict(
        src='giant_thin_src', out='giant_thin', height=86.0,
        head_box=(38, 18, 62, 44), nape_pt=(61, 31),
        rows=[
            ('walk',  'run',    [0, 1, 2, 3, 4, 5, 6, 7]),
            ('grab',  'lunge',  [0, 1, 2, 3, 4, 5, 6, 7]),
            ('kneel', 'kneel',  [0, 1, 2, 7]),
            ('death', 'death',  [0, 1, 2, 3, 4, 5, 6, 7]),
            ('guard', 'guard',  [2, 3]),
            ('run',   'run',    [0, 1, 2, 3, 4, 5, 6, 7]),
        ],
        lying={4, 5, 6, 7}, lying_nape=(22, 5), blend={3: (2, 4)}),
    # 여성형 거인 (영리한 거인 보스): 키 크고 날씬한 몸, 긴 검은 머리. 뒤로 쓰러져 머리가 오른쪽에 눕는다
    'female': dict(
        src='giant_female_src', out='giant_female', height=85.0,
        head_box=(52, 20, 82, 46), nape_pt=(66, 41),
        rows=[
            ('walk',  'walk',   [0, 1, 2, 3, 4, 5, 6, 7]),
            ('grab',  'attack', [0, 1, 2, 3, 4, 5, 6, 7]),
            ('kneel', 'kneel',  [0, 1, 2]),                  # 뒤로 주저앉기 전까지만
            ('death', 'death',  [0, 1, 2, 3, 4, 5, 6, 7]),
            ('guard', 'guard',  [2, 3]),
            ('run',   'run',    [0, 1, 2, 3, 4, 5, 6, 7]),
        ],
        lying={5, 6, 7}, lying_nape=(-13, -10), lying_from='right', blend={4: (3, 5)}),
    # 짐승 거인 (돌 던지는 거인 보스): 털북숭이 유인원 몸, 긴 팔, 짧은 뿔
    'beast': dict(
        src='giant_beast_src', out='giant_beast_px', height=86.0,
        head_box=(40, 19, 74, 47), nape_pt=(68, 40),
        rows=[
            ('walk',  'walk',    [0, 1, 2, 3, 4, 5, 6, 7]),
            ('grab',  'attack2', [0, 1, 2, 3, 4, 5, 6, 7]),
            ('kneel', 'kneel',   [0, 2, 3, 4]),
            ('death', 'death',   [0, 1, 2, 3, 4, 5, 6, 7]),
            ('guard', 'guard',   [1, 2]),
            ('run',   'run',     [0, 1, 2, 3, 4, 5, 6, 7]),
        ],
        lying={7}, lying_nape=(-13, -12), lying_from='right', blend={6: (5, 7)}),
}
GROUND_ROWS = {'death'}          # 바닥에 붙여 놓을 줄 (떠 있는 프레임을 내려서 무너지듯 쓰러지게)


def frame(src, folder, i):
    return Image.open(os.path.join(OUT, src, folder, 'west', 'frame_%03d.png' % i)).convert('RGBA')


def find_head(arr, tmpl):
    """본 머리와 가장 비슷한 위치 (왼쪽 위 좌표)"""
    th, tw = tmpl.shape[:2]
    ta = tmpl[..., 3:] / 255.0
    best, pos = None, (0, 0)
    for y in range(0, SRC_N - th + 1):
        for x in range(0, SRC_N - tw + 1):
            win = arr[y:y + th, x:x + tw]
            d = (np.abs(win[..., :3] - tmpl[..., :3]) * ta).sum() + np.abs(win[..., 3] - tmpl[..., 3]).sum()
            if best is None or d < best:
                best, pos = d, (x, y)
    return pos


def build(g):
    src, rows = g['src'], g['rows']
    x0, y0, x1, y1 = g['head_box']
    tmpl = np.asarray(frame(src, rows[0][1], rows[0][2][0]), dtype=float)[y0:y1, x0:x1]
    cols = max(len(p) for _, _, p in rows)
    sheet = Image.new('RGBA', (cols * CELL, len(rows) * CELL), (0, 0, 0, 0))
    meta = {'cell': CELL, 'cell_px': CELL, 'base': BASE, 'height': g['height'],
            'rows': [[name, len(p)] for name, _, p in rows], 'nape': {}}
    for r, (name, folder, picks) in enumerate(rows):
        napes = []
        for c, i in enumerate(picks):
            im = frame(src, folder, i)
            bb = im.getbbox()
            oy = OY + (FOOT - bb[3] if name in GROUND_ROWS else 0)
            sheet.alpha_composite(im, (c * CELL + OX, r * CELL + oy))
            if name == 'death' and i in g['lying'] and g.get('lying_from') == 'right':
                # 머리가 오른쪽에 누운 그림: 그림 오른쪽 아래에서 잰다
                nx, ny = bb[2] + g['lying_nape'][0], bb[3] + g['lying_nape'][1]
            elif name == 'death' and i in g['lying']:
                nx, ny = bb[0] + g['lying_nape'][0], bb[1] + g['lying_nape'][1]
            else:
                hx, hy = find_head(np.asarray(im, dtype=float), tmpl)
                nx, ny = g['nape_pt'][0] + hx - x0, g['nape_pt'][1] + hy - y0
            # 칸 가운데에서 x, 발 기준선에서 위로 y (그림 단위)
            napes.append([float(nx + OX - CELL / 2), float(CELL - BASE - (ny + oy))])
        meta['nape'][name] = napes
    d = meta['nape']['death']
    for k, (a, b) in g['blend'].items():
        t = (k - a) / (b - a)
        d[k] = [round(d[a][j] + (d[b][j] - d[a][j]) * t, 1) for j in range(2)]
    out = g['out']
    sheet.save(os.path.join(OUT, out + '.png'))
    a = np.asarray(sheet).copy()
    ink = a[..., :3].astype(int).sum(2) < 40
    a[~ink, :3] = 255
    Image.fromarray(a, 'RGBA').save(os.path.join(OUT, out + '_flash.png'))
    with open(os.path.join(OUT, out + '_meta.json'), 'w') as f:
        json.dump(meta, f, indent=1)
    print(out, sheet.size)
    for name, v in meta['nape'].items():
        print(' ', name, v)


def main():
    names = sys.argv[1:] or list(GIANTS)
    for n in names:
        build(GIANTS[n])


if __name__ == '__main__':
    main()
