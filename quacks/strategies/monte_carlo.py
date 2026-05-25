"""Monte Carlo stopping strategy.

Estimates the EV of drawing vs stopping by forward-simulating N random
completions of the pulling phase from the current state.

Improvement over a fixed threshold or simple one-step EV: each simulation
follows a multi-step path where the internal stopping decision at every step
uses the same one-step EV criterion as EVOptimalStrategy. This makes the
simulated paths genuinely rational rather than using an ad-hoc threshold,
so the estimated outcome of "draw one chip then play optimally" is more
accurate.

Compared to EVOptimalStrategy:
- EVOptimal: analytic one-step lookahead, deterministic, O(n)
- MonteCarlo: stochastic multi-step forward simulation, O(n * n_simulations)
  Each simulation continues drawing until the one-step EV says to stop,
  capturing the value of subsequent draws that the one-step analytic
  calculation ignores.
"""

from __future__ import annotations
import random
from collections import Counter
from typing import TYPE_CHECKING

from quacks.enums import ChipColor
from quacks.scoring import cauldron_reward, MAX_CAULDRON_POSITION
from quacks.strategies.base import PlayerStrategy

if TYPE_CHECKING:
    from quacks.chips import Chip
    from quacks.game import GameState
    from quacks.player import Player


class MonteCarloStrategy(PlayerStrategy):
    """Pull-or-stop decisions via Monte Carlo forward simulation.

    For each decision the strategy runs n_simulations random completions
    of the pulling phase. Each completion:
      1. Draws one chip immediately (the action being evaluated)
      2. Continues drawing using the one-step EV stopping criterion
         until EV(stop) >= EV(draw-one-more) or the bag is empty
      3. Returns the final total reward (VP + coins * coin_rate)

    The average outcome across simulations is compared to the current
    stop value; draws if the average is higher.
    """

    def __init__(
        self,
        n_simulations: int = 200,
        coin_rate: float = 0.25,
        rng_seed: int | None = None,
    ) -> None:
        self.n_simulations = n_simulations
        self.coin_rate = coin_rate
        self._rng = random.Random(rng_seed)

    @property
    def name(self) -> str:
        return f"MonteCarlo(n={self.n_simulations})"

    # ------------------------------------------------------------------
    # Core decision
    # ------------------------------------------------------------------

    def should_continue_pulling(self, player: "Player", state: "GameState") -> bool:
        cauldron = player.cauldron
        if cauldron.exploded or player.bag.is_empty:
            return False

        chips = player.bag.all_chips()
        white_sum = cauldron.white_sum
        position = cauldron.position

        stop_val = self._reward(position, exploded=False)
        draw_val = self._estimate_draw_ev(chips, white_sum, position)
        return draw_val > stop_val

    # ------------------------------------------------------------------
    # Simulation
    # ------------------------------------------------------------------

    def _reward(self, position: int, *, exploded: bool) -> float:
        r = cauldron_reward(position)
        if exploded:
            return max(float(r.vp), r.coins * self.coin_rate)
        return r.vp + r.coins * self.coin_rate

    def _one_step_ev(self, chips: list, white_sum: int, position: int) -> float:
        """Expected reward of drawing one chip and then stopping."""
        n = len(chips)
        if n == 0:
            return self._reward(position, exploded=False)
        counts = Counter(chips)
        total = 0.0
        for chip, count in counts.items():
            new_white = white_sum + chip.value if chip.color == ChipColor.WHITE else white_sum
            new_pos = min(position + chip.value, MAX_CAULDRON_POSITION)
            if chip.color == ChipColor.WHITE and new_white > 7:
                total += self._reward(new_pos, exploded=True) * count
            else:
                total += self._reward(new_pos, exploded=False) * count
        return total / n

    def _should_draw_in_sim(self, chips: list, white_sum: int, position: int) -> bool:
        """Internal stopping decision using one-step EV (same as EVOptimalStrategy)."""
        if not chips:
            return False
        stop_val = self._reward(position, exploded=False)
        draw_val = self._one_step_ev(chips, white_sum, position)
        return draw_val > stop_val

    def _estimate_draw_ev(self, chips: list, white_sum: int, position: int) -> float:
        total = 0.0
        for _ in range(self.n_simulations):
            total += self._simulate_one(list(chips), white_sum, position)
        return total / self.n_simulations

    def _simulate_one(self, chips: list, white_sum: int, position: int) -> float:
        """One forward sim: draw one chip, then follow one-step EV policy."""
        if not chips:
            return self._reward(position, exploded=False)

        # Draw the first chip (the action being evaluated)
        idx = self._rng.randrange(len(chips))
        chip = chips[idx]
        chips.pop(idx)

        if chip.color == ChipColor.WHITE:
            white_sum += chip.value
        position = min(position + chip.value, MAX_CAULDRON_POSITION)

        if chip.color == ChipColor.WHITE and white_sum > 7:
            return self._reward(position, exploded=True)

        # Continue drawing while one-step EV says to draw
        while chips and self._should_draw_in_sim(chips, white_sum, position):
            idx = self._rng.randrange(len(chips))
            chip = chips[idx]
            chips.pop(idx)

            if chip.color == ChipColor.WHITE:
                white_sum += chip.value
            position = min(position + chip.value, MAX_CAULDRON_POSITION)

            if chip.color == ChipColor.WHITE and white_sum > 7:
                return self._reward(position, exploded=True)

        return self._reward(position, exploded=False)

    def _p_explode(self, chips: list, white_sum: int) -> float:
        if not chips:
            return 0.0
        budget = 7 - white_sum
        dangerous = sum(1 for c in chips if c.color == ChipColor.WHITE and c.value > budget)
        return dangerous / len(chips)

    # ------------------------------------------------------------------
    # Buying
    # ------------------------------------------------------------------

    def choose_purchases(
        self, player: "Player", state: "GameState", coins: int
    ) -> list["Chip"]:
        purchases = []
        remaining = coins
        available = state.market.available_chips(state.round_number)

        priority = [
            ChipColor.GREEN,
            ChipColor.YELLOW,
            ChipColor.BLUE,
            ChipColor.RED,
            ChipColor.PURPLE,
            ChipColor.BLACK,
            ChipColor.ORANGE,
        ]
        for color in priority:
            if remaining <= 0:
                break
            color_chips = sorted(
                [l for l in available if l.chip.color == color and l.stock > 0],
                key=lambda l: l.chip.value,
                reverse=True,
            )
            for listing in color_chips:
                if listing.cost <= remaining:
                    purchases.append(listing.chip)
                    remaining -= listing.cost
                    break

        return purchases
