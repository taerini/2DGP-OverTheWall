from pico2d import *

import camera
import game_framework
import play_mode
import render
from background import Background
from config import *

background = None
t = 0.0


def init():
    global background, t
    background = Background()
    camera.reset(SCREEN_W * 0.42 + 700)
    t = 0.0


def finish():
    pass


def pause():
    pass


def resume():
    pass


def handle_events():
    for event in get_events():
        if event.type == SDL_QUIT:
            game_framework.quit()
        elif event.type == SDL_KEYDOWN and event.key == SDLK_ESCAPE:
            game_framework.quit()
        elif t > 0.4 and (event.type == SDL_MOUSEBUTTONDOWN or
                          (event.type == SDL_KEYDOWN and event.key in (SDLK_SPACE, SDLK_RETURN))):
            game_framework.change_mode(play_mode)


def update():
    global t
    dt = game_framework.frame_time
    t += dt
    camera.x += 25 * dt
    background.update(dt)


def draw():
    clear_canvas()
    background.draw_back()
    background.draw_terrain()
    background.draw_front()
    render.rect(0, 0, SCREEN_W, SCREEN_H, (0, 0, 0), 70)
    a = min(1.0, t)
    render.text('벽 너머', SCREEN_W / 2, 470, 84, (245, 242, 232), 'center', FONT_TITLE, a)
    render.text('와이어로 날아 거인의 목덜미를 베고, 적 요새를 함락하라', SCREEN_W / 2, 390, 20, (225, 228, 228), 'center', alpha=a)
    lines = ['마우스 위치: 그쪽으로 달리기 (멀수록 빠름)',
             '클릭: 클릭한 높이·방향의 가장 가까운 나무에 와이어 (가스 소모)',
             'Q 베기: 거인의 목 높이 층에서 베면 목덜미(100%), 발 높이 층에서 베면 발목(30%, 주저앉음)',
             '강화 카드로 W 회오리 베기를 얻으면 거인의 목 높이까지 솟아올라 벤다',
             '우리 벽이 무너지면 패배, 적 요새 내구도 0 이면 승리']
    for i, s in enumerate(lines):
        render.text(s, SCREEN_W / 2, 310 - i * 30, 16, (210, 214, 214), 'center', alpha=a * 0.9)
    if t > 0.4:
        render.text('클릭하여 출격', SCREEN_W / 2, 130, 22, (255, 255, 255), 'center', alpha=0.55 + 0.45 * abs((t % 2) - 1))
    update_canvas()
