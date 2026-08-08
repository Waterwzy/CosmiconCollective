import random
from typing import Literal

from core.context import GameContext, GamePatch
from core.player.default import DefaultAIPlayer, DoubleShot, players, special_dices
from core.player.player import Player


class GameManager:
    def __init__(self, red_player: Player, blue_player: Player) -> None:
        self.players = [red_player, blue_player]
        self.attacker_index = random.randint(0, 1)
        self.round = 1
        self.attacker_extra_sum = 0
        self.defender_extra_sum = 0
        self.effect_hook = HookManager()
        self.reload_times = 0
        self.state: Literal["begin", "attack", "defence", "sum"] | None = None
        self.context = GameContext(self)
        self.attacker.role = "attacker"
        self.defender.role = "defender"

    @property
    def attacker(self):
        return self.players[self.attacker_index]

    @property
    def defender(self):
        return self.players[1 - self.attacker_index]

    @property
    def attacker_sum(self):
        return sum([dice.now_value for dice in self.attacker.selected_dice])

    @property
    def defender_sum(self):
        return sum([dice.now_value for dice in self.defender.selected_dice])

    def next_round(self):
        self.attacker_index = 1 - self.attacker_index
        self.round += 1
        self.attacker_extra_sum = 0
        self.defender_extra_sum = 0
        self.attacker.role = "attacker"
        self.defender.role = "defender"
        self.attacker.clear_effects()
        self.defender.clear_effects()
        self.attacker.attack_in_round = False
        self.attacker.attack_in_round = False

    def _is_win(self) -> bool:
        return self.attacker.hp <= 0 or self.defender.hp <= 0

    def select_dice(self, target: Player, state: Literal["attack", "defence"]):
        target.dices = [dice for dice in target.dices if not dice.special]

        for dice in target.dices:
            dice.load(target.load_max)

        self.reload_times = 2 if state == "attack" else 0
        act = None
        selected = []
        before_select_view = self.context.create_view()

        target.attack_dice = target.ori_attack_dices
        target.defence_dice = target.ori_denfece_dices
        self.effect_hook.before_select(self.context)
        print(f"{state}可用重投次数{self.reload_times}")

        while True:
            print(f"{state}骰子为{[dice for dice in target.dices]}")
            act, selected = target.select_dice(
                state, self.reload_times, before_select_view
            )
            if act == 1:
                break
            elif act == 2:
                self.context.apply_patch(GamePatch(add_reload_times=-1))
                for i in selected:
                    target.dices[i].load(target.load_max)
            elif act == 3 and target.special_dice:
                target.use_spe_times -= 1
                target.dices.append(target.special_dice)
                target.dices[-1].load(target.load_max)

        print(f"{state}选择的骰子为：{[str(target.dices[i]) for i in selected]}")
        target.selected_dice = [target.dices[i] for i in selected]

        for dice in target.selected_dice:
            if dice.special and dice.now_effect:
                if hasattr(target, "use_spe"):
                    target.use_spe += 1  # type: ignore
                self.context.apply_patch(dice.trigger_dice())

    def start_round(self):
        self.state = "begin"

        if self.attacker_index == 0:
            print(f"第{self.round}回合，你先手")
        else:
            print(f"第{self.round}回合，你后手")
        print(f"攻击方当前血量为：{self.attacker.hp}，防御方血量为：{self.defender.hp}")

        round_patches = []
        round_view = self.context.create_view()
        ap = self.attacker.round_start(round_view)
        dp = self.defender.round_start(round_view)
        if ap:
            round_patches.append(ap)
        if dp:
            round_patches.append(dp)
        self.context.apply_patch(GamePatch.merge_all(round_patches))

        self.state = "attack"

        self.select_dice(self.attacker, self.state)

        ap = self.attacker.after_attack_sum(self.context.create_view())
        if ap:
            self.context.apply_patch(ap)

        self.state = "defence"

        self.select_dice(self.defender, self.state)

        dsp = self.defender.after_defence_sum(self.context.create_view())
        if dsp:
            self.context.apply_patch(dsp)

        self.state = "sum"

        self.effect_hook.before_sum(self.context)

        settle_patches = []
        settle_view = self.context.create_view()
        asp = self.attacker.after_effect_settle(settle_view)
        dsp = self.defender.after_effect_settle(settle_view)
        if asp:
            settle_patches.append(asp)
        if dsp:
            settle_patches.append(dsp)
        self.context.apply_patch(GamePatch.merge_all(settle_patches))

        print(f"攻击方总点数为：{self.attacker_sum + self.attacker_extra_sum}")
        print(f"防御方总点数为：{self.defender_sum + self.defender_extra_sum}")

        hurts = max(
            0,
            self.attacker_sum
            + self.attacker_extra_sum
            - self.defender_sum
            - self.defender_extra_sum,
        )
        print(f"受到伤害：{hurts}")
        double_shots = [
            e for e in self.attacker.effects if isinstance(e, DoubleShot) and e.alive
        ]
        hit_view = self.context.create_view()
        hurt_patch = GamePatch.merge_all(
            [
                self.defender.begin_attack(hit_view, hurts)
                for _ in range(1 + len(double_shots))
            ]
        ).merge(GamePatch(effects_to_consume=double_shots))
        print(f"sum state patch\n{hurt_patch}")
        self.context.apply_patch(hurt_patch)

        self.effect_hook.after_settlement(self.context)

        after_settle_view = self.context.create_view()
        aap = self.attacker.after_settlement(after_settle_view)
        dap = self.defender.after_settlement(after_settle_view)
        after_settle_patch = []
        if aap:
            after_settle_patch.append(aap)
        if dap:
            after_settle_patch.append(dap)
        self.context.apply_patch(GamePatch.merge_all(after_settle_patch))

        print(f"防御方剩余血量为：{self.defender.hp}")

        self.next_round()

    def main(self):
        start_patches = []
        for dice in self.players[0].dices:
            dice.master = self.players[0]
        for dice in self.players[1].dices:
            dice.master = self.players[1]
        if self.players[0].special_dice:
            self.players[0].special_dice.master = self.players[0]
        if self.players[1].special_dice:
            self.players[1].special_dice.master = self.players[1]
        start_view = self.context.create_view()
        dp = self.defender.on_game_start(start_view)
        ap = self.attacker.on_game_start(start_view)
        if dp:
            start_patches.append(dp)
        if ap:
            start_patches.append(ap)
        self.context.apply_patch(GamePatch.merge_all(start_patches))
        while not self._is_win():
            self.start_round()


class HookManager:
    """管理效果和曜彩骰的触发
    对于效果主要是生成Game Patch
    对于曜彩骰则是计数，做内部使用
    """

    def __init__(self) -> None:
        pass

    def before_sum(self, context: GameContext):
        view = context.create_view()
        patches = []
        for effect in view.attacker.effects:
            p = effect.before_sum(view)
            if p:
                patches.append(p)
        for effect in view.defender.effects:
            p = effect.before_sum(view)
            if p:
                patches.append(p)
        context.apply_patch(GamePatch.merge_all(patches))
        if view.attacker.special_dice:
            view.attacker.special_dice.before_sum(view)
        if view.defender.special_dice:
            view.defender.special_dice.before_sum(view)

    def after_settlement(self, context: GameContext):
        view = context.create_view()
        patches = []
        for effect in view.attacker.effects:
            p = effect.after_settlement(view)
            if p:
                patches.append(p)
        for effect in view.defender.effects:
            p = effect.after_settlement(view)
            if p:
                patches.append(p)
        context.apply_patch(GamePatch.merge_all(patches))

    def before_select(self, context: GameContext):
        view = context.create_view()
        patches = []
        for effect in view.attacker.effects:
            p = effect.before_select(view)
            if p:
                patches.append(p)
        for effect in view.defender.effects:
            p = effect.before_select(view)
            if p:
                patches.append(p)
        context.apply_patch(GamePatch.merge_all(patches))


if __name__ == "__main__":
    selected_player = -1
    while (
        selected_player < 0 or selected_player >= len(players)
    ) and selected_player != 1:
        selected_player = int(input(f"请选择你的角色（输入数字）：\n{players}\n"))
    selected_spe_dice = -1
    while selected_spe_dice < 0 or selected_spe_dice >= len(special_dices):
        selected_spe_dice = int(
            input(f"请选择你的曜彩骰（输入index）:\n{special_dices}\n")
        )
    players[selected_player].special_dice = special_dices[selected_spe_dice]
    game = GameManager(players[selected_player], DefaultAIPlayer())
    del players
    del special_dices
    game.main()
