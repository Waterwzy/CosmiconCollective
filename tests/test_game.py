"""整局流程的冒烟测试与提前终止测试。"""

from core.context import GamePatch, GameView
from core.player.default import DefaultAIPlayer, ForceFields, Poisoning
from core.player.dice import Dice
from core.player.player import Player
from main import GameManager


class OneShotPlayer(Player):
    """攻击点数永远远超防御，一击必杀。"""

    def __init__(self, pid: int) -> None:
        super().__init__(
            pid,
            "一击必杀测试卡",
            50,
            3,
            3,
            [Dice(6) for _ in range(4)],
            "测试用一击必杀",
            [],
            is_agent=True,
        )

    def after_attack_sum(self, view: GameView) -> GamePatch:
        return GamePatch(add_extra_attack=1000)


def _run(seed: int) -> tuple[int, int, int]:
    game = GameManager(DefaultAIPlayer(), DefaultAIPlayer(), seed=seed)
    game.main()
    return game.round, game.attacker.hp, game.defender.hp


def test_full_game_terminates():
    round_count, attacker_hp, defender_hp = _run(seed=42)
    assert round_count <= 500
    assert attacker_hp <= 0 or defender_hp <= 0
    assert not (attacker_hp <= 0 and defender_hp <= 0)


def test_same_seed_gives_same_result():
    assert _run(seed=7) == _run(seed=7)


def test_round_ends_immediately_when_a_player_dies():
    game = GameManager(OneShotPlayer(101), OneShotPlayer(102), seed=0)
    game.main()
    assert game.round == 1
    assert (game.attacker.hp <= 0) != (game.defender.hp <= 0)


def test_settlement_death_ends_round():
    first = DefaultAIPlayer()
    second = DefaultAIPlayer()
    first.effects.append(ForceFields(first, False))
    second.effects.append(ForceFields(second, False))
    second.effects.append(Poisoning(second, 30))
    game = GameManager(first, second, seed=0)
    game.main()
    assert game.round == 1
    assert (game.attacker.hp <= 0) != (game.defender.hp <= 0)
