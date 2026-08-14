"""GamePatch / GameContext 的单元测试。"""

import pytest

from core.context import GamePatch
from core.player.default import (
    DefaultAIPlayer,
    DefaultPlayer,
    ForceFields,
    Hack,
    Leap,
    Pierce,
    Poisoning,
    Siphon,
    Unyield,
)
from core.player.dice import Dice
from core.player.effects import Effect
from main import GameManager


@pytest.fixture
def game():
    return GameManager(DefaultPlayer(), DefaultAIPlayer(), seed=0)


def _dice_with_values(values: list[int]) -> list[Dice]:
    dices = []
    for value in values:
        dice = Dice(6)
        dice.now_value = value
        dices.append(dice)
    return dices


def test_empty_patch_is_falsy():
    assert not GamePatch()
    assert GamePatch(add_extra_attack=1)


def test_merge_same_damage_accumulates():
    p1 = GamePatch(damage=[{"role": "defender", "type": "common", "count": 5}])
    p2 = GamePatch(damage=[{"role": "defender", "type": "common", "count": 7}])
    merged = p1.merge(p2)
    assert merged.damage == [{"role": "defender", "type": "common", "count": 12}]


def test_merge_keeps_different_damage_types_separate():
    p1 = GamePatch(damage=[{"role": "defender", "type": "common", "count": 5}])
    p2 = GamePatch(damage=[{"role": "defender", "type": "poisoning", "count": 3}])
    merged = p1.merge(p2)
    assert len(merged.damage) == 2
    assert {"role": "defender", "type": "common", "count": 5} in merged.damage
    assert {"role": "defender", "type": "poisoning", "count": 3} in merged.damage


def test_merge_concatenates_dice_value_changes():
    p1 = GamePatch(dice_value_changes=[("defender", 0, 2)])
    p2 = GamePatch(dice_value_changes=[("defender", 1, 6)])
    merged = p1.merge(p2)
    assert merged.dice_value_changes == [("defender", 0, 2), ("defender", 1, 6)]


def test_merge_accumulates_dice_ops():
    p1 = GamePatch(dice_ops=[("defender", "raise_lowest", 1)])
    p2 = GamePatch(dice_ops=[("defender", "raise_lowest", 2)])
    merged = p1.merge(p2)
    assert merged.dice_ops == [("defender", "raise_lowest", 3)]


def test_apply_damage_reduces_hp_and_clamps_at_zero(game):
    before = game.defender.hp
    game.context.apply_patch(
        GamePatch(damage=[{"role": "defender", "type": "common", "count": before + 10}])
    )
    assert game.defender.hp == 0


def test_unyield_clamps_damage_to_keep_one_hp(game):
    game.defender.effects.append(Unyield(game.defender, False))
    game.context.apply_patch(
        GamePatch(damage=[{"role": "defender", "type": "common", "count": 100}])
    )
    assert game.defender.hp == 1


def test_siphon_heals_attacker_on_common_damage(game):
    game.attacker.effects.append(Siphon(game.attacker))
    game.attacker.hp = 10
    game.context.apply_patch(
        GamePatch(damage=[{"role": "defender", "type": "common", "count": 10}])
    )
    assert game.attacker.hp == 15


def test_siphon_ignores_non_common_damage(game):
    game.attacker.effects.append(Siphon(game.attacker))
    game.attacker.hp = 10
    game.context.apply_patch(
        GamePatch(damage=[{"role": "defender", "type": "poisoning", "count": 10}])
    )
    assert game.attacker.hp == 10


def test_force_fields_blocks_common_damage(game):
    game.defender.effects.append(ForceFields(game.defender, False))
    before = game.defender.hp
    game.context.apply_patch(
        GamePatch(damage=[{"role": "defender", "type": "common", "count": 10}])
    )
    assert game.defender.hp == before


def test_pierce_ignores_defence_and_force_fields(game):
    game.attacker.effects.append(Pierce(game.attacker))
    game.defender.effects.append(ForceFields(game.defender, False))
    game.attacker.selected_dice = _dice_with_values([3, 4, 5])
    before = game.defender.hp
    game.context.apply_patch(
        GamePatch(damage=[{"role": "defender", "type": "common", "count": 1}])
    )
    assert game.defender.hp == before - 12


def test_hack_effect_sets_largest_dice_to_two(game):
    game.defender.selected_dice = _dice_with_values([6, 5, 3])
    hack = Hack(game.attacker)
    patch = hack.before_sum(game.context.create_view())
    assert patch is not None
    game.context.apply_patch(patch)
    assert [dice.now_value for dice in game.defender.selected_dice] == [2, 5, 3]


def test_leap_effect_sets_lowest_dice_to_max(game):
    game.attacker.selected_dice = _dice_with_values([6, 1, 4])
    leap = Leap(game.attacker)
    patch = leap.before_sum(game.context.create_view())
    assert patch is not None
    game.context.apply_patch(patch)
    assert [dice.now_value for dice in game.attacker.selected_dice] == [6, 6, 4]


def test_stacked_raise_lowest_ops_raise_distinct_dice(game):
    """多个跃升叠加时，每次操作都要重新计算当前最低的骰子。"""
    game.attacker.selected_dice = _dice_with_values([1, 2, 5])
    game.context.apply_patch(GamePatch(dice_ops=[("attacker", "raise_lowest", 2)]))
    assert [dice.now_value for dice in game.attacker.selected_dice] == [6, 6, 5]


def test_stacked_lower_highest_ops_lower_distinct_dice(game):
    """多个骇入叠加时，最大的多颗骰子分别被改为 2。"""
    game.defender.selected_dice = _dice_with_values([6, 5, 3])
    game.context.apply_patch(GamePatch(dice_ops=[("defender", "lower_highest", 2)]))
    assert [dice.now_value for dice in game.defender.selected_dice] == [2, 2, 3]


def test_reload_times_clamp_at_zero(game):
    game.reload_times = 3
    game.context.apply_patch(GamePatch(add_reload_times=-5))
    assert game.reload_times == 0


def test_dice_value_changes(game):
    game.defender.selected_dice = _dice_with_values([1])
    game.context.apply_patch(GamePatch(dice_value_changes=[("defender", 0, 9)]))
    assert game.defender.selected_dice[0].now_value == 9


def test_effects_to_consume(game):
    effect = Effect("测试效果", False, game.defender)
    game.defender.effects.append(effect)
    game.context.apply_patch(GamePatch(effects_to_consume=[effect]))
    assert not effect.alive


def test_trigger_effects(game):
    game.defender.effects.append(Poisoning(game.defender, 3))
    before = game.attacker.hp
    game.context.apply_patch(GamePatch(trigger_effects=[("defender", Poisoning)]))
    assert game.attacker.hp == before - 3


def test_add_attack_dice_capped_by_total_dice(game):
    game.context.apply_patch(GamePatch(add_attack_dice={"attacker": 10}))
    assert game.attacker.attack_dice == game.attacker.ori_max_dices


def test_heal_capped_at_max_hp(game):
    game.attacker.hp = 25
    game.context.apply_patch(GamePatch(add_attacker_hp=10))
    assert game.attacker.hp == game.attacker.max_hp
