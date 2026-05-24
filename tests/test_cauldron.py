"""Tests for the cauldron mechanics."""

import pytest

from quacks.cauldron import Cauldron
from quacks.chips import WHITE_1, WHITE_2, WHITE_3, WHITE_4, GREEN_1, GREEN_2, ORANGE_1, RED_1
from quacks.enums import ChipColor
from quacks.scoring import MAX_CAULDRON_POSITION, cauldron_reward


class TestCauldronBasics:
    def setup_method(self):
        self.cauldron = Cauldron()
        self.cauldron.start_round()

    def test_starts_at_droplet_position(self):
        assert self.cauldron.position == 0

    def test_place_chip_advances_position(self):
        self.cauldron.place(WHITE_1)
        assert self.cauldron.position == 1

    def test_place_white_2_chip(self):
        self.cauldron.place(WHITE_2)
        assert self.cauldron.position == 2

    def test_multiple_placements_cumulative(self):
        self.cauldron.place(WHITE_1)
        self.cauldron.place(GREEN_2)
        assert self.cauldron.position == 3

    def test_position_capped_at_max(self):
        # Place a chip that would exceed max
        large_chip = WHITE_4
        for _ in range(10):
            self.cauldron.place(large_chip)
        assert self.cauldron.position == MAX_CAULDRON_POSITION

    def test_chips_in_pot_tracked(self):
        self.cauldron.place(WHITE_1)
        self.cauldron.place(GREEN_1)
        pot = self.cauldron.chips_in_pot
        assert WHITE_1 in pot
        assert GREEN_1 in pot

    def test_count_color(self):
        self.cauldron.place(WHITE_1)
        self.cauldron.place(WHITE_2)
        self.cauldron.place(GREEN_1)
        assert self.cauldron.count_color(ChipColor.WHITE) == 2
        assert self.cauldron.count_color(ChipColor.GREEN) == 1

    def test_sum_color(self):
        self.cauldron.place(WHITE_1)
        self.cauldron.place(WHITE_2)
        assert self.cauldron.sum_color(ChipColor.WHITE) == 3


class TestExplosionMechanic:
    def setup_method(self):
        self.cauldron = Cauldron()
        self.cauldron.start_round()

    def test_no_explosion_at_7(self):
        self.cauldron.place(WHITE_3)
        self.cauldron.place(WHITE_2)
        self.cauldron.place(WHITE_2)
        assert self.cauldron.white_sum == 7
        assert not self.cauldron.exploded

    def test_explosion_at_8(self):
        self.cauldron.place(WHITE_3)
        self.cauldron.place(WHITE_2)
        self.cauldron.place(WHITE_2)
        self.cauldron.place(WHITE_1)
        assert self.cauldron.white_sum == 8
        assert self.cauldron.exploded

    def test_non_white_chips_do_not_trigger_explosion(self):
        for _ in range(20):
            self.cauldron.place(GREEN_1)
        assert not self.cauldron.exploded

    def test_explosion_budget_remaining(self):
        self.cauldron.place(WHITE_3)
        assert self.cauldron.white_budget_remaining() == 4

    def test_explosion_budget_at_zero(self):
        self.cauldron.place(WHITE_3)
        self.cauldron.place(WHITE_4)
        # white_sum = 7, budget = 0
        assert self.cauldron.white_budget_remaining() == 0
        assert not self.cauldron.exploded

    def test_explosion_budget_negative_clamped(self):
        self.cauldron.place(WHITE_4)
        self.cauldron.place(WHITE_4)
        # white_sum = 8, exploded
        assert self.cauldron.exploded
        assert self.cauldron.white_budget_remaining() == 0


class TestDropletAndRatStones:
    def test_rat_stone_advance_shifts_starting_position(self):
        cauldron = Cauldron()
        cauldron.start_round(rat_stone_advance=3)
        assert cauldron.front_position == 3

    def test_chip_placed_after_rat_stone(self):
        cauldron = Cauldron()
        cauldron.start_round(rat_stone_advance=5)
        cauldron.place(WHITE_1)
        assert cauldron.position == 6

    def test_droplet_advance_persists(self):
        cauldron = Cauldron()
        cauldron.advance_droplet(3)
        assert cauldron.droplet_position == 3
        cauldron.start_round()
        assert cauldron.droplet_position == 3  # persists

    def test_droplet_capped_at_max(self):
        cauldron = Cauldron()
        cauldron.advance_droplet(MAX_CAULDRON_POSITION + 10)
        assert cauldron.droplet_position == MAX_CAULDRON_POSITION


class TestRoundReset:
    def test_reset_returns_chips(self):
        cauldron = Cauldron()
        cauldron.start_round()
        cauldron.place(WHITE_1)
        cauldron.place(GREEN_1)
        chips = cauldron.reset_end_of_round()
        assert WHITE_1 in chips
        assert GREEN_1 in chips

    def test_reset_clears_state(self):
        cauldron = Cauldron()
        cauldron.start_round()
        cauldron.place(WHITE_3)
        cauldron.place(WHITE_3)
        cauldron.place(WHITE_2)  # explode
        assert cauldron.exploded
        cauldron.reset_end_of_round()
        cauldron.start_round()
        assert not cauldron.exploded
        assert cauldron.white_sum == 0


class TestScoringIntegration:
    def test_reward_at_position_15(self):
        cauldron = Cauldron()
        cauldron.start_round()
        # Manually set position
        from quacks.cauldron import PlacedChip
        from quacks.chips import Chip
        cauldron._placed = [PlacedChip(WHITE_1, 15, 1)]
        reward = cauldron.reward
        assert reward.vp == 3
        assert reward.coins == 15

    def test_reward_at_position_19(self):
        from quacks.cauldron import PlacedChip
        cauldron = Cauldron()
        cauldron.start_round()
        cauldron._placed = [PlacedChip(WHITE_1, 19, 1)]
        assert cauldron.reward.vp == 5

    def test_reward_at_position_23(self):
        from quacks.cauldron import PlacedChip
        cauldron = Cauldron()
        cauldron.start_round()
        cauldron._placed = [PlacedChip(WHITE_1, 23, 1)]
        assert cauldron.reward.vp == 7

    def test_reward_at_max_position(self):
        from quacks.cauldron import PlacedChip
        cauldron = Cauldron()
        cauldron.start_round()
        cauldron._placed = [PlacedChip(WHITE_1, 33, 1)]
        assert cauldron.reward.vp == 15
        assert cauldron.reward.coins == 35
