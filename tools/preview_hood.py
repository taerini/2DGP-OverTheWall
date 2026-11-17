"""시트 애니메이션 미리보기 (pico2d). 시트의 모든 동작을 한 화면에서 반복 재생한다. ESC 또는 창 닫기로 끝낸다.
실행: python tools/preview_hood.py                         (두건 주인공)
      python tools/preview_hood.py giant_basic 0.6 6        (기본 거인, 배율 0.6, 초당 6프레임)
"""
import json
import os
import sys

import pico2d
from sdl2 import SDL_SetRenderDrawColor
from pico2d import (SDL_KEYDOWN, SDL_QUIT, SDLK_ESCAPE, clear_canvas, close_canvas, delay,
                    get_events, load_font, load_image, open_canvas, update_canvas)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

NAME = sys.argv[1] if len(sys.argv) > 1 else 'hero_hood'
SHEET = f'resource/{NAME}.png'
META = f'resource/{NAME}_meta.json'
SCALE = float(sys.argv[2]) if len(sys.argv) > 2 else 3     # 화면에 키워서 보여줄 배율
FPS = float(sys.argv[3]) if len(sys.argv) > 3 else 12      # 애니메이션 속도 (초당 프레임)
COLS = 4          # 한 줄에 놓을 동작 수
NAMES = {'idle': '대기', 'run': '달리기', 'wire': '와이어 비행', 'air': '공중(상승·하강)',
         'slashQ': '목덜미 베기 Q', 'slashW': '발목 베기 W', 'spinE': '회전 베기 E', 'hit': '피격',
         'walk': '걷기', 'grab': '잡기', 'kneel': '주저앉기', 'death': '쓰러짐', 'guard': '목 가리기', 'throw': '돌 던지기'}

with open(META) as f:
    meta = json.load(f)
if isinstance(meta['cell'], list):
    CW, CH = meta['cell']
else:                                   # 거인 시트: cell 은 그림 단위, 실제 픽셀은 cell_px
    CW = CH = meta['cell_px']
ROWS = meta['rows']
GRID_W, GRID_H = int(CW * SCALE + 40), int(CH * SCALE + 50)
W, H = GRID_W * COLS, GRID_H * ((len(ROWS) + COLS - 1) // COLS)


def main():
    open_canvas(W, H)
    sheet = load_image(SHEET)
    font = load_font('C:/Windows/Fonts/malgunbd.ttf', 18)
    frame, running = 0, True
    while running:
        for e in get_events():
            if e.type == SDL_QUIT or (e.type == SDL_KEYDOWN and e.key == SDLK_ESCAPE):
                running = False
        SDL_SetRenderDrawColor(pico2d.pico2d.renderer, 205, 215, 225, 255)   # 검은 외곽선이 보이게 밝은 배경
        clear_canvas()
        for r, (name, n) in enumerate(ROWS):
            gx, gy = r % COLS, r // COLS
            x = GRID_W * (gx + 0.5)
            y = H - GRID_H * gy - GRID_H / 2 + 12
            bottom = (len(ROWS) - 1 - r) * CH        # pico2d 는 아래가 0
            sheet.clip_draw((frame % n) * CW, bottom, CW, CH, x, y, CW * SCALE, CH * SCALE)
            font.draw(x - 60, y - CH * SCALE / 2 - 8, NAMES.get(name, name), (40, 40, 40))
        update_canvas()
        frame += 1
        delay(1 / FPS)
    close_canvas()


if __name__ == '__main__':
    main()
