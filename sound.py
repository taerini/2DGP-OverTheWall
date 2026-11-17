"""배경 음악과 효과음. 같은 곡을 이미 틀고 있으면 처음부터 다시 틀지 않는다 (모드가 바뀌어도 이어서 흐르게)."""
from pico2d import load_music, load_wav
from sdl2.sdlmixer import Mix_FadeInMusic, Mix_FadeOutMusic, Mix_PlayingMusic

import camera
from config import BGM_VOLUME, SFX_VOLUME

_music = {}          # 불러온 곡 (한 번만 불러온다)
_now = None          # 지금 트는 곡 이름


def play_bgm(name, fade_ms=1500):
    """resource/bgm/<name>.mp3 를 계속 반복해서 튼다. 처음엔 fade_ms 동안 서서히 커진다"""
    global _now
    if _now == name and Mix_PlayingMusic():
        return
    m = _music.get(name)
    if m is None:
        m = load_music(f'resource/bgm/{name}.mp3')
        if m is None:           # 소리 장치가 없으면 조용히 넘어간다
            return
        _music[name] = m
    m.set_volume(BGM_VOLUME)
    Mix_FadeInMusic(m.music, -1, fade_ms)
    _now = name


def stop_bgm(fade_ms=1000):
    global _now
    if _now is not None:
        Mix_FadeOutMusic(fade_ms)
        _now = None


# ------------------------------------------------ 효과음 (resource/sfx/<name>.wav, PixelLab 으로 만든 소리)
_wavs = {}


def sfx(name, volume=None):
    """효과음을 한 번 튼다. 소리 장치가 없으면 조용히 넘어간다"""
    w = _wavs.get(name)
    if w is None:
        w = load_wav(f'resource/sfx/{name}.wav')
        if w is None:
            return
        _wavs[name] = w
    w.set_volume(SFX_VOLUME.get(name, SFX_VOLUME['default']) if volume is None else volume)
    w.play()


def sfx_at(name, x, volume=None):
    """그 자리(월드 x)가 화면에 보일 때만 튼다 (멀리 있는 거인 소리는 안 들리게)"""
    if camera.visible(x, x, 200):
        sfx(name, volume)
