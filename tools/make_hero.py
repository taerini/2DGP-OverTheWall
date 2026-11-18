"""PixelLab 주인공(애니메이션풍 128px) 시트 합치기.

PixelLab 에서 만든 캐릭터의 오른쪽(east) 동작 프레임을 resource/hero/src/<동작>/east/ 에 받아 두고,
줄마다 쓸 프레임을 골라 한 장으로 붙인다. 프레임 캔버스(172×172)를 그대로 한 칸으로 쓰므로
모든 프레임의 발 위치가 처음부터 맞아 있다.
- 줄마다 프레임 수가 다르다 (부드럽게 보이도록 대부분 16장). 줄 이름·프레임 수는 meta 에 적는다.
- 눈: PixelLab 이 그린 형광 초록을 차분한 청록으로 바꾼다 (EYE_*).

실행: python tools/make_hero.py
  →  resource/hero/hero.png, resource/hero/hero_meta.json
(필요: pillow)
"""
import colorsys
import json
import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'resource', 'hero')
SRC = os.path.join(OUT, 'src')
CELL = 172

# 줄: (시트 줄 이름, PixelLab 동작 폴더, 쓸 프레임 번호들). 줄 순서는 player.ROWS 와 같다
R = range
RUN = list(R(3, 13))
ROWS = [
    ('run',    'run',           RUN),             # 정확히 한 걸음 주기(두 발) 10장: 12번 다음이 3번과 이어진다
    ('slash',  'run_slash',     list(R(1, 17))),             # 달리는 보폭 그대로 칼을 앞으로 휘두른다
    ('wire_slash', 'wire_slash', list(R(1, 17))),            # 와이어로 날며 몸을 활처럼 젖혔다가 칼을 크게 내리친다
    ('wire',   'wire_fly',      list(R(1, 16))),             # 0번은 몸을 눕히는 중
    ('air',    'air_jump',      list(R(1, 9)) + list(R(9, 16)) + [15]),   # 앞 8장 상승, 뒤 8장 하강
    ('spinE',  'spin_attack',   list(R(5, 16))),             # 앞쪽은 회전 전 자세
    ('hit',    'hit_knockback', list(R(12))),
    ('death',  'death',         list(R(16))),
    ('curve',  'curve',         list(R(1, 17))),             # 달리던 그대로 다리를 굴리며 앞모습을 지나 반대쪽으로 도는 커브
    ('launch', 'launch',        list(R(1, 13))),             # 와이어 출발: 앞 7장 웅크리기, 뒤 5장 튀어 오르기
    ('fall',   'fall',          list(R(1, 13))),             # 빠르게 떨어지는 중 (반복)
    ('land',   'land',          list(R(2, 11))),             # 세게 착지해 깊이 웅크렸다 일어나기
]
# 시작·끝 자세를 지정해 만든 동작은 캔버스가 달라서 다른 프레임과 맞도록 옮긴다 (첫 장과 원본 자세를 비교한 값)
ALIGN = {'run_slash': (-34, 0), 'wire_slash': (-36, -18), 'curve': (-4, -2), 'launch': (-6, -12), 'fall': (0, -8), 'land': (0, -12)}
ONLY_BODY = {'launch'}       # 몸과 떨어진 먼지 덩어리를 지운다

# 눈: 형광 초록 → 청록. 밝기에 따라 어두운 청록 ~ 밝은 청록 사이로
EYE_DARK = (52, 98, 96)
EYE_LIGHT = (126, 184, 174)


def fix_eyes(im):
    px = im.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = px[x, y]
            if not a or g <= r + 50 or g <= b + 30:
                continue
            h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
            if s < 0.5 or v < 0.45:          # 망토의 어두운 초록은 건드리지 않는다
                continue
            t = max(0.0, min(1.0, (v - 0.45) / 0.45))
            px[x, y] = tuple(int(EYE_DARK[i] + (EYE_LIGHT[i] - EYE_DARK[i]) * t) for i in range(3)) + (a,)
    return im


def only_body(im):
    """이어져 있는 덩어리 중 가장 큰 것(몸)만 남긴다"""
    px = im.load()
    seen, best = set(), []
    for y in range(im.height):
        for x in range(im.width):
            if (x, y) in seen or not px[x, y][3]:
                continue
            seen.add((x, y))
            todo, part = [(x, y)], []
            while todo:
                cx, cy = todo.pop()
                part.append((cx, cy))
                for nx in range(max(0, cx - 1), min(im.width, cx + 2)):
                    for ny in range(max(0, cy - 1), min(im.height, cy + 2)):
                        if (nx, ny) not in seen and px[nx, ny][3]:
                            seen.add((nx, ny))
                            todo.append((nx, ny))
            if len(part) > len(best):
                best = part
    out = Image.new('RGBA', im.size, (0, 0, 0, 0))
    for p in best:
        out.putpixel(p, px[p])
    return out


def frame(folder, i):
    im = Image.open(os.path.join(SRC, folder, 'east', 'frame_%03d.png' % i)).convert('RGBA')
    if folder in ONLY_BODY:
        im = only_body(im)
    if folder in ALIGN:
        dx, dy = ALIGN[folder]
        cell = Image.new('RGBA', (CELL, CELL), (0, 0, 0, 0))
        cell.paste(im, (dx, dy))
        return cell
    return im


def main():
    n_max = max(len(f) for _, _, f in ROWS)
    sheet = Image.new('RGBA', (CELL * n_max, CELL * len(ROWS)), (0, 0, 0, 0))
    for r, (name, folder, frames) in enumerate(ROWS):
        for c, i in enumerate(frames):
            sheet.alpha_composite(fix_eyes(frame(folder, i)), (c * CELL, r * CELL))
    # 발바닥: 서 있는 자세(idle 0번)의 그림 맨 아래
    feet = frame('idle', 0).getbbox()[3]
    meta = dict(cell=[CELL, CELL], base=CELL - feet, height=feet - frame('idle', 0).getbbox()[1],
                rows=[[name, len(frames)] for name, _, frames in ROWS])
    sheet.save(os.path.join(OUT, 'hero.png'))
    with open(os.path.join(OUT, 'hero_meta.json'), 'w') as f:
        json.dump(meta, f, indent=1)
    print('saved hero/hero.png', sheet.size, meta)


if __name__ == '__main__':
    main()
