SCREEN_W, SCREEN_H = 1280, 720

# 맵: 구간들 (이야기 흐름 순서), 왼쪽 끝은 우리 벽, 오른쪽 끝은 적 요새
MAP_LEN = 36000              # 맵 전체 길이 (구간 수와 상관없이 같다)
# 길 6줄 (윗면 y)
FLOORS = 6
TOP_FLOOR = FLOORS - 1
LANE_BASE = 110              # 맨 아래 길 높이. 맨 위층 위 공간이 다른 층과 비슷하게 남도록 올렸다
LANE_GAP = 100
LANE_Y = [LANE_BASE + LANE_GAP * i for i in range(FLOORS)]
GROUND_FILL = (43, 22, 30)      # 맨 아래 땅 그림 밑을 채우는 색
ANCHOR_H = 87               # 길에서 와이어 거는 점까지 높이 (가장 높게)
ANCHOR_LOW = 30              # 가장 낮게. 이 사이에서 클릭한 높이에 건다

GRAVITY = 1500.0

HERO_HEIGHT = 56              # 주인공이 서 있을 때 화면에서의 키 (px)
HERO_STRIDE = 150.0           # 달리기 그림 한 바퀴(두 걸음)에 나아가는 거리: 발 움직임이 실제 속도와 맞는다
HERO_TURN_TIME = 0.3          # 느리게 달리다 방향을 바꿀 때 달리면서 앞모습을 지나 도는 시간 (초)
HERO_JOG = 70.0               # 가장 느린 달리기 속도: 주인공은 서 있지 않고, 목표 바로 앞까지 천천히 달린다
HERO_CURVE_SPEED = 230.0      # 이 속도 이상으로 달리다 반대로 꺾으면 멈추지 않고 커브를 돈다 (아래면 HERO_TURN_TIME 의 일반 턴)
HERO_CURVE_TIME = 0.62        # 커브 한 번에 걸리는 시간 (초): 감속하며 들어가 돌고 빠져나오기까지
HERO_CURVE_MIN = 0.42         # 커브 한가운데의 실제 달리는 속력 (들어올 때 속력에 대한 비율)
HERO_CURVE_EXIT = 0.62        # 커브를 빠져나오는 순간의 속력 비율. 여기서 다시 가속한다
HERO_CURVE_RECOVER = 0.4      # 빠져나온 뒤 천천히 가속하는 시간 (초)
HERO_CURVE_ACCEL = 620.0      # 그동안의 가속도 (평소 1700)
HERO_CURVE_LEAN = 0.22        # 커브 안쪽으로 몸을 기울이는 각도 (라디안)
HERO_CURVE_DEPTH = 0.16       # 커브 한가운데서 화면 쪽으로 다가오며 커 보이는 정도
HERO_CURVE_DROP = 7.0         # 화면 쪽으로 다가오며 아래로 내려오는 높이 (px)
HERO_SLASH_TIME = 0.34        # 칼을 휘두르는 시간 (초)
HERO_WIRE_SLASH_TIME = 0.46   # 와이어로 날며 크게 베는 시간 (초)
HERO_WIRE_SLASH_HIT = 0.3     # 그중 칼을 내리치는 시점 (0~1). 앞쪽 젖히는 동작은 빠르게 지나간다
HERO_WIRE_SLASH_DASH = 1.45   # 내리치는 순간 앞으로 튀어 나가는 속도 배율
HERO_WIRE_WINDUP = 0.13       # 땅에서 와이어를 걸 때 웅크리는 시간 (이 동안 와이어가 날아간다)
HERO_WIRE_SPRING = 0.11       # 웅크렸다 튀어 오르는 그림 시간
HERO_FALL_GRAVITY = 1.4       # 떨어질 때 중력 배율 (묵직하게)
HERO_FALL_MAX = 1200.0        # 떨어지는 최대 속도
HERO_LAND_SPEED = 330.0       # 이 속도 이상으로 떨어지면 세게 착지한다

BGM_VOLUME = 80               # 배경 음악 크기 (0~128)
# 효과음 크기 (0~128). 여기 없는 소리는 default
SFX_VOLUME = {'default': 100, 'slash': 80, 'wire': 35, 'giant_attack': 90, 'gate_open': 110, 'skid': 40, 'dash': 70, 'land': 95}

# 첫 보스(1구간 보스)를 쓰러뜨리기 전까지 나오는 일반 거인 수: {크기: 마리}. 다 나오면 보스를 잡을 때까지 더 안 나온다
# (처음부터 길에 서 있는 거인 중 보스가 나오는 자리 앞쪽 것도 여기에 든다)
FIRST_BOSS_BUDGET = {1: 15, 2: 10, 3: 2}
# 크기별로 섞여 나오기 시작하는 때 (익숙해진 정도 0~1: 시작 → 남은 수만큼 다 섞임).
# 익숙해진 정도 = 첫 보스 전에 쓰러뜨린 거인 수 / FIRST_BOSS_RAMP. 길에 서 있는 거인은 보스 자리까지 얼마나 먼가로 잰다
FIRST_BOSS_UNLOCK = {1: (0.0, 0.0), 2: (0.2, 0.5), 3: (0.6, 0.9)}
FIRST_BOSS_RAMP = 15

# 시연용: n 번째 카드 고르기에 반드시 나오는 카드 (upgrade.UPGRADES 의 이름). 비우면 모두 무작위
DEMO_CARDS = ['회오리 베기 (W)', '동료: 리바이']

# 글꼴: 갈무리 픽셀 글꼴 (resource/fonts/, SIL OFL 1.1 - Galmuri-OFL.txt)
# 픽셀 글꼴은 제 크기의 정수배일 때만 또렷하다. 그래서 글자 크기를 아래 (기본 크기: 파일) 중
# 정수배가 가장 가까운 것으로 맞춘다 (render.text). 예: 16 → 갈무리14 14px, 20 → 갈무리11 22px
PIXEL_FONTS = {11: 'resource/fonts/Galmuri11-Bold.ttf', 14: 'resource/fonts/Galmuri14.ttf'}
FONT_UI = PIXEL_FONTS[11]
FONT_TITLE = PIXEL_FONTS[11]

# 오브젝트 레이어
LAYER_BUILDING, LAYER_GIANT, LAYER_ALLY, LAYER_PLAYER, LAYER_PROJECTILE, LAYER_EFFECT = range(6)

# 구간 = 이야기의 한 장면. 오른쪽으로 갈수록 이야기가 나아간다.
#   bg: 배경 그림 번호 (sky_N / far_N / mid_N), prop: 와이어 지점 그림, fx: 떠다니는 입자 움직임
#   rim · skin · particle · fog: 림 라이트, 거인 피부, 입자, 안개 색
#   gap: 와이어 지점 간격, kind: 처음부터 서 있는 거인 종류, boss: 처음 들어가면 요새에서 나오는 보스
#   boss_at: 있으면 보스가 요새가 아니라, 주인공이 구간의 이 비율만큼 들어갔을 때 화면 오른쪽 바깥에서 나온다
#   story: 처음 들어갈 때 띄우는 한 줄, rest: 쉬어 가는 구간 (가스가 빨리 찬다)
ALL_ZONES = [
    dict(name='벽 밖 들판', bg=1, prop='pine', fx='dust', shafts=True,
         rim=(225, 232, 234), skin=(232, 222, 205), particle=(245, 245, 245), fog=(205, 214, 214),
         gap=(430, 620), kind='erratic', boss='melon', boss_at=0.8,
         story='성문이 열렸다. 넓은 들판 너머, 거인들이 걸어온다'),
    dict(name='거목의 숲', bg=2, prop='bigtree', fx='firefly', shafts=True,
         rim=(170, 225, 140), skin=(176, 196, 168), particle=(200, 255, 120), fog=(80, 120, 92),
         gap=(190, 290), kind='normal', boss='smart', story='건물만 한 나무 사이를 날아라. 영리한 거인이 뒤쫓는다'),
    dict(name='달밤의 고성', bg=3, prop='tower', fx='cold', moon=True,
         rim=(150, 182, 255), skin=(170, 180, 214), particle=(190, 210, 255), fog=(80, 96, 140),
         gap=(290, 400), kind='climber', story='무너진 성에 갇혔다. 성벽을 타고 거인이 오른다'),
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
# 지금 쓰는 구간 (ALL_ZONES 번호). 맵 길이를 고르게 나눠 갖는다. 나머지 구간은 나중에 다시 넣는다
ZONE_PICK = [0, 1]           # 벽 밖 들판, 거목의 숲
ZONES = [ALL_ZONES[i] for i in ZONE_PICK]
ZONE_COUNT = len(ZONES)
ZONE_W = MAP_LEN // ZONE_COUNT   # 구간 하나의 길이
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
