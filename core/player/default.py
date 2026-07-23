from __future__ import annotations

from .dice import Dice
from .player import Player
from .effects import Effect
from . import helper
from ..context import GamePatch, GameView

from typing import Literal


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

    def after_effect_settle(self, view: GameView) -> GamePatch | None:
        if self.role != "attacker":
            return None
        sum_dict: dict[int, int] = {}
        for dice in self.selected_dice:
            sum_dict[dice.now_value] = sum_dict.get(dice.now_value, 0) + 1
        add_sum = 0
        flag = False
        for value, count in sum_dict.items():
            if count >= 2 and not flag:
                add_sum = 3
                if value == 4:
                    add_sum = 7
                    flag = True
        if add_sum == 0:
            return None
        return GamePatch(add_extra_attack=add_sum)


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

    def after_attack_sum(self, view: GameView) -> GamePatch | None:
        if self.hp != 25 and self.role is not None:
            return GamePatch(effects_to_add=[(self.role, Hack(self))])
        return None


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

    def after_defence_sum(self, view: GameView) -> GamePatch | None:
        values = [dice.now_value for dice in self.selected_dice]
        if len(values) != len(set(values)) and self.role is not None:
            return GamePatch(effects_to_add=[(self.role, InstantDamage(self, 4))])
        return None

    def before_defence_select(self, view: GameView) -> GamePatch | None:
        return GamePatch(add_reload_times=1)


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

    def after_attack_sum(self, view: GameView) -> GamePatch | None:
        for dice in self.selected_dice:
            if dice.now_value % 2 != 0:
                return None
        if self.role is not None:
            return GamePatch(effects_to_add=[(self.role, Poisoning(self, 2))])
        return None


class RubbishBinPlayer(Player):
    def __init__(self) -> None:
        super().__init__(
            6, "阮·梅造物", 25, 4, 2, [Dice(4), Dice(4), Dice(4), Dice(4), Dice(4)]
        )

    def after_effect_settle(self, view: GameView) -> GamePatch | None:
        if self.role != "attacker":
            return None
        selected_dict: dict[int, int] = {}
        for dice in self.selected_dice:
            selected_dict[dice.now_value] = selected_dict.get(dice.now_value, 0) + 1
        max_v = max(selected_dict.values(), default=0)
        if max_v < 3:
            return None
        return GamePatch(add_extra_attack=(int(max_v) - 2) * 7)


class TrafficLightPlayer(Player):
    def __init__(self) -> None:
        super().__init__(
            7, "自动机兵·甲虫", 10, 3, 3, [Dice(4), Dice(4), Dice(4), Dice(6)]
        )
        self.get_s_round: int = -1

    def before_defence_select(self, view: GameView) -> GamePatch | None:
        return GamePatch(add_reload_times=1)

    def after_defence_sum(self, view: GameView) -> GamePatch | None:
        if self.role is None:
            return None
        m_len = helper.max_continue_dices(self)
        if m_len >= 3:
            return GamePatch(
                effects_to_add=[(self.role, ForceFields(self, True))],
                player_state_changes=[(self.role, "get_s_round", view.round + 1)],
            )
        return None

    def round_start(self, view: GameView) -> GamePatch | None:
        if self.role is None:
            return None
        if view.round == self.get_s_round:
            return GamePatch(
                effects_to_add=[(self.role, Strength(self, 8, True))],
                player_state_changes=[(self.role, "get_s_round", -1)],
            )
        return None


class CivetPlayer(Player):
    def __init__(self) -> None:
        super().__init__(
            8, "狸猫记者", 28, 4, 3, [Dice(4), Dice(4), Dice(4), Dice(4), Dice(6)]
        )

    def after_being_attacked(self, view: GameView, hp_sum: int) -> GamePatch | None:
        if hp_sum <= 0 or self.role is None:
            return None
        for dice in self.selected_dice:
            if dice.now_value % 2 == 0:
                return GamePatch(effects_to_add=[(self.role, InstantDamage(self, 2))])
        return GamePatch(effects_to_add=[(self.role, InstantDamage(self, 4))])


class ScootPlayer(Player):
    def __init__(self) -> None:
        super().__init__(
            9, "斯科特", 22, 3, 2, [Dice(4), Dice(4), Dice(6), Dice(8), Dice(8)]
        )

    def after_attack_sum(self, view: GameView) -> GamePatch | None:
        if self.role is None:
            return None
        max_c = helper.max_continue_dices(self)
        if max_c < 3:
            return None
        target_role: Literal["attacker", "defender"] = (
            "defender" if self.role == "attacker" else "attacker"
        )
        for effect in view.get_player_view(target_role).effects:
            if isinstance(effect, Disturbance):
                extra_effects: list[tuple[Literal["attacker", "defender"], Effect]] = []
                if effect.layer + 1 >= 2:
                    extra_effects.append((self.role, InstantDamage(self, 5)))
                return GamePatch(
                    effect_layer_changes=[(target_role, Disturbance, 1)],
                    effects_to_add=extra_effects,
                )
        return GamePatch(effects_to_add=[(target_role, Disturbance(target_role, 1))])


class CompanyWorkerPlayer(Player):
    def __init__(self) -> None:
        super().__init__(
            10,
            "基层员工·安保",
            26,
            3,
            2,
            [Dice(4), Dice(4), Dice(6), Dice(6), Dice(8)],
            load_max=False,
        )

    def on_game_start(self, view: GameView) -> GamePatch | None:
        if self.role is None:
            return None
        return GamePatch(effects_to_add=[(self.role, Strength(self, 5, False))])


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
    ScootPlayer(),
    CompanyWorkerPlayer(),
]


class Hack(Effect):
    def __init__(self, master: Player) -> None:
        super().__init__("骇入", False, master)

    def before_sum(self, view: GameView) -> GamePatch | None:
        if not self.alive or self.master.role is None:
            return None
        target_role: Literal["attacker", "defender"] = (
            "defender" if self.master.role == "attacker" else "attacker"
        )
        self.alive = False
        return GamePatch(intend_hack=[(target_role, 1)])


class InstantDamage(Effect):
    def __init__(self, master: Player, layers: int) -> None:
        super().__init__("瞬伤", True, master, layer=layers)

    def on_denfination(self, view: GameView) -> GamePatch | None:
        if not self.alive or self.master.role is None:
            return None
        target_role: Literal["attacker", "defender"] = (
            "defender" if self.master.role == "attacker" else "attacker"
        )
        self.alive = False
        return GamePatch(
            damage=[{"role": target_role, "type": "instant", "count": self.layer}]
        )


class Poisoning(Effect):
    def __init__(self, master: Player, layers: int) -> None:
        super().__init__("中毒", True, master, layer=layers)

    def after_settlement(self, view: GameView) -> GamePatch | None:
        if not self.alive or self.master.role is None:
            return None
        target_role: Literal["attacker", "defender"] = (
            "defender" if self.master.role == "attacker" else "attacker"
        )
        print(
            f"{'攻击方' if self.master.role == 'attacker' else '防御方'}中毒效果{self.layer}层生效"
        )
        return GamePatch(
            damage=[{"role": target_role, "type": "poisoning", "count": self.layer}],
            effect_layer_changes=[(self.master.role, Poisoning, -1)],
        )


class ForceFields(Effect):
    def __init__(self, master: Player, clear: bool):
        super().__init__("力场", False, master, clear=clear)


class Strength(Effect):
    def __init__(self, master: Player, layers: int, clear: bool):
        super().__init__("力量", True, master=master, clear=clear, layer=layers)

    def before_sum(self, view: GameView) -> GamePatch | None:
        if not self.alive or self.master.role is None:
            return None
        if self.master.role == "attacker":
            return GamePatch(add_extra_attack=self.layer)
        return None


class Disturbance(Effect):
    def __init__(self, master: Player | Literal["attacker", "defender"], layers: int):
        # 兼容旧调用中传入 role 字符串的场景；GameContext 会在添加效果前修正 master
        if isinstance(master, str):
            super().__init__("干扰", True, Player(0, "", 0, 0, 0, []), layer=layers)
        else:
            super().__init__("干扰", True, master, layer=layers)

    def before_select(self, view: GameView) -> GamePatch | None:
        if not self.alive or self.master.role is None:
            return None
        if (
            self.master.role == "attacker"
            and view.state == "attack"
            or self.master.role == "defender"
            and view.state == "defence"
        ):
            return GamePatch(add_reload_times=-self.layer)
        return None
