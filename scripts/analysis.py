"""Quacks of Quedlinburg — strategy analysis script.

Runs multi-game simulations comparing all strategies and outputs:
  - Console summary tables
  - PNG plots saved to scripts/plots/

Usage:
    python scripts/analysis.py [--games N] [--seed S] [--no-plots]
"""

from __future__ import annotations
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from quacks.game import Game
from quacks.player import Player
from quacks.simulation import run_batch, compare_strategies, threshold_sweep
from quacks.stats import StatsCollector
from quacks.strategies import (
    ThresholdStrategy,
    CautiousStrategy,
    GreedyBuyerStrategy,
    AggressiveStrategy,
    EVOptimalStrategy,
    MonteCarloStrategy,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_4p_game(strategies, seed: int | None = None):
    players = [Player(f"P{i+1}({s.name})", s) for i, s in enumerate(strategies)]
    import random as _random
    rng = _random.Random(seed) if seed is not None else None
    return Game(players, rng=rng)


def run_head_to_head(strategies, n_games: int, base_seed: int = 42) -> StatsCollector:
    collector = StatsCollector()
    for i in range(n_games):
        game = _make_4p_game(strategies, seed=base_seed + i)
        result = game.run()
        collector.record_result(result)
    return collector


# ---------------------------------------------------------------------------
# Analysis sections
# ---------------------------------------------------------------------------

def section_strategy_comparison(n_games: int, save_plots: bool) -> None:
    print(f"\n{'='*64}")
    print("SECTION 1: All-Strategy Head-to-Head ({n} games)".format(n=n_games))
    print(f"{'='*64}")

    strategies = [
        ThresholdStrategy(white_threshold=5),
        CautiousStrategy(stop_threshold=0.25),
        EVOptimalStrategy(coin_rate=0.25),
        MonteCarloStrategy(n_simulations=100),
    ]

    t0 = time.perf_counter()
    collector = run_head_to_head(strategies, n_games)
    elapsed = time.perf_counter() - t0
    print(f"Simulated {n_games} games in {elapsed:.1f}s")
    print()
    print(collector.summary())

    if save_plots:
        _plot_win_rates(collector, "head_to_head_win_rates.png")
        _plot_explosion_by_round(collector, "explosion_by_round.png")
        _plot_position_dist(collector, "cauldron_position_distribution.png")


def section_threshold_sweep(n_games: int, save_plots: bool) -> None:
    print(f"\n{'='*64}")
    print("SECTION 2: Threshold Sweep (t=1..7, {n} games each)".format(n=n_games))
    print(f"{'='*64}")

    import random as _random
    dummy_strat = ThresholdStrategy(white_threshold=4)
    results = {}
    for t in range(1, 8):
        strat = ThresholdStrategy(white_threshold=t)
        target_name = f"P1(t={t})"
        collector = StatsCollector()
        for i in range(n_games):
            p = Player(target_name, strat)
            dummy = Player("Dummy", dummy_strat)
            game = Game([p, dummy], rng=_random.Random(42 + i))
            result = game.run()
            collector.record_result(result)
        recs = [r for r in collector.all_round_records() if r.player_name == target_name]
        scores = [g.final_scores.get(target_name, 0) for g in collector._games]
        results[t] = {
            "explosion_rate": sum(r.exploded for r in recs) / len(recs) if recs else 0.0,
            "avg_position": sum(r.cauldron_position for r in recs) / len(recs) if recs else 0.0,
            "avg_vp_round": sum(r.vp_scored for r in recs) / len(recs) if recs else 0.0,
            "avg_final_score": sum(scores) / len(scores) if scores else 0.0,
        }

    print(f"{'Thresh':>7} {'Explode%':>10} {'AvgPos':>8} {'VP/Rnd':>8} {'FinalVP':>9}")
    print("-" * 48)
    for t, d in results.items():
        print(
            f"  t={t}    {d['explosion_rate']:>9.1%}  {d['avg_position']:>7.1f}"
            f"  {d['avg_vp_round']:>7.2f}  {d['avg_final_score']:>8.1f}"
        )

    if save_plots:
        _plot_threshold_sweep(results, "threshold_sweep.png")


def section_ev_analysis(n_games: int, save_plots: bool) -> None:
    print(f"\n{'='*64}")
    print("SECTION 3: EV Optimal vs Threshold — Explosion & Position ({n} games)".format(n=n_games))
    print(f"{'='*64}")

    pairs = [
        ("EVOptimal", EVOptimalStrategy(coin_rate=0.25)),
        ("Threshold(5)", ThresholdStrategy(white_threshold=5)),
        ("Cautious(25%)", CautiousStrategy(stop_threshold=0.25)),
        ("Cautious(15%)", CautiousStrategy(stop_threshold=0.15)),
    ]

    import random as _random
    dummy_strat = ThresholdStrategy(white_threshold=4)
    print(f"{'Strategy':>18} {'Explode%':>10} {'AvgPos':>8} {'VP/Rnd':>8} {'FinalVP':>9}")
    print("-" * 56)
    for label, strat in pairs:
        target_name = "Target"
        collector = StatsCollector()
        for i in range(n_games):
            p = Player(target_name, strat)
            dummy = Player("Dummy", dummy_strat)
            game = Game([p, dummy], rng=_random.Random(42 + i))
            result = game.run()
            collector.record_result(result)
        recs = [r for r in collector.all_round_records() if r.player_name == target_name]
        expl_rate = sum(r.exploded for r in recs) / len(recs) if recs else 0.0
        avg_pos = sum(r.cauldron_position for r in recs) / len(recs) if recs else 0.0
        avg_vp = sum(r.vp_scored for r in recs) / len(recs) if recs else 0.0
        scores = [g.final_scores.get(target_name, 0) for g in collector._games]
        avg_score = sum(scores) / len(scores) if scores else 0.0
        print(
            f"  {label:>16}  {expl_rate:>9.1%}"
            f"  {avg_pos:>7.1f}"
            f"  {avg_vp:>7.2f}"
            f"  {avg_score:>8.1f}"
        )


def section_stopping_analysis(n_games: int, save_plots: bool) -> None:
    print(f"\n{'='*64}")
    print("SECTION 4: Optimal Stopping — VP vs Cauldron Position ({n} games)".format(n=n_games))
    print(f"{'='*64}")

    import random as _random
    dummy_strat = ThresholdStrategy(white_threshold=4)
    strat = EVOptimalStrategy(coin_rate=0.25)
    target_name = "EVTarget"
    collector = StatsCollector()
    for i in range(n_games):
        p = Player(target_name, strat)
        dummy = Player("Dummy", dummy_strat)
        game = Game([p, dummy], rng=_random.Random(42 + i))
        result = game.run()
        collector.record_result(result)

    print("\nPosition → Avg VP per round (for EVOptimal strategy):")
    print(f"{'Position':>10} {'Avg VP/Rnd':>12} {'N rounds':>10}")
    print("-" * 36)

    from collections import defaultdict
    by_pos: dict[int, list[int]] = defaultdict(list)
    for rs in collector.all_round_records():
        if rs.player_name == target_name:
            by_pos[rs.cauldron_position].append(rs.vp_scored)

    for pos in sorted(by_pos):
        vps = by_pos[pos]
        if len(vps) >= 3:
            print(f"  pos={pos:>3}      {sum(vps)/len(vps):>10.2f}   {len(vps):>8}")


# ---------------------------------------------------------------------------
# Plotting (matplotlib)
# ---------------------------------------------------------------------------

def _ensure_plot_dir() -> str:
    d = os.path.join(os.path.dirname(__file__), "plots")
    os.makedirs(d, exist_ok=True)
    return d


def _plot_win_rates(collector: StatsCollector, filename: str) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("[plots] matplotlib not available, skipping.")
        return

    win_rates = collector.win_rate_by_strategy()
    strategies = list(win_rates.keys())
    rates = [win_rates[s] for s in strategies]

    fig, ax = plt.subplots(figsize=(8, 4))
    bars = ax.bar(strategies, [r * 100 for r in rates], color="steelblue", edgecolor="white")
    ax.axhline(25, color="red", linestyle="--", linewidth=1, label="Random baseline (25%)")
    ax.set_ylabel("Win rate (%)")
    ax.set_title("Strategy Win Rates — 4-Player Head-to-Head")
    ax.legend()
    for bar, rate in zip(bars, rates):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                f"{rate:.1%}", ha="center", va="bottom", fontsize=9)
    plt.tight_layout()
    path = os.path.join(_ensure_plot_dir(), filename)
    fig.savefig(path, dpi=120)
    plt.close(fig)
    print(f"[plots] Saved {path}")


def _plot_explosion_by_round(collector: StatsCollector, filename: str) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return

    rates = collector.explosion_rate_by_round()
    rounds = list(rates.keys())
    vals = [rates[r] * 100 for r in rounds]

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(rounds, vals, marker="o", color="tomato")
    ax.set_xlabel("Round")
    ax.set_ylabel("Explosion rate (%)")
    ax.set_title("Explosion Rate by Round (all strategies, all players)")
    ax.set_xticks(rounds)
    ax.grid(axis="y", alpha=0.4)
    plt.tight_layout()
    path = os.path.join(_ensure_plot_dir(), filename)
    fig.savefig(path, dpi=120)
    plt.close(fig)
    print(f"[plots] Saved {path}")


def _plot_position_dist(collector: StatsCollector, filename: str) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return

    dist = collector.cauldron_position_distribution()
    positions = list(dist.keys())
    counts = list(dist.values())
    total = sum(counts)

    fig, ax = plt.subplots(figsize=(12, 4))
    ax.bar(positions, [c / total * 100 for c in counts], color="mediumseagreen", edgecolor="white")
    ax.set_xlabel("Cauldron position (end of round)")
    ax.set_ylabel("Frequency (%)")
    ax.set_title("Cauldron End-Position Distribution (all strategies)")
    ax.grid(axis="y", alpha=0.4)
    plt.tight_layout()
    path = os.path.join(_ensure_plot_dir(), filename)
    fig.savefig(path, dpi=120)
    plt.close(fig)
    print(f"[plots] Saved {path}")


def _plot_threshold_sweep(results: dict, filename: str) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return

    thresholds = list(results.keys())
    explode = [results[t]["explosion_rate"] * 100 for t in thresholds]
    final_vp = [results[t]["avg_final_score"] for t in thresholds]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))

    ax1.plot(thresholds, explode, marker="o", color="tomato")
    ax1.set_xlabel("White-sum threshold")
    ax1.set_ylabel("Explosion rate (%)")
    ax1.set_title("Explosion Rate vs Threshold")
    ax1.set_xticks(thresholds)
    ax1.grid(alpha=0.4)

    ax2.plot(thresholds, final_vp, marker="s", color="steelblue")
    ax2.set_xlabel("White-sum threshold")
    ax2.set_ylabel("Average final VP")
    ax2.set_title("Final Score vs Threshold (solo)")
    ax2.set_xticks(thresholds)
    ax2.grid(alpha=0.4)

    plt.suptitle("ThresholdStrategy sweep — solo games", fontweight="bold")
    plt.tight_layout()
    path = os.path.join(_ensure_plot_dir(), filename)
    fig.savefig(path, dpi=120)
    plt.close(fig)
    print(f"[plots] Saved {path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Quacks simulation analysis")
    parser.add_argument("--games", type=int, default=500,
                        help="Games per analysis section (default 500)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-plots", action="store_true")
    args = parser.parse_args()

    save_plots = not args.no_plots
    n = args.games

    print(f"Quacks of Quedlinburg — Simulation Analysis")
    print(f"  Games per section : {n}")
    print(f"  Base seed         : {args.seed}")
    print(f"  Plots             : {'enabled' if save_plots else 'disabled'}")

    section_strategy_comparison(n, save_plots)
    section_threshold_sweep(n // 5, save_plots)   # faster solo sweep
    section_ev_analysis(n // 2, save_plots)
    section_stopping_analysis(n // 2, save_plots)

    print(f"\nDone.")


if __name__ == "__main__":
    main()
