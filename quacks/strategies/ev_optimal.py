"""Expected-Value Optimal stopping strategy using full recursive DP.

At each draw decision the strategy computes the exact expected value of
drawing one more chip (then continuing optimally) versus stopping now.
It draws if and only if E[draw] > E[stop].

The DP state is (sorted_chip_tuple, white_sum_in_pot, cauldron_position).
Memoisation makes a single round's computation ~1 ms even for bags of 15+.

coin_rate converts coins into a VP-equivalent for the EV calculation.
A value of 0.25 means four coins ≈ one VP — reasonable for mid-game when
purchased chips still have several rounds to contribute.
"""

from __future__ import annotations
from collections import Counter
from typing import TYPE_CHECKING

from quacks.enums import ChipColor, ExplosionChoice
from quacks.scoring import cauldron_reward, MAX_CAULDRON_POSITION
from quacks.strategies.base import PlayerStrategy

if TYPE_CHECKING:
    from quacks.chips import Chip
    from quacks.game import GameState
    from quacks.player import Player


def _chip_key(chip: "Chip") -> tuple:
    return (chip.color.value, chip.value)


class EVOptimalStrategy(PlayerStrategy):
    """Exact EV-optimal pull-or-stop decisions via recursive DP with memoisation."""

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

        chips = tuple(sorted(player.bag.all_chips(), key=_chip_key))
        white_sum = cauldron.white_sum
        position = cauldron.position
        memo: dict = {}

        stop_val = self._stop_value(position)
        draw_val = self._draw_ev(chips, white_sum, position, memo)
        return draw_val > stop_val

    # ------------------------------------------------------------------
    # DP helpers
    # ------------------------------------------------------------------

    def _stop_value(self, position: int) -> float:
        r = cauldron_reward(position)
        return r.vp + r.coins * self.coin_rate

    def _explosion_value(self, position: int) -> float:
        """When exploded at position: player takes the better of VP or coins."""
        r = cauldron_reward(position)
        return max(float(r.vp), r.coins * self.coin_rate)

    def _optimal_value(
        self,
        chips: tuple,
        white_sum: int,
        position: int,
        memo: dict,
    ) -> float:
        """Optimal expected total value from this state (VP + coin-eq).

        Returns max(stop_now, E[draw_optimally]).
        """
        key = (chips, white_sum, position)
        if key in memo:
            return memo[key]

        stop_val = self._stop_value(position)
        if not chips:
            memo[key] = stop_val
            return stop_val

        draw_val = self._draw_ev(chips, white_sum, position, memo)
        result = max(stop_val, draw_val)
        memo[key] = result
        return result

    def _draw_ev(
        self,
        chips: tuple,
        white_sum: int,
        position: int,
        memo: dict,
    ) -> float:
        """Expected value of drawing one chip, then continuing optimally.

        Deduplicates identical chip types to avoid redundant sub-tree work.
        """
        n = len(chips)
        chip_list = list(chips)
        chip_counts = Counter(chip_list)
        total = 0.0

        for chip, count in chip_counts.items():
            remaining_list = chip_list.copy()
            remaining_list.remove(chip)            # removes first occurrence
            remaining = tuple(remaining_list)      # still sorted (sorted - one item)

            if chip.color == ChipColor.WHITE:
                new_white = white_sum + chip.value
            else:
                new_white = white_sum

            new_pos = min(position + chip.value, MAX_CAULDRON_POSITION)

            if chip.color == ChipColor.WHITE and new_white > 7:
                chip_ev = self._explosion_value(new_pos)
            else:
                chip_ev = self._optimal_value(remaining, new_white, new_pos, memo)

            total += chip_ev * count

        return total / n

    # ------------------------------------------------------------------
    # Buying: prefer high-value non-white chips; avoid diluting the bag
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
