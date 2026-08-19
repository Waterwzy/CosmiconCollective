from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .player import Player

from ..context import DamageDict, GamePatch, GameView


class Effect:
    """效果基类。子类需在类体中声明 name 与 description（类级），供 AI / 描述生成使用。"""

    name: str = ""
    description: str = ""

    def __init__(
        self,
        name: str,
        addable: bool,
        master: Player,
        layer: int = 0,
        game=None,
        clear: bool = False,
    ):  # game参数仅适用于有on_defination钩子的效果在实例化时传入
        self.name = name
        """效果名称"""
        self.addable = addable
        """是否可以叠加"""
        self.layer = layer
        """效果叠加层数"""
        self.alive = True
        """效果是否还在生效"""
        self.master = master
        """效果的拥有者"""
        self.clear_after_round = clear
        """在本回合结束后是否需要清除"""

    def before_sum(self, view: GameView) -> GamePatch | None:
        """在计算总点数前触发的效果"""

    def on_denfination(self, view: GameView) -> GamePatch | None:
        """在实例化后立刻触发的效果"""

    def after_settlement(self, view: GameView) -> GamePatch | None:
        """在结算后触发的效果"""

    def before_select(self, view: GameView) -> GamePatch | None:
        """在选择骰子前触发的效果"""

    def trigger(self, view: GameView) -> GamePatch | None:
        """需要特殊触发的效果"""

    def filter_damage(self, damage: DamageDict, view: GameView) -> DamageDict:
        """在伤害落定前修改该次伤害（如“不屈”的钳制、“力场”的免疫），返回修改后的伤害。"""
        return damage

    def after_damage(self, damage: DamageDict, view: GameView) -> GamePatch | None:
        """在某次伤害落定后触发，damage 为实际生效的伤害（如“虹吸”的回血）。"""

    def extra_hits(self, view: GameView) -> int:
        """本效果提供的额外攻击次数（如“连击”），默认 0。"""
        return 0

    def after_extra_hits(self, view: GameView) -> GamePatch | None:
        """所有追加攻击结算完毕后触发（可用于自我消耗）。"""
