"""Registry mapping (ChipColor, book_page) → effect handler.

Effect handlers are dataclasses with an apply() method. They are called
by the game engine at the appropriate phase.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from quacks.enums import ChipColor

if TYPE_CHECKING:
    from quacks.player import Player
    from quacks.game import GameState


class IngredientEffect(ABC):
    """Base class for ingredient effects."""

    @property
    @abstractmethod
    def phase(self) -> str:
        """When this effect fires: 'on_draw', 'evaluation_b', 'buying'."""

    @abstractmethod
    def apply(self, player: "Player", state: "GameState", **kwargs: Any) -> dict[str, Any]:
        """Apply the effect. Returns a dict of result data."""


# ---------------------------------------------------------------------------
# WHITE — Cherry Bombs  (explosion logic handled in game engine directly)
# ---------------------------------------------------------------------------

class WhiteEffect(IngredientEffect):
    """White chips are handled inline by the game engine (explosion check).

    This stub exists for completeness and statistics hooks.
    """
    @property
    def phase(self) -> str:
        return "on_draw"

    def apply(self, player, state, **kwargs):
        chip = kwargs.get("chip")
        return {"white_added": chip.value if chip else 0}


# ---------------------------------------------------------------------------
# ORANGE — Pumpkin  (no special effect; enables Red bonus)
# ---------------------------------------------------------------------------

class OrangeEffect(IngredientEffect):
    """Orange chips have no ability of their own; they boost Red chips."""
    @property
    def phase(self) -> str:
        return "on_draw"

    def apply(self, player, state, **kwargs):
        return {}  # Nothing to do; Red checks orange count itself


# ---------------------------------------------------------------------------
# GREEN — Garden Spider
# ---------------------------------------------------------------------------

class GreenEffectPage1(IngredientEffect):
    """If sum of white chips in pot = exactly 7, advance last chip by green sum."""
    @property
    def phase(self) -> str:
        return "evaluation_b"

    def apply(self, player, state, **kwargs):
        cauldron = player.cauldron
        if cauldron.white_sum == 7:
            green_sum = cauldron.sum_color(ChipColor.GREEN)
            if green_sum > 0 and cauldron.chips_in_pot:
                old_pos = cauldron.position
                from quacks.scoring import MAX_CAULDRON_POSITION
                new_pos = min(old_pos + green_sum, MAX_CAULDRON_POSITION)
                # Advance the last placed chip's recorded position
                if cauldron._placed:
                    last = cauldron._placed[-1]
                    from quacks.cauldron import PlacedChip
                    cauldron._placed[-1] = PlacedChip(last.chip, new_pos, last.draw_order)
                return {"green_advance": new_pos - old_pos, "new_pos": new_pos}
        return {"green_advance": 0}


class GreenEffectPage2(IngredientEffect):
    """Gain 1 ruby for each green chip that is last or second-to-last drawn."""
    @property
    def phase(self) -> str:
        return "on_draw"

    def apply(self, player, state, **kwargs):
        chip = kwargs.get("chip")
        cauldron = player.cauldron
        last = cauldron.last_chip()
        second_last = cauldron.second_to_last_chip()
        rubies = 0
        if last and last.chip.color == ChipColor.GREEN:
            rubies += 1
        if second_last and second_last.chip.color == ChipColor.GREEN:
            rubies += 1
        if rubies:
            player.rubies += rubies
        return {"rubies_earned": rubies}


class GreenEffectPage3(IngredientEffect):
    """[VERIFY page 3 effect]"""
    @property
    def phase(self) -> str:
        return "evaluation_b"

    def apply(self, player, state, **kwargs):
        return {}  # TODO: implement when verified


class GreenEffectPage4(IngredientEffect):
    """[VERIFY page 4 effect]"""
    @property
    def phase(self) -> str:
        return "evaluation_b"

    def apply(self, player, state, **kwargs):
        return {}  # TODO: implement when verified


# ---------------------------------------------------------------------------
# BLUE — Crow Skull
# ---------------------------------------------------------------------------

class BlueEffectPage1(IngredientEffect):
    """When drawn: peek at (chip.value) chips from bag; place one or return all."""
    @property
    def phase(self) -> str:
        return "on_draw"

    def apply(self, player, state, **kwargs):
        chip = kwargs.get("chip")
        if chip is None:
            return {}
        peeked = player.bag.peek(chip.value)
        # Strategy decides which to place (or None = return all)
        chosen = player.strategy.choose_blue_chip(player, state, peeked)
        if chosen is not None:
            player.bag.draw_specific(chosen)
            pos, rubies = player.cauldron.place(chosen)
            player.rubies += len(rubies)
            return {"blue_placed": str(chosen), "position": pos}
        return {"blue_placed": None}


class BlueEffectPage2(IngredientEffect):
    """Gain 1 ruby when blue chip lands on a ruby space."""
    @property
    def phase(self) -> str:
        return "on_draw"

    def apply(self, player, state, **kwargs):
        # Ruby already collected in cauldron.place() via _collect_rubies
        return {}


class BlueEffectPage3(IngredientEffect):
    """[VERIFY page 3 effect]"""
    @property
    def phase(self) -> str:
        return "on_draw"

    def apply(self, player, state, **kwargs):
        return {}


class BlueEffectPage4(IngredientEffect):
    """[VERIFY page 4 effect]"""
    @property
    def phase(self) -> str:
        return "on_draw"

    def apply(self, player, state, **kwargs):
        return {}


# ---------------------------------------------------------------------------
# RED — Toadstool
# ---------------------------------------------------------------------------

class RedEffectPage1(IngredientEffect):
    """When drawn: advance extra spaces based on orange chips in pot."""
    @property
    def phase(self) -> str:
        return "on_draw"

    def apply(self, player, state, **kwargs):
        orange_count = player.cauldron.count_color(ChipColor.ORANGE)
        if orange_count == 0:
            extra = 0
        elif orange_count <= 2:
            extra = 1
        else:
            extra = 2
        if extra > 0:
            cauldron = player.cauldron
            if cauldron._placed:
                last = cauldron._placed[-1]
                from quacks.scoring import MAX_CAULDRON_POSITION
                from quacks.cauldron import PlacedChip
                new_pos = min(last.position + extra, MAX_CAULDRON_POSITION)
                cauldron._placed[-1] = PlacedChip(last.chip, new_pos, last.draw_order)
                return {"red_extra": extra, "new_pos": new_pos}
        return {"red_extra": 0}


class RedEffectPage2(IngredientEffect):
    """If red in pot, all White 1-chips in pot each move +1 space. [VERIFY]"""
    @property
    def phase(self) -> str:
        return "on_draw"

    def apply(self, player, state, **kwargs):
        cauldron = player.cauldron
        red_count = cauldron.count_color(ChipColor.RED)
        if red_count >= 1:
            from quacks.scoring import MAX_CAULDRON_POSITION
            from quacks.cauldron import PlacedChip
            moved = 0
            for i, pc in enumerate(cauldron._placed):
                if pc.chip.color == ChipColor.WHITE and pc.chip.value == 1:
                    new_pos = min(pc.position + 1, MAX_CAULDRON_POSITION)
                    cauldron._placed[i] = PlacedChip(pc.chip, new_pos, pc.draw_order)
                    moved += 1
            return {"whites_moved": moved}
        return {"whites_moved": 0}


class RedEffectPage3(IngredientEffect):
    """[VERIFY page 3 effect]"""
    @property
    def phase(self) -> str:
        return "on_draw"

    def apply(self, player, state, **kwargs):
        return {}


class RedEffectPage4(IngredientEffect):
    """[VERIFY page 4 effect]"""
    @property
    def phase(self) -> str:
        return "on_draw"

    def apply(self, player, state, **kwargs):
        return {}


# ---------------------------------------------------------------------------
# YELLOW — Mandrake Root
# ---------------------------------------------------------------------------

class YellowEffectPage1(IngredientEffect):
    """If drawn after a white chip, may return that white chip to bag."""
    @property
    def phase(self) -> str:
        return "on_draw"

    def apply(self, player, state, **kwargs):
        cauldron = player.cauldron
        # The yellow was just placed; check second-to-last chip
        second_last = cauldron.second_to_last_chip()
        if second_last and second_last.chip.color == ChipColor.WHITE:
            # Strategy decides whether to exercise the power
            if player.strategy.use_yellow_power(player, state, second_last.chip):
                # Remove the white chip from cauldron and return to bag
                white_chip = second_last.chip
                cauldron._placed.remove(second_last)
                cauldron._white_sum -= white_chip.value
                if cauldron._white_sum <= 7:
                    cauldron._exploded = False
                player.bag.return_chip(white_chip)
                return {"yellow_returned_white": str(white_chip)}
        return {"yellow_returned_white": None}


class YellowEffectPage2(IngredientEffect):
    """[VERIFY page 2 effect]"""
    @property
    def phase(self) -> str:
        return "on_draw"

    def apply(self, player, state, **kwargs):
        return {}


class YellowEffectPage3(IngredientEffect):
    """[VERIFY page 3 effect]"""
    @property
    def phase(self) -> str:
        return "on_draw"

    def apply(self, player, state, **kwargs):
        return {}


class YellowEffectPage4(IngredientEffect):
    """[VERIFY page 4 effect]"""
    @property
    def phase(self) -> str:
        return "on_draw"

    def apply(self, player, state, **kwargs):
        return {}


# ---------------------------------------------------------------------------
# PURPLE — Raven's Feather
# ---------------------------------------------------------------------------

class PurpleEffect(IngredientEffect):
    """During buying phase: upgrade chips based on purple count in pot.

    1 purple: may trade 1→2 chip (same color)
    2 purple: may trade 2→4 chip (same color)
    3+ purple: may trade 1→4 chip (same color)
    """
    @property
    def phase(self) -> str:
        return "buying"

    def apply(self, player, state, **kwargs):
        purple_count = player.cauldron.count_color(ChipColor.PURPLE)
        if purple_count == 0:
            return {"purple_upgrade": None}
        market = state.market
        options = market.purple_upgrade(purple_count, player.bag.all_chips())
        if not options:
            return {"purple_upgrade": None}
        chosen = player.strategy.choose_purple_upgrade(player, state, options)
        if chosen:
            from_chip, to_chip = chosen
            player.bag.draw_specific(from_chip)
            market.restock(from_chip)
            market._stock[(to_chip.color, to_chip.value)] -= 1
            player.bag.add(to_chip)
            return {"purple_upgrade": f"{from_chip} → {to_chip}"}
        return {"purple_upgrade": None}


# ---------------------------------------------------------------------------
# BLACK — Crow's Eye
# ---------------------------------------------------------------------------

class BlackEffectPage1(IngredientEffect):
    """Evaluation B: count black chips; peek at that many chips from bag.
    May return any of them (keeps them drawn for next round's awareness).
    [VERIFY exact mechanic]
    """
    @property
    def phase(self) -> str:
        return "evaluation_b"

    def apply(self, player, state, **kwargs):
        black_count = player.cauldron.count_color(ChipColor.BLACK)
        if black_count == 0:
            return {}
        peeked = player.bag.peek(black_count)
        # Strategy may choose chips to 'lock in' knowledge of; no actual move
        return {"black_peeked": [str(c) for c in peeked]}


class BlackEffectPage2(IngredientEffect):
    """[VERIFY page 2 effect]"""
    @property
    def phase(self) -> str:
        return "evaluation_b"

    def apply(self, player, state, **kwargs):
        return {}


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

EFFECT_REGISTRY: dict[tuple[ChipColor, int], IngredientEffect] = {
    (ChipColor.WHITE,  1): WhiteEffect(),
    (ChipColor.ORANGE, 1): OrangeEffect(),
    (ChipColor.GREEN,  1): GreenEffectPage1(),
    (ChipColor.GREEN,  2): GreenEffectPage2(),
    (ChipColor.GREEN,  3): GreenEffectPage3(),
    (ChipColor.GREEN,  4): GreenEffectPage4(),
    (ChipColor.BLUE,   1): BlueEffectPage1(),
    (ChipColor.BLUE,   2): BlueEffectPage2(),
    (ChipColor.BLUE,   3): BlueEffectPage3(),
    (ChipColor.BLUE,   4): BlueEffectPage4(),
    (ChipColor.RED,    1): RedEffectPage1(),
    (ChipColor.RED,    2): RedEffectPage2(),
    (ChipColor.RED,    3): RedEffectPage3(),
    (ChipColor.RED,    4): RedEffectPage4(),
    (ChipColor.YELLOW, 1): YellowEffectPage1(),
    (ChipColor.YELLOW, 2): YellowEffectPage2(),
    (ChipColor.YELLOW, 3): YellowEffectPage3(),
    (ChipColor.YELLOW, 4): YellowEffectPage4(),
    (ChipColor.PURPLE, 1): PurpleEffect(),
    (ChipColor.PURPLE, 2): PurpleEffect(),
    (ChipColor.PURPLE, 3): PurpleEffect(),
    (ChipColor.PURPLE, 4): PurpleEffect(),
    (ChipColor.BLACK,  1): BlackEffectPage1(),
    (ChipColor.BLACK,  2): BlackEffectPage2(),
}


def get_effect(color: ChipColor, book_page: int) -> IngredientEffect | None:
    """Look up the effect for a given (color, book_page) pair."""
    return EFFECT_REGISTRY.get((color, book_page))
