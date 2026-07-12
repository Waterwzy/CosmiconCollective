from __future__ import annotations

from .player import Player


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
