"""Player._legal_select 合法性校验的单元测试。"""

import pytest

from core.player.default import (
    DefaultAIPlayer,
    DefaultPlayer,
    EvanesciaPlayer,
    RealSixSixDice,
)
from main import GameManager


@pytest.fixture
def view():
    game = GameManager(DefaultPlayer(), DefaultAIPlayer(), seed=0)
    return game.context.create_view()


@pytest.fixture
def player():
    return DefaultPlayer()


def test_confirm_needs_exact_attack_dice_count(player, view):
    assert player._legal_select([0, 1, 2], 1, "attack", 2, view)
    assert not player._legal_select([0, 1], 1, "attack", 2, view)


def test_confirm_rejects_empty_selection(player, view):
    assert not player._legal_select([], 1, "attack", 2, view)


def test_rejects_duplicate_and_out_of_range_indexes(player, view):
    assert not player._legal_select([0, 0, 1], 1, "attack", 2, view)
    assert not player._legal_select([0, 1, 9], 1, "attack", 2, view)


def test_invalid_action_rejected(player, view):
    assert not player._legal_select([0, 1, 2], 0, "attack", 2, view)
    assert not player._legal_select([0, 1, 2], 4, "attack", 2, view)


def test_reroll_requires_remaining_reload_times(player, view):
    assert not player._legal_select([0, 1], 2, "attack", 0, view)
    assert player._legal_select([0, 1], 2, "attack", 2, view)


def test_defence_confirm_uses_defence_dice_count(player, view):
    assert player._legal_select([0, 1, 2], 1, "defence", 0, view)
    assert not player._legal_select([0, 1], 1, "defence", 0, view)


def test_special_dice_requires_availability(player, view):
    assert not player._legal_select([], 3, "attack", 2, view)
    player.special_dice = RealSixSixDice()
    assert player._legal_select([], 3, "attack", 2, view)
    player.use_spe_times = 0
    assert not player._legal_select([], 3, "attack", 2, view)


def test_no_limit_attack_dice(view):
    player = EvanesciaPlayer()
    assert player._legal_select([0], 1, "attack", 0, view)


def test_human_select_reprompts_on_invalid_input(monkeypatch):
    inputs = iter(["0 1 x", "0 1 2", "1"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))
    player = DefaultPlayer()
    game = GameManager(DefaultPlayer(), DefaultAIPlayer(), seed=0)
    action, selected = player.select_dice(
        "attack", 2, game.context.create_view(), game.rng
    )
    assert action == 1
    assert len(selected) == player.attack_dice
