import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "service"))

from tft_advisor.state import GameState, Opponent, Unit  # noqa: E402


def test_describe_serializes_compact_state() -> None:
    state = GameState(
        stage="3-2",
        level=6,
        gold=42,
        hp=70,
        board=[Unit(name="Yasuo", star=2, items=["IE", "BT"])],
        bench=[Unit(name="Jinx")],
        shop=["Ahri", "Garen"],
        offered_augments=["Aug A"],
        picked_augments=["Aug B"],
    )
    d = state.describe()

    assert d["stage"] == "3-2"
    assert d["gold"] == 42
    assert d["board"] == ["2* Yasuo [IE, BT]"]
    assert d["bench"] == ["Jinx"]
    assert d["shop"] == ["Ahri", "Garen"]


def _opp(name: str, *units: str) -> Opponent:
    return Opponent(name=name, units=[Unit(name=u) for u in units])


def test_next_opponents_excludes_recently_fought() -> None:
    state = GameState(
        opponents=[_opp("A"), _opp("B"), _opp("C"), _opp("D")],
        fought_opponents=["A", "B"],
    )
    assert {o.name for o in state.next_opponent_candidates()} == {"C", "D"}
    assert state.describe()["likely_next_opponents"] == ["C", "D"]


def test_next_opponents_never_repeats_last_fought() -> None:
    # with 2 rivals you alternate: last fought B -> only A is a valid draw
    state = GameState(
        opponents=[_opp("A"), _opp("B")],
        fought_opponents=["A", "B"],
    )
    assert {o.name for o in state.next_opponent_candidates()} == {"A"}


def test_next_opponents_falls_back_to_all_when_cycle_completes() -> None:
    # a lone rival is always a candidate even right after fighting them
    state = GameState(opponents=[_opp("A")], fought_opponents=["A"])
    assert {o.name for o in state.next_opponent_candidates()} == {"A"}


def test_next_opponents_empty_without_opponents() -> None:
    assert GameState(fought_opponents=["X"]).next_opponent_candidates() == []
