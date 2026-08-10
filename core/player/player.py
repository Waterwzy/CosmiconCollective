from __future__ import annotations

import random
from typing import TYPE_CHECKING, Literal

from ..context import GamePatch, GameView
from .dice import Dice
from .effects import Effect

if TYPE_CHECKING:
    from .helper import Select


class Player:
    """卡牌数据"""

    def __init__(
        self,
        pid: int,
        id: str,
        hp: int,
        attack_dice: int | Select,
        defence_dice: int | Select,
        dices: list[Dice],
        flash_times: int = 0,
        special_dice: Dice | None = None,
        is_agent: bool = False,
        load_max: bool = True,
    ) -> None:
        self.pid = pid
        """角色id(唯一标识)"""
        self.id = id
        """角色名称"""
        self.hp = hp
        """角色血量"""
        self.max_hp = hp
        """角色最大血量（血量上限）"""
        self.attack_dice = attack_dice
        """攻击可用骰子数量"""
        self.defence_dice = defence_dice
        """防御可用骰子数量"""
        self.dices = dices
        """当前可用的骰子"""
        self.ori_max_dices = len(self.dices)
        """原本最大可用骰子数量"""
        self.ori_attack_dices = attack_dice
        """原本攻击骰子数量"""
        self.ori_denfece_dices = defence_dice
        """原本防御骰子数量"""
        self.flash_times = flash_times
        """镀闪次数"""
        self.special_dice = special_dice
        """可用的曜彩骰"""
        self.use_spe_times = 2
        """曜彩骰可用次数"""
        self.selected_dice: list[Dice] = []
        """选择的骰子，用于重投或者攻击/防御"""
        self.effects: list[Effect] = []
        """角色的效果列表"""
        self.is_agent = is_agent
        """是否是AI角色"""
        self.role: Literal["attacker", "defender"] | None = None
        """角色的身份，攻击方或防御方"""
        self.load_max = load_max
        """骰子是否可以投出最大值"""
        self.attack_in_round = False
        """当前回合中是否受到伤害"""

    def __str__(self) -> str:
        return f"{self.id}(pid:{self.pid})"

    def __repr__(self) -> str:
        return self.__str__()

    def _legal_select(
        self,
        selected: list[int],
        action: int | None,
        role: Literal["attack", "defence"],
        reload_times: int,
        view: GameView,
    ) -> bool:
        from .helper import Select

        if action != 1 and action != 2 and action != 3:
            return False
        if not selected and (action == 1 or action == 2):
            return False
        if action == 3:
            if self.use_spe_times <= 0:
                return False
            if not self.special_dice:
                return False
            if not self.special_dice.can_use(view):
                return False
            return not any(dice.special for dice in self.dices)
        if action == 2 and reload_times <= 0:
            return False
        if len(selected) != len(set(selected)):
            return False
        for i in selected:
            if i < 0 or i >= len(self.dices):
                return False
        if action == 1:
            if role == "attack":
                if self.attack_dice == Select.NO_LIMIT:
                    return True
                return len(selected) == self.attack_dice
            elif role == "defence":
                if self.defence_dice == Select.NO_LIMIT:
                    return True
                return len(selected) == self.defence_dice
        return True

    def select_dice(
        self, role: Literal["attack", "defence"], reload_times: int, view: GameView
    ) -> tuple[int, list]:
        """
        Returns: tuple(action , list)
            action(int):操作类型，1为确认 2为重投 3使用曜彩骰
            act_list(list):操作骰子列表
        """
        if self.is_agent:
            if self.role == "attacker":
                if isinstance(self.attack_dice, int):
                    return (
                        1,
                        random.sample(
                            range(len(self.dices)),
                            self.attack_dice,
                        ),
                    )
                else:
                    return (
                        1,
                        random.sample(
                            range(len(self.dices)), random.randint(1, len(self.dices))
                        ),
                    )
            elif self.role == "defender":
                if isinstance(self.defence_dice, int):
                    return (
                        1,
                        random.sample(
                            range(len(self.dices)),
                            self.defence_dice,
                        ),
                    )
                else:
                    return (
                        1,
                        random.sample(
                            range(len(self.dices)), random.randint(1, len(self.dices))
                        ),
                    )
        select_list = []
        action = None
        while not self._legal_select(select_list, action, role, reload_times, view):
            select_list = list(
                map(
                    int,
                    input(
                        f"输入骰子的index，确认可用骰子数量为{self.attack_dice if role == 'attack' else self.defence_dice}\n"
                    ).split(),
                )
            )
            action = int(input("输入你的行为（1为确认2为重投3为使用曜彩骰）"))
        assert action is not None
        return action, select_list

    def begin_attack(self, view: GameView, hurts: int) -> GamePatch:
        """角色遭受攻击后的行为，返回包含伤害与受击后效果的 GamePatch。

        力场（ForceFields）只免疫普通伤害（common），受击后效果仍然可以触发。
        洞穿（Pierce）无视防御和力场效果。
        连击（DoubleShot）的多次攻击由 GameManager 统一结算，本方法只计算一次攻击。
        """
        from .default import ForceFields, Pierce

        if self.role is None:
            return GamePatch()
        has_forcefield = any(
            isinstance(effect, ForceFields) and effect.alive for effect in self.effects
        )

        has_pierce = any(
            isinstance(effect, Pierce) and effect.alive
            for effect in view.attacker.effects
        )
        if has_pierce:
            common_damage = view.attacker_sum + view.attacker_extra_sum
        elif has_forcefield:
            common_damage = 0
        else:
            common_damage = hurts
        damage_patch = GamePatch(
            damage=[{"role": self.role, "type": "common", "count": common_damage}]
        )
        after_patch = self.after_being_attacked(view, common_damage)
        if after_patch is None:
            after_patch = GamePatch()
        return damage_patch.merge(after_patch)

    def clear_effects(self):
        self.effects = [
            eff for eff in self.effects if eff.alive and not eff.clear_after_round
        ]

    def _rm_outdate_effects(self):
        self.effects = [eff for eff in self.effects if eff.alive]

    def add_effect(self, effect: Effect) -> tuple[bool, GamePatch]:
        """添加效果。若目标已有同类可叠加且存活的效果，则叠加层数并返回 False；否则新增实例并返回 True。"""
        self._rm_outdate_effects()
        if effect.addable:
            b = True
            p = GamePatch()
            for eff in self.effects:
                if isinstance(eff, type(effect)) and eff.alive:
                    eff.layer += effect.layer
                    if eff.layer <= 0:
                        eff.alive = False
                        return False, GamePatch()
                    b = False
                    op = self.on_layer_change([(eff, eff.layer)])
                    p = p.merge(op) if op else p
                    break
            if effect.layer <= 0:
                return False, GamePatch()
            if b:
                self.effects.append(effect)
                op = self.on_layer_change([(effect, effect.layer)])
                p = p.merge(op) if op else p
            return (b, p)
        else:
            self.effects.append(effect)
            return (True, GamePatch())

    def after_attack_sum(self, view: GameView) -> GamePatch | None:
        pass

    def after_defence_sum(self, view: GameView) -> GamePatch | None:
        pass

    def before_attack_select(self, view: GameView) -> GamePatch | None:
        pass

    def before_defence_select(self, view: GameView) -> GamePatch | None:
        pass

    def after_effect_settle(self, view: GameView) -> GamePatch | None:
        pass

    def round_start(self, view: GameView) -> GamePatch | None:
        pass

    def after_being_attacked(self, view: GameView, hp_sum: int) -> GamePatch | None:
        pass

    def on_game_start(self, view: GameView) -> GamePatch | None:
        pass

    def after_settlement(self, view: GameView) -> GamePatch | None:
        pass

    def on_layer_change(
        self, changes: list[tuple[Effect, int]]
    ) -> GamePatch | None:  # int 值为改变后的层数
        pass

    def after_reload(self, view: GameView) -> GamePatch | None:
        pass
