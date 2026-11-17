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
import sound
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
farthest_x = 0.0    # 주인공이 가 본 가장 먼 곳 (새로 나오는 거인 크기를 정한다)
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
    sound.sfx('slash_crit')
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


DEATH_FADE = (0.5, 2.2)     # 쓰러진 뒤 (이만큼 지나서, 이 시간 동안) 화면이 점점 어두워진다
DEATH_END = 3.3             # 쓰러진 뒤 결과 화면으로 넘어가기까지 (어두워진 뒤 잠깐 머문다)


def on_player_down():
    """주인공이 쓰러졌다: 생명은 하나뿐이라 그대로 패배. 뒤로 넘어가는 동안 화면이 점점 어두워진다"""
    global end_t, hitstop
    if end_t is None:
        end_t = DEATH_END
        hitstop = max(hitstop, 0.15)       # 마지막 한 방에 잠깐 멈칫
        camera.shake(0.6)
        result_mode.set_result(False, kills, upgrades_taken, play_time, 'dead')


def death_dark():
    """쓰러진 뒤 화면을 덮는 어둠 (0~1)"""
    if not player.dead:
        return 0.0
    k = max(0.0, min(1.0, (player.death_t - DEATH_FADE[0]) / DEATH_FADE[1]))
    return k * k * (3 - 2 * k)


# ------------------------------------------------ 거인 생성
# 일반 거인 크기(1~5) 비율. 맵을 나아갈수록(맵 길이를 아래 줄 수로 나눈 단계마다) 조금씩 커진다.
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
PRESET_GAP = 1300.0  # 처음부터 서 있는 거인 사이 거리
MAX_ALIVE = 22      # 처음에 한 번에 살아 있는 일반 거인 수 (길이 다 막히지 않게)
SPAWN_RAMP = 300.0  # 이 시간(초)에 걸쳐 거인이 점점 늘어 처음의 SPAWN_MAX 배가 된다
SPAWN_MAX = 2.0


def spawn_mult():
    """거인 수 배율: 처음 1배 → SPAWN_RAMP 초 뒤 SPAWN_MAX 배"""
    return 1 + (SPAWN_MAX - 1) * min(1.0, play_time / SPAWN_RAMP)


def size_stage(x):
    """x 까지 나아갔을 때 쓰는 SIZE_WEIGHTS 줄"""
    return max(0, min(len(SIZE_WEIGHTS) - 1, int(x / MAP_W * len(SIZE_WEIGHTS))))


def spawn(kind, x, k=None, lane=None, zone=None):
    """크기 k 거인을 x 에 낸다. k 가 없으면 zone(기본: x 가 있는 구간)의 비율로 고른다.
    층은 머리가 화면을 넘지 않는 층 중에서 무작위로 고른다."""
    from giant import Giant, KINDS, max_lane
    sizes = KINDS[kind]['size']
    if k is None:
        # 그 자리에 깔린 층 수보다 큰 거인은 내지 않는다 (층이 적은 초반엔 작은 거인 위주)
        floors = sum(1 for i in range(5) if any(x1 < x + 600 and x2 > x - 600 for x1, x2 in map_data.lanes[i]))
        weights = SIZE_WEIGHTS[size_stage(x if zone is None else farthest_x)]
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


def josa_i(word):
    """받침이 있으면 '이', 없으면 '가'"""
    c = ord(word[-1]) - 0xAC00
    return '이' if 0 <= c < 11172 and c % 28 else '가'


def spawn_boss(kind, x=None):
    g = spawn(kind, FORTRESS_X + 40 if x is None else x, lane=0, zone=progress())
    g.waiting = False
    hud.show_message(f'{g.boss}{josa_i(g.boss)} 요새에서 나왔다!', 3.0)


# 새로 나오는 거인 종류. 시간이 지날수록 다양해진다 (종류, 가중치, 나오기 시작하는 시간)
FORT_KINDS = [('normal', 40, 0), ('erratic', 20, 0), ('climber', 18, 60), ('swarm', 14, 120), ('armed', 30, 180)]


# 시작 장면 시간표 (초)
INTRO_PAN = 2.2            # 성벽을 가득 보여 주던 카메라가 오른쪽으로 옮겨 간다
INTRO_GATE = (2.3, 3.8)    # 성문 쇠창살이 올라간다
INTRO_WALK = 3.3           # 주인공이 성벽 속에서 달려 나오기 시작 (성문이 2/3쯤 열렸을 때)
INTRO_START_X = WALL_X - 100   # 주인공 처음 자리: 성문 뒤 성벽 속 (벽에 가려 안 보이고, 달려서 나온다)
INTRO_RUN = 2.4            # 성벽 밖으로 달려 나가는 시간 (멈추지 않고 달리던 그대로 조작을 넘겨받는다)
INTRO_END = INTRO_WALK + INTRO_RUN   # 조작 시작 (클릭하면 건너뛴다)
INTRO_CAM_FROM = -1200.0   # 처음 카메라 위치: 성벽이 화면을 가득 채운다
INTRO_WALK_TO = WALL_X + 2000  # 달려가는 목표: 시작 장면 안에는 닿지 않을 만큼 멀리 (그래서 줄곧 같은 속도로 달린다)
INTRO_SKIP_X = WALL_X + 150    # 건너뛰었을 때 주인공 자리
intro_t = 0.0

SPAWN_HIDE = (600.0, 2000.0)   # 새 거인은 화면 오른쪽 끝에서 이만큼 더 바깥에 만든다 (생기는 모습이 안 보이게)


def spawn_x():
    """새 거인이 나올 자리: 화면 오른쪽 바깥 조금 앞. 요새보다 멀리는 가지 않는다."""
    x = camera.x + SCREEN_W + random.uniform(*SPAWN_HIDE)
    return min(x, FORTRESS_X + 40)


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

    global farthest_x
    farthest_x = max(farthest_x, player.x)
    # 구간에 처음 들어가면 이름을 띄우고 보스를 내보낸다
    z = zone_of(player.x)
    if z not in visited:
        visited.add(z)
        hud.show_banner(ZONES[z]['name'])
    # 구간 보스: 들어가자마자 요새에서 나오거나, boss_at 만큼 들어가면 화면 오른쪽 바깥에서 나온다
    info = ZONES[z]
    boss = info.get('boss')
    if boss and boss not in bosses_spawned:
        at = info.get('boss_at')
        if at is None:
            bosses_spawned.add(boss)
            spawn_boss(boss)
        elif player.x >= (z + at) * ZONE_W:
            bosses_spawned.add(boss)
            spawn_boss(boss, min(camera.x + SCREEN_W + 260, FORTRESS_X))   # 화면 오른쪽 바로 바깥


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
    global farthest_x
    farthest_x = 0.0
    spawn_t.clear()
    spawn_t['fort'] = 4.0       # 시작 장면이 끝난 뒤 이만큼 지나야 첫 거인이 나온다
    global intro_t
    intro_t = 0.0

    background = Background()
    hud = Hud()
    wall = Wall()
    fortress = Fortress()
    player = Player()
    player.x = INTRO_START_X            # 성벽 속에서 기다리다 문이 열리면 달려 나온다
    player.hidden = False
    player.auto_x = INTRO_START_X       # 문이 열릴 때까지 마우스를 따라가지 않고 성벽 속에 가만히 있는다
    game_world.add_object(wall, LAYER_BUILDING)
    game_world.add_object(fortress, LAYER_BUILDING)
    game_world.add_object(player, LAYER_PLAYER)
    camera.x = INTRO_CAM_FROM

    # 처음부터 길 곳곳에 그 구간의 거인이 서 있다 (이후로는 화면 오른쪽 바깥에서 나온다).
    # 주인공이 가까이 올 때까지 제자리에서 기다리므로, 시작하면 첫 구간의 작은 거인부터 만난다
    for x in (3000, 3600, 4300, 5000):
        spawn('normal' if x < 3800 else ZONES[0]['kind'], x, k=1).waiting = True
    # 그 뒤로는 PRESET_GAP 마다 하나씩, 요새 앞까지. 뒤로 갈수록 조금 더 빽빽하다
    x = 5400.0
    while x < FORTRESS_X - 1500:
        x += PRESET_GAP * random.uniform(0.75, 1.25) * (1 - 0.35 * x / MAP_W)
        spawn(ZONES[zone_of(x)]['kind'], x).waiting = True


def finish():
    game_world.clear()


def pause():
    pass


def resume():
    pass


def in_intro():
    return intro_t < INTRO_END


def skip_intro():
    global intro_t
    intro_t = INTRO_END


def handle_events():
    for event in get_events():
        if event.type == SDL_QUIT:
            game_framework.quit()
        elif in_intro():
            if event.type == SDL_KEYDOWN and event.key == SDLK_ESCAPE:
                game_framework.change_mode(title_mode)
            elif event.type == SDL_MOUSEBUTTONDOWN or (event.type == SDL_KEYDOWN and event.key in (SDLK_SPACE, SDLK_RETURN)):
                skip_intro()
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


def update_intro(dt):
    """시작 장면: 카메라가 성벽에서 오른쪽으로 → 성문이 열리고 → 주인공이 걸어 나온다"""
    global intro_t
    intro_t += dt
    if intro_t < INTRO_PAN:
        k = intro_t / INTRO_PAN
        k = k * k * (3 - 2 * k)
        camera.x = INTRO_CAM_FROM + (camera.MIN_X - INTRO_CAM_FROM) * k
    else:
        camera.update(player.x, dt)                     # 다 옮겨 간 뒤로는 달려 나가는 주인공을 따라간다
    g0, g1 = INTRO_GATE
    was = wall.gate_open
    wall.gate_open = max(0.0, min(1.0, (intro_t - g0) / (g1 - g0)))
    if was <= 0 < wall.gate_open:
        camera.shake(g1 - g0, 2.5)                     # 쇠창살이 올라가는 동안 땅이 웅웅 울린다
        sound.sfx('gate_open')
    if intro_t >= INTRO_WALK:
        player.auto_x = INTRO_WALK_TO
    background.update(dt)
    game_world.update(dt)
    if intro_t >= INTRO_END:                            # 끝 (또는 건너뜀): 문은 활짝, 주인공은 밖으로, 조작 시작
        wall.gate_open = 1.0
        player.hidden, player.auto_x = False, None
        player.x = max(player.x, INTRO_SKIP_X)
        # 달리던 속도는 그대로 두고, 마우스를 조금 앞에 둔 것으로 쳐서 스르르 멈추게 한다 (마우스를 움직이면 그쪽으로)
        player.mouse = camera.to_screen(player.x + 60, LANE_Y[2])


def update():
    global play_time, end_t, pending_upgrades, upgrades_taken, hitstop, flash_t
    dt = game_framework.frame_time
    if in_intro():
        update_intro(dt)
        return
    if player.auto_x is not None:                       # 건너뛴 직후 한 번 정리
        update_intro(0.0)
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
    if in_intro():
        wall.draw()                     # 시작 장면: 성벽·성문을 주인공 위에 덮어, 벽 앞면 밖으로 나온 만큼만 보이게
    background.draw_front()
    if flash_t > 0:
        render.rect(0, 0, SCREEN_W, SCREEN_H, (255, 245, 235), 75 * flash_t / 0.12)
    if not in_intro():
        hud.draw()
    elif intro_t > 1.0:
        a = min(1.0, (intro_t - 1.0) / 0.5)
        render.text('클릭하면 건너뛰기', SCREEN_W - 24, 28, 14, (220, 220, 220), 'right', alpha=0.7 * a, shadow=False)
    dark = death_dark()
    if dark > 0:
        render.rect(0, 0, SCREEN_W, SCREEN_H, (0, 0, 0), 255 * dark)


def draw():
    clear_canvas()
    render_scene()
    update_canvas()
