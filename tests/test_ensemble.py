import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "service"))

from tft_advisor.engines import Answer, EnsembleEngine, _one_hot  # noqa: E402
from tft_advisor.questions import Question  # noqa: E402

Q_COMP = Question(id="comp", kind="choice", instructions="pick", criteria={"a": "", "b": ""})
Q_NOUL = Question(id="pivot", kind="noul", instructions="pivot?")


class FakeEngine:
    def __init__(self, name: str, answers: dict[str, Answer]) -> None:
        self.name = name
        self._answers = answers

    def decide(self, state: dict, questions: list[Question]) -> dict[str, Answer]:
        return self._answers


def test_fused_choice_averages_distributions_and_flags_disagreement() -> None:
    e1 = FakeEngine("e1", {"comp": Answer("comp", "choice", {"a": 0.8, "b": 0.2}, choice="a")})
    e2 = FakeEngine("e2", {"comp": Answer("comp", "choice", {"a": 0.4, "b": 0.6}, choice="b")})
    fused = EnsembleEngine([e1, e2]).decide({}, [Q_COMP])["comp"]

    assert fused.distribution == pytest.approx({"a": 0.6, "b": 0.4})
    assert fused.choice == "a"
    assert fused.agreement is False
    assert set(fused.per_engine) == {"e1", "e2"}


def test_agreement_true_when_engines_pick_same_option() -> None:
    e1 = FakeEngine("e1", {"comp": Answer("comp", "choice", {"a": 0.9, "b": 0.1}, choice="a")})
    e2 = FakeEngine("e2", {"comp": Answer("comp", "choice", {"a": 0.7, "b": 0.3}, choice="a")})
    fused = EnsembleEngine([e1, e2]).decide({}, [Q_COMP])["comp"]

    assert fused.choice == "a"
    assert fused.agreement is True


def test_noul_is_weighted_mean() -> None:
    e1 = FakeEngine("e1", {"pivot": Answer("pivot", "noul", noul=0.9)})
    e2 = FakeEngine("e2", {"pivot": Answer("pivot", "noul", noul=0.3)})
    fused = EnsembleEngine([e1, e2], weights={"e1": 3.0, "e2": 1.0}).decide({}, [Q_NOUL])["pivot"]

    assert abs(fused.noul - (0.9 * 0.75 + 0.3 * 0.25)) < 1e-9


def test_one_hot_spreads_complement() -> None:
    dist = _one_hot("a", 0.7, ["a", "b", "c"])
    assert dist == pytest.approx({"a": 0.7, "b": 0.15, "c": 0.15})
