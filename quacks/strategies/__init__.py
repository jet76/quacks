"""Player strategies for the Quacks of Quedlinburg simulation.

A strategy encapsulates all decisions a player makes during the game:
- Whether to continue drawing chips or stop
- Which chip to buy (and how many)
- Whether to use the flask
- Whether to exercise Yellow / Blue / Purple powers
- Whether to spend rubies on droplet vs. flask
"""

from quacks.strategies.base import PlayerStrategy
from quacks.strategies.threshold import ThresholdStrategy
from quacks.strategies.greedy import GreedyBuyerStrategy
from quacks.strategies.cautious import CautiousStrategy
from quacks.strategies.aggressive import AggressiveStrategy

__all__ = [
    "PlayerStrategy",
    "ThresholdStrategy",
    "GreedyBuyerStrategy",
    "CautiousStrategy",
    "AggressiveStrategy",
]
