from __future__ import annotations

from enum import Enum

from .player import Player


class Select(Enum):
    NO_LIMIT = object()

    def __add__(self, other: int):
        return other

    def __radd__(self, other: int):
        return other

    def __iadd__(self, other: int):
        return other

    def __sub__(self, other: int):
        return -other

    def __rsub__(self, other: int):
        return other

    def __isub__(self, other: int):
        return -other


def max_continue_dices(player: Player) -> int:
    num = 0
    current = 0
    max_num = 1
    values = [dice.now_value for dice in player.selected_dice]
    values = set(values)
    for value in values:
        if value - 1 in values:
            continue
        num = value
        current = 1
        while num + 1 in values:
            num += 1
            current += 1
        max_num = max(max_num, current)
    return max_num
