import os

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
game_framework.run(title_mode)
close_canvas()
