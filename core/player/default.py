from __future__ import annotations

from .dice import Dice
from .player import Player
from .effects import Effect
from typing import TYPE_CHECKING
import math

if TYPE_CHECKING:
    from ...main import GameManager


class DefaultPlayer(Player):
    def __init__(self) -> None:
        super().__init__(
            0, "默认测试卡牌", 30, 3, 3, [Dice(4), Dice(6), Dice(6), Dice(8)]
        )


class DefaultAIPlayer(Player):
    def __init__(self) -> None:
        super().__init__(
            1,
            "默认测试卡牌",
            30,
            3,
            3,
            [Dice(4), Dice(6), Dice(6), Dice(8)],
            is_agent=True,
        )


class ChimeraPlayer(Player):
    def __init__(self) -> None:
        super().__init__(
            2,
            "奇美拉",
            22,
            3,
            2,
            [Dice(4), Dice(4), Dice(6), Dice(6)],
        )

    def after_effect_settle(self, game: GameManager):
        if not self.role == "attacker":
            return
        sum_dict = {}
        for dice in self.selected_dice:
            if dice.now_value not in sum_dict:
                sum_dict[dice.now_value] = 0
            sum_dict[dice.now_value] += 1
        flag = False
        add_sum = 0
        for value, count in sum_dict.items():
            if count >= 2 and not flag:
                add_sum = 3
                if value == 4:
                    add_sum = 7
                    flag = True
        game.attacker_extra_sum += add_sum


class KleSparSparPlayer(Player):
    def __init__(self) -> None:
        super().__init__(
            3,
            "火花花",
            25,
            3,
            2,
            [Dice(4), Dice(4), Dice(6), Dice(6), Dice(8)],
        )

    def after_attack_sum(self, game: GameManager):
        if self.hp != 25:
            self.effects.append(Hack(self))


class BatRaccoonPlayer(Player):
    def __init__(self) -> None:
        super().__init__(
            4,
            "开拓妖精",
            15,
            3,
            3,
            [Dice(4), Dice(4), Dice(4), Dice(6)],
        )

    def after_defence_sum(self, game: GameManager):
        values = [dice.now_value for dice in self.selected_dice]
        if len(values) != len(set(values)):
            self.effects.append(InstantDamage(self, 4, game))

    def before_defence_select(self, game: GameManager):
        game.reload_times += 1


class DormasPlayer(Player):
    def __init__(self) -> None:
        super().__init__(
            5,
            "大地兽",
            26,
            3,
            2,
            [Dice(4), Dice(4), Dice(6), Dice(6)],
        )

    def after_attack_sum(self, game: GameManager):
        for dice in self.selected_dice:
            if dice.now_value % 2 != 0:
                return

        for effect in self.effects:
            if isinstance(effect, Poisoning) and effect.alive:
                effect.layer += 2
                return
        self.effects.append(Poisoning(self, 2))


class RubbishBinPlayer(Player):
    def __init__(self) -> None:
        super().__init__(
            6, "阮·梅造物", 25, 4, 2, [Dice(4), Dice(4), Dice(4), Dice(4), Dice(4)]
        )

    def after_effect_settle(self, game: GameManager):
        if not self.role == "attacker":
            return
        selected_dict = {}
        for dice in self.selected_dice:
            if dice.now_value not in selected_dict:
                selected_dict[dice.now_value] = 0
            selected_dict[dice.now_value] += 1
        max_v = -math.inf
        for count in selected_dict.values():
            max_v = max(max_v, count)
        if not max_v >= 3:
            return
        max_v = int(max_v)
        game.attacker_extra_sum += (max_v - 2) * 7


class TrafficLightPlayer(Player):
    def __init__(self) -> None:
        super().__init__(
            7, "自动机兵·甲虫", 10, 3, 3, [Dice(4), Dice(4), Dice(4), Dice(6)]
        )
        self.get_s_round: int = -1

    def before_defence_select(self, game: GameManager):
        game.reload_times += 1

    def after_defence_sum(self, game: GameManager):
        values = [dice.now_value for dice in self.selected_dice]
        v_set = set(values)
        m_len = 0
        current = 0
        for num in v_set:
            if num - 1 in v_set:
                continue
            current = 1
            while num + 1 in v_set:
                num += 1
                current += 1
            m_len = max(m_len, current)
        if m_len >= 3:
            self.get_s_round = game.round + 1
            self.effects.append(ForceFields(self, True))

    def round_start(self, game: GameManager):
        if game.round == self.get_s_round:
            self.effects.append(Strength(self, 8, True))
            self.get_s_round = -1


class CivetPlayer(Player):
    def __init__(self) -> None:
        super().__init__(
            8, "狸猫记者", 28, 4, 3, [Dice(4), Dice(4), Dice(4), Dice(4), Dice(6)]
        )

    def after_being_attacked(self, game: GameManager, hp_sum: int):
        if hp_sum > 0:
            for dice in self.selected_dice:
                if dice.now_value % 2 == 0:
                    self.effects.append(InstantDamage(self, 2, game))
                    return
            self.effects.append(InstantDamage(self, 4, game))


players = [
    DefaultPlayer(),
    DefaultAIPlayer(),
    ChimeraPlayer(),
    KleSparSparPlayer(),
    BatRaccoonPlayer(),
    DormasPlayer(),
    RubbishBinPlayer(),
    TrafficLightPlayer(),
    CivetPlayer(),
]


class Hack(Effect):
    def __init__(self, master: Player) -> None:
        super().__init__("骇入", False, master)

    def before_sum(self, game: GameManager):
        if not self.alive:
            return
        max_value = -math.inf
        if self.master.role == "attacker":
            for i, dice in enumerate(game.defender.selected_dice):
                if dice.special:
                    continue
                if dice.now_value > max_value:
                    max_value = dice.now_value
                    index = i
            game.defender.selected_dice[index].now_value = 2
        else:
            for i, dice in enumerate(game.attacker.selected_dice):
                if dice.special:
                    continue
                if dice.now_value > max_value:
                    max_value = dice.now_value
                    index = i
            game.attacker.selected_dice[index].now_value = 2
        self.alive = False


class InstantDamage(Effect):
    def __init__(
        self, master: Player, layers: int, game: GameManager | None = None
    ) -> None:
        super().__init__("瞬伤", True, master, layer=layers, game=game)
        if game:
            self.on_denfination(game)

    def on_denfination(self, game: GameManager):
        if not self.alive:
            return
        if self.master.role == "attacker":
            game.defender.hp -= self.layer
        else:
            game.attacker.hp -= self.layer
        self.alive = False


class Poisoning(Effect):
    def __init__(self, master: Player, layers: int) -> None:
        super().__init__("中毒", True, master, layer=layers)

    def after_settlement(self, game: GameManager):
        if not self.alive:
            return
        if self.master.role == "attacker":
            print(f"攻击方中毒效果{self.layer}层生效")
            game.defender.hp -= self.layer
        else:
            print(f"防御方中毒效果{self.layer}层生效")
            game.attacker.hp -= self.layer
        self.layer -= 1
        if self.layer <= 0:
            self.alive = False


class ForceFields(Effect):
    def __init__(self, master: Player, clear: bool):
        super().__init__("力场", False, master, clear=clear)


class Strength(Effect):
    def __init__(self, master: Player, layers: int, clear: bool):
        super().__init__("力量", True, master=master, clear=clear, layer=layers)

    def before_sum(self, game: GameManager):
        if self.master.role == "attacker":
            game.attacker_extra_sum += self.layer
