"""Registry mapping (ChipColor, book_page) → effect handler.

Effect handlers are dataclasses with an apply() method. They are called
by the game engine at the appropriate phase.

[VERIFY] markers flag rules reconstructed from community sources rather than
confirmed against the physical game rulebook.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from quacks.enums import ChipColor
from quacks.scoring import MAX_CAULDRON_POSITION
from quacks.cauldron import PlacedChip

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
    @property
    def phase(self) -> str:
        return "on_draw"

    def apply(self, player, state, **kwargs):
        chip = kwargs.get("chip")
        return {"white_added": chip.value if chip else 0}


# ---------------------------------------------------------------------------
# ORANGE — Pumpkin  (no special effect of its own; enables Red bonus)
# ---------------------------------------------------------------------------

class OrangeEffect(IngredientEffect):
    @property
    def phase(self) -> str:
        return "on_draw"

    def apply(self, player, state, **kwargs):
        return {}


# ---------------------------------------------------------------------------
# GREEN — Garden Spider
# ---------------------------------------------------------------------------

class GreenEffectPage1(IngredientEffect):
    """Evaluation B: if white_sum == 7, advance scoring marker by green chip COUNT."""

    @property
    def phase(self) -> str:
        return "evaluation_b"

    def apply(self, player, state, **kwargs):
        cauldron = player.cauldron
        if cauldron.white_sum == 7:
            green_count = cauldron.count_color(ChipColor.GREEN)
            if green_count > 0 and cauldron._placed:
                old_pos = cauldron.position
                new_pos = min(old_pos + green_count, MAX_CAULDRON_POSITION)
                last = cauldron._placed[-1]
                cauldron._placed[-1] = PlacedChip(last.chip, new_pos, last.draw_order)
                return {"green_advance": new_pos - old_pos}
        return {"green_advance": 0}


class GreenEffectPage2(IngredientEffect):
    """Evaluation B: gain 1 ruby per green chip in pot."""

    @property
    def phase(self) -> str:
        return "evaluation_b"

    def apply(self, player, state, **kwargs):
        green_count = player.cauldron.count_color(ChipColor.GREEN)
        if green_count:
            player.rubies += green_count
        return {"rubies_earned": green_count, "green_advance": 0}


class GreenEffectPage3(IngredientEffect):
    """Evaluation B: advance scoring marker by green chip count (no white condition). [VERIFY]"""

    @property
    def phase(self) -> str:
        return "evaluation_b"

    def apply(self, player, state, **kwargs):
        cauldron = player.cauldron
        green_count = cauldron.count_color(ChipColor.GREEN)
        if green_count > 0 and cauldron._placed:
            old_pos = cauldron.position
            new_pos = min(old_pos + green_count, MAX_CAULDRON_POSITION)
            last = cauldron._placed[-1]
            cauldron._placed[-1] = PlacedChip(last.chip, new_pos, last.draw_order)
            return {"green_advance": new_pos - old_pos}
        return {"green_advance": 0}


class GreenEffectPage4(IngredientEffect):
    """Evaluation B: gain 2 rubies per green chip in pot. [VERIFY]"""

    @property
    def phase(self) -> str:
        return "evaluation_b"

    def apply(self, player, state, **kwargs):
        green_count = player.cauldron.count_color(ChipColor.GREEN)
        rubies = green_count * 2
        if rubies:
            player.rubies += rubies
        return {"rubies_earned": rubies, "green_advance": 0}


# ---------------------------------------------------------------------------
# BLUE — Crow Skull
# ---------------------------------------------------------------------------

class BlueEffectPage1(IngredientEffect):
    """On draw: peek at chip.value chips from bag; place one or return all."""

    @property
    def phase(self) -> str:
        return "on_draw"

    def apply(self, player, state, **kwargs):
        chip = kwargs.get("chip")
        if chip is None:
            return {}
        peeked = player.bag.peek(chip.value)
        chosen = player.strategy.choose_blue_chip(player, state, peeked)
        if chosen is not None:
            player.bag.draw_specific(chosen)
            pos, rubies = player.cauldron.place(chosen)
            player.rubies += len(rubies)
            if player._current_record:
                player._current_record.rubies_earned += len(rubies)
            return {"blue_placed": str(chosen), "position": pos}
        return {"blue_placed": None}


class BlueEffectPage2(IngredientEffect):
    """On draw: peek at (chip.value + 1) chips from bag; place one or return all. [VERIFY]"""

    @property
    def phase(self) -> str:
        return "on_draw"

    def apply(self, player, state, **kwargs):
        chip = kwargs.get("chip")
        if chip is None:
            return {}
        peeked = player.bag.peek(chip.value + 1)
        chosen = player.strategy.choose_blue_chip(player, state, peeked)
        if chosen is not None:
            player.bag.draw_specific(chosen)
            pos, rubies = player.cauldron.place(chosen)
            player.rubies += len(rubies)
            if player._current_record:
                player._current_record.rubies_earned += len(rubies)
            return {"blue_placed": str(chosen), "position": pos}
        return {"blue_placed": None}


class BlueEffectPage3(IngredientEffect):
    """On draw: peek at chip.value chips; must place one if any non-white available. [VERIFY]"""

    @property
    def phase(self) -> str:
        return "on_draw"

    def apply(self, player, state, **kwargs):
        chip = kwargs.get("chip")
        if chip is None:
            return {}
        peeked = player.bag.peek(chip.value)
        if not peeked:
            return {"blue_placed": None}
        chosen = player.strategy.choose_blue_chip(player, state, peeked)
        if chosen is None:
            # Page 3: forced placement of best non-white chip if one exists
            non_white = [c for c in peeked if c.color != ChipColor.WHITE]
            if non_white:
                chosen = max(non_white, key=lambda c: c.value)
        if chosen is not None:
            player.bag.draw_specific(chosen)
            pos, rubies = player.cauldron.place(chosen)
            player.rubies += len(rubies)
            if player._current_record:
                player._current_record.rubies_earned += len(rubies)
            return {"blue_placed": str(chosen), "position": pos}
        return {"blue_placed": None}


class BlueEffectPage4(IngredientEffect):
    """On draw: peek at (chip.value + 2) chips from bag; place one or return all. [VERIFY]"""

    @property
    def phase(self) -> str:
        return "on_draw"

    def apply(self, player, state, **kwargs):
        chip = kwargs.get("chip")
        if chip is None:
            return {}
        peeked = player.bag.peek(chip.value + 2)
        chosen = player.strategy.choose_blue_chip(player, state, peeked)
        if chosen is not None:
            player.bag.draw_specific(chosen)
            pos, rubies = player.cauldron.place(chosen)
            player.rubies += len(rubies)
            if player._current_record:
                player._current_record.rubies_earned += len(rubies)
            return {"blue_placed": str(chosen), "position": pos}
        return {"blue_placed": None}


# ---------------------------------------------------------------------------
# RED — Toadstool
# ---------------------------------------------------------------------------

class RedEffectPage1(IngredientEffect):
    """On draw: advance extra spaces equal to orange chip count in pot."""

    @property
    def phase(self) -> str:
        return "on_draw"

    def apply(self, player, state, **kwargs):
        extra = player.cauldron.count_color(ChipColor.ORANGE)
        if extra > 0 and player.cauldron._placed:
            last = player.cauldron._placed[-1]
            new_pos = min(last.position + extra, MAX_CAULDRON_POSITION)
            player.cauldron._placed[-1] = PlacedChip(last.chip, new_pos, last.draw_order)
            return {"red_extra": extra, "new_pos": new_pos}
        return {"red_extra": 0}


class RedEffectPage2(IngredientEffect):
    """On draw: each White-1 chip already in pot moves +1 space. [VERIFY]"""

    @property
    def phase(self) -> str:
        return "on_draw"

    def apply(self, player, state, **kwargs):
        cauldron = player.cauldron
        red_count = cauldron.count_color(ChipColor.RED)
        if red_count >= 1:
            moved = 0
            for i, pc in enumerate(cauldron._placed):
                if pc.chip.color == ChipColor.WHITE and pc.chip.value == 1:
                    new_pos = min(pc.position + 1, MAX_CAULDRON_POSITION)
                    cauldron._placed[i] = PlacedChip(pc.chip, new_pos, pc.draw_order)
                    moved += 1
            return {"red_extra": moved, "whites_moved": moved}
        return {"red_extra": 0, "whites_moved": 0}


class RedEffectPage3(IngredientEffect):
    """On draw: advance extra spaces equal to red chips already in pot (before this one). [VERIFY]"""

    @property
    def phase(self) -> str:
        return "on_draw"

    def apply(self, player, state, **kwargs):
        cauldron = player.cauldron
        # Red chips in pot includes the current one; subtract 1 for "already in pot"
        extra = max(0, cauldron.count_color(ChipColor.RED) - 1)
        if extra > 0 and cauldron._placed:
            last = cauldron._placed[-1]
            new_pos = min(last.position + extra, MAX_CAULDRON_POSITION)
            cauldron._placed[-1] = PlacedChip(last.chip, new_pos, last.draw_order)
            return {"red_extra": extra, "new_pos": new_pos}
        return {"red_extra": 0}


class RedEffectPage4(IngredientEffect):
    """On draw: advance extra by orange count + red chips already in pot. [VERIFY]"""

    @property
    def phase(self) -> str:
        return "on_draw"

    def apply(self, player, state, **kwargs):
        cauldron = player.cauldron
        orange_count = cauldron.count_color(ChipColor.ORANGE)
        red_already = max(0, cauldron.count_color(ChipColor.RED) - 1)
        extra = orange_count + red_already
        if extra > 0 and cauldron._placed:
            last = cauldron._placed[-1]
            new_pos = min(last.position + extra, MAX_CAULDRON_POSITION)
            cauldron._placed[-1] = PlacedChip(last.chip, new_pos, last.draw_order)
            return {"red_extra": extra, "new_pos": new_pos}
        return {"red_extra": 0}


# ---------------------------------------------------------------------------
# YELLOW — Mandrake Root
# ---------------------------------------------------------------------------

def _remove_chip_from_cauldron(cauldron, chip) -> bool:
    """Remove the first matching chip from cauldron._placed. Returns True if removed."""
    for i, pc in enumerate(cauldron._placed):
        if pc.chip == chip:
            cauldron._placed.pop(i)
            return True
    return False


class YellowEffectPage1(IngredientEffect):
    """On draw: if drawn after a white chip, strategy may return that white to bag."""

    @property
    def phase(self) -> str:
        return "on_draw"

    def apply(self, player, state, **kwargs):
        cauldron = player.cauldron
        second_last = cauldron.second_to_last_chip()
        if second_last and second_last.chip.color == ChipColor.WHITE:
            if player.strategy.use_yellow_power(player, state, second_last.chip):
                white_chip = second_last.chip
                cauldron._placed.remove(second_last)
                cauldron._white_sum -= white_chip.value
                if cauldron._white_sum <= 7:
                    cauldron._exploded = False
                player.bag.return_chip(white_chip)
                return {"yellow_returned_white": str(white_chip)}
        return {"yellow_returned_white": None}


class YellowEffectPage2(IngredientEffect):
    """On draw: strategy may return any one white chip from the pot to the bag. [VERIFY]"""

    @property
    def phase(self) -> str:
        return "on_draw"

    def apply(self, player, state, **kwargs):
        cauldron = player.cauldron
        whites = [pc.chip for pc in cauldron._placed if pc.chip.color == ChipColor.WHITE]
        if not whites:
            return {"yellow_returned_white": None}
        chosen = player.strategy.choose_white_to_return(player, state, whites)
        if chosen is None:
            return {"yellow_returned_white": None}
        if _remove_chip_from_cauldron(cauldron, chosen):
            cauldron._white_sum -= chosen.value
            if cauldron._white_sum <= 7:
                cauldron._exploded = False
            player.bag.return_chip(chosen)
            return {"yellow_returned_white": str(chosen)}
        return {"yellow_returned_white": None}


class YellowEffectPage3(IngredientEffect):
    """On draw: strategy may return any one chip (any color) from the pot to the bag. [VERIFY]"""

    @property
    def phase(self) -> str:
        return "on_draw"

    def apply(self, player, state, **kwargs):
        cauldron = player.cauldron
        chips_in_pot = [pc.chip for pc in cauldron._placed]
        if not chips_in_pot:
            return {"yellow_returned_chip": None}
        chosen = player.strategy.choose_chip_to_return(player, state, chips_in_pot)
        if chosen is None:
            return {"yellow_returned_chip": None}
        if _remove_chip_from_cauldron(cauldron, chosen):
            if chosen.color == ChipColor.WHITE:
                cauldron._white_sum -= chosen.value
                if cauldron._white_sum <= 7:
                    cauldron._exploded = False
            player.bag.return_chip(chosen)
            return {"yellow_returned_chip": str(chosen)}
        return {"yellow_returned_chip": None}


class YellowEffectPage4(IngredientEffect):
    """On draw: strategy may return up to 2 chips (any color) from pot to bag. [VERIFY]"""

    @property
    def phase(self) -> str:
        return "on_draw"

    def apply(self, player, state, **kwargs):
        cauldron = player.cauldron
        chips_in_pot = [pc.chip for pc in cauldron._placed]
        if not chips_in_pot:
            return {"yellow_returned_chips": []}
        chosen_list = player.strategy.choose_chips_to_return(
            player, state, chips_in_pot, max_n=2
        )
        returned = []
        for chosen in chosen_list:
            if _remove_chip_from_cauldron(cauldron, chosen):
                if chosen.color == ChipColor.WHITE:
                    cauldron._white_sum -= chosen.value
                    if cauldron._white_sum <= 7:
                        cauldron._exploded = False
                player.bag.return_chip(chosen)
                returned.append(chosen)
        return {"yellow_returned_chips": [str(c) for c in returned]}


# ---------------------------------------------------------------------------
# PURPLE — Raven's Feather  (all pages use the same tiered upgrade logic)
# ---------------------------------------------------------------------------

class PurpleEffect(IngredientEffect):
    """During buying phase: upgrade chips based on purple count in pot.

    1 purple: trade 1→2 chip (same color)
    2 purple: trade 2→4 chip (same color)
    3+ purple: trade 1→4 chip (same color)
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
    """Evaluation B: peek at black_count chips from bag top (information only)."""

    @property
    def phase(self) -> str:
        return "evaluation_b"

    def apply(self, player, state, **kwargs):
        black_count = player.cauldron.count_color(ChipColor.BLACK)
        if black_count == 0:
            return {}
        peeked = player.bag.peek(black_count)
        return {"black_peeked": [str(c) for c in peeked]}


class BlackEffectPage2(IngredientEffect):
    """Evaluation B: peek at (black_count + 1) chips from bag top. [VERIFY]"""

    @property
    def phase(self) -> str:
        return "evaluation_b"

    def apply(self, player, state, **kwargs):
        black_count = player.cauldron.count_color(ChipColor.BLACK)
        if black_count == 0:
            return {}
        peeked = player.bag.peek(black_count + 1)
        return {"black_peeked": [str(c) for c in peeked]}


class BlackEffectPage3(IngredientEffect):
    """Evaluation B: look at all chips in the bag (full information). [VERIFY]"""

    @property
    def phase(self) -> str:
        return "evaluation_b"

    def apply(self, player, state, **kwargs):
        black_count = player.cauldron.count_color(ChipColor.BLACK)
        if black_count == 0:
            return {}
        all_chips = player.bag.all_chips()
        return {"black_peeked": [str(c) for c in all_chips]}


class BlackEffectPage4(IngredientEffect):
    """Evaluation B: peek at (black_count + 1) chips; strategy may permanently remove one. [VERIFY]"""

    @property
    def phase(self) -> str:
        return "evaluation_b"

    def apply(self, player, state, **kwargs):
        black_count = player.cauldron.count_color(ChipColor.BLACK)
        if black_count == 0:
            return {}
        peeked = player.bag.peek(black_count + 1)
        chosen = player.strategy.choose_chip_to_remove(player, state, peeked)
        if chosen is not None:
            player.bag.draw_specific(chosen)  # removed from bag permanently this game
            return {
                "black_peeked": [str(c) for c in peeked],
                "black_removed": str(chosen),
            }
        return {"black_peeked": [str(c) for c in peeked]}


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
    (ChipColor.BLACK,  3): BlackEffectPage3(),
    (ChipColor.BLACK,  4): BlackEffectPage4(),
}


def get_effect(color: ChipColor, book_page: int) -> IngredientEffect | None:
    """Look up the effect for a given (color, book_page) pair."""
    return EFFECT_REGISTRY.get((color, book_page))
