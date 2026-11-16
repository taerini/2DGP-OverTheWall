import time

running = None
stack = None
frame_time = 0.0


def change_mode(mode):
    # 쌓여 있는 모드를 모두 정리하고 새 모드로 바꾼다
    global stack
    while stack:
        stack.pop().finish()
    stack.append(mode)
    mode.init()


def push_mode(mode):
    global stack
    if stack:
        stack[-1].pause()
    stack.append(mode)
    mode.init()


def pop_mode():
    global stack
    if stack:
        stack.pop().finish()
    if stack:
        stack[-1].resume()


def quit():
    global running
    running = False


def run(start_mode):
    global running, stack, frame_time
    running = True
    stack = [start_mode]
    start_mode.init()

    current_time = time.time()
    while running:
        stack[-1].handle_events()
        stack[-1].update()
        stack[-1].draw()
        now = time.time()
        # 창을 끌거나 멈췄을 때 한 번에 크게 튀지 않도록 상한을 둔다
        frame_time = min(now - current_time, 1 / 30)
        current_time = now

    while stack:
        stack.pop().finish()
