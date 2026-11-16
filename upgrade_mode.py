from pico2d import *

import game_framework
import play_mode
import render
import upgrade
from config import *

CARD_W, CARD_H = 300, 190
choices = []
hover = -1
t = 0.0


def card_rect(i):
    x = SCREEN_W / 2 + (i - 1) * (CARD_W + 30) - CARD_W / 2
    y = SCREEN_H / 2 - CARD_H / 2 - 20
    return x, y, x + CARD_W, y + CARD_H


def init():
    global choices, hover, t
    choices = upgrade.roll()
    hover = -1
    t = 0.0


def finish():
    pass


def pause():
    pass


def resume():
    pass


def choose(i):
    if 0 <= i < len(choices) and t > 0.25:
        upgrade.apply(choices[i])
        play_mode.hud.show_message(f'{choices[i][0]}: {choices[i][1]}', 2.0)
        game_framework.pop_mode()


def pick_at(x, y):
    for i in range(len(choices)):
        l, b, r, tp = card_rect(i)
        if l <= x <= r and b <= y <= tp:
            return i
    return -1


def handle_events():
    global hover
    for event in get_events():
        if event.type == SDL_QUIT:
            game_framework.quit()
        elif event.type == SDL_KEYDOWN and event.key in (SDLK_1, SDLK_2, SDLK_3):
            choose(event.key - SDLK_1)
        elif event.type == SDL_MOUSEMOTION:
            hover = pick_at(event.x, SCREEN_H - 1 - event.y)
            play_mode.player.mouse = (event.x, SCREEN_H - 1 - event.y)
        elif event.type == SDL_MOUSEBUTTONDOWN and event.button == SDL_BUTTON_LEFT:
            choose(pick_at(event.x, SCREEN_H - 1 - event.y))


def update():
    global t
    t += game_framework.frame_time


def draw():
    clear_canvas()
    play_mode.render_scene()
    render.rect(0, 0, SCREEN_W, SCREEN_H, (0, 0, 0), 150)
    render.text('강화 선택', SCREEN_W / 2, 560, 34, (245, 240, 230), 'center', FONT_TITLE)
    render.text(f'처치 {play_mode.kills} · 1 · 2 · 3 키 또는 클릭', SCREEN_W / 2, 520, 16, (210, 210, 210), 'center')
    for i, (name, desc, _, _, _) in enumerate(choices):
        l, b, r, tp = card_rect(i)
        lift = 8 if i == hover else 0
        render.rect(l, b + lift, r, tp + lift, (22, 30, 26) if i == hover else (16, 18, 20), 235)
        render.rect(l, tp + lift - 4, r, tp + lift, (90, 160, 100), 255)
        render.text(str(i + 1), l + 22, tp + lift - 30, 20, (140, 210, 150))
        render.text(name, (l + r) / 2, tp + lift - 62, 24, (245, 245, 240), 'center')
        n = upgrade.taken.get(name, 0)
        if n:
            render.text(f'보유 {n}', r - 14, tp + lift - 30, 13, (170, 170, 170), 'right')
        # 설명은 두 줄까지 나눠 쓴다
        words, lines, cur = desc.split(' '), [], ''
        for w in words:
            if len(cur) + len(w) > 15 and cur:
                lines.append(cur)
                cur = w
            else:
                cur = (cur + ' ' + w).strip()
        lines.append(cur)
        for k, s in enumerate(lines[:4]):
            render.text(s, (l + r) / 2, b + lift + 96 - k * 24, 16, (205, 210, 205), 'center')
    update_canvas()
