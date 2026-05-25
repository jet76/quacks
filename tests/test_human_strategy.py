"""Tests for HumanStrategy — all decision methods with mocked stdin."""

from __future__ import annotations
import random
from unittest.mock import patch

import pytest

from quacks.chips import (
    WHITE_1, WHITE_2, WHITE_3,
    GREEN_1, GREEN_2,
    ORANGE_1, BLUE_1, RED_1, YELLOW_1, PURPLE_1, BLACK_1,
)
from quacks.enums import ChipColor, ExplosionChoice, GamePhase
from quacks.game import Game, GameState, TOTAL_ROUNDS
from quacks.market import Market
from quacks.player import Player
from quacks.strategies.human import HumanStrategy
from quacks.strategies.threshold import ThresholdStrategy


def rng(seed: int = 0) -> random.Random:
    return random.Random(seed)


def make_state(p: Player, round_number: int = 5) -> GameState:
    return GameState(
        round_number=round_number,
        phase=GamePhase.PULLING,
        players=[p],
        market=Market(),
        current_fortune_card=None,
        flask_disabled=False,
        strong_ingredient_bonus=0,
        extra_ruby_on_landing=False,
    )


def human_player() -> Player:
    return Player("Human", HumanStrategy())


def _place(player: Player, chip) -> None:
    player.cauldron.place(chip)


# ---------------------------------------------------------------------------
# should_continue_pulling
# ---------------------------------------------------------------------------

class TestShouldContinuePulling:
    def test_yes_draws(self):
        p = human_player()
        p.cauldron.start_round()
        state = make_state(p)
        with patch("builtins.input", return_value="y"):
            assert p.strategy.should_continue_pulling(p, state) is True

    def test_no_stops(self):
        p = human_player()
        p.cauldron.start_round()
        state = make_state(p)
        with patch("builtins.input", return_value="n"):
            assert p.strategy.should_continue_pulling(p, state) is False

    def test_blank_defaults_to_stop(self):
        p = human_player()
        p.cauldron.start_round()
        state = make_state(p)
        with patch("builtins.input", return_value=""):
            assert p.strategy.should_continue_pulling(p, state) is False

    def test_exploded_returns_false_without_prompt(self):
        p = human_player()
        p.cauldron.start_round()
        p.cauldron._exploded = True
        state = make_state(p)
        # No input should be needed
        assert p.strategy.should_continue_pulling(p, state) is False

    def test_empty_bag_returns_false_without_prompt(self):
        p = human_player()
        p.cauldron.start_round()
        p.bag._chips = []
        state = make_state(p)
        assert p.strategy.should_continue_pulling(p, state) is False


# ---------------------------------------------------------------------------
# use_flask
# ---------------------------------------------------------------------------

class TestUseFlask:
    def test_yes_uses_flask(self):
        p = human_player()
        state = make_state(p)
        with patch("builtins.input", return_value="y"):
            assert p.strategy.use_flask(p, state, WHITE_1) is True

    def test_no_keeps_chip(self):
        p = human_player()
        state = make_state(p)
        with patch("builtins.input", return_value="n"):
            assert p.strategy.use_flask(p, state, WHITE_1) is False

    def test_blank_defaults_to_no(self):
        p = human_player()
        state = make_state(p)
        with patch("builtins.input", return_value=""):
            assert p.strategy.use_flask(p, state, WHITE_1) is False


# ---------------------------------------------------------------------------
# choose_explosion_outcome
# ---------------------------------------------------------------------------

class TestExplosionOutcome:
    def test_vp_choice(self):
        p = human_player()
        p.cauldron.start_round()
        _place(p, WHITE_3)
        state = make_state(p)
        with patch("builtins.input", return_value="vp"):
            assert p.strategy.choose_explosion_outcome(p, state) == ExplosionChoice.VP

    def test_coins_choice(self):
        p = human_player()
        p.cauldron.start_round()
        state = make_state(p)
        with patch("builtins.input", return_value="coins"):
            assert p.strategy.choose_explosion_outcome(p, state) == ExplosionChoice.COINS

    def test_blank_defaults_to_vp(self):
        p = human_player()
        p.cauldron.start_round()
        state = make_state(p)
        with patch("builtins.input", return_value=""):
            assert p.strategy.choose_explosion_outcome(p, state) == ExplosionChoice.VP


# ---------------------------------------------------------------------------
# choose_purchases
# ---------------------------------------------------------------------------

class TestChoosePurchases:
    def test_blank_buys_nothing(self):
        p = human_player()
        state = make_state(p)
        with patch("builtins.input", return_value=""):
            result = p.strategy.choose_purchases(p, state, coins=20)
        assert result == []

    def test_buy_first_listed_chip(self):
        p = human_player()
        state = make_state(p)
        available = state.market.available_chips(5)
        in_stock = [l for l in available if l.stock > 0]
        # Pick index 1 then blank to finish
        with patch("builtins.input", side_effect=["1", ""]):
            result = p.strategy.choose_purchases(p, state, coins=50)
        assert len(result) == 1
        assert result[0] == in_stock[0].chip

    def test_cannot_afford_chip(self):
        p = human_player()
        state = make_state(p)
        # Only 1 coin — nothing affordable
        with patch("builtins.input", return_value="1"):
            result = p.strategy.choose_purchases(p, state, coins=1)
        assert result == []

    def test_invalid_input_ignored(self):
        p = human_player()
        state = make_state(p)
        with patch("builtins.input", side_effect=["abc", "999", ""]):
            result = p.strategy.choose_purchases(p, state, coins=20)
        assert result == []


# ---------------------------------------------------------------------------
# choose_ruby_spending
# ---------------------------------------------------------------------------

class TestRubySpending:
    def test_no_spending_with_few_rubies(self):
        p = human_player()
        p.rubies = 1
        state = make_state(p)
        advances, refill = p.strategy.choose_ruby_spending(p, state)
        assert advances == 0
        assert refill is False

    def test_advance_droplet(self):
        p = human_player()
        p.rubies = 4
        state = make_state(p)
        with patch("builtins.input", side_effect=["y", "n"]):
            advances, refill = p.strategy.choose_ruby_spending(p, state)
        assert advances == 1
        assert refill is False

    def test_refill_flask(self):
        p = human_player()
        p.rubies = 4
        p.flask_full = False
        state = make_state(p)
        with patch("builtins.input", side_effect=["y", "n"]):
            advances, refill = p.strategy.choose_ruby_spending(p, state)
        assert refill is True

    def test_decline_all_spending(self):
        p = human_player()
        p.rubies = 6
        state = make_state(p)
        with patch("builtins.input", return_value="n"):
            advances, refill = p.strategy.choose_ruby_spending(p, state)
        assert advances == 0
        assert refill is False


# ---------------------------------------------------------------------------
# Ingredient powers
# ---------------------------------------------------------------------------

class TestIngredientPowers:
    def test_use_yellow_yes(self):
        p = human_player()
        state = make_state(p)
        with patch("builtins.input", return_value="y"):
            assert p.strategy.use_yellow_power(p, state, WHITE_1) is True

    def test_use_yellow_no(self):
        p = human_player()
        state = make_state(p)
        with patch("builtins.input", return_value="n"):
            assert p.strategy.use_yellow_power(p, state, WHITE_1) is False

    def test_use_yellow_blank_defaults_yes(self):
        p = human_player()
        state = make_state(p)
        with patch("builtins.input", return_value=""):
            assert p.strategy.use_yellow_power(p, state, WHITE_1) is True

    def test_choose_white_to_return_picks_chip(self):
        p = human_player()
        state = make_state(p)
        whites = [WHITE_1, WHITE_2]
        with patch("builtins.input", return_value="1"):
            result = p.strategy.choose_white_to_return(p, state, whites)
        assert result == WHITE_1

    def test_choose_white_to_return_skip(self):
        p = human_player()
        state = make_state(p)
        with patch("builtins.input", return_value="0"):
            result = p.strategy.choose_white_to_return(p, state, [WHITE_1])
        assert result is None

    def test_choose_chip_to_return_nonwhite(self):
        p = human_player()
        state = make_state(p)
        chips = [WHITE_1, GREEN_1, ORANGE_1]
        with patch("builtins.input", return_value="2"):
            result = p.strategy.choose_chip_to_return(p, state, chips)
        assert result == GREEN_1

    def test_choose_chips_to_return_two(self):
        p = human_player()
        state = make_state(p)
        chips = [WHITE_1, WHITE_2, GREEN_1]
        with patch("builtins.input", side_effect=["1", "2"]):
            result = p.strategy.choose_chips_to_return(p, state, chips, max_n=2)
        assert len(result) == 2

    def test_choose_chips_to_return_stop_early(self):
        p = human_player()
        state = make_state(p)
        chips = [WHITE_1, WHITE_2]
        with patch("builtins.input", side_effect=["1", "0"]):
            result = p.strategy.choose_chips_to_return(p, state, chips, max_n=2)
        assert len(result) == 1

    def test_choose_blue_chip_places(self):
        p = human_player()
        state = make_state(p)
        peeked = [GREEN_1, ORANGE_1]
        with patch("builtins.input", return_value="1"):
            result = p.strategy.choose_blue_chip(p, state, peeked)
        assert result == GREEN_1

    def test_choose_blue_chip_return_all(self):
        p = human_player()
        state = make_state(p)
        with patch("builtins.input", return_value="0"):
            result = p.strategy.choose_blue_chip(p, state, [GREEN_1])
        assert result is None

    def test_choose_purple_upgrade(self):
        from quacks.chips import PURPLE_1, PURPLE_2
        p = human_player()
        state = make_state(p)
        options = [(GREEN_1, GREEN_2)]
        with patch("builtins.input", return_value="1"):
            result = p.strategy.choose_purple_upgrade(p, state, options)
        assert result == (GREEN_1, GREEN_2)

    def test_choose_purple_upgrade_skip(self):
        p = human_player()
        state = make_state(p)
        with patch("builtins.input", return_value="0"):
            result = p.strategy.choose_purple_upgrade(p, state, [(GREEN_1, GREEN_2)])
        assert result is None

    def test_choose_free_chip(self):
        p = human_player()
        state = make_state(p)
        available = [GREEN_1, BLUE_1]
        with patch("builtins.input", return_value="2"):
            result = p.strategy.choose_free_chip(p, state, available)
        assert result == BLUE_1

    def test_choose_chip_to_remove_skip(self):
        p = human_player()
        state = make_state(p)
        with patch("builtins.input", return_value="0"):
            result = p.strategy.choose_chip_to_remove(p, state, [WHITE_1])
        assert result is None


# ---------------------------------------------------------------------------
# choose_book_pages
# ---------------------------------------------------------------------------

class TestChooseBookPages:
    def test_all_blank_returns_empty(self):
        p = human_player()
        state = make_state(p)
        with patch("builtins.input", return_value=""):
            pages = p.strategy.choose_book_pages(p, state)
        # All defaults (page 1) → nothing in the dict
        assert all(v == 1 for v in pages.values()) or pages == {}

    def test_selects_nondefault_page(self):
        p = human_player()
        state = make_state(p)
        colors = [c for c in ChipColor if c != ChipColor.WHITE]
        # Answer 3 for the first color, blank for the rest
        responses = ["3"] + [""] * (len(colors) - 1)
        with patch("builtins.input", side_effect=responses):
            pages = p.strategy.choose_book_pages(p, state)
        assert pages.get(colors[0]) == 3


# ---------------------------------------------------------------------------
# Full game integration
# ---------------------------------------------------------------------------

class TestHumanStrategyFullGame:
    def test_full_game_completes(self):
        """Full 9-round game with all-blank input (every prompt takes its default)."""
        p = Player("Human", HumanStrategy())
        ai = Player("AI", ThresholdStrategy())
        # return_value="" → every input() call returns ""; all decisions take defaults:
        # stop pulling, no flask, VP on explosion, no buying, no ruby spending, etc.
        with patch("builtins.input", return_value=""):
            result = Game([p, ai], rng=rng(0)).run()
        assert result.rounds_played == TOTAL_ROUNDS
        assert result.winner_name in {"Human", "AI"}

    def test_human_strategy_name(self):
        assert HumanStrategy().name == "Human"
