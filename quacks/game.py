"""Main game engine for The Quacks of Quedlinburg simulation.

Orchestrates all phases of a 9-round game:
  Fortune Teller → Pulling → Evaluation (A–E)

The engine is event-driven: each significant action emits an event dict
that observers (stats engine, loggers) can consume.
"""

from __future__ import annotations
import random
from dataclasses import dataclass, field
from typing import Callable, Optional

from quacks.chips import Chip, ROUND_6_WHITE_ADDITION
from quacks.enums import ChipColor, GamePhase, ExplosionChoice, BonusDieFace
from quacks.fortune_teller import FortuneCard, FortuneEffect, make_game_deck
from quacks.market import Market
from quacks.player import Player
from quacks.scoring import cauldron_reward, SCORING_TRACK_MAX, rubies_to_vp
from quacks.ingredients.registry import get_effect
from quacks.expansions import Expansion


TOTAL_ROUNDS = 9


# ---------------------------------------------------------------------------
# Game state snapshot (passed to strategies so they can make informed decisions)
# ---------------------------------------------------------------------------

@dataclass
class GameState:
    """Read-only view of the game passed to player strategies."""
    round_number: int
    phase: GamePhase
    players: list[Player]
    market: Market
    current_fortune_card: Optional[FortuneCard]
    total_rounds: int = TOTAL_ROUNDS

    # Round-long effect flags visible to strategies
    flask_disabled: bool = False
    strong_ingredient_bonus: int = 0
    extra_ruby_on_landing: bool = False

    @property
    def leader_score(self) -> int:
        return max(p.scoring_position for p in self.players)

    @property
    def leader(self) -> Player:
        return max(self.players, key=lambda p: p.scoring_position)

    def player_rank(self, player: Player) -> int:
        """1 = leading, len(players) = last place."""
        sorted_players = sorted(self.players, key=lambda p: -p.scoring_position)
        return sorted_players.index(player) + 1

    def is_last_round(self) -> bool:
        return self.round_number == self.total_rounds

    def rounds_remaining(self) -> int:
        return self.total_rounds - self.round_number


# ---------------------------------------------------------------------------
# Bonus die
# ---------------------------------------------------------------------------

_BONUS_DIE_FACES: list[BonusDieFace] = [
    BonusDieFace.RUBY,
    BonusDieFace.RUBY,
    BonusDieFace.DROPLET,
    BonusDieFace.DROPLET,
    BonusDieFace.ORANGE_CHIP,
    BonusDieFace.ORANGE_CHIP,
]  # [VERIFY exact distribution]


def roll_bonus_die(rng: random.Random | None = None) -> BonusDieFace:
    return (rng or random).choice(_BONUS_DIE_FACES)


# ---------------------------------------------------------------------------
# Event type
# ---------------------------------------------------------------------------

Event = dict
EventHandler = Callable[[Event], None]


def _event(event_type: str, player: Optional[Player] = None, **data) -> Event:
    return {"type": event_type, "player": player.name if player else None, **data}


# ---------------------------------------------------------------------------
# Game engine
# ---------------------------------------------------------------------------

class Game:
    """Full simulation of one complete game of Quacks of Quedlinburg."""

    def __init__(
        self,
        players: list[Player],
        book_pages: dict[ChipColor, int] | None = None,
        rng: random.Random | None = None,
        event_handlers: list[EventHandler] | None = None,
        expansions: list[Expansion] | None = None,
    ) -> None:
        if not 2 <= len(players) <= 4:
            raise ValueError(f"Need 2–4 players, got {len(players)}")
        self.players = players
        self.rng = rng or random.Random()
        self._handlers: list[EventHandler] = event_handlers or []
        self.expansions: list[Expansion] = expansions or []

        # Thread the game RNG into each player's bag for full determinism
        for player in self.players:
            player.bag._rng = self.rng

        # Collect expansion data before initialising market and deck
        extra_fortune_cards: list[FortuneCard] = []
        extra_costs: dict[tuple, int] = {}
        extra_stock: dict[tuple, int] = {}
        extra_availability: dict[ChipColor, int] = {}

        for exp in self.expansions:
            extra_fortune_cards.extend(exp.extra_fortune_cards)
            for chip, cost in exp.new_chips:
                key = (chip.color, chip.value)
                extra_costs[key] = cost
                # Default 4 copies per expansion chip (shared pool)
                extra_stock[key] = extra_stock.get(key, 0) + 4
                # Expansion colors are available from round 1 by default
                extra_availability.setdefault(chip.color, 1)
            for chip, extra_count in exp.extra_market_stock.items():
                key = (chip.color, chip.value)
                extra_stock[key] = extra_stock.get(key, 0) + extra_count

        self.market = Market(
            n_players=len(players),
            book_pages=book_pages,
            extra_costs=extra_costs or None,
            extra_stock=extra_stock or None,
            extra_availability=extra_availability or None,
        )
        self.fortune_deck: list[FortuneCard] = make_game_deck(
            self.rng, extra_cards=extra_fortune_cards or None
        )

        # Apply starting bag extras from expansions
        for exp in self.expansions:
            for player in self.players:
                for chip in exp.starting_bag_extras:
                    player.bag.add(chip)

        self.round_number: int = 0
        self.phase: GamePhase = GamePhase.SETUP
        self._current_card: Optional[FortuneCard] = None

        # Round-long modifiers must exist before _game_state() is called below
        self._rat_multiplier: int = 1
        self._vp_multiplier: int = 1
        self._stop_bonus_vp: int = 0
        self._explode_ruby_bonus: int = 0
        self._flask_free_refill: bool = False
        self._flask_disabled: bool = False
        self._strong_ingredient_bonus: int = 0
        self._extra_ruby_on_landing: bool = False
        self._bonus_coins: int = 0

        # Apply book pages: global override → expansion overrides → strategy choice.
        # All three layers are merged in that priority order.
        global_pages: dict[ChipColor, int] = book_pages or {}
        expansion_overrides: dict[ChipColor, int] = {}
        for exp in self.expansions:
            expansion_overrides.update(exp.book_page_overrides)

        setup_state = self._game_state()
        for player in self.players:
            # 1. Global pages (same for every player)
            for color, page in global_pages.items():
                if color != ChipColor.WHITE and 1 <= page <= 4:
                    player.book_pages[color] = page
            # 2. Expansion overrides
            for color, page in expansion_overrides.items():
                if color != ChipColor.WHITE and 1 <= page <= 4:
                    player.book_pages[color] = page
            # 3. Per-player strategy choice (can override both layers above)
            strategy_pages = player.strategy.choose_book_pages(player, setup_state)
            for color, page in strategy_pages.items():
                if color != ChipColor.WHITE and 1 <= page <= 4:
                    player.book_pages[color] = page

        self._emit(_event("book_pages_set",
                          pages={p.name: dict(p.book_pages) for p in self.players}))

    # ------------------------------------------------------------------
    # Event system
    # ------------------------------------------------------------------

    def _emit(self, event: Event) -> None:
        for handler in self._handlers:
            handler(event)

    def add_handler(self, handler: EventHandler) -> None:
        self._handlers.append(handler)

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self) -> "GameResult":
        self._emit(_event("game_start", players=[p.name for p in self.players]))
        for rnd in range(1, TOTAL_ROUNDS + 1):
            self.round_number = rnd
            self._run_round(rnd)
        return self._compute_result()

    def _game_state(self) -> GameState:
        return GameState(
            round_number=self.round_number,
            phase=self.phase,
            players=self.players,
            market=self.market,
            current_fortune_card=self._current_card,
            flask_disabled=self._flask_disabled,
            strong_ingredient_bonus=self._strong_ingredient_bonus,
            extra_ruby_on_landing=self._extra_ruby_on_landing,
        )

    # ------------------------------------------------------------------
    # Round
    # ------------------------------------------------------------------

    def _run_round(self, rnd: int) -> None:
        self._emit(_event("round_start", round=rnd))
        state = self._game_state()

        # --- Fortune Teller ---
        self.phase = GamePhase.FORTUNE_TELLER
        card = self.fortune_deck[rnd - 1]
        self._current_card = card
        self._reset_round_modifiers()
        self._apply_fortune_card_pre(card, state)
        self._emit(_event("fortune_card", card_id=card.card_id, name=card.name,
                          effect=card.effect.name))

        # --- Begin player rounds ---
        rat_advances = self._compute_rat_advances()
        for player in self.players:
            player.begin_round(rnd, card.card_id, rat_advances.get(player.name, 0))

        # Apply flask free refill
        if self._flask_free_refill:
            for p in self.players:
                p.flask_full = True

        # Apply immediate bonus ruby (e.g. Lucky Charm card)
        if card.effect == FortuneEffect.BONUS_RUBY:
            for p in self.players:
                p.rubies += card.magnitude
                if p._current_record:
                    p._current_record.rubies_earned += card.magnitude
            self._emit(_event("fortune_bonus_ruby", magnitude=card.magnitude))

        # Apply free chip from supply
        if card.effect == FortuneEffect.FREE_CHIP_FROM_SUPPLY:
            state = self._game_state()
            self._apply_free_chip_from_supply(state)

        # Apply winner gets free chip
        if card.effect == FortuneEffect.WINNER_FREE_CHIP:
            state = self._game_state()
            self._apply_winner_free_chip(state)

        # Apply free upgrade
        if card.effect == FortuneEffect.FREE_UPGRADE:
            state = self._game_state()
            self._apply_free_upgrades(state)

        # Apply catch-up coins
        if card.effect == FortuneEffect.CATCHUP_COINS:
            leader = max(p.scoring_position for p in self.players)
            for p in self.players:
                bonus = max(0, (leader - p.scoring_position) // 2)
                if bonus:
                    p.coins += bonus
                    self._emit(_event("catchup_coins", player=p, bonus=bonus))

        # Extra draw cards handled before pulling
        if card.effect == FortuneEffect.FREE_CHIP_DRAW_SAFE:
            for player in self.players:
                self._mandatory_extra_draw(player, self._game_state(), safe=True)
        elif card.effect == FortuneEffect.FREE_CHIP_DRAW_UNSAFE:
            for player in self.players:
                self._mandatory_extra_draw(player, self._game_state(), safe=False)

        # --- Pulling phase ---
        self.phase = GamePhase.PULLING
        state = self._game_state()
        for player in self.players:
            self._run_pulling(player, state)

        # --- Evaluation A: VP scoring ---
        self.phase = GamePhase.EVALUATION_A
        state = self._game_state()
        self._run_evaluation_a(state)

        # --- Evaluation B: special ingredient effects ---
        self.phase = GamePhase.EVALUATION_B
        state = self._game_state()
        self._run_evaluation_b(state)

        # --- Evaluation D: buying ---
        self.phase = GamePhase.EVALUATION_D
        state = self._game_state()
        self._run_evaluation_d(state)

        # --- Evaluation E: ruby spending + round reset ---
        self.phase = GamePhase.EVALUATION_E
        state = self._game_state()
        self._run_evaluation_e(state)

        # Round 6: add white chip to each bag
        if rnd == 6:
            for player in self.players:
                player.bag.add(ROUND_6_WHITE_ADDITION)
                self._emit(_event("round6_white_added", player=player))

        # End round for each player
        for player in self.players:
            rec = player.end_round()
            self._emit(_event("round_end", player=player, record=rec.round_number))

        self._emit(_event("round_complete", round=rnd,
                          scores={p.name: p.scoring_position for p in self.players}))

    # ------------------------------------------------------------------
    # Fortune Teller application
    # ------------------------------------------------------------------

    def _reset_round_modifiers(self) -> None:
        self._rat_multiplier = 1
        self._vp_multiplier = 1
        self._stop_bonus_vp = 0
        self._explode_ruby_bonus = 0
        self._flask_free_refill = False
        self._flask_disabled = False
        self._strong_ingredient_bonus = 0
        self._extra_ruby_on_landing = False
        self._bonus_coins = 0

    def _apply_fortune_card_pre(self, card: FortuneCard, state: GameState) -> None:
        match card.effect:
            case FortuneEffect.DROPLET_ADVANCE:
                for player in self.players:
                    player.cauldron.advance_droplet(card.magnitude)
                    self._emit(_event("droplet_advanced", player=player, amount=card.magnitude))
            case FortuneEffect.RAT_MULTIPLIER:
                self._rat_multiplier = card.magnitude
            case FortuneEffect.STOP_BONUS_VP:
                self._stop_bonus_vp = card.magnitude
            case FortuneEffect.EXPLODE_RUBY:
                self._explode_ruby_bonus = card.magnitude
            case FortuneEffect.FLASK_FREE_REFILL:
                self._flask_free_refill = True
            case FortuneEffect.VP_MULTIPLIER:
                self._vp_multiplier = card.magnitude
            case FortuneEffect.BONUS_COIN:
                self._bonus_coins = card.magnitude
            case FortuneEffect.NO_FLASK:
                self._flask_disabled = True
            case FortuneEffect.STRONG_INGREDIENT:
                self._strong_ingredient_bonus = card.magnitude
            case FortuneEffect.EXTRA_DROPLET_RUBY:
                self._extra_ruby_on_landing = True
            case _:
                pass  # handled directly in _run_round

    def _apply_free_chip_from_supply(self, state: GameState) -> None:
        available = state.market.available_chips(self.round_number)
        for player in self.players:
            chosen = player.strategy.choose_free_chip(
                player, state, [l.chip for l in available if l.stock > 0]
            )
            if chosen:
                key = (chosen.color, chosen.value)
                if state.market._stock.get(key, 0) > 0:
                    state.market._stock[key] -= 1
                    player.bag.add(chosen)
                    if player._current_record:
                        player._current_record.free_fortune_chip = chosen
                    self._emit(_event("free_chip_taken", player=player, chip=str(chosen)))

    def _apply_winner_free_chip(self, state: GameState) -> None:
        """Leader gets one free chip from supply."""
        leader = max(self.players, key=lambda p: p.scoring_position)
        available = state.market.available_chips(self.round_number)
        chosen = leader.strategy.choose_free_chip(
            leader, state, [l.chip for l in available if l.stock > 0]
        )
        if chosen:
            key = (chosen.color, chosen.value)
            if state.market._stock.get(key, 0) > 0:
                state.market._stock[key] -= 1
                leader.bag.add(chosen)
                self._emit(_event("winner_free_chip", player=leader, chip=str(chosen)))

    def _apply_free_upgrades(self, state: GameState) -> None:
        """Each player may upgrade one 1-chip to a 2-chip (same color) for free."""
        for player in self.players:
            bag_chips = player.bag.all_chips()
            options = []
            for chip in set(bag_chips):
                if chip.color != ChipColor.WHITE and chip.value == 1:
                    target = Chip(chip.color, 2)
                    if state.market.in_stock(target):
                        options.append((chip, target))
            if options:
                chosen = player.strategy.choose_purple_upgrade(player, state, options)
                if chosen:
                    from_chip, to_chip = chosen
                    player.bag.draw_specific(from_chip)
                    state.market.restock(from_chip)
                    state.market._stock[(to_chip.color, to_chip.value)] -= 1
                    player.bag.add(to_chip)
                    self._emit(_event("free_upgrade", player=player,
                                      upgrade=f"{from_chip} → {to_chip}"))

    def _mandatory_extra_draw(self, player: Player, state: GameState, safe: bool) -> None:
        if player.bag.is_empty:
            return
        chip = player.draw_chip()
        if safe:
            pos, rubies = player.cauldron.place(chip)
            if chip.color == ChipColor.WHITE:
                player.cauldron._white_sum -= chip.value  # safe draw: undo explosion risk
            if rubies:
                player.rubies += len(rubies)
                if player._current_record:
                    player._current_record.rubies_earned += len(rubies)
            self._emit(_event("safe_extra_draw", player=player, chip=str(chip)))
        else:
            pos, rubies = player.place_chip(chip)
            self._emit(_event("mandatory_draw", player=player, chip=str(chip), pos=pos))

    # ------------------------------------------------------------------
    # Pulling phase
    # ------------------------------------------------------------------

    def _run_pulling(self, player: Player, state: GameState) -> None:
        self._emit(_event("pulling_start", player=player))

        # Apply bonus coins from fortune card
        if self._bonus_coins:
            player.coins += self._bonus_coins

        while True:
            if player.bag.is_empty:
                break
            if player.cauldron.exploded:
                break

            if not player.strategy.should_continue_pulling(player, state):
                player._current_record.stopped_voluntarily = True
                self._emit(_event("player_stopped", player=player,
                                  pos=player.cauldron.position,
                                  white_sum=player.cauldron.white_sum))
                break

            chip = player.draw_chip()
            self._emit(_event("chip_drawn", player=player, chip=str(chip),
                              white_sum_before=player.cauldron.white_sum))

            # Flask check (before placing); respect NO_FLASK fortune card
            if (player.flask_full and not self._flask_disabled
                    and player.strategy.use_flask(player, state, chip)):
                player.use_flask(chip)
                self._emit(_event("flask_used", player=player, chip_returned=str(chip)))
                continue

            # Apply strong ingredient bonus (advance extra for non-white)
            if self._strong_ingredient_bonus and chip.color != ChipColor.WHITE:
                # Temporarily boost chip value by creating a proxy
                boosted_value = chip.value + self._strong_ingredient_bonus
                from quacks.chips import Chip as ChipCls
                boosted_chip = ChipCls(chip.color, boosted_value)
                pos, ruby_spaces = player.place_chip(boosted_chip)
                # But record the actual chip drawn
                player.cauldron._placed[-1] = type(player.cauldron._placed[-1])(
                    chip, pos, player.cauldron._placed[-1].draw_order
                )
            else:
                pos, ruby_spaces = player.place_chip(chip)

            # Extra ruby on landing (fortune card)
            if self._extra_ruby_on_landing and ruby_spaces:
                player.rubies += len(ruby_spaces)
                if player._current_record:
                    player._current_record.rubies_earned += len(ruby_spaces)

            self._emit(_event("chip_placed", player=player, chip=str(chip),
                              position=pos, rubies_hit=ruby_spaces))

            # Yellow effect
            if chip.color == ChipColor.YELLOW:
                page = player.book_pages.get(ChipColor.YELLOW, 1)
                effect = get_effect(ChipColor.YELLOW, page)
                if effect:
                    result = effect.apply(player, state, chip=chip)
                    if result.get("yellow_returned_white"):
                        self._emit(_event("yellow_power", player=player,
                                          returned=result["yellow_returned_white"]))

            # Blue effect (all pages)
            if chip.color == ChipColor.BLUE:
                page = player.book_pages.get(ChipColor.BLUE, 1)
                effect = get_effect(ChipColor.BLUE, page)
                if effect:
                    result = effect.apply(player, state, chip=chip)
                    if result.get("blue_placed"):
                        self._emit(_event("blue_power", player=player,
                                          placed=result["blue_placed"]))

            # Red effect
            if chip.color == ChipColor.RED:
                page = player.book_pages.get(ChipColor.RED, 1)
                effect = get_effect(ChipColor.RED, page)
                if effect and effect.phase == "on_draw":
                    result = effect.apply(player, state, chip=chip)
                    if result.get("red_extra", 0):
                        self._emit(_event("red_power", player=player,
                                          extra=result["red_extra"]))

            if player.cauldron.exploded:
                if self._explode_ruby_bonus:
                    player.rubies += self._explode_ruby_bonus
                    if player._current_record:
                        player._current_record.rubies_earned += self._explode_ruby_bonus
                self._emit(_event("explosion", player=player,
                                  position=player.cauldron.position,
                                  white_sum=player.cauldron.white_sum))
                break

        self._emit(_event("pulling_end", player=player,
                          position=player.cauldron.position,
                          exploded=player.cauldron.exploded))

    # ------------------------------------------------------------------
    # Evaluation A: VP scoring
    # ------------------------------------------------------------------

    def _run_evaluation_a(self, state: GameState) -> None:
        non_exploded = [p for p in self.players if not p.cauldron.exploded]
        if non_exploded:
            max_pos = max(p.cauldron.position for p in non_exploded)
            bonus_rollers = [p for p in non_exploded if p.cauldron.position == max_pos]
            for roller in bonus_rollers:
                face = roll_bonus_die(self.rng)
                self._apply_bonus_die(roller, face)
                if roller._current_record:
                    roller._current_record.bonus_die_rolled = True
                    roller._current_record.bonus_die_result = face.value
                self._emit(_event("bonus_die", player=roller, face=face.value))

        for player in self.players:
            reward = player.cauldron.reward
            if player.cauldron.exploded:
                choice = player.choose_explosion_outcome(state)
                if choice == ExplosionChoice.VP:
                    vp = reward.vp * self._vp_multiplier
                    player.score_vp(vp)
                    self._emit(_event("explosion_choice_vp", player=player, vp=vp))
                else:
                    player.earn_coins(reward.coins)
                    self._emit(_event("explosion_choice_coins", player=player,
                                      coins=reward.coins))
            else:
                vp = reward.vp * self._vp_multiplier
                if (self._stop_bonus_vp and player._current_record
                        and player._current_record.stopped_voluntarily):
                    vp += self._stop_bonus_vp
                player.score_vp(vp)
                player.earn_coins(reward.coins)
                self._emit(_event("scoring", player=player, vp=vp, coins=reward.coins))

    def _apply_bonus_die(self, player: Player, face: BonusDieFace) -> None:
        match face:
            case BonusDieFace.RUBY:
                player.rubies += 1
                if player._current_record:
                    player._current_record.rubies_earned += 1
            case BonusDieFace.DROPLET:
                player.cauldron.advance_droplet(1)
            case BonusDieFace.ORANGE_CHIP:
                from quacks.chips import ORANGE_1
                player.bag.add(ORANGE_1)

    # ------------------------------------------------------------------
    # Evaluation B: ingredient effects
    # ------------------------------------------------------------------

    def _run_evaluation_b(self, state: GameState) -> None:
        for player in self.players:
            green_page = player.book_pages.get(ChipColor.GREEN, 1)
            effect = get_effect(ChipColor.GREEN, green_page)
            if effect:
                result = effect.apply(player, state)
                advance = result.get("green_advance", 0)
                if advance:
                    if player._current_record:
                        player._current_record.green_advance = advance
                    old_reward = cauldron_reward(player.cauldron.position - advance)
                    new_reward = player.cauldron.reward
                    extra_vp = (new_reward.vp - old_reward.vp) * self._vp_multiplier
                    extra_coins = new_reward.coins - old_reward.coins
                    if extra_vp > 0:
                        player.score_vp(extra_vp)
                    if not player.cauldron.exploded and extra_coins > 0:
                        player.earn_coins(extra_coins)
                    self._emit(_event("green_power", player=player,
                                      advance=advance, extra_vp=extra_vp))
                rubies = result.get("rubies_earned", 0)
                if rubies and player._current_record:
                    player._current_record.rubies_earned += rubies

            black_page = player.book_pages.get(ChipColor.BLACK, 1)
            black_effect = get_effect(ChipColor.BLACK, black_page)
            if black_effect and player.cauldron.count_color(ChipColor.BLACK) > 0:
                black_effect.apply(player, state)

    # ------------------------------------------------------------------
    # Evaluation D: buying
    # ------------------------------------------------------------------

    def _run_evaluation_d(self, state: GameState) -> None:
        for player in self.players:
            purple_page = player.book_pages.get(ChipColor.PURPLE, 1)
            purple_effect = get_effect(ChipColor.PURPLE, purple_page)
            if purple_effect and player.cauldron.count_color(ChipColor.PURPLE) > 0:
                result = purple_effect.apply(player, state)
                if result.get("purple_upgrade") and player._current_record:
                    player._current_record.purple_upgrade = result["purple_upgrade"]
                    self._emit(_event("purple_upgrade", player=player,
                                      upgrade=result["purple_upgrade"]))

            if player.coins > 0:
                purchases = player.strategy.choose_purchases(player, state, player.coins)
                for chip in purchases:
                    cost = self.market.cost(chip)
                    if cost is None:
                        continue
                    success, reason = self.market.buy(chip, player.coins)
                    if success:
                        player.buy_chip(chip, cost)
                        self._emit(_event("chip_purchased", player=player,
                                          chip=str(chip), cost=cost))

    # ------------------------------------------------------------------
    # Evaluation E: ruby spending + reset
    # ------------------------------------------------------------------

    def _run_evaluation_e(self, state: GameState) -> None:
        for player in self.players:
            advances, refill = player.strategy.choose_ruby_spending(player, state)
            if refill:
                player.spend_rubies_for_flask()
            player.spend_rubies_for_droplet(advances)

    # ------------------------------------------------------------------
    # Rat stone computation
    # ------------------------------------------------------------------

    def _compute_rat_advances(self) -> dict[str, int]:
        if self.round_number == 1:
            return {p.name: 0 for p in self.players}
        leader_score = max(p.scoring_position for p in self.players)
        return {
            p.name: max(0, (leader_score - p.scoring_position) // 2) * self._rat_multiplier
            for p in self.players
        }

    # ------------------------------------------------------------------
    # End of game
    # ------------------------------------------------------------------

    def _compute_result(self) -> "GameResult":
        self.phase = GamePhase.GAME_OVER
        final_scores: dict[str, int] = {}
        for player in self.players:
            ruby_vp = rubies_to_vp(player.rubies)
            final_scores[player.name] = player.scoring_position + ruby_vp

        max_score = max(final_scores.values())
        top_players = [n for n, v in final_scores.items() if v == max_score]
        winner = self.rng.choice(top_players)
        self._emit(_event("game_over", scores=final_scores, winner=winner))
        return GameResult(
            players=self.players,
            final_scores=final_scores,
            winner_name=winner,
            rounds_played=TOTAL_ROUNDS,
        )


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass
class GameResult:
    players: list[Player]
    final_scores: dict[str, int]
    winner_name: str
    rounds_played: int

    @property
    def winner(self) -> Player:
        return next(p for p in self.players if p.name == self.winner_name)

    def standings(self) -> list[tuple[str, int]]:
        return sorted(self.final_scores.items(), key=lambda x: -x[1])

    def __repr__(self) -> str:
        standings = ", ".join(f"{n}={v}" for n, v in self.standings())
        return f"GameResult(winner={self.winner_name}, scores=[{standings}])"
