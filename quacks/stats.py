"""Statistical analysis engine for Quacks of Quedlinburg simulations.

Collects per-round and per-game data and computes rich statistics for
understanding game balance, strategy performance, and probability distributions.
"""

from __future__ import annotations
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Optional

from quacks.enums import ChipColor, ExplosionChoice
from quacks.player import Player, RoundRecord
from quacks.game import GameResult


# ---------------------------------------------------------------------------
# Per-round snapshot
# ---------------------------------------------------------------------------

@dataclass
class RoundStats:
    round_number: int
    player_name: str
    strategy: str
    cauldron_position: int
    white_sum: int
    exploded: bool
    explosion_choice: Optional[ExplosionChoice]
    vp_scored: int
    coins_earned: int
    scoring_pos_before: int
    scoring_pos_after: int
    rubies_earned: int
    rubies_spent: int
    rat_advance: int
    flask_used: bool
    droplet_advanced: bool
    chips_drawn: list[str]
    chips_purchased: list[str]
    stopped_voluntarily: bool
    green_advance: int
    fortune_card_id: int


# ---------------------------------------------------------------------------
# Full game record
# ---------------------------------------------------------------------------

@dataclass
class GameRecord:
    game_id: int
    n_players: int
    winner: str
    final_scores: dict[str, int]
    round_records: list[RoundStats] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Statistics collector
# ---------------------------------------------------------------------------

class StatsCollector:
    """Accumulates data across many game simulations and computes aggregate stats.

    Usage:
        collector = StatsCollector()
        game = Game(players, event_handlers=[collector.handle_event])
        result = game.run()
        collector.record_result(result)
        print(collector.summary())
    """

    def __init__(self) -> None:
        self._games: list[GameRecord] = []
        self._current_game_id: int = 0
        self._event_log: list[dict] = []

    # ------------------------------------------------------------------
    # Event collection
    # ------------------------------------------------------------------

    def handle_event(self, event: dict) -> None:
        self._event_log.append(event)

    # ------------------------------------------------------------------
    # Recording results
    # ------------------------------------------------------------------

    def record_result(self, result: GameResult, game_id: int | None = None) -> None:
        if game_id is None:
            self._current_game_id += 1
            game_id = self._current_game_id

        round_stats: list[RoundStats] = []
        for player in result.players:
            for rec in player.history:
                round_stats.append(RoundStats(
                    round_number=rec.round_number,
                    player_name=player.name,
                    strategy=player.strategy.name,
                    cauldron_position=rec.cauldron_position,
                    white_sum=player.cauldron.white_sum,
                    exploded=rec.exploded,
                    explosion_choice=rec.explosion_choice,
                    vp_scored=rec.vp_scored,
                    coins_earned=rec.coins_earned,
                    scoring_pos_before=rec.scoring_position_before,
                    scoring_pos_after=rec.scoring_position_after,
                    rubies_earned=rec.rubies_earned,
                    rubies_spent=rec.rubies_spent,
                    rat_advance=rec.rat_stone_advance,
                    flask_used=rec.flask_used,
                    droplet_advanced=rec.droplet_advanced,
                    chips_drawn=[str(c) for c in rec.chips_drawn],
                    chips_purchased=[str(c) for c in rec.chips_purchased],
                    stopped_voluntarily=rec.stopped_voluntarily,
                    green_advance=rec.green_advance,
                    fortune_card_id=rec.fortune_card_id,
                ))

        self._games.append(GameRecord(
            game_id=game_id,
            n_players=len(result.players),
            winner=result.winner_name,
            final_scores=result.final_scores,
            round_records=round_stats,
        ))

    # ------------------------------------------------------------------
    # Aggregate queries
    # ------------------------------------------------------------------

    @property
    def n_games(self) -> int:
        return len(self._games)

    def all_round_records(self) -> list[RoundStats]:
        return [rs for g in self._games for rs in g.round_records]

    # --- Explosion ---

    def explosion_rate(self, strategy: str | None = None) -> float:
        """Fraction of rounds that ended in an explosion."""
        records = self.all_round_records()
        if strategy:
            records = [r for r in records if r.strategy == strategy]
        if not records:
            return 0.0
        return sum(1 for r in records if r.exploded) / len(records)

    def explosion_rate_by_round(self) -> dict[int, float]:
        """Explosion rate for each round number (1–9)."""
        by_round: dict[int, list[bool]] = defaultdict(list)
        for rs in self.all_round_records():
            by_round[rs.round_number].append(rs.exploded)
        return {rnd: sum(vals) / len(vals) for rnd, vals in sorted(by_round.items())}

    # --- Cauldron position ---

    def avg_cauldron_position(self, strategy: str | None = None) -> float:
        records = self.all_round_records()
        if strategy:
            records = [r for r in records if r.strategy == strategy]
        if not records:
            return 0.0
        return sum(r.cauldron_position for r in records) / len(records)

    def cauldron_position_distribution(self) -> dict[int, int]:
        """Counts of each cauldron end-position across all rounds."""
        counter: Counter[int] = Counter()
        for rs in self.all_round_records():
            counter[rs.cauldron_position] += 1
        return dict(sorted(counter.items()))

    # --- VP ---

    def avg_vp_per_round(self, strategy: str | None = None) -> float:
        records = self.all_round_records()
        if strategy:
            records = [r for r in records if r.strategy == strategy]
        if not records:
            return 0.0
        return sum(r.vp_scored for r in records) / len(records)

    def avg_final_score(self, strategy: str | None = None) -> float:
        scores: list[int] = []
        for g in self._games:
            for name, vp in g.final_scores.items():
                player_strategy = self._strategy_for(g, name)
                if strategy is None or player_strategy == strategy:
                    scores.append(vp)
        return sum(scores) / len(scores) if scores else 0.0

    def _strategy_for(self, game: GameRecord, player_name: str) -> str:
        for rs in game.round_records:
            if rs.player_name == player_name:
                return rs.strategy
        return "unknown"

    # --- Win rates ---

    def win_rate_by_strategy(self) -> dict[str, float]:
        """Fraction of games won by each strategy."""
        total_by_strat: Counter[str] = Counter()
        wins_by_strat: Counter[str] = Counter()
        for g in self._games:
            for name, _ in g.final_scores.items():
                strat = self._strategy_for(g, name)
                total_by_strat[strat] += 1
                if name == g.winner:
                    wins_by_strat[strat] += 1
        return {
            strat: wins_by_strat[strat] / total_by_strat[strat]
            for strat in total_by_strat
        }

    # --- Buying patterns ---

    def purchase_frequency(self) -> dict[str, int]:
        """Count of each chip type purchased across all games."""
        counter: Counter[str] = Counter()
        for rs in self.all_round_records():
            for chip in rs.chips_purchased:
                counter[chip] += 1
        return dict(counter.most_common())

    def avg_coins_per_round(self, strategy: str | None = None) -> float:
        records = self.all_round_records()
        if strategy:
            records = [r for r in records if r.strategy == strategy]
        if not records:
            return 0.0
        return sum(r.coins_earned for r in records) / len(records)

    # --- Flask and ruby ---

    def flask_usage_rate(self) -> float:
        records = self.all_round_records()
        if not records:
            return 0.0
        return sum(1 for r in records if r.flask_used) / len(records)

    def avg_rubies_per_round(self) -> float:
        records = self.all_round_records()
        if not records:
            return 0.0
        return sum(r.rubies_earned for r in records) / len(records)

    # --- White chip analysis ---

    def avg_white_sum_at_stop(self, strategy: str | None = None) -> float:
        """Average white chip sum when pulling stopped (or explosion)."""
        records = self.all_round_records()
        if strategy:
            records = [r for r in records if r.strategy == strategy]
        if not records:
            return 0.0
        return sum(r.white_sum for r in records) / len(records)

    # --- Optimal stopping analysis ---

    def stopping_vp_correlation(self) -> list[tuple[int, float]]:
        """For each cauldron stop position, average VP earned that round.

        Helps identify optimal target positions.
        """
        by_pos: dict[int, list[int]] = defaultdict(list)
        for rs in self.all_round_records():
            by_pos[rs.cauldron_position].append(rs.vp_scored)
        return [(pos, sum(vps) / len(vps)) for pos, vps in sorted(by_pos.items())]

    # --- Probability analysis ---

    def explosion_probability_at_white_sum(self, white_sum: int) -> float:
        """Observed fraction of rounds that exploded when white_sum was at given level.

        [Note: true probability depends on bag composition, not just white_sum.]
        """
        total = 0
        exploded = 0
        for rs in self.all_round_records():
            if rs.white_sum >= white_sum:
                total += 1
                if rs.exploded:
                    exploded += 1
        return exploded / total if total else 0.0

    # --- Catch-up mechanic analysis ---

    def avg_rat_advance_by_position_gap(self) -> dict[int, float]:
        """Average rat advance for players N spots behind leader."""
        by_gap: dict[int, list[int]] = defaultdict(list)
        for rs in self.all_round_records():
            by_gap[rs.rat_advance].append(rs.cauldron_position)
        return {gap: sum(v) / len(v) for gap, v in sorted(by_gap.items())}

    # --- Summary report ---

    def summary(self) -> str:
        if not self._games:
            return "No games recorded."

        lines = [
            f"{'='*60}",
            f"QUACKS SIMULATION SUMMARY ({self.n_games} games)",
            f"{'='*60}",
            f"",
            f"EXPLOSION RATES:",
            f"  Overall: {self.explosion_rate():.1%}",
        ]
        for rnd, rate in self.explosion_rate_by_round().items():
            lines.append(f"  Round {rnd}: {rate:.1%}")

        lines += [
            f"",
            f"CAULDRON POSITION:",
            f"  Avg position: {self.avg_cauldron_position():.1f}",
        ]

        lines += [
            f"",
            f"SCORING:",
            f"  Avg VP/round: {self.avg_vp_per_round():.2f}",
            f"  Avg coins/round: {self.avg_coins_per_round():.1f}",
            f"  Avg rubies/round: {self.avg_rubies_per_round():.2f}",
        ]

        lines += [
            f"",
            f"WIN RATES BY STRATEGY:",
        ]
        for strat, rate in sorted(self.win_rate_by_strategy().items(), key=lambda x: -x[1]):
            lines.append(f"  {strat}: {rate:.1%}")

        lines += [
            f"",
            f"AVG FINAL SCORE BY STRATEGY:",
        ]
        strategies = {rs.strategy for rs in self.all_round_records()}
        for strat in sorted(strategies):
            lines.append(f"  {strat}: {self.avg_final_score(strat):.1f} VP")

        lines += [
            f"",
            f"FLASK USAGE RATE: {self.flask_usage_rate():.1%}",
            f"",
            f"TOP PURCHASED CHIPS:",
        ]
        for chip, count in list(self.purchase_frequency().items())[:10]:
            lines.append(f"  {chip}: {count}×")

        lines.append(f"{'='*60}")
        return "\n".join(lines)

    def to_dataframes(self):
        """Return (rounds_df, games_df) as pandas DataFrames for further analysis.

        Requires pandas to be installed.
        """
        import pandas as pd

        rounds_data = []
        for rs in self.all_round_records():
            rounds_data.append({
                "round": rs.round_number,
                "player": rs.player_name,
                "strategy": rs.strategy,
                "cauldron_pos": rs.cauldron_position,
                "white_sum": rs.white_sum,
                "exploded": rs.exploded,
                "explosion_choice": rs.explosion_choice.value if rs.explosion_choice else None,
                "vp_scored": rs.vp_scored,
                "coins_earned": rs.coins_earned,
                "scoring_before": rs.scoring_pos_before,
                "scoring_after": rs.scoring_pos_after,
                "rubies_earned": rs.rubies_earned,
                "rubies_spent": rs.rubies_spent,
                "rat_advance": rs.rat_advance,
                "flask_used": rs.flask_used,
                "droplet_advanced": rs.droplet_advanced,
                "n_chips_drawn": len(rs.chips_drawn),
                "n_purchased": len(rs.chips_purchased),
                "stopped_voluntarily": rs.stopped_voluntarily,
                "green_advance": rs.green_advance,
                "fortune_card": rs.fortune_card_id,
            })

        games_data = []
        for g in self._games:
            games_data.append({
                "game_id": g.game_id,
                "n_players": g.n_players,
                "winner": g.winner,
                **{f"score_{name}": vp for name, vp in g.final_scores.items()},
            })

        return pd.DataFrame(rounds_data), pd.DataFrame(games_data)
