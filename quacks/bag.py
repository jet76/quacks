"""Player bag — the draw source for chips during the pulling phase."""

from __future__ import annotations
import random
from collections import Counter
from typing import Sequence

from quacks.chips import Chip, STARTING_BAG
from quacks.enums import ChipColor


class Bag:
    """A cloth bag holding ingredient chips that are drawn randomly.

    All draws are blind (uniform random without replacement until the bag
    is empty, then reshuffle is not needed — each round the bag refills
    with ALL chips from the cauldron).
    """

    def __init__(self, chips: Sequence[Chip] | None = None, rng: random.Random | None = None) -> None:
        self._chips: list[Chip] = list(chips if chips is not None else STARTING_BAG)
        self._rng: random.Random = rng or random.Random()

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw(self) -> Chip:
        """Draw one chip at random from the bag (removes it)."""
        if not self._chips:
            raise ValueError("Bag is empty — cannot draw")
        idx = self._rng.randrange(len(self._chips))
        self._chips[idx], self._chips[-1] = self._chips[-1], self._chips[idx]
        return self._chips.pop()

    def peek(self, n: int) -> list[Chip]:
        """Peek at up to n chips without removing them (for Blue chip effect).

        Returns copies of chip references; the chips stay in the bag.
        The actual drawn selection is handled by the caller.
        """
        n = min(n, len(self._chips))
        sample = self._rng.sample(self._chips, n)
        return sample

    def draw_specific(self, chip: Chip) -> Chip:
        """Remove a specific chip instance from the bag (for Blue effect commit)."""
        try:
            self._chips.remove(chip)
            return chip
        except ValueError as exc:
            raise ValueError(f"{chip} not found in bag") from exc

    # ------------------------------------------------------------------
    # Modifications
    # ------------------------------------------------------------------

    def add(self, chip: Chip) -> None:
        """Add a chip to the bag."""
        self._chips.append(chip)

    def add_many(self, chips: Sequence[Chip]) -> None:
        for chip in chips:
            self.add(chip)

    def return_chip(self, chip: Chip) -> None:
        """Return a chip to the bag (e.g. flask use, Yellow chip effect)."""
        self._chips.append(chip)

    def refill_from(self, chips: Sequence[Chip]) -> None:
        """Refill the bag with all cauldron chips at end of round."""
        self._chips = list(chips)

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    @property
    def size(self) -> int:
        return len(self._chips)

    @property
    def is_empty(self) -> bool:
        return len(self._chips) == 0

    def count(self, color: ChipColor | None = None) -> int:
        if color is None:
            return len(self._chips)
        return sum(1 for c in self._chips if c.color == color)

    def composition(self) -> Counter[Chip]:
        return Counter(self._chips)

    def all_chips(self) -> list[Chip]:
        """Return a snapshot of all chips currently in the bag."""
        return list(self._chips)

    # Probability helpers ------------------------------------------------

    def white_sum(self) -> int:
        """Sum of values of all white chips currently in the bag."""
        return sum(c.value for c in self._chips if c.color == ChipColor.WHITE)

    def explosion_probability(self, current_white_sum: int) -> float:
        """Probability that the NEXT drawn chip causes explosion.

        Explosion occurs when white sum in pot exceeds 7.
        Only counts directly from current white chips in bag.
        """
        if self.is_empty:
            return 0.0
        remaining_budget = 7 - current_white_sum
        dangerous = sum(
            1 for c in self._chips
            if c.color == ChipColor.WHITE and c.value > remaining_budget
        )
        return dangerous / len(self._chips)

    def prob_draw_white(self) -> float:
        """Probability next draw is any white chip."""
        if self.is_empty:
            return 0.0
        white_count = sum(1 for c in self._chips if c.color == ChipColor.WHITE)
        return white_count / len(self._chips)

    def expected_advance(self) -> float:
        """Expected number of cauldron spaces advanced by next draw."""
        if self.is_empty:
            return 0.0
        return sum(c.value for c in self._chips) / len(self._chips)

    def __repr__(self) -> str:
        counts = Counter(self._chips)
        parts = ", ".join(f"{chip}×{n}" for chip, n in sorted(counts.items(), key=lambda x: x[0].color.value))
        return f"Bag({self.size} chips: {parts})"
