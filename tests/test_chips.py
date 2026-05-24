"""Tests for chip data structures and bag mechanics."""

import pytest
from collections import Counter

from quacks.chips import (
    Chip, WHITE_1, WHITE_2, WHITE_3, ORANGE_1, GREEN_1, GREEN_2, GREEN_4,
    BLUE_1, RED_1, YELLOW_1, PURPLE_1, BLACK_1, STARTING_BAG, CHIP_COSTS,
    chip_cost,
)
from quacks.bag import Bag
from quacks.enums import ChipColor


class TestChip:
    def test_chip_equality(self):
        assert WHITE_1 == Chip(ChipColor.WHITE, 1)

    def test_chip_is_hashable(self):
        s = {WHITE_1, WHITE_2}
        assert len(s) == 2

    def test_chip_repr(self):
        assert "White" in repr(WHITE_1)
        assert "1" in repr(WHITE_1)

    def test_all_colors_representable(self):
        for color in ChipColor:
            chip = Chip(color, 1)
            assert chip.color == color


class TestStartingBag:
    def test_starting_bag_size(self):
        assert len(STARTING_BAG) == 9

    def test_starting_bag_contains_whites(self):
        whites = [c for c in STARTING_BAG if c.color == ChipColor.WHITE]
        assert len(whites) == 7  # 4×1 + 2×2 + 1×3

    def test_starting_bag_white_values(self):
        whites = [c for c in STARTING_BAG if c.color == ChipColor.WHITE]
        value_counts = Counter(c.value for c in whites)
        assert value_counts[1] == 4
        assert value_counts[2] == 2
        assert value_counts[3] == 1

    def test_starting_bag_has_orange_and_green(self):
        colors = {c.color for c in STARTING_BAG}
        assert ChipColor.ORANGE in colors
        assert ChipColor.GREEN in colors

    def test_starting_white_sum(self):
        """Starting white chips sum = 4×1 + 2×2 + 1×3 = 11. Explosion budget = 7."""
        whites = [c for c in STARTING_BAG if c.color == ChipColor.WHITE]
        total = sum(c.value for c in whites)
        assert total == 11


class TestBag:
    def test_bag_initialises_from_starting_bag(self):
        bag = Bag()
        assert bag.size == len(STARTING_BAG)

    def test_draw_removes_chip(self):
        bag = Bag()
        initial_size = bag.size
        chip = bag.draw()
        assert bag.size == initial_size - 1
        assert isinstance(chip, Chip)

    def test_draw_all_chips(self):
        bag = Bag()
        drawn = []
        while not bag.is_empty:
            drawn.append(bag.draw())
        assert len(drawn) == len(STARTING_BAG)
        assert Counter(drawn) == Counter(STARTING_BAG)

    def test_empty_bag_raises(self):
        bag = Bag([])
        with pytest.raises(ValueError):
            bag.draw()

    def test_return_chip(self):
        bag = Bag()
        size = bag.size
        bag.return_chip(WHITE_1)
        assert bag.size == size + 1

    def test_add_chip(self):
        bag = Bag()
        size = bag.size
        bag.add(GREEN_4)
        assert bag.size == size + 1

    def test_white_sum(self):
        bag = Bag(list(STARTING_BAG))
        whites = [c for c in STARTING_BAG if c.color == ChipColor.WHITE]
        expected = sum(c.value for c in whites)
        assert bag.white_sum() == expected

    def test_explosion_probability_zero_when_safe(self):
        """With only 1 white 1-chip and white sum at 6, prob = chip in bag."""
        bag = Bag([WHITE_1, GREEN_1, ORANGE_1])
        # current white sum = 6, budget = 1. WHITE_1.value=1 > 0 budget? No, 1 == 1.
        # Budget remaining = 7 - 6 = 1. WHITE_1 value 1 > 1 is False. So 0 dangerous.
        prob = bag.explosion_probability(current_white_sum=6)
        assert prob == 0.0  # WHITE_1 with value=1 does not EXCEED budget of 1 (it reaches 7)

    def test_explosion_probability_nonzero(self):
        """With white_sum=7, any white chip would explode."""
        bag = Bag([WHITE_1, GREEN_1])
        prob = bag.explosion_probability(current_white_sum=7)
        assert prob == 0.5  # 1 white out of 2 chips

    def test_prob_draw_white(self):
        bag = Bag([WHITE_1, WHITE_2, GREEN_1])
        assert bag.prob_draw_white() == pytest.approx(2 / 3)

    def test_expected_advance(self):
        bag = Bag([WHITE_1, WHITE_2])  # values 1, 2 → avg 1.5
        assert bag.expected_advance() == pytest.approx(1.5)

    def test_peek_does_not_remove(self):
        bag = Bag([WHITE_1, GREEN_1, ORANGE_1])
        size_before = bag.size
        peeked = bag.peek(2)
        assert bag.size == size_before
        assert len(peeked) == 2

    def test_draw_specific(self):
        bag = Bag([WHITE_1, GREEN_1])
        bag.draw_specific(GREEN_1)
        assert bag.size == 1
        assert bag.all_chips() == [WHITE_1]

    def test_composition(self):
        bag = Bag([WHITE_1, WHITE_1, GREEN_1])
        comp = bag.composition()
        assert comp[WHITE_1] == 2
        assert comp[GREEN_1] == 1


class TestChipCosts:
    def test_orange_cost(self):
        assert chip_cost(ORANGE_1) == 3

    def test_green_costs(self):
        assert chip_cost(GREEN_1) == 4
        assert chip_cost(GREEN_2) == 8
        assert chip_cost(GREEN_4) == 14

    def test_blue_costs(self):
        assert chip_cost(BLUE_1) == 5

    def test_white_not_purchasable(self):
        assert chip_cost(WHITE_1) is None
        assert chip_cost(WHITE_2) is None
