import camera
import render
from config import *

MAX_HP = 100.0
WALL_LEFT = -3000       # 왼쪽으로 이어지는 성벽 끝 (시작 장면에서 화면을 가득 채운다)
# 성문: 벽은 옆에서 본 단면이라, 문은 벽 앞면(오른쪽 면)에 붙은 두꺼운 문짝을 옆에서 본 모습이다.
# 열릴 때 벽 앞면을 따라 위로 올라가고, 뒤에 있던 문간(어둠)으로 주인공이 걸어 나온다
GATE_H = 330            # 문 높이 (약 3층)
GATE_SLOT = 18          # 문짝 뒤 벽 앞면에 파인 문간 폭
GATE_CX = WALL_X - 20.0 # 주인공이 나오기 시작하는 x (문간 안)


class Wall:
    """우리 벽. 내구도가 0 이 되면 패배. 시작할 때 성문이 열리고 주인공이 나온다."""

    def __init__(self):
        self.tile = render.image('wall_px.png', pixel=True)
        self.end = render.image('wall_px_end.png', pixel=True)
        self.gate = render.image('gate_px_side.png', pixel=True)
        self.cracks = render.image('cracks.png')
        self.hp = MAX_HP
        self.hit_t = 9.0          # 마지막으로 맞은 뒤 지난 시간
        self.gate_open = 0.0      # 성문이 열린 정도 0~1

    def damage(self, amount):
        self.hp = max(0.0, self.hp - amount)
        self.hit_t = 0.0

    def repair(self, amount):
        self.hp = min(MAX_HP, self.hp + amount)

    def update(self, dt):
        self.hit_t += dt

    def draw(self):
        if not camera.visible(WALL_LEFT, WALL_X):
            return
        end_x = WALL_X - self.end.w
        # 왼쪽으로 이어지는 성벽 (화면에 보이는 칸만)
        tw = self.tile.w
        x = WALL_LEFT + max(0, int((camera.x - WALL_LEFT) // tw) - 1) * tw
        while x < end_x and x < camera.x + SCREEN_W:
            sx, _ = camera.to_screen(x, 0)
            w = min(tw, end_x - x)
            self.tile.clip_draw_to_origin(0, 0, int(w), self.tile.h, sx, 0)
            x += tw
        sx, _ = camera.to_screen(end_x, 0)
        self.end.draw_to_origin(sx, 0)
        self.draw_gate()
        k = 1 - self.hp / MAX_HP
        if k > 0.05:
            sx, _ = camera.to_screen(WALL_X - self.cracks.w, 0)
            self.cracks.opacify(min(1.0, k * 1.3))
            self.cracks.draw_to_origin(sx, 0)
            self.cracks.opacify(1.0)

    def draw_gate(self):
        """벽 앞면의 문간(어둠) 위로, 옆에서 본 문짝이 열린 만큼 올라가 있다"""
        x1, y1 = camera.to_screen(WALL_X - GATE_SLOT, LANE_Y[0])
        render.rect(x1, y1, x1 + GATE_SLOT, y1 + GATE_H, (12, 12, 16))           # 문간: 벽 속으로 난 길
        render.rect(x1, y1 + GATE_H, x1 + GATE_SLOT, y1 + GATE_H + 6, (70, 66, 62))  # 문간 위 돌 턱
        lift = GATE_H * self.gate_open * 1.02
        gx, gy = camera.to_screen(WALL_X - self.gate.w * 0.6, LANE_Y[0] + lift - 12)
        self.gate.draw_to_origin(gx, gy)
