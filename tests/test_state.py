import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "service"))

from tft_advisor.state import GameState, Unit  # noqa: E402


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
