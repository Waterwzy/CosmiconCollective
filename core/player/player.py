from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...main import GameManager
from .dice import Dice
from .effects import Effect
from typing import Literal
import random
import weakref


class Player:
    _instances = []

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
        self._instances.append(weakref.ref(self))

    def __str__(self) -> str:
        return f"{self.id}(pid:{self.pid})"

    def __repr__(self) -> str:
        return self.__str__()

    @classmethod
    def get_instances(cls):
        cls._instances = [ref for ref in cls._instances if ref() is not None]
        return cls._instances

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

    def begin_attack(self, hurts: int, game: GameManager):
        """角色遭受攻击后的行为"""
        from .default import ForceFields

        for effect in self.effects:
            if isinstance(effect, ForceFields) and effect.alive:
                return
        self.hp -= hurts
        self.after_being_attacked(game, hurts)

    def after_attack_sum(self, game: GameManager):
        pass

    def after_defence_sum(self, game: GameManager):
        pass

    def before_defence_select(self, game: GameManager):
        pass

    def after_effect_settle(self, game: GameManager):
        pass

    def round_start(self, game: GameManager):
        pass

    def after_being_attacked(self, game: GameManager, hp_sum: int):
        pass

    def on_game_start(self, game: GameManager):
        pass
