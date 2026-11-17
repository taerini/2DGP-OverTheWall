"""구간별 배경 레이어(하늘 → 먼 배경 → 중간 배경 → 안개), 길과 와이어 지점, 떠다니는 입자."""
import math
import random

import camera
import map_data
import render
from config import *

FAR_P, MID_P, FOG_P = 0.12, 0.4, 0.65
PX_ZONES = 2                 # 앞에서부터 이 구간 수만큼 픽셀 배경(tools/make_bg_px.py)을 쓴다


def zone_image(z, px_name, name):
    """픽셀 배경이 있는 구간은 픽셀 그림, 나머지는 원래 그림"""
    return render.image(px_name, pixel=True) if z < PX_ZONES else render.image(name)


class Background:
    def __init__(self):
        self.sky = [zone_image(i, f"sky_px_{z['bg']}.png", f"sky_{z['bg']}.png") for i, z in enumerate(ZONES)]
        self.far = [zone_image(i, f"far_px_{z['bg']}.png", f"far_{z['bg']}.png") for i, z in enumerate(ZONES)]
        self.mid = [zone_image(i, f"mid_px_{z['bg']}.png", f"mid_{z['bg']}.png") for i, z in enumerate(ZONES)]
        self.prop_img = [zone_image(i, f"prop_px_{z['prop']}.png", f"prop_{z['prop']}.png") for i, z in enumerate(ZONES)]
        # 땅·발판: [원래 그림, 픽셀 그림]
        self.lane_mids = [render.image('lane_mid.png'), render.image('lane_px_mid.png', pixel=True)]
        self.lane_lefts = [render.image('lane_left.png'), render.image('lane_px_left.png', pixel=True)]
        self.lane_rights = [render.image('lane_right.png'), render.image('lane_px_right.png', pixel=True)]
        self.grounds = [render.image('ground_mid.png'), render.image('ground_px.png', pixel=True)]
        self.moon = render.image('moon.png')
        self.fog = render.image('fog.png')
        self.shafts = render.image('shafts.png')
        self.vignette = render.image('vignette.png')
        self.dot = render.image('dot.png')
        self.time = 0.0
        self.particles = [self.new_particle(True) for _ in range(70)]

    # ------------------------------------------------ 입자
    def new_particle(self, anywhere=False):
        return [random.uniform(0, SCREEN_W), random.uniform(0, SCREEN_H) if anywhere else random.uniform(-20, SCREEN_H + 20),
                random.uniform(0, 6.28), random.uniform(0.6, 1.4), random.uniform(0.3, 1.0)]

    def update(self, dt):
        self.time += dt
        cx = camera.x + SCREEN_W / 2
        fx = ZONES[max(zone_weights(cx), key=lambda p: p[1])[0]]['fx']
        for p in self.particles:
            p[2] += dt
            if fx == 'dust':      # 흰 먼지: 천천히 떨어짐
                p[0] += (8 + 6 * math.sin(p[2])) * dt
                p[1] -= 12 * p[3] * dt
            elif fx == 'firefly':  # 반딧불: 이리저리 떠다님
                p[0] += 14 * math.sin(p[2] * 0.7 + p[3] * 5) * dt
                p[1] += 10 * math.cos(p[2] * 0.9 + p[3] * 3) * dt
            elif fx == 'cold':     # 차가운 먼지
                p[0] -= 6 * dt
                p[1] -= 6 * p[3] * dt
            elif fx == 'sand':     # 바닷바람에 날리는 모래
                p[0] -= (40 + 20 * p[3]) * dt
                p[1] += 4 * math.sin(p[2] * 2 + p[3] * 4) * dt
            elif fx == 'ember':    # 불씨: 위로 솟음
                p[0] += 18 * math.sin(p[2] * 1.3) * dt
                p[1] += 40 * p[3] * dt
            else:           # 재
                p[0] -= 10 * dt
                p[1] -= 18 * p[3] * dt
            if p[1] < -20:
                p[1] = SCREEN_H + 10
            elif p[1] > SCREEN_H + 20:
                p[1] = -10
            if p[0] < -20:
                p[0] = SCREEN_W + 10
            elif p[0] > SCREEN_W + 20:
                p[0] = -10

    # ------------------------------------------------ 그리기
    def tile(self, img, parallax, y, alpha):
        if alpha <= 0.01:
            return
        img.opacify(alpha)
        off = -(camera.x * parallax) % img.w
        sx = off - img.w
        while sx < SCREEN_W:
            img.draw_to_origin(sx, y)
            sx += img.w

    def draw_back(self):
        cx = camera.x + SCREEN_W / 2
        weights = zone_weights(cx)
        # 하늘: 첫 구간을 깔고 다음 구간을 겹친다
        for i, (z, w) in enumerate(weights):
            self.sky[z].opacify(1.0 if i == 0 else w)
            self.sky[z].draw_to_origin(0, 0, SCREEN_W, SCREEN_H)
        for z, w in weights:
            if ZONES[z].get('moon'):
                self.moon.opacify(w)
                self.moon.draw(1010 - camera.x * 0.02 % 200, 560)
            self.tile(self.far[z], FAR_P, 0, w)
        for z, w in weights:
            self.tile(self.mid[z], MID_P, -40, w)
        # 안개 띠
        fog_col = zone_color(cx, 'fog')
        render.tint(self.fog, fog_col, 0.75)
        off = -(camera.x * FOG_P) % 512
        sx = off - 512
        while sx < SCREEN_W:
            self.fog.draw_to_origin(sx, -20, 512, 230)
            sx += 512
        render.tint(self.fog, fog_col, 0.3)
        sx = (-(camera.x * 0.8) % 512) - 512
        while sx < SCREEN_W:
            self.fog.draw_to_origin(sx, 250, 512, 160)
            sx += 512
        render.untint(self.fog)

    def draw_terrain(self):
        for i in range(5):
            ly = LANE_Y[i]
            for x1, x2 in map_data.lanes[i]:
                if not camera.visible(x1, x2):
                    continue
                if i == 0:
                    self.draw_strip(self.grounds, x1, x2, ly - 78, 128)
                else:
                    self.draw_strip(self.lane_mids, x1, x2, ly - 28, 128)
                    sx, _ = camera.to_screen(x1, 0)
                    img = self.lane_lefts[zone_of(x1) < PX_ZONES]
                    render.tint(img, zone_color(x1, 'rim'))
                    img.draw_to_origin(sx - 18, ly - 28)
                    sx, _ = camera.to_screen(x2, 0)
                    img = self.lane_rights[zone_of(x2) < PX_ZONES]
                    render.tint(img, zone_color(x2, 'rim'))
                    img.draw_to_origin(sx - 6, ly - 28)
            for ax, _, z in map_data.anchors[i]:
                if not camera.visible(ax - 70, ax + 70):
                    continue
                img = self.prop_img[z]
                render.tint(img, zone_color(ax, 'rim'))
                sx, sy = camera.to_screen(ax, ly)
                img.draw(sx, sy + img.h / 2 - 1)

    def draw_strip(self, imgs, x1, x2, y, tw):
        """imgs: [원래 그림, 픽셀 그림]. 타일마다 구간을 보고 고른다."""
        x = x1 + max(0, int((camera.x - tw - x1) // tw)) * tw
        end = min(x2, camera.x + SCREEN_W + tw)
        while x < end:
            w = min(tw, x2 - x)
            img = imgs[zone_of(x + w / 2) < PX_ZONES]
            render.tint(img, zone_color(x + w / 2, 'rim'))
            sx, sy = camera.to_screen(x, y)
            if w >= tw:
                img.draw_to_origin(sx, sy)
            else:
                img.clip_draw_to_origin(0, 0, int(w), img.h, sx, sy)
            x += tw

    def draw_front(self):
        cx = camera.x + SCREEN_W / 2
        weights = zone_weights(cx)
        for z, w in weights:
            if ZONES[z].get('shafts'):
                self.shafts.opacify(w * (0.55 + 0.15 * math.sin(self.time * 0.5)))
                self.shafts.draw_to_origin(0, 0)
        col = zone_color(cx, 'particle')
        fx = ZONES[max(weights, key=lambda p: p[1])[0]]['fx']
        for x, y, ph, size, a in self.particles:
            alpha = a
            if fx == 'firefly':
                alpha = a * (0.5 + 0.5 * math.sin(ph * 2.5))
            render.tint(self.dot, col, alpha * 0.8)
            s = 6 * size if fx in ('firefly', 'ember') else 4 * size
            self.dot.draw(x, y, s, s)
        render.untint(self.dot)
        self.vignette.opacify(1.0)
        self.vignette.draw_to_origin(0, 0, SCREEN_W, SCREEN_H)
