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
