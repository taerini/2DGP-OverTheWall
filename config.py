SCREEN_W, SCREEN_H = 1280, 720

# 맵: 구간 9개 (이야기 흐름 순서), 왼쪽 끝은 우리 벽, 오른쪽 끝은 적 요새
ZONE_W = 4000               # 구간 하나의 길이. 달리고 날아도 한 구간에 한참 머물게
# 길 5줄 (윗면 y)
LANE_GAP = 115
LANE_Y = [70 + LANE_GAP * i for i in range(5)]
ANCHOR_H = 100               # 길에서 와이어 거는 점까지 높이 (가장 높게)
ANCHOR_LOW = 30              # 가장 낮게. 이 사이에서 클릭한 높이에 건다

GRAVITY = 1500.0

FONT_UI = 'C:/Windows/Fonts/malgunbd.ttf'
FONT_TITLE = 'C:/Windows/Fonts/HANBatangB.ttf'

# 오브젝트 레이어
LAYER_BUILDING, LAYER_GIANT, LAYER_ALLY, LAYER_PLAYER, LAYER_PROJECTILE, LAYER_EFFECT = range(6)

# 구간 = 이야기의 한 장면. 오른쪽으로 갈수록 이야기가 나아간다.
#   bg: 배경 그림 번호 (sky_N / far_N / mid_N), prop: 와이어 지점 그림, fx: 떠다니는 입자 움직임
#   rim · skin · particle · fog: 림 라이트, 거인 피부, 입자, 안개 색
#   gap: 와이어 지점 간격, kind: 처음부터 서 있는 거인 종류, boss: 처음 들어가면 요새에서 나오는 보스
#   story: 처음 들어갈 때 띄우는 한 줄, rest: 쉬어 가는 구간 (가스가 빨리 찬다)
ZONES = [
    dict(name='벽 밖 들판', bg=1, prop='pine', fx='dust', shafts=True,
         rim=(225, 232, 234), skin=(232, 222, 205), particle=(245, 245, 245), fog=(205, 214, 214),
         gap=(430, 620), kind='erratic', story='성문이 열렸다. 넓은 들판 너머, 거인들이 걸어온다'),
    dict(name='거목의 숲', bg=2, prop='bigtree', fx='firefly', shafts=True,
         rim=(170, 225, 140), skin=(176, 196, 168), particle=(200, 255, 120), fog=(80, 120, 92),
         gap=(190, 290), kind='normal', boss='smart', story='건물만 한 나무 사이를 날아라. 영리한 거인이 뒤쫓는다'),
    dict(name='달밤의 고성', bg=3, prop='tower', fx='cold', moon=True,
         rim=(150, 182, 255), skin=(170, 180, 214), particle=(190, 210, 255), fog=(80, 96, 140),
         gap=(290, 400), kind='climber', boss='thrower', story='무너진 성에 갇혔다. 성벽을 타고 거인이 오른다'),
    dict(name='무너진 벽 아래', bg=6, prop='pillar', fx='dust',
         rim=(236, 230, 214), skin=(228, 214, 196), particle=(240, 236, 226), fog=(196, 204, 212),
         gap=(320, 460), kind='armed', story='벽이 뚫렸다. 단단한 거인이 무너진 틈으로 들어온다'),
    dict(name='노을 평야', bg=7, prop='pine', fx='dust',
         rim=(255, 186, 140), skin=(226, 176, 150), particle=(255, 210, 170), fog=(170, 110, 110),
         gap=(360, 520), kind='swarm', story='빼앗긴 동료를 되찾으러 해 지는 평야를 달린다'),
    dict(name='불타는 마을', bg=4, prop='chimney', fx='ember',
         rim=(255, 150, 80), skin=(214, 150, 122), particle=(255, 170, 70), fog=(160, 84, 56),
         gap=(250, 360), kind='swarm', boss='colossal', story='밤새 행군해 되찾은 마을이 불탄다. 거대한 거인이 깨어난다'),
    dict(name='처음 본 바다', bg=8, prop='post', fx='sand', rest=True,
         rim=(244, 240, 220), skin=(232, 222, 205), particle=(255, 255, 250), fog=(200, 222, 236),
         gap=(300, 420), kind='normal', story='벽 밖의 끝, 바다다. 잠시 숨을 고르자 (가스가 빨리 찬다)'),
    dict(name='바다 너머 공업 도시', bg=5, prop='crane', fx='ash',
         rim=(185, 168, 205), skin=(180, 174, 190), particle=(205, 195, 195), fog=(100, 92, 112),
         gap=(270, 380), kind='armed', story='바다를 건넜다. 불빛이 꺼지지 않는 적의 도시'),
    dict(name='항구 요새', bg=9, prop='crane', fx='ash',
         rim=(226, 196, 160), skin=(200, 180, 160), particle=(220, 200, 170), fog=(150, 128, 104),
         gap=(260, 360), kind='armed', story='끝없이 행진하는 거인 무리 너머, 요새를 함락하라'),
]
ZONE_COUNT = len(ZONES)
MAP_W = ZONE_W * ZONE_COUNT
WALL_X = 150                 # 우리 벽 오른쪽 면
FORTRESS_X = MAP_W - 310     # 적 요새 왼쪽 면


def zone_of(x):
    return max(0, min(ZONE_COUNT - 1, int(x // ZONE_W)))


def zone_weights(x, band=600):
    """구간 경계 근처에서는 두 구간을 섞는다. [(구간, 비율), ...]"""
    b = round(x / ZONE_W) * ZONE_W
    t = (x - b) / band + 0.5
    if 0 < b < MAP_W and 0.0 < t < 1.0:
        t = t * t * (3 - 2 * t)
        return [(int(b // ZONE_W) - 1, 1.0 - t), (int(b // ZONE_W), t)]
    return [(zone_of(x), 1.0)]


def zone_color(x, key):
    r = g = b = 0.0
    for z, w in zone_weights(x):
        c = ZONES[z][key]
        r += c[0] * w
        g += c[1] * w
        b += c[2] * w
    return int(r), int(g), int(b)

DANGER = (255, 50, 40)       # 거인 공격이 들어올 자리를 칠하는 색

SLASH_REACH = 85.0           # Q 판정을 거인 몸 폭보다 이만큼 더 넓게 봐준다
