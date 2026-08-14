"""曜彩骰的单元测试。"""

import pytest

from core.player.default import (
    BigRedButton,
    DefaultAIPlayer,
    DefaultPlayer,
    Double,
    Overload,
    RealCactus,
    RealFate,
    RealGambler,
    RealLastWords,
    RealMiracle,
    RealOath,
    RealRevenge,
    RealStarShield,
    special_dices,
)
from main import GameManager


@pytest.fixture
def game():
    return GameManager(DefaultPlayer(), DefaultAIPlayer(), seed=0)


def test_all_special_dice_registered():
    assert len(special_dices) == 19
    names = [dice.name for dice in special_dices]
    assert names == [
        "真•进化",
        "真•6•6",
        "真•命运",
        "真•复仇",
        "真•医嘱",
        "真•遗语",
        "真•复读",
        "真•仙人球",
        "真•奇迹",
        "真•贷款",
        "真•星盾",
        "真•誓言",
        "真•质数",
        "大红按钮",
        "真•奇术师",
        "真•心跳",
        "真•战狂",
        "真•赌徒",
        "真•魔弹",
    ]


def test_double_multiplies_attacker_total(game):
    game.attacker.effects.append(Double(game.attacker))
    patch = game.attacker.effects[0].before_sum(game.context.create_view())
    assert patch is not None
    assert patch.multiply_attack == 2
    game.context.apply_patch(patch)
    assert game.attacker_multiplier == 2


def test_overload_adds_attack_when_attacking(game):
    overload = Overload(game.attacker, 3)
    patch = overload.before_sum(game.context.create_view())
    assert patch is not None
    assert patch.add_extra_attack == 3


def test_overload_self_damage_when_defending(game):
    game.attacker.role = "defender"
    overload = Overload(game.attacker, 3)
    patch = overload.before_sum(game.context.create_view())
    assert patch is not None
    assert patch.damage == [{"role": "defender", "type": "overload", "count": 1}]


def test_last_stand_sets_hp_to_one_and_adds_attack(game):
    game.attacker.hp = 20
    dice = BigRedButton()
    dice.master = game.attacker
    dice.load(True, game.rng)
    patch = dice.trigger_dice()
    assert patch.add_extra_attack == 19
    game.context.apply_patch(patch)
    assert game.attacker.hp == 1


def test_fated_dice_must_be_selected(game):
    dice = RealFate()
    dice.master = game.attacker
    dice.load(True, game.rng)
    assert dice.must_select
    game.attacker.dices.append(dice)
    view = game.context.create_view()
    assert not game.attacker._legal_select([0, 1, 2], 1, "attack", 2, view)
    index = game.attacker.dices.index(dice)
    assert game.attacker._legal_select([0, 1, index], 1, "attack", 2, view)


def test_revenge_requires_25_damage_taken(game):
    dice = RealRevenge()
    dice.master = game.attacker
    assert not dice.can_use(game.context.create_view())
    game.attacker.total_damage_taken = 25
    assert dice.can_use(game.context.create_view())


def test_gambler_only_first_four_rounds(game):
    dice = RealGambler()
    dice.master = game.attacker
    assert dice.can_use(game.context.create_view())
    game.round = 5
    assert not dice.can_use(game.context.create_view())


def test_big_red_button_requires_round_five(game):
    dice = BigRedButton()
    dice.master = game.attacker
    game.round = 4
    assert not dice.can_use(game.context.create_view())
    game.round = 5
    assert dice.can_use(game.context.create_view())


def test_defense_only_dice(game):
    for dice_type in (RealCactus, RealStarShield, RealOath):
        dice = dice_type()
        dice.master = game.defender
        assert dice.can_use(game.context.create_view())
        dice.master = game.attacker
        assert not dice.can_use(game.context.create_view())


def test_last_words_requires_low_hp(game):
    dice = RealLastWords()
    dice.master = game.attacker
    game.attacker.hp = 9
    assert not dice.can_use(game.context.create_view())
    game.attacker.hp = 8
    assert dice.can_use(game.context.create_view())


def test_miracle_requires_nine_ones(game):
    dice = RealMiracle()
    dice.master = game.attacker
    assert not dice.can_use(game.context.create_view())
    dice.chose_one = 9
    assert dice.can_use(game.context.create_view())
