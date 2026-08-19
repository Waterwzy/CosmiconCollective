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
            0,
            "默认测试卡牌",
            30,
            3,
            3,
            [Dice(4), Dice(6), Dice(6), Dice(8)],
            "默认",
            [],
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
            "默认",
            [],
            is_agent=True,
        )


class YellowSpringPlayer(Player):
    def __init__(self) -> None:
        super().__init__(
            2,
            "黄泉",
            33,
            2,
            3,
            [Dice(4), Dice(4), Dice(4), Dice(6), Dice(8)],
            "攻击时：若选定的骰子点数全为4，则本次攻击获得洞穿；每成功触发一次洞穿，攻击等级+1。",
            [Pierce],
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
            3,
            "流萤",
            28,
            4,
            3,
            [Dice(4), Dice(4), Dice(6), Dice(6), Dice(6)],
            "攻击时：若选定的骰子包含2组2个相同点数，则本次攻击获得连击。如果自身满生命值，攻击值+5。",
            [DoubleShot],
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
            4,
            "知更鸟",
            30,
            4,
            3,
            [Dice(4), Dice(4), Dice(4), Dice(6), Dice(6)],
            "攻击时：若选定的骰子全为偶数，则使选定的骰子获得升级。",
            [Upgrade],
        )

    def after_attack_sum(self, view: GameView) -> GamePatch | None:
        for dice in self.selected_dice:
            if dice.now_value % 2 != 0:
                return
        return GamePatch(upgrade_dice_requests=self.selected_dice)


class BigHertaPlayer(Player):
    def __init__(self) -> None:
        super().__init__(
            5,
            "大黑塔",
            42,
            3,
            2,
            [Dice(6), Dice(6), Dice(6), Dice(8), Dice(8)],
            "回合结束时：获得1次曜彩骰使用次数。若已触发4次以上曜彩骰的特殊效果，则此后每回合获得跃升。",
            [Leap],
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
            6,
            "卡芙卡",
            30,
            4,
            3,
            [Dice(4), Dice(4), Dice(4), Dice(6), Dice(6)],
            "攻击时：选定的骰子每有一个不同的点数，便使对方陷入1层中毒。防御失败时，移除对方1层中毒。",
            [Poisoning],
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
            7,
            "砂金",
            33,
            4,
            2,
            [Dice(4), Dice(6), Dice(6), Dice(6), Dice(8)],
            "攻击时：选定的骰子里每有1个奇数，则获得1层韧性。韧性累计至7层时，立即造成7点瞬伤，并移除7层韧性。",
            [Resilience, InstantDamage],
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
            8,
            "三月七",
            25,
            4,
            3,
            [Dice(4), Dice(4), Dice(4), Dice(6), Dice(6)],
            "攻击或防御时：选定的骰子每出现1组2个相同点数，立刻造成3点瞬伤。",
            [InstantDamage],
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
            9,
            "丹恒·腾荒",
            25,
            3,
            2,
            [Dice(6), Dice(6), Dice(6), Dice(8), Dice(8)],
            "攻击时：若攻击值≥18，下次防御时防御等级+3，并获得反击，防御结束将还原至初始防御等级。",
            [AddDefenceLevel, Counterattack],
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
            10,
            "火花",
            22,
            4,
            3,
            [Dice(4), Dice(4), Dice(6), Dice(6), Dice(8)],
            "攻击或防御时：若选定的骰子包含相同点数，则获得骇入。",
            [Hack],
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
            11,
            "爻光",
            35,
            3,
            2,
            [Dice(6), Dice(6), Dice(6), Dice(8), Dice(8)],
            "攻击时：获得4次重投机会；在单回合内超过2次重投后，每次重投会获得2层荆棘。此外，若攻击值≥18，则移除所有荆棘，并获得1次曜彩骰使用次数。",
            [Thorn],
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
            12,
            "昔涟",
            30,
            3,
            2,
            [Dice(4), Dice(6), Dice(6), Dice(6), Dice(8)],
            "将每回合自身的攻击值与防御值进行累加，总计超过24后，攻击等级变为5，此后每回合获得跃升。",
            [AddAttackLevel, Leap],
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
            13,
            "白厄",
            20,
            4,
            2,
            [Dice(6), Dice(6), Dice(6), Dice(8), Dice(8)],
            "攻击时：虹吸自己造成伤害数额50%的生命值。防御时：若选定的骰子点数全部相同，则获得不屈，最多触发1次。",
            [Siphon, Unyield],
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
            14,
            "风堇",
            28,
            2,
            2,
            [Dice(6), Dice(6), Dice(6), Dice(6), Dice(8)],
            "攻击后：将力量层数设置为本次攻击值的50%；若选定的骰子点数全为6，则设置为100%并治愈6点生命值。",
            [Strength, Recover],
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
            15,
            "银狼LV.999",
            36,
            3,
            2,
            [Dice(6), Dice(6), Dice(6), Dice(6), Dice(6)],
            "攻击或防御时：选定的骰子中若包含点数1，则获得跃升；若包含点数6，则获得骇入。跃升和骇入每回合最多只能通过本技能各获得一次。",
            [Hack, Leap],
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
            16,
            "绯英",
            30,
            helper.Select.NO_LIMIT,
            3,
            [Dice(4), Dice(4), Dice(6), Dice(6), Dice(8)],
            "攻击时：可以选定任意数量的骰子（至少一个），本次攻击若选定3个以下骰子则获得连击，若只选定一个骰子则再获得洞穿。",
            [DoubleShot, Pierce],
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
            17,
            "开拓者",
            36,
            3,
            2,
            [Dice(6), Dice(6), Dice(6), Dice(6), Dice(6)],
            "攻击时：选定的骰子中每有一个点数为6，则攻击值+2。重掷时：若将曜彩骰以外的骰子掷出点数6，则恢复一次重掷次数。",
            [],
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
            18,
            "不死途",
            23,
            3,
            3,
            [Dice(4), Dice(4), Dice(6), Dice(6), Dice(8)],
            "攻击未造成伤害时：立刻对自己造成70%攻击值的瞬伤。受到攻击伤害时：反伤自己30%防御值的伤害。",
            [InstantDamage, Counterattack],
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
            19,
            "星期日",
            27,
            4,
            3,
            [Dice(4), Dice(4), Dice(6), Dice(6), Dice(6)],
            "受到攻击伤害时：双方各获得5层荆棘。攻击时：若选定的骰子各不相同，则将自己的荆棘转移给对手。",
            [Thorn],
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
            20,
            "刃",
            49,
            4,
            2,
            [Dice(6), Dice(6), Dice(6), Dice(8), Dice(8)],
            "攻击与防御时均拥有6次重投次数，但每次重投需要消耗2点生命值。",
            [],
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
            21,
            "海瑟音",
            28,
            3,
            3,
            [Dice(4), Dice(4), Dice(4), Dice(4), Dice(6)],
            "攻击时：选定的骰子每有1个点数为偶数，则使对手陷入1层中毒。若全为偶数，则再使对手的中毒立刻结算一次。",
            [Poisoning],
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
            22,
            "阮·梅",
            50,
            2,
            2,
            [Dice(6), Dice(6), Dice(6), Dice(6), Dice(8)],
            "攻击或防御时：若选定的骰子全为连续点数，获得一层进化，否则移除一层进化。",
            [Evolution],
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
            23,
            "姬子",
            33,
            3,
            3,
            [Dice(4), Dice(4), Dice(6), Dice(6), Dice(8)],
            "攻击时：若选定的骰子权威连续点数或相同点数，攻击值+12。",
            [],
        )

    def after_attack_sum(self, view: GameView) -> GamePatch | None:
        v_list = [dice.now_value for dice in self.selected_dice]
        if helper.max_continue_dices(self) == len(v_list) or len(set(v_list)) == 1:
            return GamePatch(add_extra_attack=12)


# =====效果定义部分=====


class Hack(Effect):
    name = "骇入"
    description = (
        "结算前，将对手已选择骰子中点数最大的一颗转变为2点（不会作用于曜彩骰）"
    )

    def __init__(self, master: Player) -> None:
        super().__init__("骇入", False, master)

    def before_sum(self, view: GameView) -> GamePatch | None:
        if not self.alive or self.master.role is None:
            return None
        target_role: Literal["attacker", "defender"] = (
            "defender" if self.master.role == "attacker" else "attacker"
        )
        self.alive = False
        return GamePatch(dice_ops=[(target_role, "lower_highest", 1)])


class InstantDamage(Effect):
    name = "瞬伤"
    description = "无需进入伤害结算环节，立刻造成的伤害"

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
    name = "中毒"
    description = "在回合结算后，将会受到对应层数的伤害，随后使层数-1"

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
    name = "力场"
    description = "生效期间，不会受到常规攻击伤害"

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
    name = "力量"
    description = "在攻击时，提供对应层数的攻击值加成"

    def __init__(self, master: Player, layers: int, clear: bool):
        super().__init__("力量", True, master, clear=clear, layer=layers)

    def before_sum(self, view: GameView) -> GamePatch | None:
        if not self.alive or self.master.role is None:
            return None
        if self.master.role == "attacker":
            return GamePatch(add_extra_attack=self.layer)
        return None


class Disturbance(Effect):
    name = "干扰"
    description = "重投次数被减少"

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
    name = "治愈"
    description = "回复指定点数的生命值"

    def __init__(self, master: Player, layer: int):
        super().__init__("治愈", True, master, layer=layer)

    def on_denfination(self, view: GameView) -> GamePatch | None:
        self.alive = False
        if self.master.role == "attacker":
            return GamePatch(add_attacker_hp=self.layer)
        else:
            return GamePatch(add_defender_hp=self.layer)


class AddAttackLevel(Effect):
    name = "攻击等级"
    description = "攻击时必须选择的骰子数量"

    def __init__(self, master: Player, layer: int):
        super().__init__("攻击等级", True, master, layer=layer)

    def before_select(self, view: GameView) -> GamePatch | None:
        if self.master.role == "attacker" and view.state == "attack":
            return GamePatch(add_attack_dice={"attacker": self.layer})


class AddDefenceLevel(Effect):
    name = "防御等级"
    description = "防御时必须选择的骰子数量"

    def __init__(self, master: Player, layer: int):
        super().__init__("防御等级", True, master, layer=layer)

    def before_select(self, view: GameView) -> GamePatch | None:
        if self.master.role == "defender" and view.state == "defence":
            return GamePatch(add_defence_dice={"defender": self.layer})


class Pierce(Effect):
    name = "洞穿"
    description = "攻击时，无视对方的防御值与力场效果"

    def __init__(self, master: Player, clear: bool = False):
        super().__init__("洞穿", False, master, clear=clear)

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
    name = "连击"
    description = "额外进行1次基于当前攻击值的攻击"

    def __init__(self, master: Player, clear: bool = False):
        super().__init__("连击", False, master, clear=clear)

    def extra_hits(self, view: GameView) -> int:
        return 1

    def after_extra_hits(self, view: GameView) -> GamePatch | None:
        return GamePatch(effects_to_consume=[self])


class Leap(Effect):
    name = "跃升"
    description = "结算前，随机将已选择骰子中点数最小的一颗，转变为该骰子的最大值（不会作用于曜彩骰）"

    def __init__(self, master: Player, clear: bool = False):
        super().__init__("跃升", False, master, clear=clear)

    def before_sum(self, view: GameView) -> GamePatch | None:
        if not self.master.role:
            return GamePatch()
        return GamePatch(dice_ops=[(self.master.role, "raise_lowest", 1)])


class Thorn(Effect):
    name = "荆棘"
    description = "在回合结算前，将会受到对应层数的伤害，结算后清除荆棘"

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
    name = "韧性"
    description = "在防御时，提供对应层数的防御值加成"

    def __init__(self, master: Player, layer: int = 0, clear: bool = False):
        super().__init__("韧性", True, master, layer=layer, clear=clear)

    def before_sum(self, view: GameView) -> GamePatch | None:
        if self.master.role != "defender":
            return GamePatch()
        return GamePatch(add_extra_defence=self.layer)


class Counterattack(Effect):
    name = "反击"
    description = "在受到攻击时，如果防御值更大，对攻击方造成差值伤害"

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
    name = "虹吸"
    description = "攻击时，恢复造成伤害一定比例的生命值"

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
    name = "不屈"
    description = "生效期间，始终保留1点生命值"

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
    name = "进化"
    description = "使攻击时和防御时必选的骰子增加对应层数"

    def __init__(self, master: Player, layer: int = 0):
        super().__init__("进化", True, master, layer=layer)

    def before_select(self, view: GameView) -> GamePatch | None:
        if self.master.role == "attacker" and view.state == "attack":
            return GamePatch(add_attack_dice={"attacker": self.layer})
        if self.master.role == "defender" and view.state == "defence":
            return GamePatch(add_defence_dice={"defender": self.layer})


class Double(Effect):
    """翻倍：本回合己方总点数（已选骰子 + 额外加成）翻倍，可叠加。"""

    name = "翻倍"
    description = "本回合己方总点数（已选骰子 + 额外加成）翻倍，可叠加"

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

    name = "超载"
    description = "攻击时附加与层数相同的攻击值，但防御时对自己造成层数50%的伤害"

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

    name = "背水"
    description = "将自身生命值降低为1，获得降低值的点数加成"

    def __init__(self, master: Player):
        super().__init__("背水", False, master)


class Rainbow(Effect):
    """曜彩标记：获得 1 次曜彩骰使用次数，实际结算在骰子的 trigger_dice 中完成。"""

    name = "曜彩"
    description = "获得1次曜彩骰使用次数"

    def __init__(self, master: Player):
        super().__init__("曜彩", False, master)


class Upgrade(Effect):
    """升级标记，实际结算通过upgrade_dices在GameContext中完成"""

    name = "升级"
    description = "将符合条件的骰子进行稀有度和最大面数提升，最高变为十二面"

    def __init__(self, master: Player):
        super().__init__("升级", False, master)


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
            "随时可用",
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
            "累计选择2次骰面4后，可以在攻击时使用",
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
            "随时可用",
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
            "随时可用",
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
            "随时可用",
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
            "累计受到25点伤害后，可以在攻击时使用",
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
            "随时可用",
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
            "生命值≤8点时可用",
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
            "只能在防御时使用",
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
            "累计选择9次骰面1后，可以在攻击时使用",
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
            "随时可用",
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
            "只能在防御时使用",
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
            "只能在防御时使用",
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
            "随时可用",
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
            "回合数≥5时，可以在攻击时使用",
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
            "随时可用",
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
            "随时可用",
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
            "仅能在前4回合内使用",
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
            "随时可用",
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


# 在文件末尾实例化，确保 related_effects 引用的效果类均已定义
players: list[Player] = [
    DefaultPlayer(),
    DefaultAIPlayer(),
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
