from __future__ import annotations

from pydantic import BaseModel, Field


class Unit(BaseModel):
    name: str
    star: int = 1
    items: list[str] = Field(default_factory=list)

    def describe(self) -> str:
        star = f"{self.star}* " if self.star > 1 else ""
        items = f" [{', '.join(self.items)}]" if self.items else ""
        return f"{star}{self.name}{items}"


class Opponent(BaseModel):
    """A rival player's board, as far as GEP exposes it."""

    name: str = ""
    units: list[Unit] = Field(default_factory=list)
    health: int | None = None
    xp: int | None = None
    last_result: str = ""  # victory | defeat from the previous round

    def describe(self) -> str:
        stats = []
        if self.health is not None:
            stats.append(f"{self.health}hp")
        if self.xp is not None:
            stats.append(f"lvl{self.xp}")
        if self.last_result:
            stats.append(self.last_result)
        meta = f" ({', '.join(stats)})" if stats else ""
        board = ", ".join(u.describe() for u in self.units)
        return f"{self.name}{meta}: {board}" if board else f"{self.name}{meta}"


class GameState(BaseModel):
    """Point-in-time snapshot of a TFT game, assembled by the Overwolf listener."""

    stage: str = ""  # e.g. "3-2"
    round_type: str = ""  # pve / pvp / carousel / augment
    level: int = 0
    gold: int = 0
    hp: int = 100
    streak: int = 0  # +n wins / -n losses
    board: list[Unit] = Field(default_factory=list)
    bench: list[Unit] = Field(default_factory=list)
    shop: list[str] = Field(default_factory=list)
    items: list[str] = Field(default_factory=list)  # loose components/items on bench
    offered_augments: list[str] = Field(default_factory=list)
    picked_augments: list[str] = Field(default_factory=list)
    carousel_items: list[str] = Field(default_factory=list)  # items on the carousel wheel
    last_result: str = ""  # our outcome of the previous round: victory | defeat
    opponents: list[Opponent] = Field(default_factory=list)
    fought_opponents: list[str] = Field(default_factory=list)  # names in order fought (latest last)

    @property
    def stage_num(self) -> int:
        """Numeric stage for logic gates; 0 when the stage string is malformed."""
        try:
            return int(self.stage.split("-")[0])
        except (ValueError, IndexError, AttributeError):
            return 0

    def next_opponent_candidates(self) -> list[Opponent]:
        """Who we can face next round. TFT matchmaking cycles through the
        lobby: you can't redraw an opponent you fought in the last cycle,
        so candidates = alive rivals not seen in the most recent rounds.
        Falls back to all rivals when data is thin."""
        if not self.opponents:
            return []
        window = max(1, len(self.opponents) - 1)
        recent = set(self.fought_opponents[-window:])
        candidates = [o for o in self.opponents if o.name not in recent]
        return candidates or list(self.opponents)

    def describe(self) -> dict:
        """Compact JSON-friendly view sent to the decision models as `state`."""
        return {
            "stage": self.stage,
            "stage_num": self.stage_num,
            "round_type": self.round_type,
            "level": self.level,
            "gold": self.gold,
            "hp": self.hp,
            "streak": self.streak,
            "board": [u.describe() for u in self.board],
            "bench": [u.describe() for u in self.bench],
            "shop": self.shop,
            "items": self.items,
            "offered_augments": self.offered_augments,
            "picked_augments": self.picked_augments,
            "carousel_items": self.carousel_items,
            "last_result": self.last_result,
            "opponents": [o.describe() for o in self.opponents],
            "fought_opponents": self.fought_opponents,
            "likely_next_opponents": [
                o.describe() for o in self.next_opponent_candidates()
            ],
        }
