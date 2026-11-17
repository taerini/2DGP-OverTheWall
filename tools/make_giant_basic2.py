"""두 번째 기본 거인 시트 변환기.

받은 시트(resource/giant_basic2_src.png, 8열 6줄 격자, 왼쪽을 봄, 투명 배경)를 그대로 쓰고
게임 거인 시트 형식(128 단위 칸 = 320px, 발 기준선 4)에 맞춰 칸을 옮기고 목덜미 좌표를 찾는다.
  · 크기: 서 있을 때(걷기 첫 장) 키가 HEIGHT 단위가 되게 키운다
  · 위치: 가장 낮은 곳을 발 기준선에, 가로는 원래 칸 안 위치 그대로
  · 목덜미: 머리카락이 피부와 만나는 경계 중 등 쪽으로 가장 먼 점 (등 방향 = 머리→몸통 방향에 수직)

실행: python tools/make_giant_basic2.py
  →  resource/giant_basic2.png, resource/giant_basic2_flash.png, resource/giant_basic2_meta.json
(필요: pillow, numpy)
"""
import json
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'resource')
SRC = os.path.join(OUT, 'giant_basic2_src.png')

ROWS = [('walk', 8), ('grab', 4), ('kneel', 4), ('death', 8), ('guard', 2), ('run', 8)]
SRC_COLS, SRC_ROWS = 8, 6
CELL = 128
K = 2.5
CELL_PX = int(CELL * K)
BASE = 4
HEIGHT = 118.0


def hair_mask(a):
    """짙은 갈색 머리카락 (검은 선·피부·얼룩과 구분)"""
    r, g, b, al = [a[..., i].astype(int) for i in range(4)]
    mx = np.maximum(np.maximum(r, g), b)
    return (al > 200) & (mx >= 55) & (mx <= 112) & (r > g + 8) & (r + g + b < 250)


def largest_blob(m):
    """가장 큰 덩어리만 남긴다 (얼룩 같은 작은 조각 제거)"""
    img = Image.fromarray((m * 255).astype(np.uint8))
    ys, xs = np.nonzero(m)
    best, best_n = None, 0
    seen = np.zeros_like(m)
    for y, x in zip(ys[::25], xs[::25]):
        if seen[y, x]:
            continue
        t = img.copy()
        ImageDraw.floodfill(t, (int(x), int(y)), 128)
        blob = np.asarray(t) == 128
        seen |= blob
        if blob.sum() > best_n:
            best, best_n = blob, blob.sum()
    return best


def find_nape(a, back_view=False):
    op = a[..., 3] > 128
    hair = largest_blob(hair_mask(a))
    hy, hx = np.nonzero(hair)
    hc = np.array([hx.mean(), hy.mean()])
    by, bx = np.nonzero(op & ~hair)
    bc = np.array([bx.mean(), by.mean()])
    if back_view:                                    # 뒷모습: 머리카락 아래 가운데
        return float(hc[0]), float(hy.max())
    s = bc - hc
    s /= np.linalg.norm(s)
    back = np.array([s[1], -s[0]])                   # 왼쪽을 보는 그림에서 등 쪽 (서 있으면 오른쪽, 엎드리면 위쪽)
    # 머리카락 중 피부와 맞닿은 가장자리
    skin = op & ~hair & (a[..., :3].astype(int).sum(2) > 200)
    near_skin = np.asarray(Image.fromarray((skin * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(19))) > 0   # 사이에 검은 선이 있어 넉넉히
    ey, ex = np.nonzero(hair & near_skin)
    pts = np.stack([ex, ey], 1).astype(float)
    score = (pts - hc) @ back + 0.6 * ((pts - hc) @ s)
    p = pts[np.argmax(score)]
    return float(p[0]), float(p[1])


def main():
    src = Image.open(SRC).convert('RGBA')
    cw, ch = src.width / SRC_COLS, src.height / SRC_ROWS
    # 격자로 자르면 칸 경계를 넘은 손끝 등이 잘리므로, 시트 전체에서 그림 덩어리를 찾아
    # 덩어리 가운데가 속한 칸에 배정한다
    full = np.asarray(src)
    ma = ((full[..., 3] > 120) * 255).astype(np.uint8)     # 반투명 부스러기는 빼고 또렷한 부분으로 덩어리를 찾는다
    label = np.zeros(ma.shape, bool)
    owner = {}
    ys, xs = np.nonzero(ma[::9, ::9])                      # 9px 간격 씨앗만 보면 충분 (작은 부스러기는 저절로 빠짐)
    for y, x in zip(ys * 9, xs * 9):
        if label[y, x]:
            continue
        t = Image.fromarray(ma).copy()                     # 배열을 그대로 감싼 이미지는 채우기가 안 먹으므로 복사본에
        ImageDraw.floodfill(t, (int(x), int(y)), 128)
        blob = np.asarray(t) == 128
        label |= blob
        if blob.sum() < 200:
            continue
        by, bx = np.nonzero(blob)
        key = (int(by.mean() // ch), int(bx.mean() // cw))
        owner[key] = blob if key not in owner else (owner[key] | blob)
    # 덩어리 둘레의 부드러운 가장자리(반투명)까지 포함
    for key in owner:
        owner[key] = np.asarray(Image.fromarray((owner[key] * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5))) > 0
    cells = {}
    for r, (name, n) in enumerate(ROWS):
        for c in range(n):
            a = full.copy()
            a[~owner[(r, c)], 3] = 0
            img = Image.fromarray(a, 'RGBA')
            bb = img.getbbox()
            cells[name, c] = (img.crop(bb), bb[0] - (c + 0.5) * cw)   # 원래 칸 가운데에서 왼쪽 끝까지 거리
    # 크기: 걷기 첫 장의 키를 HEIGHT 단위로
    a0 = np.asarray(cells['walk', 0][0])[..., 3] > 128
    ys = np.nonzero(a0.any(1))[0]
    f = HEIGHT * K / (ys[-1] - ys[0] + 1)

    sheet = Image.new('RGBA', (max(n for _, n in ROWS) * CELL_PX, len(ROWS) * CELL_PX))
    check = Image.new('RGBA', sheet.size, (205, 215, 225, 255))
    meta = {'cell': CELL, 'cell_px': CELL_PX, 'base': BASE, 'height': HEIGHT, 'rows': [[r, n] for r, n in ROWS],
            'nape': {}}
    for r, (name, n) in enumerate(ROWS):
        napes = []
        for c in range(n):
            img, left = cells[name, c]
            img = img.resize((round(img.width * f), round(img.height * f)), Image.LANCZOS)
            a = np.asarray(img)
            op = a[..., 3] > 60
            ys = np.nonzero(op.any(1))[0]
            ox = round(CELL_PX / 2 + left * f)                     # 가로: 원래 칸 안 위치 그대로
            oy = round(CELL_PX - BASE * K - 1 - ys[-1])            # 세로: 가장 낮은 곳을 발 기준선에
            cell = Image.new('RGBA', (CELL_PX, CELL_PX))
            cell.paste(img, (ox, oy), img)
            nx, ny = find_nape(np.asarray(cell), back_view=(name == 'guard'))
            # 단위 좌표: 칸 가운데 기준 가로, 발 기준선 기준 높이 (왼쪽을 보는 시트 그대로라 뒤집지 않는다)
            napes.append([round((nx - CELL_PX / 2) / K, 1), round((CELL_PX - BASE * K - ny) / K, 1)])
            sheet.alpha_composite(cell, (c * CELL_PX, r * CELL_PX))
            check.alpha_composite(cell, (c * CELL_PX, r * CELL_PX))
            d = ImageDraw.Draw(check)
            x, y = c * CELL_PX + nx, r * CELL_PX + ny
            d.ellipse((x - 7, y - 7, x + 7, y + 7), outline=(0, 160, 255), width=4)
        meta['nape'][name] = napes
    sheet.save(os.path.join(OUT, 'giant_basic2.png'))
    a = np.asarray(sheet).copy()
    light = a[..., :3].astype(int).sum(2) > 160
    a[light, :3] = 255
    Image.fromarray(a, 'RGBA').save(os.path.join(OUT, 'giant_basic2_flash.png'))
    with open(os.path.join(OUT, 'giant_basic2_meta.json'), 'w') as fp:
        json.dump(meta, fp, indent=1)
    check.save(os.path.join(ROOT, 'docs', 'giant_basic2_nape_check.png'))
    print('saved giant_basic2.png', sheet.size, 'scale', round(f, 2))


if __name__ == '__main__':
    main()
