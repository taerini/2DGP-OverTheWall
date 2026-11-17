from pico2d import *

import camera
import game_framework
import play_mode
import render
import sound
from background import Background
from config import *

background = None
t = 0.0


def init():
    global background, t
    background = Background()
    camera.reset(SCREEN_W * 0.42 + 700)
    t = 0.0
    sound.play_bgm('title')     # 차분하지만 불안한 곡. 플레이에 들어가도 끊지 않고 이어서 흐른다


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


TEXT = (244, 240, 230)
SUB = (196, 200, 200)
KEY_U = 3                       # 키캡 픽셀 크기 (20칸 → 60px)
# 마우스 그림 (7×9). L 은 눌린 왼쪽 버튼
MOUSE = ['.#####.', '#LL#..#', '#LL#..#', '#######', '#.....#', '#.....#', '#.....#', '#.....#', '.#####.']
CONTROLS = [('mouse', '달리기'), ('click', '와이어'), ('Q', '베기'), ('W', '회오리')]
ARROW = ['#...', '##..', '###.', '####', '###.', '##..', '#...']   # 오른쪽을 가리키는 작은 화살표 (4×7)


def fade(start, dur=0.5):
    """t 가 start 부터 dur 동안 0 → 1"""
    return max(0.0, min(1.0, (t - start) / dur))


def draw_key(cx, y, kind, label, a):
    """키캡 하나와 아래 이름. cx 는 가운데, y 는 키캡 아래"""
    w = 20 * KEY_U
    x = cx - w / 2
    if kind in ('mouse', 'click'):
        render.pixel_key(x, y, ' ', True, u=KEY_U, alpha=a)
        ink = {'#': (30, 28, 36), 'L': (214, 84, 70) if kind == 'click' else (30, 28, 36)}
        if kind == 'mouse':
            ink['L'] = None
        render.pixel_map(MOUSE, x + 6 * KEY_U, y + 7 * KEY_U, KEY_U, {k: v for k, v in ink.items() if v}, 255 * a)
    else:
        render.pixel_key(x, y, kind, True, u=KEY_U, alpha=a)
    render.text(label, cx, y - 20, 16, SUB, 'center', alpha=a, shadow=False)


def draw():
    clear_canvas()
    background.draw_back()
    background.draw_terrain()
    background.draw_front()
    # 글자 뒤만 살짝 어둡게: 가운데 띠가 가장 진하고 위아래로 옅어진다
    render.rect(0, 0, SCREEN_W, SCREEN_H, (0, 0, 0), 40)
    for k in range(12):
        render.rect(0, 150 + k * 8, SCREEN_W, 570 - k * 8, (8, 10, 14), 14)
    cx = SCREEN_W / 2
    # 제목
    a = fade(0.0, 0.8)
    render.pixel_number('OVER THE WALL', cx, 470, 9, TEXT, 255 * a)
    # 조작: 키캡 네 개
    a = fade(0.4)
    gap = 150
    for i, (kind, label) in enumerate(CONTROLS):
        draw_key(cx + (i - 1.5) * gap, 288, kind, label, a)
    # 시작 안내: 상자 없이 글자만, 양옆 픽셀 화살표가 글자 쪽으로 까딱인다
    if t > 0.8:
        a = fade(0.8)
        y = 132
        render.text('클릭하여 출격', cx, y, 20, TEXT, 'center', alpha=a)
        nudge = 5 * abs((t % 1.0) * 2 - 1)    # 0 → 5 → 0: 글자 쪽으로 다가갔다 물러난다
        render.pixel_map(ARROW, cx - 104 - nudge, y - 10, 3, {'#': TEXT}, 255 * a)
        render.pixel_map([r[::-1] for r in ARROW], cx + 92 + nudge, y - 10, 3, {'#': TEXT}, 255 * a)
    update_canvas()
