import asyncio
import logging
import random
from collections import deque
from unicodedata import name

from consts import (
    KILL_CENTIPEDE_BODY_POINTS,
    TIMEOUT,
    Direction,
    HISTORY_LEN,
    COOL_DOWN,
    KILL_MUSHROOM_POINTS,
    MUSHROOM_SPAWN_RATE,
)
from mapa import Map

logger = logging.getLogger("Game")
logger.setLevel(logging.DEBUG)

INITIAL_SCORE = 0
GAME_SPEED = 10  # frames per second
MAP_SIZE = (40, 24)


class Centipede:
    def __init__(self, player_name: str, segments: list[tuple[int, int]], dir: Direction = Direction.EAST):
        self._name = player_name
        self._body = segments
        logger.info(f"Centipede {self._name} created with body {self._body}")
        self._direction = dir
        self._history = deque(maxlen=HISTORY_LEN)
        self._alive = True
        self.lastkey = ""
        self.to_grow = 1
        self.range = 3
        self.reverse_next_move = False
        self.move_dir = 1  # 1 means moving down, -1 means moving up

    def grow(self, amount=1):
        self.to_grow += amount
        self.to_grow = max(-len(self._body) + 1, self.to_grow)

    @property
    def head(self):
        return self._body[-1]

    @property
    def tail(self):
        return self._body[:-1]

    @property
    def body(self):
        return self._body

    @property
    def alive(self):
        return self._alive

    def kill(self):
        self._alive = False

    @property
    def name(self):
        return self._name

    @property
    def history(self):
        return str(list(self._history))

    @property
    def direction(self):
        return self._direction

    @property
    def x(self):
        return self._pos[0]

    @property
    def y(self):
        return self._pos[1]

    @property
    def __str__(self) -> str:
        return f"{self.name}({self._body}) - dir={self.direction}"

    @property
    def json(self):
        return {"name": self._name, "body": self._body, "direction": self._direction}

    def exists(self):
        return len(self._body) > 0 and self._alive

    def move(self, mapa, mushrooms, centipedes):
        # check map collisions
        new_pos = mapa.calc_pos(self.head, self.direction, traverse=False)

        # check collisions with other centipedes
        for centipede in centipedes:
            if (
                centipede.exists()
                and centipede.name != self.name
                and new_pos in centipede.body
            ):
                logger.info(
                    "Centipede <%s> collided with <%s>", centipede.name, self.name
                )
                self.reverse_direction()
                return

        # check mushroom collisions
        if new_pos in [mushroom.pos for mushroom in mushrooms]:
            new_pos = self.head

        if new_pos == self.head or self.reverse_next_move:
            # if we can't move to the new position, we banged against a wall
            logger.debug(
                "Head %s can't move to %s with direction %s",
                self.head,
                new_pos,
                self.direction,
            )
            # so we change direction and move down/up instead
            if self.head[1] == 0:
                self.move_dir = 1
            elif self.head[1] >= (mapa.size[1] - 1):
                self.move_dir = -1
            new_pos = (self.head[0], self.head[1] + self.move_dir)

            # check mushroom collisions again and reverse over itself
            if new_pos in [mushroom.pos for mushroom in mushrooms]:
                new_pos = self.head

            self._direction = (
                Direction.EAST if self.direction == Direction.WEST else Direction.WEST
            )
            self.reverse_next_move = False

        self._body.append(new_pos)
        self._body.pop(0)

        self._history.append(new_pos)

    def collision(self, pos):
        return pos in self._body

    def reverse_direction(self):
        self._body.reverse()
        if self.direction == Direction.EAST:
            self._direction = Direction.WEST
        elif self.direction == Direction.WEST:
            self._direction = Direction.EAST
        elif self.direction == Direction.NORTH:
            self._direction = Direction.SOUTH
        elif self.direction == Direction.SOUTH:
            self._direction = Direction.NORTH

    def take_hit(self, blast):
        if blast in self._body:
            index = self._body.index(blast)
            old_body = self._body.copy()
            new_body = self._body[index + 1 :]
            self._body = self._body[:index]

            logger.debug(
                f"Centipede {self.name}({old_body}) was hit at {blast}, new body {self._body}, new centipede {new_body}"
            )

            if len(self._body) < 1:
                self.kill()
            return new_body
        return []

    def _calc_dir(self, old_pos, new_pos):
        if old_pos[0] < new_pos[0]:
            return Direction.EAST
        elif old_pos[0] > new_pos[0]:
            return Direction.WEST
        elif old_pos[1] < new_pos[1]:
            return Direction.SOUTH
        elif old_pos[1] > new_pos[1]:
            return Direction.NORTH
        logger.error(
            "Can't calculate direction from %s to %s, please report as this is a bug",
            old_pos,
            new_pos,
        )
        return None


class BugBlaster:
    def __init__(self, pos):
        self._pos = pos
        self._alive = True
        self.lastkey = ""
        self._direction: Direction = Direction.EAST

    @property
    def direction(self):
        return self._direction

    def move(self, mapa, direction: Direction, mushrooms):
        if direction is None:
            return

        new_pos = self._pos

        if direction == Direction.NORTH:
            if self._pos[1] > 0:
                new_pos = (self._pos[0], self._pos[1] - 1)
        elif direction == Direction.SOUTH:
            if self._pos[1] < mapa.size[1] - 1:
                new_pos = (self._pos[0], self._pos[1] + 1)
        elif direction == Direction.WEST:
            if self._pos[0] > 0:
                new_pos = (self._pos[0] - 1, self._pos[1])
        elif direction == Direction.EAST:
            if self._pos[0] < mapa.size[0] - 1:
                new_pos = (self._pos[0] + 1, self._pos[1])
        self._direction = direction

        if new_pos not in [mushroom.pos for mushroom in mushrooms]:
            self._pos = new_pos

    def exists(self):
        return self._alive

    @property
    def pos(self):
        return self._pos

    @property
    def json(self):
        return {"pos": self._pos, "alive": self._alive}

    def kill(self):
        self._alive = False
        logger.info("BugBlaster <%s> was killed", self.pos)


class Mushroom:
    def __init__(self, x=1, y=1):
        self._pos = (x, y)
        self._health = 4

    def __str__(self):
        return f"Mushroom({self._pos}, health={self._health})"

    def take_damage(self):
        self._health -= 1

    def exists(self):
        return self._health > 0

    @property
    def pos(self):
        return self._pos

    @property
    def health(self):
        return self._health

    def collision(self, pos):
        return pos == self._pos

    @property
    def json(self):
        return {"pos": self._pos, "health": self._health}


def key2direction(key):
    if key == "w":
        return Direction.NORTH
    elif key == "a":
        return Direction.WEST
    elif key == "s":
        return Direction.SOUTH
    elif key == "d":
        return Direction.EAST
    return None


class Game:
    def __init__(self, level=1, timeout=TIMEOUT, size=MAP_SIZE, game_speed=GAME_SPEED):
        logger.info(f"Game(level={level})")
        self.initial_level = level
        self._game_speed = game_speed
        self._running = False
        self._timeout = timeout
        self._step = 0
        self._state = {}
        self._centipedes = []
        self._bug_blaster = None
        self._blasts = []
        self._last_key = ""
        self._score = 0
        self._cooldown = 0  # frames until next shot
        self.map = Map(size=size)

    @property
    def score(self):
        return self._score

    @score.setter
    def score(self, value):
        self._score = value

    @property
    def centipedes(self):
        return self._centipedes

    @property
    def bug_blaster(self):
        return self._bug_blaster

    @property
    def level(self):
        return self.map.level

    @property
    def running(self):
        return self._running

    @property
    def total_steps(self):
        return self._total_steps

    def start(self, players_names):
        logger.debug("Reset world")
        self._running = True
        self._centipedes = [Centipede("mother", self.map.spawn_centipede())]
        self._bug_blaster = BugBlaster(self.map.spawn_bug_blaster())
        self._mushrooms = [Mushroom(x, y) for x, y, _ in self.map.mushrooms]
        self._blasts = []

    def stop(self):
        logger.info("GAME OVER")
        self._running = False

    def quit(self):
        logger.debug("Quit")
        self._running = False

    def keypress(self, player_name, key):
        self._last_key = key

    def update_blasts(self):
        self._blasts = [(b_x, b_y - 1) for (b_x, b_y) in self._blasts if b_y - 1 >= 0]
        to_be_removed = []

        for blast in self._blasts:
            for mushroom in self._mushrooms:
                if mushroom.collision(blast):
                    to_be_removed.append(blast)
                    mushroom.take_damage()
                    logger.debug("Mushroom %s was hit by a blast", mushroom)
                    if not mushroom.exists():
                        logger.debug("Mushroom %s was destroyed", mushroom)
                        self._score += KILL_MUSHROOM_POINTS
                    break

        for blast in to_be_removed:
            logger.debug("Blast %s removed after hitting a mushroom", blast)
            self._blasts.remove(blast)

    def update_bug_blaster(self):
        try:
            if not self._bug_blaster.exists():
                return  # if bug_blaster is dead, we don't need to update it
            lastkey = self._last_key

            assert lastkey in "wasdA"

            # Update position
            self._bug_blaster.move(
                self.map,
                key2direction(lastkey)
                if lastkey in "wasd"
                else self._bug_blaster.direction,
                self._mushrooms,
            )

            # Shoot
            if lastkey == "A" and self._cooldown == 0:
                self._blasts.append(self._bug_blaster.pos)
                logger.info("BugBlaster <%s> fired a blast", self._bug_blaster)
                self._last_key = ""
                self._cooldown = COOL_DOWN  # frames until next shot

            if self._cooldown > 0:
                self._cooldown -= 1

        except AssertionError:
            logger.error("Invalid key <%s> pressed. Valid keys: w,a,s,d", lastkey)

        return True

    def collision(self):
        if (
            not self._running
        ):  # if game is not running, we don't need to check collisions
            return

        for centipede in self._centipedes:
            if not centipede.exists():
                continue

            # check collisions with blasters
            to_be_removed = []
            for blast in self._blasts:
                if centipede.collision(blast):
                    if (new_body := centipede.take_hit(blast)) != []:
                        new_centipede = Centipede(
                            centipede.name + "_" + str(random.randint(1, 100)),
                            new_body,
                            centipede.direction
                        )  # TODO proper naming for child centipede

                        self._centipedes.append(new_centipede)

                    self._score += (
                        KILL_CENTIPEDE_BODY_POINTS - blast[1]
                    )  # higher points for hitting higher up the screen
                    logger.info(
                        "Centipede <%s> was hit by a blast and split",
                        centipede.name,
                    )

                    self._mushrooms.append(Mushroom(x=blast[0], y=blast[1]))

                    to_be_removed.append(blast)
            self._blasts = [b for b in self._blasts if b not in to_be_removed]

            # check collisions with bug blaster
            if self._bug_blaster.exists() and centipede.collision(
                self._bug_blaster._pos
            ):
                self._bug_blaster.kill()
                logger.info("BugBlaster was killed by centipede <%s>", centipede.name)

            # TODO move blasts collision with mushrooms to here

    async def next_frame(self):
        await asyncio.sleep(1.0 / self._game_speed)

        if not self._running:
            logger.info("Waiting for player 1")
            return

        self._step += 1
        if self._step == self._timeout:
            self.stop()

        if self._step % 100 == 0:
            logger.debug(f"[{self._step}] SCORE {name}: {self.score}")

        for centipede in self._centipedes:
            if centipede.alive:
                centipede.move(self.map, self._mushrooms, self.centipedes)

        self.update_bug_blaster()
        self.update_blasts()

        self.collision()

        # clean up dead mushrooms
        self._mushrooms = [
            mushroom for mushroom in self._mushrooms if mushroom.exists()
        ]

        # spawn new mushrooms over time
        if self._step % MUSHROOM_SPAWN_RATE == 0:
            logger.info("Spawning new mushroom")
            x, y = self.map.spawn_mushroom()
            self._mushrooms.append(Mushroom(x=x, y=y))


        self._state = {
            "centipedes": [
                centipede.json for centipede in self._centipedes if centipede.alive
            ],
            "bug_blaster": self._bug_blaster.json,
            "mushrooms": [mushroom.json for mushroom in self._mushrooms],
            "blasts": self._blasts,
            "step": self._step,
            "timeout": self._timeout,
            "score": self.score,
        }

        if not self.bug_blaster.exists() or all(
            [not centipede.alive for centipede in self._centipedes]
        ):
            self.stop()

        return self._state

    def info(self):
        return {
            "size": self.map.size,
            "map": self.map.map,
            "fps": self._game_speed,
            "timeout": self._timeout,
            "level": self.map.level,
        }
