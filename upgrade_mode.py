from pico2d import *

import game_framework
import play_mode
import render
import upgrade
from config import *

CARD_W, CARD_H = 240, 300
CARD_GAP = 28
ICON_U = 6               # 아이콘 한 칸 크기 (8칸 → 48px)

# 카드 종류: 이름에 들어간 말로 고른다 → (분류 이름, 종류 색, 아이콘)
KINDS = [
    (('칼날',), '공격', (232, 96, 84), 'sword'),
    (('회오리',), '공격', (186, 146, 246), 'swirl'),
    (('가스',), '기동', (110, 184, 240), 'gas'),
    (('와이어',), '기동', (110, 210, 200), 'hook'),
    (('동료',), '동료', (130, 196, 110), 'ally'),
    (('대포',), '지원', (236, 164, 84), 'cannon'),
    (('벽',), '방어', (176, 176, 186), 'wall'),
    (('붕대',), '회복', (240, 124, 152), 'heart'),
]
CARD_BODY = (16, 17, 22)         # 반투명 몸통
CARD_LINE = (200, 202, 212)      # 얇은 테두리 (흐리게)
TEXT_MAIN = (246, 244, 238)
TEXT_SUB = (176, 178, 184)
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
    for words, label, col, icon in KINDS:
        if any(w in name for w in words):
            return label, col, icon
    return '강화', (200, 200, 200), 'sword'


def outline(l, b, r, tp, col, a, w=1):
    """속이 빈 사각형 테두리"""
    render.rect(l, tp - w, r, tp, col, a)
    render.rect(l, b, r, b + w, col, a)
    render.rect(l, b, l + w, tp, col, a)
    render.rect(r - w, b, r, tp, col, a)


choices = []
hover = -1
t = 0.0


def card_rect(i):
    x = SCREEN_W / 2 + (i - 1) * (CARD_W + CARD_GAP) - CARD_W / 2
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
    lift = (6 if hot else 0) - (1 - pop) * 30
    b, tp = b + lift, tp + lift
    a = 255 * pop
    label, col, icon = kind_of(name)
    cx = (l + r) / 2
    # 몸통: 반투명 판 + 1px 테두리. 마우스를 올리면 종류 색 테두리
    render.rect(l, b, r, tp, render.shade(CARD_BODY, 8) if hot else CARD_BODY, 242 * pop)
    if hot:
        outline(l, b, r, tp, col, a, 2)
    else:
        outline(l, b, r, tp, CARD_LINE, 60 * pop)
    # 위: 분류(종류 색)와 보유 수
    render.text(label, l + 18, tp - 24, 13, col, 'left', alpha=pop, shadow=False)
    n = upgrade.taken.get(name, 0)
    if n:
        render.text(f'보유 {n}', r - 18, tp - 24, 13, TEXT_SUB, 'right', alpha=pop, shadow=False)
    # 아이콘: 받침 없이, 종류 색 옅은 바탕 위에
    cy = tp - 92
    render.rect(cx - 38, cy - 38, cx + 38, cy + 38, col, 28 * pop)
    bob = 2 if hot and int(t * 4) % 2 else 0
    render.pixel_map(ICONS[icon], cx - 4 * ICON_U, cy - 4 * ICON_U + bob, ICON_U, ICON_COLORS, a)
    # 이름과 짧은 구분선
    render.text(name, cx, tp - 156, 20, TEXT_MAIN, 'center', alpha=pop, shadow=False)
    render.rect(cx - 14, tp - 176, cx + 14, tp - 174, col, 200 * pop)
    # 설명 (세 줄까지)
    words, lines, cur = desc.split(' '), [], ''
    for w in words:
        if len(cur) + len(w) > 13 and cur:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + ' ' + w).strip()
    lines.append(cur)
    for k, s in enumerate(lines[:3]):
        render.text(s, cx, tp - 198 - k * 20, 14, TEXT_SUB, 'center', alpha=pop, shadow=False)
    # 아래 가운데 숫자 키: 얇은 테두리만
    kx, ky = cx - 11, b + 12
    outline(kx, ky, kx + 22, ky + 24, col if hot else CARD_LINE, (200 if hot else 90) * pop)
    render.pixel_glyph(str(i + 1), kx + 6, ky + 5, 2, col if hot else TEXT_SUB, a)
