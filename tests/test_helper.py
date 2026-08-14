"""helper 辅助函数的单元测试。"""

from core.player import helper
from core.player.default import DefaultPlayer
from core.player.dice import Dice


def _player_with_values(values: list[int]) -> DefaultPlayer:
    player = DefaultPlayer()
    player.selected_dice = []
    for value in values:
        dice = Dice(6)
        dice.now_value = value
        player.selected_dice.append(dice)
    return player


def test_single_dice_is_length_one():
    assert helper.max_continue_dices(_player_with_values([3])) == 1


def test_consecutive_values():
    assert helper.max_continue_dices(_player_with_values([1, 2, 3])) == 3


def test_scattered_values():
    assert helper.max_continue_dices(_player_with_values([1, 3, 4, 6])) == 2


def test_duplicates_are_collapsed():
    assert helper.max_continue_dices(_player_with_values([2, 2, 3, 5])) == 2
