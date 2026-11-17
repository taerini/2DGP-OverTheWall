"""선 그림 스타일 시험 장면 보기 (게임 코드와 따로 돈다).

먼저 python tools/make_line_test.py 로 그림을 만든 뒤 실행한다.
  python tools/line_test_view.py
조작: ← → 카메라 이동 (가만두면 천천히 오른쪽으로 흐른다), SPACE 멈춤, ESC 끝
"""
import json
import os
import time

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pico2d import *
from sdl2 import SDL_SetHint

SCREEN_W, SCREEN_H = 1280, 720
LANE_Y = [70 + 115 * i for i in range(5)]
BG_W = 2560
DIR = 'resource/line_test/'
# 층마다 발판을 놓는 x 위치 (시험용 고정 배치, BG_W 마다 되풀이)
LEDGES = {1: (120, 820, 1500, 2100), 2: (420, 1180, 1880), 3: (60, 760, 1460, 2200), 4: (380, 1080, 1840)}
LEDGE_TOP = 8            # 발판 그림 위 끝에서 이끼 윗면까지
GROUND_TOP = 14          # 땅 그림 위 끝에서 이끼 윗면까지


class Giant:
    def __init__(self, x, lane, scale, speed, phase):
        self.x, self.lane, self.scale, self.speed, self.t = x, lane, scale, speed, phase

    def update(self, dt):
        self.t += dt
        self.x -= self.speed * dt
        if self.x < cam_x - 400:                       # 화면 왼쪽으로 사라지면 오른쪽에서 다시 나온다
            self.x = cam_x + SCREEN_W + 300

    def draw(self):
        f = int(self.t * 8 * self.speed / 60) % meta['frames']
        w, h = meta['frame_w'], meta['frame_h']
        dw, dh = w * self.scale, h * self.scale
        y = LANE_Y[self.lane] - meta['foot_pad'] * self.scale
        sheet.clip_draw_to_origin(f * w, 0, w, h, self.x - cam_x - dw / 2, y, dw, dh)


def tile(img, parallax, y):
    off = -(cam_x * parallax) % BG_W
    img.draw_to_origin(off - BG_W, y)
    img.draw_to_origin(off, y)


def draw_scene():
    clear_canvas()
    sky.draw_to_origin(0, 0)
    tile(far, 0.12, 0)
    tile(mid, 0.4, 0)
    tile(ground, 1.0, LANE_Y[0] - (ground.h - GROUND_TOP))
    for g in giants:                                   # 거인은 발판보다 뒤 (발판 사이로 몸이 보인다)
        g.draw()
    for lane, xs in LEDGES.items():
        for x in xs:
            for rep in (-BG_W, 0, BG_W):
                sx = x + rep - (cam_x % BG_W)
                if -ledge.w < sx < SCREEN_W:
                    ledge.draw_to_origin(sx, LANE_Y[lane] - (ledge.h - LEDGE_TOP))
    update_canvas()


open_canvas(SCREEN_W, SCREEN_H, sync=True)
hide_lattice()
SDL_SetHint(b'SDL_RENDER_SCALE_QUALITY', b'1')     # 줄였을 때 부드럽게
sky, far, mid = load_image(DIR + 'sky.png'), load_image(DIR + 'far.png'), load_image(DIR + 'mid.png')
ledge, ground = load_image(DIR + 'ledge.png'), load_image(DIR + 'ground.png')
sheet = load_image(DIR + 'giant_walk.png')
with open(DIR + 'giant_walk_meta.json') as f:
    meta = json.load(f)

cam_x = 0.0
giants = [Giant(900, 0, 1.0, 34, 0.0), Giant(1250, 1, 0.62, 48, 0.4), Giant(520, 2, 0.45, 60, 0.9)]
running, paused, move = True, False, 0
last = time.time()
while running:
    for e in get_events():
        if e.type == SDL_QUIT or (e.type == SDL_KEYDOWN and e.key == SDLK_ESCAPE):
            running = False
        elif e.type == SDL_KEYDOWN and e.key == SDLK_SPACE:
            paused = not paused
        elif e.type == SDL_KEYDOWN and e.key in (SDLK_LEFT, SDLK_RIGHT):
            move = -1 if e.key == SDLK_LEFT else 1
        elif e.type == SDL_KEYUP and e.key in (SDLK_LEFT, SDLK_RIGHT):
            move = 0
    now = time.time()
    dt, last = min(now - last, 1 / 30), now
    if not paused:
        cam_x += (move * 600 + (40 if move == 0 else 0)) * dt
        for g in giants:
            g.update(dt)
    draw_scene()
close_canvas()
