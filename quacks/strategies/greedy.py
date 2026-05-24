"""Greedy buyer strategy: maximise coins earned, spend aggressively on best chips."""

from __future__ import annotations
from typing import TYPE_CHECKING

from quacks.enums import ChipColor
from quacks.strategies.base import PlayerStrategy

if TYPE_CHECKING:
    from quacks.chips import Chip
    from quacks.game import GameState
    from quacks.player import Player


class GreedyBuyerStrategy(PlayerStrategy):
    """Push hard to maximise coins, then buy the most expensive chips possible.

    Continues drawing until either:
    - Explosion, OR
    - White sum reaches 7 (maximum safe), OR
    - Bag is empty
    """

    def __init__(self, max_white_sum: int = 6) -> None:
        self.max_white_sum = max_white_sum

    @property
    def name(self) -> str:
        return f"GreedyBuyer(max_white={self.max_white_sum})"

    def should_continue_pulling(self, player: "Player", state: "GameState") -> bool:
        cauldron = player.cauldron
        if cauldron.exploded:
            return False
        if cauldron.white_sum >= self.max_white_sum:
            return False
        if player.bag.is_empty:
            return False
        return True

    def choose_purchases(
        self, player: "Player", state: "GameState", coins: int
    ) -> list["Chip"]:
        """Buy the highest-value chip available, maximising cost efficiency."""
        from quacks.chips import Chip
        purchases: list[Chip] = []
        remaining = coins
        available = state.market.available_chips(state.round_number)

        while remaining > 0:
            # Find best bang-for-buck chip we can afford
            affordable = [
                l for l in available
                if l.cost <= remaining and l.stock > 0
            ]
            if not affordable:
                break
            # Pick highest-cost chip (= most powerful purchase)
            best = max(affordable, key=lambda l: (l.cost, l.chip.value))
            purchases.append(best.chip)
            remaining -= best.cost
            # Update stock in listing (simulate consumption)
            best.stock -= 1
            if best.stock == 0:
                available.remove(best)

        return purchases
