"""Expected-Value stopping strategy.

At each draw decision computes the expected marginal value of drawing one
more chip versus stopping now, using a two-tier approach:

  EV(stop)  = VP(pos) + coins(pos) * coin_rate
  EV(draw)  = average over all chips in bag of:
               - explosion_value(new_pos)   if draw would explode
               - stop_value(new_pos)        otherwise   [one-step lookahead]

Draws if EV(draw) > EV(stop).

This one-step lookahead is O(n) per decision (n = bag size), making it
fast enough for batch simulations while still being meaningfully smarter
than simple white-sum thresholds: it correctly weights explosion risk,
marginal VP at the landing position, and coins, all from the actual bag
composition rather than a fixed heuristic.

coin_rate converts coins into VP-equivalent. 0.25 → 4 coins ≈ 1 VP.
"""

from __future__ import annotations
from collections import Counter
from typing import TYPE_CHECKING

from quacks.enums import ChipColor
from quacks.scoring import cauldron_reward, MAX_CAULDRON_POSITION
from quacks.strategies.base import PlayerStrategy

if TYPE_CHECKING:
    from quacks.chips import Chip
    from quacks.game import GameState
    from quacks.player import Player


def _chip_key(chip: "Chip") -> tuple:
    return (chip.color.value, chip.value)


class EVOptimalStrategy(PlayerStrategy):
    """One-step EV-optimal pull-or-stop decisions based on bag composition.

    At each decision the strategy considers the expected outcome of drawing
    exactly one more chip (then assuming we stop):
      - Each chip in the bag is equally likely to be drawn
      - Drawing a chip that causes explosion yields explosion_value(new_pos)
      - Drawing a safe chip yields stop_value(new_pos)
    Draws iff this one-step EV exceeds stop_value(current_pos).
    """

    def __init__(self, coin_rate: float = 0.25) -> None:
        self.coin_rate = coin_rate

    @property
    def name(self) -> str:
        return f"EVOptimal(cr={self.coin_rate})"

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
        n = len(chips)

        stop_val = self._stop_value(position)
        draw_val = self._one_step_ev(chips, white_sum, position, n)
        return draw_val > stop_val

    # ------------------------------------------------------------------
    # One-step EV
    # ------------------------------------------------------------------

    def _stop_value(self, position: int) -> float:
        r = cauldron_reward(position)
        return r.vp + r.coins * self.coin_rate

    def _explosion_value(self, position: int) -> float:
        r = cauldron_reward(position)
        return max(float(r.vp), r.coins * self.coin_rate)

    def _one_step_ev(
        self, chips: list, white_sum: int, position: int, n: int
    ) -> float:
        """Expected value of drawing one chip and then stopping."""
        chip_counts = Counter(chips)
        total = 0.0

        for chip, count in chip_counts.items():
            if chip.color == ChipColor.WHITE:
                new_white = white_sum + chip.value
            else:
                new_white = white_sum

            new_pos = min(position + chip.value, MAX_CAULDRON_POSITION)

            if chip.color == ChipColor.WHITE and new_white > 7:
                val = self._explosion_value(new_pos)
            else:
                val = self._stop_value(new_pos)

            total += val * count

        return total / n

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
