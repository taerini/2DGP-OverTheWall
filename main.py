import os
import sys

# 어디서 실행해도 resource/ 를 찾을 수 있도록 작업 폴더를 맞춘다
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from pico2d import open_canvas, close_canvas, hide_lattice

import game_framework
import render
import title_mode
from config import SCREEN_W, SCREEN_H

open_canvas(SCREEN_W, SCREEN_H, sync=True)
hide_lattice()
render.setup()
if 'test' in sys.argv[1:]:          # python main.py test → 테스트 창 (test_mode.py)
    import test_mode
    game_framework.run(test_mode)
else:
    game_framework.run(title_mode)
close_canvas()
