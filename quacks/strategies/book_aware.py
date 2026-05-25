"""Book-aware pulling strategy.

Adjusts the white-sum stop threshold dynamically based on:
  - which ingredient book pages are active for the player
  - how many valuable ingredient chips remain in the bag

Intuition: if your Blue page 3 is active and there are 2 blue chips
still in the bag, drawing them is worth far more than a plain chip
(each one forces an extra placement from the bag top). You should
tolerate more white-sum risk to keep pulling for those chips.

The threshold scales per remaining chip of each color, capped at
max_chips_per_color to avoid runaway values on large bags.
"""

from __future__ import annotations
from collections import Counter
from typing import TYPE_CHECKING

from quacks.enums import ChipColor
from quacks.strategies.base import PlayerStrategy
from quacks.strategies.buying import greedy_value_buy

if TYPE_CHECKING:
    from quacks.chips import Chip
    from quacks.game import GameState
    from quacks.player import Player


# Per-chip threshold bonus by color and minimum page required.
# Keyed as {color: [(min_page, bonus_per_chip), ...]} in ascending page order.
# The highest applicable level for the active page is used.
_BONUSES: dict[ChipColor, list[tuple[int, float]]] = {
    ChipColor.YELLOW: [
        (2, 1.0),   # page 2: return a white from pot → real safety gain
        (3, 1.5),   # page 3: return any chip
        (4, 2.0),   # page 4: return up to 2 chips
    ],
    ChipColor.BLUE: [
        (2, 0.75),  # page 2: peek one extra chip
        (3, 1.0),   # page 3: forced placement of best non-white
        (4, 1.25),  # page 4: peek two extra chips
    ],
    ChipColor.GREEN: [
        (2, 0.5),   # page 2: +1 ruby per green in pot
        (3, 0.75),  # page 3: advance by green count
        (4, 1.0),   # page 4: +2 rubies per green
    ],
    ChipColor.RED: [
        (2, 0.5),   # page 2: white-1 chips move when red in pot
        (3, 0.5),
        (4, 0.75),
    ],
    ChipColor.PURPLE: [
        (2, 0.25),
        (4, 0.5),
    ],
    ChipColor.BLACK: [
        (2, 0.25),
        (3, 0.5),   # page 3: peek all — useful information
        (4, 0.75),  # page 4: may permanently remove a chip
    ],
    ChipColor.ORANGE: [
        (1, 0.2),   # orange always gives a bonus position (page-independent)
    ],
}


def _chip_bonus(color: ChipColor, page: int) -> float:
    """Return the per-chip threshold bonus for this color at the active page."""
    levels = _BONUSES.get(color, [])
    result = 0.0
    for min_page, bonus in levels:
        if page >= min_page:
            result = bonus   # levels are ascending, so last match wins
    return result


class BookAwareStrategy(PlayerStrategy):
    """Threshold strategy that raises its pull limit when valuable ingredient
    chips are still in the bag.

    Parameters
    ----------
    base_threshold : int
        White-sum threshold when no ingredient bonuses apply (same role as
        ThresholdStrategy's ``t``).
    max_threshold : int
        Hard cap on the adjusted threshold.  7 allows the strategy to push
        aggressively when high-value ingredient chips remain in the bag.
    max_chips_per_color : int
        Maximum chips of one color counted toward the bonus (prevents a
        huge bag full of one ingredient from inflating the threshold wildly).
    coin_rate : float
        Coin → VP rate used by the buying heuristic.
    """

    def __init__(
        self,
        base_threshold: int = 5,
        max_threshold: int = 7,
        max_chips_per_color: int = 3,
        coin_rate: float = 0.25,
    ) -> None:
        self.base_threshold = base_threshold
        self.max_threshold = max_threshold
        self.max_chips_per_color = max_chips_per_color
        self.coin_rate = coin_rate

    @property
    def name(self) -> str:
        return f"BookAware(base={self.base_threshold},max={self.max_threshold})"

    def _adjusted_threshold(self, player: "Player") -> float:
        """Compute the effective white-sum threshold for this decision."""
        bag_chips = player.bag.all_chips()
        if not bag_chips:
            return self.base_threshold

        pages = player.book_pages
        threshold = float(self.base_threshold)

        color_counts: Counter[ChipColor] = Counter(c.color for c in bag_chips)
        for color, count in color_counts.items():
            page = pages.get(color, 1)
            bonus = _chip_bonus(color, page)
            if bonus:
                threshold += bonus * min(count, self.max_chips_per_color)

        return min(threshold, self.max_threshold)

    def should_continue_pulling(
        self, player: "Player", state: "GameState"
    ) -> bool:
        if player.cauldron.exploded or player.bag.is_empty:
            return False
        return player.cauldron.white_sum < self._adjusted_threshold(player)

    def choose_purchases(
        self, player: "Player", state: "GameState", coins: int
    ) -> list["Chip"]:
        return greedy_value_buy(player, state, coins, coin_rate=self.coin_rate)
