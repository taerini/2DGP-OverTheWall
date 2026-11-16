"""길 구간과 와이어 지점. 매 판 같은 맵이 나오도록 시드를 고정한다."""
import math
import random

from config import *

# 위쪽 길이 시작되는 x (오른쪽으로 갈수록 위로 갈라진다)
LANE_START = [WALL_X, 700, 1500, 2500, 3500]

lanes = []      # lanes[i] = [(x1, x2), ...]
anchors = []    # anchors[i] = [(x, 길 y, 구간), ...]


def build():
    rnd = random.Random(2026)
    lanes.clear()
    anchors.clear()
    lanes.append([(0, MAP_W)])
    for i in range(1, 5):
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
    for i in range(4, -1, -1):
        ly = LANE_Y[i]
        if y_prev >= ly - 0.01 and y_now <= ly and segment_at(i, x):
            return i
    return None


def find_anchor(px, py, cx, cy, reach):
    """와이어가 닿는 나무 중 클릭한 곳에서 가장 가까운 나무에, 클릭한 높이로 건다.
    높이는 그 나무의 걸 수 있는 범위(길 위 ANCHOR_LOW ~ ANCHOR_H) 안으로 맞춘다."""
    best = None
    for row in anchors:
        for ax, ly, z in row:
            ay = max(ly + ANCHOR_LOW, min(ly + ANCHOR_H, cy))
            d = math.hypot(ax - px, ay - py)
            if d > reach or d < 30:
                continue
            gap = math.hypot(ax - cx, ay - cy)
            if best is None or gap < best[0]:
                best = (gap, (ax, ay))
    return best[1] if best else None


build()
