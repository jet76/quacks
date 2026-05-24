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
from quacks.enums import ChipColor, GamePhase, FortuneCardType, ExplosionChoice, BonusDieFace
from quacks.fortune_teller import FortuneCard, FortuneEffect, make_shuffled_deck
from quacks.market import Market
from quacks.player import Player
from quacks.scoring import cauldron_reward, SCORING_TRACK_MAX, rubies_to_vp
from quacks.ingredients.registry import get_effect


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

Event = dict  # simple dict-based event system; keys: "type", "player", "data"
EventHandler = Callable[[Event], None]


def _event(event_type: str, player: Optional[Player] = None, **data) -> Event:
    return {"type": event_type, "player": player.name if player else None, **data}


# ---------------------------------------------------------------------------
# Game engine
# ---------------------------------------------------------------------------

class Game:
    """Full simulation of one complete game of Quacks of Quedlinburg.

    Usage:
        game = Game(players=[...], n_players=4)
        result = game.run()
    """

    def __init__(
        self,
        players: list[Player],
        book_pages: dict[ChipColor, int] | None = None,
        rng: random.Random | None = None,
        event_handlers: list[EventHandler] | None = None,
    ) -> None:
        if not 2 <= len(players) <= 4:
            raise ValueError(f"Need 2–4 players, got {len(players)}")
        self.players = players
        self.rng = rng or random.Random()
        self._handlers: list[EventHandler] = event_handlers or []

        # Thread the game RNG into each player's bag for full determinism
        for player in self.players:
            player.bag._rng = self.rng

        self.market = Market(n_players=len(players), book_pages=book_pages)
        self.fortune_deck: list[FortuneCard] = make_shuffled_deck(self.rng)
        self.round_number: int = 0
        self.phase: GamePhase = GamePhase.SETUP
        self._current_card: Optional[FortuneCard] = None

        # Round-long modifiers set by Fortune Teller cards
        self._rat_multiplier: int = 1
        self._vp_multiplier: int = 1
        self._stop_bonus_vp: int = 0
        self._explode_ruby_bonus: int = 0
        self._flask_free_refill: bool = False

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
        """Run the complete 9-round game and return the result."""
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
        self._emit(_event("fortune_card", card_id=card.card_id, name=card.name, effect=card.effect.name))

        # --- Begin player rounds ---
        rat_advances = self._compute_rat_advances()
        for player in self.players:
            player.begin_round(rnd, card.card_id, rat_advances.get(player.name, 0))

        # Fortune card: flask free refill
        if self._flask_free_refill:
            for p in self.players:
                p.flask_full = True

        # Fortune card: extra mandatory draw before pulling (card 9)
        if card.effect == FortuneEffect.EXTRA_DRAW_BEFORE:
            for player in self.players:
                self._mandatory_extra_draw(player, state, safe=False)

        # Fortune card: free draw before pulling (card 3)
        if card.effect == FortuneEffect.FREE_CHIP_DRAW:
            for player in self.players:
                self._mandatory_extra_draw(player, state, safe=True)

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

        # --- Evaluation C: rat stones ---
        self.phase = GamePhase.EVALUATION_C
        # (Rat advances are computed for NEXT round, not applied here)

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

    def _apply_fortune_card_pre(self, card: FortuneCard, state: GameState) -> None:
        """Apply pre-round fortune effects."""
        match card.effect:
            case FortuneEffect.DROPLET_ADVANCE:
                for player in self.players:
                    player.cauldron.advance_droplet(card.magnitude)
                    self._emit(_event("droplet_advanced", player=player, amount=card.magnitude))
            case FortuneEffect.RAT_DOUBLE:
                self._rat_multiplier = card.magnitude
            case FortuneEffect.STOP_BONUS_VP:
                self._stop_bonus_vp = card.magnitude
            case FortuneEffect.EXPLODE_RUBY:
                self._explode_ruby_bonus = card.magnitude
            case FortuneEffect.FLASK_FREE_REFILL:
                self._flask_free_refill = True
            case FortuneEffect.VP_DOUBLED:
                self._vp_multiplier = card.magnitude
            case FortuneEffect.FREE_CHIP_FROM_SUPPLY:
                self._apply_free_chip_from_supply(state)
            case _:
                pass  # EXTRA_DRAW_BEFORE and FREE_CHIP_DRAW handled separately

    def _apply_free_chip_from_supply(self, state: GameState) -> None:
        """Fortune card 6: each player gets one free chip from market."""
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

    def _mandatory_extra_draw(self, player: Player, state: GameState, safe: bool) -> None:
        """Draw one chip before pulling starts (fortune card 3 = safe, 9 = unsafe)."""
        if player.bag.is_empty:
            return
        chip = player.draw_chip()
        if safe:
            # Safe draw: does not count toward explosion
            pos, _ = player.cauldron.place(chip)
            if chip.color == ChipColor.WHITE:
                player.cauldron._white_sum -= chip.value  # undo white sum addition
            self._emit(_event("safe_extra_draw", player=player, chip=str(chip)))
        else:
            pos, rubies = player.cauldron.place(chip)
            player.rubies += len(rubies)
            self._emit(_event("mandatory_draw", player=player, chip=str(chip), pos=pos))

    # ------------------------------------------------------------------
    # Pulling phase
    # ------------------------------------------------------------------

    def _run_pulling(self, player: Player, state: GameState) -> None:
        self._emit(_event("pulling_start", player=player))

        while True:
            if player.bag.is_empty:
                break
            if player.cauldron.exploded:
                break

            # Strategy decides to continue or stop
            if not player.strategy.should_continue_pulling(player, state):
                player._current_record.stopped_voluntarily = True
                self._emit(_event("player_stopped", player=player,
                                  pos=player.cauldron.position,
                                  white_sum=player.cauldron.white_sum))
                break

            # Draw chip
            chip = player.draw_chip()
            self._emit(_event("chip_drawn", player=player, chip=str(chip),
                              white_sum_before=player.cauldron.white_sum))

            # Check flask (before placing)
            if player.flask_full and player.strategy.use_flask(player, state, chip):
                player.use_flask(chip)
                self._emit(_event("flask_used", player=player, chip_returned=str(chip)))
                continue

            # Place chip in cauldron
            pos, ruby_spaces = player.place_chip(chip)
            self._emit(_event("chip_placed", player=player, chip=str(chip),
                              position=pos, rubies_hit=ruby_spaces))

            # Yellow effect: may return preceding white chip
            if chip.color == ChipColor.YELLOW:
                page = player.book_pages.get(ChipColor.YELLOW, 1)
                effect = get_effect(ChipColor.YELLOW, page)
                if effect:
                    result = effect.apply(player, state, chip=chip)
                    if result.get("yellow_returned_white"):
                        self._emit(_event("yellow_power", player=player,
                                          returned=result["yellow_returned_white"]))

            # Blue effect: additional chip placement
            if chip.color == ChipColor.BLUE:
                page = player.book_pages.get(ChipColor.BLUE, 1)
                if page == 1:
                    effect = get_effect(ChipColor.BLUE, 1)
                    if effect:
                        result = effect.apply(player, state, chip=chip)
                        if result.get("blue_placed"):
                            self._emit(_event("blue_power", player=player,
                                              placed=result["blue_placed"]))

            # Red effect: extra spaces from orange
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
        # Determine who rolled bonus die (highest non-exploded cauldron pos)
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
                    self._emit(_event("explosion_choice_coins", player=player, coins=reward.coins))
            else:
                vp = reward.vp * self._vp_multiplier
                if self._stop_bonus_vp and player._current_record and player._current_record.stopped_voluntarily:
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
    # Evaluation B: special ingredient effects
    # ------------------------------------------------------------------

    def _run_evaluation_b(self, state: GameState) -> None:
        for player in self.players:
            # Green page 1: bonus if white sum = 7
            green_page = player.book_pages.get(ChipColor.GREEN, 1)
            if green_page == 1:
                effect = get_effect(ChipColor.GREEN, 1)
                if effect:
                    result = effect.apply(player, state)
                    advance = result.get("green_advance", 0)
                    if advance:
                        if player._current_record:
                            player._current_record.green_advance = advance
                        # Re-score with new position
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
            elif green_page == 2:
                effect = get_effect(ChipColor.GREEN, 2)
                if effect:
                    effect.apply(player, state)

            # Black effect
            black_page = player.book_pages.get(ChipColor.BLACK, 1)
            black_effect = get_effect(ChipColor.BLACK, black_page)
            if black_effect and player.cauldron.count_color(ChipColor.BLACK) > 0:
                black_effect.apply(player, state)

            # Purple effect (applied in buying phase, prepared here)

    # ------------------------------------------------------------------
    # Evaluation D: buying
    # ------------------------------------------------------------------

    def _run_evaluation_d(self, state: GameState) -> None:
        for player in self.players:
            # Purple upgrade (if purple in pot)
            purple_page = player.book_pages.get(ChipColor.PURPLE, 1)
            purple_effect = get_effect(ChipColor.PURPLE, purple_page)
            if purple_effect and player.cauldron.count_color(ChipColor.PURPLE) > 0:
                result = purple_effect.apply(player, state)
                if result.get("purple_upgrade") and player._current_record:
                    player._current_record.purple_upgrade = result["purple_upgrade"]
                    self._emit(_event("purple_upgrade", player=player,
                                      upgrade=result["purple_upgrade"]))

            # Regular purchases
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
                    else:
                        self._emit(_event("purchase_failed", player=player,
                                          chip=str(chip), reason=reason))

    # ------------------------------------------------------------------
    # Evaluation E: ruby spending + reset
    # ------------------------------------------------------------------

    def _run_evaluation_e(self, state: GameState) -> None:
        for player in self.players:
            advances, refill = player.strategy.choose_ruby_spending(player, state)
            if refill:
                player.spend_rubies_for_flask()
            actual_advances = player.spend_rubies_for_droplet(advances)
            if actual_advances:
                self._emit(_event("droplet_ruby_advance", player=player, advances=actual_advances))

    # ------------------------------------------------------------------
    # Rat stone computation (for next round)
    # ------------------------------------------------------------------

    def _compute_rat_advances(self) -> dict[str, int]:
        """Compute how many rat stone spaces each player gets next round."""
        if self.round_number == 1:
            return {p.name: 0 for p in self.players}
        leader_score = max(p.scoring_position for p in self.players)
        advances = {}
        for player in self.players:
            gap = max(0, leader_score - player.scoring_position)
            advances[player.name] = gap * self._rat_multiplier
        return advances

    # ------------------------------------------------------------------
    # End of game
    # ------------------------------------------------------------------

    def _compute_result(self) -> "GameResult":
        self.phase = GamePhase.GAME_OVER
        final_scores: dict[str, int] = {}
        for player in self.players:
            # Convert remaining rubies to VP
            ruby_vp = rubies_to_vp(player.rubies)
            total_vp = player.scoring_position + ruby_vp
            final_scores[player.name] = total_vp

        # Tie-break randomly among players with the highest score
        max_score = max(final_scores.values())
        top_players = [name for name, vp in final_scores.items() if vp == max_score]
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
    final_scores: dict[str, int]          # name → total VP
    winner_name: str
    rounds_played: int

    @property
    def winner(self) -> Player:
        return next(p for p in self.players if p.name == self.winner_name)

    def standings(self) -> list[tuple[str, int]]:
        """Return [(name, vp), ...] sorted by VP descending."""
        return sorted(self.final_scores.items(), key=lambda x: -x[1])

    def __repr__(self) -> str:
        standings = ", ".join(f"{n}={v}" for n, v in self.standings())
        return f"GameResult(winner={self.winner_name}, scores=[{standings}])"
