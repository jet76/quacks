"""Tests for ingredient book page selection — setup, priority, and strategy hooks."""

from __future__ import annotations
import random

import pytest

from quacks.chips import Chip
from quacks.enums import ChipColor, GamePhase
from quacks.expansions import Expansion
from quacks.game import Game, GameState, TOTAL_ROUNDS
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
# Default: all players start on page 1
# ---------------------------------------------------------------------------

class TestDefaultPages:
    def test_all_colors_default_to_page_1(self):
        players = two_players()
        Game(players, rng=rng(0))
        for p in players:
            for color in ChipColor:
                if color == ChipColor.WHITE:
                    continue
                assert p.book_pages[color] == 1, (
                    f"{p.name} {color.value} expected page 1, got {p.book_pages[color]}"
                )


# ---------------------------------------------------------------------------
# Global book_pages param propagates to every player
# ---------------------------------------------------------------------------

class TestGlobalBookPages:
    def test_global_page_applied_to_all_players(self):
        players = two_players()
        Game(players, rng=rng(0), book_pages={ChipColor.GREEN: 3})
        for p in players:
            assert p.book_pages[ChipColor.GREEN] == 3

    def test_other_colors_remain_page_1(self):
        players = two_players()
        Game(players, rng=rng(0), book_pages={ChipColor.GREEN: 2})
        for p in players:
            assert p.book_pages[ChipColor.BLUE] == 1

    def test_invalid_page_0_ignored(self):
        players = two_players()
        Game(players, rng=rng(0), book_pages={ChipColor.GREEN: 0})
        for p in players:
            assert p.book_pages[ChipColor.GREEN] == 1   # unchanged

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
# Expansion book_page_overrides propagate to every player
# ---------------------------------------------------------------------------

class TestExpansionPageOverrides:
    def test_expansion_override_applied(self):
        exp = Expansion(
            name="Test",
            book_page_overrides={ChipColor.YELLOW: 3},
        )
        players = two_players()
        Game(players, rng=rng(0), expansions=[exp])
        for p in players:
            assert p.book_pages[ChipColor.YELLOW] == 3

    def test_expansion_override_beats_global(self):
        """Expansion overrides take priority over global book_pages param."""
        exp = Expansion(
            name="Test",
            book_page_overrides={ChipColor.GREEN: 4},
        )
        players = two_players()
        Game(players, rng=rng(0),
             book_pages={ChipColor.GREEN: 2},
             expansions=[exp])
        for p in players:
            assert p.book_pages[ChipColor.GREEN] == 4


# ---------------------------------------------------------------------------
# Strategy choose_book_pages — per-player independent choices
# ---------------------------------------------------------------------------

class TestStrategyBookPages:
    def test_strategy_can_choose_pages(self):
        class Page3GreenStrategy(ThresholdStrategy):
            def choose_book_pages(self, player, state):
                return {ChipColor.GREEN: 3}

        p1 = Player("P1", Page3GreenStrategy())
        p2 = Player("P2", ThresholdStrategy())          # stays page 1
        Game([p1, p2], rng=rng(0))
        assert p1.book_pages[ChipColor.GREEN] == 3
        assert p2.book_pages[ChipColor.GREEN] == 1

    def test_strategy_choice_beats_global(self):
        """Strategy choice takes highest priority — overrides global book_pages."""
        class Page4Strategy(ThresholdStrategy):
            def choose_book_pages(self, player, state):
                return {ChipColor.BLUE: 4}

        p1 = Player("P1", Page4Strategy())
        p2 = Player("P2", ThresholdStrategy())
        Game([p1, p2], rng=rng(0), book_pages={ChipColor.BLUE: 2})
        assert p1.book_pages[ChipColor.BLUE] == 4   # strategy wins
        assert p2.book_pages[ChipColor.BLUE] == 2   # global applies to p2

    def test_invalid_strategy_page_ignored(self):
        class BadPageStrategy(ThresholdStrategy):
            def choose_book_pages(self, player, state):
                return {ChipColor.RED: 99}

        p = Player("P1", BadPageStrategy())
        Game([p, Player("P2", ThresholdStrategy())], rng=rng(0))
        assert p.book_pages[ChipColor.RED] == 1    # invalid page ignored

    def test_strategy_receives_valid_state(self):
        """Strategy's choose_book_pages receives a proper GameState object."""
        received = {}

        class InspectingStrategy(ThresholdStrategy):
            def choose_book_pages(self, player, state):
                received["state"] = state
                return {}

        p = Player("P", InspectingStrategy())
        Game([p, Player("P2", ThresholdStrategy())], rng=rng(0))
        assert "state" in received
        assert isinstance(received["state"], GameState)


# ---------------------------------------------------------------------------
# Priority order: global < expansion < strategy
# ---------------------------------------------------------------------------

class TestPagePriority:
    def test_full_priority_chain(self):
        """global=2, expansion=3, strategy=4 → strategy wins."""
        exp = Expansion(name="E", book_page_overrides={ChipColor.BLACK: 3})

        class MaxPageStrategy(ThresholdStrategy):
            def choose_book_pages(self, player, state):
                return {ChipColor.BLACK: 4}

        p_max = Player("Max", MaxPageStrategy())
        p_exp = Player("Exp", ThresholdStrategy())   # gets expansion page (3)
        p_base = Player("Base", ThresholdStrategy()) # gets global page (2) overridden by exp (3)

        # MaxPageStrategy only applies to p_max; p_exp and p_base use expansion override
        Game(
            [p_max, p_exp],
            rng=rng(0),
            book_pages={ChipColor.BLACK: 2},
            expansions=[exp],
        )
        assert p_max.book_pages[ChipColor.BLACK] == 4   # strategy beats all
        assert p_exp.book_pages[ChipColor.BLACK] == 3   # expansion beats global


# ---------------------------------------------------------------------------
# Full-game integration with strategy-chosen pages
# ---------------------------------------------------------------------------

class TestBookPagesFullGame:
    def test_game_runs_with_strategy_chosen_pages(self):
        class AllPage2Strategy(ThresholdStrategy):
            def choose_book_pages(self, player, state):
                return {
                    ChipColor.GREEN: 2,
                    ChipColor.BLUE: 2,
                    ChipColor.RED: 2,
                    ChipColor.YELLOW: 2,
                    ChipColor.BLACK: 2,
                }

        players = [Player("P1", AllPage2Strategy()), Player("P2", ThresholdStrategy())]
        result = Game(players, rng=rng(5)).run()
        assert result.rounds_played == TOTAL_ROUNDS

    def test_game_with_all_page_4_completes(self):
        class MaxPageStrategy(ThresholdStrategy):
            def choose_book_pages(self, player, state):
                return {
                    ChipColor.GREEN: 4,
                    ChipColor.BLUE: 4,
                    ChipColor.RED: 4,
                    ChipColor.YELLOW: 4,
                    ChipColor.BLACK: 4,
                    ChipColor.PURPLE: 4,
                }

        players = [Player("P1", MaxPageStrategy()), Player("P2", ThresholdStrategy())]
        result = Game(players, rng=rng(42)).run()
        assert result.rounds_played == TOTAL_ROUNDS
        assert result.winner_name in {"P1", "P2"}
