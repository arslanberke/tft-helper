from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Protocol

from .questions import Question


@dataclass
class Answer:
    question_id: str
    kind: str
    distribution: dict[str, float] = field(default_factory=dict)  # choice only
    choice: str | None = None
    score: float | None = None
    noul: float | None = None
    confidence: float = 0.0

    @property
    def top(self) -> str | None:
        return self.choice


@dataclass
class FusedAnswer(Answer):
    agreement: bool = True
    per_engine: dict[str, Answer] = field(default_factory=dict)


class Engine(Protocol):
    """A System-1 decision model: typed questions in, calibrated answers out."""

    name: str

    def decide(self, state: dict, questions: list[Question]) -> dict[str, Answer]: ...


def _one_hot(choice: str, confidence: float, options: list[str]) -> dict[str, float]:
    rest = (1.0 - confidence) / max(len(options) - 1, 1)
    return {o: (confidence if o == choice else rest) for o in options}


def _dist_from(raw: Any, choice: str, confidence: float, options: list[str]) -> dict[str, float]:
    """Per-option probabilities when the SDK exposes them; one-hot otherwise."""
    dist = raw.get("distribution") or raw.get("probabilities") if isinstance(raw, dict) else None
    if isinstance(dist, dict) and dist:
        total = sum(dist.values()) or 1.0
        return {o: dist.get(o, 0.0) / total for o in options}
    return _one_hot(choice, confidence, options)


class LayaEngine:
    """Local System-1 model (`pip install laya`). Free, offline, no key."""

    name = "laya"

    def __init__(self, model: str = "convaiinnovations/laya") -> None:
        import laya  # lazy: heavy torch dep

        self._agent = laya.load(model)

    def decide(self, state: dict, questions: list[Question]) -> dict[str, Answer]:
        qs = {
            q.id: {"type": q.kind, "instructions": q.instructions, "criteria": q.criteria}
            for q in questions
        }
        answers = self._agent.predict(state, qs)["answers"]
        out: dict[str, Answer] = {}
        for q in questions:
            raw = answers[q.id]
            if q.kind == "choice":
                options = list(q.criteria) if isinstance(q.criteria, dict) else []
                conf = float(raw.get("confidence", 0.0))
                out[q.id] = Answer(
                    question_id=q.id,
                    kind="choice",
                    choice=raw["choice"],
                    confidence=conf,
                    distribution=_dist_from(raw, raw["choice"], conf, options),
                )
            elif q.kind == "score":
                out[q.id] = Answer(question_id=q.id, kind="score", score=float(raw["score"]))
            else:
                out[q.id] = Answer(
                    question_id=q.id,
                    kind="noul",
                    noul=float(raw["noul"]),
                    confidence=float(raw["noul"]),
                )
        return out


class JevEngine:
    """Hosted TypeSafe System-1 model (`pip install typesafe-sdk`, TYPESAFE_API_KEY)."""

    name = "jev"

    def __init__(self, model: str = "jev-latest") -> None:
        from typesafe_sdk import TypeSafeClient  # lazy: optional dep

        self._sdk = __import__("typesafe_sdk")
        self._client = TypeSafeClient(model=model)

    def decide(self, state: dict, questions: list[Question]) -> dict[str, Answer]:
        Choice, Noul, Score = self._sdk.Choice, self._sdk.Noul, self._sdk.Score
        qs = {}
        for q in questions:
            if q.kind == "choice":
                qs[q.id] = Choice(instructions=q.instructions, criteria=q.criteria)
            elif q.kind == "score":
                qs[q.id] = Score(instructions=q.instructions, criteria=q.criteria)
            else:
                qs[q.id] = Noul(instructions=q.instructions)
        response = self._client.system_one(state=state, questions=qs)
        out: dict[str, Answer] = {}
        for q in questions:
            raw = response.answers[q.id]
            if q.kind == "choice":
                options = list(q.criteria) if isinstance(q.criteria, dict) else []
                conf = float(getattr(raw, "confidence", 0.0))
                raw_d = {
                    "distribution": getattr(raw, "distribution", None),
                    "probabilities": getattr(raw, "probabilities", None),
                }
                out[q.id] = Answer(
                    question_id=q.id,
                    kind="choice",
                    choice=raw.choice,
                    confidence=conf,
                    distribution=_dist_from(raw_d, raw.choice, conf, options),
                )
            elif q.kind == "score":
                out[q.id] = Answer(question_id=q.id, kind="score", score=float(raw.score))
            else:
                out[q.id] = Answer(
                    question_id=q.id,
                    kind="noul",
                    noul=float(raw.noul),
                    confidence=float(raw.noul),
                )
        return out


class EnsembleEngine:
    """Consensus layer: ask every engine the same questions and fuse the answers.

    Choices fuse per-option probability distributions (weighted mean); noul and
    score fuse the scalar. `agreement` is True when every engine picked the same
    top option — the overlay surfaces disagreement rather than hiding it.
    """

    name = "ensemble"

    def __init__(self, engines: list[Engine], weights: dict[str, float] | None = None) -> None:
        if not engines:
            raise ValueError("EnsembleEngine needs at least one engine")
        self.engines = engines
        self.weights = weights or {}

    def decide(self, state: dict, questions: list[Question]) -> dict[str, FusedAnswer]:
        with ThreadPoolExecutor(max_workers=len(self.engines)) as pool:
            results = dict(
                zip(
                    [e.name for e in self.engines],
                    pool.map(lambda e: e.decide(state, questions), self.engines),
                    strict=True,
                )
            )

        fused: dict[str, FusedAnswer] = {}
        for q in questions:
            per_engine = {name: res[q.id] for name, res in results.items()}
            weights = {n: self.weights.get(n, 1.0) for n in per_engine}
            total_w = sum(weights.values())
            tops = {a.choice for a in per_engine.values()}
            agreement = len(tops) == 1

            if q.kind == "choice":
                options = list(q.criteria) if isinstance(q.criteria, dict) else []
                dist = {
                    o: sum(weights[n] * a.distribution.get(o, 0.0) for n, a in per_engine.items())
                    / total_w
                    for o in options
                }
                choice = max(dist, key=dist.get)
                fused[q.id] = FusedAnswer(
                    question_id=q.id,
                    kind="choice",
                    choice=choice,
                    distribution=dist,
                    confidence=dist[choice],
                    agreement=agreement,
                    per_engine=per_engine,
                )
            elif q.kind == "score":
                score = sum(weights[n] * (a.score or 0.0) for n, a in per_engine.items()) / total_w
                fused[q.id] = FusedAnswer(
                    question_id=q.id, kind="score", score=score,
                    agreement=agreement, per_engine=per_engine,
                )
            else:
                noul = sum(weights[n] * (a.noul or 0.0) for n, a in per_engine.items()) / total_w
                fused[q.id] = FusedAnswer(
                    question_id=q.id, kind="noul", noul=noul, confidence=noul,
                    agreement=agreement, per_engine=per_engine,
                )
        return fused


class MockEngine:
    """Deterministic heuristic engine for end-to-end testing without models.

    Lets you run the service + Overwolf integration before Laya is downloaded
    or a Jev key exists. Enable with TFT_ENGINE=mock. Not for real decisions.
    """

    name = "mock"

    def decide(self, state: dict, questions: list[Question]) -> dict[str, Answer]:
        out: dict[str, Answer] = {}
        owned = {
            (u.get("name") if isinstance(u, dict) else str(u)).lower()
            for u in state.get("board", []) + state.get("bench", [])
        }
        for q in questions:
            if q.kind == "choice":
                options = list(q.criteria) if isinstance(q.criteria, dict) else []
                scores = [self._score(q.id, o, q.criteria or {}, owned, state) for o in options]
                total = sum(scores) or 1.0
                dist = {o: s / total for o, s in zip(options, scores, strict=True)}
                choice = max(dist, key=dist.get) if dist else None
                out[q.id] = Answer(
                    question_id=q.id, kind="choice", choice=choice,
                    distribution=dist, confidence=dist.get(choice or "", 0.0),
                )
            elif q.kind == "score":
                out[q.id] = Answer(question_id=q.id, kind="score", score=1.0)
            else:
                out[q.id] = Answer(question_id=q.id, kind="noul", noul=0.3, confidence=0.3)
        return out

    @staticmethod
    def _score(
        question_id: str,
        option: str,
        criteria: dict[str, str] | list[str],
        owned: set[str],
        state: dict,
    ) -> float:
        if question_id == "econ":
            gold = int(state.get("gold") or 0)
            stage_num = int(str(state.get("stage") or "0").split("-")[0] or 0)
            rules = {"hold": gold >= 50, "level": stage_num >= 4 and gold >= 20, "roll": True}
            return 3.0 if rules.get(option) else 1.0
        if isinstance(criteria, dict):
            text = criteria.get(option, "").lower()
            return 1.0 + sum(1 for name in owned if name and name in text)
        return 1.0


def build_default_engine() -> Engine:
    """Laya always; Jev joins the ensemble when TYPESAFE_API_KEY is set."""
    if os.environ.get("TFT_ENGINE") == "mock":
        return EnsembleEngine([MockEngine()])
    engines: list[Engine] = []
    try:
        engines.append(LayaEngine())
    except ImportError:
        pass
    if os.environ.get("TYPESAFE_API_KEY"):
        try:
            engines.append(JevEngine())
        except ImportError:
            pass
    if not engines:
        raise RuntimeError(
            "No decision engine available: `pip install laya` for the local model "
            "or set TYPESAFE_API_KEY for Jev."
        )
    return EnsembleEngine(engines)
