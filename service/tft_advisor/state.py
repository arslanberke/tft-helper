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

    def describe(self) -> str:
        board = ", ".join(u.describe() for u in self.units)
        return f"{self.name}: {board}" if board else self.name


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
    opponents: list[Opponent] = Field(default_factory=list)

    def describe(self) -> dict:
        """Compact JSON-friendly view sent to the decision models as `state`."""
        return {
            "stage": self.stage,
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
            "opponents": [o.describe() for o in self.opponents],
        }
