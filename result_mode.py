from pico2d import *

import game_framework
import render
import title_mode
from config import *

win = False
kills = 0
upgrades = 0
seconds = 0.0
t = 0.0


def set_result(victory, k, u, s):
    global win, kills, upgrades, seconds
    win, kills, upgrades, seconds = victory, k, u, s


def init():
    global t
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
        elif t > 1.0 and (event.type == SDL_MOUSEBUTTONDOWN or
                          (event.type == SDL_KEYDOWN and event.key in (SDLK_SPACE, SDLK_RETURN, SDLK_ESCAPE))):
            game_framework.change_mode(title_mode)


def update():
    global t
    t += game_framework.frame_time


def draw():
    clear_canvas()
    sky = render.image('sky_5.png' if win else 'sky_4.png')
    sky.opacify(1.0)
    sky.draw_to_origin(0, 0, SCREEN_W, SCREEN_H)
    a = min(1.0, t)
    title = '적 요새 함락' if win else '벽이 무너졌다'
    sub = '거인의 근원을 끊어냈다.' if win else '거인이 벽 안으로 쏟아져 들어온다…'
    render.text(title, SCREEN_W / 2, 480, 60, (245, 236, 220) if win else (240, 150, 130), 'center', FONT_TITLE, a)
    render.text(sub, SCREEN_W / 2, 410, 20, (210, 210, 210), 'center', alpha=a)
    s = int(seconds)
    rows = [('처치한 거인', f'{kills}'), ('강화 횟수', f'{upgrades}'), ('걸린 시간', f'{s // 60:02d}:{s % 60:02d}')]
    for i, (k, v) in enumerate(rows):
        y = 330 - i * 40
        render.text(k, SCREEN_W / 2 - 20, y, 20, (200, 200, 200), 'right', alpha=a)
        render.text(v, SCREEN_W / 2 + 20, y, 22, (255, 255, 255), alpha=a)
    if t > 1.0:
        render.text('클릭하여 타이틀로', SCREEN_W / 2, 150, 18, (190, 190, 190), 'center', alpha=0.6 + 0.4 * abs((t % 2) - 1))
    vig = render.image('vignette.png')
    vig.draw_to_origin(0, 0, SCREEN_W, SCREEN_H)
    update_canvas()
