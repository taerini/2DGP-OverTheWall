import math
import random

from pico2d import *

import camera
import effect
import game_framework
import game_world
import map_data
import render
import result_mode
import title_mode
import upgrade
import upgrade_mode
from background import Background
from config import *

player = None
wall = None
fortress = None
background = None
hud = None
cannons = 0
cart_list = []
kills = 0
upgrades_taken = 0
next_upgrade = 3
upgrade_gap = 4
pending_upgrades = 0
play_time = 0.0
end_t = None
spawn_t = {}
hitstop = 0.0       # 목덜미를 벨 때 잠깐 멈추는 시간
flash_t = 0.0       # 처치할 때 화면 번쩍임
visited = set()
bosses_spawned = set()


def giants():
    return game_world.objects(LAYER_GIANT)


def allies():
    """쓰러지지 않은 동료들"""
    return [a for a in game_world.objects(LAYER_ALLY) if a.alive()]


def carts():
    """부서지지 않은 수레 대포들"""
    return [c for c in cart_list if c.alive()]


def player_dead():
    return False


# ------------------------------------------------ 게임 사건
def on_giant_killed(g):
    global kills, next_upgrade, upgrade_gap, pending_upgrades
    kills += 1
    if kills >= next_upgrade:
        pending_upgrades += 1
        next_upgrade += upgrade_gap
        upgrade_gap += 1


def neck_juice(g, dmg, killed, face, big=True):
    """목덜미를 벴을 때의 타격감: 일섬, 큰 궤적, 핏빛 불꽃, 큰 숫자, 멈칫, 흔들림, 번쩍임"""
    global hitstop, flash_t
    nx, ny = g.nape()
    s = 1.0 if big else 0.55
    effect.add(effect.Streak(nx, ny, -0.6 * face, (280 + g.size * 0.25) * s, 22 * s))
    effect.add(effect.BigArc(nx, ny, (160 + g.size * 0.12) * s, face, -0.25))
    effect.add(effect.Spray(nx, ny, (0.0 if face > 0 else math.pi) - 0.35 * face, int(28 * s)))
    effect.damage_number(nx + 10 * face, ny + 60, dmg, g.crit, int(35 * s))
    if not big:
        return
    if killed:
        hitstop = max(hitstop, 0.16)
        flash_t = 0.12
        camera.shake(0.32, 11 + g.k)
    else:
        hitstop = max(hitstop, 0.075)
        camera.shake(0.16, 7)


def on_player_down():
    """주인공이 쓰러졌다: 생명은 하나뿐이라 그대로 패배"""
    global end_t
    if end_t is None:
        end_t = 2.0
        camera.shake(0.6)
        hud.show_message('쓰러졌다…', 2.0)
        result_mode.set_result(False, kills, upgrades_taken, play_time, 'dead')


# ------------------------------------------------ 거인 생성
# 구간별 일반 거인 크기(1~5) 비율. 이야기가 나아갈수록 조금씩 커진다.
# 크기 4 는 드물게만, 크기 5 는 보스만 쓴다 (큰 거인이 흔하면 보스가 보스 같지 않다)
SIZE_WEIGHTS = [
    (85, 15, 0, 0, 0),
    (65, 30, 5, 0, 0),
    (55, 32, 13, 0, 0),
    (48, 34, 16, 2, 0),
    (45, 34, 18, 3, 0),
    (42, 34, 20, 4, 0),
    (50, 32, 15, 3, 0),
    (40, 34, 21, 5, 0),
    (38, 34, 22, 6, 0),
]
MAX_ALIVE = 22      # 처음에 한 번에 살아 있는 일반 거인 수 (길이 다 막히지 않게)
SPAWN_RAMP = 300.0  # 이 시간(초)에 걸쳐 거인이 점점 늘어 처음의 SPAWN_MAX 배가 된다
SPAWN_MAX = 2.0


def spawn_mult():
    """거인 수 배율: 처음 1배 → SPAWN_RAMP 초 뒤 SPAWN_MAX 배"""
    return 1 + (SPAWN_MAX - 1) * min(1.0, play_time / SPAWN_RAMP)


def spawn(kind, x, k=None, lane=None, zone=None):
    """크기 k 거인을 x 에 낸다. k 가 없으면 zone(기본: x 가 있는 구간)의 비율로 고른다.
    층은 머리가 화면을 넘지 않는 층 중에서 무작위로 고른다."""
    from giant import Giant, KINDS, max_lane
    sizes = KINDS[kind]['size']
    if k is None:
        # 그 자리에 깔린 층 수보다 큰 거인은 내지 않는다 (층이 적은 초반엔 작은 거인 위주)
        floors = sum(1 for i in range(5) if any(x1 < x + 600 and x2 > x - 600 for x1, x2 in map_data.lanes[i]))
        weights = SIZE_WEIGHTS[zone_of(x) if zone is None else zone]
        allowed = [s for s in sizes if s <= floors and weights[s - 1] > 0] or [min(sizes)]
        k = random.choices(allowed, [weights[s - 1] or 1 for s in allowed])[0]
    lanes = [i for i in range(max_lane(k) + 1) if map_data.segment_at(i, x)]
    if lane not in lanes:
        lane = random.choice(lanes)
    # 체력은 플레이 시간이 아니라 이야기 진행(구간)에 따라 오른다. 맵이 길어도 후반이 지나치게 단단하지 않게
    z = zone_of(x) if zone is None else zone
    g = Giant(kind, x, lane, k, 1 + 0.12 * z)
    game_world.add_object(g, LAYER_GIANT)
    return g


def progress():
    """주인공이 들어가 본 가장 먼 구간"""
    return max(visited) if visited else 0


def spawn_boss(kind):
    g = spawn(kind, FORTRESS_X + 40, lane=0, zone=progress())
    hud.show_message(f'{g.boss}가 요새에서 나왔다! (크기 {g.k})', 3.0)


# 새로 나오는 거인 종류. 시간이 지날수록 다양해진다 (종류, 가중치, 나오기 시작하는 시간)
FORT_KINDS = [('normal', 40, 0), ('erratic', 20, 0), ('climber', 18, 60), ('swarm', 14, 120), ('armed', 30, 180)]


SPAWN_HIDE = 600.0  # 새 거인은 화면 오른쪽 끝에서 이만큼 더 바깥에 만든다 (생기는 모습이 안 보이게)


def spawn_x():
    """새 거인이 나올 자리: 주인공이 있는 구간의 다음 구간 시작점. 화면에 보이면 화면 밖으로 민다.
    마지막(요새) 구간이면 요새에서 나온다."""
    z = zone_of(player.x)
    fort = FORTRESS_X + 40
    if z >= ZONE_COUNT - 1:
        return fort
    x = max((z + 1) * ZONE_W, camera.x + SCREEN_W + SPAWN_HIDE)
    return min(x, fort)


def fort_spawn():
    kinds = [(k, w) for k, w, t in FORT_KINDS if play_time >= t]
    kind = random.choices([k for k, _ in kinds], [w for _, w in kinds])[0]
    x = spawn_x()
    # 크기는 요새가 아니라 주인공이 이야기를 얼마나 나아갔는지(들어가 본 가장 먼 구간)를 따른다
    z = progress()
    spawn(kind, x, lane=0, zone=z)
    if kind == 'swarm':
        for i in range(1, 3):
            spawn('swarm', x + i * 50, lane=0, zone=z)


def update_spawns(dt):
    alive = sum(1 for g in giants() if g.alive() and not g.boss and not g.waiting)
    near_fort = player.x > FORTRESS_X - 1600
    # 거인은 주인공이 있는 구간의 다음 구간 시작점(화면 밖)에서 나와 걸어온다. 시간이 지날수록 자주
    spawn_t['fort'] -= dt
    if spawn_t['fort'] <= 0:
        m = spawn_mult()
        spawn_t['fort'] = max(2.4, 5.5 - play_time * 0.015) * (0.6 if near_fort else 1.0) / m
        if alive < MAX_ALIVE * m:
            fort_spawn()

    # 구간에 처음 들어가면 이름을 띄우고 보스를 내보낸다
    z = zone_of(player.x)
    if z not in visited:
        visited.add(z)
        hud.show_banner(f'{z + 1}. {ZONES[z]["name"]}', ZONES[z]['story'])
        boss = ZONES[z].get('boss')
        if boss and boss not in bosses_spawned:
            bosses_spawned.add(boss)
            spawn_boss(boss)


# ------------------------------------------------ 모드
def init():
    global player, wall, fortress, background, hud, cannons
    global kills, upgrades_taken, next_upgrade, upgrade_gap, pending_upgrades, play_time, end_t, hitstop, flash_t
    from player import Player
    from wall import Wall
    from fortress import Fortress
    from ui import Hud
    game_world.clear()
    upgrade.reset()
    cannons = 0
    cart_list.clear()
    kills, upgrades_taken = 0, 0
    next_upgrade, upgrade_gap, pending_upgrades = 3, 4, 0
    play_time = 0.0
    end_t = None
    hitstop = flash_t = 0.0
    visited.clear()
    bosses_spawned.clear()
    spawn_t.clear()
    spawn_t['fort'] = 4.0

    background = Background()
    hud = Hud()
    wall = Wall()
    fortress = Fortress()
    player = Player()
    game_world.add_object(wall, LAYER_BUILDING)
    game_world.add_object(fortress, LAYER_BUILDING)
    game_world.add_object(player, LAYER_PLAYER)
    camera.reset(player.x)

    # 처음부터 구간마다 그 구간의 거인이 서 있다 (이후로는 다음 구간 시작점에서 나온다).
    # 주인공이 가까이 올 때까지 제자리에서 기다리므로, 시작하면 첫 구간의 작은 거인부터 만난다
    for x in (1100, 1700, 2400, 3200):
        spawn('normal' if x < 2000 else ZONES[0]['kind'], x, k=1).waiting = True
    # 뒤 구간일수록 미리 서 있는 거인이 많다 (2구간 3마리 → 마지막 앞 구간 6마리)
    for z in range(1, ZONE_COUNT - 1):
        n = round(3 + 3 * (z - 1) / max(1, ZONE_COUNT - 3))
        for i in range(n):
            x = z * ZONE_W + (i + 0.5) * ZONE_W / n + random.uniform(-150, 150)
            spawn(ZONES[z]['kind'], x).waiting = True


def finish():
    game_world.clear()


def pause():
    pass


def resume():
    pass


def handle_events():
    for event in get_events():
        if event.type == SDL_QUIT:
            game_framework.quit()
        elif event.type == SDL_KEYDOWN:
            if event.key == SDLK_ESCAPE:
                game_framework.change_mode(title_mode)
            elif player.dead:
                pass                                   # 쓰러진 뒤에는 조작하지 않는다
            elif event.key == SDLK_q:
                player.slash()
            elif event.key == SDLK_w:
                player.tornado()
        elif event.type == SDL_MOUSEMOTION:
            player.mouse = (event.x, SCREEN_H - 1 - event.y)
        elif event.type == SDL_MOUSEBUTTONDOWN and event.button == SDL_BUTTON_LEFT:
            player.mouse = (event.x, SCREEN_H - 1 - event.y)
            if end_t is None and not player.dead:
                player.fire_wire(*player.mouse)


def update():
    global play_time, end_t, pending_upgrades, upgrades_taken, hitstop, flash_t
    dt = game_framework.frame_time
    flash_t = max(0.0, flash_t - dt)
    if hitstop > 0:
        # 멈칫하는 동안 세상은 멈추고 화면만 흔들린다
        hitstop -= dt
        camera.update(player.x, dt)
        return
    if end_t is None:
        play_time += dt
        update_spawns(dt)
    game_world.update(dt)
    background.update(dt)
    hud.update(dt)
    camera.update(player.x, dt)

    if end_t is None:
        if fortress.hp <= 0:
            end_t = 2.5
            result_mode.set_result(True, kills, upgrades_taken, play_time)
        elif wall.hp <= 0:
            end_t = 2.0
            camera.shake(1.0)
            result_mode.set_result(False, kills, upgrades_taken, play_time)
        elif pending_upgrades > 0:
            pending_upgrades -= 1
            upgrades_taken += 1
            game_framework.push_mode(upgrade_mode)
    else:
        end_t -= dt
        if end_t <= 0:
            game_framework.change_mode(result_mode)


def render_scene():
    background.draw_back()
    # 거인 몸은 길 뒤에, 약점 표시는 길 앞에 그린다
    for g in giants():
        g.draw_body()
    background.draw_terrain()
    game_world.render()
    background.draw_front()
    if flash_t > 0:
        render.rect(0, 0, SCREEN_W, SCREEN_H, (255, 245, 235), 75 * flash_t / 0.12)
    hud.draw()


def draw():
    clear_canvas()
    render_scene()
    update_canvas()
