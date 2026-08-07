from __future__ import annotations

import random
from typing import TYPE_CHECKING, Type

from loguru import logger

if TYPE_CHECKING:
    from ..context import GameView, GamePatch
    from .effects import Effect
    from .player import Player


class Dice:
    """骰子数据，可以是曜彩骰"""

    def __init__(
        self,
        sides: int,
        special: bool = False,
        details: list[dict] | None = None,
        name: str | None = None,
    ) -> None:
        self.sides = sides
        """骰子的面数"""
        self.special = special
        """骰子是否为曜彩骰"""
        self.details = details
        """曜彩骰的特殊效果详情，非曜彩骰为None"""
        # 样式示例：列表长度需要为6，例如[{"effect":"some_effect","value":8},{},...]
        self.now_value: int = 0
        """目前骰子的面数"""
        self.now_effect: None | Type[Effect] = None
        """目前的效果，无则为None"""
        self.name: None | str = name
        """曜彩骰的名称"""
        self.master: None | Player = None

    def __str__(self) -> str:
        if self.special:
            return f"曜彩骰{self.name}，当前点数为{self.now_value}，当前效果为{self.now_effect}"
        else:
            return f"普通骰子，当前点数为{self.now_value}/{self.sides}"

    def __repr__(self) -> str:
        return self.__str__()

    def upgrade(self):
        if self.special:
            logger.warning("曜彩骰无法升级")
            return
        if self.sides == 4:
            self.sides = 6
        elif self.sides == 6:
            self.sides = 8
        elif self.sides == 8:
            self.sides = 12
        elif self.sides == 12:
            logger.warning("骰子已经到12点，无法继续升级")

    def load(self, load_max: bool):
        """投骰子，可以用于初始投掷或者重投"""
        if self.special:
            side = random.randint(0, 5)
            self.now_value = self.details[side]["value"]  # type:ignore
            self.now_effect = self.details[side]["effect"]  # type:ignore
        else:
            if load_max:
                self.now_value = random.randint(1, self.sides)
            else:
                self.now_value = random.randint(1, self.sides - 1)

    def can_use(self, view: GameView) -> bool:
        """描述曜彩骰是否可用，子类重写此方法"""
        return True

    def trigger_dice(self) -> GamePatch:
        """曜彩骰触发效果"""
        return GamePatch()

    def before_sum(self, view: GameView):
        return
