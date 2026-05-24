"""Scoring tables for the Quacks of Quedlinburg cauldron board.

Confirmed data points from the rulebook:
  position 15 → 3 VP, 15 coins
  position 19 → 5 VP, 19 coins
  position 23 → 7 VP, 23 coins
  position 33 → 15 VP, 35 coins  (maximum position, bonus coins)

All other values are interpolated. [VERIFY against physical game]
"""

from dataclasses import dataclass
from typing import Optional


MAX_CAULDRON_POSITION = 33

# (position) → (vp, coins, has_ruby)
# Coins = position number; position 33 gives 35 coins (bonus).
# VP values at confirmed positions: 15→3, 19→5, 23→7, 33→15.
_SCORING_DATA: list[tuple[int, int, int, bool]] = [
    #  pos   vp  coins  ruby
    (0,    0,   0,    False),
    (1,    0,   1,    False),
    (2,    0,   2,    False),
    (3,    0,   3,    False),
    (4,    0,   4,    True),   # ruby [VERIFY position]
    (5,    1,   5,    False),
    (6,    1,   6,    False),
    (7,    1,   7,    False),
    (8,    1,   8,    False),
    (9,    2,   9,    True),   # ruby [VERIFY position]
    (10,   2,   10,   False),
    (11,   2,   11,   False),
    (12,   2,   12,   False),
    (13,   3,   13,   False),
    (14,   3,   14,   False),
    (15,   3,   15,   True),   # ruby [VERIFY position]; 3 VP confirmed
    (16,   4,   16,   False),
    (17,   4,   17,   False),
    (18,   4,   18,   False),
    (19,   5,   19,   False),  # 5 VP confirmed
    (20,   5,   20,   True),   # ruby [VERIFY position]
    (21,   6,   21,   False),
    (22,   6,   22,   False),
    (23,   7,   23,   False),  # 7 VP confirmed
    (24,   7,   24,   False),
    (25,   8,   25,   True),   # ruby [VERIFY position]
    (26,   8,   26,   False),
    (27,   9,   27,   False),
    (28,   9,   28,   False),
    (29,   10,  29,   False),
    (30,   10,  30,   False),
    (31,   11,  31,   False),
    (32,   12,  32,   False),
    (33,   15,  35,   True),   # 15 VP / 35 coins confirmed; ruby [VERIFY]
]


@dataclass(frozen=True)
class SpaceReward:
    vp: int
    coins: int
    has_ruby: bool


# Build lookup dict
_TABLE: dict[int, SpaceReward] = {
    pos: SpaceReward(vp, coins, ruby)
    for pos, vp, coins, ruby in _SCORING_DATA
}


def cauldron_reward(position: int) -> SpaceReward:
    """Return the reward for a given cauldron position.

    Positions beyond MAX_CAULDRON_POSITION are capped.
    """
    capped = min(position, MAX_CAULDRON_POSITION)
    return _TABLE[capped]


# Scoring-track ruby positions (main board) [VERIFY exact positions]
# The track has 50 spaces; players can lap it. Rubies on first lap only.
SCORING_TRACK_RUBY_POSITIONS: frozenset[int] = frozenset({10, 20, 30, 40, 50})

# End-of-game ruby conversion: every 2 rubies = 1 VP [VERIFY]
RUBY_VP_DIVISOR = 2


def rubies_to_vp(rubies: int) -> int:
    return rubies // RUBY_VP_DIVISOR


# The scoring track has 50 spaces but supports multiple laps [VERIFY].
# We allow scoring up to 100 to accommodate typical 9-round games (avg ~64 VP).
SCORING_TRACK_MAX = 100
