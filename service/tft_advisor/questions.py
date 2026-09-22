from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .comps import Comp
from .state import GameState

QuestionKind = Literal["choice", "score", "noul"]

FLEX_SLUG = "__flex__"

_ECON_CRITERIA = {
    "roll": "Roll down gold now to hit unit upgrades or key units for the board.",
    "level": "Spend gold on XP to reach the next level and unlock better shop odds.",
    "hold": "Save gold to keep interest / econ thresholds; board is stable enough.",
}


@dataclass(frozen=True)
class Question:
    id: str
    kind: QuestionKind
    instructions: str
    criteria: dict[str, str] | list[str] | None = None


def build_questions(state: GameState, comps: list[Comp]) -> list[Question]:
    """Translate a game snapshot + comp library into System-1 typed questions."""
    questions: list[Question] = []

    if comps:
        criteria = {c.slug: c.describe() for c in comps}
        criteria[FLEX_SLUG] = (
            "None of the named comps fits; strongest play is staying flexible "
            "with the current board instead of forcing a listed comp."
        )
        questions.append(
            Question(
                id="comp",
                kind="choice",
                instructions=(
                    "You are a Challenger-level TFT coach. Given this board, bench, shop, "
                    "items, augments and economy, which composition should the player commit "
                    "to? Downweight comps that opponents are clearly contesting — rival "
                    "boards are listed under opponents."
                ),
                criteria=criteria,
            )
        )

    questions.append(
        Question(
            id="econ",
            kind="choice",
            instructions=(
                "You are a Challenger-level TFT coach. Given the stage, level, gold, HP and "
                "board strength, what is the best economy action right now?"
            ),
            criteria=dict(_ECON_CRITERIA),
        )
    )

    if len(state.offered_augments) >= 2:
        questions.append(
            Question(
                id="augment",
                kind="choice",
                instructions=(
                    "You are a Challenger-level TFT coach. Of the augments currently offered, "
                    "which best fits the player's board direction and likely comp?"
                ),
                criteria={a: "" for a in state.offered_augments},
            )
        )

    if state.board and int(state.stage.split("-")[0] or 0) >= 3:
        questions.append(
            Question(
                id="pivot",
                kind="noul",
                instructions=(
                    "Should the player pivot away from their current board direction? "
                    "Consider contested lines, item fit, and whether a listed comp "
                    "is clearly better."
                ),
            )
        )

    return questions
