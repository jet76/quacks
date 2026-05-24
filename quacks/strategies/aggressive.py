"""Aggressive strategy: keep drawing until bag is nearly empty or explosion."""

from __future__ import annotations
from typing import TYPE_CHECKING

from quacks.enums import ChipColor, ExplosionChoice
from quacks.strategies.base import PlayerStrategy

if TYPE_CHECKING:
    from quacks.chips import Chip
    from quacks.game import GameState
    from quacks.player import Player


class AggressiveStrategy(PlayerStrategy):
    """Always draw until explosion or bag empty. Prefers coins on explosion.

    Maximises cauldron position at the cost of frequent explosions.
    In late rounds, explosions that trade VP for coins can be strategic.
    """

    @property
    def name(self) -> str:
        return "Aggressive"

    def should_continue_pulling(self, player: "Player", state: "GameState") -> bool:
        return not player.cauldron.exploded and not player.bag.is_empty

    def choose_explosion_outcome(self, player, state) -> ExplosionChoice:
        # Always take coins — use the explosion to fund better purchases
        cauldron_coins = player.cauldron.reward.coins
        cauldron_vp = player.cauldron.reward.vp
        # Take VP only if we're way behind and coins won't help
        if player.scoring_position < (state.leader_score - 5) and state.round_number >= 7:
            return ExplosionChoice.VP
        return ExplosionChoice.COINS

    def choose_purchases(
        self, player: "Player", state: "GameState", coins: int
    ) -> list["Chip"]:
        """Buy the most expensive chips available — go for 4-chips."""
        from quacks.chips import Chip
        purchases: list[Chip] = []
        remaining = coins
        available = state.market.available_chips(state.round_number)

        while remaining > 0:
            # Prefer high-value chips that grow the bag faster
            affordable = sorted(
                [l for l in available if l.cost <= remaining and l.stock > 0],
                key=lambda l: (-l.chip.value, -l.cost),
            )
            if not affordable:
                break
            best = affordable[0]
            purchases.append(best.chip)
            remaining -= best.cost
            best.stock -= 1
            if best.stock == 0:
                available.remove(best)

        return purchases
