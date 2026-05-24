"""CLI entry point: run a simulation and print results."""

from __future__ import annotations
import argparse
import sys

from quacks.simulation import run_batch, all_vs_all, threshold_sweep
from quacks.strategies.threshold import ThresholdStrategy
from quacks.strategies.aggressive import AggressiveStrategy
from quacks.strategies.cautious import CautiousStrategy
from quacks.strategies.greedy import GreedyBuyerStrategy


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Quacks of Quedlinburg simulation engine"
    )
    sub = parser.add_subparsers(dest="command")

    # quacks run
    run_p = sub.add_parser("run", help="Run a single multi-player game")
    run_p.add_argument("--players", type=int, default=4, choices=[2, 3, 4])
    run_p.add_argument("--seed", type=int, default=42)

    # quacks batch
    batch_p = sub.add_parser("batch", help="Run a batch simulation")
    batch_p.add_argument("--n", type=int, default=1000, help="Number of games")
    batch_p.add_argument("--seed", type=int, default=42)
    batch_p.add_argument(
        "--mode", choices=["all_vs_all", "threshold_sweep"], default="all_vs_all"
    )

    args = parser.parse_args()

    if args.command == "run":
        from quacks.simulation import run_game
        from quacks.strategies.threshold import ThresholdStrategy
        strategies = [
            ThresholdStrategy(5),
            CautiousStrategy(0.25),
            GreedyBuyerStrategy(6),
            AggressiveStrategy(),
        ][: args.players]
        result, _ = run_game(strategies, collect_stats=False)
        print("\n" + "=" * 50)
        print("GAME RESULT")
        print("=" * 50)
        for rank, (name, vp) in enumerate(result.standings(), 1):
            marker = " ← WINNER" if name == result.winner_name else ""
            print(f"  {rank}. {name}: {vp} VP{marker}")

    elif args.command == "batch":
        if args.mode == "all_vs_all":
            collector = all_vs_all(n_games=args.n, seed=args.seed)
        else:
            threshold_sweep([3, 4, 5, 6, 7], n_games=args.n // 10, seed=args.seed)
            return
        print()
        print(collector.summary())

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
