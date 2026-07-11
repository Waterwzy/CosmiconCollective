from core.player.player import Player
from core.player.default import players, DefaultAIPlayer
from core.player.effects import Effect
import random


class GameManager:
    def __init__(self, red_player: Player, blue_player: Player) -> None:
        self.players = [red_player, blue_player]
        self.attacker_index = random.randint(0, 1)
        self.round = 0
        self.attacker_extra_sum = 0
        self.defender_extra_sum = 0
        self.effect_hook = EffectHookManager()
        self.reload_times = 0

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
        for effect in self.attacker.effects:
            if not effect.alive or effect.clear_after_round:
                self.attacker.effects.remove(effect)
        for effect in self.defender.effects:
            if not effect.alive or effect.clear_after_round:
                self.defender.effects.remove(effect)

    def _is_win(self) -> bool:
        if self.attacker.hp <= 0 or self.defender.hp <= 0:
            return True
        return False

    def start_round(self):
        self.next_round()
        if self.attacker_index == 0:
            print(f"第{self.round}回合，你先手")
        else:
            print(f"第{self.round}回合，你后手")
        print(f"攻击方当前血量为：{self.attacker.hp}，防御方血量为：{self.defender.hp}")

        self.attacker.round_start(self)
        self.defender.round_start(self)

        for dice in self.attacker.dices:
            dice.load()

        self.reload_times = 2
        act = None
        attack_selected = []

        while True:
            print(f"攻击方骰子为：{[str(dice) for dice in self.attacker.dices]}")
            act, attack_selected = self.attacker.select_dice(
                "attack", self.reload_times
            )
            if act == 1:
                break
            elif act == 2:
                self.reload_times -= 1
                for i in attack_selected:
                    self.attacker.dices[i].load()

        print(
            f"攻击方选择的骰子为：{[str(self.attacker.dices[i]) for i in attack_selected]}"
        )
        self.attacker.selected_dice = [self.attacker.dices[i] for i in attack_selected]

        self.attacker.after_attack_sum(self)

        for dice in self.defender.dices:
            dice.load()

        self.reload_times = 0
        act = None
        defence_selected = []

        self.defender.before_defence_select(self)

        while True:
            print(f"防御方骰子为：{[str(dice) for dice in self.defender.dices]}")
            act, defence_selected = self.defender.select_dice(
                "defence", self.reload_times
            )
            if act == 1:
                break
            elif act == 2:
                self.reload_times -= 1
                for i in defence_selected:
                    self.defender.dices[i].load()

        print(
            f"防御方选择的骰子为：{[str(self.defender.dices[i]) for i in defence_selected]}"
        )
        self.defender.selected_dice = [self.defender.dices[i] for i in defence_selected]

        self.defender.after_defence_sum(self)

        self.effect_hook.before_sum(self)

        self.attacker.after_effect_settle(self)
        self.defender.after_effect_settle(self)

        print(f"攻击方总点数为：{self.attacker_sum + self.attacker_extra_sum}")
        print(f"防御方总点数为：{self.defender_sum + self.defender_extra_sum}")

        self.defender.begin_attack(
            max(
                0,
                self.attacker_sum
                + self.attacker_extra_sum
                - self.defender_sum
                - self.defender_extra_sum,
            )
        )

        self.effect_hook.after_settlement(self)

        print(f"防御方剩余血量为：{self.defender.hp}")

    def main(self):
        while not self._is_win():
            self.start_round()


class EffectHookManager:
    def __init__(self) -> None:
        pass

    def before_sum(self, game: GameManager):
        for effect_ref in Effect.get_instances():
            effect = effect_ref()
            effect.before_sum(game)

    def after_settlement(self, game: GameManager):
        for effect_ref in Effect.get_instances():
            effect = effect_ref()
            effect.after_settlement(game)


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
