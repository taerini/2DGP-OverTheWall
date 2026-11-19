"""테스트 창: 동작을 빠르게 확인하는 작은 무대.
실행: python main.py test

- 길 2층 (층마다 나무 2그루), 주인공 하나, 2m 거인 하나
- 거인은 제자리에 서서 TEST_ATTACK_GAP 초마다 한 번 휘두른다. 쓰러지면 잠시 뒤 다시 나온다
- 주인공은 맞아도 체력이 줄지 않고, 회오리 베기(W)도 처음부터 쓸 수 있다
조작은 본 게임과 같다: 클릭 와이어, Q 베기, W 회오리, R 거인 다시, ESC 나가기
"""
from pico2d import *

import camera
import game_framework
import game_world
import map_data
import play_mode
import render
import sound
import title_mode
from config import *
from giant import Giant, GRAB_TIME

TEST_X0 = 1200               # 무대 왼쪽 끝 (성벽이 보이지 않을 만큼 오른쪽)
TEST_W = 1400                # 무대 폭: 주인공은 이 안에서만 움직인다
TEST_LANE1 = (TEST_X0 + 250, TEST_X0 + 1050)            # 2층 길
TEST_TREES = {0: (TEST_X0 + 300, TEST_X0 + 800),       # 층마다 나무 2그루
              1: (TEST_X0 + 400, TEST_X0 + 900)}
TEST_GIANT_X = TEST_X0 + 1150
TEST_GIANT_SIZE = 2
TEST_ATTACK_GAP = 5.0        # 거인이 휘두르는 간격 (초)
TEST_RESPAWN = 2.5           # 거인이 쓰러진 뒤 다시 나오기까지 (초)

giant = None
attack_t = TEST_ATTACK_GAP
respawn_t = 0.0


def build_map():
    """map_data 를 작은 2층 무대로 바꾼다 (나갈 때 map_data.build() 로 되돌린다)"""
    map_data.lanes[:] = [[(0, MAP_W)], [TEST_LANE1]] + [[] for _ in range(FLOORS - 2)]
    map_data.anchors[:] = [[(x, LANE_Y[i], 0) for x in TEST_TREES.get(i, ())] for i in range(FLOORS)]


def spawn_giant():
    global giant, attack_t
    giant = Giant('normal', TEST_GIANT_X, 0, TEST_GIANT_SIZE)
    giant.start_swat = lambda warn: None      # 목 뒤 반격은 끈다: 휘두르기는 정해진 간격에만
    game_world.add_object(giant, LAYER_GIANT)
    attack_t = TEST_ATTACK_GAP


def init():
    global respawn_t
    play_mode.init()                          # 본 게임 무대를 그대로 만든 뒤
    for g in list(play_mode.giants()):        # 미리 서 있는 거인은 치운다
        game_world.remove_object(g)
    play_mode.skip_intro()
    play_mode.wall.gate_open = 1.0
    build_map()
    p = play_mode.player
    p.x, p.y, p.lane = TEST_X0 + 150.0, float(LANE_Y[0]), 0
    p.hidden, p.auto_x = False, None
    p.has_tornado = True
    p.mouse = camera.to_screen(p.x + 60, LANE_Y[1])
    camera.reset(p.x)
    respawn_t = 0.0
    spawn_giant()


def finish():
    game_world.clear()
    map_data.build()                          # 본 게임 맵으로 되돌린다


def pause():
    pass


def resume():
    pass


def handle_events():
    """본 게임과 같은 조작 + R 로 거인 다시 내기"""
    p = play_mode.player
    for event in get_events():
        if event.type == SDL_QUIT:
            game_framework.quit()
        elif event.type == SDL_KEYDOWN:
            if event.key == SDLK_ESCAPE:
                game_framework.change_mode(title_mode)
            elif event.key == SDLK_r:
                if giant is not None and giant in play_mode.giants():
                    game_world.remove_object(giant)
                spawn_giant()
            elif event.key == SDLK_q:
                p.slash()
            elif event.key == SDLK_w:
                p.tornado()
        elif event.type == SDL_MOUSEMOTION:
            p.mouse = (event.x, SCREEN_H - 1 - event.y)
        elif event.type == SDL_MOUSEBUTTONDOWN and event.button == SDL_BUTTON_LEFT:
            p.mouse = (event.x, SCREEN_H - 1 - event.y)
            p.fire_wire(*p.mouse)


def update_giant(dt):
    global attack_t, respawn_t, giant
    if giant is None or giant.state == 'dead':
        respawn_t += dt
        if respawn_t >= TEST_RESPAWN:
            respawn_t = 0.0
            if giant is not None and giant in play_mode.giants():
                game_world.remove_object(giant)
            spawn_giant()
        return
    p = play_mode.player
    giant.waiting = False
    giant.x = TEST_GIANT_X                    # 제자리에 서 있는다
    giant.grab_cd = giant.swat_cd = 99.0      # 스스로는 공격하지 않는다
    if giant.state == 'walk':
        giant.dir = 1 if p.x > giant.x else -1
    attack_t -= dt
    if attack_t <= 0:
        attack_t = TEST_ATTACK_GAP
        if giant.state == 'walk' and giant.kneel_t <= 0:
            giant.state, giant.state_t = 'grab', GRAB_TIME
            giant.grabbed = False
            sound.sfx_at('giant_attack', giant.x)


def update():
    dt = game_framework.frame_time
    p = play_mode.player
    p.hp = p.max_hp                           # 테스트: 맞아도 쓰러지지 않는다
    play_mode.flash_t = max(0.0, play_mode.flash_t - dt)
    if play_mode.hitstop > 0:
        play_mode.hitstop -= dt
        camera.update(p.x, dt)
        return
    update_giant(dt)
    game_world.update(dt)
    if giant is not None and giant.state != 'dead':
        giant.x = TEST_GIANT_X                # 걷거나 쫓아가도 제자리로
    play_mode.background.update(dt)
    play_mode.hud.update(dt)
    p.x = max(TEST_X0, min(TEST_X0 + TEST_W, p.x))
    camera.update(p.x, dt)


def draw():
    clear_canvas()
    play_mode.render_scene()
    render.text('테스트 창   클릭 와이어 · Q 베기 · W 회오리 · R 거인 다시 · ESC 나가기',
                SCREEN_W // 2, SCREEN_H - 24, 14, (255, 255, 255), 'center')
    if giant is not None and giant.state != 'dead':
        render.text(f'거인 공격까지 {max(0.0, attack_t):.1f}초', SCREEN_W // 2, SCREEN_H - 46, 14, (255, 210, 190), 'center')
    update_canvas()
