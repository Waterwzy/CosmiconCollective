from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .player import Player

from ..context import GamePatch, GameView


class Effect:
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
        pass

    def on_denfination(self, view: GameView) -> GamePatch | None:
        """在实例化后立刻触发的效果"""
        pass

    def after_settlement(self, view: GameView) -> GamePatch | None:
        """在结算后触发的效果"""
        pass

    def before_select(self, view: GameView) -> GamePatch | None:
        """在选择骰子前触发的效果"""
        pass
