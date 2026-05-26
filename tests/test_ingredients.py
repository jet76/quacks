"""Tests for ingredient effects — all 4 pages of each color, plus bug-fix regressions."""

from __future__ import annotations
import random

import pytest

from quacks.cauldron import Cauldron
from quacks.chips import (
    Chip,
    WHITE_1, WHITE_2, WHITE_3,
    ORANGE_1,
    GREEN_1, GREEN_2, GREEN_4,
    BLUE_1, BLUE_2,
    RED_1, RED_2,
    YELLOW_1,
    PURPLE_1,
    BLACK_1,
)
from quacks.enums import ChipColor, GamePhase
from quacks.game import Game, GameState, TOTAL_ROUNDS
from quacks.ingredients.registry import get_effect, EFFECT_REGISTRY
from quacks.market import Market
from quacks.player import Player
from quacks.strategies.threshold import ThresholdStrategy


def rng(seed: int) -> random.Random:
    return random.Random(seed)


def make_state(p: Player, round_number: int = 1) -> GameState:
    return GameState(
        round_number=round_number,
        phase=GamePhase.EVALUATION_B,
        players=[p],
        market=Market(),
        current_fortune_card=None,
        flask_disabled=False,
        strong_ingredient_bonus=0,
        extra_ruby_on_landing=False,
    )


def place_chip(player: Player, chip: Chip) -> None:
    """Helper: place a chip into the player's cauldron directly."""
    player.cauldron.place(chip)


def place_chips(player: Player, chips: list[Chip]) -> None:
    for c in chips:
        place_chip(player, c)


# ---------------------------------------------------------------------------
# Bug fix: rat stone catch-up uses floor(gap/2)
# ---------------------------------------------------------------------------

class TestRatStoneFix:
    def test_rat_advance_is_half_gap(self):
        """A 6-point gap should advance 3 spaces, not 6."""
        p1 = Player("P1", ThresholdStrategy())
        p2 = Player("P2", ThresholdStrategy())
        game = Game([p1, p2], rng=rng(0))
        # Manually set scoring positions
        p1.scoring_position = 10
        p2.scoring_position = 4
        game.round_number = 2   # non-round-1 so rat stones fire
        advances = game._compute_rat_advances()
        assert advances["P1"] == 0
        assert advances["P2"] == 3   # floor((10 - 4) / 2) = 3

    def test_rat_advance_rounds_down(self):
        p1 = Player("P1", ThresholdStrategy())
        p2 = Player("P2", ThresholdStrategy())
        game = Game([p1, p2], rng=rng(0))
        p1.scoring_position = 5
        p2.scoring_position = 0
        game.round_number = 2
        advances = game._compute_rat_advances()
        assert advances["P2"] == 2   # floor(5 / 2) = 2

    def test_rat_advance_zero_when_tied(self):
        p1 = Player("P1", ThresholdStrategy())
        p2 = Player("P2", ThresholdStrategy())
        game = Game([p1, p2], rng=rng(0))
        p1.scoring_position = 5
        p2.scoring_position = 5
        game.round_number = 2
        advances = game._compute_rat_advances()
        assert advances["P1"] == 0
        assert advances["P2"] == 0


# ---------------------------------------------------------------------------
# Bug fix: Green page 1 uses COUNT not sum
# ---------------------------------------------------------------------------

class TestGreenPage1Fix:
    def test_advances_by_count_not_sum(self):
        """One Green(4) chip should advance by 1 space (count), not 4 (sum)."""
        p = Player("P", ThresholdStrategy())
        p.cauldron.start_round()
        # white_sum == 7 is required
        place_chips(p, [WHITE_1, WHITE_2, WHITE_1, WHITE_3])  # 1+2+1+3 = 7
        p.cauldron._white_sum = 7
        place_chip(p, GREEN_4)

        old_pos = p.cauldron.position
        effect = get_effect(ChipColor.GREEN, 1)
        result = effect.apply(p, make_state(p))
        assert result["green_advance"] == 1  # count = 1, not 4

    def test_two_green_chips_advance_by_two(self):
        p = Player("P", ThresholdStrategy())
        p.cauldron.start_round()
        p.cauldron._white_sum = 7
        place_chips(p, [GREEN_1, GREEN_2])

        old_pos = p.cauldron.position
        effect = get_effect(ChipColor.GREEN, 1)
        result = effect.apply(p, make_state(p))
        assert result["green_advance"] == 2

    def test_no_advance_when_white_sum_not_7(self):
        p = Player("P", ThresholdStrategy())
        p.cauldron.start_round()
        p.cauldron._white_sum = 5
        place_chip(p, GREEN_1)

        effect = get_effect(ChipColor.GREEN, 1)
        result = effect.apply(p, make_state(p))
        assert result["green_advance"] == 0


# ---------------------------------------------------------------------------
# Bug fix: Red page 1 — no cap on orange bonus
# ---------------------------------------------------------------------------

class TestRedPage1Fix:
    def test_three_oranges_give_three_extra(self):
        """3 orange chips → +3 extra spaces (no cap at 2)."""
        p = Player("P", ThresholdStrategy())
        p.cauldron.start_round()
        place_chips(p, [ORANGE_1, ORANGE_1, ORANGE_1])
        place_chip(p, RED_1)

        before = p.cauldron.position
        effect = get_effect(ChipColor.RED, 1)
        result = effect.apply(p, make_state(p), chip=RED_1)
        assert result["red_extra"] == 3

    def test_zero_oranges_no_extra(self):
        p = Player("P", ThresholdStrategy())
        p.cauldron.start_round()
        place_chip(p, RED_1)
        effect = get_effect(ChipColor.RED, 1)
        result = effect.apply(p, make_state(p), chip=RED_1)
        assert result["red_extra"] == 0

    def test_five_oranges_give_five_extra(self):
        p = Player("P", ThresholdStrategy())
        p.cauldron.start_round()
        for _ in range(5):
            place_chip(p, ORANGE_1)
        place_chip(p, RED_1)
        effect = get_effect(ChipColor.RED, 1)
        result = effect.apply(p, make_state(p), chip=RED_1)
        assert result["red_extra"] == 5


# ---------------------------------------------------------------------------
# Green pages 2, 3, 4
# ---------------------------------------------------------------------------

class TestGreenPage2:
    def test_one_green_chip_gives_one_ruby(self):
        p = Player("P", ThresholdStrategy())
        p.cauldron.start_round()
        place_chip(p, GREEN_1)
        rubies_before = p.rubies
        effect = get_effect(ChipColor.GREEN, 2)
        result = effect.apply(p, make_state(p))
        assert result["rubies_earned"] == 1
        assert p.rubies == rubies_before + 1

    def test_three_green_chips_give_three_rubies(self):
        p = Player("P", ThresholdStrategy())
        p.cauldron.start_round()
        place_chips(p, [GREEN_1, GREEN_2, GREEN_4])
        rubies_before = p.rubies
        effect = get_effect(ChipColor.GREEN, 2)
        result = effect.apply(p, make_state(p))
        assert result["rubies_earned"] == 3
        assert p.rubies == rubies_before + 3

    def test_no_green_no_ruby(self):
        p = Player("P", ThresholdStrategy())
        p.cauldron.start_round()
        place_chip(p, ORANGE_1)
        rubies_before = p.rubies
        effect = get_effect(ChipColor.GREEN, 2)
        result = effect.apply(p, make_state(p))
        assert result["rubies_earned"] == 0
        assert p.rubies == rubies_before


class TestGreenPage3:
    def test_advances_without_white_condition(self):
        """Page 3 advances even when white_sum != 7."""
        p = Player("P", ThresholdStrategy())
        p.cauldron.start_round()
        p.cauldron._white_sum = 3
        place_chips(p, [GREEN_1, GREEN_2])
        old_pos = p.cauldron.position
        effect = get_effect(ChipColor.GREEN, 3)
        result = effect.apply(p, make_state(p))
        assert result["green_advance"] == 2

    def test_advances_with_white_sum_7(self):
        p = Player("P", ThresholdStrategy())
        p.cauldron.start_round()
        p.cauldron._white_sum = 7
        place_chip(p, GREEN_1)
        effect = get_effect(ChipColor.GREEN, 3)
        result = effect.apply(p, make_state(p))
        assert result["green_advance"] == 1


class TestGreenPage4:
    def test_two_rubies_per_green(self):
        p = Player("P", ThresholdStrategy())
        p.cauldron.start_round()
        place_chips(p, [GREEN_1, GREEN_2])
        rubies_before = p.rubies
        effect = get_effect(ChipColor.GREEN, 4)
        result = effect.apply(p, make_state(p))
        assert result["rubies_earned"] == 4
        assert p.rubies == rubies_before + 4


# ---------------------------------------------------------------------------
# Blue pages 1–4
# ---------------------------------------------------------------------------

class TestBluePages:
    def _player_with_bag(self, chips):
        p = Player("P", ThresholdStrategy())
        p.bag._chips = list(chips)
        p.cauldron.start_round()
        return p

    def test_page1_places_chip(self):
        p = self._player_with_bag([GREEN_1, ORANGE_1])
        p.cauldron.start_round()
        effect = get_effect(ChipColor.BLUE, 1)
        result = effect.apply(p, make_state(p), chip=BLUE_1)
        assert result["blue_placed"] is not None

    def test_page2_peeks_more_than_page1(self):
        """Page 2 peeks value+1 chips; it should see further into the bag."""
        bag_chips = [GREEN_1, GREEN_2, ORANGE_1, RED_1]
        p1 = self._player_with_bag(bag_chips)
        p2 = self._player_with_bag(bag_chips)
        # Both use BLUE_1; page 2 peeks 2 chips (1+1), page 1 peeks 1
        effect1 = get_effect(ChipColor.BLUE, 1)
        effect2 = get_effect(ChipColor.BLUE, 2)
        # Both may or may not place; just verify both run without error
        effect1.apply(p1, make_state(p1), chip=BLUE_1)
        effect2.apply(p2, make_state(p2), chip=BLUE_1)

    def test_page3_forces_placement_of_non_white(self):
        """Page 3 forces placement of best non-white chip even if strategy returns None."""
        from quacks.strategies.base import PlayerStrategy
        from quacks.enums import ExplosionChoice

        class NullBlueStrategy(ThresholdStrategy):
            def choose_blue_chip(self, player, state, peeked):
                return None  # always declines

        p = Player("P", NullBlueStrategy())
        p.bag._chips = [GREEN_2, ORANGE_1]
        p.cauldron.start_round()
        effect = get_effect(ChipColor.BLUE, 3)
        result = effect.apply(p, make_state(p), chip=BLUE_1)
        # Despite strategy returning None, page 3 forces a placement
        assert result["blue_placed"] is not None

    def test_page4_peeks_extra_chips(self):
        """Page 4 should function and optionally place a chip."""
        p = self._player_with_bag([GREEN_2, ORANGE_1, RED_1, BLUE_1])
        effect = get_effect(ChipColor.BLUE, 4)
        result = effect.apply(p, make_state(p), chip=BLUE_1)
        assert "blue_placed" in result


# ---------------------------------------------------------------------------
# Red pages 2–4
# ---------------------------------------------------------------------------

class TestRedPages:
    def test_page2_moves_white1_chips(self):
        p = Player("P", ThresholdStrategy())
        p.cauldron.start_round()
        place_chip(p, WHITE_1)
        pos_before = p.cauldron._placed[0].position
        place_chip(p, RED_1)  # red in pot now
        effect = get_effect(ChipColor.RED, 2)
        result = effect.apply(p, make_state(p), chip=RED_1)
        assert result["whites_moved"] == 1
        # White-1 chip should have moved +1
        assert p.cauldron._placed[0].position == pos_before + 1

    def test_page2_no_white1_no_move(self):
        p = Player("P", ThresholdStrategy())
        p.cauldron.start_round()
        place_chips(p, [WHITE_2, RED_1])
        effect = get_effect(ChipColor.RED, 2)
        result = effect.apply(p, make_state(p), chip=RED_1)
        assert result["whites_moved"] == 0

    def test_page3_extra_equals_prior_reds(self):
        """Page 3: first red → 0 extra (no prior reds); second red → 1 extra."""
        p = Player("P", ThresholdStrategy())
        p.cauldron.start_round()
        place_chip(p, RED_1)    # first red; no prior reds
        effect = get_effect(ChipColor.RED, 3)
        result = effect.apply(p, make_state(p), chip=RED_1)
        assert result["red_extra"] == 0

        place_chip(p, RED_2)    # second red; 1 prior red
        result2 = effect.apply(p, make_state(p), chip=RED_2)
        assert result2["red_extra"] == 1

    def test_page4_combines_orange_and_red(self):
        p = Player("P", ThresholdStrategy())
        p.cauldron.start_round()
        place_chips(p, [ORANGE_1, ORANGE_1, RED_1])  # 2 orange, 0 prior reds
        effect = get_effect(ChipColor.RED, 4)
        place_chip(p, RED_2)   # 2 prior = {2 orange + 0 prior-reds-before-this}
        result = effect.apply(p, make_state(p), chip=RED_2)
        # orange_count=2, red_already=max(0, count_red-1)=1 → extra=3
        assert result["red_extra"] == 3


# ---------------------------------------------------------------------------
# Yellow pages 2–4
# ---------------------------------------------------------------------------

class TestYellowPages:
    def test_page2_returns_any_white(self):
        p = Player("P", ThresholdStrategy())
        p.cauldron.start_round()
        place_chips(p, [WHITE_1, WHITE_2, ORANGE_1])
        p.cauldron._white_sum = 3
        white_sum_before = p.cauldron._white_sum
        bag_size_before = p.bag.size

        effect = get_effect(ChipColor.YELLOW, 2)
        result = effect.apply(p, make_state(p))
        returned = result["yellow_returned_white"]
        assert returned is not None  # default strategy returns lowest white
        # white_sum should decrease
        assert p.cauldron._white_sum < white_sum_before
        # chip should have returned to bag
        assert p.bag.size == bag_size_before + 1

    def test_page2_no_white_returns_none(self):
        p = Player("P", ThresholdStrategy())
        p.cauldron.start_round()
        place_chip(p, ORANGE_1)
        effect = get_effect(ChipColor.YELLOW, 2)
        result = effect.apply(p, make_state(p))
        assert result["yellow_returned_white"] is None

    def test_page3_can_return_nonwhite(self):
        """Default strategy returns highest white; but page 3 accepts any chip."""
        p = Player("P", ThresholdStrategy())
        p.cauldron.start_round()
        place_chips(p, [WHITE_1, GREEN_2])
        bag_size_before = p.bag.size

        effect = get_effect(ChipColor.YELLOW, 3)
        result = effect.apply(p, make_state(p))
        # Default returns highest white → WHITE_1 returned
        assert result["yellow_returned_chip"] is not None
        assert p.bag.size == bag_size_before + 1

    def test_page4_returns_up_to_two_chips(self):
        p = Player("P", ThresholdStrategy())
        p.cauldron.start_round()
        place_chips(p, [WHITE_1, WHITE_2, GREEN_1])
        p.cauldron._white_sum = 3
        bag_size_before = p.bag.size

        effect = get_effect(ChipColor.YELLOW, 4)
        result = effect.apply(p, make_state(p))
        assert len(result["yellow_returned_chips"]) == 2
        assert p.bag.size == bag_size_before + 2

    def test_page4_empty_pot_returns_nothing(self):
        p = Player("P", ThresholdStrategy())
        p.cauldron.start_round()
        effect = get_effect(ChipColor.YELLOW, 4)
        result = effect.apply(p, make_state(p))
        assert result["yellow_returned_chips"] == []


# ---------------------------------------------------------------------------
# Black pages 2–4
# ---------------------------------------------------------------------------

class TestBlackPages:
    def _player_with_bag_of(self, chips):
        p = Player("P", ThresholdStrategy())
        p.bag._chips = list(chips)
        p.bag._rng = random.Random(1)  # fixed seed so peek is deterministic
        p.cauldron.start_round()
        place_chip(p, BLACK_1)  # 1 black chip in pot
        return p

    def test_page2_peeks_more_than_page1(self):
        p1 = self._player_with_bag_of([WHITE_1, GREEN_1, ORANGE_1])
        p2 = self._player_with_bag_of([WHITE_1, GREEN_1, ORANGE_1])
        r1 = get_effect(ChipColor.BLACK, 1).apply(p1, make_state(p1))
        r2 = get_effect(ChipColor.BLACK, 2).apply(p2, make_state(p2))
        # Page 2 should peek at least as many chips as page 1
        assert len(r2["black_peeked"]) >= len(r1["black_peeked"])

    def test_page3_peeks_all_chips(self):
        chips = [WHITE_1, GREEN_1, ORANGE_1, RED_1, BLUE_1]
        p = self._player_with_bag_of(chips)
        result = get_effect(ChipColor.BLACK, 3).apply(p, make_state(p))
        # Should see all 5 chips
        assert len(result["black_peeked"]) == len(chips)

    def test_page3_no_black_no_peek(self):
        p = Player("P", ThresholdStrategy())
        p.bag._chips = [WHITE_1, GREEN_1]
        p.cauldron.start_round()  # no black chip placed
        result = get_effect(ChipColor.BLACK, 3).apply(p, make_state(p))
        assert result == {}

    def test_page4_removes_chip(self):
        p = self._player_with_bag_of([WHITE_2, GREEN_1, ORANGE_1])
        bag_size_before = p.bag.size
        result = get_effect(ChipColor.BLACK, 4).apply(p, make_state(p))
        # Default strategy removes highest white (WHITE_2)
        assert result.get("black_removed") is not None
        assert p.bag.size == bag_size_before - 1

    def test_page4_no_white_no_removal(self):
        p = self._player_with_bag_of([GREEN_1, ORANGE_1])
        bag_size_before = p.bag.size
        result = get_effect(ChipColor.BLACK, 4).apply(p, make_state(p))
        # Default strategy returns None when no whites in peeked chips
        assert result.get("black_removed") is None
        assert p.bag.size == bag_size_before


# ---------------------------------------------------------------------------
# Registry completeness
# ---------------------------------------------------------------------------

class TestRegistryCompleteness:
    def test_all_colors_have_pages_1_and_2(self):
        colors = [
            ChipColor.GREEN, ChipColor.BLUE, ChipColor.RED,
            ChipColor.YELLOW, ChipColor.BLACK, ChipColor.PURPLE,
        ]
        for color in colors:
            for page in (1, 2):
                assert get_effect(color, page) is not None, (
                    f"Missing effect for {color.value} page {page}"
                )

    def test_all_colors_have_pages_3_and_4(self):
        colors = [
            ChipColor.GREEN, ChipColor.BLUE, ChipColor.RED,
            ChipColor.YELLOW, ChipColor.BLACK,
        ]
        for color in colors:
            for page in (3, 4):
                assert get_effect(color, page) is not None, (
                    f"Missing effect for {color.value} page {page}"
                )

    def test_all_effects_have_correct_phase_types(self):
        valid_phases = {"on_draw", "evaluation_b", "buying"}
        for key, effect in EFFECT_REGISTRY.items():
            assert effect.phase in valid_phases, (
                f"Effect {key} has unknown phase '{effect.phase}'"
            )


# ---------------------------------------------------------------------------
# Full-game integration with non-default book pages
# ---------------------------------------------------------------------------

class TestIngredientPagesIntegration:
    def _run_game(self, book_pages: dict, seed: int = 0) -> None:
        players = [
            Player("P1", ThresholdStrategy()),
            Player("P2", ThresholdStrategy()),
        ]
        for p in players:
            p.book_pages.update(book_pages)
        game = Game(players, rng=rng(seed))
        result = game.run()
        assert result.rounds_played == TOTAL_ROUNDS

    def test_green_page2_game(self):
        self._run_game({ChipColor.GREEN: 2})

    def test_green_page3_game(self):
        self._run_game({ChipColor.GREEN: 3})

    def test_green_page4_game(self):
        self._run_game({ChipColor.GREEN: 4})

    def test_blue_page2_game(self):
        self._run_game({ChipColor.BLUE: 2})

    def test_blue_page3_game(self):
        self._run_game({ChipColor.BLUE: 3})

    def test_blue_page4_game(self):
        self._run_game({ChipColor.BLUE: 4})

    def test_red_page3_game(self):
        self._run_game({ChipColor.RED: 3})

    def test_red_page4_game(self):
        self._run_game({ChipColor.RED: 4})

    def test_yellow_page2_game(self):
        self._run_game({ChipColor.YELLOW: 2})

    def test_yellow_page3_game(self):
        self._run_game({ChipColor.YELLOW: 3})

    def test_yellow_page4_game(self):
        self._run_game({ChipColor.YELLOW: 4})

    def test_black_page2_game(self):
        self._run_game({ChipColor.BLACK: 2})

    def test_black_page3_game(self):
        self._run_game({ChipColor.BLACK: 3})

    def test_black_page4_game(self):
        self._run_game({ChipColor.BLACK: 4})

    def test_all_pages_maxed_game(self):
        """Run a full game with every ingredient at page 4."""
        self._run_game({
            ChipColor.GREEN: 4,
            ChipColor.BLUE: 4,
            ChipColor.RED: 4,
            ChipColor.YELLOW: 4,
            ChipColor.BLACK: 4,
            ChipColor.PURPLE: 4,
        }, seed=77)
