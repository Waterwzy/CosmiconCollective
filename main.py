import random
from typing import Literal

from core.context import GameContext, GamePatch
from core.player.default import DefaultAIPlayer, players, special_dices
from core.player.player import Player


class GameManager:
    def __init__(
        self, red_player: Player, blue_player: Player, seed: int | None = None
    ) -> None:
        self.players = [red_player, blue_player]
        self.rng = random.Random(seed)
        """对局随机源，可注入种子以复现对局"""
        self.attacker_index = self.rng.randint(0, 1)
        self.round = 1
        self.attacker_extra_sum = 0
        self.defender_extra_sum = 0
        self.attacker_multiplier = 1
        self.defender_multiplier = 1
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
        self.attacker_multiplier = 1
        self.defender_multiplier = 1
        self.attacker.role = "attacker"
        self.defender.role = "defender"
        self.attacker.clear_effects()
        self.defender.clear_effects()
        self.attacker.attack_in_round = False
        self.defender.attack_in_round = False

    def _is_win(self) -> bool:
        return self.attacker.hp <= 0 or self.defender.hp <= 0

    def select_dice(self, target: Player, state: Literal["attack", "defence"]):
        target.dices = [dice for dice in target.dices if not dice.special]

        for dice in target.dices:
            dice.load(target.load_max, self.rng)

        self.reload_times = 2 if state == "attack" else 0
        act = None
        selected = []

        target.attack_dice = target.ori_attack_dices
        target.defence_dice = target.ori_denfece_dices

        before_select_view = self.context.create_view()

        patch = GamePatch()
        if target.role == "attacker":
            patch = target.before_attack_select(before_select_view)
        if target.role == "defender":
            patch = target.before_defence_select(before_select_view)
        if patch:
            self.context.apply_patch(patch)
        self.effect_hook.before_select(self.context)
        print(f"{state}可用重投次数{self.reload_times}")
        before_select_view = self.context.create_view()

        while True:
            print(f"{state}骰子为{[dice for dice in target.dices]}")
            act, selected = target.select_dice(
                state, self.reload_times, before_select_view, self.rng
            )
            if act == 1:
                break
            elif act == 2:
                self.context.apply_patch(GamePatch(add_reload_times=-1))
                for i in selected:
                    target.dices[i].load(target.load_max, self.rng)
                v = self.context.create_view()
                patch = target.after_reload(v, selected)
                if patch:
                    self.context.apply_patch(patch)
            elif act == 3 and target.special_dice:
                target.use_spe_times -= 1
                target.dices.append(target.special_dice)
                target.dices[-1].load(target.load_max, self.rng)

        print(f"{state}选择的骰子为：{[str(target.dices[i]) for i in selected]}")
        target.selected_dice = [target.dices[i] for i in selected]

        for dice in target.selected_dice:
            if dice.special and dice.now_effect:
                if hasattr(target, "use_spe"):
                    target.use_spe += 1  # type: ignore
                self.context.apply_patch(dice.trigger_dice())

    def start_round(self):
        """执行一整轮。任意一方血量归零时本回合立即终止，不再进入下一轮。"""
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
        if self._is_win():
            return

        self.state = "attack"

        self.select_dice(self.attacker, self.state)
        if self._is_win():
            return

        ap = self.attacker.after_attack_sum(self.context.create_view())
        if ap:
            self.context.apply_patch(ap)
        if self._is_win():
            return

        self.state = "defence"

        self.select_dice(self.defender, self.state)
        if self._is_win():
            return

        dp = self.defender.after_defence_sum(self.context.create_view())
        if dp:
            self.context.apply_patch(dp)
        if self._is_win():
            return

        self.state = "sum"

        self.effect_hook.before_sum(self.context)
        if self._is_win():
            return

        settle_patches = []
        settle_view = self.context.create_view()
        asp = self.attacker.after_effect_settle(settle_view)
        dsp = self.defender.after_effect_settle(settle_view)
        if asp:
            settle_patches.append(asp)
        if dsp:
            settle_patches.append(dsp)
        self.context.apply_patch(GamePatch.merge_all(settle_patches))
        if self._is_win():
            return

        attacker_total = (
            self.attacker_sum + self.attacker_extra_sum
        ) * self.attacker_multiplier
        defender_total = (
            self.defender_sum + self.defender_extra_sum
        ) * self.defender_multiplier
        print(f"攻击方总点数为：{attacker_total}")
        print(f"防御方总点数为：{defender_total}")

        hurts = max(0, attacker_total - defender_total)
        print(f"受到伤害：{hurts}")

        # 追加攻击次数由攻击方存活效果声明（如连击），结算完毕后效果可自我消耗
        extra_hit_view = self.context.create_view()
        hit_effects = [
            effect
            for effect in self.attacker.effects
            if effect.alive and effect.extra_hits(extra_hit_view) > 0
        ]
        extra_hits = sum(effect.extra_hits(extra_hit_view) for effect in hit_effects)
        for _ in range(1 + extra_hits):
            hit_view = self.context.create_view()
            hit_patch = self.defender.begin_attack(hit_view, hurts)
            print(f"sum state patch\n{hit_patch}")
            hp_before = self.defender.hp
            self.context.apply_patch(hit_patch)
            if self._is_win():
                return
            hp_sum = max(0, hp_before - self.defender.hp)
            after_view = self.context.create_view()
            dp = self.defender.after_being_attacked(after_view, hp_sum)
            if dp:
                self.context.apply_patch(dp)
            if self._is_win():
                return
            ap = self.attacker.after_attack(after_view, hp_sum)
            if ap:
                self.context.apply_patch(ap)
            if self._is_win():
                return

        after_extra_hits_view = self.context.create_view()
        for effect in hit_effects:
            if effect.alive:
                consume_patch = effect.after_extra_hits(after_extra_hits_view)
                if consume_patch:
                    self.context.apply_patch(consume_patch)

        self.effect_hook.after_settlement(self.context)
        if self._is_win():
            return

        after_settle_view = self.context.create_view()
        aap = self.attacker.after_settlement(after_settle_view)
        dap = self.defender.after_settlement(after_settle_view)
        after_settle_patches = []
        if aap:
            after_settle_patches.append(aap)
        if dap:
            after_settle_patches.append(dap)
        self.context.apply_patch(GamePatch.merge_all(after_settle_patches))
        if self._is_win():
            return

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

        print("游戏结束！")
        if self.attacker.hp <= 0 and self.defender.hp <= 0:
            print("双方同归于尽！")
        elif self.attacker.hp <= 0:
            print(f"{self.defender.id}获胜！")
        else:
            print(f"{self.attacker.id}获胜！")


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
            if not effect.alive:
                continue
            p = effect.before_sum(view)
            if p:
                patches.append(p)
        for effect in view.defender.effects:
            if not effect.alive:
                continue
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
            if not effect.alive:
                continue
            p = effect.after_settlement(view)
            if p:
                patches.append(p)
        for effect in view.defender.effects:
            if not effect.alive:
                continue
            p = effect.after_settlement(view)
            if p:
                patches.append(p)
        context.apply_patch(GamePatch.merge_all(patches))

    def before_select(self, context: GameContext):
        view = context.create_view()
        patches = []
        for effect in view.attacker.effects:
            if not effect.alive:
                continue
            p = effect.before_select(view)
            if p:
                patches.append(p)
        for effect in view.defender.effects:
            if not effect.alive:
                continue
            p = effect.before_select(view)
            if p:
                patches.append(p)
        context.apply_patch(GamePatch.merge_all(patches))


if __name__ == "__main__":
    import sys

    def input_int(prompt: str) -> int:
        while True:
            try:
                return int(input(prompt))
            except ValueError:
                print("输入无效，请输入数字。")

    seed = None
    if len(sys.argv) > 1:
        try:
            seed = int(sys.argv[1])
        except ValueError:
            print(f"无效的随机种子 {sys.argv[1]}，本次使用随机种子。")

    print("可用角色：")
    for index, player in enumerate(players):
        tag = "（AI角色）" if player.is_agent else ""
        print(f"{index}. {player}{tag}")

    selected_player = input_int("请选择你的角色（输入数字）：")
    while True:
        if (
            0 <= selected_player < len(players)
            and not players[selected_player].is_agent
        ):
            break
        if 0 <= selected_player < len(players):
            print("该角色是 AI 角色，无法选择，请选择其他角色。")
        else:
            print(f"输入无效，请输入 0 到 {len(players) - 1} 之间的数字。")
        selected_player = input_int("请选择你的角色（输入数字）：")

    print("可用曜彩骰：")
    for index, dice in enumerate(special_dices):
        print(f"{index}. {dice.name}")

    selected_spe_dice = input_int("请选择你的曜彩骰（输入index）：")
    while not 0 <= selected_spe_dice < len(special_dices):
        print(f"输入无效，请输入 0 到 {len(special_dices) - 1} 之间的数字。")
        selected_spe_dice = input_int("请选择你的曜彩骰（输入index）：")

    players[selected_player].special_dice = special_dices[selected_spe_dice]
    game = GameManager(players[selected_player], DefaultAIPlayer(), seed=seed)
    del players
    del special_dices
    game.main()
