from pico2d import *

import game_framework
import play_mode
import render
import upgrade
from config import *

CARD_W, CARD_H = 280, 300
U = 4                    # 카드 픽셀 크기

# 카드 종류: 이름에 들어간 말로 고른다 → (종류 색, 아이콘)
KINDS = [
    (('칼날',), (214, 74, 66), 'sword'),
    (('가스',), (96, 170, 230), 'gas'),
    (('와이어',), (110, 200, 200), 'hook'),
    (('동료',), (110, 170, 96), 'ally'),
    (('대포',), (226, 150, 70), 'cannon'),
    (('벽',), (160, 160, 168), 'wall'),
    (('회오리',), (176, 130, 236), 'swirl'),
    (('붕대',), (232, 110, 140), 'heart'),
]
ICON_COLORS = {'K': (20, 18, 24), 'W': (245, 242, 232), 'Y': (230, 190, 80), 'B': (120, 190, 240),
               'G': (110, 170, 96), 'R': (226, 66, 66), 'P': (190, 140, 255), 'O': (226, 150, 70),
               'S': (160, 160, 168), 'D': (90, 90, 100), 'M': (138, 140, 150)}
ICONS = {   # 8×8 픽셀 아이콘
    'sword':  ['.......W', '......WW', '.....WW.', '....WW..', 'Y..WW...', '.YWW....', '..YY....', '.Y.Y....'],
    'gas':    ['...KK...', '..KWWK..', '.KBBBBK.', '.KBWBBK.', '.KBBBBK.', '.KBBBBK.', '.KBBBBK.', '..KKKK..'],
    'hook':   ['...WWWW.', '..W....W', '..W.....', '..W.....', '..W.....', 'W.W.....', '.WW.....', '..W.....'],
    'ally':   ['..GGGG..', '.GGGGGG.', '.GKKKKG.', '.GKKKKG.', '..GGGG..', '.GGGGGG.', 'GGGGGGGG', 'GGGGGGGG'],
    'cannon': ['........', '......MM', '....MMMM', '..MMMMM.', '.MMMMM..', 'MOOM....', 'OWWO....', '.OO.....'],
    'wall':   ['S.S..S.S', 'SSSSSSSS', 'SDSSSDSS', 'SSSSSSSS', 'SSDSSSDS', 'SSSSSSSS', 'SDSSKKSS', 'SSSSKKSS'],
    'swirl':  ['..PPPP..', '.P....P.', 'P..PP..P', 'P.P..P.P', 'P.P.P..P', 'P..P..P.', '.P...P..', '..PPP...'],
    'heart':  ['.RR..RR.', 'RWRRRRRR', 'RRRRRRRR', 'RRRRRRRR', '.RRRRRR.', '..RRRR..', '...RR...', '........'],
}


def kind_of(name):
    for words, col, icon in KINDS:
        if any(w in name for w in words):
            return col, icon
    return (200, 200, 200), 'sword'


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
    render.rect(0, 0, SCREEN_W, SCREEN_H, (0, 0, 0), 160)
    render.text('강화 선택', SCREEN_W / 2, 600, 34, (245, 240, 230), 'center', FONT_TITLE)
    render.text('1 · 2 · 3 키 또는 클릭', SCREEN_W / 2, 562, 15, (200, 200, 200), 'center')
    for i, (name, desc, _, _, _) in enumerate(choices):
        draw_card(i, name, desc)
    update_canvas()


def draw_card(i, name, desc):
    l, b, r, tp = card_rect(i)
    hot = i == hover
    pop = min(1.0, max(0.0, (t - i * 0.06) / 0.18))          # 차례로 아래에서 솟아오른다
    lift = (8 if hot else 0) - (1 - pop) * 40
    b, tp = b + lift, tp + lift
    col, icon = kind_of(name)
    accent = render.shade(col, 40) if hot else col
    render.pixel_frame(l, b, r, tp, (30, 28, 38) if not hot else (38, 36, 50), accent, U, 255 * pop)
    # 위쪽 이름 띠 (종류 색)
    render.rect(l + 4 * U, tp - 16 * U, r - 4 * U, tp - 4 * U, render.shade(col, -40), 255 * pop)
    render.rect(l + 4 * U, tp - 5 * U, r - 4 * U, tp - 4 * U, render.shade(col, 10), 255 * pop)
    render.text(name, (l + r) / 2, tp - 10 * U, 21, (250, 248, 240), 'center', alpha=pop)
    # 가운데 아이콘 (검은 받침 위)
    cx, cy = (l + r) / 2, tp - 32 * U
    render.rect(cx - 9 * U, cy - 9 * U, cx + 9 * U, cy + 9 * U, (14, 12, 18), 255 * pop)
    render.rect(cx - 8 * U, cy - 8 * U, cx + 8 * U, cy + 8 * U, (22, 20, 30), 255 * pop)
    bob = 2 if hot and int(t * 4) % 2 else 0
    render.pixel_map(ICONS[icon], cx - 4 * 2 * U, cy - 4 * 2 * U + bob, 2 * U,
                     ICON_COLORS, 255 * pop)
    # 설명 (세 줄까지)
    words, lines, cur = desc.split(' '), [], ''
    for w in words:
        if len(cur) + len(w) > 14 and cur:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + ' ' + w).strip()
    lines.append(cur)
    for k, s in enumerate(lines[:3]):
        render.text(s, (l + r) / 2, b + 30 * U - k * 22 - 22, 15, (214, 214, 206), 'center', alpha=pop)
    # 아래 왼쪽 숫자 키, 아래 오른쪽 보유 수
    kx, ky = l + 5 * U, b + 5 * U
    render.rect(kx, ky, kx + 9 * 2, ky + 11 * 2, (14, 12, 18), 255 * pop)
    render.rect(kx + 2, ky + 2, kx + 16, ky + 20, render.shade(col, 30), 255 * pop)
    render.pixel_glyph(str(i + 1), kx + 4, ky + 4, 2, (20, 18, 24), 255 * pop)
    n = upgrade.taken.get(name, 0)
    if n:
        render.text(f'보유 {n}', r - 6 * U, b + 9 * U, 13, (180, 180, 180), 'right', alpha=pop)
