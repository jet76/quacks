"""Quacks of Quedlinburg — interactive single-player game.

Run from the repo root:
    python scripts/play.py

You play as the human; 1–3 AI opponents fill the remaining seats.
"""

from __future__ import annotations
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from quacks.enums import ChipColor
from quacks.game import Game, TOTAL_ROUNDS
from quacks.player import Player
from quacks.strategies.ev_optimal import EVOptimalStrategy
from quacks.strategies.human import HumanStrategy
from quacks.strategies.monte_carlo import MonteCarloStrategy
from quacks.strategies.threshold import ThresholdStrategy


_DIFFICULTIES: dict[str, object] = {
    "easy":   lambda: ThresholdStrategy(white_threshold=4),
    "medium": lambda: EVOptimalStrategy(),
    "hard":   lambda: MonteCarloStrategy(n_simulations=200),
}

_W = 60


def _rule(char: str = "═") -> str:
    return char * _W


def _banner(text: str) -> None:
    print(f"\n{_rule()}")
    print(f"  {text}")
    print(_rule())


def _ask(prompt: str, options: list[str], default: str) -> str:
    while True:
        raw = input(prompt).strip().lower()
        if not raw:
            return default
        if raw in options:
            return raw
        print(f"  Please enter: {' / '.join(options)}")


# ---------------------------------------------------------------------------
# Event handler — prints round-by-round narration
# ---------------------------------------------------------------------------

def make_event_printer(human_name: str):
    def handler(event: dict) -> None:
        t = event["type"]
        player = event.get("player")

        if t == "game_start":
            _banner("GAME START")

        elif t == "book_pages_set":
            print("\n  Book pages selected:")
            for pname, pages in event["pages"].items():
                overrides = {
                    c.value: p for c, p in pages.items() if p != 1
                }
                label = (
                    ", ".join(f"{c}=pg{p}" for c, p in overrides.items())
                    if overrides else "all page 1"
                )
                marker = " ◄ you" if pname == human_name else ""
                print(f"    {pname:<20} {label}{marker}")

        elif t == "round_start":
            _banner(f"ROUND {event['round']} / {TOTAL_ROUNDS}")

        elif t == "fortune_card":
            print(f"\n  Fortune card : {event['name']}")
            print(f"  Effect       : {event['effect'].replace('_', ' ').lower()}")

        elif t == "droplet_advanced":
            print(f"  {player}: droplet +{event['amount']}")

        # AI pulling — just show start / end
        elif t == "pulling_start" and player != human_name:
            print(f"\n  {player} pulling...", end="", flush=True)

        elif t == "pulling_end" and player != human_name:
            pos = event["position"]
            status = "EXPLODED" if event["exploded"] else f"stopped at {pos}"
            print(f"  {status}  (position {pos})")

        # Human pulling — verbose
        elif t == "pulling_start" and player == human_name:
            _banner(f"Your turn — {human_name}")

        elif t == "chip_drawn" and player == human_name:
            print(f"\n  Drew: {event['chip']}")

        elif t == "flask_used" and player == human_name:
            print(f"  Flask: returned {event['chip_returned']} to bag.")

        elif t == "player_stopped" and player == human_name:
            print(f"\n  You stopped at position {event['pos']}.")

        elif t == "pulling_end" and player == human_name:
            if event["exploded"]:
                print(f"\n  *** POT EXPLODED at position {event['position']} ***")

        elif t == "scoring" and player == human_name:
            print(f"  Scored: +{event['vp']} VP, +{event['coins']} coins")

        elif t == "explosion_choice_vp" and player == human_name:
            print(f"  Explosion: took +{event['vp']} VP")

        elif t == "explosion_choice_coins" and player == human_name:
            print(f"  Explosion: took +{event['coins']} coins")

        elif t == "green_power" and player == human_name:
            adv = event["advance"]
            evp = event.get("extra_vp", 0)
            if adv:
                print(f"  Green power: marker advanced {adv} spaces"
                      + (f", +{evp} VP" if evp else ""))

        elif t == "yellow_power" and player == human_name:
            if event.get("returned"):
                print(f"  Yellow power: returned {event['returned']} to bag.")

        elif t == "blue_power" and player == human_name:
            if event.get("placed"):
                print(f"  Blue power: placed {event['placed']} from bag peek.")

        elif t == "purple_upgrade" and player == human_name:
            print(f"  Purple power: {event['upgrade']}")

        elif t == "bonus_die" and player == human_name:
            face = event["face"].replace("_", " ")
            print(f"\n  Bonus die (furthest marker!): {face}")

        elif t == "bonus_die" and player != human_name:
            print(f"  {player} rolls bonus die: {event['face'].replace('_', ' ')}")

        elif t == "chip_purchased" and player == human_name:
            print(f"  Bought {event['chip']} for {event['cost']}c")

        elif t == "chip_purchased" and player != human_name:
            pass   # don't clutter AI buying

        elif t == "round_complete":
            _banner(f"Round {event['round']} scores")
            scores = sorted(event["scores"].items(), key=lambda x: -x[1])
            for rank, (pname, score) in enumerate(scores, 1):
                marker = " ◄ you" if pname == human_name else ""
                print(f"  {rank}. {pname:<20} {score:>4} VP{marker}")

        elif t == "game_over":
            _banner("GAME OVER — FINAL SCORES")
            scores = sorted(event["scores"].items(), key=lambda x: -x[1])
            for rank, (pname, score) in enumerate(scores, 1):
                marker = " ◄ you" if pname == human_name else ""
                print(f"  {rank}. {pname:<20} {score:>4} VP{marker}")
            winner = event["winner"]
            print()
            if winner == human_name:
                print("  You win!  Excellent brewing.")
            else:
                print(f"  {winner} wins.  Better luck next time!")
            print()

    return handler


# ---------------------------------------------------------------------------
# Setup prompt
# ---------------------------------------------------------------------------

def _setup() -> tuple[str, int, str, int | None]:
    print()
    print(_rule())
    print("  QUACKS OF QUEDLINBURG — Interactive Simulation")
    print(_rule())

    name = input("\n  Your name [default: Player]: ").strip() or "Player"

    n_ai = None
    while n_ai is None:
        raw = input("  AI opponents [1-3, default 1]: ").strip()
        try:
            n_ai = int(raw) if raw else 1
            if not 1 <= n_ai <= 3:
                print("  Enter 1, 2, or 3.")
                n_ai = None
        except ValueError:
            print("  Enter a number.")

    diff = _ask(
        "  Difficulty [easy/medium/hard, default medium]: ",
        list(_DIFFICULTIES), default="medium",
    )

    seed_raw = input("  Seed for RNG (blank = random): ").strip()
    seed = int(seed_raw) if seed_raw.isdigit() else None

    return name, n_ai, diff, seed


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    name, n_ai, difficulty, seed = _setup()

    rng = random.Random(seed)
    human = Player(name, HumanStrategy())
    ai_players = [
        Player(f"AI-{i + 1}", _DIFFICULTIES[difficulty]())
        for i in range(n_ai)
    ]

    game = Game(
        [human] + ai_players,
        rng=rng,
        event_handlers=[make_event_printer(human_name=name)],
    )
    game.run()


if __name__ == "__main__":
    main()
