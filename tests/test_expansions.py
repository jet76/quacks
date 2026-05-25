"""Tests for the expansion framework, value-buying, and Market extension."""

from __future__ import annotations
import random

import pytest

from quacks.chips import Chip, GREEN_1, ORANGE_1, WHITE_1
from quacks.enums import ChipColor, GamePhase
from quacks.expansions import Expansion
from quacks.expansions.herb_witches import HERB_WITCHES, CYAN_1, CYAN_2, GRAY_1
from quacks.fortune_teller import FortuneCard, FortuneEffect, make_game_deck
from quacks.game import Game, GameState, TOTAL_ROUNDS
from quacks.market import Market
from quacks.player import Player
from quacks.strategies.buying import greedy_value_buy, _chip_score
from quacks.strategies.ev_optimal import EVOptimalStrategy
from quacks.strategies.monte_carlo import MonteCarloStrategy
from quacks.strategies.threshold import ThresholdStrategy


def rng(seed: int) -> random.Random:
    return random.Random(seed)


def make_state(p: Player, round_number: int = 1) -> GameState:
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


# ---------------------------------------------------------------------------
# Expansion dataclass
# ---------------------------------------------------------------------------

class TestExpansionDataclass:
    def test_defaults_are_empty(self):
        exp = Expansion(name="Test")
        assert exp.new_chips == []
        assert exp.extra_fortune_cards == []
        assert exp.starting_bag_extras == []
        assert exp.book_page_overrides == {}
        assert exp.extra_market_stock == {}

    def test_repr(self):
        exp = Expansion(name="Foo")
        assert "Foo" in repr(exp)

    def test_herb_witches_has_chips(self):
        assert len(HERB_WITCHES.new_chips) > 0
        colors = {chip.color for chip, _ in HERB_WITCHES.new_chips}
        assert ChipColor.CYAN in colors
        assert ChipColor.GRAY in colors

    def test_herb_witches_has_fortune_cards(self):
        assert len(HERB_WITCHES.extra_fortune_cards) == 8

    def test_herb_witches_card_ids_unique(self):
        ids = [c.card_id for c in HERB_WITCHES.extra_fortune_cards]
        assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# make_game_deck with extra cards
# ---------------------------------------------------------------------------

class TestMakeGameDeck:
    def test_base_deck_is_9_cards(self):
        deck = make_game_deck(rng(0))
        assert len(deck) == 9

    def test_extra_cards_expand_pool(self):
        extra = HERB_WITCHES.extra_fortune_cards
        deck = make_game_deck(rng(0), extra_cards=extra)
        assert len(deck) == 9  # still 9 drawn

    def test_extra_cards_can_appear(self):
        # With 8 extra cards in a 32-card pool, run many seeds; some should appear
        extra = HERB_WITCHES.extra_fortune_cards
        extra_ids = {c.card_id for c in extra}
        found = False
        for seed in range(200):
            deck = make_game_deck(rng(seed), extra_cards=extra)
            if any(c.card_id in extra_ids for c in deck):
                found = True
                break
        assert found, "Extra fortune cards never appeared in any 200-seed draw"


# ---------------------------------------------------------------------------
# Market with expansion chips
# ---------------------------------------------------------------------------

class TestMarketExpansion:
    def _cyan_costs(self):
        return {
            (ChipColor.CYAN, 1): 3,
            (ChipColor.CYAN, 2): 6,
        }

    def _cyan_stock(self):
        return {
            (ChipColor.CYAN, 1): 4,
            (ChipColor.CYAN, 2): 4,
        }

    def _cyan_avail(self):
        return {ChipColor.CYAN: 1}

    def test_expansion_chips_listed(self):
        m = Market(
            extra_costs=self._cyan_costs(),
            extra_stock=self._cyan_stock(),
            extra_availability=self._cyan_avail(),
        )
        listings = m.available_chips(1)
        colors = {l.chip.color for l in listings}
        assert ChipColor.CYAN in colors

    def test_expansion_chip_cost(self):
        m = Market(
            extra_costs=self._cyan_costs(),
            extra_stock=self._cyan_stock(),
            extra_availability=self._cyan_avail(),
        )
        assert m.cost(Chip(ChipColor.CYAN, 1)) == 3
        assert m.cost(Chip(ChipColor.CYAN, 2)) == 6

    def test_expansion_chip_buyable(self):
        m = Market(
            extra_costs=self._cyan_costs(),
            extra_stock=self._cyan_stock(),
            extra_availability=self._cyan_avail(),
        )
        success, _ = m.buy(Chip(ChipColor.CYAN, 1), coins=10)
        assert success

    def test_base_chips_still_available(self):
        m = Market(
            extra_costs=self._cyan_costs(),
            extra_stock=self._cyan_stock(),
            extra_availability=self._cyan_avail(),
        )
        listings = m.available_chips(1)
        colors = {l.chip.color for l in listings}
        assert ChipColor.GREEN in colors
        assert ChipColor.BLUE in colors


# ---------------------------------------------------------------------------
# Game with expansions
# ---------------------------------------------------------------------------

class TestGameWithExpansion:
    def test_game_runs_with_herb_witches(self):
        players = [
            Player("P1", EVOptimalStrategy()),
            Player("P2", ThresholdStrategy()),
        ]
        game = Game(players, rng=rng(7), expansions=[HERB_WITCHES])
        result = game.run()
        assert result.rounds_played == TOTAL_ROUNDS
        assert result.winner_name in {"P1", "P2"}

    def test_market_has_expansion_chips(self):
        players = [
            Player("P1", ThresholdStrategy()),
            Player("P2", ThresholdStrategy()),
        ]
        game = Game(players, rng=rng(0), expansions=[HERB_WITCHES])
        listings = game.market.available_chips(1)
        colors = {l.chip.color for l in listings}
        assert ChipColor.CYAN in colors
        assert ChipColor.GRAY in colors

    def test_starting_bag_extras_applied(self):
        extra_chip = GREEN_1
        exp = Expansion(name="Test", starting_bag_extras=[extra_chip])
        p1 = Player("P1", ThresholdStrategy())
        p2 = Player("P2", ThresholdStrategy())
        game = Game([p1, p2], rng=rng(0), expansions=[exp])
        # After Game.__init__, each player's bag should have the extra chip
        assert extra_chip in p1.bag.all_chips()
        assert extra_chip in p2.bag.all_chips()

    def test_game_without_expansions_unchanged(self):
        players = [Player("P1", ThresholdStrategy()), Player("P2", ThresholdStrategy())]
        result = Game(players, rng=rng(42)).run()
        assert result.rounds_played == TOTAL_ROUNDS

    def test_multiple_expansions_stack(self):
        exp_a = Expansion(
            name="A",
            new_chips=[(Chip(ChipColor.CYAN, 1), 3)],
        )
        exp_b = Expansion(
            name="B",
            new_chips=[(Chip(ChipColor.GRAY, 1), 2)],
        )
        players = [Player("P1", ThresholdStrategy()), Player("P2", ThresholdStrategy())]
        game = Game(players, rng=rng(1), expansions=[exp_a, exp_b])
        listings = game.market.available_chips(1)
        colors = {l.chip.color for l in listings}
        assert ChipColor.CYAN in colors
        assert ChipColor.GRAY in colors


# ---------------------------------------------------------------------------
# greedy_value_buy
# ---------------------------------------------------------------------------

class TestGreedyValueBuy:
    def test_no_coins_buys_nothing(self):
        p = Player("P1", EVOptimalStrategy())
        state = make_state(p)
        result = greedy_value_buy(p, state, coins=0)
        assert result == []

    def test_last_round_buys_nothing(self):
        # rounds_remaining() == 0 in round 9 → score is -inf → nothing bought
        p = Player("P1", EVOptimalStrategy())
        state = make_state(p, round_number=9)
        result = greedy_value_buy(p, state, coins=100)
        assert result == []

    def test_prefers_green_over_orange(self):
        # With enough coins for either GREEN_1 (4) or ORANGE_1 (3),
        # should pick GREEN_1 (higher colour weight)
        p = Player("P1", EVOptimalStrategy())
        state = make_state(p, round_number=1)
        result = greedy_value_buy(p, state, coins=4)
        assert any(c.color == ChipColor.GREEN for c in result)

    def test_buys_nothing_without_affordable_chip(self):
        p = Player("P1", EVOptimalStrategy())
        state = make_state(p, round_number=1)
        result = greedy_value_buy(p, state, coins=1)
        assert result == []

    def test_does_not_buy_white(self):
        p = Player("P1", EVOptimalStrategy())
        state = make_state(p, round_number=1)
        result = greedy_value_buy(p, state, coins=100)
        assert all(c.color != ChipColor.WHITE for c in result)

    def test_spends_up_to_budget(self):
        p = Player("P1", EVOptimalStrategy())
        state = make_state(p, round_number=1)
        budget = 12
        result = greedy_value_buy(p, state, coins=budget)
        available = state.market.available_chips(1)
        cost_map = {(l.chip.color, l.chip.value): l.cost for l in available}
        total_spent = sum(cost_map[(c.color, c.value)] for c in result)
        assert total_spent <= budget

    def test_chip_score_increases_with_rounds(self):
        chip = GREEN_1
        score_early = _chip_score(chip, 4, rounds_left=8, coin_rate=0.25)
        score_late = _chip_score(chip, 4, rounds_left=1, coin_rate=0.25)
        assert score_early > score_late

    def test_chip_score_zero_rounds_is_negative(self):
        assert _chip_score(GREEN_1, 4, rounds_left=0, coin_rate=0.25) < 0


# ---------------------------------------------------------------------------
# Value-buying integration: strategies use greedy_value_buy
# ---------------------------------------------------------------------------

class TestStrategiesBuySmarter:
    def test_ev_optimal_avoids_white(self):
        strat = EVOptimalStrategy()
        p = Player("P1", strat)
        state = make_state(p, round_number=1)
        purchases = strat.choose_purchases(p, state, 20)
        assert all(c.color != ChipColor.WHITE for c in purchases)

    def test_mc_avoids_white(self):
        strat = MonteCarloStrategy(n_simulations=10)
        p = Player("P1", strat)
        state = make_state(p, round_number=1)
        purchases = strat.choose_purchases(p, state, 20)
        assert all(c.color != ChipColor.WHITE for c in purchases)

    def test_ev_buys_nothing_last_round(self):
        strat = EVOptimalStrategy()
        p = Player("P1", strat)
        state = make_state(p, round_number=TOTAL_ROUNDS)
        purchases = strat.choose_purchases(p, state, 50)
        assert purchases == []
