from __future__ import annotations

from .dice import Dice
from .effects import Effect
from ..context import GamePatch, GameView
from typing import Literal
import random


class Player:
    """卡牌数据"""

    def __init__(
        self,
        pid: int,
        id: str,
        hp: int,
        attack_dice: int,
        defence_dice: int,
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
        self.flash_times = flash_times
        """镀闪次数"""
        self.special_dice = special_dice
        """可用的曜彩骰"""
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
        """当前回合中是否收到伤害"""

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
    ) -> bool:
        if action != 1 and action != 2:
            return False
        if not selected:
            return False
        if action == 2 and reload_times <= 0:
            return False
        if len(selected) != len(set(selected)):
            return False
        for i in selected:
            if i < 0 or i >= len(self.dices):
                return False
        if action == 1:
            if role == "attack" and len(selected) != self.attack_dice:
                return False
            elif role == "defence" and len(selected) != self.defence_dice:
                return False
        return True

    def select_dice(
        self, role: Literal["attack", "defence"], reload_times: int
    ) -> tuple[int, list]:
        """
        Returns: tuple(action , list)
            action(int):操作类型，1为确认 2为重投
            act_list(list):操作骰子列表
        """
        if self.is_agent:
            return (
                1,
                random.sample(
                    range(len(self.dices)),
                    self.attack_dice if role == "attack" else self.defence_dice,
                ),
            )
        select_list = []
        action = None
        while not self._legal_select(select_list, action, role, reload_times):
            select_list = list(
                map(
                    int,
                    input(
                        f"输入骰子的index，确认可用骰子数量为{self.attack_dice if role == 'attack' else self.defence_dice}\n"
                    ).split(),
                )
            )
            action = int(input("输入你的行为（1为确认2为重投）"))
        assert action is not None
        return action, select_list

    def begin_attack(self, view: GameView, hurts: int) -> GamePatch:
        """角色遭受攻击后的行为，返回包含伤害与受击后效果的 GamePatch。

        力场（ForceFields）只免疫普通伤害（common），受击后效果仍然可以触发。
        """
        from .default import ForceFields

        if self.role is None:
            return GamePatch()
        has_forcefield = any(
            isinstance(effect, ForceFields) and effect.alive for effect in self.effects
        )
        common_damage = 0 if has_forcefield else hurts
        damage_patch = GamePatch(
            damage=[{"role": self.role, "type": "common", "count": common_damage}]
        )
        after_patch = self.after_being_attacked(view, hurts)
        if after_patch is None:
            after_patch = GamePatch()
        return damage_patch.merge(after_patch)

    def clear_effects(self):
        self.effects = [
            eff for eff in self.effects if eff.alive and not eff.clear_after_round
        ]

    def _rm_outdate_effects(self):
        self.effects = [eff for eff in self.effects if eff.alive]

    def add_effect(self, effect: Effect):
        self._rm_outdate_effects()
        if effect.addable:
            flag = False
            for eff in self.effects:
                if isinstance(eff, type(effect)):
                    eff.layer += effect.layer
                    flag = True
            if not flag:
                self.effects.append(effect)
        else:
            self.effects.append(effect)

    def after_attack_sum(self, view: GameView) -> GamePatch | None:
        pass

    def after_defence_sum(self, view: GameView) -> GamePatch | None:
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
