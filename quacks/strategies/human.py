"""Interactive human player strategy.

Prints game state and prompts for input at every decision point.
Works with the standard PlayerStrategy interface so it slots into
any Game(...) call like any other strategy.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Optional

from quacks.enums import ChipColor, ExplosionChoice
from quacks.strategies.base import PlayerStrategy

if TYPE_CHECKING:
    from quacks.chips import Chip
    from quacks.game import GameState
    from quacks.player import Player


# ---------------------------------------------------------------------------
# Low-level input helpers
# ---------------------------------------------------------------------------

def _ask(prompt: str, options: list[str], default: str) -> str:
    """Prompt until the user enters one of options; return default on blank."""
    while True:
        raw = input(prompt).strip().lower()
        if not raw:
            return default
        if raw in options:
            return raw
        print(f"    Please enter: {' / '.join(options)}")


def _ask_int(prompt: str, lo: int, hi: int, default: int) -> int:
    """Prompt until the user enters an integer in [lo, hi]."""
    while True:
        raw = input(prompt).strip()
        if not raw:
            return default
        try:
            val = int(raw)
            if lo <= val <= hi:
                return val
        except ValueError:
            pass
        print(f"    Enter a number between {lo} and {hi}.")


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def _rule(char: str = "─", width: int = 58) -> str:
    return char * width


def _show_pot(player: "Player") -> None:
    cauldron = player.cauldron
    reward = cauldron.reward
    chips = cauldron.chips_in_pot
    budget = cauldron.white_budget_remaining()

    print(f"  Position : {cauldron.position}"
          f"  →  VP {reward.vp}, Coins {reward.coins}")
    print(f"  White sum: {cauldron.white_sum}/7"
          f"  (budget: {budget} remaining)")

    if chips:
        from collections import Counter
        cts = Counter(str(c) for c in chips)
        line = ", ".join(f"{c}×{n}" if n > 1 else c for c, n in cts.items())
        print(f"  Pot      : {line}")
    else:
        print(f"  Pot      : (empty)")


def _show_bag(player: "Player") -> None:
    from collections import Counter
    chips = player.bag.all_chips()
    if not chips:
        print("  Bag      : (empty)")
        return
    budget = player.cauldron.white_budget_remaining()
    cts = Counter(str(c) for c in chips)
    summary = ", ".join(f"{c}×{n}" if n > 1 else c for c, n in sorted(cts.items()))
    danger = sum(
        1 for c in chips
        if c.color == ChipColor.WHITE and c.value > budget
    )
    risk = f"  [{danger}/{len(chips)} dangerous]" if danger else ""
    print(f"  Bag ({len(chips):2d})  : {summary}{risk}")


# ---------------------------------------------------------------------------
# HumanStrategy
# ---------------------------------------------------------------------------

class HumanStrategy(PlayerStrategy):
    """Prompts the human player for every in-game decision."""

    @property
    def name(self) -> str:
        return "Human"

    # ------------------------------------------------------------------
    # Pre-game
    # ------------------------------------------------------------------

    def choose_book_pages(
        self, player: "Player", state: "GameState"
    ) -> dict[ChipColor, int]:
        print(f"\n{_rule()}")
        print("  Ingredient Book Pages")
        print(_rule())
        print("  Choose page 1–4 for each ingredient (Enter = page 1).\n")

        pages: dict[ChipColor, int] = {}
        for color in ChipColor:
            if color == ChipColor.WHITE:
                continue
            page = _ask_int(
                f"    {color.value.capitalize():<10} [1-4, default 1]: ",
                lo=1, hi=4, default=1,
            )
            if page != 1:
                pages[color] = page
        return pages

    # ------------------------------------------------------------------
    # Pulling phase
    # ------------------------------------------------------------------

    def should_continue_pulling(
        self, player: "Player", state: "GameState"
    ) -> bool:
        if player.cauldron.exploded or player.bag.is_empty:
            return False
        print()
        _show_pot(player)
        _show_bag(player)
        flask = player.flask_full and not state.flask_disabled
        suffix = "  (flask ready)" if flask else ""
        ans = _ask(f"  Draw another chip?{suffix} [y/n, default n]: ",
                   ["y", "n"], default="n")
        return ans == "y"

    def use_flask(
        self, player: "Player", state: "GameState", chip: "Chip"
    ) -> bool:
        new_ws = player.cauldron.white_sum + (
            chip.value if chip.color == ChipColor.WHITE else 0
        )
        print(f"\n  Drew: {chip}  (white sum would become {new_ws}/7)")
        ans = _ask(
            f"  Use flask to return {chip} to bag? [y/n, default n]: ",
            ["y", "n"], default="n",
        )
        return ans == "y"

    # ------------------------------------------------------------------
    # Explosion outcome
    # ------------------------------------------------------------------

    def choose_explosion_outcome(
        self, player: "Player", state: "GameState"
    ) -> ExplosionChoice:
        reward = player.cauldron.reward
        print(f"\n  *** POT EXPLODED at position {player.cauldron.position} ***")
        print(f"  Choose: VP {reward.vp}  OR  Coins {reward.coins}  (not both)")
        ans = _ask("  Take [vp/coins, default vp]: ", ["vp", "coins"], default="vp")
        return ExplosionChoice.VP if ans == "vp" else ExplosionChoice.COINS

    # ------------------------------------------------------------------
    # Buying phase
    # ------------------------------------------------------------------

    def choose_purchases(
        self, player: "Player", state: "GameState", coins: int
    ) -> list["Chip"]:
        print(f"\n{_rule()}")
        print(f"  Buying Phase  —  Coins: {coins}")
        print(_rule())

        available = state.market.available_chips(state.round_number)
        in_stock = [l for l in available if l.stock > 0]

        if not in_stock:
            print("  Market is empty.")
            return []

        print(f"  {'#':>3}  {'Chip':<14}  Cost  Stock")
        print(f"  {_rule('─', 36)}")
        for i, lst in enumerate(in_stock, 1):
            mark = "✓" if lst.cost <= coins else " "
            print(f"  {i:>3}. {str(lst.chip):<14}  {lst.cost:>3}c  {lst.stock:>4}  {mark}")

        print()
        purchases: list["Chip"] = []
        remaining = coins
        virtual = {(l.chip.color, l.chip.value): l.stock for l in in_stock}
        chip_by_idx = {i: l for i, l in enumerate(in_stock, 1)}

        while remaining > 0:
            raw = input(f"  Buy # (budget {remaining}c, Enter to finish): ").strip()
            if not raw:
                break
            for token in raw.split():
                try:
                    idx = int(token)
                except ValueError:
                    print(f"    '{token}': enter a number from the list.")
                    continue
                if idx not in chip_by_idx:
                    print(f"    {idx}: not in list.")
                    continue
                lst = chip_by_idx[idx]
                key = (lst.chip.color, lst.chip.value)
                if lst.cost > remaining:
                    print(f"    Can't afford {lst.chip} ({lst.cost}c, have {remaining}c).")
                    continue
                if virtual.get(key, 0) <= 0:
                    print(f"    {lst.chip} out of stock.")
                    continue
                purchases.append(lst.chip)
                remaining -= lst.cost
                virtual[key] -= 1
                print(f"    + {lst.chip} ({lst.cost}c).  Budget left: {remaining}c.")

        return purchases

    # ------------------------------------------------------------------
    # Ruby spending
    # ------------------------------------------------------------------

    def choose_ruby_spending(
        self, player: "Player", state: "GameState"
    ) -> tuple[int, bool]:
        rubies = player.rubies
        print(f"\n  Rubies: {rubies}  |  "
              f"Droplet: {player.cauldron.droplet_position}  |  "
              f"Flask: {'full' if player.flask_full else 'empty (2 rubies to refill)'}")

        if rubies < 2:
            print("  (fewer than 2 rubies — nothing to spend)")
            return 0, False

        remaining = rubies
        refill = False
        advances = 0

        if not player.flask_full and remaining >= 2:
            ans = _ask("  Refill flask (2 rubies)? [y/n, default n]: ",
                       ["y", "n"], default="n")
            if ans == "y":
                refill = True
                remaining -= 2

        while remaining >= 2:
            ans = _ask(
                f"  Advance droplet (2 rubies, {remaining} left)? [y/n, default n]: ",
                ["y", "n"], default="n",
            )
            if ans == "y":
                advances += 1
                remaining -= 2
            else:
                break

        return advances, refill

    # ------------------------------------------------------------------
    # Ingredient powers
    # ------------------------------------------------------------------

    def use_yellow_power(
        self, player: "Player", state: "GameState", white_chip: "Chip"
    ) -> bool:
        ans = _ask(
            f"  Yellow: return {white_chip} to bag? [y/n, default y]: ",
            ["y", "n"], default="y",
        )
        return ans == "y"

    def choose_white_to_return(
        self,
        player: "Player",
        state: "GameState",
        whites: list["Chip"],
    ) -> Optional["Chip"]:
        print("  Yellow: choose a white chip from the pot to return:")
        for i, c in enumerate(whites, 1):
            print(f"    {i}. {c}")
        idx = _ask_int("  Number (0 to skip): ", lo=0, hi=len(whites), default=0)
        return whites[idx - 1] if idx else None

    def choose_chip_to_return(
        self,
        player: "Player",
        state: "GameState",
        chips: list["Chip"],
    ) -> Optional["Chip"]:
        unique = list(dict.fromkeys(chips))
        print("  Yellow: choose any chip from the pot to return:")
        for i, c in enumerate(unique, 1):
            print(f"    {i}. {c}")
        idx = _ask_int("  Number (0 to skip): ", lo=0, hi=len(unique), default=0)
        return unique[idx - 1] if idx else None

    def choose_chips_to_return(
        self,
        player: "Player",
        state: "GameState",
        chips: list["Chip"],
        max_n: int,
    ) -> list["Chip"]:
        unique = list(dict.fromkeys(chips))
        print(f"  Yellow: choose up to {max_n} chips from the pot to return:")
        for i, c in enumerate(unique, 1):
            print(f"    {i}. {c}")
        chosen: list["Chip"] = []
        for n in range(max_n):
            remaining = [c for c in unique if c not in chosen]
            if not remaining:
                break
            idx = _ask_int(
                f"  Chip {n + 1} of {max_n} (0 to stop): ",
                lo=0, hi=len(unique), default=0,
            )
            if not idx:
                break
            chosen.append(unique[idx - 1])
        return chosen

    def choose_blue_chip(
        self,
        player: "Player",
        state: "GameState",
        peeked: list["Chip"],
    ) -> Optional["Chip"]:
        if not peeked:
            return None
        print("  Blue: peeked chips from bag top:")
        for i, c in enumerate(peeked, 1):
            print(f"    {i}. {c}")
        idx = _ask_int(
            "  Place which? (0 = return all to bag): ",
            lo=0, hi=len(peeked), default=0,
        )
        return peeked[idx - 1] if idx else None

    def choose_purple_upgrade(
        self,
        player: "Player",
        state: "GameState",
        options: list[tuple["Chip", "Chip"]],
    ) -> Optional[tuple["Chip", "Chip"]]:
        print("  Purple: available upgrades:")
        for i, (src, dst) in enumerate(options, 1):
            print(f"    {i}. {src} → {dst}")
        idx = _ask_int(
            "  Upgrade which? (0 to skip): ",
            lo=0, hi=len(options), default=0,
        )
        return options[idx - 1] if idx else None

    def choose_free_chip(
        self,
        player: "Player",
        state: "GameState",
        available: list["Chip"],
    ) -> Optional["Chip"]:
        if not available:
            return None
        unique = list(dict.fromkeys(available))
        print("  Fortune card: choose a free chip:")
        for i, c in enumerate(unique, 1):
            print(f"    {i}. {c}")
        idx = _ask_int(
            "  Choose (0 to skip): ",
            lo=0, hi=len(unique), default=0,
        )
        return unique[idx - 1] if idx else None

    def choose_chip_to_remove(
        self,
        player: "Player",
        state: "GameState",
        peeked: list["Chip"],
    ) -> Optional["Chip"]:
        if not peeked:
            return None
        print("  Black: peeked chips — may permanently remove one from bag:")
        for i, c in enumerate(peeked, 1):
            print(f"    {i}. {c}")
        idx = _ask_int(
            "  Remove which? (0 to skip): ",
            lo=0, hi=len(peeked), default=0,
        )
        return peeked[idx - 1] if idx else None
