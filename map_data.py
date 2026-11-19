"""길 구간과 와이어 지점. 매 판 같은 맵이 나오도록 시드를 고정한다."""
import math
import random

from config import *

# 위쪽 길이 시작되는 x (오른쪽으로 갈수록 위로 갈라진다)
LANE_START = [WALL_X, 700, 1500, 2500, 3500, 4500]

lanes = []      # lanes[i] = [(x1, x2), ...]
anchors = []    # anchors[i] = [(x, 길 y, 구간), ...]


def build():
    rnd = random.Random(2026)
    lanes.clear()
    anchors.clear()
    lanes.append([(0, MAP_W)])
    for i in range(1, FLOORS):
        segs = []
        x = LANE_START[i] + rnd.uniform(0, 200)
        end = FORTRESS_X - 120
        while x < end - 300:
            length = rnd.uniform(520, 1250)
            x2 = min(end, x + length)
            segs.append((x, x2))
            x = x2 + rnd.uniform(150, 300)
        lanes.append(segs)

    for i, segs in enumerate(lanes):
        row = []
        for x1, x2 in segs:
            x = max(x1, WALL_X + 260) + rnd.uniform(40, 120)
            while x < x2 - 40:
                z = zone_of(x)
                if not (i == 0 and x > FORTRESS_X - 150):
                    row.append((x, LANE_Y[i], z))
                x += rnd.uniform(*ZONES[z]['gap'])   # 들판은 드물고 숲은 빽빽하다
        anchors.append(row)


def segment_at(lane, x):
    for x1, x2 in lanes[lane]:
        if x1 <= x <= x2:
            return x1, x2
    return None


def landing_lane(x, y_prev, y_now):
    """y_prev → y_now 로 내려오면서 지나친 길 중 가장 높은 것"""
    for i in range(TOP_FLOOR, -1, -1):
        ly = LANE_Y[i]
        if y_prev >= ly - 0.01 and y_now <= ly and segment_at(i, x):
            return i
    return None


def floor_at(y):
    """높이 y 가 몇 층인가 (0~TOP_FLOOR). 길 윗면 사이를 한 층으로 친다 (맨 아래 길 아래는 0층, 맨 위 길 위는 4층)"""
    f = 0
    for i in range(FLOORS):
        if y >= LANE_Y[i]:
            f = i
    return f


def find_anchor(px, py, cx, cy):
    """클릭한 높이(cy)가 속한 층의 나무 중, 클릭한 곳(cx)에서 가장 가까운 나무에 건다. 사거리는 없다.
    거는 높이는 클릭한 높이를 그 나무의 걸 수 있는 범위(길 위 ANCHOR_LOW ~ ANCHOR_H) 안으로 맞춘 곳.
    주인공 바로 곁(30px 안)의 나무는 걸어도 움직이지 않으니 건너뛴다."""
    best = None
    for ax, ly, z in anchors[floor_at(cy)]:
        ay = max(ly + ANCHOR_LOW, min(ly + ANCHOR_H, cy))
        if math.hypot(ax - px, ay - py) < 30:
            continue
        gap = abs(ax - cx)
        if best is None or gap < best[0]:
            best = (gap, (ax, ay))
    return best[1] if best else None


build()
