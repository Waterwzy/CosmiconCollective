from __future__ import annotations

from typing import Literal

from ..context import DamageDict, GamePatch, GameView
from . import helper
from .dice import Dice
from .effects import Effect
from .player import Player

# =====玩家定义部分=====


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
                    effects_to_add=extra_effects
                    + [(target_role, Disturbance(self, 1))],
                )
        return GamePatch(effects_to_add=[(target_role, Disturbance(self, 1))])


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


class OverManPlayer(Player):
    def __init__(self) -> None:
        super().__init__(
            11,
            "蕉研组的财富蕉师",
            24,
            4,
            3,
            [Dice(4), Dice(4), Dice(4), Dice(6), Dice(6)],
        )
        self.trigger_once = False

    def before_defence_select(self, view: GameView) -> GamePatch | None:
        return GamePatch(add_reload_times=1)

    def after_settlement(self, view: GameView) -> GamePatch | None:
        patch_list = []
        if not self.trigger_once and self.hp <= 5:
            patch_list.append(
                GamePatch(
                    player_state_changes=[("defender", "trigger_once", True)],
                    effects_to_add=[(self.role, AddDefenceLevel(self, 1))]
                    if self.role
                    else [],
                )
            )
        if self.role == "defender" and not self.attack_in_round:
            patch_list.append(
                GamePatch(effects_to_add=[("defender", Recover(self, 5))])
            )
        if not patch_list:
            return
        return GamePatch.merge_all(patch_list)


class TeamLeaderPlayer(Player):
    def __init__(self) -> None:
        super().__init__(
            12, "资深员工·组长", 22, 3, 2, [Dice(4), Dice(4), Dice(4), Dice(6), Dice(8)]
        )

    def after_attack_sum(self, view: GameView) -> GamePatch | None:
        selected = [dice.now_value for dice in view.attacker.selected_dice]
        return GamePatch(add_extra_attack=len(set(selected)))

    def after_defence_sum(self, view: GameView) -> GamePatch | None:
        selected = [dice.now_value for dice in view.defender.selected_dice]
        return GamePatch(add_extra_defence=len(set(selected)))


class CastoricePlayer(Player):
    def __init__(self) -> None:
        super().__init__(
            13, "遐蝶", 27, 3, 2, [Dice(4), Dice(4), Dice(6), Dice(8), Dice(8)]
        )

    def after_being_attacked(self, view: GameView, hp_sum: int) -> GamePatch | None:
        if hp_sum >= 8 and self.role == "defender":
            return GamePatch(
                effects_to_add=[
                    (self.role, AddDefenceLevel(self, 1)),
                    (self.role, AddAttackLevel(self, 1)),
                ]
            )
        elif hp_sum <= 5 and self.role and hp_sum > 0:
            return GamePatch(effects_to_add=[(self.role, InstantDamage(self, 3))])


class YellowSpringPlayer(Player):
    def __init__(self) -> None:
        super().__init__(
            14, "黄泉", 33, 2, 3, [Dice(4), Dice(4), Dice(4), Dice(6), Dice(8)]
        )

    def after_attack_sum(self, view: GameView) -> GamePatch | None:
        if self.role != "attacker":
            return None
        if all(dice.now_value == 4 for dice in view.attacker.selected_dice):
            return GamePatch(
                effects_to_add=[
                    (self.role, Pierce(self, True)),
                    (self.role, AddAttackLevel(self, 1)),
                ]
            )


class FireflyPlayer(Player):
    def __init__(self) -> None:
        super().__init__(
            15, "流萤", 28, 4, 3, [Dice(4), Dice(4), Dice(6), Dice(6), Dice(6)]
        )

    def after_attack_sum(self, view: GameView) -> GamePatch | None:
        if not self.role:
            return
        v_dict = {}
        patchs = []
        values = [dice.now_value for dice in self.selected_dice]
        for v in values:
            v_dict[v] = v_dict[v] + 1 if v_dict.get(v) else 1
        times = 0
        for v in v_dict.values():
            times += int(v / 2)
        if times >= 2:
            patchs.append(
                GamePatch(effects_to_add=[(self.role, DoubleShot(self, True))])
            )
        if self.hp == self.max_hp:
            patchs.append(GamePatch(add_extra_attack=5))
        return GamePatch.merge_all(patchs)


class RobinPlayer(Player):
    def __init__(self) -> None:
        super().__init__(
            16, "知更鸟", 30, 4, 3, [Dice(4), Dice(4), Dice(4), Dice(6), Dice(6)]
        )

    def after_attack_sum(self, view: GameView) -> GamePatch | None:
        for dice in self.selected_dice:
            if dice.now_value % 2 != 0:
                return
        return GamePatch(upgrade_dice_requests=self.selected_dice)


class BigHertaPlayer(Player):
    def __init__(self) -> None:
        super().__init__(
            17, "大黑塔", 42, 3, 2, [Dice(6), Dice(6), Dice(6), Dice(8), Dice(8)]
        )
        self.use_spe = 0

    def after_settlement(self, view: GameView) -> GamePatch | None:
        self.use_spe_times += 1

    def after_attack_sum(self, view: GameView) -> GamePatch | None:
        if not self.role:
            return GamePatch()
        e = [type(effect) for effect in self.effects if effect.alive]
        if not Leap in e and self.use_spe >= 4:
            return GamePatch(effects_to_add=[(self.role, Leap(self))])

    def after_defence_sum(self, view: GameView) -> GamePatch | None:
        return self.after_attack_sum(view)


class KafukaPlayer(Player):
    def __init__(self) -> None:
        super().__init__(
            18, "卡芙卡", 30, 4, 3, [Dice(4), Dice(4), Dice(4), Dice(6), Dice(6)]
        )

    def after_attack_sum(self, view: GameView) -> GamePatch | None:
        values = [dice.now_value for dice in self.selected_dice]
        return GamePatch(
            effects_to_add=[("attacker", Poisoning(self, len(set(values))))]
        )

    def after_being_attacked(self, view: GameView, hp_sum: int) -> GamePatch | None:
        if hp_sum > 0:
            return GamePatch(effects_to_add=[("defender", Poisoning(self, -1))])


class AventurinePlayer(Player):
    def __init__(self) -> None:
        super().__init__(
            19, "砂金", 33, 4, 2, [Dice(4), Dice(6), Dice(6), Dice(6), Dice(8)]
        )

    def after_attack_sum(self, view: GameView) -> GamePatch | None:
        s = 0
        for dice in self.selected_dice:
            if dice.now_value % 2 == 1:
                s += 1
        return GamePatch(effects_to_add=[("attacker", Resilience(self, s))])

    def on_layer_change(self, changes: list[tuple[Effect, int]]) -> GamePatch | None:
        if not self.role:
            return GamePatch()
        for item in changes:
            if isinstance(item[0], Resilience) and item[1] >= 7:
                return GamePatch(
                    effects_to_add=[
                        (self.role, Resilience(self, -7)),
                        (self.role, InstantDamage(self, 7)),
                    ]
                )


class MartchSeventhPlayer(Player):
    def __init__(self) -> None:
        super().__init__(
            20, "三月七", 25, 4, 3, [Dice(4), Dice(4), Dice(4), Dice(6), Dice(6)]
        )

    def after_attack_sum(self, view: GameView) -> GamePatch | None:
        if not self.role:
            return GamePatch()
        v_list = [dice.now_value for dice in self.selected_dice]
        v_dict = {}
        for v in v_list:
            v_dict[v] = v_dict.get(v, 0) + 1
        dam = 0
        for times in v_dict.values():
            dam += 3 * int(times / 2)
        return GamePatch(effects_to_add=[(self.role, InstantDamage(self, dam))])

    def after_defence_sum(self, view: GameView) -> GamePatch | None:
        return self.after_attack_sum(view)


class DesolateDanHengPlayer(Player):
    def __init__(self) -> None:
        super().__init__(
            21, "丹恒·腾荒", 25, 3, 2, [Dice(6), Dice(6), Dice(6), Dice(8), Dice(8)]
        )
        self.round_add_denfece = -1

    def after_settlement(self, view: GameView) -> GamePatch | None:
        if self.role == "defender" and self.round_add_denfece == view.round:
            self.round_add_denfece = -1
            return GamePatch(effects_to_add=[(self.role, AddDefenceLevel(self, -3))])
        if self.role != "attacker":
            return

        if view.attacker_sum + view.attacker_extra_sum >= 18:
            self.round_add_denfece = view.round + 1

    def round_start(self, view: GameView) -> GamePatch | None:
        if view.round != self.round_add_denfece or self.role != "defender":
            return

        return GamePatch(
            effects_to_add=[
                (self.role, AddDefenceLevel(self, 3)),
                (self.role, Counterattack(self, True)),
            ]
        )


class KleSparPlayer(Player):
    def __init__(self) -> None:
        super().__init__(
            22, "火花", 22, 4, 3, [Dice(4), Dice(4), Dice(6), Dice(6), Dice(8)]
        )

    def after_attack_sum(self, view: GameView) -> GamePatch | None:
        if not self.role:
            return GamePatch()
        vs = [dice.now_value for dice in self.selected_dice]
        if len(vs) != len(set(vs)):
            return GamePatch(effects_to_add=[(self.role, Hack(self))])

    def after_defence_sum(self, view: GameView) -> GamePatch | None:
        return self.after_attack_sum(view)


class YaoGuangPlayer(Player):
    def __init__(self) -> None:
        super().__init__(
            23, "爻光", 35, 3, 2, [Dice(6), Dice(6), Dice(6), Dice(8), Dice(8)]
        )
        self.reload_this_round = 0

    def before_attack_select(self, view: GameView) -> GamePatch | None:
        return GamePatch(add_reload_times=4 - view.reload_times)

    def round_start(self, view: GameView) -> GamePatch | None:
        self.reload_this_round = 0

    def after_reload(self, view: GameView, selected: list[int]) -> GamePatch | None:
        if self.role != "attacker":
            return
        self.reload_this_round += 1
        if self.reload_this_round > 2:
            return GamePatch(effects_to_add=[(self.role, Thorn(self, 2))])

    def after_attack_sum(self, view: GameView) -> GamePatch | None:
        if view.attacker_sum + view.attacker_extra_sum >= 18:
            return GamePatch(
                effects_to_consume=[
                    effect
                    for effect in self.effects
                    if effect.alive and isinstance(effect, Thorn)
                ]
            )


class CyrenePlayer(Player):
    def __init__(self) -> None:
        super().__init__(
            24, "昔涟", 30, 3, 2, [Dice(4), Dice(6), Dice(6), Dice(6), Dice(8)]
        )
        self.all_sum = 0

    def after_settlement(self, view: GameView) -> GamePatch | None:
        if self.role == "attacker":
            self.all_sum += view.attacker_sum + view.attacker_extra_sum
        if self.role == "defender":
            self.all_sum += view.defender_sum + view.defender_extra_sum

    def round_start(self, view: GameView) -> GamePatch | None:
        if not self.role:
            return
        if self.all_sum >= 24 and not Leap in [type(effect) for effect in self.effects]:
            return GamePatch(effects_to_add=[(self.role, Leap(self))])

    def _get_attack_layer(self):
        l = self.ori_attack_dices
        for eff in self.effects:
            if isinstance(eff, AddAttackLevel) and eff.alive:
                l += eff.layer
        return l

    def before_attack_select(self, view: GameView) -> GamePatch | None:
        if not self.role:
            return
        if self.all_sum >= 24:
            return GamePatch(
                effects_to_add=[
                    (self.role, AddAttackLevel(self, 5 - self._get_attack_layer()))
                ]
            )


class PhainonPlayer(Player):
    def __init__(self) -> None:
        super().__init__(
            25, "白厄", 20, 4, 2, [Dice(6), Dice(6), Dice(6), Dice(8), Dice(8)]
        )
        self.has_unyield = False

    def on_game_start(self, view: GameView) -> GamePatch | None:
        if not self.role:
            return
        return GamePatch(effects_to_add=[(self.role, Siphon(self))])

    def after_defence_sum(self, view: GameView) -> GamePatch | None:
        if not self.role:
            return
        v = [dice.now_value for dice in self.selected_dice]
        if len(set(v)) == 1 and not self.has_unyield:
            self.has_unyield = True
            return GamePatch(effects_to_add=[(self.role, Unyield(self, True))])


class HyacinePlayer(Player):
    def __init__(self) -> None:
        super().__init__(
            26, "风堇", 28, 2, 2, [Dice(6), Dice(6), Dice(6), Dice(6), Dice(8)]
        )

    def _get_strength_layers(self):
        for eff in self.effects:
            if isinstance(eff, Strength) and eff.alive:
                return eff.layer
        return 0

    def after_settlement(self, view: GameView) -> GamePatch | None:
        if self.role != "attacker":
            return
        all_sum = view.attacker_sum + view.attacker_extra_sum
        if all(dice.now_value == 6 for dice in self.selected_dice):
            return GamePatch(
                effects_to_add=[
                    (
                        self.role,
                        Strength(self, all_sum - self._get_strength_layers(), False),
                    ),
                    (self.role, Recover(self, 6)),
                ]
            )
        return GamePatch(
            effects_to_add=[
                (
                    self.role,
                    Strength(
                        self, int(all_sum / 2) - self._get_strength_layers(), False
                    ),
                )
            ]
        )


class SliverWolfPlayer(Player):
    def __init__(self) -> None:
        super().__init__(
            27, "银狼LV.999", 36, 3, 2, [Dice(6), Dice(6), Dice(6), Dice(6), Dice(6)]
        )

    def after_attack_sum(self, view: GameView) -> GamePatch | None:
        if not self.role:
            return
        vl = [dice.now_value for dice in self.selected_dice]
        p = GamePatch()
        if 1 in vl:
            p = p.merge(GamePatch(effects_to_add=[(self.role, Leap(self, True))]))
        if 6 in vl:
            p = p.merge(GamePatch(effects_to_add=[(self.role, Hack(self))]))
        return p

    def after_defence_sum(self, view: GameView) -> GamePatch | None:
        return self.after_attack_sum(view)


class EvanesciaPlayer(Player):
    def __init__(self) -> None:
        super().__init__(
            28,
            "绯英",
            30,
            helper.Select.NO_LIMIT,
            3,
            [Dice(4), Dice(4), Dice(6), Dice(6), Dice(8)],
        )

    def after_attack_sum(self, view: GameView) -> GamePatch | None:
        if not self.role:
            return
        eff = []
        if len(self.selected_dice) <= 3:
            eff.append((self.role, DoubleShot(self, True)))
        if len(self.selected_dice) == 1:
            eff.append((self.role, Pierce(self, True)))
        return GamePatch(effects_to_add=eff)


class MyPlayer(Player):
    def __init__(self) -> None:
        super().__init__(
            29, "开拓者", 36, 3, 2, [Dice(6), Dice(6), Dice(6), Dice(6), Dice(6)]
        )

    def after_attack_sum(self, view: GameView) -> GamePatch | None:
        add = 0
        for num in self.selected_dice:
            if num.now_value == 6:
                add += 2
        return GamePatch(add_extra_attack=add)

    def after_reload(self, view: GameView, selected: list[int]) -> GamePatch | None:
        for i in selected:
            if self.dices[i].now_value == 6 and not self.dices[i].special:
                return GamePatch(add_reload_times=1)


class AshveilPlayer(Player):
    def __init__(self) -> None:
        super().__init__(
            30, "不死途", 23, 3, 3, [Dice(4), Dice(4), Dice(6), Dice(6), Dice(8)]
        )

    def after_attack(self, view: GameView, hp_sum: int) -> GamePatch | None:
        if not self.role:
            return
        if hp_sum == 0:
            return GamePatch(
                effects_to_add=[
                    (
                        self.role,
                        InstantDamage(
                            self,
                            int((view.attacker_sum + view.attacker_extra_sum) * 0.7),
                        ),
                    )
                ]
            )

    def after_being_attacked(self, view: GameView, hp_sum: int) -> GamePatch | None:
        if not self.role:
            return
        if hp_sum > 0:
            return GamePatch(
                effects_to_add=[
                    (
                        self.role,
                        InstantDamage(
                            self,
                            int((view.defender_extra_sum + view.defender_sum) * 0.3),
                        ),
                    )
                ]
            )


class SundayPlayer(Player):
    def __init__(self) -> None:
        super().__init__(
            31, "星期日", 27, 4, 3, [Dice(4), Dice(4), Dice(6), Dice(6), Dice(6)]
        )

    def after_being_attacked(self, view: GameView, hp_sum: int) -> GamePatch | None:
        if hp_sum > 0:
            return GamePatch(
                effects_to_add=[
                    ("attacker", Thorn(self, 5)),
                    ("defender", Thorn(self, 5)),
                ]
            )

    def _get_thron_layers(self):
        for eff in self.effects:
            if isinstance(eff, Thorn) and eff.alive:
                return eff.layer
        return 0

    def after_attack_sum(self, view: GameView) -> GamePatch | None:
        if self.role != "attacker":
            return
        v_list = [dice.now_value for dice in self.selected_dice]
        if len(v_list) != len(set(v_list)):
            return
        layers = self._get_thron_layers()
        return GamePatch(
            effects_to_add=[
                ("attacker", Thorn(self, -layers)),
                ("defender", Thorn(self, layers)),
            ]
        )


class BladePlayer(Player):
    def __init__(self) -> None:
        super().__init__(
            32, "刃", 49, 4, 2, [Dice(6), Dice(6), Dice(6), Dice(8), Dice(8)]
        )

    def before_attack_select(self, view: GameView) -> GamePatch | None:
        return GamePatch(add_reload_times=6 - view.reload_times)

    def before_defence_select(self, view: GameView) -> GamePatch | None:
        return self.before_attack_select(view)

    def after_reload(self, view: GameView, selected: list[int]) -> GamePatch | None:
        if not self.role:
            return
        return GamePatch(damage=[{"count": 2, "role": self.role, "type": "blade"}])


class HysilensPlayer(Player):
    def __init__(self) -> None:
        super().__init__(
            33, "海瑟音", 28, 3, 3, [Dice(4), Dice(4), Dice(4), Dice(4), Dice(6)]
        )

    def after_attack_sum(self, view: GameView) -> GamePatch | None:
        if self.role != "attacker":
            return
        v_list = [dice.now_value for dice in self.selected_dice]
        s = 0
        for num in v_list:
            if num % 2 == 0:
                s += 1
        p = GamePatch()
        p = p.merge(GamePatch(effects_to_add=[(self.role, Poisoning(self, s))]))
        if s == len(self.selected_dice):
            p = p.merge(GamePatch(trigger_effects=[(self.role, Poisoning)]))
        return p


class RuanMeiPlayer(Player):
    def __init__(self) -> None:
        super().__init__(
            34, "阮·梅", 50, 2, 2, [Dice(6), Dice(6), Dice(6), Dice(6), Dice(8)]
        )

    def after_attack_sum(self, view: GameView) -> GamePatch | None:
        if not self.role:
            return
        if helper.max_continue_dices(self) == len(self.selected_dice):
            return GamePatch(effects_to_add=[(self.role, Evolution(self, 1))])
        return GamePatch(effects_to_add=[(self.role, Evolution(self, -1))])

    def after_defence_sum(self, view: GameView) -> GamePatch | None:
        return self.after_attack_sum(view)


class HimekoPlayer(Player):
    def __init__(self) -> None:
        super().__init__(
            35, "姬子", 33, 3, 3, [Dice(4), Dice(4), Dice(6), Dice(6), Dice(8)]
        )

    def after_attack_sum(self, view: GameView) -> GamePatch | None:
        v_list = [dice.now_value for dice in self.selected_dice]
        if helper.max_continue_dices(self) == len(v_list) or len(set(v_list)) == 1:
            return GamePatch(add_extra_attack=12)


players: list[Player] = [
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
    OverManPlayer(),
    TeamLeaderPlayer(),
    CastoricePlayer(),
    YellowSpringPlayer(),
    FireflyPlayer(),
    RobinPlayer(),
    BigHertaPlayer(),
    KafukaPlayer(),
    AventurinePlayer(),
    MartchSeventhPlayer(),
    DesolateDanHengPlayer(),
    KleSparPlayer(),
    YaoGuangPlayer(),
    CyrenePlayer(),
    PhainonPlayer(),
    HyacinePlayer(),
    SliverWolfPlayer(),
    EvanesciaPlayer(),
    MyPlayer(),
    AshveilPlayer(),
    SundayPlayer(),
    BladePlayer(),
    HysilensPlayer(),
    RuanMeiPlayer(),
    HimekoPlayer(),
]


# =====效果定义部分=====


class Hack(Effect):
    def __init__(self, master: Player) -> None:
        super().__init__("骇入", False, master)

    def before_sum(self, view: GameView) -> GamePatch | None:
        if not self.alive or self.master.role is None:
            return None
        target_role: Literal["attacker", "defender"] = (
            "defender" if self.master.role == "attacker" else "attacker"
        )
        target = view.get_player_view(target_role)
        candidates = [
            (index, dice.now_value)
            for index, dice in enumerate(target.selected_dice)
            if not dice.special and dice.now_value > 2
        ]
        candidates.sort(key=lambda item: item[1], reverse=True)
        self.alive = False
        return GamePatch(
            dice_value_changes=[(target_role, index, 2) for index, _ in candidates[:1]]
        )


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
            effects_to_add=[(self.master.role, Poisoning(self.master, -1))],
        )

    def trigger(self, view: GameView) -> GamePatch | None:
        if not self.alive or self.master.role is None:
            return None
        target_role: Literal["attacker", "defender"] = (
            "defender" if self.master.role == "attacker" else "attacker"
        )
        print(
            f"{'攻击方' if self.master.role == 'attacker' else '防御方'}中毒效果{self.layer}层生效"
        )
        return GamePatch(
            damage=[{"role": target_role, "type": "poisoning", "count": self.layer}]
        )


class ForceFields(Effect):
    def __init__(self, master: Player, clear: bool):
        super().__init__("力场", False, master, clear=clear)

    def filter_damage(self, damage: DamageDict, view: GameView) -> DamageDict:
        """免疫普通伤害，但无法免疫洞穿。"""
        if damage.get("pierce"):
            return damage
        if damage["role"] != self.master.role or damage["type"] != "common":
            return damage
        return {"role": damage["role"], "type": damage["type"], "count": 0}


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
    def __init__(self, master: Player, layers: int):
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


class Recover(Effect):
    def __init__(self, master: Player, layer: int):
        super().__init__("治愈", True, master, layer)

    def on_denfination(self, view: GameView) -> GamePatch | None:
        self.alive = False
        if self.master.role == "attacker":
            return GamePatch(add_attacker_hp=self.layer)
        else:
            return GamePatch(add_defender_hp=self.layer)


class AddAttackLevel(Effect):
    def __init__(self, master: Player, layer: int):
        super().__init__("攻击等级", True, master, layer)

    def before_select(self, view: GameView) -> GamePatch | None:
        if self.master.role == "attacker" and view.state == "attack":
            return GamePatch(add_attack_dice={"attacker": self.layer})


class AddDefenceLevel(Effect):
    def __init__(self, master: Player, layer: int):
        super().__init__("防御等级", True, master, layer)

    def before_select(self, view: GameView) -> GamePatch | None:
        if self.master.role == "defender" and view.state == "defence":
            return GamePatch(add_defence_dice={"defender": self.layer})


class Pierce(Effect):
    def __init__(self, master: Player, clear: bool = False):
        super().__init__("洞穿", False, master=master, clear=clear)

    def filter_damage(self, damage: DamageDict, view: GameView) -> DamageDict:
        """无视防御点数和力场效果。"""
        if self.master.role != "attacker":
            return damage
        if damage["role"] == self.master.role or damage["type"] != "common":
            return damage
        return {
            "role": damage["role"],
            "type": damage["type"],
            "count": (view.attacker_sum + view.attacker_extra_sum)
            * view.attacker_multiplier,
            "pierce": True,
        }


class DoubleShot(Effect):
    def __init__(self, master: Player, clear: bool = False):
        super().__init__("连击", False, master, clear=clear)

    def extra_hits(self, view: GameView) -> int:
        return 1

    def after_extra_hits(self, view: GameView) -> GamePatch | None:
        return GamePatch(effects_to_consume=[self])


class Leap(Effect):
    def __init__(self, master: Player, clear: bool = False):
        super().__init__("跃升", False, master, clear=clear)

    def before_sum(self, view: GameView) -> GamePatch | None:
        if not self.master.role:
            return GamePatch()
        target = view.get_player_view(self.master.role)
        candidates = [
            (index, dice.now_value)
            for index, dice in enumerate(target.selected_dice)
            if not dice.special
        ]
        if not candidates:
            return GamePatch()
        index, _ = min(candidates, key=lambda item: item[1])
        return GamePatch(
            dice_value_changes=[
                (self.master.role, index, target.selected_dice[index].sides)
            ]
        )


class Thorn(Effect):
    def __init__(self, master: Player, layer: int = 0):
        super().__init__("荆棘", True, master, layer=layer)

    def before_sum(self, view: GameView) -> GamePatch | None:
        if not self.master.role:
            return GamePatch()
        self.alive = False
        return GamePatch(
            damage=[{"type": "thorn", "count": self.layer, "role": self.master.role}]
        )


class Resilience(Effect):
    def __init__(self, master: Player, layer: int = 0, clear: bool = False):
        super().__init__("韧性", True, master, layer, clear)

    def before_sum(self, view: GameView) -> GamePatch | None:
        if self.master.role != "defender":
            return GamePatch()
        return GamePatch(add_extra_defence=self.layer)


class Counterattack(Effect):
    def __init__(self, master: Player, clear: bool = False):
        super().__init__("反击", False, master, clear=clear)

    def after_settlement(self, view: GameView) -> GamePatch | None:
        if self.master.role != "defender":
            return
        ex_defence_num = (
            view.defender_sum + view.defender_extra_sum
        ) * view.defender_multiplier - (
            view.attacker_sum + view.attacker_extra_sum
        ) * view.attacker_multiplier
        if ex_defence_num > 0:
            return GamePatch(
                damage=[
                    {
                        "role": "attacker",
                        "type": "counterattack",
                        "count": ex_defence_num,
                    }
                ]
            )


class Siphon(Effect):
    def __init__(self, master: Player):
        super().__init__("虹吸", False, master)

    def after_damage(self, damage: DamageDict, view: GameView) -> GamePatch | None:
        if self.master.role != "attacker":
            return None
        if damage["role"] == self.master.role:
            return None
        if damage["type"] != "common" or damage["count"] <= 0:
            return None
        return GamePatch(add_attacker_hp=int(damage["count"] * 0.5))


class Unyield(Effect):
    def __init__(self, master: Player, clear: bool = False):
        super().__init__("不屈", False, master, clear=clear)

    def filter_damage(self, damage: DamageDict, view: GameView) -> DamageDict:
        """受到伤害时至少保留 1 点血量。"""
        if damage["role"] != self.master.role:
            return damage
        return {
            "role": damage["role"],
            "type": damage["type"],
            "count": min(damage["count"], self.master.hp - 1),
        }


class Evolution(Effect):
    def __init__(self, master: Player, layer: int = 0):
        super().__init__("进化", True, master, layer=layer)

    def before_select(self, view: GameView) -> GamePatch | None:
        if self.master.role == "attacker" and view.state == "attack":
            return GamePatch(add_attack_dice={"attacker": self.layer})
        if self.master.role == "defender" and view.state == "defence":
            return GamePatch(add_defence_dice={"defender": self.layer})


class Double(Effect):
    """翻倍：本回合己方总点数（已选骰子 + 额外加成）翻倍，可叠加。"""

    def __init__(self, master: Player) -> None:
        super().__init__("翻倍", True, master, layer=1, clear=True)

    def before_sum(self, view: GameView) -> GamePatch | None:
        if not self.alive or self.master.role is None:
            return None
        factor = 2**self.layer
        if self.master.role == "attacker":
            return GamePatch(multiply_attack=factor)
        return GamePatch(multiply_defence=factor)


class Overload(Effect):
    """超载：攻击时附加与层数相同的攻击值，防御时对自己造成层数一半（向下取整）的伤害。"""

    def __init__(self, master: Player, layer: int) -> None:
        super().__init__("超载", True, master, layer=layer)

    def before_sum(self, view: GameView) -> GamePatch | None:
        if not self.alive or self.master.role is None:
            return None
        if self.master.role == "attacker":
            return GamePatch(add_extra_attack=self.layer)
        return GamePatch(
            damage=[
                {
                    "role": self.master.role,
                    "type": "overload",
                    "count": self.layer // 2,
                }
            ]
        )


class LastStand(Effect):
    """背水标记：实际结算在骰子的 trigger_dice 中完成。"""


class Rainbow(Effect):
    """曜彩标记：获得 1 次曜彩骰使用次数，实际结算在骰子的 trigger_dice 中完成。"""


# =====曜彩骰定义部分=====


class RealSixSixDice(Dice):
    def __init__(self) -> None:
        super().__init__(
            6,
            True,
            [
                {"effect": None, "value": 6},
                {"effect": None, "value": 6},
                {"effect": None, "value": 6},
                {"effect": None, "value": 6},
                {"effect": None, "value": 6},
                {"effect": None, "value": 6},
            ],
            "真•6•6",
        )


class RealRepeat(Dice):
    def __init__(self) -> None:
        super().__init__(
            6,
            True,
            [
                {"effect": None, "value": 1},
                {"effect": None, "value": 1},
                {"effect": None, "value": 4},
                {"effect": None, "value": 4},
                {"effect": DoubleShot, "value": 4},
                {"effect": DoubleShot, "value": 4},
            ],
            "真•复读",
        )
        self.chose_four = 0

    def before_sum(self, view: GameView):
        if not self.master:
            return
        for dice in self.master.selected_dice:
            if dice.now_value == 4:
                self.chose_four += 1

    def can_use(self, view: GameView) -> bool:
        if not self.master:
            return False
        return bool(self.master.role == "attacker" and self.chose_four >= 2)

    def trigger_dice(self) -> GamePatch:
        if not self.master or not self.master.role:
            return GamePatch()
        if self.now_effect == DoubleShot:
            return GamePatch(
                effects_to_add=[(self.master.role, DoubleShot(self.master, True))]
            )
        else:
            return GamePatch()


class RealWarManiac(Dice):
    def __init__(self) -> None:
        super().__init__(
            6,
            True,
            [
                {"effect": None, "value": 4},
                {"effect": None, "value": 4},
                {"effect": Thorn, "value": 8},
                {"effect": Thorn, "value": 8},
                {"effect": Thorn, "value": 12},
                {"effect": Thorn, "value": 12},
            ],
            "真•战狂",
        )

    def trigger_dice(self) -> GamePatch:
        if (
            not self.master
            or not self.master.role
            or (self.now_value != 8 and self.now_value != 12)
        ):
            return GamePatch()
        if self.now_value == 8:
            return GamePatch(effects_to_add=[(self.master.role, Thorn(self.master, 2))])
        elif self.now_value == 12:
            return GamePatch(effects_to_add=[(self.master.role, Thorn(self.master, 3))])
        return GamePatch()


class RealEvolution(Dice):
    def __init__(self) -> None:
        super().__init__(
            6,
            True,
            [
                {"effect": None, "value": 3},
                {"effect": None, "value": 3},
                {"effect": None, "value": 4},
                {"effect": None, "value": 4},
                {"effect": None, "value": 6},
                {"effect": Double, "value": 2},
            ],
            "真•进化",
        )

    def trigger_dice(self) -> GamePatch:
        if not self.master or not self.master.role:
            return GamePatch()
        if self.now_effect == Double:
            return GamePatch(effects_to_add=[(self.master.role, Double(self.master))])
        return GamePatch()


class RealFate(Dice):
    def __init__(self) -> None:
        super().__init__(
            6,
            True,
            [
                {"effect": None, "value": 1, "must_select": True},
                {"effect": None, "value": 3, "must_select": True},
                {"effect": None, "value": 3, "must_select": True},
                {"effect": None, "value": 12, "must_select": True},
                {"effect": None, "value": 12, "must_select": True},
                {"effect": None, "value": 16, "must_select": True},
            ],
            "真•命运",
        )


class RealRevenge(Dice):
    def __init__(self) -> None:
        super().__init__(
            6,
            True,
            [
                {"effect": None, "value": 6},
                {"effect": None, "value": 6},
                {"effect": None, "value": 8},
                {"effect": None, "value": 8},
                {"effect": None, "value": 12},
                {"effect": None, "value": 12},
            ],
            "真•复仇",
        )

    def can_use(self, view: GameView) -> bool:
        if not self.master:
            return False
        return bool(
            self.master.role == "attacker" and self.master.total_damage_taken >= 25
        )


class RealMedicalAdvice(Dice):
    def __init__(self) -> None:
        super().__init__(
            6,
            True,
            [
                {"effect": Recover, "value": 1},
                {"effect": Recover, "value": 2},
                {"effect": Recover, "value": 3},
                {"effect": Recover, "value": 4},
                {"effect": Recover, "value": 6},
                {"effect": Recover, "value": 6},
            ],
            "真•医嘱",
        )

    def trigger_dice(self) -> GamePatch:
        if not self.master or not self.master.role:
            return GamePatch()
        if self.now_effect == Recover:
            return GamePatch(
                effects_to_add=[
                    (self.master.role, Recover(self.master, self.now_value))
                ]
            )
        return GamePatch()


class RealLastWords(Dice):
    def __init__(self) -> None:
        super().__init__(
            6,
            True,
            [
                {"effect": None, "value": 4},
                {"effect": None, "value": 5},
                {"effect": None, "value": 5},
                {"effect": Double, "value": 1},
                {"effect": Double, "value": 2},
                {"effect": Double, "value": 4},
            ],
            "真•遗语",
        )

    def can_use(self, view: GameView) -> bool:
        if not self.master:
            return False
        return self.master.hp <= 8

    def trigger_dice(self) -> GamePatch:
        if not self.master or not self.master.role:
            return GamePatch()
        if self.now_effect == Double:
            return GamePatch(effects_to_add=[(self.master.role, Double(self.master))])
        return GamePatch()


class RealCactus(Dice):
    def __init__(self) -> None:
        super().__init__(
            6,
            True,
            [
                {"effect": Counterattack, "value": 4},
                {"effect": Counterattack, "value": 5},
                {"effect": Counterattack, "value": 6},
                {"effect": Counterattack, "value": 7},
                {"effect": Counterattack, "value": 8},
                {"effect": Counterattack, "value": 9},
            ],
            "真•仙人球",
        )

    def can_use(self, view: GameView) -> bool:
        if not self.master:
            return False
        return self.master.role == "defender"

    def trigger_dice(self) -> GamePatch:
        if not self.master or not self.master.role:
            return GamePatch()
        if self.now_effect == Counterattack:
            return GamePatch(
                effects_to_add=[(self.master.role, Counterattack(self.master, True))]
            )
        return GamePatch()


class RealMiracle(Dice):
    def __init__(self) -> None:
        super().__init__(
            6,
            True,
            [
                {"effect": None, "value": 99},
                {"effect": None, "value": 99},
                {"effect": None, "value": 99},
                {"effect": None, "value": 99},
                {"effect": None, "value": 99},
                {"effect": None, "value": 99},
            ],
            "真•奇迹",
        )
        self.chose_one = 0

    def before_sum(self, view: GameView):
        if not self.master:
            return
        for dice in self.master.selected_dice:
            if dice.now_value == 1:
                self.chose_one += 1

    def can_use(self, view: GameView) -> bool:
        if not self.master:
            return False
        return bool(self.master.role == "attacker" and self.chose_one >= 9)


class RealLoan(Dice):
    def __init__(self) -> None:
        super().__init__(
            6,
            True,
            [
                {"effect": Overload, "value": 2},
                {"effect": Overload, "value": 2},
                {"effect": Overload, "value": 3},
                {"effect": Overload, "value": 3},
                {"effect": Overload, "value": 4},
                {"effect": Overload, "value": 4},
            ],
            "真•贷款",
        )

    def trigger_dice(self) -> GamePatch:
        if not self.master or not self.master.role:
            return GamePatch()
        if self.now_effect == Overload:
            return GamePatch(
                effects_to_add=[
                    (self.master.role, Overload(self.master, self.now_value))
                ]
            )
        return GamePatch()


class RealStarShield(Dice):
    def __init__(self) -> None:
        super().__init__(
            6,
            True,
            [
                {"effect": None, "value": 7},
                {"effect": None, "value": 7},
                {"effect": None, "value": 7},
                {"effect": ForceFields, "value": 1},
                {"effect": ForceFields, "value": 1},
                {"effect": ForceFields, "value": 1},
            ],
            "真•星盾",
        )

    def can_use(self, view: GameView) -> bool:
        if not self.master:
            return False
        return self.master.role == "defender"

    def trigger_dice(self) -> GamePatch:
        if not self.master or not self.master.role:
            return GamePatch()
        if self.now_effect == ForceFields:
            return GamePatch(
                effects_to_add=[(self.master.role, ForceFields(self.master, True))]
            )
        return GamePatch()


class RealOath(Dice):
    def __init__(self) -> None:
        super().__init__(
            6,
            True,
            [
                {"effect": None, "value": 8},
                {"effect": None, "value": 8},
                {"effect": Unyield, "value": 4},
                {"effect": Unyield, "value": 4},
                {"effect": Unyield, "value": 6},
                {"effect": Unyield, "value": 6},
            ],
            "真•誓言",
        )

    def can_use(self, view: GameView) -> bool:
        if not self.master:
            return False
        return self.master.role == "defender"

    def trigger_dice(self) -> GamePatch:
        if not self.master or not self.master.role:
            return GamePatch()
        if self.now_effect == Unyield:
            return GamePatch(
                effects_to_add=[(self.master.role, Unyield(self.master, True))]
            )
        return GamePatch()


class RealPrime(Dice):
    def __init__(self) -> None:
        super().__init__(
            6,
            True,
            [
                {"effect": None, "value": 5},
                {"effect": None, "value": 5},
                {"effect": None, "value": 5},
                {"effect": None, "value": 7},
                {"effect": None, "value": 7},
                {"effect": None, "value": 7},
            ],
            "真•质数",
        )


class BigRedButton(Dice):
    def __init__(self) -> None:
        super().__init__(
            6,
            True,
            [
                {"effect": LastStand, "value": 6},
                {"effect": LastStand, "value": 6},
                {"effect": LastStand, "value": 6},
                {"effect": LastStand, "value": 8},
                {"effect": LastStand, "value": 8},
                {"effect": LastStand, "value": 8},
            ],
            "大红按钮",
        )

    def can_use(self, view: GameView) -> bool:
        if not self.master:
            return False
        return bool(self.master.role == "attacker" and view.round >= 5)

    def trigger_dice(self) -> GamePatch:
        if not self.master or not self.master.role or self.now_effect != LastStand:
            return GamePatch()
        reduction = max(0, self.master.hp - 1)
        return GamePatch(
            add_extra_attack=reduction,
            player_state_changes=[(self.master.role, "hp", 1)],
        )


class RealMagician(Dice):
    def __init__(self) -> None:
        super().__init__(
            6,
            True,
            [
                {"effect": None, "value": 4},
                {"effect": None, "value": 4},
                {"effect": None, "value": 4},
                {"effect": Hack, "value": 4},
                {"effect": Hack, "value": 6},
                {"effect": Hack, "value": 6},
            ],
            "真•奇术师",
        )

    def trigger_dice(self) -> GamePatch:
        if not self.master or not self.master.role:
            return GamePatch()
        if self.now_effect == Hack:
            return GamePatch(effects_to_add=[(self.master.role, Hack(self.master))])
        return GamePatch()


class RealHeartbeat(Dice):
    def __init__(self) -> None:
        super().__init__(
            6,
            True,
            [
                {"effect": None, "value": 1},
                {"effect": None, "value": 1},
                {"effect": None, "value": 1},
                {"effect": None, "value": 1},
                {"effect": Rainbow, "value": 9},
                {"effect": Rainbow, "value": 9},
            ],
            "真•心跳",
        )

    def trigger_dice(self) -> GamePatch:
        if not self.master or not self.master.role:
            return GamePatch()
        if self.now_effect == Rainbow:
            return GamePatch(
                player_state_changes=[
                    (self.master.role, "use_spe_times", self.master.use_spe_times + 1)
                ]
            )
        return GamePatch()


class RealGambler(Dice):
    def __init__(self) -> None:
        super().__init__(
            6,
            True,
            [
                {"effect": None, "value": 1},
                {"effect": None, "value": 1},
                {"effect": None, "value": 6},
                {"effect": None, "value": 8},
                {"effect": None, "value": 10},
                {"effect": None, "value": 12},
            ],
            "真•赌徒",
        )

    def can_use(self, view: GameView) -> bool:
        return view.round <= 4


class RealMagicBullet(Dice):
    def __init__(self) -> None:
        super().__init__(
            6,
            True,
            [
                {"effect": None, "value": 3},
                {"effect": None, "value": 5},
                {"effect": None, "value": 7},
                {"effect": InstantDamage, "value": 3},
                {"effect": InstantDamage, "value": 5},
                {"effect": InstantDamage, "value": 7},
            ],
            "真•魔弹",
        )

    def trigger_dice(self) -> GamePatch:
        if not self.master or not self.master.role:
            return GamePatch()
        if self.now_effect == InstantDamage:
            return GamePatch(
                effects_to_add=[
                    (self.master.role, InstantDamage(self.master, self.now_value))
                ]
            )
        return GamePatch()


special_dices = [
    RealEvolution(),
    RealSixSixDice(),
    RealFate(),
    RealRevenge(),
    RealMedicalAdvice(),
    RealLastWords(),
    RealRepeat(),
    RealCactus(),
    RealMiracle(),
    RealLoan(),
    RealStarShield(),
    RealOath(),
    RealPrime(),
    BigRedButton(),
    RealMagician(),
    RealHeartbeat(),
    RealWarManiac(),
    RealGambler(),
    RealMagicBullet(),
]
