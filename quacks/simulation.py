"""Simulation runner for batch game analysis.

Provides functions to run many games and collect statistics.
"""

from __future__ import annotations
import random
import time
from dataclasses import dataclass
from typing import Optional

from quacks.chips import STARTING_BAG
from quacks.enums import ChipColor
from quacks.game import Game, GameResult
from quacks.player import Player
from quacks.stats import StatsCollector
from quacks.strategies.base import PlayerStrategy
from quacks.strategies.threshold import ThresholdStrategy
from quacks.strategies.greedy import GreedyBuyerStrategy
from quacks.strategies.cautious import CautiousStrategy
from quacks.strategies.aggressive import AggressiveStrategy


def run_game(
    strategies: list[PlayerStrategy],
    book_pages: dict[ChipColor, int] | None = None,
    rng: random.Random | None = None,
    collect_stats: bool = False,
) -> tuple[GameResult, Optional[StatsCollector]]:
    """Run a single game with the given player strategies.

    Returns:
        (GameResult, StatsCollector if collect_stats else None)
    """
    players = [
        Player(name=f"P{i+1}_{strategy.name}", strategy=strategy)
        for i, strategy in enumerate(strategies)
    ]

    collector = StatsCollector() if collect_stats else None
    handlers = [collector.handle_event] if collector else []

    game = Game(players=players, book_pages=book_pages, rng=rng, event_handlers=handlers)
    result = game.run()

    if collector:
        collector.record_result(result, game_id=1)

    return result, collector


def run_batch(
    strategies: list[PlayerStrategy],
    n_games: int = 1000,
    book_pages: dict[ChipColor, int] | None = None,
    seed: int | None = None,
    verbose: bool = True,
) -> StatsCollector:
    """Run n_games games and collect aggregate statistics.

    Args:
        strategies: One strategy per player (2–4).
        n_games: Number of games to simulate.
        book_pages: Book page selection per ingredient color.
        seed: Random seed for reproducibility.
        verbose: Print progress.

    Returns:
        StatsCollector with all game data.
    """
    collector = StatsCollector()
    rng = random.Random(seed)
    start = time.time()

    for game_id in range(1, n_games + 1):
        players = [
            Player(name=f"P{i+1}_{strategy.name}", strategy=strategy)
            for i, strategy in enumerate(strategies)
        ]
        handlers = [collector.handle_event]
        game = Game(players=players, book_pages=book_pages,
                    rng=random.Random(rng.randint(0, 2**32)),
                    event_handlers=handlers)
        result = game.run()
        collector.record_result(result, game_id=game_id)

        if verbose and game_id % max(1, n_games // 10) == 0:
            elapsed = time.time() - start
            print(f"  [{game_id}/{n_games}] {elapsed:.1f}s — "
                  f"win rates: {_format_win_rates(collector)}")

    if verbose:
        elapsed = time.time() - start
        print(f"Completed {n_games} games in {elapsed:.2f}s "
              f"({n_games/elapsed:.0f} games/sec)")

    return collector


def _format_win_rates(collector: StatsCollector) -> str:
    rates = collector.win_rate_by_strategy()
    return ", ".join(f"{s}: {r:.0%}" for s, r in sorted(rates.items()))


def compare_strategies(
    strategy_sets: list[list[PlayerStrategy]],
    n_games: int = 500,
    seed: int = 42,
) -> dict[str, StatsCollector]:
    """Run multiple configurations head-to-head and return collectors per config.

    Args:
        strategy_sets: Each list is a set of strategies for one 'configuration'.
        n_games: Games per configuration.
    """
    results: dict[str, StatsCollector] = {}
    for strat_list in strategy_sets:
        label = " vs ".join(s.name for s in strat_list)
        print(f"\nConfiguration: {label}")
        collector = run_batch(strat_list, n_games=n_games, seed=seed, verbose=True)
        results[label] = collector
    return results


# ---------------------------------------------------------------------------
# Pre-built configurations for common experiments
# ---------------------------------------------------------------------------

def all_vs_all(n_games: int = 1000, seed: int = 42) -> StatsCollector:
    """4-player game with one of each strategy type."""
    return run_batch(
        strategies=[
            ThresholdStrategy(white_threshold=5),
            CautiousStrategy(stop_threshold=0.25),
            GreedyBuyerStrategy(max_white_sum=6),
            AggressiveStrategy(),
        ],
        n_games=n_games,
        seed=seed,
        verbose=True,
    )


def threshold_sweep(thresholds: list[int], n_games: int = 500, seed: int = 42) -> dict:
    """Test different stopping thresholds in 2-player head-to-head games.

    Returns dict mapping threshold_pair → StatsCollector.
    """
    results = {}
    for t1 in thresholds:
        for t2 in thresholds:
            if t1 > t2:
                continue
            label = f"T{t1} vs T{t2}"
            print(f"\n{label}")
            collector = run_batch(
                [ThresholdStrategy(t1), ThresholdStrategy(t2)],
                n_games=n_games, seed=seed, verbose=False,
            )
            results[label] = collector
            wr = collector.win_rate_by_strategy()
            print(f"  Win rates: {wr}")
    return results


def explosion_probability_study(n_games: int = 2000, seed: int = 99) -> StatsCollector:
    """Study explosion probabilities across different bag states and rounds."""
    return run_batch(
        strategies=[AggressiveStrategy()] * 4,
        n_games=n_games,
        seed=seed,
        verbose=True,
    )
