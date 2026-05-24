"""Player state and round-by-round data for the Quacks simulation."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from quacks.bag import Bag
from quacks.cauldron import Cauldron
from quacks.chips import Chip, STARTING_BAG
from quacks.enums import ChipColor, ExplosionChoice

if TYPE_CHECKING:
    from quacks.game import GameState
    from quacks.strategies.base import PlayerStrategy


@dataclass
class RoundRecord:
    """Everything that happened to a player in one round."""
    round_number: int
    fortune_card_id: int
    chips_drawn: list[Chip] = field(default_factory=list)
    white_sum_history: list[int] = field(default_factory=list)
    stopped_voluntarily: bool = False
    exploded: bool = False
    cauldron_position: int = 0
    explosion_choice: Optional[ExplosionChoice] = None
    vp_scored: int = 0
    coins_earned: int = 0
    chips_purchased: list[Chip] = field(default_factory=list)
    purple_upgrade: Optional[str] = None
    scoring_position_before: int = 0
    scoring_position_after: int = 0
    rubies_earned: int = 0
    rubies_spent: int = 0
    rat_stone_advance: int = 0
    flask_used: bool = False
    droplet_advanced: bool = False
    bonus_die_rolled: bool = False
    bonus_die_result: Optional[str] = None
    free_fortune_chip: Optional[Chip] = None   # from fortune card
    green_advance: int = 0


class Player:
    """Complete state for one player throughout the game."""

    def __init__(self, name: str, strategy: "PlayerStrategy") -> None:
        self.name = name
        self.strategy = strategy
        self.bag = Bag(list(STARTING_BAG))
        self.cauldron = Cauldron()
        self.scoring_position: int = 0      # position on main scoring track
        self.rubies: int = 0
        self.flask_full: bool = True         # flask starts full each game
        self.coins: int = 0                  # leftover coins (usually 0 between rounds)
        self.book_pages: dict[ChipColor, int] = {
            color: 1 for color in ChipColor if color != ChipColor.WHITE
        }
        self.history: list[RoundRecord] = []
        self._current_record: Optional[RoundRecord] = None

    # ------------------------------------------------------------------
    # Round management
    # ------------------------------------------------------------------

    def begin_round(self, round_number: int, fortune_card_id: int, rat_stone_advance: int = 0) -> RoundRecord:
        self._current_record = RoundRecord(
            round_number=round_number,
            fortune_card_id=fortune_card_id,
            scoring_position_before=self.scoring_position,
            rat_stone_advance=rat_stone_advance,
        )
        self.cauldron.start_round(rat_stone_advance)
        self.coins = 0
        return self._current_record

    def end_round(self) -> RoundRecord:
        """Finalise this round's record and archive it. Return all chips to bag."""
        rec = self._current_record
        assert rec is not None, "end_round called without begin_round"
        rec.scoring_position_after = self.scoring_position
        rec.cauldron_position = self.cauldron.position
        rec.exploded = self.cauldron.exploded

        # Chips drawn during pulling were removed from the bag; chips_from_pot
        # are those drawn chips now returning. remaining_in_bag are the chips
        # that were never drawn this round. Together they form the full bag.
        chips_from_pot = self.cauldron.reset_end_of_round()
        remaining_in_bag = self.bag.all_chips()
        self.bag.refill_from(chips_from_pot + remaining_in_bag)

        self.history.append(rec)
        self._current_record = None
        return rec

    # ------------------------------------------------------------------
    # Pulling phase actions
    # ------------------------------------------------------------------

    def draw_chip(self) -> Chip:
        """Draw one chip from the bag (blind)."""
        chip = self.bag.draw()
        rec = self._current_record
        if rec is not None:
            rec.chips_drawn.append(chip)
            rec.white_sum_history.append(self.cauldron.white_sum)
        return chip

    def place_chip(self, chip: Chip) -> tuple[int, list[int]]:
        """Place a chip in the cauldron. Returns (new_position, rubies_hit)."""
        pos, ruby_spaces = self.cauldron.place(chip)
        rubies_gained = len(ruby_spaces)
        self.rubies += rubies_gained
        if self._current_record:
            self._current_record.rubies_earned += rubies_gained
        return pos, ruby_spaces

    def use_flask(self, chip: Chip) -> bool:
        """Return a chip to the bag using the flask. Returns True if successful."""
        if not self.flask_full:
            return False
        self.bag.return_chip(chip)
        self.flask_full = False
        if self._current_record:
            self._current_record.flask_used = True
        return True

    # ------------------------------------------------------------------
    # Scoring phase
    # ------------------------------------------------------------------

    def score_vp(self, vp: int) -> None:
        """Advance the scoring marker by vp spaces (collecting scoring-track rubies)."""
        from quacks.scoring import SCORING_TRACK_RUBY_POSITIONS, SCORING_TRACK_MAX
        old = self.scoring_position
        new = min(old + vp, SCORING_TRACK_MAX)
        # Collect rubies on scoring track
        for pos in range(old + 1, new + 1):
            if pos in SCORING_TRACK_RUBY_POSITIONS:
                self.rubies += 1
                if self._current_record:
                    self._current_record.rubies_earned += 1
        self.scoring_position = new
        if self._current_record:
            self._current_record.vp_scored = vp

    def earn_coins(self, coins: int) -> None:
        self.coins += coins
        if self._current_record:
            self._current_record.coins_earned = coins

    # ------------------------------------------------------------------
    # Buying phase
    # ------------------------------------------------------------------

    def buy_chip(self, chip: Chip, cost: int) -> bool:
        """Deduct coins and add chip to bag. Returns False if insufficient coins."""
        if self.coins < cost:
            return False
        self.coins -= cost
        self.bag.add(chip)
        if self._current_record:
            self._current_record.chips_purchased.append(chip)
        return True

    # ------------------------------------------------------------------
    # Ruby spending
    # ------------------------------------------------------------------

    def spend_rubies_for_droplet(self, times: int = 1) -> int:
        """Spend 2 rubies per advance. Returns number of times advanced."""
        from quacks.scoring import MAX_CAULDRON_POSITION as CAULDRON_MAX
        advances = 0
        for _ in range(times):
            if self.rubies >= 2 and self.cauldron.droplet_position < CAULDRON_MAX:
                self.rubies -= 2
                self.cauldron.advance_droplet(1)
                advances += 1
                if self._current_record:
                    self._current_record.rubies_spent += 2
                    self._current_record.droplet_advanced = True
        return advances

    def spend_rubies_for_flask(self) -> bool:
        """Spend 2 rubies to refill the flask. Returns True if successful."""
        if self.rubies >= 2 and not self.flask_full:
            self.rubies -= 2
            self.flask_full = True
            if self._current_record:
                self._current_record.rubies_spent += 2
            return True
        return False

    # ------------------------------------------------------------------
    # Explosion handling
    # ------------------------------------------------------------------

    def choose_explosion_outcome(self, state: "GameState") -> ExplosionChoice:
        """Let strategy decide between VP and coins after explosion."""
        choice = self.strategy.choose_explosion_outcome(self, state)
        if self._current_record:
            self._current_record.explosion_choice = choice
        return choice

    # ------------------------------------------------------------------
    # Computed properties
    # ------------------------------------------------------------------

    @property
    def total_bag_size(self) -> int:
        return self.bag.size + len(self.cauldron.chips_in_pot)

    def bag_white_count(self) -> int:
        return self.bag.count(ChipColor.WHITE) + self.cauldron.count_color(ChipColor.WHITE)

    def all_chips(self) -> list[Chip]:
        """All chips owned (bag + cauldron)."""
        return self.bag.all_chips() + self.cauldron.chips_in_pot

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def snapshot(self) -> dict:
        return {
            "name": self.name,
            "scoring_position": self.scoring_position,
            "rubies": self.rubies,
            "flask_full": self.flask_full,
            "droplet_position": self.cauldron.droplet_position,
            "bag_size": self.bag.size,
            "bag_composition": str(self.bag),
        }

    def __repr__(self) -> str:
        return (
            f"Player({self.name!r}, score={self.scoring_position}, "
            f"rubies={self.rubies}, bag={self.bag.size} chips)"
        )
