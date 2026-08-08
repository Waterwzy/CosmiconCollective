from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Literal, TypedDict

from .player.dice import Dice

if TYPE_CHECKING:
    from ..main import GameManager
    from .player.effects import Effect
    from .player.player import Player


class PlayerView:
    """对 Player 的只读视图。效果逻辑通过它读取角色状态，禁止直接修改内部对象。"""

    def __init__(self, player: Player) -> None:
        self._player = player

    @property
    def pid(self) -> int:
        return self._player.pid

    @property
    def id(self) -> str:
        return self._player.id

    @property
    def hp(self) -> int:
        return self._player.hp

    @property
    def attack_dice(self) -> int:
        return self._player.attack_dice

    @property
    def defence_dice(self) -> int:
        return self._player.defence_dice

    @property
    def dices(self) -> tuple[Dice, ...]:
        """返回当前可用骰子的只读元组。"""
        return tuple(self._player.dices)

    @property
    def flash_times(self) -> int:
        return self._player.flash_times

    @property
    def special_dice(self):
        return self._player.special_dice

    @property
    def selected_dice(self) -> tuple:
        """返回已选择骰子的只读元组。"""
        return tuple(self._player.selected_dice)

    @property
    def effects(self) -> tuple:
        """返回效果列表的只读元组。"""
        return tuple(self._player.effects)

    @property
    def is_agent(self) -> bool:
        return self._player.is_agent

    @property
    def role(self) -> Literal["attacker", "defender"] | None:
        return self._player.role

    @property
    def load_max(self) -> bool:
        return self._player.load_max

    def has_effect(self, effect_type: type) -> bool:
        """判断是否拥有指定类型的效果。"""
        return any(isinstance(eff, effect_type) for eff in self._player.effects)


class GameView:
    """对 GameManager 的只读视图，同一时间触发的效果会收到同一个快照。"""

    def __init__(self, game: GameManager) -> None:
        self._game = game
        self._attacker_view = PlayerView(game.attacker)
        self._defender_view = PlayerView(game.defender)

    @property
    def attacker(self) -> PlayerView:
        return self._attacker_view

    @property
    def defender(self) -> PlayerView:
        return self._defender_view

    @property
    def round(self) -> int:
        return self._game.round

    @property
    def attacker_extra_sum(self) -> int:
        return self._game.attacker_extra_sum

    @property
    def defender_extra_sum(self) -> int:
        return self._game.defender_extra_sum

    @property
    def reload_times(self) -> int:
        return self._game.reload_times

    @property
    def state(self) -> Literal["begin", "attack", "defence", "sum"] | None:
        return self._game.state

    @property
    def attacker_sum(self) -> int:
        return self._game.attacker_sum

    @property
    def defender_sum(self) -> int:
        return self._game.defender_sum

    def get_player_view(self, role: Literal["attacker", "defender"]) -> PlayerView:
        return self.attacker if role == "attacker" else self.defender


class DamageDict(TypedDict):
    role: Literal["attacker", "defender"]
    type: Literal["common", "poisoning", "instant", "thorn"]
    count: int


class GamePatch:
    """描述一次对游戏状态的修改意图。"""

    def __init__(
        self,
        damage: list[DamageDict] | None = None,
        add_reload_times: int = 0,
        add_extra_attack: int = 0,
        add_extra_defence: int = 0,
        add_attacker_hp: int = 0,
        add_defender_hp: int = 0,
        add_attack_dice: dict[Literal["attacker", "defender"], int] | None = None,
        add_defence_dice: dict[Literal["attacker", "defender"], int] | None = None,
        effects_to_add: list[tuple[Literal["attacker", "defender"], Effect]]
        | None = None,
        dice_value_changes: list[tuple[Literal["attacker", "defender"], int, int]]
        | None = None,
        upgrade_dice_requests: list[Dice] | None = None,
        player_state_changes: list[tuple[Literal["attacker", "defender"], str, Any]]
        | None = None,
        intend_hack: list[tuple[Literal["attacker", "defender"], int]] | None = None,
        intend_leap: list[tuple[Literal["attacker", "defender"], int]] | None = None,
        effects_to_consume: Sequence[Effect] | None = None,
    ) -> None:
        self.damage: list[DamageDict] = damage if damage is not None else []
        self.add_reload_times = add_reload_times
        self.add_extra_attack = add_extra_attack
        self.add_extra_defence = add_extra_defence
        self.add_attacker_hp = add_attacker_hp
        self.add_defender_hp = add_defender_hp
        self.add_attack_dice = add_attack_dice if add_attack_dice is not None else {}
        self.add_defence_dice = add_defence_dice if add_defence_dice is not None else {}
        self.effects_to_add: list[tuple[Literal["attacker", "defender"], Effect]] = (
            effects_to_add if effects_to_add is not None else []
        )
        self.dice_value_changes: list[
            tuple[Literal["attacker", "defender"], int, int]
        ] = dice_value_changes if dice_value_changes is not None else []
        self.upgrade_dice_requests: list[Dice] = (
            upgrade_dice_requests if upgrade_dice_requests is not None else []
        )
        self.player_state_changes: list[
            tuple[Literal["attacker", "defender"], str, Any]
        ] = player_state_changes if player_state_changes is not None else []
        self.intend_hack: list[tuple[Literal["attacker", "defender"], int]] = (
            intend_hack if intend_hack is not None else []
        )
        self.intend_leap: list[tuple[Literal["attacker", "defender"], int]] = (
            intend_leap if intend_leap is not None else []
        )
        self.effects_to_consume: list[Effect] = (
            list(effects_to_consume) if effects_to_consume is not None else []
        )

    def __str__(self) -> str:
        return f"Patch:\nDamage list:{self.damage}\nReload times add:{self.add_reload_times}\nExtra attack add:{self.add_extra_attack}\nExtra defence add:{self.add_extra_defence}\nAdd effects list:{self.effects_to_add}\nDice value changes:{self.dice_value_changes}\nPlayer changes:{self.player_state_changes}\nHacks intend:{self.intend_hack}\nEffects to consume:{self.effects_to_consume}"

    def __bool__(self):
        return any(
            [
                self.damage,
                self.add_reload_times,
                self.add_extra_attack,
                self.add_extra_defence,
                self.add_attacker_hp,
                self.add_defender_hp,
                self.add_attack_dice,
                self.add_defence_dice,
                self.effects_to_add,
                self.dice_value_changes,
                self.upgrade_dice_requests,
                self.player_state_changes,
                self.intend_hack,
                self.intend_leap,
                self.effects_to_consume,
            ]
        )

    def merge(self, other: GamePatch) -> GamePatch:
        """将另一个 patch 合并到当前 patch，同类伤害会叠加。"""
        merged_damage: list[DamageDict] = []
        for dam in self.damage:
            merged_damage.append(
                {"role": dam["role"], "type": dam["type"], "count": dam["count"]}
            )

        for dam in other.damage:
            found = False
            for existing in merged_damage:
                if existing["role"] == dam["role"] and existing["type"] == dam["type"]:
                    existing["count"] += dam["count"]
                    found = True
                    break
            if not found:
                merged_damage.append(
                    {"role": dam["role"], "type": dam["type"], "count": dam["count"]}
                )

        # 合并骇入意图（按目标 role 累加数量）
        merged_hack: dict[Literal["attacker", "defender"], int] = {}
        for role, count in self.intend_hack:
            merged_hack[role] = merged_hack.get(role, 0) + count
        for role, count in other.intend_hack:
            merged_hack[role] = merged_hack.get(role, 0) + count
        merged_hack_list: list[tuple[Literal["attacker", "defender"], int]] = [
            (role, count) for role, count in merged_hack.items()
        ]

        merged_leap: dict[Literal["attacker", "defender"], int] = {}
        for role, count in self.intend_leap:
            merged_leap[role] = merged_leap.get(role, 0) + count
        for role, count in other.intend_leap:
            merged_leap[role] = merged_leap.get(role, 0) + count
        merged_leap_list: list[tuple[Literal["attacker", "defender"], int]] = [
            (role, count) for role, count in merged_leap.items()
        ]

        return GamePatch(
            damage=merged_damage,
            add_reload_times=self.add_reload_times + other.add_reload_times,
            add_extra_attack=self.add_extra_attack + other.add_extra_attack,
            add_extra_defence=self.add_extra_defence + other.add_extra_defence,
            add_attacker_hp=self.add_attacker_hp + other.add_attacker_hp,
            add_defender_hp=self.add_defender_hp + other.add_defender_hp,
            add_attack_dice=dict(
                Counter(self.add_attack_dice) + Counter(other.add_attack_dice)
            ),
            add_defence_dice=dict(
                Counter(self.add_defence_dice) + Counter(other.add_defence_dice)
            ),
            effects_to_add=list(self.effects_to_add) + list(other.effects_to_add),
            dice_value_changes=list(self.dice_value_changes)
            + list(other.dice_value_changes),
            upgrade_dice_requests=list(
                set(self.upgrade_dice_requests + other.upgrade_dice_requests)
            ),
            player_state_changes=list(self.player_state_changes)
            + list(other.player_state_changes),
            intend_hack=merged_hack_list,
            intend_leap=merged_leap_list,
            effects_to_consume=list(self.effects_to_consume)
            + list(other.effects_to_consume),
        )

    @staticmethod
    def merge_all(patches: list[GamePatch]) -> GamePatch:
        """将多个同时发生的 patch 合并成一个大的 patch。"""
        result = GamePatch()
        for patch in patches:
            result = result.merge(patch)
        return result

    @staticmethod
    def empty() -> GamePatch:
        return GamePatch()


class GameContext:
    """游戏状态修改的统一入口。所有状态变更都应通过本类提交的 GamePatch 完成。"""

    def __init__(self, game: GameManager) -> None:
        self._game = game

    def create_view(self) -> GameView:
        """创建当前游戏状态的只读快照。"""
        return GameView(self._game)

    def _get_player(self, role: Literal["attacker", "defender"]) -> Player:
        return self._game.attacker if role == "attacker" else self._game.defender

    def apply_patch(self, patch: GamePatch) -> None:
        """将一个（已合并的）GamePatch 应用到 GameManager。"""
        if not patch:
            return

        # 伤害
        for dam in patch.damage:
            target = self._get_player(dam["role"])
            target.hp -= dam["count"]
            if dam["count"] != 0:
                target.attack_in_round = True

        # 回复血量
        self._game.attacker.hp = min(
            self._game.attacker.max_hp, self._game.attacker.hp + patch.add_attacker_hp
        )
        self._game.defender.hp = min(
            self._game.defender.max_hp, self._game.defender.hp + patch.add_defender_hp
        )

        # 防御/攻击等级
        if patch.add_attack_dice.get("attacker"):
            self._game.attacker.attack_dice = min(
                self._game.attacker.ori_attack_dices
                + patch.add_attack_dice["attacker"],
                self._game.attacker.ori_max_dices,
            )
        if patch.add_attack_dice.get("defender"):
            self._game.defender.attack_dice = min(
                self._game.defender.ori_attack_dices
                + patch.add_attack_dice["defender"],
                self._game.defender.ori_max_dices,
            )
        if patch.add_defence_dice.get("attacker"):
            self._game.attacker.defence_dice = min(
                self._game.attacker.ori_denfece_dices
                + patch.add_defence_dice["attacker"],
                self._game.attacker.ori_max_dices,
            )
        if patch.add_defence_dice.get("defender"):
            self._game.defender.defence_dice = min(
                self._game.defender.ori_denfece_dices
                + patch.add_defence_dice["defender"],
                self._game.defender.ori_max_dices,
            )

        # 额外点数
        self._game.attacker_extra_sum += patch.add_extra_attack
        self._game.defender_extra_sum += patch.add_extra_defence

        # 重投次数
        self._game.reload_times += patch.add_reload_times
        self._game.reload_times = max(self._game.reload_times, 0)

        # 新增效果：可叠加且目标已有同类效果时直接叠加层数，否则新增实例
        newly_added_effects: list[Effect] = []
        np = GamePatch()
        for role, effect in patch.effects_to_add:
            target = self._get_player(role)
            effect.master = target
            b, p = target.add_effect(effect)
            np = np.merge(p)
            if b:
                newly_added_effects.append(effect)

        if np:
            self.apply_patch(np)

        if newly_added_effects:
            view = self.create_view()
            def_patches: list[GamePatch] = []
            for effect in newly_added_effects:
                p = effect.on_denfination(view)
                if p is not None:
                    def_patches.append(p)
            if def_patches:
                self.apply_patch(GamePatch.merge_all(def_patches))

        # 修改骰子点数
        for role, index, value in patch.dice_value_changes:
            target = self._get_player(role)
            target.selected_dice[index].now_value = value

        # 升级骰子
        for dice in patch.upgrade_dice_requests:
            dice.upgrade()

        # 玩家自定义状态字段（如 TrafficLightPlayer 的 get_s_round）
        for role, attr, value in patch.player_state_changes:
            target = self._get_player(role)
            setattr(target, attr, value)

        # 骇入意图：对目标角色已选骰子中点数大于 2 的最大 X 个骰子改为 2
        for role, count in patch.intend_hack:
            target = self._get_player(role)
            candidates = [
                (i, dice.now_value)
                for i, dice in enumerate(target.selected_dice)
                if not dice.special and dice.now_value > 2
            ]
            candidates.sort(key=lambda x: x[1], reverse=True)
            for index, _ in candidates[:count]:
                target.selected_dice[index].now_value = 2

        for role, count in patch.intend_leap:
            target = self._get_player(role)
            for _ in range(count):
                candidates = [
                    (i, dice.now_value)
                    for i, dice in enumerate(target.selected_dice)
                    if not dice.special
                ]
                candidates.sort(key=lambda x: x[1])
                target.selected_dice[candidates[0][0]].now_value = target.selected_dice[
                    candidates[0][0]
                ].sides

        # 消耗效果（如连击触发后置死）
        for effect in patch.effects_to_consume:
            effect.alive = False
