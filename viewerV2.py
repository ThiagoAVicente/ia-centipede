import argparse
import asyncio
import json
import logging
import os
import pprint

from consts import Tiles
import pygame
import websockets

from viewer.navigator import FrameNavigator, NAVIGATOR_PANEL_WIDTH

replay_buffer_size:int
frame_nav:FrameNavigator

from viewer.common import (
    Blast,
    Directions,
    Food,
    Centipede,
    Stone,
    ScoreBoard,
    get_direction,
    BugBlaster,
    int2dir,
)
from viewer.sprites import (
    BACKGROUND_COLOR,
    BlastSprite,
    BugBlasterSprite,
    Info,
    GameInfoSprite,
    CentipedeSprite,
    FoodSprite,
    StoneSprite,
    ScoreBoardSprite,
)

logging.basicConfig(level=logging.DEBUG)
logger_websockets = logging.getLogger("websockets")
logger_websockets.setLevel(logging.WARN)

logger = logging.getLogger("Viewer")
logger.setLevel(logging.DEBUG)


async def main_loop(q, SCALE):
    while True:
        await main(SCALE)


def should_quit(navigate:bool = False):

    global frame_nav

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            raise SystemExit

        if navigate:
            frame_nav.handle_key_event(event)

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                pygame.quit()
                raise SystemExit


async def main(SCALE):

    global frame_nav

    logging.info("Waiting for map information from server")
    while True:
        try:
            should_quit()
            state = q.get_nowait()  # first state message includes map information
            break
        except asyncio.queues.QueueEmpty:
            await asyncio.sleep(0.1)

    logging.debug("Initial game status: %s", state)
    newgame_json = json.loads(state)

    new_game = True
    GAME_SPEED = newgame_json["fps"]
    WIDTH, HEIGHT = newgame_json["size"]
    MAP = newgame_json["map"]

    display = pygame.display.set_mode((SCALE * WIDTH, SCALE * HEIGHT))

    all_sprites = pygame.sprite.Group()
    centipede_sprites = pygame.sprite.Group()
    food_sprites = pygame.sprite.Group()
    stone_sprites = pygame.sprite.Group()
    bugblaster_sprites = pygame.sprite.Group()
    prev_mushrooms = None
    centipedes = {}

    game_info = Info(text="Score: 0000 Step: 0000")

    while True:
        should_quit(True)

        new_state = None
        try:
            new_state = json.loads(q.get_nowait())
            frame_nav.add_frame(new_state)
            pprint.pprint(new_state)
        except asyncio.queues.QueueEmpty:
            await asyncio.sleep(0.1/GAME_SPEED)

            if frame_nav.is_live():  # Only sleep if we're in live mode
                continue

        state = frame_nav.get_current_frame()
        if state is None:
            continue

        try:


            if "centipedes" in state and "mushrooms" in state:
                centipedes_update = state["centipedes"]
                mushrooms_update = state["mushrooms"]
                game_info.text = f"Score: {state['score']} Step: {state['step']} |{frame_nav.get_info()}"

                if not "highscores" in state:
                    # TODO: remove ScoreBoardSprite
                    # remove scoreboardsprite to avoid bugs when going back to a previous game
                    if not "highscores" in state:
                        for sprite in [s for s in all_sprites if isinstance(s, ScoreBoardSprite)]:
                            all_sprites.remove(sprite)
                            #break # dont break because when using replay mode it can add more sprites :)

            elif "highscores" in state:
                all_sprites.add(
                    ScoreBoardSprite(
                        ScoreBoard(
                            highscores=[(p[0], p[1]) for p in state["highscores"]]
                        ),
                        WIDTH,
                        HEIGHT,
                        SCALE,
                    )
                )
            else:
                new_game = True

        except asyncio.queues.QueueEmpty:
            await asyncio.sleep(0.1 / GAME_SPEED)
            continue

        # Update Foods
        if new_game or prev_mushrooms != mushrooms_update:
            food_sprites.empty()

            foods = {
                f"{food}": Food(
                    pos=(food["pos"][0], food["pos"][1])
                )  # TODO pass heatlh
                for food in mushrooms_update
            }
            food_sprites.add(
                [FoodSprite(food, WIDTH, HEIGHT, SCALE) for food in foods.values()]
            )
            prev_mushrooms = mushrooms_update

        # Update Stones
        if new_game:
            for x, col in enumerate(MAP):
                for y, pos in enumerate(col):
                    if pos == Tiles.STONE:
                        stone_sprites.add(
                            StoneSprite(Stone(pos=(x, y)), WIDTH, HEIGHT, SCALE)
                        )

        # Update centipedes
        if new_game or not all(
            [
                centipede["name"] in [s.name for s in centipedes.values()]
                for centipede in centipedes_update
            ]
        ):
            all_sprites.empty()
            centipede_sprites.empty()

            centipedes = {
                centipede["name"]: Centipede(
                    body=centipede["body"],
                    direction=Directions.RIGHT,
                    name=centipede["name"],
                )
                for centipede in centipedes_update
            }

            all_sprites.add(
                GameInfoSprite(
                    game_info, WIDTH - len(game_info.text) / 2, 0, WIDTH, SCALE
                )
            )

            centipede_sprites.add(
                [
                    CentipedeSprite(centipede, WIDTH, HEIGHT, SCALE)
                    for centipede in centipedes.values()
                ]
            )

        else:
            for centipede in centipedes_update:
                centipedes[centipede["name"]].body = centipede["body"]
                head = centipede["body"][0]
                if len(centipede["body"]) > 1:
                    neck = centipede["body"][1]
                    centipedes[centipede["name"]].direction = get_direction(
                        head[0], head[1], neck[0], neck[1], HEIGHT=HEIGHT, WIDTH=WIDTH
                    )
                else:
                    centipedes[centipede["name"]].direction = int2dir(
                        centipede["direction"]
                    )

            # Remove dead centipedes
            dead_centipede_names = []
            for centipede in centipedes.values():
                if centipede.name not in [s["name"] for s in centipedes_update]:
                    # Remove sprites
                    for sprite in centipede_sprites:
                        if sprite.centipede.name == centipede.name:
                            centipede_sprites.remove(sprite)
                    # Track for removal from dictionary
                    dead_centipede_names.append(centipede.name)
            
            # Remove from centipedes dictionary
            for name in dead_centipede_names:
                del centipedes[name]

        # update bug blaster
        if "bug_blaster" in state:
            bugblaster_sprites.empty()
            bugblaster = BugBlaster(pos=state["bug_blaster"]["pos"])
            bugblaster_sprites.add(
                BugBlasterSprite(bugblaster.pos, WIDTH, HEIGHT, SCALE)
            )

            for blast in state.get("blasts", []):
                bugblaster_sprites.add(BlastSprite(Blast(blast), WIDTH, HEIGHT, SCALE))

        new_game = False

        # Render Window
        display.fill(BACKGROUND_COLOR)

        try:
            all_sprites.update()
            centipede_sprites.update()
            food_sprites.update()
            stone_sprites.update()
            bugblaster_sprites.update()
        except Exception as e:
            logging.error(e)
        stone_sprites.draw(display)
        food_sprites.draw(display)
        all_sprites.draw(display)
        centipede_sprites.draw(display)
        bugblaster_sprites.draw(display)

        # update window
        pygame.display.flip()


async def messages_handler(ws_path, queue):
    async with websockets.connect(ws_path) as websocket:
        await websocket.send(json.dumps({"cmd": "join"}))

        while True:
            r = await websocket.recv()
            queue.put_nowait(r)


if __name__ == "__main__":

    SERVER = os.environ.get("SERVER", "localhost")
    PORT = os.environ.get("PORT", "8000")

    parser = argparse.ArgumentParser()
    parser.add_argument("--server", help="IP address of the server", default=SERVER)
    parser.add_argument(
        "--scale", help="reduce size of window by x times", type=int, default=1
    )
    parser.add_argument("--port", help="TCP port", type=int, default=PORT)
    parser.add_argument("--buffer", help="Navigator buffer size", type=int, default=200 )
    args = parser.parse_args()

    replay_buffer_size = args.buffer
    frame_nav = FrameNavigator(replay_buffer_size)

    SCALE = 32 * (1 / args.scale)

    LOOP = asyncio.get_event_loop()
    pygame.init()
    pygame.font.init()
    pygame.key.set_repeat(300,50)
    q: asyncio.Queue = asyncio.Queue()

    ws_path = f"ws://{args.server}:{args.port}/viewer"

    try:
        LOOP.run_until_complete(
            asyncio.gather(messages_handler(ws_path, q), main_loop(q, SCALE=SCALE))
        )
    finally:
        LOOP.stop()
