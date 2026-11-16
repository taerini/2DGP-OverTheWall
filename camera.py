import random

from config import SCREEN_W, MAP_W

# 주인공이 화면 왼쪽에서 42% 지점에 오게 한다
OFFSET_X = SCREEN_W * 0.42

x = 0.0
shake_time = 0.0
shake_amp = 5.0
shake_dx, shake_dy = 0.0, 0.0


def clamp_x(v):
    return max(0.0, min(MAP_W - SCREEN_W, v))


def reset(tx):
    global x
    x = clamp_x(tx - OFFSET_X)


def update(tx, dt):
    global x, shake_time, shake_dx, shake_dy, shake_amp
    k = min(1.0, dt * 5)
    x = clamp_x(x + (tx - OFFSET_X - x) * k)
    shake_time = max(0.0, shake_time - dt)
    if shake_time > 0:
        a = shake_amp * min(1.0, shake_time * 6)
        shake_dx, shake_dy = random.uniform(-a, a), random.uniform(-a * 0.8, a * 0.8)
    else:
        shake_dx, shake_dy = 0.0, 0.0
        shake_amp = 5.0


def shake(t, amp=5.0):
    global shake_time, shake_amp
    shake_time = max(shake_time, t)
    shake_amp = max(shake_amp, amp)


def to_screen(wx, wy):
    return wx - x + shake_dx, wy + shake_dy


def to_world(sx, sy):
    return sx + x, sy


def visible(x1, x2, margin=80):
    return x2 > x - margin and x1 < x + SCREEN_W + margin
