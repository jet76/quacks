"""Cauldron board — the spiral track where chips are placed during pulling."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

from quacks.chips import Chip
from quacks.enums import ChipColor
from quacks.scoring import cauldron_reward, MAX_CAULDRON_POSITION, SpaceReward


@dataclass
class PlacedChip:
    """A chip placed at a specific position in the cauldron spiral."""
    chip: Chip
    position: int       # absolute cauldron space (0–33)
    draw_order: int     # 1-indexed order it was drawn this round


class Cauldron:
    """The cauldron spiral for one player.

    Tracks:
    - The droplet position (start of spiral this round)
    - Rat stone advance (catch-up bonus applied before pulling)
    - All placed chips and their positions
    - White chip sum (explosion counter)
    - Whether the pot has exploded
    - Rubies earned during pulling

    At end of round, all placed chips are returned to the bag and the
    cauldron is reset (keeping updated droplet and rat stone positions).
    """

    def __init__(self) -> None:
        self.droplet_position: int = 0      # advances via rubies (persistent)
        self.rat_stone_advance: int = 0     # set each round by catch-up mechanic
        self._placed: list[PlacedChip] = []
        self._white_sum: int = 0
        self._exploded: bool = False
        self._rubies_earned_this_round: int = 0
        self._draw_counter: int = 0

    # ------------------------------------------------------------------
    # Round lifecycle
    # ------------------------------------------------------------------

    def start_round(self, rat_stone_advance: int = 0) -> None:
        """Prepare the cauldron for a new pulling phase."""
        self._placed = []
        self._white_sum = 0
        self._exploded = False
        self._rubies_earned_this_round = 0
        self._draw_counter = 0
        self.rat_stone_advance = rat_stone_advance

    def reset_end_of_round(self) -> list[Chip]:
        """Return all chips from the cauldron (to go back in the bag).

        Rat stones and droplet are preserved across rounds.
        """
        chips = [pc.chip for pc in self._placed]
        self._placed = []
        self._white_sum = 0
        self._exploded = False
        self._rubies_earned_this_round = 0
        self._draw_counter = 0
        return chips

    # ------------------------------------------------------------------
    # Drawing & placing
    # ------------------------------------------------------------------

    @property
    def front_position(self) -> int:
        """Current front-of-pot position (where next chip will START from)."""
        if self._placed:
            return self._placed[-1].position
        # Before any chip is placed, the front is the droplet + rat stone
        return self.droplet_position + self.rat_stone_advance

    def can_place(self, chip: Chip) -> bool:
        """True if placing this chip would not push beyond MAX + it is legal."""
        # Even if it would exceed max, the chip is capped — always can place
        return True

    def place(self, chip: Chip) -> tuple[int, list[int]]:
        """Place a chip in the cauldron. Returns (new_position, ruby_positions_hit).

        Advances front_position by chip.value, capped at MAX_CAULDRON_POSITION.
        Updates white_sum and explosion state.
        """
        new_pos = min(self.front_position + chip.value, MAX_CAULDRON_POSITION)

        # Collect rubies from spaces traversed (inclusive of landing space)
        old_pos = self.front_position
        ruby_spaces = self._collect_rubies(old_pos, new_pos)

        self._draw_counter += 1
        placed = PlacedChip(chip, new_pos, self._draw_counter)
        self._placed.append(placed)

        if chip.color == ChipColor.WHITE:
            self._white_sum += chip.value
            if self._white_sum > 7:
                self._exploded = True

        self._rubies_earned_this_round += len(ruby_spaces)
        return new_pos, ruby_spaces

    def _collect_rubies(self, from_pos: int, to_pos: int) -> list[int]:
        """Return list of ruby spaces collected when landing on to_pos.

        Chips advance by their value and land on a single space. A ruby is
        collected only if the chip actually moved AND landed on a ruby space.
        Chips already at max position (no movement) do not re-trigger rubies.
        """
        from quacks.scoring import _TABLE
        if to_pos > from_pos and to_pos in _TABLE and _TABLE[to_pos].has_ruby:
            return [to_pos]
        return []

    # ------------------------------------------------------------------
    # State inspection
    # ------------------------------------------------------------------

    @property
    def exploded(self) -> bool:
        return self._exploded

    @property
    def white_sum(self) -> int:
        return self._white_sum

    @property
    def position(self) -> int:
        """Current cauldron position (last chip placed)."""
        if not self._placed:
            return self.droplet_position + self.rat_stone_advance
        return self._placed[-1].position

    @property
    def rubies_earned(self) -> int:
        return self._rubies_earned_this_round

    @property
    def chips_in_pot(self) -> list[Chip]:
        return [pc.chip for pc in self._placed]

    def count_color(self, color: ChipColor) -> int:
        return sum(1 for pc in self._placed if pc.chip.color == color)

    def sum_color(self, color: ChipColor) -> int:
        return sum(pc.chip.value for pc in self._placed if pc.chip.color == color)

    def last_chip(self) -> Optional[PlacedChip]:
        return self._placed[-1] if self._placed else None

    def second_to_last_chip(self) -> Optional[PlacedChip]:
        return self._placed[-2] if len(self._placed) >= 2 else None

    @property
    def reward(self) -> SpaceReward:
        """VP and coins available from current cauldron position."""
        return cauldron_reward(self.position)

    def white_budget_remaining(self) -> int:
        """How many more white value points can be drawn before explosion (>7)."""
        return max(0, 7 - self._white_sum)

    def explosion_budget_remaining(self) -> int:
        """Alias for white_budget_remaining."""
        return self.white_budget_remaining()

    def advance_droplet(self, spaces: int = 1) -> None:
        """Move the droplet forward (persists to future rounds). Costs 2 rubies each."""
        self.droplet_position = min(
            self.droplet_position + spaces, MAX_CAULDRON_POSITION
        )

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def snapshot(self) -> dict:
        """Return a dict snapshot of current cauldron state for logging/stats."""
        return {
            "position": self.position,
            "white_sum": self._white_sum,
            "exploded": self._exploded,
            "droplet_pos": self.droplet_position,
            "rat_stone_advance": self.rat_stone_advance,
            "chips_in_pot": [str(c) for c in self.chips_in_pot],
            "rubies_earned": self._rubies_earned_this_round,
            "vp": self.reward.vp,
            "coins": self.reward.coins,
        }

    def __repr__(self) -> str:
        status = "💥 EXPLODED" if self._exploded else f"pos={self.position}"
        return (
            f"Cauldron({status}, white_sum={self._white_sum}/7, "
            f"droplet={self.droplet_position}, chips={len(self._placed)})"
        )
