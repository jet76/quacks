#!/usr/bin/env python3
"""Simulate a single player and print draw probabilities at every step.

Usage:
    python scripts/simulate.py                   # threshold strategy, random seed
    python scripts/simulate.py --strategy ev     # EV-optimal strategy
    python scripts/simulate.py --seed 42         # reproducible run
    python scripts/simulate.py --strategy mc --seed 7
"""

from __future__ import annotations
import argparse
import random
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from quacks.game import Game, TOTAL_ROUNDS
from quacks.player import Player
from quacks.enums import ChipColor
from quacks.strategies.threshold import ThresholdStrategy
from quacks.strategies.ev_optimal import EVOptimalStrategy
from quacks.strategies.monte_carlo import MonteCarloStrategy
from quacks.strategies.book_aware import BookAwareStrategy
from quacks.strategies.human import _show_bag, _show_pot, _rule


_STRATEGIES: dict[str, object] = {
    "threshold": lambda: ThresholdStrategy(4),
    "ev": EVOptimalStrategy,
    "mc": lambda: MonteCarloStrategy(200),
    "book": lambda: BookAwareStrategy(),
}

_RULE_WIDTH = 58


# ---------------------------------------------------------------------------
# Verbose strategy wrapper
# ---------------------------------------------------------------------------

class _VerboseWrapper:
    """Duck-type wrapper that prints bag probabilities before each pull decision.

    All methods not overridden here are forwarded to the inner strategy via
    __getattr__, so no per-method boilerplate is needed.
    """

    def __init__(self, inner):
        self._inner = inner

    def __getattr__(self, name):
        return getattr(self._inner, name)

    @property
    def name(self) -> str:
        return self._inner.name

    def should_continue_pulling(self, player, state) -> bool:
        if player.cauldron.exploded or player.bag.is_empty:
            return False
        print()
        _show_pot(player)
        _show_bag(player)
        result = self._inner.should_continue_pulling(player, state)
        print(f"  Decision : {'DRAW' if result else 'STOP'}")
        return result


# ---------------------------------------------------------------------------
# Event handler
# ---------------------------------------------------------------------------

def _ability(label: str, detail: str) -> None:
    print(f"     ★ {label}: {detail}")


def _make_handler(player: "Player"):
    player_name = player.name
    ctx = {"round": 0, "draws": 0}

    def handler(ev):
        t = ev["type"]
        pn = ev.get("player", "")

        # ── Round header ────────────────────────────────────────────────
        if t == "round_start":
            ctx["round"] = ev["round"]
            ctx["draws"] = 0
            print(f"\n{'═' * _RULE_WIDTH}")
            print(f"  Round {ev['round']} of {TOTAL_ROUNDS}")
            print(f"{'═' * _RULE_WIDTH}")
            # Player state carried in from the previous round
            droplet = player.cauldron.droplet_position
            flask   = "full" if player.flask_full else "empty"
            rubies  = player.rubies
            vp      = player.scoring_position
            print(f"  VP: {vp}   Droplet: {droplet}   Flask: {flask}"
                  f"   Rubies: {rubies}")

        elif t == "fortune_card":
            print(f"  Fortune  : [{ev['name']}]  {ev['effect']}")

        elif t == "fortune_bonus_ruby" and pn == player_name:
            _ability("Fortune bonus", f"+{ev['magnitude']} ruby")

        elif t == "catchup_coins" and pn == player_name:
            _ability("Catchup", f"+{ev['bonus']} coins (trailing player bonus)")

        elif t == "round6_white_added" and pn == player_name:
            _ability("Round 6 rule", "White(1) added to your bag")

        # ── Chip draw ───────────────────────────────────────────────────
        elif t == "chip_drawn" and pn == player_name:
            ctx["draws"] += 1
            print(f"\n  → Drew {ev['chip']}  (white_sum before: {ev['white_sum_before']})")

        elif t == "flask_used" and pn == player_name:
            _ability("Flask", f"returned {ev['chip_returned']} to bag")

        elif t == "chip_placed" and pn == player_name:
            rubies = (f"  +{len(ev['rubies_hit'])} ruby"
                      if ev.get("rubies_hit") else "")
            print(f"     placed at position {ev['position']}{rubies}")

        # ── Ingredient powers (on-draw) ─────────────────────────────────
        elif t == "yellow_power" and pn == player_name:
            ret = ev.get("returned")
            if ret:
                _ability("Yellow", f"returned {ret} to bag")

        elif t == "blue_power" and pn == player_name:
            placed = ev.get("placed")
            if placed:
                _ability("Blue", f"pulled {placed} from top of bag → placed in pot")

        elif t == "red_power" and pn == player_name:
            _ability("Red", f"+{ev['extra']} extra positions")

        # ── Explosion ───────────────────────────────────────────────────
        elif t == "explosion" and pn == player_name:
            print(f"\n  *** EXPLOSION  position {ev['position']}"
                  f"  white_sum {ev['white_sum']} ***")

        elif t == "explosion_choice_vp" and pn == player_name:
            print(f"  Chose     : +{ev['vp']} VP  (skipped coins)")

        elif t == "explosion_choice_coins" and pn == player_name:
            print(f"  Chose     : +{ev['coins']} coins  (skipped VP)")

        # ── End of pulling ──────────────────────────────────────────────
        elif t == "player_stopped" and pn == player_name:
            print(f"\n  Stopped at position {ev['pos']}"
                  f"  (white_sum {ev['white_sum']})")

        elif t == "pulling_end" and pn == player_name:
            n = ctx["draws"]
            status = "EXPLODED" if ev["exploded"] else "stopped"
            print(f"\n  {_rule('─', 44)}")
            print(f"  Pulled {n} chip{'s' if n != 1 else ''},  "
                  f"{status} at position {ev['position']}")

        # ── Evaluation phase abilities ───────────────────────────────────
        elif t == "green_power" and pn == player_name:
            adv = ev.get("advance", 0)
            vp = ev.get("extra_vp", 0)
            rubies = ev.get("rubies", 0)
            if adv:
                _ability("Green", f"+{adv} position advance"
                         + (f",  +{vp} VP" if vp else ""))
            if rubies:
                _ability("Green", f"+{rubies} {'ruby' if rubies == 1 else 'rubies'}")

        elif t == "purple_upgrade" and pn == player_name:
            _ability("Purple", f"upgraded {ev['upgrade']}")

        elif t == "bonus_die" and pn == player_name:
            _ability("Bonus die", f"rolled {ev['face']}")

        elif t == "droplet_advanced" and pn == player_name:
            _ability("Droplet", f"advanced +{ev['amount']}")

        elif t == "free_chip_taken" and pn == player_name:
            _ability("Fortune free chip", str(ev.get("chip", "")))

        elif t == "winner_free_chip" and pn == player_name:
            _ability("Winner free chip", str(ev.get("chip", "")))

        elif t == "free_upgrade" and pn == player_name:
            _ability("Free upgrade", str(ev.get("upgrade", "")))

        # ── Scoring / purchases ─────────────────────────────────────────
        elif t == "scoring" and pn == player_name:
            print(f"  Score    : +{ev['vp']} VP,  +{ev['coins']} coins")

        elif t == "chip_purchased" and pn == player_name:
            print(f"  Bought   : {ev['chip']}  ({ev['cost']}c)")

        # ── Round and game summary ──────────────────────────────────────
        elif t == "round_complete":
            scores = ev.get("scores", {})
            if scores:
                print(f"\n  Running totals:")
                for name, vp in sorted(scores.items(), key=lambda kv: -kv[1]):
                    marker = " ◀" if name == player_name else ""
                    print(f"    {name:<20} {vp:>4} VP{marker}")

        elif t == "game_over":
            print(f"\n{'═' * _RULE_WIDTH}")
            print(f"  GAME OVER")
            print(f"{'═' * _RULE_WIDTH}")
            scores = ev.get("scores", {})
            winner = ev.get("winner", "")
            for name, vp in sorted(scores.items(), key=lambda kv: -kv[1]):
                marker = "  ◀ winner" if name == winner else ""
                print(f"  {name:<20} {vp:>4} VP{marker}")
            print()

    return handler


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Simulate one player and show draw probabilities at each step"
    )
    ap.add_argument(
        "--strategy",
        choices=list(_STRATEGIES),
        default="threshold",
        help="AI strategy to simulate (default: threshold)",
    )
    ap.add_argument(
        "--seed",
        type=int,
        default=None,
        help="RNG seed for a reproducible run",
    )
    ap.add_argument(
        "--pages",
        nargs="*",
        metavar="COLOR=PAGE",
        default=[],
        help=(
            "Book pages per ingredient color, e.g. --pages green=2 blue=3 red=2  "
            "(valid pages: 1–4; colors: green yellow blue red purple black orange)"
        ),
    )
    args = ap.parse_args()

    # Parse --pages COLOR=N tokens into a ChipColor → int dict
    book_pages: dict[ChipColor, int] = {}
    for token in (args.pages or []):
        try:
            color_str, page_str = token.split("=", 1)
            color = ChipColor(color_str.lower())
            page = int(page_str)
            if color == ChipColor.WHITE:
                ap.error("white book pages cannot be changed")
            if not (1 <= page <= 4):
                ap.error(f"page must be 1–4, got {page!r}")
            book_pages[color] = page
        except ValueError:
            ap.error(
                f"invalid --pages entry {token!r}  "
                f"(expected COLOR=PAGE, e.g. green=2)"
            )

    rng = random.Random(args.seed)
    inner = _STRATEGIES[args.strategy]()
    player = Player("Player", _VerboseWrapper(inner))
    # Ghost opponent keeps the 2-player minimum and activates rat stone/catchup
    ghost = Player("Ghost", ThresholdStrategy(4))

    pages_display = (
        "  ".join(f"{c.value}={p}" for c, p in sorted(book_pages.items(),
                                                        key=lambda kv: kv[0].value))
        or "all defaults (page 1)"
    )
    print(f"\n  Strategy : {inner.name}")
    print(f"  Pages    : {pages_display}")
    print(f"  Seed     : {args.seed if args.seed is not None else '(random)'}")
    print(f"  Rounds   : {TOTAL_ROUNDS}")

    game = Game(
        players=[player, ghost],
        rng=rng,
        book_pages=book_pages or None,
        event_handlers=[_make_handler(player)],
    )
    game.run()


if __name__ == "__main__":
    main()
