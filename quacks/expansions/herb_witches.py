"""The Herb Witches expansion stub.

[VERIFY all values against the physical expansion box]

Adds:
  - Witch's Tooth chips (CYAN): advance the droplet and grant rubies
  - Bone chips (GRAY): reduce white chip sum in pot
  - 8 new Fortune Teller cards (total deck grows to 32; 9 still drawn per game)
  - Herb Witches ingredient book pages for the new colors

Reference: BGG expansion page + community rules summaries.
All magnitudes and costs are approximations — mark [VERIFY].
"""

from __future__ import annotations
from quacks.chips import Chip
from quacks.enums import ChipColor
from quacks.expansions import Expansion
from quacks.fortune_teller import FortuneCard, FortuneEffect


# ---------------------------------------------------------------------------
# New chips
# ---------------------------------------------------------------------------

CYAN_1 = Chip(ChipColor.CYAN, 1)
CYAN_2 = Chip(ChipColor.CYAN, 2)
CYAN_3 = Chip(ChipColor.CYAN, 3)
CYAN_4 = Chip(ChipColor.CYAN, 4)

GRAY_1 = Chip(ChipColor.GRAY, 1)
GRAY_2 = Chip(ChipColor.GRAY, 2)
GRAY_3 = Chip(ChipColor.GRAY, 3)


# ---------------------------------------------------------------------------
# Market costs [VERIFY]
# ---------------------------------------------------------------------------

_CYAN_MARKET: list[tuple[Chip, int]] = [
    (CYAN_1, 3),
    (CYAN_2, 6),
    (CYAN_3, 9),
    (CYAN_4, 14),
]

_GRAY_MARKET: list[tuple[Chip, int]] = [
    (GRAY_1, 2),
    (GRAY_2, 4),
    (GRAY_3, 7),
]


# ---------------------------------------------------------------------------
# Extra fortune teller cards (ids 25–32) [VERIFY]
# ---------------------------------------------------------------------------

_EXTRA_FORTUNE_CARDS: list[FortuneCard] = [
    FortuneCard(25, "Witch's Favour",
                FortuneEffect.BONUS_RUBY,
                "All players receive 1 ruby and advance their droplet 1 space.", 1),
    FortuneCard(26, "Bone Broth",
                FortuneEffect.STOP_BONUS_VP,
                "Players who stop voluntarily score +1 bonus VP per bone chip in pot.", 1),
    FortuneCard(27, "Bitter Herb",
                FortuneEffect.DROPLET_ADVANCE,
                "All players advance their droplet 1 space forward.", 1),
    FortuneCard(28, "Cursed Brew",
                FortuneEffect.EXPLODE_RUBY,
                "Exploded players receive 1 ruby and may draw 1 free chip.", 1),
    FortuneCard(29, "Herb Garden",
                FortuneEffect.FREE_CHIP_FROM_SUPPLY,
                "Each player may take 1 cyan or gray chip from supply free.", 1),
    FortuneCard(30, "Tincture",
                FortuneEffect.FLASK_FREE_REFILL,
                "All players treat their flask as refilled for free this round.", 1),
    FortuneCard(31, "Potion of Foresight",
                FortuneEffect.LOOK_AT_BAG_TOP,
                "Each player may look at the top 4 chips of their bag.", 4),
    FortuneCard(32, "Moon Phase",
                FortuneEffect.VP_MULTIPLIER,
                "All VP scored from the cauldron this round is multiplied by 1.5 "
                "(round down).", 2),
]


# ---------------------------------------------------------------------------
# Expansion object
# ---------------------------------------------------------------------------

HERB_WITCHES: Expansion = Expansion(
    name="The Herb Witches",
    new_chips=_CYAN_MARKET + _GRAY_MARKET,
    extra_fortune_cards=_EXTRA_FORTUNE_CARDS,
    starting_bag_extras=[],    # base game starting bag unchanged [VERIFY]
    book_page_overrides={},    # expansion adds new color pages, not overrides
    extra_market_stock={},
)
