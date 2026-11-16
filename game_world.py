from config import LAYER_EFFECT

world = [[] for _ in range(LAYER_EFFECT + 1)]


def add_object(o, depth):
    world[depth].append(o)


def remove_object(o):
    for layer in world:
        if o in layer:
            layer.remove(o)
            return


def objects(depth):
    return list(world[depth])


def update(dt):
    for layer in world:
        for o in list(layer):
            o.update(dt)


def render():
    for layer in world:
        for o in layer:
            o.draw()


def clear():
    for layer in world:
        layer.clear()


def collide(bb_a, bb_b):
    la, ba, ra, ta = bb_a
    lb, bb, rb, tb = bb_b
    return not (la > rb or ra < lb or ta < bb or ba > tb)
