import random

import game_world
import play_mode
from ally import Levi, Mikasa
from cannon import Cannon, CartCannon
from config import LAYER_ALLY, LAYER_BUILDING


def blade(p):
    p.blade += 0.15      # 곱하기로 불어나지 않게 더한다 (9장 = 2.35배)


def gas_save(p):
    p.gas_cost *= 0.75


def gas_tank(p):
    p.gas_max += 35
    p.gas = p.gas_max


def wire(p):
    p.reel_mult *= 1.3
    p.reach += 150


MAX_ALLIES = 4


def ally_count():
    return len(game_world.objects(LAYER_ALLY))


def add_allies(cls, n):
    for _ in range(n):
        if ally_count() >= MAX_ALLIES:
            break
        game_world.add_object(cls(ally_count()), LAYER_ALLY)


def levi(p):
    add_allies(Levi, 1)


def mikasa(p):
    add_allies(Mikasa, 1)


def ally_heal(p):
    for a in game_world.objects(LAYER_ALLY):
        a.heal(2)


def cannon(p):
    game_world.add_object(Cannon(play_mode.cannons), LAYER_BUILDING)
    play_mode.cannons += 1


def cart(p):
    c = CartCannon(len(play_mode.cart_list))
    play_mode.cart_list.append(c)
    game_world.add_object(c, LAYER_BUILDING)


def repair(p):
    play_mode.wall.repair(35)


def tornado(p):
    p.has_tornado = True


def bandage(p):
    p.max_hp += 10
    p.hp = p.max_hp


def has_allies():
    return ally_count() > 0


def room(n):
    return lambda: ally_count() + n <= MAX_ALLIES


def unique(cls):
    """한 명뿐인 동료: 자리가 있고 아직 데려오지 않았을 때만 카드가 나온다"""
    return lambda: ally_count() + 1 <= MAX_ALLIES and not any(type(a) is cls for a in game_world.objects(LAYER_ALLY))


# (이름, 설명, 적용 함수, 최대 횟수, 나올 조건)
UPGRADES = [
    ('칼날 강화', '공격력 +15%', blade, 9, None),
    ('가스 절약', '와이어 가스 소모 -25%', gas_save, 3, None),
    ('가스통 확장', '최대 가스 +35, 가득 채움', gas_tank, 5, None),
    ('와이어 강화', '감는 속도 +30%, 사거리 +150', wire, 4, None),
    ('동료: 리바이', '작은 거인의 목덜미를 벤다. 큰 거인은 발목을 베어 주저앉힌다', levi, 1, unique(Levi)),
    ('동료: 미카사', '목 높이로 돌진하며 작은 거인을 최대 3마리 벤다', mikasa, 1, unique(Mikasa)),
    ('동료 치료', '모든 동료 체력 회복, 최대 체력 +2, 후퇴한 동료 즉시 복귀', ally_heal, 3, has_allies),
    ('성 대포', '우리 벽 위에 대포 1문. 벽에 가까운 거인을 자동 포격', cannon, 4, None),
    ('수레 대포', '전장으로 밀고 나가 거인을 쏘고, 끝내 적 요새를 포격한다', cart, 3, None),
    ('벽 보수', '우리 벽 내구도 +35', repair, 99, None),
    ('회오리 베기 (W)', '거인 발목 앞에서 목 높이까지 회오리처럼 솟아올라 목덜미를 벤다', tornado, 1, None),
    ('붕대', '체력 모두 회복, 최대 체력 +10', bandage, 2, None),
]

taken = {}


def reset():
    taken.clear()


def roll():
    pool = [u for u in UPGRADES if taken.get(u[0], 0) < u[3] and (u[4] is None or u[4]())]
    return random.sample(pool, min(3, len(pool)))


def apply(u):
    taken[u[0]] = taken.get(u[0], 0) + 1
    u[2](play_mode.player)
