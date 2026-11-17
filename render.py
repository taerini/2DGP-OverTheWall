"""pico2d 에 없는 그리기 도구: 색 입히기, 반투명 사각형, 한글 글자 캐시."""
from pico2d import Image, load_image
import pico2d.pico2d as p2
from sdl2 import (SDL_SetHint, SDL_SetRenderDrawBlendMode, SDL_BLENDMODE_BLEND, SDL_SetTextureColorMod,
                  SDL_CreateTextureFromSurface, SDL_FreeSurface, SDL_Color, SDL_SetRenderDrawColor,
                  SDL_RenderFillRect, SDL_RenderDrawLine, SDL_Rect)
from sdl2.sdlttf import TTF_OpenFont, TTF_RenderUTF8_Blended

from config import SCREEN_H, FONT_UI

_images = {}
_fonts = {}
_texts = {}


def setup():
    # 확대·축소할 때 부드럽게 (이후에 만드는 텍스처부터 적용)
    SDL_SetHint(b'SDL_RENDER_SCALE_QUALITY', b'1')
    SDL_SetRenderDrawBlendMode(p2.renderer, SDL_BLENDMODE_BLEND)


def image(name, pixel=False):
    """같은 그림을 여러 번 불러오지 않도록 모아 둔다.
    pixel=True 면 크게 늘려도 번지지 않게 픽셀을 그대로 키운다 (픽셀 그림 시트용)."""
    img = _images.get(name)
    if img is None:
        if pixel:
            SDL_SetHint(b'SDL_RENDER_SCALE_QUALITY', b'0')
        img = load_image('resource/' + name)
        if pixel:
            SDL_SetHint(b'SDL_RENDER_SCALE_QUALITY', b'1')
        _images[name] = img
    return img


def shade(col, d):
    return tuple(max(0, min(255, c + d)) for c in col)


def pixel_bar(x, y, n, k, col, u=3, seg_w=3, seg_h=4, alpha=1.0):
    """픽셀 느낌 칸 막대. (x, y) 왼쪽 아래, u = 픽셀 하나 크기. 칸 n 개 중 k(0~1) 만큼 찬다.
    검은 테두리 + 어두운 바탕 + 칸마다 위 밝은 줄·아래 어두운 줄. (폭, 높이)를 돌려준다."""
    w = (3 + n * (seg_w + 1)) * u
    h = (seg_h + 4) * u
    a = 255 * alpha
    rect(x, y, x + w, y + h, (14, 12, 18), a)
    rect(x + u, y + u, x + w - u, y + h - u, (40, 38, 48), a)
    fill = max(0.0, min(1.0, k)) * n
    for i in range(n):
        sx = x + 2 * u + i * (seg_w + 1) * u
        sy = y + 2 * u
        rect(sx, sy, sx + seg_w * u, sy + seg_h * u, (62, 60, 72), a)
        part = min(1.0, fill - i)
        if part <= 0:
            continue
        fw = max(1, round(seg_w * part)) * u            # 칸 일부만 찰 때도 픽셀 단위로 끊는다
        rect(sx, sy, sx + fw, sy + seg_h * u, col, a)
        rect(sx, sy + (seg_h - 1) * u, sx + fw, sy + seg_h * u, shade(col, 60), a)
        rect(sx, sy, sx + fw, sy + u, shade(col, -60), a)
    return w, h


GLYPHS = {   # 5×7 픽셀 글자 (위에서 아래로)
    'Q': ['.###.', '#...#', '#...#', '#...#', '#.#.#', '#..#.', '.##.#'],
    'W': ['#...#', '#...#', '#...#', '#.#.#', '#.#.#', '##.##', '#...#'],
    '1': ['..#..', '.##..', '..#..', '..#..', '..#..', '..#..', '.###.'],
    '2': ['.###.', '#...#', '....#', '...#.', '..#..', '.#...', '#####'],
    '3': ['####.', '....#', '....#', '.###.', '....#', '....#', '####.'],
}


def pixel_frame(x1, y1, x2, y2, body, accent, u=4, a=255):
    """각진 픽셀 액자: 모서리 한 칸을 깎은 검은 테두리 + 안쪽 밝은 위·왼쪽 / 어두운 아래·오른쪽 줄"""
    k = (14, 12, 18)
    rect(x1 + u, y1, x2 - u, y2, k, a)
    rect(x1, y1 + u, x2, y2 - u, k, a)
    rect(x1 + u, y1 + u, x2 - u, y2 - u, accent, a)                      # 바깥 띠 (종류 색)
    rect(x1 + 2 * u, y1 + 2 * u, x2 - 2 * u, y2 - 2 * u, k, a)
    rect(x1 + 3 * u, y1 + 3 * u, x2 - 3 * u, y2 - 3 * u, body, a)        # 몸통
    rect(x1 + 3 * u, y2 - 4 * u, x2 - 3 * u, y2 - 3 * u, shade(body, 28), a)   # 윗줄 빛
    rect(x1 + 3 * u, y1 + 3 * u, x2 - 3 * u, y1 + 4 * u, shade(body, -18), a)  # 아랫줄 그늘


def pixel_glyph(ch, x, y, u, col, a=255):
    """5×7 픽셀 글자를 (x, y) 왼쪽 아래부터 찍는다"""
    for r, row in enumerate(GLYPHS[ch]):
        for c, v in enumerate(row):
            if v == '#':
                px, py = x + c * u, y + (6 - r) * u
                rect(px, py, px + u, py + u, col, a)


def pixel_key(x, y, ch, ready, cool=0.0, u=3, w=20, h=20, alpha=1.0):
    """픽셀 키캡. (x, y) 왼쪽 아래. cool(0~1) 만큼 아래에서부터 어둡게 덮는다 (재사용 대기)"""
    face = (206, 200, 186) if ready else (112, 110, 106)
    W, H = w * u, h * u
    a = 255 * alpha
    rect(x, y, x + W, y + H, (14, 12, 18), a)
    rect(x + u, y + u, x + W - u, y + H - u, shade(face, -70), a)           # 옆면 (아래로 두껍게)
    rect(x + u, y + 4 * u, x + W - u, y + H - u, face, a)                     # 윗면
    rect(x + 2 * u, y + H - 2 * u, x + W - 2 * u, y + H - u, shade(face, 40), a)   # 윗줄 빛
    pixel_glyph(ch, x + (w - 5) // 2 * u, y + 9 * u, u, (30, 28, 36) if ready else (64, 62, 60), a)
    if cool > 0:
        ch_ = max(1, round((h - 2) * min(1.0, cool))) * u
        rect(x + u, y + u, x + W - u, y + u + ch_, (20, 18, 26), 170 * alpha)
    return W, H


def pixel_map(rows, x, y, u, colors, a=255, dx=0, dy=0):
    """문자 격자 그림을 (x, y) 왼쪽 아래부터 찍는다. colors: {문자: rgb}. 없는 문자는 투명"""
    h = len(rows)
    for r, row in enumerate(rows):
        for c, ch in enumerate(row):
            col = colors.get(ch)
            if col:
                px, py = x + c * u + dx, y + (h - 1 - r) * u + dy
                rect(px, py, px + u, py + u, col, a)


def pixel_gauge(x, y, n, k, col, ghost=0.0, u=2, h=6, a=255):
    """이어진 픽셀 게이지. (x, y) 왼쪽 위 기준이 아니라 왼쪽 아래. n = 안쪽 폭(픽셀 수), h = 안쪽 높이(픽셀 수).
    k 만큼 col 로 차고, ghost(>k) 까지는 방금 깎인 부분을 하얗게 보여 준다. 픽셀 단위로 끊는다."""
    W, H = (n + 2) * u, (h + 2) * u
    rect(x, y, x + W, y + H, (14, 12, 18), a)                      # 테두리
    rect(x + u, y + u, x + W - u, y + H - u, (40, 36, 46), a)       # 빈 속
    fill = max(0, min(n, round(n * k)))
    gh = max(fill, min(n, round(n * ghost)))
    if gh > fill:
        rect(x + u + fill * u, y + u, x + u + gh * u, y + H - u, (245, 236, 220), a)
    if fill > 0:
        x1, x2 = x + u, x + u + fill * u
        rect(x1, y + u, x2, y + H - u, col, a)
        rect(x1, y + H - 2 * u, x2, y + H - u, shade(col, 55), a)   # 윗줄 빛
        rect(x1, y + u, x2, y + 2 * u, shade(col, -55), a)           # 아랫줄 그늘
    return W, H


ORB_N = 16                       # 가스 게이지 격자 크기


def pixel_orb(cx, cy, k, col, u=3, a=255):
    """둥근 픽셀 게이지: 검은 테두리, 어두운 속, 아래에서부터 k(0~1) 만큼 col 로 찬다. 윗줄은 밝게."""
    n, r = ORB_N, ORB_N / 2
    x0, y0 = cx - n * u / 2, cy - n * u / 2
    level = round(k * (n - 2))           # 찬 줄 수 (테두리 안쪽 기준)
    for row in range(n):                 # row 0 = 맨 아래
        yc = row + 0.5 - r
        half = (r * r - yc * yc) ** 0.5
        c1, c2 = int(round(r - half)), int(round(r + half))
        if c2 <= c1:
            continue
        py = y0 + row * u
        rect(x0 + c1 * u, py, x0 + c2 * u, py + u, (14, 12, 18), a)          # 테두리
        if row == 0 or row == n - 1 or c2 - c1 <= 2:
            continue
        inner = (x0 + (c1 + 1) * u, py, x0 + (c2 - 1) * u, py + u)
        if row - 1 < level:
            top = row == level                                              # 찬 물의 맨 윗줄
            rect(*inner, shade(col, 50) if top else col, a)
        else:
            rect(*inner, (34, 32, 42), a)
    # 유리 반짝임
    rect(x0 + 4 * u, y0 + (n - 4) * u, x0 + 6 * u, y0 + (n - 3) * u, (255, 255, 255), a * 0.7)
    rect(x0 + 3 * u, y0 + (n - 6) * u, x0 + 4 * u, y0 + (n - 4) * u, (255, 255, 255), a * 0.5)


def pixel_panel(x1, y1, x2, y2, u=3, alpha=0.75):
    """픽셀 느낌 패널: 검은 테두리 + 반투명 어두운 바탕 + 안쪽 밝은 테두리 한 줄"""
    a = 255 * alpha
    rect(x1, y1, x2, y2, (14, 12, 18), a)
    rect(x1 + u, y1 + u, x2 - u, y2 - u, (70, 66, 80), a)
    rect(x1 + 2 * u, y1 + 2 * u, x2 - 2 * u, y2 - 2 * u, (26, 24, 32), a)


def tint(img, rgb, alpha=1.0):
    SDL_SetTextureColorMod(img.texture, int(rgb[0]), int(rgb[1]), int(rgb[2]))
    img.opacify(max(0.0, min(1.0, alpha)))


def untint(img):
    SDL_SetTextureColorMod(img.texture, 255, 255, 255)
    img.opacify(1.0)


def rect(x1, y1, x2, y2, rgb, a=255):
    """채운 사각형. (x1, y1)은 왼쪽 아래"""
    SDL_SetRenderDrawColor(p2.renderer, int(rgb[0]), int(rgb[1]), int(rgb[2]), int(a))
    SDL_RenderFillRect(p2.renderer, SDL_Rect(int(x1), int(SCREEN_H - y2), int(x2 - x1), int(y2 - y1)))


def line(x1, y1, x2, y2, rgb, a=255):
    SDL_SetRenderDrawColor(p2.renderer, int(rgb[0]), int(rgb[1]), int(rgb[2]), int(a))
    SDL_RenderDrawLine(p2.renderer, int(x1), int(SCREEN_H - y1), int(x2), int(SCREEN_H - y2))


def text(s, x, y, size=18, color=(255, 255, 255), align='left', font=FONT_UI, alpha=1.0, shadow=True):
    """(x, y)는 글자 줄의 세로 가운데. align: left / center / right"""
    if not s:
        return
    if shadow:
        text(s, x + 1, y - 2, size, (0, 0, 0), align, font, alpha * 0.6, False)
    key = (s, size, color, font)
    img = _texts.get(key)
    if img is None:
        f = _fonts.get((font, size))
        if f is None:
            f = TTF_OpenFont(font.encode('utf-8'), size)
            _fonts[(font, size)] = f
        surf = TTF_RenderUTF8_Blended(f, s.encode('utf-8'), SDL_Color(*color))
        img = Image(SDL_CreateTextureFromSurface(p2.renderer, surf))
        SDL_FreeSurface(surf)
        if len(_texts) > 800:
            _texts.clear()
        _texts[key] = img
    if align == 'center':
        x -= img.w / 2
    elif align == 'right':
        x -= img.w
    img.opacify(alpha)
    img.draw(x + img.w / 2, y)
