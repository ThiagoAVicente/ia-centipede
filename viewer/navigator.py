import pygame
import logging
from collections import deque

LIVE:int = -1
NAVIGATOR_PANEL_WIDTH = 200

logger = logging.getLogger("Navigator")
logger.setLevel(logging.DEBUG)

class FrameNavigator:
    def __init__(self, buffer_size:int=100) -> None:
        self.buffer = deque(maxlen=buffer_size)
        self.current_index:int = LIVE
        self.isPaused:bool = False
        self.has_moved:bool = False

    def add_frame(self, game_state) -> None:
        """Add new frame to buffer"""
        start = len(self.buffer)
        self.buffer.append(game_state)
        end = len(self.buffer)
        if self.current_index != -1 and (start == end):
            self.current_index = max(0,self.current_index-1)

    def go_back(self, times:int = 1) -> bool:
        """Go to previous frame"""
        # TODO: use times
        # try to move buffer to left
        if not self.buffer or (self.current_index == 0):
            return False

        if self.current_index == -1:
            self.current_index = len(self.buffer) - 1
        elif self.current_index > 0:
            self.current_index -= 1

        self.isPaused = True
        return True

    def go_forward(self, times:int = 1) -> bool:
        """Go to next frame"""
        # TODO: use times
        # try to move buffer to right
        if not self.buffer:
            return False

        if self.current_index == -1:
            return False # live

        if self.current_index < len(self.buffer) -1:
            self.current_index += 1

        else:
            # back to live
            self.current_index = -1
            self.isPaused = False

        return True

    def get_current_frame(self):
        """Get current frame from pointer"""
        if not self.buffer:
            return None

        # live mode
        if self.current_index == -1:
            return self.buffer[-1]

        # paused/replay mode
        if 0 <= self.current_index < len(self.buffer):
            current_frame = self.buffer[self.current_index]

            # advance to next frame if on replay mode
            if not (self.isPaused or self.is_live()):
                self.current_index+=1

                # go live if on the last element
                if self.current_index >= len(self.buffer):
                    self.current_index = -1
                    self.isPaused = False

            return current_frame

        return None

    def toggle_pause(self):
        """Toggle pause mode"""
        if self.current_index == -1:
            self.current_index = len(self.buffer) - 1

        self.isPaused = not self.isPaused

    def pause(self):
        """Pause the process"""

        if not self.buffer:
            return None

        self.current_index = len(self.buffer) - 1

    def is_live(self) -> bool:
        """Check if the navigator is live"""
        if not self.buffer or self.current_index >= 0:
            return False
        return True

    def go_live(self) -> bool:
        """Set navigator to live"""
        if not self.buffer:
            return False
        self.current_index = -1
        self.isPaused = False
        return True

    def get_info(self) -> str:
        if self.isPaused:
            return "Paused"
        if self.current_index == -1:
            return "Live"
        return "Replay"

    def handle_key_event(self,event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_LEFT:  # Go back
                if self.go_back():
                    logger.info("Stepped backward")

            elif event.key == pygame.K_RIGHT:  # Go forward
                if self.go_forward():
                    logger.info("Stepped forward")

            elif event.key == pygame.K_RETURN:
                self.go_live()

            elif event.key == pygame.K_SPACE:  # Toggle pause/live
                self.toggle_pause()
