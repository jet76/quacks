"""Enumerations for the Quacks of Quedlinburg simulation."""

from enum import Enum, auto


class ChipColor(Enum):
    WHITE = "white"       # Cherry Bombs — explosion counter
    ORANGE = "orange"     # Pumpkin — filler, boosts Red
    GREEN = "green"       # Garden Spider — ruby / position bonus
    BLUE = "blue"         # Crow Skull — peek and choose
    RED = "red"           # Toadstool — advances extra with orange
    YELLOW = "yellow"     # Mandrake Root — returns white chip
    PURPLE = "purple"     # Raven's Feather — chip upgrades
    BLACK = "black"       # Crow's Eye — peek at bag


class GamePhase(Enum):
    SETUP = auto()
    FORTUNE_TELLER = auto()
    PULLING = auto()
    EVALUATION_A = auto()   # Scoring / VP advancement
    EVALUATION_B = auto()   # Special ingredient effects
    EVALUATION_C = auto()   # Rat stones / catch-up
    EVALUATION_D = auto()   # Buying phase
    EVALUATION_E = auto()   # Ruby spending, reset
    GAME_OVER = auto()


class FortuneCardType(Enum):
    IMMEDIATE = "immediate"   # One-time effect at card reveal
    ROUND_LONG = "round_long" # Effect persists through the round


class BonusDieFace(Enum):
    RUBY = "ruby"
    DROPLET = "droplet"
    ORANGE_CHIP = "orange_chip"


class IngredientBookPage(Enum):
    PAGE_1 = 1
    PAGE_2 = 2
    PAGE_3 = 3
    PAGE_4 = 4


class ExplosionChoice(Enum):
    VP = "vp"
    COINS = "coins"
