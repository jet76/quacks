"""Monte Carlo stopping strategy.

Rather than the exact DP used by EVOptimalStrategy, this estimates the
EV of drawing vs stopping by forward-simulating N random completions of
the pulling phase from the current state.

This is useful when:
- You want strategies that reason about the full remaining pulling phase
  (not just a one-chip lookahead)
- You want approximate but fast decisions with tunable accuracy

The simulated completions use a simple internal stopping heuristic
(stop when explosion probability exceeds sim_stop_threshold) to
represent plausible future play.
"""

from __future__ import annotations
import random
from typing import TYPE_CHECKING

from quacks.enums import ChipColor, ExplosionChoice
from quacks.scoring import cauldron_reward, MAX_CAULDRON_POSITION
from quacks.strategies.base import PlayerStrategy

if TYPE_CHECKING:
    from quacks.chips import Chip
    from quacks.game import GameState
    from quacks.player import Player


class MonteCarloStrategy(PlayerStrategy):
    """Pull-or-stop decisions via Monte Carlo forward simulation.

    For each decision the strategy runs n_simulations completions of the
    pulling phase, each time drawing one chip immediately and then
    continuing with the internal stopping heuristic. The average outcome
    is compared against stopping now; the action with higher expected
    value is taken.

    coin_rate: how many VP-equivalent a coin is worth (default 0.25).
    sim_stop_threshold: internal explosion-probability threshold used
        inside simulations (default 0.3 = stop when >30% chance of boom).
    """

    def __init__(
        self,
        n_simulations: int = 200,
        coin_rate: float = 0.25,
        sim_stop_threshold: float = 0.30,
    ) -> None:
        self.n_simulations = n_simulations
        self.coin_rate = coin_rate
        self.sim_stop_threshold = sim_stop_threshold
        self._rng = random.Random()

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
    # Simulation helpers
    # ------------------------------------------------------------------

    def _reward(self, position: int, *, exploded: bool) -> float:
        r = cauldron_reward(position)
        if exploded:
            return max(float(r.vp), r.coins * self.coin_rate)
        return r.vp + r.coins * self.coin_rate

    def _p_explode(self, chips: list, white_sum: int) -> float:
        if not chips:
            return 0.0
        budget = 7 - white_sum
        dangerous = sum(
            1 for c in chips if c.color == ChipColor.WHITE and c.value > budget
        )
        return dangerous / len(chips)

    def _estimate_draw_ev(
        self, chips: list, white_sum: int, position: int
    ) -> float:
        """Average outcome of drawing one chip then running internal heuristic."""
        total = 0.0
        for _ in range(self.n_simulations):
            total += self._simulate_one(list(chips), white_sum, position)
        return total / self.n_simulations

    def _simulate_one(
        self, chips: list, white_sum: int, position: int
    ) -> float:
        """One forward simulation: draw one chip, then apply internal heuristic."""
        if not chips:
            return self._reward(position, exploded=False)

        # Draw one chip (the action we're evaluating)
        idx = self._rng.randrange(len(chips))
        chip = chips[idx]
        chips.pop(idx)

        if chip.color == ChipColor.WHITE:
            white_sum += chip.value
        position = min(position + chip.value, MAX_CAULDRON_POSITION)

        if chip.color == ChipColor.WHITE and white_sum > 7:
            return self._reward(position, exploded=True)

        # Continue with internal stopping heuristic
        while chips:
            if self._p_explode(chips, white_sum) > self.sim_stop_threshold:
                break
            idx = self._rng.randrange(len(chips))
            chip = chips[idx]
            chips.pop(idx)

            if chip.color == ChipColor.WHITE:
                white_sum += chip.value
            position = min(position + chip.value, MAX_CAULDRON_POSITION)

            if chip.color == ChipColor.WHITE and white_sum > 7:
                return self._reward(position, exploded=True)

        return self._reward(position, exploded=False)

    # ------------------------------------------------------------------
    # Buying: same priority as EVOptimal
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
