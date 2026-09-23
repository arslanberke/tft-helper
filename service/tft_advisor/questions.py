from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .comps import Comp
from .setdata import annotated
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
                    "to? Each comp lists its 'play when' conditions — prefer the comps whose "
                    "openers, item needs and augment triggers best match the current state. "
                    "Downweight comps that opponents are clearly contesting (rival boards are "
                    "listed under opponents; the ones likely up next are under "
                    "likely_next_opponents), and downweight strong comps whose entry "
                    "conditions are unmet: forcing a comp with no setup loses more LP than "
                    "playing a slightly weaker comp that is already online."
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
                "board strength, what is the best economy action right now? Pick the "
                "contextually optimal line, not a fixed rule — benchmarks are only priors: "
                "hold above 50g for max interest when stable, hit level windows "
                "(3-2 ~lvl 6, 4-1/4-2 lvl 8 with a roll-down, 5-2+ lvl 9), roll early when "
                "the bench holds live pairs, when losses are getting heavy, or just before "
                "the lobby spikes — but override any of these when the board says otherwise. "
                "Unit quality beats an extra slot when 2-stars carry the board; if the "
                "chosen comp is a reroll line, roll at its reroll level. On a win streak "
                "spend to protect it (tempo levels); on a deep loss streak keep banking — "
                "the gold and carousel priority are the comeback, roll only to stop "
                "bleeding HP."
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
                    "which best fits the player's board direction and likely comp? An augment "
                    "that unlocks or completes a strong comp's 'play when' conditions beats a "
                    "generically good one."
                ),
                criteria={a: "" for a in state.offered_augments},
            )
        )

    if state.offered_specials:
        options = list(state.offered_specials)
        # A lone offer is still a decision — skipping keeps the gold/tempo.
        if len(options) == 1:
            options.append("Skip (save gold)")
        questions.append(
            Question(
                id="special",
                kind="choice",
                instructions=(
                    "You are a Challenger-level TFT coach. A patch/set-specific "
                    "shop power-up is offered (anomaly, encounter, special row…). "
                    "Pick the option that most advances a winning line for this "
                    "state — tempo, econ, and how well it fits the player's comp "
                    "direction all count; 'Skip' only when nothing beats holding "
                    "the gold."
                ),
                criteria={s: annotated(s) for s in options},
            )
        )

    if state.board and state.stage_num >= 3:
        questions.append(
            Question(
                id="pivot",
                kind="noul",
                instructions=(
                    "Should the player pivot away from their current board direction? "
                    "Consider contested lines (an uncontested B-tier often outperforms a "
                    "contested S-tier), item fit, unmet 'play when' conditions, and whether "
                    "a listed comp sharing the current units is clearly better."
                ),
            )
        )

    if state.items:
        questions.append(
            Question(
                id="slam",
                kind="noul",
                instructions=(
                    "Should the player slam the components/items sitting on their bench "
                    "right now, or hold them for a better-in-slot combination later? Slam "
                    "high when: the board is bleeding HP and any combat item stabilizes it, "
                    "the player is on a win streak worth protecting with tempo, or an early "
                    "item-holder unit (a comp's item_holders entry) is already on the board "
                    "so items can move to the real carry later. Hold when: key BiS "
                    "components are one piece away and the board is winning anyway, or the "
                    "comp's item plan says it is BiS-dependent. The chosen comp's "
                    "'item plan' and 'item priority' lines describe its preferred policy."
                ),
            )
        )

    if state.last_result:
        questions.append(
            Question(
                id="post_fight",
                kind="noul",
                instructions=(
                    "A fight just resolved — the state's 'last_result' field says whether "
                    "the player won or lost the previous round. Should the player change "
                    "plan in reaction to that result? Score high when the result should "
                    "alter the next decisions: after a loss consider whether the board needs "
                    "immediate power (roll window, slam bench items onto the holder, "
                    "reposition for the likely next opponents) versus staying the course "
                    "because the loss was positioning variance; after a win consider "
                    "protecting the streak with tempo versus greedier econ. Weigh HP, "
                    "gold/level, the win/loss streak, and how strong the likely next "
                    "opponents look. Score low when the correct move is to keep the "
                    "current plan unchanged."
                ),
            )
        )

    informed = [
        o for o in state.next_opponent_candidates() if o.units or o.name
    ]
    if informed and state.stage_num >= 2:
        questions.append(
            Question(
                id="prep",
                kind="noul",
                instructions=(
                    "Given the likely next opponents (listed under "
                    "likely_next_opponents — TFT matchmaking can't redraw the "
                    "recently fought ones), should the player adjust board "
                    "positioning or itemization to prepare? High when a likely "
                    "opponent's comp punishes the current layout (e.g. assassin "
                    "dive vs cornered carries, AoE vs clumping); low when the "
                    "standard positioning already covers it."
                ),
            )
        )

    return questions
