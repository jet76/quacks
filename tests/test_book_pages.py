"""Tests for ingredient book page selection — setup, book sets, and priority."""

from __future__ import annotations
import random

import pytest

from quacks.chips import Chip
from quacks.enums import ChipColor, GamePhase
from quacks.expansions import Expansion
from quacks.game import Game, GameState, TOTAL_ROUNDS, _SET_COLORS, _black_page
from quacks.market import Market
from quacks.player import Player
from quacks.strategies.base import PlayerStrategy
from quacks.strategies.threshold import ThresholdStrategy
from quacks.enums import ExplosionChoice


def rng(seed: int) -> random.Random:
    return random.Random(seed)


def two_players(**kwargs) -> list[Player]:
    return [
        Player("P1", ThresholdStrategy()),
        Player("P2", ThresholdStrategy()),
    ]


# ---------------------------------------------------------------------------
# Default: all players start on page 1 (Set 1)
# ---------------------------------------------------------------------------

class TestDefaultPages:
    def test_set_colors_default_to_page_1(self):
        players = two_players()
        Game(players, rng=rng(0))
        for p in players:
            for color in _SET_COLORS:
                assert p.book_pages[color] == 1, (
                    f"{p.name} {color.value} expected page 1, got {p.book_pages[color]}"
                )

    def test_orange_always_page_1(self):
        players = two_players()
        Game(players, rng=rng(0), book_set=4)
        for p in players:
            assert p.book_pages[ChipColor.ORANGE] == 1

    def test_black_page_1_for_two_players(self):
        players = two_players()
        Game(players, rng=rng(0))
        for p in players:
            assert p.book_pages[ChipColor.BLACK] == 1

    def test_black_page_2_for_three_players(self):
        players = [Player(f"P{i}", ThresholdStrategy()) for i in range(3)]
        Game(players, rng=rng(0))
        for p in players:
            assert p.book_pages[ChipColor.BLACK] == 2

    def test_black_page_2_for_four_players(self):
        players = [Player(f"P{i}", ThresholdStrategy()) for i in range(4)]
        Game(players, rng=rng(0))
        for p in players:
            assert p.book_pages[ChipColor.BLACK] == 2


# ---------------------------------------------------------------------------
# book_set parameter
# ---------------------------------------------------------------------------

class TestBookSet:
    def test_book_set_applies_to_all_set_colors(self):
        for n in [1, 2, 3, 4]:
            players = two_players()
            Game(players, rng=rng(0), book_set=n)
            for p in players:
                for color in _SET_COLORS:
                    assert p.book_pages[color] == n, (
                        f"set {n}: {p.name} {color.value} expected page {n}"
                    )

    def test_book_set_does_not_change_orange(self):
        players = two_players()
        Game(players, rng=rng(0), book_set=3)
        for p in players:
            assert p.book_pages[ChipColor.ORANGE] == 1

    def test_book_set_does_not_change_black(self):
        players = two_players()
        Game(players, rng=rng(0), book_set=4)
        for p in players:
            assert p.book_pages[ChipColor.BLACK] == 1  # 2-player → page 1

    def test_book_set_applied_equally_to_all_players(self):
        players = two_players()
        Game(players, rng=rng(0), book_set=2)
        pages_p1 = dict(players[0].book_pages)
        pages_p2 = dict(players[1].book_pages)
        assert pages_p1 == pages_p2

    def test_book_set_random_picks_valid_set(self):
        for seed in range(20):
            players = two_players()
            Game(players, rng=rng(seed), book_set="random")
            for color in _SET_COLORS:
                assert 1 <= players[0].book_pages[color] <= 4

    def test_book_set_random_same_for_all_players(self):
        players = two_players()
        Game(players, rng=rng(7), book_set="random")
        for color in _SET_COLORS:
            assert players[0].book_pages[color] == players[1].book_pages[color]

    def test_invalid_book_set_raises(self):
        with pytest.raises((ValueError, TypeError)):
            Game(two_players(), rng=rng(0), book_set=5)

    def test_invalid_book_set_zero_raises(self):
        with pytest.raises((ValueError, TypeError)):
            Game(two_players(), rng=rng(0), book_set=0)


# ---------------------------------------------------------------------------
# book_pages explicit overrides
# ---------------------------------------------------------------------------

class TestBookPagesOverride:
    def test_book_pages_overrides_set(self):
        players = two_players()
        Game(players, rng=rng(0), book_set=2,
             book_pages={ChipColor.GREEN: 4})
        for p in players:
            assert p.book_pages[ChipColor.GREEN] == 4   # override wins
            assert p.book_pages[ChipColor.BLUE] == 2    # set still applies

    def test_book_pages_alone_without_set(self):
        players = two_players()
        Game(players, rng=rng(0), book_pages={ChipColor.GREEN: 3})
        for p in players:
            assert p.book_pages[ChipColor.GREEN] == 3
            assert p.book_pages[ChipColor.BLUE] == 1    # unaffected

    def test_invalid_page_0_ignored(self):
        players = two_players()
        Game(players, rng=rng(0), book_pages={ChipColor.GREEN: 0})
        for p in players:
            assert p.book_pages[ChipColor.GREEN] == 1

    def test_invalid_page_5_ignored(self):
        players = two_players()
        Game(players, rng=rng(0), book_pages={ChipColor.BLUE: 5})
        for p in players:
            assert p.book_pages[ChipColor.BLUE] == 1

    def test_white_cannot_be_overridden(self):
        players = two_players()
        Game(players, rng=rng(0), book_pages={ChipColor.WHITE: 2})
        for p in players:
            assert ChipColor.WHITE not in p.book_pages


# ---------------------------------------------------------------------------
# Expansion overrides (highest priority)
# ---------------------------------------------------------------------------

class TestExpansionPageOverrides:
    def test_expansion_override_beats_book_set(self):
        exp = Expansion(name="Test", book_page_overrides={ChipColor.YELLOW: 3})
        players = two_players()
        Game(players, rng=rng(0), book_set=2, expansions=[exp])
        for p in players:
            assert p.book_pages[ChipColor.YELLOW] == 3   # expansion wins
            assert p.book_pages[ChipColor.GREEN] == 2    # set still applies

    def test_expansion_override_beats_book_pages(self):
        exp = Expansion(name="Test", book_page_overrides={ChipColor.GREEN: 4})
        players = two_players()
        Game(players, rng=rng(0), book_pages={ChipColor.GREEN: 2}, expansions=[exp])
        for p in players:
            assert p.book_pages[ChipColor.GREEN] == 4


# ---------------------------------------------------------------------------
# Full-game integration
# ---------------------------------------------------------------------------

class TestBookPagesFullGame:
    def test_game_runs_with_book_set_2(self):
        players = two_players()
        result = Game(players, rng=rng(5), book_set=2).run()
        assert result.rounds_played == TOTAL_ROUNDS

    def test_game_runs_with_book_set_4(self):
        players = two_players()
        result = Game(players, rng=rng(42), book_set=4).run()
        assert result.rounds_played == TOTAL_ROUNDS
        assert result.winner_name in {"P1", "P2"}

    def test_game_runs_with_random_set(self):
        players = two_players()
        result = Game(players, rng=rng(99), book_set="random").run()
        assert result.rounds_played == TOTAL_ROUNDS

    def test_book_set_deterministic_with_seed(self):
        def run(seed):
            players = two_players()
            return Game(players, rng=rng(seed), book_set="random").run().winner_name

        assert run(1) == run(1)
        assert run(2) == run(2)
