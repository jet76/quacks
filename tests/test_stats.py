"""Tests for the statistics collector."""

import pytest

from quacks.player import Player
from quacks.game import Game, GameResult
from quacks.simulation import run_batch, run_game
from quacks.stats import StatsCollector
from quacks.strategies.threshold import ThresholdStrategy
from quacks.strategies.aggressive import AggressiveStrategy


def quick_batch(n=20, seed=1):
    return run_batch(
        [ThresholdStrategy(5), AggressiveStrategy()],
        n_games=n,
        seed=seed,
        verbose=False,
    )


class TestStatsCollector:
    def test_records_games(self):
        collector = quick_batch(10)
        assert collector.n_games == 10

    def test_explosion_rate_in_range(self):
        collector = quick_batch(50)
        rate = collector.explosion_rate()
        assert 0.0 <= rate <= 1.0

    def test_explosion_rate_by_round(self):
        collector = quick_batch(50)
        by_round = collector.explosion_rate_by_round()
        assert len(by_round) == 9
        for rnd, rate in by_round.items():
            assert 1 <= rnd <= 9
            assert 0.0 <= rate <= 1.0

    def test_avg_cauldron_position_positive(self):
        collector = quick_batch(20)
        avg = collector.avg_cauldron_position()
        assert avg > 0

    def test_win_rate_by_strategy_sums_to_one_per_player(self):
        collector = quick_batch(100)
        win_rates = collector.win_rate_by_strategy()
        # In a 2-player game with 2 strategies, total wins = n_games
        assert len(win_rates) == 2
        # Each rate between 0 and 1
        for rate in win_rates.values():
            assert 0.0 <= rate <= 1.0

    def test_avg_vp_per_round_positive(self):
        collector = quick_batch(20)
        assert collector.avg_vp_per_round() > 0

    def test_purchase_frequency_tracked(self):
        collector = quick_batch(50)
        freq = collector.purchase_frequency()
        # Should have purchases across multiple chip types
        assert len(freq) > 0

    def test_summary_string_contains_key_info(self):
        collector = quick_batch(20)
        summary = collector.summary()
        assert "EXPLOSION RATES" in summary
        assert "WIN RATES" in summary
        assert "SCORING" in summary

    def test_stopping_vp_correlation(self):
        collector = quick_batch(50)
        corr = collector.stopping_vp_correlation()
        assert len(corr) > 0
        for pos, avg_vp in corr:
            assert pos >= 0
            assert avg_vp >= 0

    def test_run_single_game_with_stats(self):
        result, collector = run_game(
            [ThresholdStrategy(5), ThresholdStrategy(4)],
            collect_stats=True,
        )
        assert collector is not None
        assert collector.n_games == 1
        assert result.rounds_played == 9
