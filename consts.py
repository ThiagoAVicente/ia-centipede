from enum import IntEnum

HISTORY_LEN = 10

KILL_CENTIPEDE_BODY_POINTS = 100
KILL_MUSHROOM_POINTS = 1

CENTIPEDE_LENGTH = 20

COOL_DOWN = 10  # frames until next shot

MUSHROOM_SPAWN_RATE = 20  # frames between spawning new mushrooms

TIMEOUT = 3600


class Tiles(IntEnum):
    PASSAGE = 0
    STONE = 1
    FOOD = 2
    SUPER = 3
    SNAKE = 4


class Speed(IntEnum):
    SLOWEST = (1,)
    SLOW = (2,)
    NORMAL = (3,)
    FAST = 4


class Direction(IntEnum):
    NORTH = 0
    EAST = 1
    SOUTH = 2
    WEST = 3
