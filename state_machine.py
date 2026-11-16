# 이벤트는 (종류, 값) 튜플이다.
#   ('WIRE', 와이어 지점), ('ARRIVE', None), ('FALL', None), ('LAND', None), ('TORNADO', 거인)


def wire_fire(e):
    return e[0] == 'WIRE'


def arrive(e):
    return e[0] == 'ARRIVE'


def fall(e):
    return e[0] == 'FALL'


def land(e):
    return e[0] == 'LAND'


def tornado(e):
    return e[0] == 'TORNADO'


class StateMachine:
    def __init__(self, start_state, rules):
        self.cur_state = start_state
        self.rules = rules  # {상태: {이벤트 검사 함수: 다음 상태}}
        self.cur_state.enter(('START', None))

    def update(self, dt):
        self.cur_state.do(dt)

    def handle_event(self, e):
        for check, next_state in self.rules[self.cur_state].items():
            if check(e):
                self.cur_state.exit(e)
                self.cur_state = next_state
                self.cur_state.enter(e)
                return True
        return False
