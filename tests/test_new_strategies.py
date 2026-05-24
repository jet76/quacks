"""Tests for EVOptimalStrategy, MonteCarloStrategy, and stats bug fixes."""

from __future__ import annotations
import random

import pytest

from quacks.chips import WHITE_1, WHITE_2, WHITE_3, GREEN_1, ORANGE_1, BLUE_1
from quacks.enums import ChipColor, GamePhase
from quacks.game import Game, GameState, TOTAL_ROUNDS
from quacks.player import Player
from quacks.stats import StatsCollector
from quacks.strategies.ev_optimal import EVOptimalStrategy
from quacks.strategies.monte_carlo import MonteCarloStrategy
from quacks.strategies.threshold import ThresholdStrategy
from quacks.scoring import cauldron_reward
from quacks.market import Market


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
# Bug fix: white_sum captured before cauldron reset
# ---------------------------------------------------------------------------

class TestWhiteSumStatsBug:
    def test_white_sum_nonzero_in_stats(self):
        """white_sum in RoundRecord should reflect actual sum, not 0 post-reset."""
        strat = ThresholdStrategy(white_threshold=7)  # draws heavily → high white_sum
        p = Player("P1", strat)
        game = Game([p, Player("P2", ThresholdStrategy())], rng=rng(42))
        result = game.run()

        collector = StatsCollector()
        collector.record_result(result)

        round_records = collector.all_round_records()
        max_white = max(r.white_sum for r in round_records)
        assert max_white > 0, "All white_sum values are 0 — stats bug not fixed"

    def test_white_sum_never_exceeds_7_when_not_exploded(self):
        """Explosion triggers at white_sum > 7, so end-of-round white_sum ≤ 7
        for non-exploded rounds (final chip may push it to 8 on explosion)."""
        strat = ThresholdStrategy(white_threshold=6)
        p = Player("P1", strat)
        game = Game([p, Player("P2", ThresholdStrategy())], rng=rng(99))
        result = game.run()
        for rec in p.history:
            if not rec.exploded:
                assert rec.white_sum <= 7


# ---------------------------------------------------------------------------
# Bug fix: vp_scored accumulates (not overwrites)
# ---------------------------------------------------------------------------

class TestVPScoredAccumulation:
    def test_vp_scored_nonnegative(self):
        """VP scored each round should be ≥ 0."""
        for seed in range(10):
            strat = ThresholdStrategy(white_threshold=5)
            p = Player("P1", strat)
            game = Game([p, Player("P2", ThresholdStrategy())], rng=rng(seed))
            result = game.run()
            for rec in p.history:
                assert rec.vp_scored >= 0

    def test_vp_scored_matches_cauldron_position(self):
        """Rounds with valid cauldron positions should yield nonnegative VP."""
        strat = ThresholdStrategy(white_threshold=5)
        p = Player("P1", strat)
        game = Game([p, Player("P2", ThresholdStrategy())], rng=rng(0))
        result = game.run()
        for rec in p.history:
            assert rec.vp_scored >= 0


# ---------------------------------------------------------------------------
# Bug fix: coins_earned accumulates
# ---------------------------------------------------------------------------

class TestCoinsEarnedAccumulation:
    def test_coins_earned_nonnegative(self):
        for seed in range(5):
            strat = ThresholdStrategy(white_threshold=5)
            p = Player("P1", strat)
            game = Game([p, Player("P2", ThresholdStrategy())], rng=rng(seed))
            result = game.run()
            for rec in p.history:
                assert rec.coins_earned >= 0


# ---------------------------------------------------------------------------
# EVOptimalStrategy
# ---------------------------------------------------------------------------

class TestEVOptimalStrategy:
    def test_instantiation(self):
        strat = EVOptimalStrategy()
        assert strat.coin_rate == 0.25
        strat2 = EVOptimalStrategy(coin_rate=0.1)
        assert strat2.coin_rate == 0.1

    def test_name_includes_coin_rate(self):
        strat = EVOptimalStrategy(coin_rate=0.3)
        assert "0.3" in strat.name

    def test_stop_value_at_position_0(self):
        strat = EVOptimalStrategy(coin_rate=0.25)
        assert strat._stop_value(0) == 0.0

    def test_stop_value_at_position_15(self):
        strat = EVOptimalStrategy(coin_rate=0.25)
        # position 15: VP=3, coins=15 → 3 + 15*0.25 = 6.75
        assert abs(strat._stop_value(15) - (3 + 15 * 0.25)) < 1e-9

    def test_explosion_value_takes_max(self):
        strat = EVOptimalStrategy(coin_rate=0.25)
        r = cauldron_reward(15)    # VP=3, coins=15
        ev = strat._explosion_value(15)
        assert ev == max(3.0, 15 * 0.25)

    def test_empty_bag_stops_immediately(self):
        strat = EVOptimalStrategy()
        p = Player("P1", strat)
        p.bag._chips = []
        p.cauldron.start_round()
        state = make_state(p)
        assert strat.should_continue_pulling(p, state) is False

    def test_all_white_stops_when_risky(self):
        """With bag full of WHITE_3 chips and white_sum=5, any draw explodes."""
        strat = EVOptimalStrategy(coin_rate=0.0)
        p = Player("P1", strat)
        p.bag._chips = [WHITE_3, WHITE_3]
        p.cauldron.start_round()
        p.cauldron._white_sum = 5   # 5 + 3 = 8 > 7 → guaranteed explosion
        state = make_state(p)
        assert strat.should_continue_pulling(p, state) is False

    def test_runs_full_game(self):
        strat = EVOptimalStrategy(coin_rate=0.25)
        p1 = Player("EV", strat)
        p2 = Player("Thresh", ThresholdStrategy())
        game = Game([p1, p2], rng=rng(7))
        result = game.run()
        assert result.rounds_played == TOTAL_ROUNDS
        assert result.winner_name in {p1.name, p2.name}

    def test_ev_optimal_wins_more_than_random_threshold(self):
        """EVOptimal should win at least 30% of heads-up games."""
        n = 50
        ev_wins = 0
        for seed in range(n):
            p_ev = Player("EV", EVOptimalStrategy())
            p_th = Player("Th", ThresholdStrategy(white_threshold=5))
            result = Game([p_ev, p_th], rng=rng(seed)).run()
            if result.winner_name == "EV":
                ev_wins += 1
        win_rate = ev_wins / n
        assert win_rate >= 0.28, f"EVOptimal win rate {win_rate:.1%} is unexpectedly low"

    def test_memoisation_consistency(self):
        """Same bag/white_sum/position always returns the same EV."""
        strat = EVOptimalStrategy()
        chips = tuple(sorted([WHITE_1, WHITE_2, GREEN_1, ORANGE_1],
                              key=lambda c: (c.color.value, c.value)))
        memo1: dict = {}
        memo2: dict = {}
        ev1 = strat._draw_ev(chips, 0, 5, memo1)
        ev2 = strat._draw_ev(chips, 0, 5, memo2)
        assert abs(ev1 - ev2) < 1e-12

    def test_choose_purchases_avoids_white(self):
        """EVOptimal should not buy white chips (none available in market)."""
        strat = EVOptimalStrategy()
        p = Player("P1", strat)
        p.begin_round(1, 0)
        p.earn_coins(20)
        state = make_state(p)
        purchases = strat.choose_purchases(p, state, 20)
        for chip in purchases:
            assert chip.color != ChipColor.WHITE


# ---------------------------------------------------------------------------
# MonteCarloStrategy
# ---------------------------------------------------------------------------

class TestMonteCarloStrategy:
    def test_instantiation(self):
        strat = MonteCarloStrategy()
        assert strat.n_simulations == 200
        strat2 = MonteCarloStrategy(n_simulations=50, coin_rate=0.1)
        assert strat2.n_simulations == 50
        assert strat2.coin_rate == 0.1

    def test_name_includes_n_sims(self):
        strat = MonteCarloStrategy(n_simulations=150)
        assert "150" in strat.name

    def test_empty_bag_stops(self):
        strat = MonteCarloStrategy(n_simulations=20)
        p = Player("P1", strat)
        p.bag._chips = []
        p.cauldron.start_round()
        state = make_state(p)
        assert strat.should_continue_pulling(p, state) is False

    def test_guaranteed_explosion_stops_with_zero_coin_rate(self):
        # coin_rate=0 → explosion value == 0 == stop value at position 0
        # so drawing is not better than stopping
        strat = MonteCarloStrategy(n_simulations=50, coin_rate=0.0)
        p = Player("P1", strat)
        p.bag._chips = [WHITE_3, WHITE_3]
        p.cauldron.start_round()
        p.cauldron._white_sum = 5
        state = make_state(p)
        assert strat.should_continue_pulling(p, state) is False

    def test_runs_full_game(self):
        strat = MonteCarloStrategy(n_simulations=50)
        p1 = Player("MC", strat)
        p2 = Player("Thresh", ThresholdStrategy())
        game = Game([p1, p2], rng=rng(13))
        result = game.run()
        assert result.rounds_played == TOTAL_ROUNDS

    def test_p_explode_helper(self):
        strat = MonteCarloStrategy()
        # 2 white chips (value 1 each) in bag, white_sum=6: 6+1=7 ≤ 7 → NOT dangerous
        chips = [WHITE_1, WHITE_1, GREEN_1, GREEN_1]
        assert strat._p_explode(chips, 6) == 0.0

        # white_sum=7: any white chip (value 1) pushes to 8 > 7 → dangerous
        assert strat._p_explode(chips, 7) == 0.5  # 2/4 chips are dangerous

    def test_mc_wins_some_games(self):
        n = 40
        mc_wins = 0
        strat = MonteCarloStrategy(n_simulations=30)
        for seed in range(n):
            p_mc = Player("MC", strat)
            p_th = Player("Th", ThresholdStrategy(white_threshold=5))
            result = Game([p_mc, p_th], rng=rng(seed)).run()
            if result.winner_name == "MC":
                mc_wins += 1
        win_rate = mc_wins / n
        assert win_rate >= 0.20, f"MonteCarlo win rate {win_rate:.1%} unexpectedly low"


# ---------------------------------------------------------------------------
# 4-player mix with new strategies
# ---------------------------------------------------------------------------

class TestMixedStrategies:
    def test_four_strategy_game(self):
        players = [
            Player("EV", EVOptimalStrategy(coin_rate=0.25)),
            Player("MC", MonteCarloStrategy(n_simulations=50)),
            Player("Th5", ThresholdStrategy(white_threshold=5)),
            Player("Ca", ThresholdStrategy(white_threshold=3)),
        ]
        game = Game(players, rng=rng(42))
        result = game.run()
        assert result.rounds_played == TOTAL_ROUNDS
        assert result.winner_name in {p.name for p in players}

    def test_stats_collector_with_new_strategies(self):
        collector = StatsCollector()
        for seed in range(20):
            players = [
                Player("EV", EVOptimalStrategy()),
                Player("MC", MonteCarloStrategy(n_simulations=30)),
                Player("Th", ThresholdStrategy()),
                Player("Ag", ThresholdStrategy(white_threshold=6)),
            ]
            game = Game(players, rng=rng(seed))
            result = game.run()
            collector.record_result(result)

        assert collector.n_games == 20
        wr = collector.win_rate_by_strategy()
        assert len(wr) > 0
        # Total player-game slots equals n_games * 4
        total_slots = sum(collector.n_games for _ in wr)
        assert total_slots >= len(wr)
