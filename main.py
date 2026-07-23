from core.player.player import Player
from core.player.default import players, DefaultAIPlayer
from core.context import GameContext, GamePatch
from typing import Literal
import random


class GameManager:
    def __init__(self, red_player: Player, blue_player: Player) -> None:
        self.players = [red_player, blue_player]
        self.attacker_index = random.randint(0, 1)
        self.round = 1
        self.attacker_extra_sum = 0
        self.defender_extra_sum = 0
        self.effect_hook = EffectHookManager()
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

    def _is_win(self) -> bool:
        if self.attacker.hp <= 0 or self.defender.hp <= 0:
            return True
        return False

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

        for dice in self.attacker.dices:
            dice.load(self.attacker.load_max)

        self.reload_times = 2
        act = None
        attack_selected = []

        self.effect_hook.before_select(self.context)
        print(f"攻击方可用重投次数：{self.reload_times}")

        while True:
            print(f"攻击方骰子为：{[str(dice) for dice in self.attacker.dices]}")
            act, attack_selected = self.attacker.select_dice(
                "attack", self.reload_times
            )
            if act == 1:
                break
            elif act == 2:
                self.context.apply_patch(GamePatch(add_reload_times=-1))
                for i in attack_selected:
                    self.attacker.dices[i].load(self.attacker.load_max)

        print(
            f"攻击方选择的骰子为：{[str(self.attacker.dices[i]) for i in attack_selected]}"
        )
        self.attacker.selected_dice = [self.attacker.dices[i] for i in attack_selected]

        ap = self.attacker.after_attack_sum(self.context.create_view())
        if ap:
            self.context.apply_patch(ap)

        self.state = "defence"

        for dice in self.defender.dices:
            dice.load(self.defender.load_max)

        self.reload_times = 0
        act = None
        defence_selected = []

        dp = self.defender.before_defence_select(self.context.create_view())
        if dp:
            self.context.apply_patch(dp)
        self.effect_hook.before_select(self.context)
        print(f"防御方可用重投次数：{self.reload_times}")

        while True:
            print(f"防御方骰子为：{[str(dice) for dice in self.defender.dices]}")
            act, defence_selected = self.defender.select_dice(
                "defence", self.reload_times
            )
            if act == 1:
                break
            elif act == 2:
                self.context.apply_patch(GamePatch(add_reload_times=-1))
                for i in defence_selected:
                    self.defender.dices[i].load(self.defender.load_max)

        print(
            f"防御方选择的骰子为：{[str(self.defender.dices[i]) for i in defence_selected]}"
        )
        self.defender.selected_dice = [self.defender.dices[i] for i in defence_selected]

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
        hurt_patch = self.defender.begin_attack(self.context.create_view(), hurts)
        print(f"sum state patch{hurt_patch}")
        self.context.apply_patch(hurt_patch)

        self.effect_hook.after_settlement(self.context)

        print(f"防御方剩余血量为：{self.defender.hp}")

        self.next_round()

    def main(self):
        start_patches = []
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


class EffectHookManager:
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
        isinstance(selected_player, int)
        and (selected_player < 0 or selected_player >= len(players))
        and selected_player != 1
    ):
        selected_player = int(input(f"请选择你的角色（输入数字）：\n{players}\n"))
    game = GameManager(players[selected_player], DefaultAIPlayer())
    del players
    game.main()
