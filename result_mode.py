from pico2d import *

import game_framework
import render
import title_mode
from config import *

win = False
reason = 'wall'          # 졌을 때 이유: 'wall' 벽이 무너짐, 'dead' 주인공이 쓰러짐
kills = 0
upgrades = 0
seconds = 0.0
t = 0.0


def set_result(victory, k, u, s, why='wall'):
    global win, kills, upgrades, seconds, reason
    win, kills, upgrades, seconds, reason = victory, k, u, s, why


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
        elif t > 1.8 and (event.type == SDL_MOUSEBUTTONDOWN or
                          (event.type == SDL_KEYDOWN and event.key in (SDLK_SPACE, SDLK_RETURN, SDLK_ESCAPE))):
            game_framework.change_mode(title_mode)


def update():
    global t
    t += game_framework.frame_time


TEXT = (244, 240, 230)
SUB = (170, 172, 176)
ARROW = ['#...', '##..', '###.', '####', '###.', '##..', '#...']   # 타이틀 화면과 같은 작은 화살표


def fade(start, dur=0.6):
    return max(0.0, min(1.0, (t - start) / dur))


def draw():
    # 플레이 화면이 어둠으로 끝나므로 어두운 바탕에서 글자만 차례로 떠오른다
    clear_canvas()
    render.rect(0, 0, SCREEN_W, SCREEN_H, (10, 10, 13), 255)
    cx = SCREEN_W / 2
    if win:
        title, sub, col = '적 요새 함락', '거인의 근원을 끊어냈다', (240, 214, 150)
    elif reason == 'dead':
        title, sub, col = '쓰러졌다', '다시 일어나지 못했다', (226, 120, 104)
    else:
        title, sub, col = '벽이 무너졌다', '거인이 벽 안으로 쏟아져 들어온다', (226, 120, 104)
    render.text(title, cx, 470, 66, col, 'center', FONT_TITLE, fade(0.2, 1.0))   # 66 = 갈무리11 굵게 6배
    render.text(sub, cx, 400, 18, SUB, 'center', alpha=fade(0.8), shadow=False)
    # 기록: 이름은 흐리게 오른쪽 정렬, 값은 밝게 왼쪽 정렬
    s = int(seconds)
    rows = [('처치한 거인', f'{kills}'), ('강화 횟수', f'{upgrades}'), ('걸린 시간', f'{s // 60:02d}:{s % 60:02d}')]
    a = fade(1.2)
    render.rect(cx - 160, 337, cx + 160, 338, (80, 80, 88), 255 * a)
    for i, (k, v) in enumerate(rows):
        y = 300 - i * 40
        render.text(k, cx - 16, y, 18, SUB, 'right', alpha=a, shadow=False)
        render.text(v, cx + 16, y, 22, TEXT, alpha=a, shadow=False)
    # 돌아가기 안내 (타이틀 화면과 같은 모양)
    if t > 1.8:
        a = fade(1.8)
        y = 120
        render.text('클릭하여 타이틀로', cx, y, 18, TEXT, 'center', alpha=a, shadow=False)
        nudge = 5 * abs((t % 1.0) * 2 - 1)
        render.pixel_map(ARROW, cx - 112 - nudge, y - 10, 3, {'#': TEXT}, 255 * a)
        render.pixel_map([r[::-1] for r in ARROW], cx + 100 + nudge, y - 10, 3, {'#': TEXT}, 255 * a)
    update_canvas()
