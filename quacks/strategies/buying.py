"""Shared value-buying logic for pull-or-stop strategies.

Replaces the fixed-priority colour lists with a cost-adjusted EV score
that accounts for rounds remaining, chip face value, and colour strength.
Both EVOptimalStrategy and MonteCarloStrategy delegate choose_purchases here.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from quacks.enums import ChipColor

if TYPE_CHECKING:
    from quacks.chips import Chip
    from quacks.game import GameState
    from quacks.player import Player

# Relative pulling strength of each colour.
# Derived from effect quality: green/yellow top tier, orange filler.
_COLOR_WEIGHT: dict[ChipColor, float] = {
    ChipColor.GREEN:  2.0,
    ChipColor.YELLOW: 1.8,
    ChipColor.BLUE:   1.6,
    ChipColor.RED:    1.4,
    ChipColor.PURPLE: 1.2,
    ChipColor.BLACK:  1.1,
    ChipColor.ORANGE: 0.8,
    # Expansion colours (inactive in base game)
    ChipColor.CYAN:   1.5,
    ChipColor.GRAY:   0.9,
    ChipColor.PINK:   1.3,
}


def _chip_score(chip: "Chip", cost: int, rounds_left: int, coin_rate: float) -> float:
    """Score a potential purchase as marginal EV per coin over remaining rounds.

    Estimated marginal EV = chip.value * colour_weight * coin_rate * rounds_left.
    Dividing by cost gives value per coin, used to rank candidates.
    Returns a large negative value for unbuyable / zero-round cases so they
    are never chosen.
    """
    if rounds_left <= 0 or cost <= 0:
        return -1e9
    weight = _COLOR_WEIGHT.get(chip.color, 1.0)
    marginal_ev = chip.value * weight * coin_rate * rounds_left
    return marginal_ev / cost


def greedy_value_buy(
    player: "Player",
    state: "GameState",
    coins: int,
    coin_rate: float = 0.25,
) -> list["Chip"]:
    """Greedy buying: repeatedly pick the highest-scoring affordable chip.

    Maintains a virtual stock snapshot so the same chip isn't over-bought
    within a single call. Stops when no affordable chip remains.
    """
    rounds_left = max(0, state.rounds_remaining())
    available = state.market.available_chips(state.round_number)

    # Virtual stock: track what we've committed to buy this turn
    virtual_stock: dict[tuple, int] = {
        (l.chip.color, l.chip.value): l.stock for l in available
    }
    cost_lookup: dict[tuple, int] = {
        (l.chip.color, l.chip.value): l.cost for l in available
    }

    purchases: list["Chip"] = []
    remaining = coins

    while True:
        best_score = -1e9
        best_chip: "Chip | None" = None
        best_cost = 0

        for listing in available:
            chip = listing.chip
            if chip.color == ChipColor.WHITE:
                continue
            key = (chip.color, chip.value)
            if virtual_stock.get(key, 0) <= 0:
                continue
            if listing.cost > remaining:
                continue
            score = _chip_score(chip, listing.cost, rounds_left, coin_rate)
            if score > best_score:
                best_score = score
                best_chip = chip
                best_cost = listing.cost

        if best_chip is None:
            break

        purchases.append(best_chip)
        remaining -= best_cost
        key = (best_chip.color, best_chip.value)
        virtual_stock[key] -= 1

    return purchases
