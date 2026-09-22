import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "service"))

from tft_advisor.comps import Comp, SourceRating  # noqa: E402
from tft_advisor.questions import FLEX_SLUG, build_questions  # noqa: E402
from tft_advisor.state import GameState, Opponent, Unit  # noqa: E402


def _comps() -> list[Comp]:
    return [
        Comp(
            slug="c1",
            name="Comp One",
            units=["u1", "u2"],
            sources=[SourceRating(site="s", tier="S")],
        ),
        Comp(slug="c2", name="Comp Two", sources=[SourceRating(site="s", tier="B")]),
    ]


def test_comp_question_covers_all_comps_plus_flex() -> None:
    qs = build_questions(GameState(stage="3-2"), _comps())
    comp_q = next(q for q in qs if q.id == "comp")

    assert comp_q.kind == "choice"
    assert set(comp_q.criteria) == {"c1", "c2", FLEX_SLUG}
    assert "S" in comp_q.criteria["c1"]  # consensus tier reaches criteria text


def test_econ_always_asked() -> None:
    qs = build_questions(GameState(), [])
    assert "econ" in {q.id for q in qs}


def test_augment_question_only_when_choice_offered() -> None:
    assert "augment" not in {q.id for q in build_questions(GameState(), _comps())}

    state = GameState(offered_augments=["Aug X", "Aug Y", "Aug Z"])
    aug = next(q for q in build_questions(state, _comps()) if q.id == "augment")
    assert set(aug.criteria) == {"Aug X", "Aug Y", "Aug Z"}


def test_pivot_question_gated_by_stage_and_board() -> None:
    no_board = GameState(stage="4-1")
    assert "pivot" not in {q.id for q in build_questions(no_board, [])}

    early = GameState(stage="2-1", board=[Unit(name="u")])
    assert "pivot" not in {q.id for q in build_questions(early, [])}

    mid = GameState(stage="3-1", board=[Unit(name="u")])
    assert "pivot" in {q.id for q in build_questions(mid, [])}


def test_prep_question_gated_on_opponents_and_stage() -> None:
    # no opponents -> no prep question
    assert "prep" not in {q.id for q in build_questions(GameState(stage="3-2"), _comps())}

    # opponents but stage 1 -> too early to care
    early = GameState(stage="1-3", opponents=[Opponent(name="A")])
    assert "prep" not in {q.id for q in build_questions(early, _comps())}

    # opponents + stage 2 -> asked
    mid = GameState(stage="2-4", opponents=[Opponent(name="A")])
    assert "prep" in {q.id for q in build_questions(mid, _comps())}

    # recently fought opponents are excluded -> prep still fires for remaining
    fought = GameState(
        stage="3-1",
        opponents=[Opponent(name="A"), Opponent(name="B")],
        fought_opponents=["A"],
    )
    prep = next(q for q in build_questions(fought, _comps()) if q.id == "prep")
    assert "likely_next_opponents" in prep.instructions


def test_slam_question_gated_on_bench_items() -> None:
    assert "slam" not in {q.id for q in build_questions(GameState(), _comps())}

    state = GameState(items=["bow", "rod"])
    qs = {q.id: q for q in build_questions(state, _comps())}
    assert "slam" in qs
    assert qs["slam"].kind == "noul"
